# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-015 (EP-INT-05) — the adapter protocol and its conformance
#           kit. Screens: S141 · S142
# Rules:    BR-INT-038 · BR-INT-019 · BR-INT-003 · BR-INT-004 · BR-INT-018
#           (an adapter that answers a boolean is `unconfirmed`)
# Tests:    this file — TC-1 (one real message) · TC-2 (`hunter2 `) · TC-3
#           (returns-True refused by the kit AND the runtime) · TC-4
#           (describe, three exits) · TC-5 (no safe instance → refused) ·
#           TC-6 (the 37-case kit, unchanged per adapter) · TC-7 (the grep)
# Impacts:  apps/integrations/adapters/base.py · conformance.py · jobs.py ·
#           runners/deliver.py
# ───────────────────────────────────────────────────────
"""US-INT-015 — four methods, and the kit that decides whether a class is an adapter."""

from __future__ import annotations

import logging
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from apps.integrations import conformance, models, services
from apps.integrations.adapters.base import ConnectionView, RunResult, TestResult
from apps.integrations.registry import REGISTRY, Registry
from apps.integrations.registry import Manifest, Operation, Auth, Field, Idempotency  # noqa: I001
from tests.test_us_int_helpers_b import *  # noqa: F401,F403
from tests.test_us_int_helpers_b import RECIPIENT, SMTP_FIELDS, post_connect, post_run, post_test, run_job
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · audit_rows

REPO = Path(__file__).resolve().parents[2]
VIEW = ConnectionView(provider_key="email_smtp", environment="production", config=conformance.RECORDED_SMTP_FIXTURE.config, label="Billing mailbox")


def test_us_int_015_tc1_a_correct_password_sends_one_real_message_to_the_typed_address():
    result = conformance.RecordedSmtpAdapter().test(VIEW, {"password": conformance._SMTP_GOOD}, recipient=RECIPIENT)
    assert result == TestResult(ok=True, sentence=f"Sent one test message to {RECIPIENT}.")


def test_us_int_015_tc2_the_trailing_space_password_is_the_mail_servers_own_verdict_in_a_sentence():
    result = conformance.RecordedSmtpAdapter().test(VIEW, {"password": conformance._SMTP_BAD}, recipient=RECIPIENT)
    assert result.ok is False
    assert result.sentence == "The mail server rejected the password."
    assert result.provider_text == "535 5.7.8 AUTHENTICATION FAILED"


@pytest.mark.django_db
def test_us_int_015_tc3_an_execute_that_returns_true_is_unconfirmed_and_fails_the_kit(
    brazos, dana, bind_adapter, recording_dispatcher
):
    findings = conformance.run_kit(conformance.ReturnsTrueAdapter, REGISTRY.require("email_smtp"), conformance.RECORDED_SMTP_FIXTURE)
    assert not conformance.passed(findings)
    assert any("RunResult, never a boolean" in one for one in conformance.failures(findings))
    bind_adapter("email_smtp", conformance.ReturnsTrueAdapter)
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    run_job(post_run(brazos, dana, "email_smtp", "send_message", work=[{"ref": "A-1"}]).data)
    run = models.IntegrationRun.objects.get(operation="send_message")
    assert run.outcome == "unconfirmed"
    assert run.summary == "The provider did not say how many it accepted."


def test_us_int_015_tc4_describe_is_the_masked_line_and_the_password_reaches_no_exit(caplog):
    caplog.set_level(logging.DEBUG)
    line = conformance.RecordedSmtpAdapter().describe(VIEW)
    assert line == "billing@brazosbend.example · Custom SMTP"
    assert conformance._SMTP_GOOD not in line
    assert conformance._SMTP_GOOD not in caplog.text


@pytest.mark.django_db
def test_us_int_015_tc5_a_manifest_with_no_safe_instance_refuses_the_test_by_sentence(
    brazos, dana, bind_adapter, recording_dispatcher
):
    """`map_tiles_public` declares a test action; a manifest without one is
    built here on a fresh registry and mounted through the service seam."""
    fresh = Registry()
    fresh.register(
        Manifest(
            key="email_smtp",
            category="email",
            display_name="Custom SMTP",
            summary="Any mail server.",
            auth=Auth(mode="we_hold_theirs", placement="native"),
            fields=(Field(name="host", label="Mail server", kind="host"), Field(name="password", label="Password", kind="secret")),
            operations=(
                Operation(
                    name="send_message", label="Send messages", direction="out", initiative="us",
                    transport="smtp", trigger="dispatcher", idempotency=Idempotency(mode="refuse", source="queue_row_id"),
                    # CR-110-BRC04 — every operation names its ceiling, and
                    # DEF-INT-5488 — it names the host field the form collects.
                    completion="immediate", test_action=None, rate_limit_per_minute=120,
                    host_field="host",
                ),
            ),
        )
    )
    fresh.register_adapter("email_smtp", conformance.RecordedSmtpAdapter)
    from core import tenancy as core_tenancy

    with core_tenancy.tenant_context(brazos.id):
        row = services.connect_with_fields(
            actor=dana, tenant_id=brazos.id, provider_key="email_smtp", environment="production",
            cadence="manual", label=None, fields={"host": "smtp.brazosbend.example", "password": "x"}, registry=fresh,
        )
        with pytest.raises(Exception) as refused:
            services.request_test(actor=dana, tenant_id=brazos.id, provider_key="email_smtp", registry=fresh)
    assert getattr(refused.value, "message_key", None) == services.REFUSAL_NO_TEST_ACTION
    assert getattr(refused.value, "br_ref", None) == "BR-INT-019"
    assert row.status == "untested"


def test_us_int_015_tc6_the_kit_is_thirty_seven_cases_and_the_recorded_adapter_passes_them_all():
    manifest = REGISTRY.require("email_smtp")
    findings = conformance.run_kit(conformance.RecordedSmtpAdapter, manifest, conformance.RECORDED_SMTP_FIXTURE)
    assert len(findings) == conformance.CASE_COUNT == 37
    assert conformance.passed(findings), conformance.failures(findings)


def test_us_int_015_tc6b_the_kit_runs_unchanged_over_a_second_adapter_and_names_what_it_refuses():
    """Adding an adapter edits the kit nowhere: the same call, a different class."""
    manifest = REGISTRY.require("email_smtp")
    no_count = conformance.run_kit(conformance.NoCountAdapter, manifest, conformance.RECORDED_SMTP_FIXTURE)
    assert conformance.passed(no_count)  # an honest `confirmed=False` is conformant

    class FifthMethod(conformance.RecordedSmtpAdapter):
        def retry(self) -> None:  # retry is the framework's, never the adapter's
            return None

    five = conformance.run_kit(FifthMethod, manifest, conformance.RECORDED_SMTP_FIXTURE)
    assert not conformance.passed(five)
    assert conformance.failures(five)[0].startswith("01 four public methods and only four")

    class Leaky(conformance.RecordedSmtpAdapter):
        def describe(self, conn: ConnectionView) -> str:
            return f"{conn.config.get('username')} · {conformance._SMTP_GOOD}"

    leaky = conformance.run_kit(Leaky, manifest, conformance.RECORDED_SMTP_FIXTURE)
    assert any("describe() carries no secret" in one for one in conformance.failures(leaky))

    class Logs(conformance.RecordedSmtpAdapter):
        def test(self, conn: ConnectionView, secrets: Mapping[str, str], *, recipient: str | None = None) -> TestResult:
            logging.getLogger("smartbillhub.integrations").info("dialling with %s", secrets.get("password"))
            return super().test(conn, secrets, recipient=recipient)

    logs = conformance.run_kit(Logs, manifest, conformance.RECORDED_SMTP_FIXTURE)
    assert any("no log line during test() carries the credential" in one for one in conformance.failures(logs))


def test_us_int_015_tc7_no_protocol_library_is_imported_outside_adapters_and_core():
    hits = subprocess.run(
        ["grep", "-rln", r"^import smtplib\|^import requests\|^from requests\|^import paramiko\|^from paramiko", str(REPO / "06-backend" / "apps"), "--include=*.py"],
        capture_output=True, text=True, check=False,
    ).stdout.split()
    outside = [
        one for one in hits
        if "/apps/integrations/adapters/" not in one and "/tests/" not in one
    ]
    assert outside == [], outside


@pytest.mark.django_db
def test_us_int_015_the_no_count_fixture_is_unconfirmed_through_the_runtime(brazos, dana, bind_adapter, recording_dispatcher):
    bind_adapter("email_smtp", conformance.NoCountAdapter)
    post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    run_job(post_run(brazos, dana, "email_smtp", "send_message", work=[{"ref": "A-1"}]).data)
    run = models.IntegrationRun.objects.get(operation="send_message")
    assert run.outcome == "unconfirmed" and run.attempted == 1 and run.succeeded == 1


def test_us_int_015_the_slow_fixture_sleeps_and_never_raises():
    class Quick(conformance.SlowAdapter):
        SLOW_SECONDS = 0.01

    result = Quick().test(VIEW, {"password": conformance._SMTP_GOOD}, recipient=RECIPIENT)
    assert result.ok


def test_us_int_015_the_registry_refuses_binding_an_adapter_to_a_coming_soon_provider():
    fresh = Registry()
    from apps.integrations import manifests

    manifests.register_all(fresh)
    with pytest.raises(Exception, match="coming-soon provider registers no adapter"):
        # `payments_card` until `CR-110-BRC04`; the five named processors it
        # became each carry the same W7 hold.
        fresh.register_adapter("pay_invoicecloud", conformance.RecordedSmtpAdapter)
    assert fresh.adapter_for("pay_invoicecloud") is None
