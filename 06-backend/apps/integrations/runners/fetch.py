# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-016 (EP-INT-05) — the runtime, quadrant `in · us`: we go
#           and collect. US-INT-028 (the walk: windows × pages across a
#           ten-minute token). US-INT-031 (submit–poll–collect: a link, or a
#           handle). US-INT-035 🔒 (safety parameters, and a fetch that changes
#           their world). Screens: S142
# Rules:    BR-INT-038 · BR-INT-018 · BR-INT-003 · BR-INT-041 — as deliver.py;
#           BR-INT-029 (idempotency mode `refuse` or `reconcile` is the
#           OPERATION's declaration, read here and applied by wave C/L's
#           collectors, never by an adapter) · BR-INT-047 (token exchange
#           writes no credential row; window and page size are declared data) ·
#           BR-INT-046 (a run is not finished until the file is collected; an
#           exhausted poll is `unconfirmed`) · BR-INT-050 (no vendor default on
#           a money path; one close, not two) · BR-INT-020 (the key is
#           generated before the call) · BR-INT-054 as amended 2026-09-06 (what
#           the collected rows MEAN is Runbooks')
# Tests:    06-backend/tests/test_us_int_016_queue.py ·
#           06-backend/tests/test_us_int_028_token_walk.py ·
#           06-backend/tests/test_us_int_031_submit_poll_collect.py ·
#           06-backend/tests/test_us_int_035_safety_parameters.py
# Impacts:  apps/integrations/jobs.py (`integration.walk` and
#           `integration.collect` bodies) · apps/integrations/runtime.py
#           (`TokenCache`) · apps/integrations/seams/runbooks.py (the door the
#           collected pages leave through) · wave L builds its reconciler on
#           the walk below
# ───────────────────────────────────────────────────────
"""FETCH — we go and collect something (`in · us`): readings from a head-end, a file from a folder.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 IDEMPOTENCY KEYS (CLAUDE.md sensitive
    paths), from wave K (2026-09-06). `submit_poll_collect` mints and stores the
    key that stops a partner's billing routes closing twice, and it stores it
    BEFORE the request leaves — the same class as `apps/integrations/arrivals.py`
    pointing the other way. Authored by AI under the standing protocol (PO
    2026-08-09, *"AI will do it; we will review it later as human"*); the row
    stating what a reviewer is owed, in plain English with a figure, is in
    `12-governance/09-human-review-ledger.md`, and the glob is in
    `10-scripts/gates/human_owned.txt`.

The same one-attempt shape as `deliver.py` — the runtime opens the run row,
holds the secrets for the length of the call, closes the row with the counts
— and ONE more thing this quadrant owns: the **fifth count**, `changed`. A
collector that reconciles (idempotency mode `reconcile`, BR-INT-029) reports
*1,240 read · 6 revised*, and the six are `changed` on the run row, which is
the number a support agent needs and the number a bare success hides (C13).

In wave B nothing collected yet: the runner existed so the quadrant table had
no empty cell. The item's `changed` marker is
read off `ItemResult.provider_text` until wave C names a field for it — that
is the one placeholder here, stated.

WAVE K ADDED THE THREE SHAPES A REAL COLLECTION TAKES (2026-09-06)
------------------------------------------------------------------
    walk(...)            windows × pages, checkpointed. A two-year backfill
                         at seven days a window is **105 windows**; a failure
                         at window 61 resumes at 61 and windows 1–60 are not
                         re-fetched.
    submit_poll_collect  they build the file while we wait. Ask every 30
                         seconds, up to 40 times — twenty minutes — then
                         `unconfirmed`, never `succeeded` and never silently
                         `failed`.
    safety_refusal(...)  a request that leaves an unsafe default unset DOES
                         NOT START, and the refusal names the parameter.

⚠ **THE TOKEN IS MINTED HERE AND STORED NOWHERE** (`BR-INT-047`). A head-end
bearer token lives ten minutes; the walk above takes two hours, so the token is
re-minted twelve times or more mid-walk. `runtime.TOKENS` holds it in memory
for the length of the walk and `services.record_credential` is never reached —
`US-INT-028` TC-1 asserts the credential table holds **one** row before and
after. Writing a version per mint would be roughly **144 rows a day** on one
connection and would make the rotation history unreadable inside a week.

⚠ **WHAT THIS RUNNER DOES NOT DO, AND WHOSE IT IS** (`BR-INT-054` as amended
2026-09-06, `CR-069` §20.4 wave K). It collects and it counts. It does not turn
a collected reading into our measurement frame, does not reconcile by natural
key, and does not decide which meter belongs to which account — that is the
readings PROJECTION, which the boundary ruling moves to Runbooks in as many
words. Every page leaves through `seams/runbooks.project_readings`, which
returns nothing today, and a test asserts that it does so the door cannot open
silently.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from datetime import date, timedelta

from apps.integrations import models, runtime, services
from apps.integrations.adapters.base import (
    ITEM_SUCCEEDED,
    MINTED_TOKEN_KEY,
    Adapter,
    RunResult,
    token_minter,
)
from apps.integrations.registry import REGISTRY, Operation, Registry
from apps.integrations.runners.deliver import RUN_DIRECTION, view_of
from apps.integrations.runtime import ProviderTimeout
from apps.integrations.seams import runbooks as runbooks_seam


def execute_run(
    *,
    connection: models.IntegrationConnection,
    operation: Operation,
    adapter: Adapter,
    work: Sequence[Mapping[str, Any]],
    trigger: str,
    job_id: Any = None,
) -> models.IntegrationRun:
    run = services.start_run(
        connection=connection,
        operation=operation.name,
        direction=RUN_DIRECTION[(operation.direction, operation.initiative)],
        trigger=trigger,
        job_id=job_id,
    )
    secrets = services.credential_secrets(connection)  # the ONE point (BR-INT-003)
    try:
        # The same guard as `deliver.py` — collecting from a head-end that has
        # stopped answering fills a worker exactly as sending to one does.
        outcome = services.guarded_adapter_call(
            connection=connection,
            operation=operation,
            # ⚠ BOUND AS A DEFAULT, NOT CLOSED OVER. `finally` below deletes
            # `secrets` (BR-INT-003 — the plaintext lives for one call), and a
            # closure would read the name AFTER that `del` if anything ever
            # called this lambda late. Binding it here means the value is
            # captured now and dies with the lambda.
            call=lambda _secrets=secrets: adapter.execute(view_of(connection), _secrets, work),
        )
    except Exception as exc:  # noqa: BLE001 — recorded, then re-raised for the framework's retry
        services.finish_run(
            run,
            attempted=len(work),
            succeeded=0,
            failed=0,
            skipped=0,
            confirmed=False,
            summary="The provider could not be reached.",
            provider_error=services.scrub(str(exc)),
        )
        raise
    finally:
        del secrets
    if outcome.skipped:
        return services.finish_run(
            run,
            attempted=0,
            succeeded=0,
            failed=0,
            skipped=0,
            confirmed=True,
            never_dialled=True,
            summary=outcome.sentence,
        )
    if outcome.timed_out:
        services.finish_run(
            run,
            attempted=len(work),
            succeeded=0,
            failed=0,
            skipped=0,
            confirmed=False,
            indeterminate=True,
            summary=outcome.sentence,
        )
        raise ProviderTimeout(outcome.sentence or "the provider did not answer") from None
    result = outcome.value
    if not isinstance(result, RunResult):
        return services.finish_run(
            run,
            attempted=len(work),
            succeeded=0,
            failed=0,
            skipped=0,
            confirmed=False,
            summary="The provider did not say how many it accepted.",
        )
    changed = sum(1 for one in result.items if one.provider_text == "changed")
    return services.finish_run(
        run,
        confirmed=result.confirmed,
        changed=changed,
        provider_error=services.scrub(result.provider_text) if result.provider_text else None,
        **result.counts,
    )



# ═══════════════════════════════════════════════════════════════════════════
# WAVE K · the sentences a clerk reads
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ THESE ARE ENGLISH FALLBACKS. The catalogue key wins on screen where it is
# present (`integrations.runs.*`), so a translation is a catalogue line and
# never an edit here — B14 rule 35: a catalogue is written in its own language,
# not translated from English. `arrivals.duplicate_summary` carries the same
# note for the same reason.

#: `US-INT-035` TC-1, the design's own words: *not started —
#: `actual_consumption` was not set*. ⚠ Longer than B14 rule 33's five or six
#: words, and kept because the parameter's NAME is the whole content of the
#: refusal: *Something was not set* sends a clerk to a support call, and the
#: rule exists to stop a sentence being useless rather than to stop it being
#: informative. The divergence is stamped here rather than left to be noticed.
SAFETY_REFUSAL = "not started — {parameter} was not set"
#: `US-INT-031` TC-4 — an exhausted poll budget. `unconfirmed`, never
#: `succeeded` and never silently `failed` (`BR-INT-018`).
NEVER_FINISHED = "they never finished the file"
#: Frame 53.2 — what S142 shows WHILE the vendor is building. Two figures: how
#: many times we have asked, and how long until we ask again.
COLLECTING = "They are building the file. We will collect it when it is ready"
#: `US-INT-035` TC-3 — the retry of a request that already changed their world.
ALREADY_DONE = "already closed on {when}"
#: Progress, in the clerk's units rather than ours — *window 61 of 105*, never
#: *61%* and never a row count (frame 53.2, `US-INT-028` §5).
WINDOW_PROGRESS = "window {done} of {total}"
#: The vendor's own word for *not yet*. THEIRS, translated by the adapter, and
#: the only value this runner compares against — see `submit_poll_collect`.
BUILDING = "building"


# ═══════════════════════════════════════════════════════════════════════════
# The fetch plan, walked — `C12`, and none of these numbers is in this file
# ═══════════════════════════════════════════════════════════════════════════


def windows(start: date, end: date, window_days: int) -> list[tuple[date, date]]:
    """Their chunks of time, from `start` up to but not including `end`.

    Two years from 2024-09-01 at seven days a window is **105 windows** — 104
    whole ones and a short tail — which is the figure `US-INT-028` §4 names and
    the figure S142 counts against (*window 61 of 105*).

    ⚠ **THE LAST WINDOW IS SHORT AND IS NOT PADDED.** Asking a provider for
    days that have not happened is how a walk earns a refusal on its final
    request after two hours of correct work, and the rows we would get back are
    empty either way.
    """
    if window_days < 1:  # pragma: no cover — the registry refuses this at load
        raise ValueError("a fetch plan's window is at least one day")
    spans: list[tuple[date, date]] = []
    cursor = start
    step = timedelta(days=window_days)
    while cursor < end:
        spans.append((cursor, min(cursor + step, end)))
        cursor += step
    return spans


def safety_refusal(operation: Operation, parameters: Mapping[str, Any]) -> str | None:
    """The first safety parameter this request leaves unset, or `None`.

    ⚠ **SET MEANS *THE KEY IS PRESENT*, NEVER *THE VALUE IS TRUTHY*, AND THE
    DIFFERENCE IS THE ONE THAT BITES.** `include_estimates=False` is the SAFE
    value — it is the whole reason the parameter is on the list — so a
    truthiness check would refuse exactly the request we want made, and would
    accept a dangerous one on any parameter whose unsafe value happens to be
    non-empty. `C18` is about a DEFAULT that is unsafe; the cure is that the
    request states its own value, whatever that value is.

    ⚠ And `None` is treated as unset, deliberately: a template carrying
    `actual_consumption: null` has not stated anything, and the head-end would
    fall back to the default this rule exists to refuse.
    """
    for name in operation.safety_parameters:
        if name not in parameters or parameters.get(name) is None:
            return SAFETY_REFUSAL.format(parameter=name)
    return None


def _token_for(
    *,
    connection: models.IntegrationConnection,
    adapter: Adapter,
    secrets: Mapping[str, str],
    registry: Registry = REGISTRY,
) -> str | None:
    """The connection's short-lived token, minted through the cache, or `None`.

    ⚠ **THE CACHE KEY IS THE TENANT AND THE CONNECTION, WHICH IS THE CREDENTIAL
    ON THIS MODEL** (`US-INT-028` TC-6). Two utilities collecting from the same
    head-end vendor hold two different long-lived pairs and must get two caches;
    keying on the provider would let one present the other's token, which is the
    one failure this cache could cause that nothing else in the product would
    catch. ⚠ If credentials ever become plural per connection
    (`DEF-INT-4118`), THIS KEY is what has to grow a credential id — the claim
    *one credential row before and after* is about the stored PAIR, never about
    the connection (`CR-069` §20.8).
    """
    manifest = registry.require(connection.provider_key)
    exchange = manifest.auth.token
    if exchange is None:
        return None  # not a token-exchange provider; the secrets go as they are
    minter = token_minter(adapter)
    if minter is None:
        # ⚠ A NAME IN A CONSTANT IS NOT A GUARANTEE (hard-won law 1). The
        # manifest says this provider exchanges; the adapter cannot. Refusing
        # here names it, instead of dialling with no token and reading the
        # provider's authentication failure back to a clerk.
        raise RuntimeError(
            f"{manifest.key} declares a token exchange and its adapter cannot mint one"
        )
    view = view_of(connection)
    return runtime.TOKENS.token_for(
        f"{connection.tenant_id}:{connection.id}",
        lambda: minter(view, secrets),
        ttl_seconds=exchange.ttl_seconds,
        refresh_before_s=exchange.refresh_before_s,
    )


def walk(
    *,
    connection: models.IntegrationConnection,
    operation: Operation,
    adapter: Adapter,
    start: date,
    end: date,
    parameters: Mapping[str, Any] | None = None,
    trigger: str = "manual",
    job_id: Any = None,
    resume_from: int = 0,
    progress: Any = None,
    registry: Registry = REGISTRY,
    max_pages_per_window: int = 1000,
) -> models.IntegrationRun:
    """Windows × pages, checkpointed, across a token that expires mid-walk.

    `US-INT-028` end to end. Returns the run row.

    **The order is the guarantee, so read it as a sequence:**

      1. refuse a request that leaves a safety parameter unset — BEFORE
         anything is dialled (`US-INT-035` TC-1: *nothing left*);
      2. open the run row;
      3. for each window from `resume_from`, page until they say there is no
         more, minting through the cache whenever the token has aged out;
      4. record progress AND the checkpoint after each window, so a failure at
         window 61 resumes at 61 (`US-INT-028` TC-3);
      5. hand every page to Runbooks' door, which is shut (`BR-INT-054`);
      6. close the row with the counts.

    ⚠ **`progress` IS `core.jobs.record_progress` PASSED IN, NOT IMPORTED.** A
    test that patched a module attribute would keep passing the day somebody
    renamed it, and this is the path that decides whether two hours of
    collection has to start again. It also lets the walk be asserted with no
    `jobs` row at all.

    ⚠ **PAGING STOPS ON `hasMore`, NOT ON A SHORT PAGE.** A provider that
    returns exactly `page_size` rows on its last page is not unusual, and a
    runner inferring *short page means done* would silently drop the tail of
    every window that divided evenly. `max_pages_per_window` is the belt for a
    provider whose `hasMore` never goes false — without it a bug on their side
    is an infinite loop on ours.
    """
    parameters = dict(parameters or {})
    refusal = safety_refusal(operation, parameters)
    if refusal is not None:
        # 1 · nothing leaves. The row records that we did NOT ask
        # (`never_dialled` → `skipped`), which is the third kind of
        # not-knowing and the only one with an action attached to it.
        run = services.start_run(
            connection=connection,
            operation=operation.name,
            direction=RUN_DIRECTION[(operation.direction, operation.initiative)],
            trigger=trigger,
            job_id=job_id,
            registry=registry,
        )
        return services.finish_run(
            run,
            attempted=0,
            succeeded=0,
            failed=0,
            skipped=0,
            confirmed=True,
            never_dialled=True,
            summary=refusal,
        )

    plan = operation.fetch_plan
    if plan is None:  # pragma: no cover — a walk without a plan is a caller error
        raise ValueError(f"{operation.name} declares no fetch plan; there is nothing to walk")
    spans = windows(start, end, plan.window_days)
    total = len(spans)

    run = services.start_run(
        connection=connection,
        operation=operation.name,
        direction=RUN_DIRECTION[(operation.direction, operation.initiative)],
        trigger=trigger,
        job_id=job_id,
        registry=registry,
    )
    secrets = dict(services.credential_secrets(connection))  # the ONE point (BR-INT-003)
    attempted = succeeded = failed = 0
    reached = resume_from
    provider_error: str | None = None
    try:
        for index in range(resume_from, total):
            window_start, window_end = spans[index]
            for page in range(1, max_pages_per_window + 1):
                token = _token_for(
                    connection=connection, adapter=adapter, secrets=secrets, registry=registry
                )
                call_secrets = dict(secrets)
                if token:
                    call_secrets[MINTED_TOKEN_KEY] = token
                work = [
                    {
                        # B14 rule 31 — the visible reference is the window and
                        # the page, which is what a person would search for.
                        "ref": f"{window_start.isoformat()} · page {page}",
                        "operation": operation.name,
                        "payload": {
                            **parameters,
                            "windowDays": plan.window_days,
                            "from": window_start.isoformat(),
                            "to": window_end.isoformat(),
                            "page": page,
                            "pageSize": plan.page_size,
                        },
                    }
                ]
                outcome = services.guarded_adapter_call(
                    connection=connection,
                    operation=operation,
                    # ⚠ Bound as a default, not closed over — the `finally`
                    # below clears the secrets, and a closure would read the
                    # name after it.
                    call=lambda _s=call_secrets, _w=work: adapter.execute(
                        view_of(connection), _s, _w
                    ),
                )
                if outcome.skipped:
                    return services.finish_run(
                        run,
                        attempted=attempted,
                        succeeded=succeeded,
                        failed=failed,
                        skipped=0,
                        confirmed=True,
                        never_dialled=True,
                        summary=outcome.sentence,
                    )
                if outcome.timed_out:
                    services.finish_run(
                        run,
                        attempted=attempted + 1,
                        succeeded=succeeded,
                        failed=failed,
                        skipped=0,
                        confirmed=False,
                        indeterminate=True,
                        summary=outcome.sentence,
                    )
                    raise ProviderTimeout(outcome.sentence or "the provider did not answer")
                result = outcome.value
                attempted += 1
                if not isinstance(result, RunResult) or not result.items:
                    failed += 1
                    break
                item = result.items[0]
                if item.outcome != ITEM_SUCCEEDED:
                    # ⚠ `US-INT-028` TC-4 — a provider refusing a parameter we
                    # asked for is recorded in THEIR words, naming it. We do not
                    # narrow the window and try again: a silent narrowing means
                    # the walk we recorded is not the walk we made.
                    failed += 1
                    provider_error = item.provider_text or item.detail
                    break
                succeeded += 1
                # 5 · the door to Runbooks. It returns nothing, on purpose.
                runbooks_seam.project_readings(
                    connection_id=connection.id,
                    operation=operation.name,
                    window_start=window_start,
                    window_end=window_end,
                )
                if not _has_more(item):
                    break
            reached = index + 1
            # 4 · progress AND the checkpoint, after each WINDOW rather than
            # each page: a resume re-fetches at most one window's pages, and a
            # checkpoint per page would write 105 × N rows for the same answer.
            if progress is not None and job_id is not None:
                progress(
                    job_id,
                    reached,
                    total,
                    checkpoint={"window": reached, "of": total},
                )
    finally:
        secrets.clear()
        del secrets

    return services.finish_run(
        run,
        attempted=attempted,
        succeeded=succeeded,
        failed=failed,
        skipped=0,
        confirmed=True,
        summary=WINDOW_PROGRESS.format(done=reached, total=total),
        provider_error=services.scrub(provider_error) if provider_error else None,
    )


def _has_more(item: Any) -> bool:
    """Whether the adapter said this window has another page.

    The adapter reports what came back in `detail` — *4,912 records* — and the
    runner must not parse a sentence to decide control flow. `hasMore` rides on
    the item's `provider_text` as the literal word `more`, set by the adapter:
    the same channel wave B used for the `changed` marker, carrying the same
    stated placeholder — wave C named a field for `changed` and a later wave
    should name one for this.
    """
    return str(getattr(item, "provider_text", "") or "") == "more"


# ═══════════════════════════════════════════════════════════════════════════
# Submit → poll → collect — `C10`, `C20`, and the run is not finished until
# the file is in hand
# ═══════════════════════════════════════════════════════════════════════════


def submit_poll_collect(
    *,
    connection: models.IntegrationConnection,
    operation: Operation,
    adapter: Adapter,
    parameters: Mapping[str, Any] | None = None,
    request_key: str | None = None,
    trigger: str = "manual",
    job_id: Any = None,
    progress: Any = None,
    registry: Registry = REGISTRY,
    sleep: Any = None,
) -> models.IntegrationRun:
    """Ask them to build it, ask again on their schedule, collect it when it is.

    `US-INT-031` end to end, and `US-INT-035` TC-3 for the half that changes
    their world.

    **Two declared values decide everything and neither is in this function:**
    `poll` (every 30 seconds, up to 40 — twenty minutes) and `result_delivery`
    (`link` or `handle`). Neptune's two API versions answer with two different
    kinds of thing and **the same code path serves both**, which is what makes
    `C20` a declaration rather than a branch.

    ⚠ **AN EXHAUSTED BUDGET IS `unconfirmed`** (`BR-INT-018`, `US-INT-031`
    TC-4): *they never finished the file*. Never `succeeded` — we have no file —
    and never `failed`, because nothing went wrong; they are simply still
    building, and a clerk told *failed* will go and start it again.

    ⚠ **`mutates_partner_state` WRITES THE KEY BEFORE THE CALL** (`BR-INT-020`,
    `BR-INT-050`). Neptune's export can carry `CloseOnExport`, which closes
    billing routes on THEIR side. So the run row is opened with the key already
    on it — exactly as `arrivals.record_arrival` opens a row with the digest
    already on it — and a retry of the same period finds it and is refused
    *already closed on 1 Sep* rather than closing the routes a second time.
    A key written when the call RETURNS would not exist during the one window
    where a retry is most likely: the moment the far end went quiet.
    """
    parameters = dict(parameters or {})
    refusal = safety_refusal(operation, parameters)
    if refusal is not None:
        run = services.start_run(
            connection=connection,
            operation=operation.name,
            direction=RUN_DIRECTION[(operation.direction, operation.initiative)],
            trigger=trigger,
            job_id=job_id,
            registry=registry,
        )
        return services.finish_run(
            run, attempted=0, succeeded=0, failed=0, skipped=0,
            confirmed=True, never_dialled=True, summary=refusal,
        )

    if operation.mutates_partner_state:
        if not request_key:
            # ⚠ The registry already refuses a manifest that declares this flag
            # with no `request_key` SOURCE; this refuses a CALLER that minted no
            # key VALUE. Two different mistakes, and only the first one can be
            # caught at load.
            raise ValueError(
                f"{operation.name} changes the partner's state and no request key was minted"
            )
        first = previous_request(connection=connection, request_key=request_key)
        if first is not None:
            run = services.start_run(
                connection=connection,
                operation=operation.name,
                direction=RUN_DIRECTION[(operation.direction, operation.initiative)],
                trigger=trigger,
                job_id=job_id,
                request_key=request_key,
                registry=registry,
            )
            return services.finish_run(
                run, attempted=0, succeeded=0, failed=0, skipped=0,
                confirmed=True, never_dialled=True,
                summary=already_done_summary(first),
            )

    poll = operation.poll
    if poll is None:  # pragma: no cover — the registry refuses this at load
        raise ValueError(f"{operation.name} declares no poll schedule")

    #: 2 · the row, carrying the key ALREADY, before anything is sent.
    run = services.start_run(
        connection=connection,
        operation=operation.name,
        direction=RUN_DIRECTION[(operation.direction, operation.initiative)],
        trigger=trigger,
        job_id=job_id,
        request_key=request_key,
        registry=registry,
    )
    secrets = dict(services.credential_secrets(connection))
    artifact: str | None = None
    asked = 0
    try:
        token = _token_for(
            connection=connection, adapter=adapter, secrets=secrets, registry=registry
        )
        if token:
            secrets[MINTED_TOKEN_KEY] = token
        _call_once(
            connection=connection, operation=operation, adapter=adapter, secrets=secrets,
            ref="submit", method="POST", payload=parameters,
        )
        for attempt in range(1, poll.max_attempts + 1):
            asked = attempt
            token = _token_for(
                connection=connection, adapter=adapter, secrets=secrets, registry=registry
            )
            if token:
                secrets[MINTED_TOKEN_KEY] = token
            answer = _call_once(
                connection=connection, operation=operation, adapter=adapter, secrets=secrets,
                ref=f"poll {attempt}", method="GET", payload=parameters,
            )
            if progress is not None and job_id is not None:
                # Frame 53.2 — *asked them 4 times · checking again in 30
                # seconds*. The two figures the screen shows, recorded as the
                # job's own progress so a clerk who closed the page reads them
                # on return (`US-INT-031` TC-3).
                progress(
                    job_id,
                    attempt,
                    poll.max_attempts,
                    checkpoint={
                        "sentence": COLLECTING,
                        "asked": attempt,
                        "next_in_s": poll.every_seconds,
                    },
                )
            # ⚠ *STILL BUILDING* IS THE ONLY WORD THIS LOOP READS, and it
            # is read as an EQUALITY rather than as *not ready*: an empty
            # answer, a breaker sentence or a timeout must NOT be mistaken for
            # a finished file, and every one of them is *not "building"*.
            if answer and answer != BUILDING:
                # `link` delivery already handed the URL back with the ready
                # answer; `handle` delivery needs one more call to collect by.
                artifact = (
                    answer
                    if operation.result_delivery == "link"
                    else _collect(
                        connection=connection, operation=operation, adapter=adapter,
                        secrets=secrets, parameters=parameters,
                    )
                )
                break
            if attempt < poll.max_attempts and sleep is not None:
                sleep(poll.every_seconds)
    finally:
        secrets.clear()
        del secrets

    if artifact is None:
        # `BR-INT-018` — we asked forty times and have no file. That is not a
        # failure and it is certainly not a success.
        return services.finish_run(
            run, attempted=1, succeeded=0, failed=0, skipped=0,
            confirmed=False, summary=NEVER_FINISHED,
        )
    return services.finish_run(
        run, attempted=1, succeeded=1, failed=0, skipped=0,
        confirmed=True, artifact_link=artifact,
        summary=WINDOW_PROGRESS.format(done=asked, total=poll.max_attempts),
    )


def _call_once(
    *,
    connection: models.IntegrationConnection,
    operation: Operation,
    adapter: Adapter,
    secrets: Mapping[str, str],
    ref: str,
    method: str,
    payload: Mapping[str, Any],
    url: str | None = None,
) -> str:
    """One request through the guard. Answers the vendor's own status word."""
    work = [
        {
            "ref": ref,
            "operation": operation.name,
            "method": method,
            "payload": dict(payload),
            **({"url": url} if url else {}),
        }
    ]
    outcome = services.guarded_adapter_call(
        connection=connection,
        operation=operation,
        call=lambda _s=dict(secrets), _w=work: adapter.execute(view_of(connection), _s, _w),
    )
    if outcome.skipped or outcome.timed_out:
        return str(outcome.sentence or "")
    result = outcome.value
    if not isinstance(result, RunResult) or not result.items:
        return ""
    return str(result.items[0].detail or "")


def _collect(
    *,
    connection: models.IntegrationConnection,
    operation: Operation,
    adapter: Adapter,
    secrets: Mapping[str, str],
    parameters: Mapping[str, Any],
) -> str:
    """Collect BY a handle — the second half of `C20`'s two declared values.

    ⚠ **`link` NEVER REACHES HERE, AND THAT IS THE POINT RATHER THAN A GAP.**
    Their v1 hands the URL back with the *ready* answer, so `submit_poll_collect`
    already has the file's address and asks nothing further; their v2 hands back
    an identifier and this makes the one extra call. `US-INT-031` TC-2 asserts
    *the same runner served both* — one function, two declared values, and no
    branch on the provider anywhere. The day a third delivery appears it is a
    value in `RESULT_DELIVERIES` and one clause in the caller, never a new path.
    """
    return _call_once(
        connection=connection, operation=operation, adapter=adapter, secrets=secrets,
        ref="collect", method="GET", payload={**parameters, "collect": True},
    )


def previous_request(
    *, connection: models.IntegrationConnection, request_key: str
) -> models.IntegrationRun | None:
    """The first run that already sent this key on this connection, or `None`.

    ⚠ SCOPED TO THE CONNECTION, and that is a judgment rather than an
    optimisation — the same one `arrivals.previous_arrival` makes. Two Neptune
    connections at one utility are two relationships with two head-ends, and a
    period closed on one of them says nothing about the other. The tenant is
    stated explicitly as well as scoped by RLS, because the suite runs on
    SQLite where a missing filter would pass every test.
    """
    return (
        models.IntegrationRun.objects.filter(
            tenant_id=connection.tenant_id,
            connection_id=connection.id,
            request_key=request_key,
        )
        .order_by("started_at", "id")
        .first()
    )


def already_done_summary(first: models.IntegrationRun) -> str:
    """*already closed on 1 Sep* — the ENGLISH fallback (`US-INT-035` TC-3).

    ⚠ THE DATE COMES OFF THE FIRST RUN'S OWN TIMESTAMP and is never a guess:
    the row carries the instant, so the sentence and the row cannot disagree.
    """
    when = first.started_at
    return ALREADY_DONE.format(when=f"{when.day} {when:%b}")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-016@62d3643 (EP-INT-05 story + BR-INT-018..053 snapshot)
# generated: 2026-09-03 by the CR-069 wave B build lane
# checklist: A✔ B✔ C✔ D✔(reached through POST /integrations/{key}/run for an `in · us` operation) E=deferred(wave C's S142) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_016_queue.py
# exceptions: no collector exists yet — this runner is the quadrant's shape; the `changed` marker rides `provider_text` until wave C names a field
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
