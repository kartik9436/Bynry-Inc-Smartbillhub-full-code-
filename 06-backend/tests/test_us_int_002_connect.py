# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-002 (EP-INT-01) — the connect modal's four endpoints: save
#           encrypts, test verifies, failures surface. US-INT-019 TC-6 (a
#           sandbox connection reads Sandbox and is never handed a real
#           batch). US-INT-015 TC-1 · TC-2 (the recorded SMTP fixture through
#           the runtime). Screens: S141 · S8
# Rules:    BR-INT-002 (the endpoint set) · BR-INT-003 (never rendered back,
#           never logged, never in an audit payload) · BR-INT-015 (a failed
#           test rests the card at *Not working* with the provider's words —
#           never silent) · BR-INT-025 (a credential is versioned) ·
#           BR-INT-026 (two environments are two rows; a sandbox is never
#           handed a real batch) · BR-INT-016 (disconnect destroys the
#           secret, keeps the history; reconnect needs fresh credentials)
# Tests:    this file — US-INT-002 TC-1..5 · TC-7 · US-INT-019 TC-6 · the
#           PATCH / DELETE / credential / run routes
# Impacts:  apps/integrations/api.py · services.py · selectors.py · jobs.py
# ───────────────────────────────────────────────────────
"""US-INT-002 — connecting through the API, end to end, against the recorded SMTP fixture."""

from __future__ import annotations

import json
import logging

import pytest

from apps.integrations import conformance, models, services
from tests.test_us_int_helpers_b import *  # noqa: F401,F403
from tests.test_us_int_helpers_b import (
    BAD_PASSWORD,
    GOOD_PASSWORD,
    RECIPIENT,
    SMTP_FIELDS,
    card,
    counts,
    delete_connection,
    grid,
    patch_connection,
    post_connect,
    post_credential,
    post_run,
    post_test,
    run_job,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin · audit_rows


@pytest.mark.django_db
def test_us_int_002_tc1_connect_then_test_stores_v1_runs_one_real_message_and_turns_the_card_working(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    response = post_connect(brazos, dana, "email_smtp", SMTP_FIELDS, label="Billing mailbox")
    assert response.status_code == 201, response.data
    assert response.data["key"] == "email_smtp"
    assert response.data["state"] == "untested"
    row = models.IntegrationConnection.objects.get(tenant_id=brazos.id, provider_key="email_smtp")
    assert row.environment == "production" and row.cadence == "nightly"
    assert row.connected_by_id == dana.user.id and row.connected_at is not None
    assert "password" not in row.config, "the secret landed in the non-secret column"
    credential = models.IntegrationCredential.objects.get(connection=row)
    assert credential.version == 1 and credential.is_active
    assert credential.masked_hint == "••••kbox"  # the last four of Ew3!kQ9-lockbox

    accepted = post_test(brazos, dana, "email_smtp")
    assert accepted.status_code == 202
    assert set(accepted.data) == {"job_id", "status_url"}
    run_job(accepted.data)
    row.refresh_from_db()
    assert row.status == "working" and row.last_test_ok is True
    assert row.last_test_text == f"Sent one test message to {RECIPIENT}."
    run = models.IntegrationRun.objects.get(connection=row)
    assert run.outcome == "succeeded" and run.trigger == "manual" and run.finished_at is not None
    assert len(run.trace_id) == 8


@pytest.mark.django_db
def test_us_int_002_tc2_reopening_shows_the_masked_hint_and_the_secret_appears_nowhere(
    brazos, dana, smtp_adapter, recording_dispatcher, caplog, audit_rows
):
    caplog.set_level(logging.DEBUG)
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    run_job(post_test(brazos, dana, "email_smtp").data)
    payload = grid(brazos, dana)
    smtp = card(brazos, dana, "email_smtp")
    assert smtp["connection"]["credential"] == {"version": 1, "hint": "••••kbox", "expires_at": None}
    assert smtp["connection"]["describe"] == "billing@brazosbend.example · Custom SMTP"
    assert smtp["connection"]["connected_by"] == dana.user.full_name
    assert GOOD_PASSWORD not in json.dumps(payload, default=str)
    assert GOOD_PASSWORD not in caplog.text
    assert GOOD_PASSWORD not in json.dumps(audit_rows, default=str)
    stored = models.IntegrationCredential.objects.get(connection__provider_key="email_smtp")
    raw = models.IntegrationCredential.objects.filter(pk=stored.pk).values_list("payload_enc", flat=True)
    # The field decrypts on read; the row's ciphertext is asserted through the
    # crypto module's own marker in test_us_int_014_tables — here: the wire.
    assert stored.masked_hint != GOOD_PASSWORD and len(raw) == 1


@pytest.mark.django_db
def test_us_int_002_tc3_sandbox_first_then_production_are_two_rows_with_two_credentials(
    brazos, dana, smtp_adapter
):
    first = post_connect(brazos, dana, "email_smtp", SMTP_FIELDS, environment="sandbox")
    assert first.status_code == 201
    again = post_connect(brazos, dana, "email_smtp", SMTP_FIELDS, environment="sandbox")
    assert again.status_code == 409 and again.data["message_key"] == services.REFUSAL_ALREADY_CONNECTED
    second = post_connect(
        brazos, dana, "email_smtp", {**SMTP_FIELDS, "password": "a-different-production-one"}
    )
    assert second.status_code == 201
    rows = {one.environment: one for one in models.IntegrationConnection.objects.filter(tenant_id=brazos.id)}
    assert set(rows) == {"sandbox", "production"}
    hints = {env: models.IntegrationCredential.objects.get(connection=row).masked_hint for env, row in rows.items()}
    assert hints == {"sandbox": "••••kbox", "production": "••••-one"}
    smtp = card(brazos, dana, "email_smtp")
    assert smtp["connection"]["environment"] == "production"  # the card is decided by production
    assert [one["environment"] for one in smtp["connections"]] == ["production", "sandbox"]


@pytest.mark.django_db
def test_us_int_002_tc4_a_failed_test_rests_the_card_at_not_working_with_the_providers_words(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    post_connect(brazos, dana, "email_smtp", {**SMTP_FIELDS, "password": BAD_PASSWORD})
    run_job(post_test(brazos, dana, "email_smtp").data)
    row = models.IntegrationConnection.objects.get(provider_key="email_smtp")
    assert row.status == "not_working" and row.last_test_ok is False
    assert row.last_test_text == "The mail server rejected the password."
    run = models.IntegrationRun.objects.get(connection=row)
    assert run.outcome == "failed"
    assert run.summary == "The mail server rejected the password."
    assert run.provider_error == "535 5.7.8 AUTHENTICATION FAILED"
    smtp = card(brazos, dana, "email_smtp")
    assert smtp["state"] == "not_working"
    # Retry re-runs the test without re-entering the key: a second 202.
    retry = post_test(brazos, dana, "email_smtp")
    assert retry.status_code == 202


@pytest.mark.django_db
def test_us_int_002_tc5_a_first_connect_with_no_credential_creates_no_empty_secret_row(brazos, dana, smtp_adapter):
    response = post_connect(brazos, dana, "email_smtp", {**SMTP_FIELDS, "password": ""})
    assert response.status_code == 422
    assert {one["field"] for one in response.data["field_errors"]} == {"password"}
    assert counts() == {"connections": 0, "credentials": 0, "runs": 0}


@pytest.mark.django_db
def test_us_int_002_tc7_two_tenants_connect_the_same_provider_and_never_see_each_other(
    brazos, dana, lonestar, erin, smtp_adapter
):
    assert post_connect(brazos, dana, "email_smtp", SMTP_FIELDS, label="Brazos mailbox").status_code == 201
    assert post_connect(lonestar, erin, "email_smtp", {**SMTP_FIELDS, "password": "lone-star-secret"}, label="LSR mailbox").status_code == 201
    assert models.IntegrationConnection.objects.count() == 2
    assert models.IntegrationCredential.objects.count() == 2
    lsr = card(lonestar, erin, "email_smtp")
    assert lsr["connection"]["label"] == "LSR mailbox"
    assert lsr["connection"]["credential"]["hint"] == "••••cret"
    assert "Brazos" not in json.dumps(grid(lonestar, erin), default=str)


@pytest.mark.django_db
def test_us_int_019_tc6_a_sandbox_connection_reads_sandbox_and_is_never_handed_a_real_batch(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS, environment="sandbox")
    smtp = card(brazos, dana, "email_smtp")
    assert smtp["connection"]["environment"] == "sandbox"  # the word is the catalogue's
    refused = post_run(brazos, dana, "email_smtp", "send_message", work=[{"ref": "A-1"}])
    assert refused.status_code == 409
    assert refused.data["message_key"] == services.REFUSAL_SANDBOX_ONLY
    assert models.IntegrationRun.objects.count() == 0


@pytest.mark.django_db
def test_us_int_002_patch_changes_non_secret_settings_and_refuses_a_secret_or_an_unknown_one(
    brazos, dana, smtp_adapter, audit_rows
):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    ok = patch_connection(brazos, dana, "email_smtp", {"cadence": "hourly", "label": "Renamed"})
    assert ok.status_code == 200 and ok.data["connection"]["cadence"] == "hourly"
    updated = [one for one in audit_rows if one["action"] == services.AUDIT_UPDATED]
    assert updated and updated[-1]["before"] == {"label": None, "cadence": "nightly"}
    assert updated[-1]["after"] == {"label": "Renamed", "cadence": "hourly"}
    unknown = patch_connection(brazos, dana, "email_smtp", {"colour": "teal"})
    assert unknown.status_code == 422 and unknown.data["field_errors"][0]["field"] == "colour"
    secret = patch_connection(brazos, dana, "email_smtp", {"config": {"password": "x"}})
    assert secret.status_code == 422 and secret.data["field_errors"][0]["field"] == "password"
    bad_config = patch_connection(brazos, dana, "email_smtp", {"config": {"port": "abc"}})
    assert bad_config.status_code == 422 and bad_config.data["field_errors"][0]["field"] == "port"
    row = models.IntegrationConnection.objects.get(provider_key="email_smtp")
    assert row.config["port"] == "587"  # the refused PATCH changed nothing


@pytest.mark.django_db
def test_us_int_002_delete_destroys_every_credential_keeps_the_runs_and_a_reconnect_needs_a_fresh_one(
    brazos, dana, smtp_adapter, recording_dispatcher, audit_rows
):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    run_job(post_test(brazos, dana, "email_smtp").data)
    assert post_credential(brazos, dana, "email_smtp", {"password": "second-version-9Z11"}).status_code == 200
    assert models.IntegrationCredential.objects.count() == 2
    gone = delete_connection(brazos, dana, "email_smtp")
    assert gone.status_code == 200 and gone.data["state"] == "off"
    assert models.IntegrationCredential.objects.count() == 0, "a destroyed secret must not linger"
    assert models.IntegrationRun.objects.count() == 1, "history is kept"
    row = models.IntegrationConnection.objects.get(provider_key="email_smtp")
    assert row.status == "off" and row.enabled is False
    disconnected = [one for one in audit_rows if one["action"] == services.AUDIT_DISCONNECTED]
    assert disconnected[-1]["after"]["destroyed"] == ["••••kbox", "••••9Z11"]
    assert GOOD_PASSWORD not in json.dumps(disconnected, default=str)
    # Disconnected: nothing to test, nothing to disconnect again.
    assert post_test(brazos, dana, "email_smtp").data["message_key"] == services.REFUSAL_NOT_CONNECTED
    assert delete_connection(brazos, dana, "email_smtp").data["message_key"] == services.REFUSAL_NOT_CONNECTED
    # Reconnect reuses the row and needs a credential typed again.
    assert post_connect(brazos, dana, "email_smtp", {**SMTP_FIELDS, "password": ""}).status_code == 422
    back = post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    assert back.status_code == 201 and back.data["state"] == "untested"
    assert models.IntegrationConnection.objects.count() == 1
    assert models.IntegrationCredential.objects.count() == 1


@pytest.mark.django_db
def test_us_int_002_credential_rotation_writes_v2_and_deactivates_v1(brazos, dana, smtp_adapter):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    response = post_credential(brazos, dana, "email_smtp", {"password": "rotated-A17C"})
    assert response.status_code == 200  # a mail test needs a typed address, so none is queued blind
    versions = list(
        models.IntegrationCredential.objects.filter(connection__provider_key="email_smtp")
        .order_by("version")
        .values_list("version", "is_active", "masked_hint")
    )
    assert versions == [(1, False, "••••kbox"), (2, True, "••••A17C")]
    refused = post_credential(brazos, dana, "email_smtp", {"host": "x"})
    assert refused.status_code == 422 and refused.data["field_errors"][0]["field"] == "host"


@pytest.mark.django_db
def test_us_int_002_a_manual_run_enqueues_and_the_body_records_per_item_counts(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    accepted = post_run(brazos, dana, "email_smtp", "send_message", work=[{"ref": "A-1"}, {"ref": "A-2"}])
    assert accepted.status_code == 202
    in_flight = post_run(brazos, dana, "email_smtp", "send_message", work=[{"ref": "A-3"}])
    assert in_flight.status_code == 409 and in_flight.data["message_key"] == services.REFUSAL_RUN_IN_FLIGHT
    run_job(accepted.data)
    run = models.IntegrationRun.objects.get(operation="send_message")
    assert (run.attempted, run.succeeded, run.failed, run.skipped, run.outcome) == (2, 2, 0, 0, "succeeded")
    unknown = post_run(brazos, dana, "email_smtp", "no_such_operation")
    assert unknown.status_code == 422 and unknown.data["message_key"] == services.REFUSAL_UNKNOWN_OPERATION


@pytest.mark.django_db
def test_us_int_002_an_operation_the_partner_starts_is_not_ours_to_run(brazos, dana, bind_adapter, recording_dispatcher):
    bind_adapter("payments_kiosk", conformance.RecordedSmtpAdapter)  # any adapter; the refusal is earlier
    assert post_connect(brazos, dana, "payments_kiosk", {"allowed_addresses": "198.51.100.0/24"}).status_code == 201
    refused = post_run(brazos, dana, "payments_kiosk", "payments")
    assert refused.status_code == 409 and refused.data["message_key"] == services.REFUSAL_NOT_OURS_TO_START


# ── DEF-INT-5582 · a retired manifest field freezes the connection for ever ──
#
# ⚠ **THIS IS THE `DEF-INT-5581` BLOCKER'S SECOND HALF, AND IT IS THE HALF THAT
# BITES ON THE PO'S OWN CONNECTOR.** Wiring S147's *Save* to `PATCH` fixes
# nothing on `erp_aclarian`, because that connection's stored `config` still
# holds `scopes` and `client_id` — values written when the manifest declared
# those fields, and retired from all five ERP manifests by `CR-110-BRC04` wave
# A. `update_connection` merged the stored half into the supplied half and then
# validated the MERGE, so `validate_fields` refused two names the clerk never
# sent. Measured through the real door on 2026-09-17, before the fix:
#
#     PATCH /api/brazosbend/integrations/erp_aclarian  {"config": {...}}
#     422 {"code":"VAL-002","field_errors":[
#            {"field":"scopes","message_key":"integrations.field.unknown"},
#            {"field":"client_id","message_key":"integrations.field.unknown"}]}
#
# — whatever the clerk had actually changed, for ever, with no screen able to
# clear it.
#
# ⚠ **THE ASYMMETRY IS THE WHOLE ASSERTION, WHICH IS WHY IT IS ONE CASE AND NOT
# TWO.** A name already AT REST is our own rot and is pruned; a name a CALLER
# sends is still refused. A test that only proved the first half would pass
# just as well over a `update_connection` that had stopped validating at all.
@pytest.mark.django_db
def test_def_int_5582_a_retired_field_at_rest_does_not_freeze_the_connection(brazos, dana, smtp_adapter):
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    row = models.IntegrationConnection.objects.get(provider_key="email_smtp")
    # What a retired manifest field leaves behind. `email_smtp` declares no
    # `scopes`, exactly as the five ERP manifests no longer do.
    row.config = {**dict(row.config or {}), "scopes": "payments"}
    row.save(update_fields=["config"])

    ok = patch_connection(brazos, dana, "email_smtp", {"config": {"port": "2525"}})
    assert ok.status_code == 200, ok.data
    row.refresh_from_db()
    assert row.config["port"] == "2525"
    # Pruned rather than carried, so the next PATCH is not refused either.
    assert "scopes" not in row.config

    # …and the guard that matters is untouched: a name the CALLER sends is
    # still refused by name, and a secret still cannot come this way.
    caller_sent = patch_connection(brazos, dana, "email_smtp", {"config": {"colour": "teal"}})
    assert caller_sent.status_code == 422
    assert caller_sent.data["field_errors"][0]["field"] == "colour"
    secret = patch_connection(brazos, dana, "email_smtp", {"config": {"password": "x"}})
    assert secret.status_code == 422
