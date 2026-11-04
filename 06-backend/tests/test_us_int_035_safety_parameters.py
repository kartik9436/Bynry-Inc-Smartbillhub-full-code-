# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-035 (EP-INT-09) 🔒 TC-1..6 — safety-relevant parameters
#           stated explicitly, and a fetch that changes their world recorded
#           as a write. Screens: S142
# Rules:    BR-INT-050 (no vendor default on a money path; a partner-state
#           write carries a key and a receipt; the retry is refused) ·
#           BR-INT-020 (the key is generated BEFORE the call) · CLAUDE.md hard
#           rule 3 (consumption always with an explicit unit) · hard rule 6
# Tests:    this file
# Impacts:  apps/integrations/runners/fetch.py (`safety_refusal`,
#           `submit_poll_collect`, `previous_request`) ·
#           apps/integrations/migrations/0007_k1_request_key.py ·
#           apps/integrations/registry.py (the load-time refusal, TC-4)
# ───────────────────────────────────────────────────────
"""US-INT-035 — nothing leaves with an unsafe default, and their routes close once.

⚠ THE FAILURE THIS STORY PREVENTS IS SILENT, WHICH IS WHY THE CASES LOOK
PARANOID. A collection that omits `actual_consumption` does not error: the
head-end answers happily with ESTIMATED figures in the same shape as real
reads, nothing downstream can tell them apart, and a utility bills them. There
is no exception to catch and no row that looks wrong — the only place to stop
it is before the request leaves.

⚠ AND *SET* MEANS *THE KEY IS PRESENT*, NEVER *THE VALUE IS TRUTHY*. The safe
value of `include_estimates` is **False**; a truthiness check would refuse
exactly the request we want made. That is asserted below rather than left to a
comment, because it is the single most likely way to get this rule wrong.
"""

from __future__ import annotations

import json

import pytest

from apps.integrations import models, runtime, services
from apps.integrations import neptune_fixtures as fx
from apps.integrations.adapters import meters_neptune360 as neptune
from apps.integrations.registry import REGISTRY, ManifestError, validate
from apps.integrations.runners import fetch
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

NEPTUNE = "meters_neptune360"
READINGS = "collect_readings"
#: The operation that carries `CloseOnExport` and closes THEIR billing routes.
CLOSING_EXPORT = "request_billing_export"

SAFE = {
    "actual_consumption": True,
    "include_estimates": False,
    "unit_of_measure": "GAL",
    "read_time_zone": "America/Chicago",
}


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
def head_end(monkeypatch):
    runtime.reset_tokens()
    runtime.reset_caps()
    client = fx.RecordedHeadEnd()
    monkeypatch.setattr(neptune, "HEAD_END_CLIENT", client)
    yield client
    runtime.reset_tokens()


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — a request missing `actual_consumption` does not start, and NOTHING
#        LEAVES. The second half is the one that matters.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc1_a_missing_safety_parameter_stops_the_run_before_anything_is_dialled(
    brazos, dana, head_end
):
    """*The run does not start; S142 reads `not started — actual_consumption
    was not set`; no request left.*

    ⚠ `head_end.calls == []` IS THE ASSERTION THAT CARRIES THIS CASE. A run
    recorded as refused while the request still went out would satisfy every
    other line here and would be the exact bug the rule exists to prevent —
    estimates collected, and a row saying we did not ask for them.
    """
    missing = {k: v for k, v in SAFE.items() if k != "actual_consumption"}
    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        run = fetch.walk(
            connection=connection,
            operation=_operation(READINGS),
            adapter=neptune.MetersNeptune360Adapter(),
            start=fx_date(),
            end=fx_date(days=28),
            parameters=missing,
        )
    assert run.summary == "not started — actual_consumption was not set"
    assert run.outcome == models.OUTCOME_SKIPPED
    assert run.attempted == 0
    assert head_end.calls == [], "a request left despite the refusal"


def fx_date(days: int = 0):
    """A fixed window start, plus `days`. Kept local so no case depends on today."""
    from datetime import date, timedelta

    return date(2026, 8, 1) + timedelta(days=days)


@pytest.mark.django_db
@pytest.mark.parametrize("missing", sorted(SAFE))
def test_tc1_every_one_of_the_four_is_refused_by_its_own_name(brazos, dana, head_end, missing):
    """All four, and the refusal NAMES the one that was unset.

    A single sentence for all four — *a parameter was not set* — would send a
    clerk to a support call, which is why the name is in the copy.
    """
    parameters = {k: v for k, v in SAFE.items() if k != missing}
    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        run = fetch.walk(
            connection=connection,
            operation=_operation(READINGS),
            adapter=neptune.MetersNeptune360Adapter(),
            start=fx_date(),
            end=fx_date(days=7),
            parameters=parameters,
        )
    assert run.summary == f"not started — {missing} was not set"
    assert head_end.calls == []


def test_tc1_false_is_a_value_and_not_an_absence():
    """⚠ THE MOST LIKELY WAY TO GET THIS RULE WRONG, asserted directly.

    `include_estimates=False` is the SAFE value — the whole reason the
    parameter is on the list — so a truthiness check would refuse exactly the
    request we want made. And `None` IS treated as unset, because a template
    carrying `actual_consumption: null` has stated nothing and the head-end
    would fall back to the default this rule exists to refuse.
    """
    operation = _operation(READINGS)
    assert fetch.safety_refusal(operation, SAFE) is None
    assert fetch.safety_refusal(operation, {**SAFE, "include_estimates": False}) is None
    assert fetch.safety_refusal(operation, {**SAFE, "actual_consumption": None}) == (
        "not started — actual_consumption was not set"
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — all four set: the run starts and the request carries all four
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc2_all_four_parameters_travel_on_the_request(brazos, dana, head_end):
    """*The request carries all four explicitly, asserted on the fixture.*

    ⚠ ASSERTED ON WHAT THE HEAD-END RECEIVED, never on what we passed in.
    Checking our own input would prove the test set a dictionary; checking the
    recorded call proves the values reached the wire, which is the claim
    `C18` makes.
    """
    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        run = fetch.walk(
            connection=connection,
            operation=_operation(READINGS),
            adapter=neptune.MetersNeptune360Adapter(),
            start=fx_date(),
            end=fx_date(days=7),
            parameters=SAFE,
        )
    asked = [one for one in head_end.calls if not one["url"].endswith("/oauth/token")]
    assert asked, "nothing was requested"
    for name, value in SAFE.items():
        assert asked[0]["payload"][name] == value
    assert run.outcome == models.OUTCOME_SUCCEEDED
    # The manifest declares FOUR and two of them are on the money path.
    assert len(_operation(READINGS).safety_parameters) == 4
    assert "actual_consumption" in _operation(READINGS).safety_parameters


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — CloseOnExport: the key and the receipt are written BEFORE the call,
#        and the retry of the same period is refused. One close, not two.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc3_a_partner_state_write_happens_once_and_the_retry_is_refused(
    brazos, dana, monkeypatch
):
    """*A run row with an idempotency key and a receipt is written before the
    call; the retry of the same period is refused — one close, not two.*"""
    runtime.reset_tokens()
    client = fx.RecordedHeadEnd(export_fixture="v1_link")
    monkeypatch.setattr(neptune, "HEAD_END_CLIENT", client)
    key = "2026-08:route-north:CloseOnExport"

    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        first = fetch.submit_poll_collect(
            connection=connection,
            operation=_operation(CLOSING_EXPORT),
            adapter=neptune.MetersNeptune360Adapter(),
            parameters={"period": "2026-08", "CloseOnExport": True},
            request_key=key,
        )
        calls_after_first = len(client.calls)

        second = fetch.submit_poll_collect(
            connection=connection,
            operation=_operation(CLOSING_EXPORT),
            adapter=neptune.MetersNeptune360Adapter(),
            parameters={"period": "2026-08", "CloseOnExport": True},
            request_key=key,
        )

    # The key is on the FIRST row, and the receipt is the artifact it collected.
    assert first.request_key == key
    assert first.artifact_link == fx.READY_LINK_RESPONSE["downloadUrl"]
    assert first.outcome == models.OUTCOME_SUCCEEDED

    # The retry names the day of the first close, off that row's own timestamp.
    assert second.outcome == models.OUTCOME_SKIPPED
    assert second.summary == fetch.already_done_summary(first)
    assert second.summary.startswith("already closed on ")
    # ⚠ AND NOTHING WAS SENT THE SECOND TIME. Without this, a run row marked
    # refused over a request that still closed their routes would pass.
    assert len(client.calls) == calls_after_first


@pytest.mark.django_db
def test_tc3_the_key_is_on_the_row_before_the_call_is_made(brazos, dana, monkeypatch):
    """The ORDERING, proved structurally rather than claimed in a comment.

    The head-end is replaced with one that raises. If the key were written when
    the call RETURNED, the row would carry no key — and a retry after exactly
    this kind of failure is the case `BR-INT-020` exists for: the moment the far
    end goes quiet is the moment somebody presses the button again.
    """
    runtime.reset_tokens()

    class Explodes(fx.RecordedHeadEnd):
        def call(self, *, method, url, headers=None, payload=None, timeout_s=30):
            if url.endswith("/oauth/token"):
                return super().call(
                    method=method, url=url, headers=headers, payload=payload, timeout_s=timeout_s
                )
            raise RuntimeError("the head-end went quiet mid-call")

    monkeypatch.setattr(neptune, "HEAD_END_CLIENT", Explodes())
    key = "2026-07:route-south:CloseOnExport"
    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        with pytest.raises(RuntimeError):
            fetch.submit_poll_collect(
                connection=connection,
                operation=_operation(CLOSING_EXPORT),
                adapter=neptune.MetersNeptune360Adapter(),
                parameters={"period": "2026-07", "CloseOnExport": True},
                request_key=key,
            )
        stranded = fetch.previous_request(connection=connection, request_key=key)

    assert stranded is not None, "the key was not on the row when the call failed"
    assert stranded.request_key == key


@pytest.mark.django_db
def test_tc3_a_partner_state_write_with_no_key_is_refused_by_the_caller(brazos, dana, head_end):
    """The registry refuses a MANIFEST with no key source; this refuses a
    CALLER that minted no key VALUE. Two different mistakes, and only the first
    can be caught at load."""
    with tenant_ctx(brazos):
        connection = _with_credential(dana, _connection(brazos))
        with pytest.raises(ValueError) as refused:
            fetch.submit_poll_collect(
                connection=connection,
                operation=_operation(CLOSING_EXPORT),
                adapter=neptune.MetersNeptune360Adapter(),
                parameters={"period": "2026-08"},
            )
    assert "no request key was minted" in str(refused.value)
    assert head_end.calls == []


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — `mutates_partner_state` with no idempotency source is REFUSED AT LOAD
# ═══════════════════════════════════════════════════════════════════════════


def test_tc4_mutates_partner_state_needs_a_key_we_mint_before_the_call():
    """*Refused at load.*

    ⚠ AND IT MUST BE `request_key` SPECIFICALLY, not merely *any* source. A key
    computed from what came BACK — a content hash, the provider's own event id
    — cannot exist before the question is asked, so it cannot refuse the retry
    of a call that has already closed their routes. That is asserted with a
    source which IS a real value in the vocabulary, so the case cannot pass by
    accident on a validation error about something else.
    """
    import dataclasses

    from apps.integrations.registry import Idempotency

    manifest = REGISTRY.require(NEPTUNE)
    closing = next(one for one in manifest.operations if one.name == CLOSING_EXPORT)

    for bad_source in ("none", "content_hash", "natural_key"):
        broken = dataclasses.replace(
            manifest,
            key=f"fixture_{bad_source}",
            operations=(
                dataclasses.replace(
                    closing, idempotency=Idempotency(mode="refuse", source=bad_source)
                ),
            ),
        )
        with pytest.raises(ManifestError) as refused:
            validate(broken)
        assert "changes the partner's state" in str(refused.value)
        assert CLOSING_EXPORT in str(refused.value)

    # ⚠ THE CONTROL — three refusals mean nothing if the validator refuses
    # everything, so the shipped manifest must still pass in the same case.
    validate(manifest)
    assert closing.mutates_partner_state is True
    assert closing.idempotency.source == "request_key"


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — a response amount with no declared unit: the PROJECTION's case, and
#        the projection is Runbooks' (BR-INT-054, CR-069 §20.4)
# ═══════════════════════════════════════════════════════════════════════════


def test_tc5_the_unit_refusal_lives_with_the_projection_which_this_module_does_not_own():
    """`US-INT-035` TC-5 asks for *a response amount field with no declared
    unit in the PROJECTION* to be refused by name. **That case travels with the
    projection**, which `CR-069` §20.4 moves to Runbooks in as many words —
    *"turning what was collected into our measurement frame is ETL"*.

    ⚠ SO THIS IS NOT THE CASE DEFERRED; IT IS THE CASE RE-HOMED, and what is
    asserted here is that the half integrations DOES own is real: the REQUEST
    states its unit explicitly, which is `unit_of_measure` on the manifest's
    safety-parameter list. Hard rule 3 — *consumption always with an explicit
    unit, never assumed* — is met on the way out; meeting it on the way in is
    the projection's job and the door to it returns nothing (asserted in
    `tests/test_us_int_028_token_walk.py`).

    The decision log of 2026-09-06 records this split so a later reader does
    not read the missing assertion as an oversight.
    """
    from apps.integrations.seams import runbooks as runbooks_seam

    assert "unit_of_measure" in _operation(READINGS).safety_parameters
    assert runbooks_seam.projects_nothing() is True


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — two tenants export the same period: two keys, neither refuses the other
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_tc6_two_tenants_closing_the_same_period_do_not_refuse_each_other(
    brazos, lonestar, dana, erin, monkeypatch
):
    """The duplicate lookup is scoped to the CONNECTION, so one utility's close
    can never refuse another's — the same judgment `arrivals.previous_arrival`
    makes for an inbound file.

    ⚠ The two utilities use the SAME key string on purpose. A lookup scoped
    only by the key would refuse the second one, and every other assertion in
    this file would still pass.
    """
    runtime.reset_tokens()
    monkeypatch.setattr(neptune, "HEAD_END_CLIENT", fx.RecordedHeadEnd())
    shared_key = "2026-08:route-north:CloseOnExport"

    with tenant_ctx(brazos):
        one = _with_credential(dana, _connection(brazos))
        run_one = fetch.submit_poll_collect(
            connection=one,
            operation=_operation(CLOSING_EXPORT),
            adapter=neptune.MetersNeptune360Adapter(),
            parameters={"period": "2026-08", "CloseOnExport": True},
            request_key=shared_key,
        )
    runtime.reset_tokens()
    monkeypatch.setattr(neptune, "HEAD_END_CLIENT", fx.RecordedHeadEnd())
    with tenant_ctx(lonestar):
        two = _with_credential(erin, _connection(lonestar))
        run_two = fetch.submit_poll_collect(
            connection=two,
            operation=_operation(CLOSING_EXPORT),
            adapter=neptune.MetersNeptune360Adapter(),
            parameters={"period": "2026-08", "CloseOnExport": True},
            request_key=shared_key,
        )

    assert run_one.outcome == models.OUTCOME_SUCCEEDED
    assert run_two.outcome == models.OUTCOME_SUCCEEDED, "one utility's close refused another's"
    assert run_one.request_key == run_two.request_key == shared_key


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-035 (EP-INT-09) 🔒 + BR-INT-050 · BR-INT-020 · CLAUDE.md hard rule 3 verbatim
# generated: 2026-09-06 by the CR-069 wave K build lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=pending(🔒 HUMAN-REVIEW-PENDING — the row is in 09-human-review-ledger.md)
# gates: pytest tests/test_us_int_035_safety_parameters.py
# exceptions: TC-5's unit refusal is RE-HOMED with the readings projection to Runbooks (CR-069 §20.4) rather than deferred — the request half of hard rule 3 is asserted here and the response half is asserted absent
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
