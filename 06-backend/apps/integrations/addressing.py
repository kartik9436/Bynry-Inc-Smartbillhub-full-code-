# ── Trace ──────────────────────────────────────────────
# Story:    CR-115-BRC05 §6 lane 1 — *"ONE PATH DECIDES AN API'S URL"*, a
#           de-risking refactor with NO behaviour change, done BEFORE the
#           per-API work adds a fourth source.
# Defects:  DEF-INT-5502 (the endpoint column blank on every connector we ship) ·
#           DEF-INT-4259 (one connection, two hosts — the wrong one reached a
#           browser page policy) · DEF-INT-5488 (a `host_field` naming a field
#           the manifest never declares) · DEF-INT-5589 (nineteen *Service
#           address* fields moved from kind `host` to kind `url`) ·
#           DEF-INT-5612 (the screen shows an address three adapters never
#           dial) · DEF-INT-5613 (the set-up screen re-derived it in
#           TypeScript and answered differently) · DEF-INT-5614 (a fourth
#           hardcoded `base_url`, in `live_calls`).
# Rules:    BR-INT-037 (data, never a branch on a provider key; `G77`) ·
#           CLAUDE.md hard-won law 3 (the permissive answer is the one you
#           type) · law 7 (a check that cannot fail; a blind spot with no
#           number beside it) · CR-115-BRC05 §3 risk 2.
# Tests:    06-backend/tests/test_cr115_one_address.py ·
#           10-scripts/cr115_one_address_enumeration.py (the before/after
#           enumeration whose empty diff IS the deliverable) ·
#           10-scripts/gates/g128_one_address_resolver.py
# Impacts:  selectors.py (the ENDPOINT column) · page_policy.py (what a browser
#           may fetch) · live_calls.py · 07-frontend ConnectorSetupPage.tsx and
#           ConnectionDetailPage.tsx, which now READ the served answer instead
#           of deriving one.
# ───────────────────────────────────────────────────────
"""ONE FUNCTION DECIDES WHERE AN OPERATION'S CALL GOES, AND SAYS HOW IT DECIDED.

WHY THIS FILE EXISTS
--------------------
On 2026-09-17 an operation's address was decided in **five** places that did not
agree with one another:

  1. `selectors._operation_row` — the operation's own field, then the
     connector's single address field, then the manifest's `served_path`. This
     is what the ENDPOINT column on the connection view (S142) shows.
  2. `page_policy.granted` — the operation's own field ONLY, deliberately
     failing closed, plus `live_calls.LIVE_CALL_DEFAULTS` for a tenant holding
     no row. This is what a browser is permitted to fetch.
  3. `live_calls.host_for` — a bare `config["base_url"]`, no manifest, no
     operation (`DEF-INT-5614`).
  4. `ConnectorSetupPage.endpointText` in TypeScript — source 1 only, so the
     set-up screen printed a dash on **9 of 91 operations** where the
     connection view printed an address (`DEF-INT-5613`).
  5. The ADAPTERS, each with its own literal — and three of them with no
     literal at all, dialling a compiled-in constant (`DEF-INT-5612`).

`CR-115-BRC05` §3 names the cost: *"a fourth URL source is exactly how it went
blank on every connector before (`DEF-INT-5502`), and how the wrong host reached
a browser page policy (`DEF-INT-4259`)"*. The per-API work is about to add a
fifth — a URL typed per API row — so the sources are collapsed here FIRST.

WHAT THIS FILE CHANGES, AND WHAT IT DELIBERATELY DOES NOT
---------------------------------------------------------
It changes sources 1, 2 and 3 to call `resolve_address` below, and 4 to read
what the server already serves. **The ANSWERS do not move** — that is the
deliverable, and it is proved by enumerating every connector × every operation ×
every config shape and diffing the resolved address before and after
(`10-scripts/cr115_one_address_enumeration.py`).

**It does not touch source 5**, and that is a decision rather than an oversight.
An adapter taking its address from here instead of from a constant would change
where a real call goes, which is a behaviour change on a live money path;
`DEF-INT-5612` carries it.

✅ **THE PER-API BRANCH LANDED ON 2026-09-17 AND THIS PARAGRAPH IS NOW A
RECORD RATHER THAN AN INSTRUCTION.** `CR-115-BRC05` §1.6 (PO R32, *"here
Customer is giving custom URLs … hence we need a form to add them"*) puts a URL
on an API ROW. It was built exactly as this file said to build it — **one more
entry at the top of the ladder with its own source word, `SOURCE_API_ROW`, and
a `row` argument threaded through `resolve_address`** — so nothing else in this
module moved and no caller outside it changed. **A SIXTH SOURCE IS STILL THE
THING THAT MUST NOT HAPPEN, AND `G128` STILL REFUSES ONE.**

⚠ **THIS SENTENCE IS UPDATED IN THE COMMIT THAT BUILT THE THING IT DESCRIBES,
ON PURPOSE.** CLAUDE.md's own most-repeated lesson is that ratifying a rule and
amending the pointer to it are two acts and only the first feels like the work —
B14's rule count has been wrong six times that way. A docstring saying *"it is
lane 2's and is deliberately not here"* about code that IS here would be hard-won
law 1 in its purest form.

THE LADDER, AND WHY IT IS IN THIS ORDER
---------------------------------------
0. **`SOURCE_API_ROW`** — the address a clerk typed on THIS API's own row
   (`CR-115-BRC05` §7). Rung zero because it is the most specific statement
   anybody has made about where this call goes: a clerk who typed an address for
   one API meant that address for that API. Only a CUSTOM row carries one; a
   standard row's `url` is `NULL` and falls straight through to rung 1, because
   the address of an API we ship is the connector's.
1. **`SOURCE_OPERATION_FIELD`** — the value in the config field this operation
   NAMES (`Operation.host_field`). Most specific: a connector holding two
   addresses says per operation which one it dials, which is the whole of
   `DEF-INT-4259`. `gis_esri`'s `map_tiles` names `tile_url` and its two server
   operations name `base_url`.
2. **`SOURCE_CONNECTOR_FIELD`** — the connector's single declared address field,
   when the operation's own names nothing. ⚠ **EXACTLY ONE IS A FALLBACK; TWO
   ANSWERS `None`, DELIBERATELY** (`DEF-INT-4259` again — guessing between two
   hosts put the address service in a browser's `img-src` and left the tile
   server out). Without this rung the column is one that can never show
   anything: all 45 operations took `host_field`'s default of `base_url` and
   not one manifest declared a field of that name (`DEF-INT-5502`).
3. **`SOURCE_SERVED_PATH`** — the address WE publish, for a door a partner
   dials (`out · them`). There is no vendor host in any setting because there is
   no vendor host at all. ⚠ **IT IS LAST, SO A TYPED HOST STILL WINS** — a
   connector that both publishes a door and dials a vendor would otherwise show
   its own address beside the vendor's call, which is `DEF-INT-4259` a third
   time.
4. **`SOURCE_NONE`** — nothing. **No placeholder.** `api.vendor.example` is the
   blueprint's illustration (B14 rule 37) and printing it would tell a clerk we
   call an address we do not call.

THE PROVENANCE IS REQUIRED, NOT DECORATION
------------------------------------------
`CR-115-BRC05` §6: *"The provenance is required: the per-API work must show a
clerk 'using the connector's address' vs 'its own', and a screen re-deriving
that is a second source by another name."* So `ResolvedAddress` carries the
source word and the config key that answered, both travel on the wire as
`endpoint_source` and `endpoint_field`, and no screen ever has to ask which rung
won. A screen that worked it out from `host_field` and `settings` would be
source 4 all over again.

⚠ **`allow` NARROWS THE LADDER; IT DOES NOT REORDER IT.** `page_policy` passes
`OWN_FIELD_ONLY` because granting a browser an origin is a security decision and
hard-won law 3 says the permissive answer is the one you type. That restriction
lives at the call site, in one argument a reviewer can see, rather than as a
second copy of the ladder in `page_policy`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from apps.integrations.registry import ADDRESS_FIELD_KINDS, Manifest, Operation

#: ── `CR-115-BRC05` §7 · THE PER-API ROW, AND IT IS RUNG ZERO ────────────────
#: The value was typed on THIS API's own row by a clerk (`integration_api.url`).
#:
#: ⚠ **IT IS THE MOST SPECIFIC THING THERE IS, SO IT GOES FIRST.** The module
#: docstring above wrote this rung out before it existed — *"That URL is more
#: specific than the operation's own field and therefore goes FIRST, as one
#: more entry at the top of `_LADDER` below with its own source word"* — and
#: this is that entry. A clerk who typed an address for one API means that
#: address for that API; anything else here would be the product overruling
#: them silently.
#:
#: ⚠ **AND IT IS A BRANCH IN THIS FUNCTION RATHER THAN A FOURTH LOOKUP, WHICH
#: IS THE WHOLE OF §7.7.** *"The per-API URL must be ONE BRANCH inside a single
#: resolution function, never a fourth lookup."* It cost twice already:
#: `DEF-INT-5502` (the endpoint column blank on every connector we ship) and
#: `DEF-INT-4259` (the wrong host of two reached a browser page policy, and the
#: City's own map server would have been blocked). `G128` refuses a second
#: resolver and is deliberately not a grep for a function name.
SOURCE_API_ROW = "api_row"
#: The value came from the config field THIS operation names.
SOURCE_OPERATION_FIELD = "operation_field"
#: The value came from the connector's single declared address field.
SOURCE_CONNECTOR_FIELD = "connector_field"
#: The value is the address WE publish for a door a partner dials.
SOURCE_SERVED_PATH = "served_path"

#: `DEF-INT-10020` — where every address we publish is mounted
#: (`config/urls.py` mounts `partner_urls` at `api/`). A manifest's
#: `served_path` is written WITHOUT it (`/partner/v1/bills`), so the served-path
#: rung below puts it back: the endpoint a card shows is the one a System Admin
#: copies into a partner's set-up, and until 2026-10-07 every partner card
#: showed `/partner/v1/…` — an address that answers nothing, because the
#: `/api` the partner must dial was missing from it.
OUR_API_ROOT = "/api"
#: Nothing named an address. A screen draws no endpoint at all.
SOURCE_NONE = "none"

#: The whole ladder, in order. ⚠ **THE ORDER IS THE CONTRACT** — see the module
#: docstring for what each rung costs when it moves.
EVERY_SOURCE: tuple[str, ...] = (
    SOURCE_API_ROW,
    SOURCE_OPERATION_FIELD,
    SOURCE_CONNECTOR_FIELD,
    SOURCE_SERVED_PATH,
)

#: What `page_policy` passes. An origin a browser may fetch from is earned, and
#: a guess between two hosts is `DEF-INT-4259`.
OWN_FIELD_ONLY: tuple[str, ...] = (SOURCE_OPERATION_FIELD,)


@dataclass(frozen=True)
class ResolvedAddress:
    """Where this operation's call goes, and HOW that was decided.

    `value` is `None` — never `""` — when nothing named an address, so a caller
    cannot tell a blank apart from an absence by accident.
    `field` is the config key that answered, or `None` when no config key did.
    """

    value: str | None
    source: str
    field: str | None = None

    @property
    def found(self) -> bool:
        return self.value is not None

    @property
    def is_own(self) -> bool:
        """*Its own* — the words `CR-115-BRC05` §6 asks a clerk to be shown.

        ⚠ **A PER-API ROW IS *ITS OWN* TOO, AND MORE LITERALLY THAN RUNG 1
        IS.** §7.4 draws standard and custom in one list and marks OURS as
        standard; the fact a clerk needs is *whose address is this*, and a URL
        they typed on the row is theirs by definition. Leaving this property
        reading only rung 1 would have made the one row that unambiguously has
        its own address the one row the screen called *the connector's*.
        """
        return self.source in (SOURCE_API_ROW, SOURCE_OPERATION_FIELD)

    @property
    def is_connectors(self) -> bool:
        """*Using the connector's address* — the other half of that sentence."""
        return self.source == SOURCE_CONNECTOR_FIELD


def host_fallback_field(manifest: Manifest) -> str | None:
    """The field this connector actually keeps its address in, when the
    operation's declared `host_field` names nothing.

    ⚠ **WITHOUT THIS THE ENDPOINT COLUMN IS A COLUMN THAT CAN NEVER SHOW
    ANYTHING, WHICH IS WORSE THAN NO COLUMN** (hard-won law 7's *incapable of
    passing*, and the PO's own *"a box that does nothing is worse than no
    box"*). Measured on the running product before this was written: all 45
    registered operations took `host_field`'s default of `base_url`, and **not
    one manifest declared a field called `base_url`** — `email_smtp` keeps its
    address in `host`, `bank_lockbox_file` in `sftp_host`. So the declared
    pointer pointed at nothing on every connector we ship, and the drawn column
    rendered blank on all of them (`DEF-INT-5502`).

    ⚠ **THE FALLBACK IS THE MANIFEST'S OWN FIELD KIND, NEVER A PROVIDER
    BRANCH** (`BR-INT-037`). `Field.kind` is already the registry's word for
    *this is an address*, the same reading `settings_for` uses to decide what is
    a secret. Exactly ONE such field is a fallback; **two is ambiguous and
    answers `None`, because `DEF-INT-4259` is the record of what guessing
    between two hosts costs** — the wrong one went into a security header and
    the city's own map would have been blocked. `CR-115-BRC05` §6 names that
    `None` as deliberate, in as many words; it is not a gap to tidy.

    ⚠ **IT READS `url` AS WELL AS `host`, AND MISSING THAT WOULD HAVE EMPTIED
    THE COLUMN AGAIN (`DEF-INT-5589`).** On 2026-09-17 nineteen *Service
    address* fields moved from `host` to the new `url` kind so a path could be
    typed into them. This function asks the manifest for its single ADDRESS
    field — so had it asked only for kind `host`, the day of that move it would
    have found none on eighteen connectors and answered `None`, restoring the
    exact blank column `DEF-INT-5502` was filed for, silently and with every
    test green. Both kinds mean *this is an address*; that is the reading, and
    it is why they are named together in `ADDRESS_FIELD_KINDS` rather than in
    two branches.

    ⚠ **IT LIVES HERE RATHER THAN IN `selectors` FROM `CR-115-BRC05`** — it is
    a rung of the ladder above and `selectors` is one of four callers, not its
    owner. `selectors.host_fallback_field` re-exports it so no citation and no
    test had to move.
    """
    # ⚠ **A GROUPED FIELD IS NEVER THE CONNECTOR'S ADDRESS (`CR-173-BRC10`).**
    # New World's *Server* belongs to its *Send to City folder* group and to the
    # one operation that names it as `host_field`. Counting it here made it the
    # "single address field" of a connector whose other two rows are OUR
    # addresses, and the screen printed the City's SFTP host under
    # `/partner/v1/receipts` — found by the browser walk, not by a test.
    hosts = [
        one.name
        for one in manifest.fields
        if one.kind in ADDRESS_FIELD_KINDS and not getattr(one, "group", "")
    ]
    return hosts[0] if len(hosts) == 1 else None


def _settings_of(manifest: Manifest, connection: Any) -> Mapping[str, Any]:
    """The connection's non-secret settings, or `{}`.

    Imported inside the function because `selectors` imports THIS module; the
    two would otherwise be a cycle.
    """
    if connection is None:
        return {}
    from apps.integrations.selectors import settings_for

    return settings_for(manifest, connection)


def resolve_address(
    manifest: Manifest,
    operation: Operation,
    connection: Any = None,
    *,
    settings: Mapping[str, Any] | None = None,
    allow: Sequence[str] = EVERY_SOURCE,
    row: Any = None,
) -> ResolvedAddress:
    """Where THIS operation's call goes, on THIS connection, and how we decided.

    `settings` wins when given — `page_policy` hands the raw `connection.config`
    on purpose, because it is deciding what a browser may fetch and it wants the
    value as stored. Otherwise the connection's manifest-filtered settings are
    read, which is what every screen sees.

    ⚠ **THE LADDER IS `or`-SHAPED AND THAT IS LOAD-BEARING.** An empty string is
    not an address, so a field present and blank falls through to the next rung
    exactly as the three separate copies of this chain did before `CR-115`. A
    rewrite using `in settings` instead of truthiness would move rows on every
    connector where a clerk cleared a box, and the enumeration would catch it —
    which is why the enumeration exists.

    `row` is ONE `integration_api` row — a custom API a clerk added
    (`CR-115-BRC05` §7). When it carries a URL that URL wins, because it is the
    most specific statement anybody has made about where this call goes. Pass
    `None` and the ladder is exactly what it was before §7, which is why every
    existing caller needed no change.

    ⚠ **A STANDARD ROW HAS NO URL AND MUST FALL THROUGH, NOT ANSWER.** Its
    `url` is `NULL` on purpose — the address of an API we ship is the
    connector's and belongs on rung 1 or 2. The truthiness test below covers
    both that and a clerk who cleared the box.
    """
    values = settings if settings is not None else _settings_of(manifest, connection)
    permitted = tuple(allow)

    if SOURCE_API_ROW in permitted and row is not None:
        typed = getattr(row, "url", None)
        if typed:
            # ⚠ `field` is None rather than `"url"`: it is the name of a
            # CONFIG key that answered, and no config key did. Naming a column
            # here would send a screen looking for a setting that is not there.
            return ResolvedAddress(str(typed), SOURCE_API_ROW, None)

    if SOURCE_OPERATION_FIELD in permitted:
        own = values.get(operation.host_field)
        if own:
            return ResolvedAddress(str(own), SOURCE_OPERATION_FIELD, operation.host_field)

    if SOURCE_CONNECTOR_FIELD in permitted:
        fallback = host_fallback_field(manifest)
        if fallback:
            shared = values.get(fallback)
            if shared:
                return ResolvedAddress(str(shared), SOURCE_CONNECTOR_FIELD, fallback)

    if SOURCE_SERVED_PATH in permitted and operation.served_path:
        return ResolvedAddress(f"{OUR_API_ROOT}{operation.served_path}", SOURCE_SERVED_PATH, None)

    return ResolvedAddress(None, SOURCE_NONE, None)


def connector_address(manifest: Manifest, connection: Any = None, *, settings=None) -> ResolvedAddress:
    """The CONNECTOR'S address — the question with no operation in it.

    `live_calls.host_for` asks it: *what address has this utility given this
    provider*, with no operation in hand. It answered `config["base_url"]`, a
    literal, which is `DEF-INT-5614` and is the fourth place this repository
    decided an address. Asking the manifest which field holds one gives the same
    answer for both live-call providers — `geocoder_census` and
    `map_tiles_public` each declare exactly one address field and it is called
    `base_url` — and stops being a literal.

    Two or zero address fields answer `None`, for the reason
    `host_fallback_field` gives: a connector with two addresses has no single
    *the* address, and inventing one is what `DEF-INT-4259` cost.
    """
    values = settings if settings is not None else _settings_of(manifest, connection)
    field = host_fallback_field(manifest)
    if not field:
        return ResolvedAddress(None, SOURCE_NONE, None)
    value = values.get(field)
    if not value:
        return ResolvedAddress(None, SOURCE_NONE, None)
    return ResolvedAddress(str(value), SOURCE_CONNECTOR_FIELD, field)


__all__ = [
    "EVERY_SOURCE",
    "OWN_FIELD_ONLY",
    "SOURCE_API_ROW",
    "SOURCE_CONNECTOR_FIELD",
    "SOURCE_NONE",
    "SOURCE_OPERATION_FIELD",
    "SOURCE_SERVED_PATH",
    "ResolvedAddress",
    "connector_address",
    "host_fallback_field",
    "resolve_address",
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 §6 lane 1 @ 40499dd5 (the pinned tip)
# generated: 2026-09-17 by the CR-115-BRC05 lane 1 one-address refactor
# checklist: A✔ B✔(both integrations screens read the served answer) C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: 10-scripts/gates/g128_one_address_resolver.py · pytest tests/test_cr115_one_address.py · 10-scripts/cr115_one_address_enumeration.py (empty diff)
# exceptions: the ADAPTERS still read their own literals — DEF-INT-5612, deliberately out of a no-behaviour-change refactor
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
