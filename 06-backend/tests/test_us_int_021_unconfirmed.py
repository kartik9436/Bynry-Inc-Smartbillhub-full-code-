# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-021 (EP-INT-06) — the unconfirmed outcome: a run whose
#           numbers cannot be reconciled says so. Screens: S142 · S8
# Rules:    BR-INT-018 (`succeeded` only when `attempted = succeeded + failed +
#           skipped` AND the far end confirmed a count; otherwise
#           `unconfirmed`, never rounded down to `failed` and never up to
#           green) · BR-INT-040 (P4 — per-item results, never a batch boolean)
# Tests:    this file — TC-1 (the no-count fixture) · **TC-2, the RED-FIRST
#           proof**: the stub that always writes `succeeded` is BUILT here and
#           TC-1 is run against it, and the test asserts that it FAILS ·
#           TC-3 (86 + 7 named) · TC-4 (the double count) · TC-5 (93 of 93) ·
#           TC-6 (the send half; bounces stay *not reported*)
# Impacts:  apps/integrations/services.py (`outcome_for` · `finish_run`) ·
#           apps/integrations/selectors.py (the S8 panel's word)
# ───────────────────────────────────────────────────────
"""US-INT-021 — *we do not know* is an answer, and a green tick is not.

⚠ THE RED RUN THIS STORY ASKS FOR IS `test_us_int_021_tc2_...` BELOW, AND IT
IS NOT A COMMENT. The story says so in capital letters: TC-1 *"is trivially
satisfied by a stub that always writes `succeeded`"*, so the proof that the
guard can go red has to be executable. `_AlwaysSucceeded` is that stub — the
naive implementation a lane would write on a Friday — and TC-2 drives the
no-count fixture through it and asserts the assertion fails. Hard-won law 7:
prove a new guard goes RED before trusting it green.
"""

from __future__ import annotations

import pytest

from apps.integrations import models, selectors, services
from apps.integrations.adapters.base import ItemResult, RunResult
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx

SMTP = "email_smtp"


def _connection(tenant, label="billing@brazosbend.example"):
    return models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=SMTP,
        label=label,
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_UNTESTED,
        cadence=models.CADENCE_MANUAL,
        config={},
    )


def _run(connection, trigger="scheduled"):
    return services.start_run(
        connection=connection, operation="send_message", direction="outbound", trigger=trigger
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the provider answered 200 and would not say how many it accepted
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_int_021_tc1_a_provider_that_will_not_say_is_unconfirmed(brazos):
    """93 handed over, no count back. Not succeeded. Not failed. Unconfirmed."""
    with tenant_ctx(brazos):
        run = services.finish_run(
            _run(_connection(brazos)),
            attempted=93,
            succeeded=0,
            failed=0,
            skipped=0,
            confirmed=False,
            summary="We handed over 93 messages and the provider did not say how many it accepted.",
        )
    assert run.outcome == models.OUTCOME_UNCONFIRMED
    assert run.outcome != models.OUTCOME_SUCCEEDED
    assert run.outcome != models.OUTCOME_FAILED  # never rounded DOWN either
    assert run.attempted == 93
    # The dashes on frame 51.2 are these zeroes NOT being claims: the screen
    # renders a dash for every count on an unconfirmed run, and the test that
    # it does is ConnectionDetailPage.test.tsx. Here we only assert that the
    # runtime made no claim it could not support.
    assert (run.succeeded, run.failed, run.skipped) == (0, 0, 0)


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — THE RED-FIRST PROOF. A stub that always writes `succeeded`.
# ═══════════════════════════════════════════════════════════════════════════


class _AlwaysSucceeded:
    """The naive runtime `US-INT-021` names: the far end answered 200, so the
    run succeeded. It is a real, runnable implementation of `outcome_for` —
    not a mock — because a stub that cannot be run cannot be shown to fail."""

    @staticmethod
    def outcome_for(
        *,
        attempted,
        succeeded,
        failed,
        skipped,
        confirmed,
        indeterminate=False,
        never_dialled=False,
        **_later,
    ):
        # ⚠ `**_later` IS NOT LAZINESS, IT IS THIS STUB'S JOB. It stands in for
        # a naive implementation that ignores everything it is told and says
        # `succeeded`, so it must keep accepting whatever the real
        # `outcome_for` accepts — otherwise it stops failing for the right
        # reason and starts failing with a `TypeError`, which passes
        # `pytest.raises(AssertionError)` nowhere and reads as an environment
        # problem. That is exactly what happened when `CR-069` wave F added
        # `never_dialled` (2026-09-05): this file went red with a Redis
        # connection error in the teardown noise and looked like a broker
        # outage. `never_dialled` is named explicitly above it because it is
        # the one this stub would most plausibly get wrong on purpose — a
        # window nobody dialled, reported as 93 bills sent.
        return models.OUTCOME_SUCCEEDED


@pytest.mark.django_db
def test_us_int_021_tc2_the_always_succeeded_stub_fails_tc1(brazos, monkeypatch):
    """Run TC-1's fixture against the stub and assert the assertion FAILS.

    This is the recorded red run. When it stops failing, either the stub has
    been fixed (fine — delete it and this test with it) or `finish_run` has
    stopped computing the outcome and started taking a caller's word for it,
    which is the defect this whole story exists to prevent.
    """
    monkeypatch.setattr(services, "outcome_for", _AlwaysSucceeded.outcome_for)
    with tenant_ctx(brazos):
        run = services.finish_run(
            _run(_connection(brazos)),
            attempted=93,
            succeeded=0,
            failed=0,
            skipped=0,
            confirmed=False,
        )
    # The stub's answer, and it is exactly the lie the story warns about:
    assert run.outcome == models.OUTCOME_SUCCEEDED
    # …and TC-1's assertion, run against it, fails. Quoted in the wave report.
    with pytest.raises(AssertionError):
        assert run.outcome == models.OUTCOME_UNCONFIRMED, (
            "a stub that always writes `succeeded` reports 93 unsent bills as sent"
        )


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 · TC-4 · TC-5 — the arithmetic, in the three shapes that matter
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_int_021_tc3_eighty_six_of_ninety_three_is_partial_and_the_seven_are_named(brazos):
    with tenant_ctx(brazos):
        run = services.finish_run(
            _run(_connection(brazos)),
            attempted=93,
            succeeded=86,
            failed=7,
            skipped=0,
            confirmed=True,
            summary="Seven addresses were refused by the mail server.",
            items=[
                ItemResult(ref=f"A-104{n:02d}", outcome="failed", detail=f"x{n}@example.invalid",
                           provider_text="No such mailbox")
                for n in range(7)
            ],
        )
    assert run.outcome == models.OUTCOME_PARTIAL
    assert len(run.items) == 7  # named, not counted (BR-INT-040)
    assert {one["outcome"] for one in run.items} == {"failed"}


@pytest.mark.django_db
def test_us_int_021_tc4_a_double_counted_item_does_not_reconcile(brazos):
    """`succeeded = 93` against `attempted = 92`: the arithmetic does not hold,
    so the run cannot claim success — and it does not claim failure either."""
    with tenant_ctx(brazos):
        run = services.finish_run(
            _run(_connection(brazos)),
            attempted=92,
            succeeded=93,
            failed=0,
            skipped=0,
            confirmed=True,
            summary="The provider reported more messages than we handed over.",
        )
    assert run.outcome == models.OUTCOME_UNCONFIRMED
    assert "more messages than we handed over" in run.summary


@pytest.mark.django_db
def test_us_int_021_tc5_ninety_three_of_ninety_three_confirmed_is_succeeded(brazos):
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        run = services.finish_run(
            _run(connection),
            attempted=93, succeeded=93, failed=0, skipped=0, confirmed=True,
        )
        assert run.outcome == models.OUTCOME_SUCCEEDED
        assert selectors.operation_state(connection, run) == models.STATUS_WORKING


# ═══════════════════════════════════════════════════════════════════════════
# TC-1's other half — the S8 panel shows ATTENTION for an unconfirmed run
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_int_021_tc1_the_grid_panel_is_never_green_for_an_unconfirmed_run(brazos):
    """*"the S8 provider-status panel treats it as needing attention, never as
    green"*. `working` is the green word; an unconfirmed run must not produce
    it, and the outcome itself travels beside the state so the card can say
    the honest word rather than only the red one."""
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        run = services.finish_run(
            _run(connection), attempted=93, succeeded=0, failed=0, skipped=0, confirmed=False
        )
        assert selectors.operation_state(connection, run) != models.STATUS_WORKING
        card = selectors.provider_card(brazos.id, SMTP)
    operation = next(one for one in card["operations"] if one["name"] == "send_message")
    assert operation["state"] != models.STATUS_WORKING
    assert operation["last_outcome"] == models.OUTCOME_UNCONFIRMED
    assert card["display_state"] != models.STATUS_WORKING


# ═══════════════════════════════════════════════════════════════════════════
# The adapter's own arithmetic — `RunResult.counts` and `confirmed`
# ═══════════════════════════════════════════════════════════════════════════


def test_us_int_021_the_adapter_states_counts_and_never_the_word():
    """BR-INT-040: per-item results, never a batch boolean. `RunResult` has no
    `outcome` field at all — an adapter physically cannot type `succeeded`."""
    result = RunResult(
        items=(
            ItemResult(ref="A-1", outcome="succeeded"),
            ItemResult(ref="A-2", outcome="failed", provider_text="No such mailbox"),
            ItemResult(ref="A-3", outcome="skipped"),
        ),
        confirmed=True,
    )
    assert result.counts == {"attempted": 3, "succeeded": 1, "failed": 1, "skipped": 1}
    assert not hasattr(result, "outcome")
    assert services.outcome_for(**result.counts, confirmed=result.confirmed) == (
        models.OUTCOME_PARTIAL
    )
    # …and the same counts with a provider that would not confirm:
    assert services.outcome_for(**result.counts, confirmed=False) == models.OUTCOME_UNCONFIRMED
