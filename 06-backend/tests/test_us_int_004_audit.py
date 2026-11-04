# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-004 (EP-INT-01) — connection events → audit_log (masked)
#           + the read-model for consumers. Screens: S8 · S61 (the viewer)
# Rules:    BR-INT-014 (every lifecycle event writes audit_log with who /
#           what / before-after, masked refs) · BR-INT-003 (zero credential
#           bytes in any audit row or read-model response) · BR-INT-008
#           (consumers read the service function, never the tables) ·
#           CLAUDE.md hard rule 7
# Tests:    this file — TC-1 (the four rows, in order) · TC-6 (the dump) ·
#           TC-7 (the read-model under the other tenant)
# Impacts:  apps/integrations/services.py · selectors.py
# ───────────────────────────────────────────────────────
"""US-INT-004 — four lifecycle rows, masked, and a read-model that never crosses a tenant."""

from __future__ import annotations

import json

import pytest

from apps.integrations import services
from apps.integrations.manifests import CONNECTOR_COUNT
from tests.test_us_int_helpers_b import *  # noqa: F401,F403
from tests.test_us_int_helpers_b import GOOD_PASSWORD, SMTP_FIELDS, delete_connection, grid, patch_connection, post_connect, post_test, run_job
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin · audit_rows
from tests.test_us_met_helpers import audit_actions


@pytest.mark.django_db
def test_us_int_004_tc1_the_full_lifecycle_writes_four_rows_in_order_with_actor_and_masked_refs(
    brazos, dana, smtp_adapter, recording_dispatcher, audit_rows
):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    run_job(post_test(brazos, dana, "email_smtp").data)
    patch_connection(brazos, dana, "email_smtp", {"cadence": "hourly"})
    delete_connection(brazos, dana, "email_smtp")
    lifecycle = [one for one in audit_actions(audit_rows) if one.startswith("integration.") and one != "integration.credential.record"]
    assert lifecycle == [
        "integration.connected",
        services.AUDIT_TEST_RUN,
        services.AUDIT_UPDATED,
        services.AUDIT_DISCONNECTED,
    ]
    by_action = {one["action"]: one for one in audit_rows}
    assert by_action["integration.connected"]["actor_user_id"] == dana.user.id
    assert by_action[services.AUDIT_UPDATED]["before"] == {"cadence": "nightly"}
    assert by_action[services.AUDIT_UPDATED]["after"] == {"cadence": "hourly"}
    assert by_action[services.AUDIT_TEST_RUN]["after"]["outcome"] == "succeeded"
    assert len(by_action[services.AUDIT_TEST_RUN]["after"]["trace_id"]) == 8
    assert by_action[services.AUDIT_DISCONNECTED]["after"]["destroyed"] == ["••••kbox"]


@pytest.mark.django_db
def test_us_int_004_tc6_every_audit_row_and_read_model_response_holds_zero_credential_bytes(
    brazos, dana, smtp_adapter, recording_dispatcher, audit_rows
):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    run_job(post_test(brazos, dana, "email_smtp").data)
    dump = json.dumps(audit_rows, default=str) + json.dumps(grid(brazos, dana), default=str)
    assert GOOD_PASSWORD not in dump
    assert "payload_enc" not in dump
    credential_rows = [one for one in audit_rows if one["action"] == "integration.credential.record"]
    assert credential_rows and credential_rows[0]["after"] == {"version": 1, "masked_hint": "••••kbox", "expires_at": None}


@pytest.mark.django_db
def test_us_int_004_tc7_the_read_model_under_lone_star_ridge_holds_its_connections_only(
    brazos, dana, lonestar, erin, smtp_adapter
):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS, label="Brazos mailbox")
    theirs = grid(lonestar, erin)
    # ⚠ **THE LITERAL IS GONE — `DEF-INT-5575`.** This read
    # `{"providers": 18, "connected": 0}` and had been RED since 2026-09-16,
    # when the registry went to 28; `git log -S` puts the expectation at
    # 2026-09-06, so it was wrong for a day before anybody noticed and was filed
    # by a lane reading a failure it did not cause. **A literal in a test is a
    # copy of a fact that has no reason to stay right.**
    #
    # `CONNECTOR_COUNT` is the ONE place this number is declared, and
    # `tests/test_cr110_connectors.py` locks it against `len(MANIFESTS)` and
    # against the loaded registry — so this is not self-referential and it is
    # not `len()` of the thing under test either. What it asserts is what this
    # case is for: **the grid a tenant sees carries every connector we ship.**
    #
    # What TC-7 is actually for is the line below it — Lone Star Ridge's grid
    # names nothing of Brazos Bend's.
    assert theirs["counts"] == {"providers": CONNECTOR_COUNT, "connected": 0}
    assert "Brazos" not in json.dumps(theirs, default=str)
    post_connect(lonestar, erin, "email_smtp", SMTP_FIELDS, label="LSR mailbox")
    assert grid(lonestar, erin)["counts"]["connected"] == 1
    assert grid(brazos, dana)["counts"]["connected"] == 1
