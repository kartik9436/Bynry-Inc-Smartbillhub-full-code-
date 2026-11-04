# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-018 (EP-INT-05) — operations, not providers, are the unit.
#           Screens: S8 · S142
# Rules:    BR-INT-028 (one card, one credential, several things it does; no
#           aggregate word) · BR-INT-037 (the card renders from the registry) ·
#           BR-INT-018 (the outcome is arithmetic)
# Tests:    this file — TC-1, TC-2, TC-4, TC-6; TC-3 is in
#           test_us_int_013_registry.py; TC-5 (S142 groups) lands with wave C
# Impacts:  apps/integrations/selectors.py · services.py
# ───────────────────────────────────────────────────────
"""US-INT-018 — the kiosk card lists three things, each with its own state."""

import pytest

from apps.integrations import api as integrations_api
from apps.integrations import models, selectors, services
from apps.integrations.adapters.base import TestResult
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call


def _kiosk(actor, tenant):
    return services.connect(
        actor=actor,
        tenant_id=tenant.id,
        provider_key="payments_kiosk",
        environment="production",
        label="Kiosk network",
    )


def _grid(tenant, actor):
    response = api_call(
        integrations_api.integrations_grid,
        "get",
        f"/api/{tenant.subdomain}/integrations",
        user=actor.user,
        role="system_admin",
        tenant=tenant,
    )
    assert response.status_code == 200
    return response.data


def _card(data, key):
    return next(one for one in data["providers"] if one["key"] == key)


@pytest.mark.django_db
def test_us_int_018_tc1_one_card_three_rows_one_credential(brazos, dana):
    with tenant_ctx(brazos):
        row = _kiosk(dana, brazos)
        services.record_credential(actor=dana, connection=row, payload="k", masked_hint="••••K1OS")
    card = _card(_grid(brazos, dana), "payments_kiosk")
    assert [one["label"] for one in card["operations"]] == ["Payments", "Account lookup", "Returns"]
    assert card["connection"]["credential"] == {
        "version": 1,
        "hint": "••••K1OS",
        "expires_at": None,
    }
    assert models.IntegrationCredential.objects.filter(connection=row).count() == 1
    # the card is ONE provider row, not three
    assert sum(1 for one in _grid(brazos, dana)["providers"] if one["key"] == "payments_kiosk") == 1


@pytest.mark.django_db
def test_us_int_018_tc2_returns_failed_and_payments_working_read_differently(brazos, dana):
    with tenant_ctx(brazos):
        row = _kiosk(dana, brazos)
        payments = services.start_run(
            connection=row, operation="payments", direction="inbound", trigger="webhook"
        )
        services.finish_run(
            payments, attempted=41, succeeded=41, failed=0, skipped=0, confirmed=True
        )
        returns = services.start_run(
            connection=row, operation="returns", direction="inbound", trigger="webhook"
        )
        services.finish_run(
            returns,
            attempted=1,
            succeeded=0,
            failed=1,
            skipped=0,
            confirmed=True,
            summary="the return named a payment we do not hold",
        )
    card = _card(_grid(brazos, dana), "payments_kiosk")
    by_name = {one["name"]: one for one in card["operations"]}
    assert by_name["payments"]["state"] == "working"
    assert by_name["payments"]["last_outcome"] == "succeeded"
    assert by_name["returns"]["state"] == "not_working"
    assert by_name["returns"]["last_outcome"] == "failed"
    assert by_name["account_lookup"]["state"] == "untested"
    assert by_name["account_lookup"]["last_run_at"] is None
    # NO aggregate word: display_state is the connection's own status, not an
    # average of the three — and the screen draws rows, never a headline.
    assert card["display_state"] == "untested"  # the connection was never tested
    assert len(card["operations"]) == 3


@pytest.mark.django_db
def test_us_int_018_tc4_every_operation_row_carries_the_declared_shape(brazos, dana):
    with tenant_ctx(brazos):
        _kiosk(dana, brazos)
    card = _card(_grid(brazos, dana), "payments_kiosk")
    for one in card["operations"]:
        assert set(one) >= {
            "name",
            "direction",
            "initiative",
            "state",
            "last_run_at",
            "last_outcome",
        }
        assert one["direction"] == "in" and one["initiative"] == "them"
    # ⚠ **THIS COMMENT READ *"a single-operation provider shows its operation's
    # state as the card state"* UNTIL 2026-09-17 (`DEF-INT-5597`), AND THE
    # ASSERTION UNDER IT COULD NEVER HAVE CHECKED THAT.** With no connection at
    # all, BOTH candidate facts are `not_set_up`, so the line is true whichever
    # one the code picks — law 7's *structurally incapable of failing*, sitting
    # under a comment that claimed the very behaviour it could not see.
    # It stays, because *a connector nobody has set up says so on the card AND
    # on every API row* is worth pinning; what it does not do is decide the
    # subject of the State column. The decisive cases are at the end of this
    # file and each asserts its two facts DIFFER before saying which one wins.
    smtp = _card(_grid(brazos, dana), "email_smtp")
    assert smtp["connection"] is None  # ← the reason both words agree here
    assert len(smtp["operations"]) == 1
    assert smtp["display_state"] == smtp["operations"][0]["state"] == "not_set_up"


@pytest.mark.django_db
def test_us_int_018_a_one_api_connector_does_not_take_its_operations_word(brazos, dana):
    """⚠ **THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-09-17, AND IT WAS THE ONE
    THING HOLDING `DEF-INT-5597` IN PLACE.** It was named
    `…_takes_its_operations_word` and required `display_state == "working"`
    here, so the defect could not be fixed without it going red — the shape
    this repo already records at `DEF-INT-3721`: a test holding a superseded
    reading in place. It was RIGHT on the card, where one API was the whole
    connector; the table put an APIs column beside the State column and the
    substitution became a wrong answer under a heading that promises another.

    ⚠ **AND READ WHAT IT USED TO ASSERT, BECAUSE IT IS A SECOND DEFECT WRITTEN
    DOWN AS AN EXPECTATION.** The connector below has never been TESTED — its
    status is `untested` and `last_test_at` is None — and one run SUCCEEDED.
    The old line called that *Working*. A run is not a test: `DEF-INT-5598`
    records that `connection.status` moves on an explicit test, on a credential
    change and on three consecutive timeouts, **and on nothing else**, so a
    successful run must not promote the connector's word any more than a failed
    one demotes it.
    """
    with tenant_ctx(brazos):
        row = services.connect(
            actor=dana, tenant_id=brazos.id, provider_key="email_smtp", environment="production"
        )
        run = services.start_run(
            connection=row, operation="send_message", direction="outbound", trigger="dispatcher"
        )
        services.finish_run(run, attempted=93, succeeded=93, failed=0, skipped=0, confirmed=True)
        row.refresh_from_db()
        assert row.last_test_at is None  # nobody has tested this connector
    smtp = _card(_grid(brazos, dana), "email_smtp")
    # ⚠ DECISIVE ONLY WHILE THE TWO DIFFER — assert that, then the subject.
    assert smtp["operations"][0]["state"] == "working"
    assert smtp["connection"]["status"] == models.STATUS_UNTESTED
    assert smtp["display_state"] == models.STATUS_UNTESTED


@pytest.mark.django_db
def test_us_int_018_tc6_lone_star_ridge_gets_three_rows_all_not_set_up_and_no_last_run(
    brazos, dana, lonestar, erin
):
    with tenant_ctx(brazos):
        row = _kiosk(dana, brazos)
        run = services.start_run(
            connection=row, operation="payments", direction="inbound", trigger="webhook"
        )
        services.finish_run(run, attempted=41, succeeded=41, failed=0, skipped=0, confirmed=True)
    card = _card(_grid(lonestar, erin), "payments_kiosk")
    assert card["connection"] is None
    assert [one["state"] for one in card["operations"]] == ["not_set_up"] * 3
    assert all(one["last_run_at"] is None for one in card["operations"])


def test_us_int_018_the_outcome_is_arithmetic_not_a_word_a_caller_types():
    """BR-INT-018 — one place chooses the word."""
    assert (
        services.outcome_for(attempted=93, succeeded=93, failed=0, skipped=0, confirmed=True)
        == "succeeded"
    )
    assert (
        services.outcome_for(attempted=93, succeeded=86, failed=7, skipped=0, confirmed=True)
        == "partial"
    )
    assert (
        services.outcome_for(attempted=1, succeeded=0, failed=1, skipped=0, confirmed=True)
        == "failed"
    )
    # 200 with no count → unconfirmed, never succeeded and never rounded down
    assert (
        services.outcome_for(attempted=93, succeeded=93, failed=0, skipped=0, confirmed=False)
        == "unconfirmed"
    )
    # the arithmetic does not hold → unconfirmed
    assert (
        services.outcome_for(attempted=93, succeeded=90, failed=0, skipped=0, confirmed=True)
        == "unconfirmed"
    )
    assert (
        services.outcome_for(
            attempted=1, succeeded=0, failed=0, skipped=0, confirmed=False, indeterminate=True
        )
        == "indeterminate"
    )


def test_us_int_018_reading_from_us_is_computed_never_stored():
    """State 6 of frame 48.1 — not a value of the status column."""
    assert selectors.DISPLAY_READING_FROM_US not in models.STATUSES
    assert len(models.STATUSES) == 5


# ═══════════════════════════════════════════════════════════════════════════
# DEF-INT-5597 — THE STATE COLUMN IS THE CONNECTOR'S, ON EVERY ROW
# ═══════════════════════════════════════════════════════════════════════════
#
# Product Owner, 2026-09-17, looking at the connector TABLE (`CON-01`):
#     *"Here in Table - State - it should be for conenctor not for APis - you
#     are showing the wrong status"*
# and, on what the word MEANS:
#     *"Connector status is with respect ot partner and that tenant - so it
#     will be tenant /utility speicific"*
#
# ⚠ **WHAT WOULD MAKE THESE TESTS PASS WRONGLY, AND WHAT IS DONE ABOUT IT.**
# On 26 of the 28 connectors a tenant actually holds, the connection's status
# and its operations' states AGREE — so an assertion of the form
# `display_state == connection.status` is true on almost every row whichever
# value the code picks, and proves nothing at all. Every case below therefore
# asserts the DISAGREEMENT FIRST: it states, as its own assertion, that the two
# candidate facts are different on this fixture, and only then says which one
# the card must carry. Delete that first assertion and the rest becomes a
# coincidence detector.


@pytest.mark.django_db
def test_def_int_5597_a_one_api_connector_shows_the_connection_not_the_api(brazos, dana):
    """A single-API connector nobody has TESTED, whose one RUN failed.

    Before this defect was fixed the card read `not_working` — the API's word —
    so the State column said *Not working* about a connector whose STATE is
    *Not tested yet*, with `1 · 0 working` in the APIs column immediately
    beside it saying the same thing under the heading that owns it.
    """
    with tenant_ctx(brazos):
        row = services.connect(
            actor=dana, tenant_id=brazos.id, provider_key="email_smtp", environment="production"
        )
        run = services.start_run(
            connection=row, operation="send_message", direction="outbound", trigger="dispatcher"
        )
        services.finish_run(
            run, attempted=1, succeeded=0, failed=1, skipped=0, confirmed=True,
            summary="the mail server refused the password",
        )
        row.refresh_from_db()
        connection_status = row.status

    smtp = _card(_grid(brazos, dana), "email_smtp")
    assert len(smtp["operations"]) == 1
    # ⚠ THE CASE IS ONLY DECISIVE WHILE THESE TWO DIFFER — assert it.
    assert connection_status == models.STATUS_UNTESTED
    assert smtp["operations"][0]["state"] == models.STATUS_NOT_WORKING
    assert smtp["operations"][0]["state"] != connection_status
    # …and the card carries the CONNECTION's.
    assert smtp["display_state"] == connection_status == models.STATUS_UNTESTED
    # The row's four actions turn on `not_set_up` alone, so this must not move.
    assert smtp["display_state"] != models.STATUS_NOT_SET_UP
    assert smtp["connection"]["status"] == models.STATUS_UNTESTED


@pytest.mark.django_db
def test_def_int_5597_two_utilities_on_one_connector_each_see_their_own_word(
    brazos, dana, lonestar, erin
):
    """*"…with respect ot partner and that tenant"* — the PO's own reasoning.

    Two utilities, ONE single-API connector, DIFFERENT states. Each reads its
    own. This is the case the suite did not have, which is why nothing failed:
    every existing grid case has one tenant connected at a time, so a value
    leaking across utilities would have been invisible.

    ⚠ **THIS PROVES THE QUERY NAMES THE UTILITY, NOT THAT THE DATABASE WOULD
    STOP IT.** The suite runs on in-memory SQLite (`config/settings/test.py`,
    hard-won law 14), which has no row-level security at all, so RLS `FORCE` is
    not exercised here and cannot be. The RLS half is `10-scripts/prove_isolation.py`
    against a real PostgreSQL; this case is the other half and the two are not
    substitutes for one another.
    """
    with tenant_ctx(brazos):
        theirs = services.connect(
            actor=dana, tenant_id=brazos.id, provider_key="email_smtp", environment="production"
        )
        test_run = services.start_run(
            connection=theirs, operation="send_message", direction="outbound", trigger="manual"
        )
        services.record_test_result(
            actor=dana,
            connection=theirs,
            run=test_run,
            result=TestResult(ok=True, sentence="Sent one test message."),
        )
    with tenant_ctx(lonestar):
        ours = services.connect(
            actor=erin, tenant_id=lonestar.id, provider_key="email_smtp", environment="production"
        )
        failed = services.start_run(
            connection=ours, operation="send_message", direction="outbound", trigger="dispatcher"
        )
        services.finish_run(
            failed, attempted=1, succeeded=0, failed=1, skipped=0, confirmed=True,
            summary="the mail server refused the password",
        )

    brazos_card = _card(_grid(brazos, dana), "email_smtp")
    lonestar_card = _card(_grid(lonestar, erin), "email_smtp")

    # ⚠ DECISIVE ONLY WHILE THE TWO UTILITIES DISAGREE — assert that first.
    assert brazos_card["display_state"] != lonestar_card["display_state"]
    # Brazos Bend tested it and it worked.
    assert brazos_card["display_state"] == models.STATUS_WORKING
    # Lone Star Ridge never tested it; one run failed. The CONNECTOR is
    # untested — which is the whole of this defect, because the API is not.
    assert lonestar_card["operations"][0]["state"] == models.STATUS_NOT_WORKING
    assert lonestar_card["display_state"] == models.STATUS_UNTESTED
