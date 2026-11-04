# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-042 (EP-INT-12) — `C14`: executor is declared per operation,
#           and the page-security policy is GENERATED from the registered
#           browser operations. Screens: every page the SPA serves; S8's card
#           line *the call is made by the browser*.
# Defects:  DEF-INT-4259 (one connection, two hosts — `Operation.host_field`) ·
#           DEF-INT-4261 (the webfont hosts) · **DEF-INT-4287, 2026-09-06 — the
#           policy granted no tile host to any tenant, because nothing creates
#           the connection it was generated from, and the asset map went grey
#           for everyone. `granted()` carries that story.**
# Rules:    BR-INT-048 (a browser-executed operation carries no tenant secret;
#           a page-security policy is generated from the registered browser
#           operations) · BR-INT-003 (no secret reaches the browser) ·
#           BR-INT-037 (data, not code — no provider is named here) ·
#           CLAUDE.md hard rule 1 (a tenant's hosts are read under its own
#           context) · hard-won law 3 (defaults fail closed)
# Tests:    06-backend/tests/test_us_int_042_gis.py (the generated directives,
#           the per-tenant hosts, the unknown-tenant answer)
# Impacts:  apps/integrations/api.py (`GET /integrations/page-policy`) ·
#           apps/integrations/middleware.py (the header on API responses) ·
#           07-frontend/server.mjs (the header on the DOCUMENT, which is the
#           one the browser enforces) · 07-frontend/src/features/assets/
#           AssetMapTab.tsx (the tile host, read from the same connection)
# ───────────────────────────────────────────────────────
"""THE PAGE-SECURITY POLICY, GENERATED — because this repository had none.

WHY THIS FILE EXISTS
---------------------
`US-INT-042` §1 states the gap in one sentence: *"The map draws tiles from the
page, hundreds per pan, and this repository configures no Content-Security-
Policy at all."* That was true at `HEAD` on 2026-09-06 — neither
`07-frontend/server.mjs` nor any Django setting emitted one — so the browser's
own answer to *what may this page fetch* was **anything**.

**The rule is not "add a CSP". It is that the policy is GENERATED from the
registered browser operations** (`BR-INT-048`). Two things follow, and both are
the point:

1. **A host appears in the policy because a manifest declares an operation the
   BROWSER executes and a tenant has connected it** — never because somebody
   typed it into a settings file. Change `map_tiles_public`'s connection to a
   city-run tile server and the policy changes with it, with no second edit.
   That is `R-7`'s case (*"a city that runs its own map server points the same
   operation at the body that already owns the data"*) costing one row.
2. **A host that is not registered is not in the policy**, so the egress a
   `CR-028` §10-D6 ruling ACCEPTED is now bounded by something a browser
   enforces rather than by a comment saying it was accepted.

WHERE IT IS SERVED, AND WHY THERE — the judgment this wave was asked to make
----------------------------------------------------------------------------
`M1` says *"the lane decides where it is served and records why"*. It is served
in **two** places, and they are not redundant:

* **On the DOCUMENT, by `07-frontend/server.mjs`.** This is the one that
  matters. A browser applies a Content-Security-Policy to the document it
  arrived with and to every subresource that document fetches; a header on an
  XHR response governs nothing. The SPA server is the only thing in this
  deployment that serves `index.html`, so it is the only place the enforcing
  header can be set.
* **On API responses, by `middleware.py`.** Cheap, and it makes the generated
  string readable at `GET /integrations/page-policy` and assertable in a test
  without a browser in the loop.

**The document policy is per TENANT**, because the first path segment of every
SPA route is the tenant (`BR-TEN-003`) and two utilities may draw two different
cities' maps (`US-INT-042` TC-7). The SPA server therefore asks this module,
through the API, for the tenant in the path.

⚠ **THE READ IS `AllowAny` AND THAT IS A DELIBERATE, NARROW CHOICE.** A
document is served BEFORE anyone signs in — the sign-in screen is itself a
document — and an SPA does not reload after sign-in, so a policy computed from
an authenticated session would be computed once, on the login page, with no
hosts in it, and the map would be blocked for the rest of the session by a
policy that was correct when it was made. The endpoint therefore answers
without a session. What it discloses is the set of hosts the browser is about
to be told to fetch from, which is a fact any viewer of that page can read out
of their own developer tools a second later. It discloses **no** credential, no
count, no name and no row.

⚠ **AND IT FAILS CLOSED (hard-won law 3) — WITH ONE NAMED EXCEPTION ADDED ON
2026-09-06 BECAUSE THE FIRST READING OF "CLOSED" TURNED THE MAP OFF FOR EVERY
TENANT (`DEF-INT-4287`).** ⚠ **THIS PARAGRAPH READ *"a tenant with no map
connection, a tenant whose connection is switched off, and an unknown tenant
all get the SAME policy"* UNTIL THEN, AND THAT SENTENCE IS THE DEFECT.** The
three cases are not one case:

* **An UNKNOWN tenant** gets `BASE_POLICY` — unchanged, and it is the right
  answer: we know nothing about what that page is allowed to draw.
* **A tenant with NO connection row** gets the **shipped default host** of each
  registered browser operation, because that is the host our own bundle is
  about to fetch from anyway. Refusing it does not stop the fetch — it makes
  the browser refuse it silently, which is a blank grey map and a console line
  nobody reads. `AssetMapTab.tsx` shipped exactly such a fallback and this
  module forbade exactly that host, so the one case the fallback existed for
  was the one case it could never work in.
* **A tenant whose connection is switched off or disabled** gets **nothing**,
  as before — and now the screen draws no tile layer either, so *off* looks
  like a choice rather than like a broken product.

The unsafe answer — a host nobody registered and our own code never calls — is
still the one that has to be earned.

WHAT IS NOT HERE
----------------
No provider is named in this file (`BR-INT-037`) — it walks the registry. And
it grants nothing for a `server` operation: our own outbound calls are made by
our own process, which no browser policy governs, so putting their hosts in a
page policy would be a widening that buys nothing.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from apps.integrations import addressing, live_calls, models
from apps.integrations.registry import BROWSER_EXECUTORS, REGISTRY, Manifest, Registry

#: The directives that never depend on a connection. `'self'` is the origin the
#: SPA and the API share (`server.mjs`'s whole reason to exist), so an app that
#: connects nothing still works completely.
#:
#: ⚠ **`fonts.googleapis.com` AND `fonts.gstatic.com` ARE THIS PRODUCT'S OWN
#: WEBFONT, AND LEAVING THEM OUT BLOCKED IT (`DEF-INT-4261`).**
#: `07-frontend/src/styles/tokens.css` opens with an `@import` of Archivo from
#: Google Fonts. Without the first host the stylesheet is refused; without the
#: second the font files behind it are — and every screen renders in the
#: fallback system font, SILENTLY, because a CSP refusal is a console line and
#: nothing else. They are BASE directives rather than earned hosts because they
#: are not an integration a utility connects: they are how our own bundle is
#: built. Archivo is ratified (`OQ-272` (a), PO 2026-10-20); self-host it
#: (`OQ-272` (b), still open) and these two go with the import.
#:
#: ⚠ `style-src` carries `'unsafe-inline'` and that is NOT laziness — Leaflet
#: positions every tile and marker with an inline `style` attribute, so a
#: policy without it draws a blank grey square and no error a clerk could read.
#: It is recorded here rather than discovered by the next lane wondering why
#: the map is empty. `script-src` does NOT carry it, which is the half that
#: actually stops an injected script.
BASE_DIRECTIVES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("default-src", ("'self'",)),
    ("script-src", ("'self'",)),
    ("style-src", ("'self'", "'unsafe-inline'", "https://fonts.googleapis.com")),
    ("img-src", ("'self'", "data:", "blob:")),
    ("font-src", ("'self'", "data:", "https://fonts.gstatic.com")),
    # CR-169-BRC10 (PO 2026-10-04, answer 2: PostHog US cloud) — the ingest
    # host and the host serving each project's remote config. posthog-js and
    # its recorder are BUNDLED, so `script-src` stays `'self'`. Kept identical
    # to `server.mjs` by `server.test.mjs`.
    ("connect-src", ("'self'", "https://us.i.posthog.com", "https://us-assets.i.posthog.com")),
    # `DEF-INT-4410` — THIS PRODUCT'S OWN DOCUMENTS, and both were `'none'`
    # from the day this policy landed. The two screens that put a bill in front
    # of a person are SAME-ORIGIN embeds: the staff bill's Document tab frames
    # `/api/{tenant}/…/document.pdf` so the browser's own viewer carries print
    # and save (`BR-BIL-036`'s floor), and the portal's `DocumentPreview` shows
    # the kept file in an `<object>`. Under `'none'` a browser draws an empty
    # grey box and says the content is blocked — which is us blocking us, and is
    # what the Product Owner reported on 2026-09-07.
    #
    # `'self'` and NOT `*`: nothing off this origin may be framed or embedded,
    # and a connected provider still has to EARN a host through `granted()`
    # below. (`frame-ancestors` moved to `'self'` in the same fix and for the
    # same reason — it is the OTHER half, and it still refuses every other
    # site.)
    ("frame-src", ("'self'",)),
    ("object-src", ("'self'",)),
    ("base-uri", ("'none'",)),
    ("form-action", ("'self'",)),
    # `DEF-INT-4410`, THE OTHER HALF — and on THIS side it is the whole defect.
    # `frame-src` above is about what a page may frame; `frame-ancestors`
    # travels on the FRAMED RESOURCE and says who may frame it. This policy
    # goes out on every API response (`middleware.PagePolicyMiddleware`),
    # including `GET /invoices/{id}/document.pdf` and the portal's copy of it —
    # so `'none'` refused the product's own page, same origin and all, and
    # Chromium answered `net::ERR_BLOCKED_BY_RESPONSE`.
    #
    # `'self'` and NOT `*`: the SPA and the API are one origin by construction,
    # so this permits exactly this product to embed exactly its own documents
    # and still refuses every other site.
    # ⚠ **NO LONGER ONE ORIGIN — `DEF-INT-9707` (2026-10-05).** Since
    # `CR-144-BRC07` the app and the API are two hosts, so the API's responses
    # add the app origins from `CORS_ALLOWED_ORIGINS` to this directive
    # (`middleware._with_app_ancestors`). This base value is unchanged.
    ("frame-ancestors", ("'self'",)),
)

#: Which directive a browser-executed operation widens, by TRANSPORT — not by
#: provider (`BR-INT-037`). A tile is an image; a hosted card page is a frame;
#: anything else the browser fetches is a connection.
_DIRECTIVE_FOR_CODEC = {"tiles": "img-src"}

#: The operation a basemap comes from, in ANY provider's manifest. Named once
#: here because `_directive_for` and `tile_host` both key off it, and two
#: spellings of it would be the bug this module exists to prevent.
TILE_OPERATION = "map_tiles"

#: Where a granted origin came from — used by `described()` so a screen can
#: tell *the utility chose this* from *this is what we ship*.
SOURCE_CONNECTION = "connection"
SOURCE_DEFAULT = "shipped_default"


def _origin(value: Any) -> str | None:
    """`https://tiles.example/x/y.png` → `https://tiles.example`.

    A CSP source is an ORIGIN. Handing it a whole URL with a path is a source
    expression a browser reads differently from the origin it looks like, so
    the trimming happens here, once, rather than in each caller.
    """
    text = str(value or "").strip()
    if not text:
        return None
    if "://" not in text:
        text = f"https://{text}"
    parts = urlsplit(text)
    if not parts.scheme or not parts.netloc:
        return None
    if parts.scheme not in ("https", "http"):
        return None
    return f"{parts.scheme}://{parts.netloc}"


def browser_operations(
    *, registry: Registry = REGISTRY
) -> tuple[tuple[Manifest, Any], ...]:
    """Every `(manifest, operation)` the VIEWER's browser executes.

    The whole input to the policy, and the reason no provider is named below.
    """
    found: list[tuple[Manifest, Any]] = []
    for manifest in registry.all():
        for operation in manifest.operations:
            if operation.executor in BROWSER_EXECUTORS:
                found.append((manifest, operation))
    return tuple(found)


def _directive_for(operation: Any) -> str:
    if operation.executor == "browser_credentialed":
        # The processor hosts the page and we put it in a frame — PO
        # 2026-09-03, *"they are on Spruce page"*. It is not an image and it is
        # not our fetch.
        return "frame-src"
    if operation.name == TILE_OPERATION or operation.codec in _DIRECTIVE_FOR_CODEC:
        return "img-src"
    return "connect-src"


def granted(tenant_id: Any, *, registry: Registry = REGISTRY) -> list[dict[str, Any]]:
    """Every origin this tenant's browser is permitted, one row per operation.

    `{provider_key, operation, executor, directive, host, source}` — the whole
    input to both the header and to any screen that needs to know WHICH host it
    is about to fetch from. One walk, so the policy and the screen cannot
    disagree about a host; two walks is `DEF-INT-4252` one layer up.

    ⚠ **THE SHIPPED DEFAULT IS GRANTED WHEN A TENANT HAS NO CONNECTION ROW AT
    ALL, AND THAT IS `DEF-INT-4287`.** Until 2026-09-06 this function granted a
    host only for a CONNECTED provider, while `AssetMapTab.tsx` shipped a
    fallback tile host for exactly the tenant that has connected nothing — so
    the one case the fallback exists for was the one case the policy forbade,
    and every tenant's asset map drew a **flat grey rectangle with no error
    anybody could read**. Both files warned about that state in their own
    docstrings; neither asked whether they agreed. A policy that names the host
    our own bundle is about to fetch is not a widening — it is the policy
    telling the truth about what the product does. The genuinely closed answer
    is the one below, and the utility owns it.

    ⚠ **A CONNECTION ROW SUPPRESSES THE DEFAULT, IN EVERY STATE.** Once a
    utility has a row, that row is the answer: switched off or disabled it
    grants NOTHING and the basemap goes away, because otherwise the switch
    would be decorative and the product would quietly go on calling a host the
    utility told it to stop calling.
    """
    pairs = browser_operations(registry=registry)
    if not pairs:
        return []
    keys = {manifest.key for manifest, _ in pairs}
    live: dict[str, list[Any]] = {}
    #: Every key the tenant holds a row for, WHATEVER its state — the set that
    #: decides whether the shipped default is still ours to offer.
    held: set[str] = set()
    for row in models.IntegrationConnection.objects.filter(
        tenant_id=tenant_id, provider_key__in=keys
    ):
        held.add(row.provider_key)
        if row.enabled and row.status != models.STATUS_OFF:
            live.setdefault(row.provider_key, []).append(row)

    out: list[dict[str, Any]] = []
    for manifest, operation in pairs:
        directive = _directive_for(operation)
        # ⚠ **THE OPERATION'S OWN FIELD, AND ONLY THAT (`DEF-INT-4259`).**
        # One connection can hold two hosts — `gis_esri` has an address
        # service our server calls and a tile server the browser draws
        # from — and reading `base_url` for every browser operation put the
        # address service in `img-src` and left the tile server out. A
        # connection with nothing in its declared field contributes NO
        # host, which fails closed.
        #
        # ⚠ **`CR-115-BRC05` MOVED THE READ INTO `addressing.resolve_address`
        # AND KEPT THE RESTRICTION VISIBLE AS ONE ARGUMENT.** The connection
        # view's column climbs a three-rung ladder — the operation's field,
        # then the connector's single address field, then the address we
        # publish. **Granting a browser an origin may climb only the first
        # rung**, because hard-won law 3 says the permissive answer is the one
        # you type, and the second rung is a GUESS between two hosts, which is
        # the whole of `DEF-INT-4259`. `OWN_FIELD_ONLY` is that sentence in
        # code, at the site where it is a security decision, rather than a
        # second private copy of the ladder in this file.
        entry = {
            "provider_key": manifest.key,
            "operation": operation.name,
            "executor": operation.executor,
            "directive": directive,
        }
        origins: list[tuple[str, str]] = []
        for connection in live.get(manifest.key, ()):
            # ⚠ THE RAW `config`, NOT the manifest-filtered settings a screen
            # sees. This function decides what a BROWSER may fetch, and it
            # wants the value exactly as the utility stored it.
            found = addressing.resolve_address(
                manifest,
                operation,
                settings=dict(connection.config or {}),
                allow=addressing.OWN_FIELD_ONLY,
            )
            origin = _origin(found.value)
            if origin is not None:
                origins.append((origin, SOURCE_CONNECTION))
        if manifest.key not in held:
            shipped = addressing.resolve_address(
                manifest,
                operation,
                settings=live_calls.LIVE_CALL_DEFAULTS.get(manifest.key, {}),
                allow=addressing.OWN_FIELD_ONLY,
            )
            default = _origin(shipped.value)
            if default is not None:
                origins.append((default, SOURCE_DEFAULT))
        if not origins:
            out.append({**entry, "host": None, "source": None})
            continue
        for origin, source in origins:
            out.append({**entry, "host": origin, "source": source})
    return out


def hosts_for(tenant_id: Any, *, registry: Registry = REGISTRY) -> dict[str, list[str]]:
    """`directive → the origins this tenant's browser may fetch from`.

    A fold of `granted()` — see it for why a tenant with no connection still
    gets the shipped default and a tenant who switched one off gets nothing.
    """
    out: dict[str, list[str]] = {}
    for row in granted(tenant_id, registry=registry):
        if row["host"] is None:
            continue
        bucket = out.setdefault(str(row["directive"]), [])
        if row["host"] not in bucket:
            bucket.append(row["host"])
    return {directive: sorted(values) for directive, values in out.items() if values}


def tile_host(tenant_id: Any, *, registry: Registry = REGISTRY) -> str | None:
    """The ONE origin the browser draws basemap tiles from, or `None`.

    ⚠ **THE MAP ASKS FOR ITS OWN OPERATION'S HOST BY NAME, NEVER FOR THE FIRST
    ENTRY OF `img-src`.** `img-src` is a DIRECTIVE and can hold several origins
    at once — `map_tiles_public`'s and a city's own tile server both land in
    it — so picking `hosts["img-src"][0]` picks whichever sorted first, which
    is a coin toss dressed as a lookup. `None` means the utility has switched
    the basemap off, and the screen must then draw no tile layer at all: a
    request the policy refuses looks exactly like a broken product.

    A utility's OWN connection beats the shipped default when both are on
    offer, because the whole point of `R-7` is that a city that runs its own
    tile server sees its own tiles.
    """
    rows = [
        row
        for row in granted(tenant_id, registry=registry)
        if row["operation"] == TILE_OPERATION and row["host"] is not None
    ]
    for row in rows:
        if row["source"] == SOURCE_CONNECTION:
            return str(row["host"])
    return str(rows[0]["host"]) if rows else None


def policy(extra: dict[str, list[str]] | None = None) -> str:
    """Render the header value from the base directives plus what was earned.

    ⚠ A directive that gained a host loses `'none'` — `frame-src 'none'
    https://cards.example` is a policy a browser reads as *no frames at all*,
    silently, which is exactly the shape of a check that cannot fail.
    """
    granted = {key: list(values) for key, values in (extra or {}).items()}
    parts: list[str] = []
    for directive, defaults in BASE_DIRECTIVES:
        sources = [one for one in defaults]
        earned = granted.pop(directive, [])
        if earned:
            sources = [one for one in sources if one != "'none'"] + list(earned)
        parts.append(f"{directive} {' '.join(sources)}".strip())
    for directive, earned in sorted(granted.items()):
        if earned:
            parts.append(f"{directive} {' '.join(earned)}")
    return "; ".join(parts)


def policy_for(tenant_id: Any, *, registry: Registry = REGISTRY) -> str:
    """The header value for ONE tenant."""
    return policy(hosts_for(tenant_id, registry=registry))


#: What an UNKNOWN tenant gets, and what a tenant who has switched every
#: browser operation off gets — byte-identically. Named so a caller can fail
#: closed without re-deriving it and without a second definition drifting.
#: ⚠ **A tenant with NOTHING CONNECTED no longer gets this** — it gets the
#: shipped default hosts, which is `DEF-INT-4287`; see `granted()`.
BASE_POLICY = policy()


def described(tenant_id: Any, *, registry: Registry = REGISTRY) -> dict[str, Any]:
    """What `GET /integrations/page-policy` answers.

    `hosts` is beside `policy` on purpose: a test that asserts *exactly the
    registered tile host and nothing else* should not have to parse a header
    string to do it, and a screen that wants to say which host the browser
    calls should not have to either.

    ⚠ **`tile_host` IS THE ANSWER THE MAP READS, AND IT IS HERE RATHER THAN
    DERIVED ON THE SCREEN (`DEF-INT-4287`).** A screen that picks its host out
    of `hosts["img-src"]` is guessing which of several origins is the one it
    means; this key says so, in one place, and `null` means *switched off* and
    not *not answered yet*. Every entry of `browser_operations` now carries its
    own `host` and `source` too, so a support question — *which map server is
    this utility actually calling* — is a field rather than an inference.
    """
    rows = granted(tenant_id, registry=registry)
    directives: dict[str, list[str]] = {}
    for row in rows:
        if row["host"] is None:
            continue
        bucket = directives.setdefault(str(row["directive"]), [])
        if row["host"] not in bucket:
            bucket.append(row["host"])
    directives = {key: sorted(values) for key, values in directives.items() if values}
    return {
        "policy": policy(directives),
        "hosts": directives,
        "tile_host": tile_host(tenant_id, registry=registry),
        "browser_operations": rows,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-042@this-commit (EP-INT-12 story + BR-INT-048/003 verbatim; CR-069 §20.4 wave M)
# generated: 2026-09-06 by the CR-069 wave M build lane · AMENDED 2026-09-06 by the CR-075 map lane (DEF-INT-4287 — `granted()`, the shipped-default grant and `tile_host`)
# checklist: A✔ B✔(server.mjs sets the document header) C✔ D✔(GET /integrations/page-policy) E✔(AssetMapTab reads `tile_host` off THIS payload) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_042_gis.py · the M4 walkthrough reads the header off a real response · def_int_4287 walkthrough: the asset map draws tiles on a tenant that has connected nothing
# exceptions: the read is AllowAny and the docstring says why (an SPA does not reload after sign-in) · `style-src 'unsafe-inline'` is Leaflet's inline positioning and is named rather than left to be rediscovered · a tenant with NO connection is granted the shipped default host — the one place this module is not fail-closed, argued in `granted()` and paid for by `DEF-INT-4287`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
