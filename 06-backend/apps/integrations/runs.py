# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-020 (EP-INT-06) — *"the last twenty runs with the counts
#           written as a clerk reads them … each row opening a run with its
#           per-item results and artifact"*. US-INT-021 — `unconfirmed` is its
#           own thing on the screen and never green.
#           Screens: S142 (frames 44.1 · 25.2 the table · 51.1 · 51.2 the card)
# Rules:    BR-INT-039 (every attempt is a durable record with a trace id) ·
#           BR-INT-018 (`succeeded` only when the counts reconcile AND the far
#           end confirmed) · BR-INT-040 (per-item results, never a batch
#           boolean) · CLAUDE.md hard rule 1 (every read is tenant-scoped —
#           explicitly here, because SQLite has no RLS to fall back on) ·
#           B14 rule 31 (no database id is ever a visible value) · rule 32
#           (one sentence per section) · B8 / LAW 0 (this is the read path;
#           nothing here writes)
# Tests:    06-backend/tests/test_us_int_020_runs.py ·
#           06-backend/tests/test_us_int_021_unconfirmed.py ·
#           06-backend/tests/test_us_int_020_pg.py
# Impacts:  apps/integrations/runs_api.py (the two routes) ·
#           07-frontend/src/features/integrations/ConnectionDetailPage.tsx
# ───────────────────────────────────────────────────────
"""The run read model — what S142 draws, and what it deliberately does not serve.

TWO SHAPES, AND THE DIFFERENCE BETWEEN THEM IS THE STORY'S WHOLE MITIGATION
---------------------------------------------------------------------------
    row(run)     the LIST shape — counts, outcome, summary, trace id.
                 **No `provider_error`. No items.** `US-INT-020` TC-6: the one
                 column where another tenant's data can arrive is never in a
                 list payload, an audit row or a notification.
    detail(run)  the ONE-RUN shape — the same, plus `provider_error` (scrubbed
                 at the write seam) and the items the run could not do.

A list is served to a screen full of rows and is easy to log, cache and
forward; a detail is served for one run a clerk deliberately opened. Keeping
them two functions is what makes the rule checkable by grep rather than by
reading every caller.

THE COUNTS ARE NUMBERS HERE AND A SENTENCE ON THE SCREEN
--------------------------------------------------------
*93 of 93* · *86 of 93 · 7 bad addresses* · *Unconfirmed · 93 sent, provider
did not say* are the strings the design draws, and none of them is built in
this file. This module serves `attempted`, `succeeded`, `failed`, `skipped`,
`changed` and `outcome`; the screen composes the sentence from the eleven
catalogues, because a sentence composed here would be English and eleven
languages would read it as English. The one thing this module DOES decide is
whether `changed` is shown at all — the fifth count means *revised* and only a
`reconcile` operation revises anything (`C13`), so the manifest's idempotency
mode says so and no screen has to know.

⚠ THE SEARCH IS TENANT-WIDE ON PURPOSE, AND THE ROW SAYS WHERE IT LIVES.
The demo is a support agent read eight characters down the phone. They do not
know which connection those characters belong to — that is the thing they are
trying to find out — so a search scoped to the connection whose page happens
to be open would answer *no runs* for a trace id that exists. `q` therefore
matches `trace_id` across the tenant, and every row carries its provider's key
and name so the answer reads *this is the Billing mailbox* rather than being
silently mixed into the page.

⚠ AND EIGHT HEX CHARACTERS ARE NOT UNIQUE. 4.3 billion values against this
product's own sizing (`US-INT-020`: 720,000 runs a year for email alone) puts
two runs on the same trace id roughly sixty times a year. So the search
returns a LIST — never `.get()` — and a clerk who lands on two picks by time.
A detail is addressed by the run's id and never by its trace id, for exactly
that reason.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from apps.integrations import models, selectors
from apps.integrations.registry import REGISTRY, Manifest, Registry
from apps.integrations.seams import tenancy as tenancy_seam
from core.pagination import DEFAULT_PAGE_SIZE, ListParams

#: ⚠ THE CAPABILITY MATRIX SAYS *"Twenty rows by default"* AND THIS SERVES
#: FIFTY — a stamped deviation, not an oversight (08-screen-layouts.md, S142).
#: The product has ONE page-size vocabulary — 50 · 100 · 200 · 500 · 1000, PO
#: ruling 2026-08-09 — and S142's run table is drawn by the same `DataTable`
#: assembly as every other list (B14 rule 36). A default of twenty would be a
#: size the screen's own page-size picker could not express, which is a second
#: way of paginating on one screen. The kernel decides; nothing here does.
DEFAULT_WINDOW = DEFAULT_PAGE_SIZE

#: The filters the capability matrix declares for S142's run table.
FILTERS: tuple[str, ...] = ("operation", "outcome", "trigger")
SORTS: tuple[str, ...] = ("started",)
DEFAULT_SORT = "started"

#: The outcome filter's vocabulary, in the model's own declaration order so
#: the chips never reshuffle between requests — a frozenset would.
FINISHED_OUTCOMES_ORDERED: tuple[str, ...] = tuple(
    one for one in models.OUTCOMES if one in models.FINISHED_OUTCOMES
)

#: `changed` is *revised*, and only a reconcile operation revises anything
#: (`C13`; frame 83.2 *1,240 read · 6 changed*). Any other mode shows four
#: counts, not five — a zero in a column that cannot move is noise.
RECONCILE = "reconcile"


def _operation_labels(manifest: Manifest) -> dict[str, Any]:
    return {one.name: one for one in manifest.operations}


def _shows_changed(operation: Any) -> bool:
    idempotency = getattr(operation, "idempotency", None)
    return getattr(idempotency, "mode", None) == RECONCILE


def _connection_word(connection: models.IntegrationConnection | None, manifest: Manifest) -> str:
    """What to call the connection a run belongs to — the tenant's own label
    when they gave one, else the provider's name. Never an id (rule 31)."""
    if connection is None:
        return manifest.display_name
    return connection.label or manifest.display_name


def row(
    run: models.IntegrationRun,
    *,
    manifest: Manifest,
    connection: models.IntegrationConnection | None,
) -> dict[str, Any]:
    """One run, LIST shape. No `provider_error`, no items — see the docstring."""
    operation = _operation_labels(manifest).get(run.operation)
    stored = run.items if isinstance(run.items, list) else []
    unsuccessful = (run.failed or 0) + (run.skipped or 0)
    return {
        # Carried so the row action can fetch the detail; never rendered
        # (B14 rule 31 — the visible identifier on this screen is the trace id,
        # labelled *Support reference*).
        "id": str(run.id),
        "trace_id": run.trace_id,
        "provider_key": manifest.key,
        "provider_name": manifest.display_name,
        "connection_label": _connection_word(connection, manifest),
        "environment": connection.environment if connection is not None else None,
        "operation": run.operation,
        "operation_label": operation.label if operation is not None else run.operation,
        "direction": run.direction,
        "trigger": run.trigger,
        # ── 2026-09-17 · `CR-115-BRC05` R31 ────────────────────────────────
        # ⚠ **THE LIST SHAPE AND NOT THE DETAIL, DELIBERATELY.** *Preview* and
        # *who pressed it* are what a reader of the RUN TABLE is looking for —
        # a column of runs where half changed nothing and half changed
        # everything, with no way to tell which, is worse than no column. They
        # cost no extra query: both are on the row `row()` already holds.
        # `null` on every run with no such choice to make, which is every run
        # in this product except the parcel reconciliation.
        "mode": run.mode,
        "started_by_name": run.started_by_name,
        "outcome": run.outcome,
        "attempted": run.attempted,
        "succeeded": run.succeeded,
        "failed": run.failed,
        "skipped": run.skipped,
        "changed": run.changed,
        "show_changed": _shows_changed(operation),
        "summary": run.summary,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "has_artifact": bool(run.artifact_link),
        "named_items": len(stored),
        #: How many of the unsuccessful items the cap left out. The screen says
        #: so in words; it is never a silent difference between two numbers.
        "unnamed_items": max(unsuccessful - len(stored), 0),
    }


def collecting(run: models.IntegrationRun, operation: Any) -> dict[str, Any] | None:
    """What a RUNNING submit-poll-collect or walk has told us so far (wave K).

    Frame 53.2 — *They are building the file. We will collect it when it is
    ready · asked them 4 times · checking again in 30 seconds*, and *window 61
    of 105*. Both figures live on the job record's `checkpoint`, written by
    `runners/fetch.py` as the walk goes, so a clerk who closed the page reads
    them on return (`US-INT-031` TC-3).

    `None` for a finished run and for a run whose job cannot be read — the
    screen then shows the counts and no progress band, which is honest. ⚠ **IT
    IS NEVER A GUESS**: a run that says nothing about its progress is a run
    that has not recorded any, and inventing *window 1 of 105* here would be a
    claim about a walk we cannot see.
    """
    if run.outcome not in (models.OUTCOME_RUNNING, models.OUTCOME_QUEUED):
        return None
    record = tenancy_seam.job(run.job_id)
    if record is None:
        return None
    checkpoint = record.get("checkpoint")
    if not isinstance(checkpoint, dict):
        return None
    progress = record.get("progress") or {}
    answer: dict[str, Any] = {
        "done": progress.get("done"),
        "total": progress.get("total"),
    }
    # Two shapes, and the SCREEN decides which sentence to draw from which key
    # rather than this module composing English (the same rule the counts
    # already follow — see the module docstring).
    if "asked" in checkpoint:
        answer["asked"] = checkpoint.get("asked")
        answer["next_in_s"] = checkpoint.get("next_in_s")
    if "window" in checkpoint:
        answer["window"] = checkpoint.get("window")
        answer["of"] = checkpoint.get("of")
    return answer


def detail(
    run: models.IntegrationRun,
    *,
    manifest: Manifest,
    connection: models.IntegrationConnection | None,
) -> dict[str, Any]:
    """One run, DETAIL shape — the list row plus the two things a list may
    never carry: the provider's own words, and the items it could not do.

    ⚠ WAVE K ADDS TWO KEYS AND BOTH ARE DETAIL-ONLY, deliberately. `collecting`
    reads the job record — one extra query per run, which a list of fifty must
    not make — and `asked_for` is the four request parameters (frame 83.1),
    which is a thing a clerk opens a run to see rather than something a table
    row could hold.
    """
    operation = _operation_labels(manifest).get(run.operation)
    payload = row(run, manifest=manifest, connection=connection)
    stored = run.items if isinstance(run.items, list) else []
    payload.update(
        {
            "provider_error": run.provider_error,
            "artifact_link": run.artifact_link,
            "content_hash": run.input_hash,
            # Frame 83.1, *what we ask them for* — the parameters whose default
            # is unsafe, shown EXPLICITLY so a clerk can see that we stated them
            # rather than trusting the vendor (`US-INT-035`, `C18`). An
            # operation with none serves an empty list and the panel is absent.
            "asked_for": list(getattr(operation, "safety_parameters", ()) or ()),
            "collecting": collecting(run, operation),
            "items": [
                {
                    "ref": one.get("ref"),
                    "detail": one.get("detail"),
                    "outcome": one.get("outcome"),
                    "provider_text": one.get("provider_text"),
                }
                for one in stored
                if isinstance(one, dict)
            ],
        }
    )
    return payload


def _runs_for(tenant_id: Any, connection_ids: list[Any]) -> Any:
    return models.IntegrationRun.objects.filter(
        tenant_id=tenant_id, connection_id__in=connection_ids
    )


def _apply(queryset: Any, params: ListParams) -> Any:
    for name in FILTERS:
        value = params.filters.get(name)
        if value:
            queryset = queryset.filter(**{name: value})
    return queryset


def list_view(
    tenant_id: Any,
    provider_key: str,
    *,
    params: ListParams,
    per: int = DEFAULT_WINDOW,
    registry: Registry = REGISTRY,
) -> dict[str, Any]:
    """S142's whole payload in one call: the head, the operations, the runs.

    The head is `selectors.provider_card` — the same read model the grid draws
    from, so the card and its detail can never disagree about a state word.
    """
    card = selectors.provider_card(tenant_id, provider_key, registry=registry)
    manifest = registry.get(provider_key)
    by_id: dict[Any, models.IntegrationConnection] = {}
    for connection in models.IntegrationConnection.objects.filter(
        tenant_id=tenant_id, provider_key=provider_key
    ):
        by_id[connection.id] = connection

    manifests: dict[str, Manifest] = {provider_key: manifest}
    if params.q:
        # Tenant-wide: eight characters down the phone name a run, not a page.
        queryset = models.IntegrationRun.objects.filter(
            tenant_id=tenant_id, trace_id__iexact=params.q.strip()
        )
        for connection in models.IntegrationConnection.objects.filter(tenant_id=tenant_id):
            by_id.setdefault(connection.id, connection)
    else:
        queryset = _runs_for(tenant_id, list(by_id))
    queryset = _apply(queryset, params)
    direction = "" if params.dir == "asc" else "-"
    queryset = queryset.order_by(f"{direction}started_at", "id")

    count = queryset.count()
    per = max(per, 1)
    pages = max((count + per - 1) // per, 1)
    page = min(max(params.page, 1), pages)
    window = list(queryset[(page - 1) * per : page * per])

    rows = []
    for run in window:
        connection = by_id.get(run.connection_id)
        key = connection.provider_key if connection is not None else provider_key
        found = manifests.get(key)
        if found is None:
            found = registry.get(key) or manifest
            manifests[key] = found
        rows.append(row(run, manifest=found, connection=connection))

    return {
        "provider": {
            "key": manifest.key,
            "display_name": manifest.display_name,
            "category": manifest.category,
            # Wave H — S142 needs to know whether this connection has a PASSWORD
            # or is SIGNED IN TO, because *Replace password* on a mailbox you
            # sign in to opened a form the server refuses (`DEF-INT-4237`). It
            # travels as manifest DATA so the screen branches on a declared
            # placement and never on a provider key (BR-INT-037, G77). The grid
            # has served the same two fields since wave A; this is the detail
            # payload catching up, not a new fact.
            "auth": {"mode": manifest.auth.mode, "placement": manifest.auth.placement},
            # ── CR-110-BRC04 wave B ─────────────────────────────────────────
            # PO ruling 2026-09-16 on the two unnamed vendors — *"keep it as it
            # is right now - we will replace them - theya re dummay right now"*
            # — and the CR extends it to anything declaring
            # `Disposition(kind="coming_soon")`: the card says so and the
            # server refuses the connect.
            #
            # ⚠ **THE GRID SAID IT AND THIS PAGE DID NOT**, so a clerk who
            # opened the print vendor's own page saw a full API table and *Not
            # set up* with nothing to say it can never be connected. That is
            # hard-won law 2's mirror — a screen that reads as ready over a
            # thing the server refuses — and the blueprint files it in its own
            # words on p146: *"offered as live with no connector — a card a
            # utility can press that cannot work."* Same field, same wire, so
            # the two surfaces cannot drift apart on it.
            "disposition": {
                "kind": manifest.disposition.kind,
                "wave": manifest.disposition.wave,
            },
            # `CR-174-BRC10` — the kinds of their words this connector ships,
            # so S142 can offer the door to S143 (*Map their words →*). Data
            # off the manifest, never a branch on a key; the grid already
            # serves the same list as `vocabularies`.
            "vocabularies": card.get("vocabularies", []),
        },
        "describe": card["connection"]["describe"] if card["connection"] else None,
        "display_state": card["display_state"],
        "connection": card["connection"],
        "operations": card["operations"],
        # ── `CR-115-BRC05` §7.3 · WHAT THE ADD FORM MAY OFFER ────────────────
        # ⚠ **THIS LINE IS WHY THE CONTROL EXISTS AT ALL, AND ITS ABSENCE WAS
        # INVISIBLE TO EVERY CHECK.** S142 draws its whole self from THIS
        # payload rather than from `provider_card` — `operations` two lines up
        # says so — so serving the closed list on the card and not here left
        # the screen with an empty list, `+ API` undrawn, and the per-API form
        # unreachable. `tsc` passed, every unit test passed, the backend suite
        # passed: the field is optional on the wire and an empty array is a
        # legal answer. **It was found by CLICKING** (hard-won law 6 — no gate
        # in this repo reads rendered output), which is the whole reason §7.10
        # asks for a browser walk rather than a green run.
        #
        # Off the SAME card as `operations` and `credentials` above, so this
        # page and the grid cannot drift about what may be added.
        "custom_api_kinds": card.get("custom_api_kinds", []),
        # Wave E (US-INT-024 · US-INT-025): the credential history under
        # *Replace password* (frame 54.2) and the two figures the disconnect
        # confirm states. Both come off the card, so this page and the grid
        # cannot disagree about how many versions there are — one source.
        "credentials": card["credentials"],
        # ── CR-110-BRC04 phase 2 · `DEF-INT-5533` ────────────────────────────
        # THE KEYS WE ISSUE, which VIEW-17 draws its own panel for (p066) and
        # which this page has never had. The card has served them since wave R
        # — hint, state, issued, last used and, since the key-scope wave, the
        # OPERATIONS the key may call — and no screen read them. That is
        # hard-won law 2 with a SERVED FIELD in place of a prop: `tsc` and every
        # test pass over a fact nothing renders, because nothing asks whether a
        # served field has a reader.
        #
        # It comes off the SAME card as `credentials` above, so this page and
        # S144 cannot disagree about how many keys exist or what each reaches.
        # `[]` on the twelve connectors we dial, because `provider_card` serves
        # it only where the manifest declares an `issued_secret` field.
        "issued_keys": card["issued_keys"],
        "disconnect": card["disconnect"],
        "filters": {
            "operations": [
                {"name": one.name, "label": one.label} for one in manifest.operations
            ],
            "outcomes": list(FINISHED_OUTCOMES_ORDERED),
            "triggers": list(models.RUN_TRIGGERS),
        },
        "applied": {
            "q": params.q,
            **{name: params.filters.get(name) for name in FILTERS},
        },
        "rows": rows,
        "page": {"page": page, "per": per, "count": count, "pages": pages},
        #: How many rows on this page belong to a DIFFERENT connection than the
        #: one whose page is open — non-zero only on a trace search, and the
        #: screen says which one each is rather than mixing them in silently.
        #:
        #: ⚠ **THIS COMPARES TWO RUNTIME KEYS AND NAMES NO PROVIDER, WHICH IS
        #: WHY `G77` NO LONGER REFUSES IT (`DEF-INT-4400`).** `BR-INT-037` is
        #: about branching on ONE provider — `if provider_key == "email_smtp"`
        #: — and this line does not change when a provider is added. The gate
        #: used to blank every string literal before matching, so it could not
        #: tell the two apart and refused this one for a day; it walks the
        #: syntax tree now and allows a comparison only when EVERY side is a
        #: provider-key expression. Put a LITERAL on either side of this and it
        #: fails again, correctly.
        "elsewhere": sum(1 for one in rows if one["provider_key"] != provider_key),
    }


def detail_view(
    tenant_id: Any,
    provider_key: str,
    run_id: str,
    *,
    registry: Registry = REGISTRY,
) -> dict[str, Any] | None:
    """One run, or None — and None is the ONLY answer for another tenant's run.

    An id that belongs to another tenant and an id that belongs to nobody take
    the same path and produce the same 404 (`US-INT-020` TC-5): the read is
    filtered by `tenant_id` before the id is looked at, so an existing id
    cannot be told from an absent one by timing or by message.
    """
    try:
        wanted = UUID(str(run_id))
    except (TypeError, ValueError):
        return None
    run = (
        models.IntegrationRun.objects.filter(tenant_id=tenant_id, id=wanted)
        .order_by("-started_at")
        .first()
    )
    if run is None:
        return None
    connection = models.IntegrationConnection.objects.filter(
        tenant_id=tenant_id, id=run.connection_id
    ).first()
    key = connection.provider_key if connection is not None else provider_key
    manifest = registry.get(key) or registry.get(provider_key)
    if manifest is None:
        return None
    return detail(run, manifest=manifest, connection=connection)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-020 (EP-INT-06) · US-INT-021 · 07-endpoints.md rows 10–11 · 08-screen-layouts.md S142
# generated: 2026-09-04 by the CR-069 wave C build lane
# checklist: A✔ B✔ C✔ D✔(GET /integrations/{key}/runs · /runs/{run_id}) E✔(ConnectionDetailPage.tsx) F✔ G✔ H=n/a(read path; no money, no policy)
# gates: pytest tests/test_us_int_020_runs.py tests/test_us_int_021_unconfirmed.py · G6 (no ORM in the API layer) · G77 (no provider_key branch — the manifest is data)
# exceptions: the trace search is tenant-wide and every row names its connection — argued in the docstring · a run is addressed by id and never by trace id, because eight hex characters collide
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
