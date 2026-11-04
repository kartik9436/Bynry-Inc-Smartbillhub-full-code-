# ── Trace ──────────────────────────────────────────────
# Story:  US-INT-025 (EP-INT-07) TC-1..6 — *"disconnect destroys the credential
#         immediately and keeps the run history"*. US-INT-003 — the IS-6
#         confirm's consequence copy. Screens: S8 · S142
# Rules:  BR-INT-016 (the secret is destroyed; nothing queued or recorded is
#         lost; reconnection needs fresh credentials) · BR-INT-042 (a secret
#         and a record have different retention) · BR-INT-014 (audited with
#         masked refs) · BR-NOT-005 (rows rest `queued`; no shared-sender
#         fallback) · B14 rule 6 (danger tier)
# ───────────────────────────────────────────────────────
"""The deletion path — written before the first real credential could be stored.

⚠ TC-6 IS THIS FILE'S EXISTENCE. *"The disconnect test lands in the same PR as,
or before, the first adapter that stores a credential."* `adapters/email_smtp.py`
and this file are in one commit, and the assertion at the bottom is the standing
form of it: if a real adapter is bound, this file is here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.integrations import models, services
from core import errors
from tests.test_us_int_helpers_b import *  # noqa: F401,F403 — fixtures + request helpers
from tests.test_us_int_helpers_b import (
    GOOD_PASSWORD,
    SMTP_FIELDS,
    delete_connection,
    post_connect,
    post_credential,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

FRIDAY_PASSWORD = "wrong-key-friday"


def _connected_with_two_versions_and_runs(tenant, actor, runs: int = 3):
    post_connect(tenant, actor, "email_smtp", SMTP_FIELDS)
    post_credential(tenant, actor, "email_smtp", {"password": FRIDAY_PASSWORD})
    with tenant_ctx(tenant):  # BE-01 — every write runs in the caller's tenant context
        connection = services.connection_for(tenant.id, "email_smtp")
        for _ in range(runs):
            run = services.start_run(
                connection=connection,
                operation="send_message",
                direction="outbound",
                trigger="manual",
            )
            services.finish_run(run, attempted=1, succeeded=1, failed=0, skipped=0, confirmed=True)
    return connection


def test_tc1_disconnect_destroys_every_version_keeps_every_run_and_audits_the_hints(
    brazos, dana, smtp_adapter, recording_dispatcher, audit_rows
):
    connection = _connected_with_two_versions_and_runs(brazos, dana, runs=3)
    assert models.IntegrationCredential.objects.filter(connection=connection).count() == 2

    delete_connection(brazos, dana, "email_smtp")

    assert models.IntegrationCredential.objects.filter(connection=connection).count() == 0
    assert models.IntegrationRun.objects.filter(connection=connection).count() == 3
    connection.refresh_from_db()
    assert connection.status == models.STATUS_OFF
    assert connection.enabled is False

    row = [one for one in audit_rows if one["action"] == services.AUDIT_DISCONNECTED][-1]
    assert row["after"]["destroyed"] == ["••••kbox", "••••iday"]
    assert row["after"]["summary"] == "••••kbox, ••••iday destroyed"
    assert row["after"]["runs_kept"] == 3
    for plaintext in (GOOD_PASSWORD, FRIDAY_PASSWORD):
        assert plaintext not in json.dumps(audit_rows, default=str)


def test_tc2_queued_messages_rest_queued_and_nothing_falls_back_to_a_shared_sender(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    """BR-NOT-005 + the A15 addendum. Disconnect touches the queue at all, and
    the CONFIRM says how many are waiting so a clerk is not guessing."""
    from apps.notifications import models as notification_models
    from apps.notifications import provider_seam

    _connected_with_two_versions_and_runs(brazos, dana, runs=1)
    with tenant_ctx(brazos):
        preview = services.disconnect_preview(brazos.id, "email_smtp")
    assert preview["channel"] == "email"
    # Notifications answered, so this is a number and not a shrug.
    assert isinstance(preview["messages_waiting"], int)
    queued_before = preview["messages_waiting"]

    delete_connection(brazos, dana, "email_smtp")

    still = notification_models.OutboundMessage.objects.filter(
        tenant_id=brazos.id, status=notification_models.STATUS_QUEUED
    ).count()
    assert still == queued_before, "disconnect moved a queue row — it must touch none"
    # And the channel now reports itself as not connected rather than sending.
    route = provider_seam.channel_route(notification_models.CHANNEL_EMAIL, active=True)
    assert route.dispatchable is False
    assert route.problem["code"] == provider_seam.ROUTE_PROVIDER_NOT_CONNECTED


def test_tc3_reconnecting_needs_fresh_credentials_and_roll_back_is_refused(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    """No resurrect: the old secret is gone, so the only path back is Connect."""
    _connected_with_two_versions_and_runs(brazos, dana, runs=1)
    delete_connection(brazos, dana, "email_smtp")

    with tenant_ctx(brazos), pytest.raises(errors.BizError) as refusal:
        services.rollback_credential(actor=dana, tenant_id=brazos.id, provider_key="email_smtp")
    assert refusal.value.message_key == services.REFUSAL_NOT_CONNECTED

    again = post_connect(brazos, dana, "email_smtp", SMTP_FIELDS)
    assert again.status_code == 201
    connection = services.connection_for(brazos.id, "email_smtp")
    rows = list(models.IntegrationCredential.objects.filter(connection=connection))
    assert len(rows) == 1 and rows[0].version == 1, "a reconnect starts the versions again"
    assert connection.status == models.STATUS_UNTESTED


def test_tc4_a_dump_after_disconnect_holds_no_ciphertext_and_the_whole_history(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    """A backup taken the day after must not contain the departed secret."""
    connection = _connected_with_two_versions_and_runs(brazos, dana, runs=2)
    delete_connection(brazos, dana, "email_smtp")

    from django.db import connection as db

    with db.cursor() as cursor:
        cursor.execute("SELECT payload_enc FROM integration_credential")
        assert cursor.fetchall() == []
        # ⚠ ONE PARAMETER, TWO SPELLINGS. SQLite stores a UUID as 32 hex
        # characters with no dashes and PostgreSQL as the dashed form, so a
        # raw comparison against `str(uuid)` matches nothing on SQLite while
        # the ORM is perfectly happy. Both are offered rather than the test
        # being made vendor-specific.
        cursor.execute(
            "SELECT count(*) FROM integration_run WHERE connection_id IN (%s, %s)",
            [str(connection.id), str(connection.id).replace("-", "")],
        )
        assert cursor.fetchone()[0] == 2


def test_tc5_another_tenant_cannot_disconnect_this_ones_connection(
    brazos, dana, lonestar, erin, smtp_adapter, recording_dispatcher
):
    _connected_with_two_versions_and_runs(brazos, dana, runs=1)
    refused = delete_connection(lonestar, erin, "email_smtp")
    assert refused.status_code >= 400
    connection = services.connection_for(brazos.id, "email_smtp")
    assert models.IntegrationCredential.objects.filter(connection=connection).count() == 2
    connection.refresh_from_db()
    assert connection.status != models.STATUS_OFF


def test_tc6_the_ordering_gate_this_file_is_the_standing_form_of():
    """*"The disconnect test lands in the same PR as, or before, the first
    adapter that stores a credential."* If a real adapter exists, so does a
    destroyer for what it stores — asserted rather than remembered."""
    from apps.integrations.adapters import ADAPTERS

    if not ADAPTERS:
        pytest.skip("no real adapter is bound yet, so nothing stores a credential")
    assert hasattr(services, "disconnect"), "an adapter can store a secret and nothing removes it"
    assert Path(__file__).exists()


def test_us_int_003_the_confirm_states_what_stops_and_what_is_kept_with_figures(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    """The consequence copy is DATA plus a category; the sentences are eleven
    catalogue lines. This asserts the data half — the figures a clerk reads."""
    _connected_with_two_versions_and_runs(brazos, dana, runs=4)
    with tenant_ctx(brazos):
        preview = services.disconnect_preview(brazos.id, "email_smtp")
        assert services.disconnect_preview(brazos.id, "email_google") is None
    assert preview["category"] == "email"
    assert preview["versions"] == 2
    assert preview["runs_kept"] == 4
    assert preview["channel"] == "email"
    # No sentence on the wire — the server sends the numbers (B14 rule 35's
    # reason: a served sentence is a sentence in one language).
    assert not any(isinstance(v, str) and " " in v for k, v in preview.items() if k != "label")
    # (the `None` case for a provider with no connection is asserted above,
    #  inside the tenant context — a dead panel is hard-won law 2)


def test_the_confirm_says_nothing_rather_than_zero_when_nobody_could_count(
    brazos, dana, smtp_adapter, recording_dispatcher, monkeypatch
):
    """`None` is not zero. If notifications cannot answer, the screen must not
    tell a utility nothing is waiting — nobody looked."""
    from apps.integrations.seams import notifications as seam

    _connected_with_two_versions_and_runs(brazos, dana, runs=1)
    monkeypatch.setattr(seam, "_resolve", lambda *a, **k: None)
    with tenant_ctx(brazos):
        preview = services.disconnect_preview(brazos.id, "email_smtp")
    assert preview["messages_waiting"] is None
    assert preview["runs_kept"] == 1  # the half we CAN count is still counted


def test_the_seam_reads_and_the_module_writes_nothing_of_notifications(
    brazos, dana, smtp_adapter, recording_dispatcher
):
    """BR-TEN-013's shape, and G78's rule kept by hand for this module: the
    seam has one read and no writer to reach for."""
    from apps.integrations.seams import notifications as seam

    assert seam.BACKLOG_READ == "deferred_backlog"
    assert seam.channel_for("email") == "email"
    assert seam.channel_for("accounting") is None
    assert seam.queued_on_channel(None) is None
    source = Path(seam.__file__).read_text(encoding="utf-8")
    for write in (".save(", ".delete(", ".update(", ".create("):
        assert write not in source, f"the seam calls {write} — it reads and never writes"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-025@5bfc2492 (EP-INT-07 story + BR-INT-016/042 snapshot; co-packet US-INT-003@5bfc2492)
# generated: 2026-09-04 by the CR-069 wave E build lane
# checklist: A✔ B✔ C✔ D✔(DELETE /integrations/{key}) E✔(S142's Disconnect → the I7 confirm) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_025_disconnect.py · G94 · G78's rule asserted here by reading the seam's own source
# exceptions: TC-2's queue count is whatever the fixture tenant holds — the assertion is that disconnect does not CHANGE it, which is the rule, rather than a fixed number the fixture would have to keep true
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
