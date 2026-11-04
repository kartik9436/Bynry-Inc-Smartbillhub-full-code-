# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-001 (EP-INT-01) — S8's card grid data source. US-INT-004 —
#           the consumer read-model (this is it; consumers never touch the
#           tables). US-INT-013 — every manifest joined to THIS tenant's state.
#           US-INT-018 — `operations[]` per connection, each with its own state.
#           Screens: S8
# Rules:    BR-INT-002 (`GET /integrations` is the grid's read) · BR-INT-003
#           (masked refs only — no payload leaves this module) · BR-INT-004 (a
#           provider-agnostic seam — nothing here branches on a provider key) ·
#           BR-INT-028 (a provider with several operations carries NO aggregate
#           word) · BR-INT-037 (the seventeen come from the registry, none from
#           code here or in React) · CLAUDE.md hard rule 1 (reads run under the
#           request's tenant context; the tenant filter is the second guard)
# Tests:    06-backend/tests/test_us_int_001_grid.py · tests/test_us_int_018_operations.py
#           · tests/test_us_int_013_registry.py (TC-1 · TC-7)
# Impacts:  apps/integrations/api.py (serves this) ·
#           07-frontend/src/api/integrationsEndpoints.ts (types it) ·
#           07-frontend/src/features/integrations/IntegrationsTab.tsx (draws it)
# ───────────────────────────────────────────────────────
"""integrations read side — the grid read-model, and the state words it computes.

ONE READ, SEVENTEEN CARDS, THIS TENANT ONLY
-------------------------------------------
`grid(tenant_id)` walks `REGISTRY.all()` in registration order and joins each
manifest to the connection rows THIS tenant holds for it (one per environment)
and to the latest finished run per `(connection, operation)`. A tenant with no
connections gets seventeen providers, every one `not_set_up` — that is the
truth of the table, and it is the same seventeen for every tenant (US-INT-013
TC-7: J. Okafor of Lone Star Ridge sees nothing of Brazos Bend, because the
read runs under Lone Star Ridge's tenant context and RLS FORCE hides the rest;
the explicit `tenant_id` filter is the second guard for SQLite, which has no
RLS).

THE STATE WORDS, AND WHERE EACH COMES FROM
------------------------------------------
* A provider with NO connection: `not_set_up`, for the card and every operation.
* A connection with `enabled = False`: `off` (*Turned off*), for all of them.
* An operation with no finished run yet: `untested` (*Not tested yet*).
* The latest finished run decides the operation's word — `succeeded` and
  `partial` → `working`; `failed` → `not_working`. ⚠ `unconfirmed` and
  `indeterminate` read `not_working` HERE and their honest outcome travels
  beside the word in `last_outcome`; wave C (US-INT-021, *the word for not
  knowing*) owns the screen sentence for those and revisits this line.
* The CONNECTOR's word (`display_state`): **the connection's own status, on
  every row, whatever the API count** — never an operation's, and never an
  average of them. ⚠ It substituted the operation's word on a ONE-API provider
  until 2026-09-17 (`DEF-INT-5597`); `BR-INT-028`'s grid half had already been
  narrowed on 2026-09-16 (`DEF-INT-5528`) so that every card carries its own
  word, and this line lagged it. The PO's reading is the reason and it is
  narrower than *the connector*: *"Connector status is with respect ot partner
  and that tenant"* — the pair (this utility, this partner), which is exactly
  what a `connection` row IS. `state` on the wire is the same status, for the
  button map, and the per-API detail lives in `operations[]` and the APIs
  column (`BR-INT-028`, untouched: each operation still reports its own).
* `display_state` adds the ONE computed value the status enum does not hold:
  `reading_from_us`, for a connection whose operations are all the partner's
  reads of us (`out · them`) and that has at least one `inbound_read` run. It
  is not a synonym for working: nothing of ours ran, so we can only say that
  somebody has been reading, and when (08-screen-layouts.md S8, state 6).

WHAT NEVER LEAVES THIS MODULE
-----------------------------
No `payload_enc`, ever — the credential table is not even queried for its
payload column. The wire carries `credential_hint` (`••••3F9A`), `expires_at`
and the version number, which is what a card and S142 need (BR-INT-003).
`provider_error` is served ONLY inside the owning tenant's read, which this is.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from django.db.models import Max
from django.utils import timezone

from apps.integrations import (
    addressing,
    custom_apis,
    expiry,
    machine_auth,
    mappings,
    models,
    services,
)
from apps.integrations.adapters.base import ConnectionView
# ⚠ **THE ADDRESS LADDER LIVES IN `addressing` FROM `CR-115-BRC05`, AND THIS
# MODULE IS ONE OF FOUR CALLERS RATHER THAN ITS OWNER.** `host_fallback_field`
# is re-exported below so every existing citation and test keeps working; the
# chain that used to be written out inside `_operation_row` is now one call.
from apps.integrations.addressing import host_fallback_field
from apps.integrations.registry import (
    REGISTRY,
    Manifest,
    Operation,
    Registry,
)
# ⚠ `runners.serve` IS THE ONE PLACE THE INBOUND CEILING IS DECIDED, so the
# RATE LIMIT column reads it from there rather than restating 100 here. A
# number restated in a second file is a number that drifts (hard-won law 1),
# and this is the direction the PO's ruling is actually about. `serve` imports
# models, services, adapters and registry and NOT this module, so there is no
# cycle — checked rather than assumed.
from apps.integrations.runners import serve

#: The computed sixth display word — never a value of `integration_connection.status`.
DISPLAY_READING_FROM_US = "reading_from_us"

#: Wave D (US-INT-037): S143's read lives in `mappings.py`; reachable from
#: here so the read ring has one door.
mappings_view = mappings.view


def _connections_for(tenant_id: Any) -> dict[str, list[models.IntegrationConnection]]:
    """This tenant's connection rows, keyed by provider, production first."""
    by_key: dict[str, list[models.IntegrationConnection]] = {}
    rows = (
        models.IntegrationConnection.objects.filter(tenant_id=tenant_id)
        .select_related("connected_by")
        .order_by("provider_key", "environment")
    )
    for row in rows:
        by_key.setdefault(row.provider_key, []).append(row)
    for rows_for_key in by_key.values():
        rows_for_key.sort(key=lambda one: 0 if one.environment == "production" else 1)
    return by_key


def _latest_runs(connections: Iterable[models.IntegrationConnection]) -> dict[tuple, Any]:
    """The latest FINISHED run per (connection_id, operation) — one query for
    the timestamps, one for the rows, so seventeen cards cost two reads."""
    ids = [one.id for one in connections]
    if not ids:
        return {}
    latest = (
        models.IntegrationRun.objects.filter(connection_id__in=ids, finished_at__isnull=False)
        .values("connection_id", "operation")
        .annotate(latest=Max("finished_at"))
    )
    wanted = {(one["connection_id"], one["operation"]): one["latest"] for one in latest}
    if not wanted:
        return {}
    rows = models.IntegrationRun.objects.filter(
        connection_id__in=ids,
        finished_at__in=list(set(wanted.values())),
    )
    found: dict[tuple, Any] = {}
    for run in rows:
        key = (run.connection_id, run.operation)
        if wanted.get(key) == run.finished_at:
            found[key] = run
    return found


def _has_inbound_read(connections: Iterable[models.IntegrationConnection]) -> set[Any]:
    ids = [one.id for one in connections]
    if not ids:
        return set()
    return set(
        models.IntegrationRun.objects.filter(
            connection_id__in=ids, direction=models.RUN_DIRECTION_INBOUND_READ
        )
        .values_list("connection_id", flat=True)
        .distinct()
    )


def _credential_hints(connections: Iterable[models.IntegrationConnection]) -> dict[Any, dict]:
    """Version, hint and expiry of the ACTIVE credential — never the payload.
    `.values()` names the columns, so `payload_enc` is not even read."""
    ids = [one.id for one in connections]
    if not ids:
        return {}
    rows = models.IntegrationCredential.objects.filter(
        connection_id__in=ids, is_active=True, slot=models.CREDENTIAL_SLOT_PRIMARY
    ).values("connection_id", "version", "masked_hint", "expires_at")
    return {
        one["connection_id"]: {
            "version": one["version"],
            "hint": one["masked_hint"],
            "expires_at": one["expires_at"],
        }
        for one in rows
    }


def operation_state(
    connection: models.IntegrationConnection | None, run: models.IntegrationRun | None
) -> str:
    """The word for one operation — see the module docstring for the table."""
    if connection is None:
        return models.STATUS_NOT_SET_UP
    if not connection.enabled:
        return models.STATUS_OFF
    if run is None or run.outcome not in models.FINISHED_OUTCOMES:
        return models.STATUS_UNTESTED
    if run.outcome in (models.OUTCOME_SUCCEEDED, models.OUTCOME_PARTIAL):
        return models.STATUS_WORKING
    # failed · unconfirmed · indeterminate — wave C (US-INT-021) owns the
    # honest sentence for the last two; the outcome word travels beside this.
    return models.STATUS_NOT_WORKING


def display_state(
    manifest: Manifest,
    connection: models.IntegrationConnection | None,
    operation_states: list[str],
    has_inbound_read: bool,
) -> str:
    """**THE CONNECTOR'S OWN WORD — NEVER AN API'S, WHATEVER THE API COUNT.**

    ⚠ **THIS SUBSTITUTED THE OPERATION'S STATE ON ANY ONE-API CONNECTOR UNTIL
    2026-09-17 (`DEF-INT-5597`).** Product Owner, verbatim, looking at the
    connector TABLE: *"Here in Table - State - it should be for conenctor not
    for APis - you are showing the wrong status"* — and, on what the word
    MEANS: *"Connector status is with respect ot partner and that tenant - so
    it will be tenant /utility speicific"*. **That second sentence is the
    reasoning and it is stronger than the duplication:** `connection.status` is
    the only value on the row scoped to the pair (this utility, this partner).
    An operation's state is a fact about ONE API, so substituting it answers a
    different question under a heading that promises this one.

    ⚠ **IT WAS CORRECT ON THE CARD AND THE CARD IS GONE.** When one API *was*
    the whole connector there was no APIs column to contradict it. The table
    has one, so on 2026-09-17 `Custom SMTP` read *● Not working* in State with
    `1 · 0 working` beside it — the same fact printed twice, one of them wrong
    about its own subject, because that connector had never been TESTED and its
    status was `untested`. `BR-INT-028`'s grid half was already narrowed on
    2026-09-16 (`DEF-INT-5528`) so that every card carries its own
    `display_state`; this line was the last remnant of the older reading and
    nobody re-asked it. **A ruling landed and the code contradicting it did not
    move** — the shape `CLAUDE.md` records against itself.

    ⚠ **THE THREE REMAINING BRANCHES ARE UNCHANGED AND EACH IS STILL THE
    CONNECTOR'S OWN FACT:** no connection at all → `not_set_up` · the
    connection turned off → `off` · a partner-read connector somebody has read
    from → the computed `reading_from_us`, which is the one value the status
    enum does not hold and is never stored.

    ⚠ **`operation_states` IS STILL A PARAMETER AND IS DELIBERATELY UNUSED
    HERE.** It is read by nothing in this function on purpose; the APIs column
    is where an operation's state belongs and it computes its own. Removing the
    parameter would be a wider change to every caller than this defect needs,
    and leaving it named is what tells the next reader the omission is a
    decision rather than an oversight.

    ⚠ **`CR-115-BRC05` §7.5 RULE 4 ASKS THAT THE STATE WORD COUNT ONLY ENABLED
    APIs, AND THIS FUNCTION ALREADY OBEYS IT BY COUNTING NONE.** *"a connector
    is not Not working because of one you turned off"* — it cannot be, because
    since `DEF-INT-5597` the word is `connection.status` and no operation's
    state reaches it. **So rule 4 needs NOTHING here, and the only way to get it
    wrong is to add something**: a lane that "implemented" rule 4 by filtering
    operation states into this function would have rebuilt the aggregate
    `DEF-INT-5597` removed and broken rule 5 — *"Do NOT undo `DEF-INT-5597`"* —
    in the act of obeying rule 4. Rule 4's live half is the *Working N of M*
    tile, which filters on the `enabled` flag `_operation_row` serves.

    ⚠ **THE MIRROR IS A SEPARATE, OPEN DEFECT AND THIS FUNCTION CANNOT FIX IT**
    (`DEF-INT-5598`): `connection.status` is moved by an explicit test, by a
    credential change and by three CONSECUTIVE TIMEOUTS opening the breaker —
    and **by nothing else**. A run that fails because the provider ANSWERED
    unhappily leaves it exactly where it was, so a connector tested once and
    failing nightly ever since still reads *Working*. That is a defect in what
    WRITES the column, not in what reads it, and it is filed rather than
    smuggled in here.
    """
    if connection is None:
        return models.STATUS_NOT_SET_UP
    if not connection.enabled:
        return models.STATUS_OFF
    all_partner_reads = all(
        one.direction == "out" and one.initiative == "them" for one in manifest.operations
    )
    if all_partner_reads and has_inbound_read:
        return DISPLAY_READING_FROM_US
    return connection.status


# ⚠ **`host_fallback_field` MOVED TO `apps/integrations/addressing.py` IN
# `CR-115-BRC05` AND IS IMPORTED ABOVE.** It is a rung of one address ladder,
# and this module was the third of five places that decided an address. The
# whole docstring — what `DEF-INT-5502` measured, why exactly one field is a
# fallback and two answer `None` per `DEF-INT-4259`, why `url` counts as well
# as `host` per `DEF-INT-5589` — travelled with it rather than being summarised
# here, because a summary of a rule is the thing that goes stale.


def _operation_row(
    op: Operation,
    connection,
    run,
    settings: Mapping[str, Any] | None = None,
    manifest: Manifest | None = None,
    api_row: Any = None,
    *,
    enabled: bool = True,
) -> dict[str, Any]:
    """One API on this connection as a screen may see it — OURS or THEIRS.

    ⚠ **THE FIFTH ARGUMENT WAS `host_fallback: str | None` UNTIL
    `CR-115-BRC05`, AND IT IS NOW THE MANIFEST.** Handing in a pre-computed rung
    of the address ladder made this function a place the ladder was partly
    decided; handing in the manifest lets `addressing.resolve_address` decide
    all of it, in one place — which is where the per-API URL went.

    ⚠ **`api_row` IS A CUSTOM API A CLERK ADDED** (`CR-115-BRC05` §7.4 — *"ours
    and theirs in ONE list, ours marked as standard"*). It borrows this
    operation's CODE and direction and trigger, because that is precisely what
    a Kind is — *"the KIND is ours, the NAME is theirs"* — and overrides only
    the two things that are the clerk's: the NAME and the ADDRESS. The address
    override is not applied here; it is `resolve_address`'s rung zero, so this
    function still asks exactly one question of exactly one resolver (§7.7,
    `G128`).
    """
    address = (
        addressing.resolve_address(manifest, op, settings=settings or {}, row=api_row)
        if manifest is not None
        else addressing.ResolvedAddress(None, addressing.SOURCE_NONE, None)
    )
    return {
        "name": op.name,
        "label": op.label,
        # ── CR-115-BRC05 §7 · WHICH API THIS ROW IS ────────────────────────
        # ⚠ **`api_id` IS A HANDLE FOR AN ACTION AND NEVER A VISIBLE VALUE**
        # (B14 rule 31 — *"no database id is ever the visible value of a
        # field"*). `_connection_row` serves `id` under the same rule and the
        # same comment. `null` on a standard row, which HAS no stored row until
        # somebody touches its switch.
        "api_id": None if api_row is None else str(api_row.id),
        # OURS or THEIRS. The screen marks ours as standard; it does not infer
        # it from whether a name happens to differ from a label.
        "is_standard": api_row is None,
        # The clerk's own name, or `None` where the manifest's label is the
        # name. Two fields rather than one overwritten `label`, so a screen can
        # show *their* name without losing *which of ours* it runs.
        "custom_name": None if api_row is None else api_row.name,
        # WHAT KIND OF CALL THIS IS, from the closed list we ship. `None` on a
        # connector that offers none — twenty-seven of twenty-eight today.
        "api_kind": (
            None if manifest is None else custom_apis.kind_of(manifest.key, op.name)
        ),
        # ── §7.5 rule 3 · A DISABLED API IS NOT SCHEDULED AND NOT CALLED ───
        # ⚠ **THE SCREEN DRAWS THIS SWITCH AND THE RUNNERS OBEY IT** —
        # `gis.search` drops a disabled lookup, `gis.reconcile` refuses a
        # disabled sync. Serving it without those would be hard-won law 2's
        # mirror exactly: a control that renders and changes nothing looks
        # identical to a working one.
        "enabled": bool(enabled),
        "description": op.description,
        "direction": op.direction,
        "initiative": op.initiative,
        "state": operation_state(connection, run),
        # ── CR-110-BRC04 wave B · the RESOLVED endpoint and the rate limit ──
        # ⚠ **`trigger` IS NOT REPEATED HERE — WAVE A ALREADY SERVES IT BELOW,
        # AND A SECOND `"trigger"` IN THIS LITERAL WOULD BE LEGAL PYTHON THAT
        # SILENTLY WINS.** This wave was built from a branch point before wave
        # A landed and re-derived onto the tip at push time, which is exactly
        # when law 11 says to look; the duplicate key existed for about a
        # minute and nothing in the suite could have seen it.
        #
        # `endpoint` is the RESOLVED address and `host_field` below is the NAME
        # of the field that holds it. Both travel, on purpose and not by
        # accident: wave A's set-up screen walks the name itself, and this page
        # needs the value.
        #
        # ⚠ **THE LADDER — the operation's own field, then the connector's
        # single address field, then the address WE publish — MOVED TO
        # `apps/integrations/addressing.py` IN `CR-115-BRC05`, WHICH IS WHY
        # THESE THREE LINES ARE ONE CALL.** It was written out here, again in
        # `page_policy`, again in `live_calls` and a fourth time in TypeScript,
        # and the four did not agree: the set-up screen printed a dash on 9 of
        # 91 operations where this column printed an address (`DEF-INT-5613`).
        # Why each rung is where it is — `DEF-INT-5502`'s blank column,
        # `DEF-INT-4259`'s two hosts, `BR-INT-037`'s data-not-branches — is in
        # that module's docstring rather than paraphrased here.
        #
        # ⚠ **THE PER-API URL GOES INTO THAT LADDER AND NOT INTO THIS LINE**
        # (`CR-115-BRC05` §1.6, lane 2). `G128` refuses a second resolver.
        "endpoint": address.value,
        # ── CR-115-BRC05 lane 1 · HOW the address above was decided ─────────
        # `operation_field` · `connector_field` · `served_path` · `none`, plus
        # the config key that answered. ⚠ **A SCREEN MUST NEVER WORK THIS OUT
        # FOR ITSELF**: the per-API work has to tell a clerk *using the
        # connector's address* apart from *its own*, and a screen re-deriving
        # that from `host_field` and `settings` is a second source by another
        # name — which is exactly what `DEF-INT-5613` was.
        "endpoint_source": address.source,
        "endpoint_field": address.field,
        # RATE LIMIT. Display only — PO 2026-09-16, *"we cant allow clark to
        # reset it … keep the check in code - thats it"*. No input, no Save.
        #
        # ⚠ **A NUMBER ONLY WHERE ONE IS REALLY ENFORCED, AND A DASH EVERYWHERE
        # ELSE.** `check_rate_limit` guards ONE direction: a partner calling
        # OUR endpoints, which is `initiative == "them"`. Nothing throttles the
        # calls WE place at a vendor, so an outward row answers None and the
        # screen draws a dash — printing the inbound ceiling beside an outbound
        # call would be a limit that does not exist (hard-won law 1).
        # ⚠ **THE OPERATION IS NAMED, AND IT WAS NOT** (`CR-110-BRC04` phase 2).
        # `rate_limit_for` reads three sources in order — the tenant's own row,
        # the connection's config, then THE MANIFEST'S DECLARED DEFAULT FOR THIS
        # OPERATION — and the third one is reachable only when the operation is
        # passed. Called without it, this column skipped straight from an absent
        # config value to `DEFAULT_RATE_LIMIT_PER_MINUTE`, so **every connector
        # that declares its own ceiling displayed 100 while the door enforced
        # what the manifest said** (`check_rate_limit` has always passed the
        # operation). Aclarian ships 60; the screen read 100. A limit nobody may
        # edit from a screen, displayed wrongly on the one screen that shows it,
        # is hard-won law 1 in a table column.
        #
        # ⚠ **AND A CARD WITH NO CONNECTION YET SHOWS THE MANIFEST'S NUMBER
        # RATHER THAN A DASH.** Before a clerk connects there is no row and no
        # config, so the only true answer is the default this connector ships —
        # which is exactly what a clerk deciding whether to connect wants to
        # read. `rate_limit_for` needs a connection for its first two sources,
        # so the manifest value is read directly here.
        "rate_limit_per_minute": (
            None
            if op.initiative != "them"
            else (
                serve.rate_limit_for(connection, op.name)
                if connection is not None
                else op.rate_limit_per_minute
            )
        ),
        "last_run_at": run.finished_at if run is not None else None,
        "last_outcome": run.outcome if run is not None else None,
        "trace_id": run.trace_id if run is not None else None,
        # Wave B (BR-INT-019): what `test()` does, in the manifest's words, or
        # None — the card then reads *cannot be tested until first use*.
        "test_action": op.test_action,
        "test_needs_recipient": op.test_needs_recipient,
        # ── CR-069 wave M (US-INT-042, `C14` / `BR-INT-048`) ────────────────
        # WHO PLACES THE CALL. `server` is our process; `browser` is the
        # viewer's, carrying no tenant secret; `browser_credentialed` is the
        # page the processor hosts (PO 2026-09-03, *"they are on Spruce
        # page"*). The card reads *the call is made by the browser* off this,
        # and the test modal offers the page's reach separately from the
        # server's — neither by branching on a provider (`BR-INT-037`).
        "executor": op.executor,
        # `C15` — an INLINE operation has a budget instead of a job, so a
        # screen reading these rows knows not to offer a poll. `None` on every
        # other kind, which is the honest answer rather than a default.
        "latency_budget_ms": op.latency_budget_ms,
        # `C16` — `offer` means the answer is SHOWN and nothing is written
        # until a person picks a row.
        "result_disposition": op.result_disposition,
        # ── CR-110-BRC04 wave A — the set-up screen's WHEN and ENDPOINT ─────
        # Two facts that have been on the manifest since wave B and have never
        # reached a screen, because nothing serialised them. `S147` draws both
        # as columns (the blueprint's `CFG-nn` frames, `WHEN` and the host
        # under `API · ENDPOINT`), and without these two lines each renders as
        # a dash on all 28 connectors — a column of nothing, forever, with
        # every test green. That is hard-won law 2 pointing the other way: G13
        # asks whether a prop has a caller and nothing asks whether a DECLARED
        # field has a reader.
        #
        # ⚠ **NEITHER IS ONE OF THE THREE CONTROLS ANOTHER LANE OWNS.** The
        # call limit, the nightly hour and the key's scope are that lane's, and
        # none of them is here: `trigger` and `host_field` are manifest data
        # this module already loads, validates and stores.
        #
        # `trigger` is the vendor's, per operation — `manual` · `scheduled` ·
        # `dispatcher` · `webhook` · `partner` · `inline`. The screen turns it
        # into the drawn words (*Nightly* · *On demand* · *When queued* ·
        # *While you wait*); the enum never reaches a clerk.
        "trigger": op.trigger,
        # ⚠ `host_field` NAMES WHICH CONFIGURED FIELD HOLDS THE HOST — it is
        # not the host. 15 of 18 manifests name `base_url` and do not declare
        # it, so for those the screen finds nothing on the connection and draws
        # no endpoint at all, which is the honest answer. That gap is
        # `DEF-INT-5488` and is NOT closed by this line; serving the name is
        # what lets a screen look, and the manifests are what have to declare
        # the field. **Nothing here invents `api.vendor.example`** — B14 rule
        # 37: a figure drawn in a wireframe is an illustration.
        "host_field": op.host_field,
        # ── 2026-09-17 · `CR-115-BRC05` R31 — does this row get a RUN NOW? ───
        # PO, verbatim: *"i dont have Run button here"*.
        #
        # ⚠ **THE SERVER DECIDES, AND THE ALTERNATIVE WAS A LIVE BUTTON OVER A
        # DEAD DOOR.** A screen could read the shape off this very row —
        # *inbound, ours, scheduled, server-executed* — and FIVE shipped
        # connectors declare that shape with no service behind them. The
        # button would render, a clerk would press it, and the route would
        # answer the plain 404 an invented provider gets: hard-won law 2's
        # mirror, a live control that refuses.
        #
        # ⚠ **AND IT IS A MEMBERSHIP TEST AGAINST A MAP, NOT A BRANCH ON A
        # PROVIDER KEY** (`G77`, whose own docstring says a mapping keyed by
        # provider is the declarative form). The map is `gis.RUN_NOW_OPERATIONS`
        # and it sits beside the runner, so a second run-now operation is added
        # where its runner is.
        #
        # Imported inside the call: `gis` imports `services`, and a
        # module-level import here would tie this module's load order to the
        # runner's for one boolean.
        "can_run_now": _can_run_now(connection, op),
    }


def _can_run_now(connection, op: Operation) -> bool:
    """`True` only where a CONNECTED connection has a service behind this row.

    Not connected is `False` for the same reason *Keys* is absent where we issue
    none: a door onto an empty room is worse than no door.
    """
    if connection is None:
        return False
    from apps.integrations import gis

    return gis.can_run_now(str(connection.provider_key), op.name)


def describe_line(
    manifest: Manifest, connection: models.IntegrationConnection, registry: Registry
) -> str:
    """The masked line on the card (US-INT-015 `describe()`): the adapter's
    when one is bound, else the label or the provider's name. Never a secret
    — the adapter is handed a view with no credential on it."""
    adapter_cls = registry.adapter_for(manifest.key)
    if adapter_cls is not None:
        view = ConnectionView(
            provider_key=connection.provider_key,
            environment=connection.environment,
            config=dict(connection.config or {}),
            label=connection.label,
        )
        return adapter_cls().describe(view)
    return connection.label or manifest.display_name


def settings_for(
    manifest: Manifest, connection: models.IntegrationConnection
) -> dict[str, Any]:
    """The connection's own SETTINGS — every field the manifest does not call a
    secret, and not one it does (`CR-069` wave J).

    ⚠ **THE FILTER IS THE MANIFEST'S AND NEVER A LIST TYPED HERE.** `Field.kind`
    already decides what a secret is (`secret`, `issued_secret`), which is the
    same reading `adapters.base.split_fields` uses on the way IN. One reading,
    two directions: a field that cannot be written into `config` cannot be read
    out of it either, and a manifest that adds a secret field is protected on
    both paths without anybody remembering to edit a second list.

    ⚠ **AND AN UNKNOWN KEY IS DROPPED RATHER THAN PASSED THROUGH.** A `config`
    holding a name the manifest no longer declares is a leftover from an older
    shape, and serving it would put a value on a screen that no field slot can
    place — B14 rule 31's neighbouring failure. What the manifest declares is
    what a screen may see.

    Why a screen needs it: S43 remembers where the month's journal goes, and
    *QuickBooks · IIF · downloaded here* is `file_format` and `destination`
    rather than prose. `describe` is a SENTENCE for a person to read; this is
    the two values a picker has to be set to, and parsing the sentence back
    into them would be a second source of truth that drifts on the first
    translation.
    """
    declared = {one.name: one for one in manifest.fields}
    config = dict(connection.config or {})
    return {
        name: value
        for name, value in config.items()
        if name in declared and not declared[name].is_secret
    }


def _connection_row(
    connection: models.IntegrationConnection,
    hint: dict | None,
    *,
    describe: str | None = None,
    settings: dict[str, Any] | None = None,
    now: datetime | None = None,
    registry: Registry = REGISTRY,
) -> dict[str, Any]:
    """The connection as a screen may see it. NO secret material — the row is
    safe to serve for the same reason it is safe to audit (US-INT-014)."""
    who = connection.connected_by
    return {
        "id": str(connection.id),  # a handle for wave B's Manage; never a visible value (rule 31)
        "label": connection.label,
        "describe": describe,
        #: Wave J. The non-secret fields, filtered BY THE MANIFEST — see
        #: `settings_for` above for why the filter is not a list typed here.
        "settings": settings or {},
        "connected_by": (who.full_name or None) if who is not None else None,
        "environment": connection.environment,
        "status": connection.status,
        "enabled": connection.enabled,
        "cadence": connection.cadence,
        "next_run_at": connection.next_run_at,
        "last_test_at": connection.last_test_at,
        "last_test_ok": connection.last_test_ok,
        "last_test_text": connection.last_test_text,
        "connected_at": connection.connected_at,
        "credential": hint,  # {version, hint, expires_at} or None — never a payload
        # ⚠ Wave H (US-INT-027 · BR-INT-042). The credential's LIFECYCLE, which
        # is a different fact from the credential: `{state, expires_at,
        # days_left, window_days, version}` and nothing else. Both S142's
        # WarningBox and the S7 attention strip read THIS, so the boundary
        # between *warning* and *lapsed* is decided once, on the server, and
        # two screens cannot drift apart on which side of it a date falls.
        #
        # ⚠ `expires_at` travels as ISO-8601 and is NOT formatted here. The
        # tenant's regional format belongs to the screen (BR-SHL-023 — one
        # formatting path), and a date the server pre-rendered would be a
        # second one that no locale change could reach.
        "expiry": expiry.view_for(
            connection, now=now or timezone.now(), registry=registry
        ).as_dict(),
    }


def _provider_row(
    manifest: Manifest,
    connections: list[models.IntegrationConnection],
    latest: dict[tuple, Any],
    inbound_read: set[Any],
    hints: dict[Any, dict],
    registry: Registry,
) -> dict[str, Any]:
    # The PRODUCTION connection decides the card; a sandbox twin travels
    # beside it in `connections` (BR-INT-026: two rows, shown in words).
    primary = connections[0] if connections else None
    # `CR-110-BRC04` wave B — the endpoint under each operation's label comes
    # from the connection's own NON-SECRET settings, filtered once here rather
    # than once per row, and never from `connection.config` directly.
    primary_settings = settings_for(manifest, primary) if primary is not None else None
    # ── CR-115-BRC05 §7.4 · OURS AND THEIRS IN ONE LIST ────────────────────
    # ⚠ **ONE LIST AND NOT TWO, BECAUSE THE RULING ASKS FOR ONE.** *"Columns:
    # Name · Kind · URL · Key · Enabled · Edit. Ours and theirs in ONE list,
    # ours marked as standard."* Two arrays would have let the screen draw two
    # tables, and the whole point of the ruling is that a clerk reads *what does
    # this connector call* in one place.
    #
    # ⚠ **THE CUSTOM ROWS FOLLOW THE OPERATION THEY BORROW, NOT THE END OF THE
    # LIST.** A clerk's second address layer belongs beside the first, where the
    # merge that rule 2 performs is legible; at the bottom of the table it reads
    # as an unrelated extra.
    #
    # ⚠ **ONE QUERY FOR THE ROWS, READ ONCE.** `is_enabled` and the loop below
    # both take the same list rather than each asking the database, so a
    # connector with sixteen operations costs one read and not seventeen.
    api_rows = custom_apis.rows_for(primary)
    operations: list[dict[str, Any]] = []
    for op in manifest.operations:
        run_row = latest.get((primary.id, op.name)) if primary else None
        operations.append(
            _operation_row(
                op,
                primary,
                run_row,
                primary_settings,
                manifest,
                enabled=custom_apis.is_enabled(primary, op.name, rows=api_rows),
            )
        )
        for row in api_rows:
            if row.is_standard or row.operation != op.name:
                continue
            operations.append(
                _operation_row(
                    op,
                    primary,
                    run_row,
                    primary_settings,
                    manifest,
                    row,
                    enabled=bool(row.enabled),
                )
            )
    direction, initiative = manifest.kicker
    return {
        "key": manifest.key,
        "category": manifest.category,
        "display_name": manifest.display_name,
        "summary": manifest.summary,
        # Wave B (BR-INT-043): the field slot is rendered from THIS list and
        # from nothing in React — kinds are the registry's closed vocabulary.
        "fields": [
            {
                "name": one.name,
                "label": one.label,
                "kind": one.kind,
                "required": one.required,
                "options": list(one.options),
                # CR-173-BRC10 — the named section this field is drawn and
                # saved in, or None for the connection's own details.
                "group": one.group or None,
            }
            for one in manifest.fields
        ],
        "disposition": {
            "kind": manifest.disposition.kind,
            "wave": manifest.disposition.wave,
            "phase": manifest.disposition.phase,
        },
        "kicker": {"direction": direction, "initiative": initiative},
        # ── CR-115-BRC05 §7.3 · WHAT THE ADD FORM MAY OFFER ────────────────
        # ⚠ **THE SERVER DECIDES THE CLOSED LIST, NOT THE SCREEN.** A React
        # array of three kinds would be the front end deciding what the product
        # can do — the same shape `BR-INT-037` forbids for the connector list,
        # and the shape that let a set-up screen answer differently from a view
        # screen on 9 of 91 operations (`DEF-INT-5613`). A Kind reaches this
        # list only where the operation that RUNS it is really declared, which
        # is what makes *"nothing addable can lack code behind it"* a fact
        # rather than a promise.
        #
        # Each entry carries `refusal` — a catalogue key or `None`. `None` means
        # Add will work; a key is the sentence a clerk reads instead, and today
        # the only one is rule 1's second scheduled sync. ⚠ **A KIND ALREADY
        # CONFIGURED IS SIMPLY ABSENT** (§7.4 — *"one configuration per API,
        # never two"*), which is a different state from refused and is why they
        # are not one flag.
        #
        # EMPTY on twenty-seven of twenty-eight connectors, and the screen draws
        # no form at all then — the honest answer for a connector whose every
        # API is bespoke, which is the half of the earlier ruling §7.2 keeps.
        "custom_api_kinds": (
            custom_apis.addable_kinds(primary, manifest) if primary is not None else []
        ),
        "auth": {"mode": manifest.auth.mode, "placement": manifest.auth.placement},
        "codecs": list(manifest.codecs),
        # Wave D (US-INT-037): the kinds of their words this provider ships,
        # so the card can offer *Mappings* — data, never a per-provider branch.
        "vocabularies": [
            {"entity_type": one.entity_type, "label": one.label, "count": len(one.values)}
            for one in manifest.vocabularies
        ],
        "adapter_registered": registry.adapter_for(manifest.key) is not None,
        # `CR-198-BRC10` — a provider the PLATFORM holds (`platform_holds_ours`)
        # is never connected by a utility; its card reads this instead of a
        # connection. Booleans, codes and a masked tail — never a secret.
        "platform": _platform_state(manifest),
        "connection": (
            _connection_row(
                primary,
                hints.get(primary.id),
                describe=describe_line(manifest, primary, registry),
                settings=settings_for(manifest, primary),
                registry=registry,
            )
            if primary
            else None
        ),
        "connections": [
            _connection_row(
                one,
                hints.get(one.id),
                describe=describe_line(manifest, one, registry),
                settings=settings_for(manifest, one),
                registry=registry,
            )
            for one in connections
        ],
        "state": primary.status if primary else models.STATUS_NOT_SET_UP,
        "display_state": _platform_display_state(manifest)
        or display_state(
            manifest,
            primary,
            [one["state"] for one in operations],
            primary.id in inbound_read if primary else False,
        ),
        "operations": operations,
        # Wave E (US-INT-024 · US-INT-025): the credential HISTORY under
        # *Replace password* (frame 54.2) and the two figures the disconnect
        # confirm needs. Hints and counts — never a payload, and the encrypted
        # column is not read by anything on this page.
        "credentials": (
            services.credential_versions(primary) if primary is not None else []
        ),
        # Wave R (US-INT-040): S144's rows — hint, state, issued, last used.
        # Served only where the manifest says we ISSUE a key, so a card with no
        # `issued_secret` field carries `[]` rather than an empty table nobody
        # can fill. NEVER the key: there is none stored to serve (machine_auth).
        "issued_keys": (
            services.issued_keys(primary)
            if primary is not None and machine_auth.issued_key_field(manifest) is not None
            else []
        ),
        "disconnect": (
            services.disconnect_preview(primary.tenant_id, manifest.key, registry=registry)
            if primary is not None
            else None
        ),
    }


def _platform_state(manifest: Manifest) -> dict[str, Any] | None:
    """`platform_sms.card_state` for a platform-held provider, else None."""
    from apps.integrations.registry import MODE_PLATFORM_HOLDS_OURS

    if manifest.auth.mode != MODE_PLATFORM_HOLDS_OURS:
        return None
    from apps.integrations import platform_sms
    from apps.integrations.seams import tenancy as tenancy_seam

    return platform_sms.card_state(tenancy_seam.subdomain())


def _platform_display_state(manifest: Manifest) -> str | None:
    """A platform-held provider's state word: `working` when the server holds
    its credentials and a sender, `not_set_up` when it does not. None for every
    other provider (the connection decides those)."""
    state = _platform_state(manifest)
    if state is None:
        return None
    return "working" if state.get("configured") else models.STATUS_NOT_SET_UP


def provider_display_name(provider_key: Any, *, registry: Registry = REGISTRY) -> str | None:
    """A provider's own name as the Connectors screen prints it, or `None`.

    `DEF-PAY-10015` — published for `payments.payment_detail`, which names the
    payment agent that took a payment (*"taken by USPayments"*). One name per
    provider, the manifest's, so the payment page and the connector card can
    never spell it two ways. Reads the registry only; no row, no tenant.
    """
    manifest = registry.get(str(provider_key or ""))
    return None if manifest is None else manifest.display_name


def grid(tenant_id: Any, *, registry: Registry = REGISTRY) -> dict[str, Any]:
    """`GET /integrations` — every manifest joined to THIS tenant's state.

    `categories` is generated from the registry, in first-appearance order, so
    the filter chips are never a typed list (08-screen-layouts.md deviation 1).
    """
    by_key = _connections_for(tenant_id)
    every_connection = [one for rows in by_key.values() for one in rows]
    latest = _latest_runs(every_connection)
    inbound_read = _has_inbound_read(every_connection)
    hints = _credential_hints(every_connection)
    providers = [
        _provider_row(manifest, by_key.get(manifest.key, []), latest, inbound_read, hints, registry)
        for manifest in registry.all()
    ]
    return {
        "categories": [{"key": one} for one in registry.categories()],
        "providers": providers,
        "counts": {
            "providers": len(providers),
            "connected": sum(1 for one in providers if one["connection"] is not None),
        },
    }


def provider_card(tenant_id: Any, key: str, *, registry: Registry = REGISTRY) -> dict[str, Any]:
    """One card of the grid — what a write route answers with, so the modal
    and the grid read the same shape (wave B). Raises KeyError for an
    unknown key; the API has already refused that as 404."""
    by_key = {card["key"]: card for card in grid(tenant_id, registry=registry)["providers"]}
    return by_key[key]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-001@a63a1b7 (EP-INT-01 story + BR-INT-001..017 snapshot; co-packets US-INT-013@62d3643 · US-INT-018@62d3643)
# generated: 2026-09-03 by the CR-069 wave A build lane
# checklist: A✔ B✔ C✔ D✔(GET /integrations, apps/integrations/api.py) E✔(IntegrationsTab.tsx) F✔ G✔ H=n/a(read side; the 🔒 half is the RLS migration)
# gates: pytest tests/test_us_int_001_grid.py tests/test_us_int_018_operations.py tests/test_us_int_013_registry.py · G77 (no `provider_key ==` — the read branches on nothing but the registry's data)
# exceptions: `unconfirmed` / `indeterminate` read `not_working` as the operation WORD until wave C (US-INT-021) lands the honest sentence — the outcome itself is served beside it · `reading_from_us` is computed and never stored (a sixth status value would be a migration for a word)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
