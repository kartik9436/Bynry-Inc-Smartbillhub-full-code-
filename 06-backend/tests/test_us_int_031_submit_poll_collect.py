# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-031 (EP-INT-08) TC-1..6 — completion: immediate, or
#           submit–poll–collect, and a result that is a link or a handle.
#           Screens: S142 (the collecting sentence, frame 53.2)
# Rules:    BR-INT-046 (completion and result delivery are declared; a run is
#           not finished until the file is collected) · BR-INT-018 (an
#           exhausted poll is `unconfirmed`, not succeeded) · CLAUDE.md hard
#           rule 1 (tenant scoping)
# Tests:    this file
# Impacts:  apps/integrations/runners/fetch.py (`submit_poll_collect`) ·
#           apps/integrations/registry.py (the load-time refusal, TC-5) ·
#           apps/integrations/manifests/meters_neptune360.py
# ───────────────────────────────────────────────────────
"""US-INT-031 — they build the file while we wait, and the run is not finished until we have it.

⚠ THE THREE FIXTURES ARE THE POINT (`US-INT-031` §4): *v1 link*, *v2 handle*,
*never ready*. One code path serves all three, because `result_delivery` is a
DECLARED VALUE and not a branch — and a suite with only one fixture would have
covered one path and left the other two to the first real utility.

⚠ AND TC-4 IS THE CASE MOST LIKELY TO BE WRITTEN WRONG. *Forty polls, never
ready* must be `unconfirmed`: never `succeeded`, because we have no file, and
never `failed`, because nothing went wrong — they are simply still building,
and a clerk told *failed* will go and start it again.
"""

from __future__ import annotations

import json

import pytest

from apps.integrations import models, runtime, services
from apps.integrations import neptune_fixtures as fx
from apps.integrations.adapters import meters_neptune360 as neptune
from apps.integrations.registry import REGISTRY, ManifestError, Registry, validate
from apps.integrations.runners import fetch
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

NEPTUNE = "meters_neptune360"
#: The v1 half — `result_delivery = link`, and it CHANGES THEIR WORLD, so every
#: call to it carries a request key (that half is `US-INT-035`'s).
REQUEST_EXPORT = "request_billing_export"
#: The v2 half — `result_delivery = handle`, collected by identifier.
COLLECT_EXPORT = "collect_billing_export"

#: `IntegrationRun.job_id` is a UUID column — a readable string is refused on save.
JOB_ID = "0199b6a0-0000-7000-8000-000000000002"


def _connection(tenant):
    return models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=NEPTUNE,
        label="Water meter cloud",
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_UNTESTED,
        cadence=models.CADENCE_MANUAL,
        config=fx.recorded_config(),
    )


def _with_credential(actor, connection):
    services.record_credential(
        actor=actor,
        connection=connection,
        payload=json.dumps(fx.recorded_secrets()),
        masked_hint=f"••••{fx.RECORDED_HINT_TAIL}",
    )
    return connection


def _operation(name):
    return next(one for one in REGISTRY.require(NEPTUNE).operations if one.name == name)


@pytest.fixture()
def bind(monkeypatch):
    """Bind a recorded head-end of a named flavour, and unbind it after."""

    def _bind(flavour):
        runtime.reset_tokens()
        runtime.reset_caps()
        client = fx.RecordedHeadEnd(export_fixture=flavour)
        monkeypatch.setattr(neptune, "HEAD_END_CLIENT", client)
        return client

    yield _bind
    runtime.reset_tokens()


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — building four times, then a link. `asked them 4 times` is the figure
#        the screen shows, so it is the figure recorded.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc1_four_building_answers_then_a_link_and_the_run_succeeds(brazos, dana, bind):
    """*S142 shows the sentence with asked them 4 times · checking again in 30
    seconds while running; on the fifth poll `artifact_link` is set.*"""
    bind("v1_link")
    marks: list[dict] = []

    def progress(job_id, done, total, checkpoint=None):
        marks.append({"done": done, "total": total, **dict(checkpoint or {})})

    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        run = fetch.submit_poll_collect(
            connection=connection,
            operation=_operation(REQUEST_EXPORT),
            adapter=neptune.MetersNeptune360Adapter(),
            parameters={"period": "2026-08"},
            request_key="2026-08:route-north",
            job_id=JOB_ID,
            progress=progress,
        )

    assert run.outcome == models.OUTCOME_SUCCEEDED
    assert run.artifact_link == fx.READY_LINK_RESPONSE["downloadUrl"]
    # The two figures frame 53.2 draws, recorded on the job as they happened.
    assert [one["asked"] for one in marks] == [1, 2, 3, 4, 5]
    assert marks[3]["asked"] == fx.BUILDS_FOR
    assert marks[3]["next_in_s"] == 30
    assert marks[3]["sentence"] == fetch.COLLECTING
    # The poll BUDGET is the manifest's, not this file's.
    assert marks[0]["total"] == _operation(REQUEST_EXPORT).poll.max_attempts == 40


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — the other vendor version answers with an identifier, and THE SAME
#        RUNNER collects it. A declared value, not a branch.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc2_the_same_runner_collects_by_handle(brazos, dana, bind):
    """*The runner collects by handle into the artifact store; the same runner
    served both — a declared value, no branch.*"""
    client = bind("v2_handle")
    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        run = fetch.submit_poll_collect(
            connection=connection,
            operation=_operation(COLLECT_EXPORT),
            adapter=neptune.MetersNeptune360Adapter(),
            parameters={"period": "2026-08"},
        )
    assert run.outcome == models.OUTCOME_SUCCEEDED
    assert run.artifact_link == fx.COLLECTED_BY_HANDLE_RESPONSE["artifactUrl"]
    # ⚠ THE CLAIM `C20` ACTUALLY MAKES, asserted on the code rather than on the
    # outcome: ONE function served a link in TC-1 and a handle here, and the
    # only thing that differed is the manifest's declared value.
    assert _operation(REQUEST_EXPORT).result_delivery == "link"
    assert _operation(COLLECT_EXPORT).result_delivery == "handle"
    # The handle path makes exactly one EXTRA call — the collect — and the link
    # path makes none, because v1 hands the URL back with the ready answer.
    collects = [one for one in client.calls if one["payload"].get("collect")]
    assert len(collects) == 1


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — the clerk closes the browser at poll 2; nothing changes
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc3_closing_the_page_changes_nothing(brazos, dana, bind):
    """The job runs where the browser is not.

    ⚠ HOW A TEST CAN ASSERT THIS AT ALL: the walk takes no argument that could
    carry a browser, a session or a request, so *the clerk left* is expressed
    as *nothing observes the run while it happens* — the run is driven to
    completion with no progress callable at all and the outcome is identical.
    A run that depended on being watched would differ here.
    """
    bind("v1_link")
    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        watched = fetch.submit_poll_collect(
            connection=connection,
            operation=_operation(COLLECT_EXPORT),
            adapter=neptune.MetersNeptune360Adapter(),
            parameters={"period": "2026-08"},
            job_id=JOB_ID,
            progress=lambda *a, **k: None,
        )
    bind("v1_link")
    with tenant_ctx(brazos):
        unwatched = fetch.submit_poll_collect(
            connection=connection,
            operation=_operation(COLLECT_EXPORT),
            adapter=neptune.MetersNeptune360Adapter(),
            parameters={"period": "2026-08"},
        )
    assert watched.outcome == unwatched.outcome == models.OUTCOME_SUCCEEDED
    assert watched.artifact_link == unwatched.artifact_link


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — forty polls, never ready → `unconfirmed`, never succeeded, never
#        silently failed
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc4_an_exhausted_poll_budget_is_unconfirmed(brazos, dana, bind):
    """`BR-INT-018` — *they never finished the file*.

    ⚠ THE TWO THINGS IT MUST NOT BE ARE ASSERTED EXPLICITLY, because both are
    plausible bugs and each is wrong in its own direction: `succeeded` claims a
    file we do not have, and `failed` sends a clerk to start it all over again.
    """
    client = bind("never_ready")
    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        run = fetch.submit_poll_collect(
            connection=connection,
            operation=_operation(COLLECT_EXPORT),
            adapter=neptune.MetersNeptune360Adapter(),
            parameters={"period": "2026-08"},
        )
    assert run.outcome == models.OUTCOME_UNCONFIRMED
    assert run.outcome != models.OUTCOME_SUCCEEDED
    assert run.outcome != models.OUTCOME_FAILED
    assert run.summary == fetch.NEVER_FINISHED
    assert run.artifact_link in (None, "")
    # Exactly the declared budget was spent — 40 polls plus the submit.
    polls = [one for one in client.calls if "/exports" in one["url"]]
    assert len(polls) == 1 + 40


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — a manifest that declares submit_poll_collect and no poll schedule is
#        REFUSED AT LOAD
# ═══════════════════════════════════════════════════════════════════════════


def test_tc5_submit_poll_collect_with_no_poll_schedule_is_refused_at_load():
    """*Refused at load* — `manage.py check` fails on the developer's machine,
    not the first real batch at 06:02 on the first of the month.

    ⚠ AND THE COMPANION REFUSALS ARE ASSERTED IN THE SAME CASE, because each
    is a way of declaring half the rule: no `result_delivery` leaves us unable
    to read the answer, and a poll schedule on an `immediate` operation is a
    number nothing reads. This guard went RED on a real manifest the first time
    all eighteen were validated together — `print_vendor`, `DEF-INT-4244`.
    """
    import dataclasses

    manifest = REGISTRY.require(NEPTUNE)
    export = next(one for one in manifest.operations if one.name == COLLECT_EXPORT)
    immediate = next(one for one in manifest.operations if one.name == "collect_readings")

    no_poll = dataclasses.replace(
        manifest,
        key="fixture_no_poll",
        operations=(dataclasses.replace(export, poll=None),),
    )
    with pytest.raises(ManifestError) as refused:
        validate(no_poll)
    assert "no poll schedule" in str(refused.value)
    assert COLLECT_EXPORT in str(refused.value)  # it names the OPERATION

    no_delivery = dataclasses.replace(
        manifest,
        key="fixture_no_delivery",
        operations=(dataclasses.replace(export, result_delivery=None),),
    )
    with pytest.raises(ManifestError) as refused:
        validate(no_delivery)
    assert "no result_delivery" in str(refused.value)

    poll_on_immediate = dataclasses.replace(
        manifest,
        key="fixture_poll_on_immediate",
        operations=(dataclasses.replace(immediate, poll=export.poll),),
    )
    with pytest.raises(ManifestError) as refused:
        validate(poll_on_immediate)
    assert "nothing polls an immediate operation" in str(refused.value)

    # ⚠ THE CONTROL. Three refusals prove nothing if the validator refuses
    # everything, so the shipped manifest must still pass in the same case.
    validate(manifest)


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — two tenants export at once; neither collects the other's file
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc6_two_tenants_exporting_at_once_get_two_runs(brazos, lonestar, dana, erin, bind):
    """Two jobs, two handles, and each run row belongs to its own utility.

    The tenant is asserted on the ROWS rather than on the response, because the
    suite runs on SQLite where RLS does not exist — the one mechanism that
    would otherwise make this true is absent, so the filter has to be real.
    """
    bind("v2_handle")
    with tenant_ctx(brazos):
        one = _with_credential(dana, _connection(brazos))
        run_one = fetch.submit_poll_collect(
            connection=one,
            operation=_operation(COLLECT_EXPORT),
            adapter=neptune.MetersNeptune360Adapter(),
            parameters={"period": "2026-08"},
        )
    bind("v2_handle")
    with tenant_ctx(lonestar):
        two = _with_credential(erin, _connection(lonestar))
        run_two = fetch.submit_poll_collect(
            connection=two,
            operation=_operation(COLLECT_EXPORT),
            adapter=neptune.MetersNeptune360Adapter(),
            parameters={"period": "2026-08"},
        )
        mine = models.IntegrationRun.objects.filter(tenant_id=lonestar.id)

    assert run_one.tenant_id == brazos.id
    assert run_two.tenant_id == lonestar.id
    assert run_one.id != run_two.id
    assert list(mine.values_list("id", flat=True)) == [run_two.id]


# ═══════════════════════════════════════════════════════════════════════════
# The READ MODEL — what S142 is actually handed, because a screen asserted in
# isolation is a screen asserted against a fixture nobody serves
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_run_detail_serves_the_four_parameters_and_the_collected_file(brazos, dana, bind):
    """`asked_for` and `artifact_link`, off the real read model.

    ⚠ **THE SCREEN TESTS AND THIS ONE PROVE DIFFERENT HALVES, AND NEITHER IS
    ENOUGH ALONE.** `ConnectionDetailPage.test.tsx` mounts the card over a
    hand-built `RunDetail` and proves the DRAWING; this proves the SERVING. A
    key the screen reads and the API never sends is the shape of hard-won law
    2 — every check green over a panel that is blank for every real run.
    """
    from apps.integrations import runs
    from apps.integrations.registry import REGISTRY as registry

    bind("v1_link")
    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        run = fetch.submit_poll_collect(
            connection=connection,
            operation=_operation(REQUEST_EXPORT),
            adapter=neptune.MetersNeptune360Adapter(),
            parameters={"period": "2026-08"},
            request_key="2026-08:read-model",
        )
        payload = runs.detail(
            run, manifest=registry.require(NEPTUNE), connection=connection
        )

    assert payload["artifact_link"] == fx.READY_LINK_RESPONSE["downloadUrl"]
    # A finished run is not collecting anything, and the screen draws no band.
    assert payload["collecting"] is None
    # The export states nothing unsafe, so the panel is ABSENT rather than empty
    # (B14 rule 32 — a stated absence is closed by default).
    assert payload["asked_for"] == []


@pytest.mark.django_db
def test_a_readings_run_serves_the_four_parameters_it_states(brazos, dana, bind):
    """Frame 83.1 — *what we ask them for*, off the manifest, through the API."""
    from apps.integrations import models as int_models
    from apps.integrations import runs
    from apps.integrations.registry import REGISTRY as registry

    bind("v1_link")
    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        run = int_models.IntegrationRun.objects.create(
            tenant_id=brazos.id,
            connection=connection,
            operation="collect_readings",
            direction=int_models.RUN_DIRECTION_INBOUND,
            trigger="manual",
            outcome=int_models.OUTCOME_SUCCEEDED,
            trace_id="ABCD1234",
        )
        payload = runs.detail(
            run, manifest=registry.require(NEPTUNE), connection=connection
        )

    assert payload["asked_for"] == [
        "actual_consumption",
        "include_estimates",
        "unit_of_measure",
        "read_time_zone",
    ]
    # ⚠ AND THE LIST SHAPE IS NOT IN THIS FILE — it is read off the manifest, so
    # a fifth unsafe default added there appears on the screen with no code
    # change, which is the whole of `BR-INT-037`.
    assert payload["asked_for"] == list(_operation("collect_readings").safety_parameters)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-031 (EP-INT-08) + BR-INT-046 · BR-INT-018 verbatim
# generated: 2026-09-06 by the CR-069 wave K build lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_031_submit_poll_collect.py
# exceptions: the 30-second wait between polls is not slept in tests — `sleep` is an injected callable and is left None, so forty polls take no wall time and the SCHEDULE is asserted from the manifest instead
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
