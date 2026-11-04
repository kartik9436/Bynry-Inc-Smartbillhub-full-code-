# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-028 (EP-INT-07) TC-1..6 — a ten-minute token across a
#           two-hour walk, and NOT one credential row for it. Screens: S142
# Rules:    BR-INT-047 (token exchange never writes the credential table;
#           window and page size are declared data) · BR-INT-025 (versions are
#           written only by rotation) · BR-INT-003 (the plaintext lives for one
#           call; three exits) · BR-INT-054 as amended 2026-09-06 (what the
#           collected rows MEAN is Runbooks') · CLAUDE.md hard rule 1
# Tests:    this file
# Impacts:  apps/integrations/runtime.py (`TokenCache`) ·
#           apps/integrations/runners/fetch.py (`walk`, `windows`) ·
#           apps/integrations/adapters/meters_neptune360.py ·
#           apps/integrations/seams/runbooks.py
# ───────────────────────────────────────────────────────
"""US-INT-028 — the walk: windows, pages, mints, and one credential row.

⚠ WHAT THE RECORDED HEAD-END REFUSES, SAID FIRST, BECAUSE IT IS WHAT MAKES
EVERY COUNT IN THIS FILE MEAN SOMETHING. `RecordedHeadEnd` answers `error:
missing bearer token` to any request without an `Authorization` header. A
fixture that answered happily without one would let a runner that NEVER MINTED
pass all six cases below — law 7's *incapable of failing* shape, in the one
place it would be hardest to notice, because the walk would still complete and
every page would still be counted.

⚠ AND THE MINT COUNT IS TAKEN FROM THE FIXTURE'S OWN TALLY, not from the
cache's. `TokenCache.mints` is our bookkeeping; `RecordedHeadEnd.mints` is how
many times the token endpoint was actually asked. Asserting the first would
prove that a counter increments; asserting the second proves a network call was
made, which is the claim.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from apps.integrations import models, runtime, services
from apps.integrations import neptune_fixtures as fx
from apps.integrations.adapters import meters_neptune360 as neptune
from apps.integrations.registry import REGISTRY
from apps.integrations.runners import fetch
from apps.integrations.seams import runbooks as runbooks_seam
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

NEPTUNE = "meters_neptune360"

#: `US-INT-028` §4 — the two-year backfill the story sizes at 105 windows.
BACKFILL_START = date(2024, 9, 1)
BACKFILL_END = date(2026, 9, 1)

#: `IntegrationRun.job_id` is a UUID column, so the checkpoint cases need one.
JOB_ID = "0199b6a0-0000-7000-8000-000000000001"


def _connection(tenant, label="Water meter cloud"):
    return models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=NEPTUNE,
        label=label,
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_UNTESTED,
        cadence=models.CADENCE_MANUAL,
        config=fx.recorded_config(),
    )


def _with_credential(actor, connection, api_key=fx.RECORDED_API_KEY):
    services.record_credential(
        actor=actor,
        connection=connection,
        payload=json.dumps({"api_key": api_key}),
        masked_hint=f"••••{fx.RECORDED_HINT_TAIL}",
    )
    return connection


def _operation(name):
    return next(one for one in REGISTRY.require(NEPTUNE).operations if one.name == name)


#: The four request parameters whose default is unsafe, all set — this file is
#: about the WALK, and `US-INT-035` is where the refusal is exercised.
SAFE = {
    "actual_consumption": True,
    "include_estimates": False,
    "unit_of_measure": "GAL",
    "read_time_zone": "America/Chicago",
}


@pytest.fixture()
def head_end(monkeypatch):
    """Bind a recorded head-end for one case, and unbind it after."""
    runtime.reset_tokens()
    runtime.reset_caps()
    client = fx.RecordedHeadEnd()
    monkeypatch.setattr(neptune, "HEAD_END_CLIENT", client)
    yield client
    runtime.reset_tokens()


# ═══════════════════════════════════════════════════════════════════════════
# The arithmetic, first — 105 windows, asserted rather than assumed
# ═══════════════════════════════════════════════════════════════════════════


def test_a_two_year_backfill_is_one_hundred_and_five_seven_day_windows():
    """`US-INT-028` §4's own figure, computed rather than quoted.

    730 days ÷ 7 = 104 whole windows and a two-day tail — **105**. The story,
    S142's *window 61 of 105* and this function have to agree, and this is the
    one place the number is derived instead of typed.
    """
    spans = fetch.windows(BACKFILL_START, BACKFILL_END, 7)
    assert len(spans) == 105
    assert spans[0] == (date(2024, 9, 1), date(2024, 9, 8))
    # ⚠ The LAST window is SHORT and is not padded past the end date — asking a
    # provider for days that have not happened earns a refusal on the final
    # request after two hours of correct work.
    assert spans[-1][1] == BACKFILL_END
    assert (spans[-1][1] - spans[-1][0]).days == 2


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — a walk of 105 windows across a ten-minute token: ≥ 11 mints, ONE row
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc1_the_token_is_re_minted_mid_walk_and_the_credential_table_holds_one_row(
    brazos, dana, head_end
):
    """The whole of `BR-INT-047`, in one case.

    The clock is injected so a two-hour walk takes no wall time: each call to
    `now` advances by 65 seconds, so the ten-minute token ages out roughly
    every ninth check across 105 windows. The story asks for **≥ 11** mints;
    what matters is that the number is far above one and that the credential
    table has not moved.
    """
    ticks = iter(range(0, 2_000_000, 65))
    runtime.TOKENS = runtime.TokenCache(now=lambda: next(ticks))
    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        before = models.IntegrationCredential.objects.filter(connection=connection).count()

        run = fetch.walk(
            connection=connection,
            operation=_operation("collect_readings"),
            adapter=neptune.MetersNeptune360Adapter(),
            start=BACKFILL_START,
            end=BACKFILL_END,
            parameters=SAFE,
        )
        after = models.IntegrationCredential.objects.filter(connection=connection).count()

    assert before == 1
    # ⚠ THE ASSERTION THE STORY ACTUALLY MAKES. Not "the count did not grow" —
    # ONE row, before and after. `US-INT-028` TC-1 (doc TC-INT-37).
    assert after == 1
    assert head_end.mints >= 11, f"minted only {head_end.mints} times across 105 windows"
    assert run.outcome == models.OUTCOME_SUCCEEDED
    assert run.succeeded == 105
    # Every request carried a bearer — the fixture refuses one that does not,
    # so this also proves the mints reached the calls rather than a counter.
    assert all(one.startswith("Bearer ") for one in head_end.bearer_seen)


@pytest.mark.django_db
def test_tc1_a_cached_token_is_reused_rather_than_re_minted_per_page(brazos, dana, head_end):
    """The mirror of the case above, and the one that would catch a cache that
    is not a cache.

    ⚠ **WITHOUT THIS, TC-1 PASSES ON A RUNNER THAT MINTS ON EVERY SINGLE
    CALL** — 105 mints is also *≥ 11*. A frozen clock means the token never
    ages out, so a correct implementation mints exactly ONCE for the whole walk
    and a broken one mints 105 times.
    """
    runtime.TOKENS = runtime.TokenCache(now=lambda: 1000.0)
    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        fetch.walk(
            connection=connection,
            operation=_operation("collect_readings"),
            adapter=neptune.MetersNeptune360Adapter(),
            start=BACKFILL_START,
            end=BACKFILL_END,
            parameters=SAFE,
        )
    assert head_end.mints == 1, f"minted {head_end.mints} times with a frozen clock"


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — the declared page sizes are what leaves, and changing one changes the
#        request with no code change
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
@pytest.mark.parametrize(
    "operation_name,page_size",
    [("collect_readings", 5000), ("collect_meter_inventory", 150), ("collect_routes", 100)],
)
def test_tc2_the_runner_requests_exactly_the_declared_page_size(
    brazos, dana, head_end, operation_name, page_size
):
    """*Page sizes declared 5000 / 150 / 100 for three services.*

    ⚠ ASSERTED ON THE REQUEST THE FIXTURE RECEIVED, never on the manifest.
    Reading the number back off the manifest would assert that a constant
    equals itself; reading it off the recorded call proves it reached the wire.
    """
    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        fetch.walk(
            connection=connection,
            operation=_operation(operation_name),
            adapter=neptune.MetersNeptune360Adapter(),
            start=date(2026, 8, 1),
            end=date(2026, 8, 8),
            parameters=SAFE if operation_name.startswith("collect_readings") else {},
        )
    asked = [one for one in head_end.calls if not one["url"].endswith("/oauth/token")]
    assert asked, "nothing was requested"
    assert {one["payload"]["pageSize"] for one in asked} == {page_size}
    assert {one["payload"]["windowDays"] for one in asked} == {7}


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — a failure at window 61 resumes at 61, and 1–60 are not re-fetched
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc3_the_walk_resumes_at_the_window_it_reached(brazos, dana, head_end):
    """`resume_from` is read from the job's checkpoint and skips finished work.

    The checkpoint is recorded through a `progress` callable the caller passes
    in — `core.jobs.record_progress` in production — so this case can assert
    the resume marker with no `jobs` row at all, and so a test cannot go on
    passing after somebody renames the function it would otherwise have
    patched.
    """
    marks: list[tuple[int, int, dict]] = []

    def progress(job_id, done, total, checkpoint=None):
        marks.append((done, total, dict(checkpoint or {})))

    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        fetch.walk(
            connection=connection,
            operation=_operation("collect_readings"),
            adapter=neptune.MetersNeptune360Adapter(),
            start=BACKFILL_START,
            end=BACKFILL_END,
            parameters=SAFE,
            # ⚠ A REAL uuid: `IntegrationRun.job_id` is a `UUIDField`, so a
            # readable string like "JOB-1" is refused on save. The job id is a
            # database value here and a poll URL everywhere else.
            job_id=JOB_ID,
            progress=progress,
        )
        # The checkpoint after window 61 says 61 — that is what a resume reads.
        assert marks[60][0] == 61
        assert marks[60][2] == {"window": 61, "of": 105}

        head_end.calls.clear()
        run = fetch.walk(
            connection=connection,
            operation=_operation("collect_readings"),
            adapter=neptune.MetersNeptune360Adapter(),
            start=BACKFILL_START,
            end=BACKFILL_END,
            parameters=SAFE,
            resume_from=60,
        )

    asked = [one for one in head_end.calls if not one["url"].endswith("/oauth/token")]
    # 105 − 60 = 45 windows left. Windows 1–60 are not re-fetched, which is the
    # whole value of the checkpoint: two hours of work is not repeated.
    assert len(asked) == 45
    assert run.succeeded == 45
    # Window 61 begins 60 × 7 = 420 days after 2024-09-01. ⚠ Written as the
    # ARITHMETIC rather than as a literal, because a hand-typed date is exactly
    # the assertion that is wrong by one day and looks right — this one was, on
    # its first draft.
    assert asked[0]["payload"]["from"] == (BACKFILL_START + timedelta(days=420)).isoformat()


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — a window wider than they allow is refused BY THEM, naming the
#        parameter, and we do not narrow it quietly
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc4_a_window_the_provider_refuses_is_recorded_naming_the_parameter(
    brazos, dana, monkeypatch
):
    """*The provider refuses; the run records the refusal naming the parameter;
    no silent narrowing.*

    The manifest is not edited — a `FetchPlan` with a thirty-day window is
    handed to the runner directly, because editing the shipped manifest would
    make every other case in this suite depend on the mutation.
    """
    import dataclasses

    runtime.reset_tokens()
    client = fx.RecordedHeadEnd(window_cap_days=7)
    monkeypatch.setattr(neptune, "HEAD_END_CLIENT", client)
    thirty_days = dataclasses.replace(
        _operation("collect_readings"),
        fetch_plan=dataclasses.replace(_operation("collect_readings").fetch_plan, window_days=30),
    )
    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        run = fetch.walk(
            connection=connection,
            operation=thirty_days,
            adapter=neptune.MetersNeptune360Adapter(),
            start=date(2026, 6, 1),
            end=date(2026, 9, 1),
            parameters=SAFE,
        )
    assert run.failed >= 1
    assert "windowDays" in (run.provider_error or "")
    # ⚠ THE CONTROL HALF. *Nothing was collected* also describes a runner that
    # is simply broken, so the refusal only means something if what we asked
    # for was genuinely the thirty days the manifest declared.
    asked = [one for one in client.calls if not one["url"].endswith("/oauth/token")]
    assert asked[0]["payload"]["windowDays"] == 30


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — neither the long-lived pair nor any short-lived token appears in a log
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc5_no_log_line_carries_the_pair_or_the_token(brazos, dana, head_end, caplog):
    """`BR-INT-003`'s three exits, captured across a whole walk."""
    import logging

    with caplog.at_level(logging.DEBUG):
        with tenant_ctx(brazos):
            connection = _with_credential(dana, _connection(brazos))
            run = fetch.walk(
                connection=connection,
                operation=_operation("collect_readings"),
                adapter=neptune.MetersNeptune360Adapter(),
                start=date(2026, 8, 1),
                end=date(2026, 8, 29),
                parameters=SAFE,
            )
    captured = "\n".join(record.getMessage() for record in caplog.records)
    assert fx.RECORDED_API_KEY not in captured
    assert fx.RECORDED_TOKEN not in captured
    # …and not in the row a clerk reads either — the second and third exits.
    assert fx.RECORDED_API_KEY not in (run.summary or "")
    assert fx.RECORDED_TOKEN not in (run.summary or "")
    assert fx.RECORDED_TOKEN not in str(run.items)


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — two tenants, two token caches, and neither presents the other's
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc6_two_tenants_on_one_vendor_get_two_token_caches(brazos, lonestar, dana, erin, monkeypatch):
    """The isolation case, and it is about the CREDENTIAL rather than the vendor.

    Both utilities use the same manifest and the same head-end. They hold
    different long-lived pairs, so they must mint different tokens and neither
    may ever present the other's.
    """
    runtime.reset_tokens()

    class TwoSites(fx.RecordedHeadEnd):
        """Answers a token that names the pair it was given, so a swapped
        token is visible rather than merely improbable."""

        def call(self, *, method, url, headers=None, payload=None, timeout_s=30):
            if url.endswith("/oauth/token"):
                self.mints += 1
                return {"access_token": f"TOKEN-FOR-{(payload or {}).get('apiKey')}"}
            return super().call(
                method=method, url=url, headers=headers, payload=payload, timeout_s=timeout_s
            )

    client = TwoSites()
    monkeypatch.setattr(neptune, "HEAD_END_CLIENT", client)

    with tenant_ctx(brazos):
        one = _with_credential(dana, _connection(brazos), api_key="PAIR-BRAZOS")
        fetch.walk(
            connection=one,
            operation=_operation("collect_readings"),
            adapter=neptune.MetersNeptune360Adapter(),
            start=date(2026, 8, 1),
            end=date(2026, 8, 8),
            parameters=SAFE,
        )
    seen_by_brazos = list(client.bearer_seen)
    client.bearer_seen.clear()

    with tenant_ctx(lonestar):
        two = _with_credential(erin, _connection(lonestar), api_key="PAIR-LONESTAR")
        fetch.walk(
            connection=two,
            operation=_operation("collect_readings"),
            adapter=neptune.MetersNeptune360Adapter(),
            start=date(2026, 8, 1),
            end=date(2026, 8, 8),
            parameters=SAFE,
        )

    assert seen_by_brazos and all("PAIR-BRAZOS" in one for one in seen_by_brazos)
    assert client.bearer_seen and all("PAIR-LONESTAR" in one for one in client.bearer_seen)
    assert not any("PAIR-BRAZOS" in one for one in client.bearer_seen)


# ═══════════════════════════════════════════════════════════════════════════
# The boundary — the door to Runbooks is SHUT, and this is the test that goes
# red the day somebody opens it (BR-INT-054, CR-069 §20.4 wave K)
# ═══════════════════════════════════════════════════════════════════════════


def test_the_runbooks_seam_projects_nothing_today():
    """`CR-069` §20.4 moves the readings projection to Runbooks in as many
    words, so integrations collects and hands over and does nothing else.

    ⚠ THIS IS A DELIBERATE ABSENCE AND NOT A STUB — nothing is unruled, nothing
    is blocked, and a lane finding it should leave it alone. The assertion
    exists so the boundary cannot close silently: the day Runbooks plugs its
    projection into `seams/runbooks.py`, this goes RED and names the paragraph
    that explains why it was empty.
    """
    assert runbooks_seam.projects_nothing() is True
    assert (
        runbooks_seam.project_readings(
            connection_id="anything", operation="collect_readings", records=[{"value": "1"}]
        )
        == ()
    )


@pytest.mark.django_db
def test_a_walk_writes_no_meter_read_and_no_asset(brazos, dana, head_end):
    """The same boundary, asserted where it would actually be crossed.

    A projection that started here would show up as rows in metering's tables,
    not as a changed return value — so the seam test above is necessary and is
    not sufficient.
    """
    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        before = metering_models.MeterRead.objects.count()
        connection = _with_credential(dana, _connection(brazos))
        fetch.walk(
            connection=connection,
            operation=_operation("collect_readings"),
            adapter=neptune.MetersNeptune360Adapter(),
            start=date(2026, 8, 1),
            end=date(2026, 8, 29),
            parameters=SAFE,
        )
        assert metering_models.MeterRead.objects.count() == before


# ═══════════════════════════════════════════════════════════════════════════
# BUILT IS NOT WIRED (hard-won law 2) — the walk is reachable from the button
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_run_job_dispatches_a_walk_rather_than_one_attempt(brazos, dana, head_end):
    """⚠ **WITHOUT THIS CASE THE WHOLE WAVE IS DEAD CODE, AND EVERY OTHER TEST
    IN IT STILL PASSES.** `walk()` and `submit_poll_collect()` can be perfect,
    tested and reached by nothing a clerk can press: `POST
    /integrations/{key}/run` enqueues `integration.run`, whose body called the
    one-attempt runner for every operation until wave K taught it the three
    shapes. The token cache would never be exercised, the checkpoint would
    never be written, and the suite would be green over a feature that does not
    exist — four defects in one day, 2026-08-10.

    So this drives the JOB BODY, not the runner, and asserts the walk actually
    happened: 4 windows of 7 days, one run row with 4 successes, and a
    checkpoint on the job record.
    """
    from apps.integrations import jobs as integration_jobs

    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        marks: list[dict] = []
        record = {
            "id": JOB_ID,
            "tenant_id": brazos.id,
            "kind": integration_jobs.RUN_JOB,
            "checkpoint": None,
            "payload": {
                "connection_id": str(connection.id),
                "operation": "collect_readings",
                "work": [],
                "parameters": SAFE,
                "from": "2026-08-01",
                "to": "2026-08-29",
                "request_key": None,
                "actor_user_id": str(dana.id),
            },
        }
        # `core.jobs.record_progress` needs a stored job row; the body reads the
        # callable off the module, so a double proves the CALL rather than the
        # storage — and the storage has its own test in `core`.
        import core.jobs as core_jobs

        original = core_jobs.record_progress
        core_jobs.record_progress = lambda job_id, done, total, checkpoint=None: marks.append(
            {"done": done, "total": total, **dict(checkpoint or {})}
        )
        try:
            integration_jobs.run_run_job(record)
        finally:
            core_jobs.record_progress = original

        run = models.IntegrationRun.objects.filter(
            connection=connection, operation="collect_readings"
        ).latest("started_at")

    # 28 days ÷ 7 = FOUR windows, walked and checkpointed.
    assert [one["window"] for one in marks] == [1, 2, 3, 4]
    assert run.succeeded == 4
    assert run.outcome == models.OUTCOME_SUCCEEDED
    # …and the token was minted, which the one-attempt runner would also have
    # done — so the WINDOW COUNT above is the assertion that separates them.
    assert head_end.mints >= 1


@pytest.mark.django_db
def test_a_walk_with_no_window_falls_back_to_one_attempt_rather_than_inventing_one(
    brazos, dana, head_end
):
    """⚠ THE MIRROR, and it is about a decision this module must NOT make.

    A payload with no `from`/`to` has not asked for a walk. Defaulting to *the
    last seven days* here would be integrations deciding WHEN to collect, which
    is scheduling and belongs to Runbooks (`BR-INT-054` as amended 2026-09-06).
    So the body falls through to the one-attempt runner, which asks for nothing
    and records an empty run — honest, and visibly not a walk.
    """
    from apps.integrations import jobs as integration_jobs

    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        integration_jobs.run_run_job(
            {
                "id": JOB_ID,
                "tenant_id": brazos.id,
                "kind": integration_jobs.RUN_JOB,
                "checkpoint": None,
                "payload": {
                    "connection_id": str(connection.id),
                    "operation": "collect_readings",
                    "work": [],
                    "parameters": SAFE,
                    "actor_user_id": str(dana.id),
                },
            }
        )
        run = models.IntegrationRun.objects.filter(
            connection=connection, operation="collect_readings"
        ).latest("started_at")

    asked = [one for one in head_end.calls if not one["url"].endswith("/oauth/token")]
    assert asked == [], "a run with no window asked the provider for something"
    assert run.attempted == 0


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-028 (EP-INT-07) + BR-INT-047 · BR-INT-025 · BR-INT-003 verbatim
# generated: 2026-09-06 by the CR-069 wave K build lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_028_token_walk.py
# exceptions: the two-hour walk is simulated with an injected clock — the wall time is not the subject, the mint count and the credential row count are
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
