# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-NOT-10534 (mail server typed in two places) · DEF-NOT-10533
#           (the Channel status card's false "Nothing is sent" sentence)
# Ruling:   PO 2026-10-22 — *"We have to move everything in connector not any
#           other place"* and *"A. Each channel tells the clerk the truth about
#           itself, in one short line."* (decision log 2026-10-22, three
#           entries, and the lane SETTINGS-MOVE judgments entry)
# Rules:    BR-NOT-023 · BR-INT-005 · CLAUDE.md hard rules 1 and 7 · law 14
# ───────────────────────────────────────────────────────
"""Mail server in Connectors only, proved at its four edges.

1. **The read.** `sender_config.sender_route()` follows a change made on
   Connectors, and reads no `notification_settings` column.
2. **The guard.** The email adapter and `sender_config` name no retired column
   outside the list that retires them.
3. **The refusal.** The settings API refuses a mail-server field BY NAME and
   writes nothing.
4. **The move.** `integrations/0016` copies a value only the old form held; a
   value the connector already has wins; a re-run changes nothing; audited.

Plus the channel line (DEF-NOT-10533): email reads *"Sending through Custom
SMTP (<host>)"* from the live connector.

The migration cases are also run on PostgreSQL (law 14 — the per-tenant
SAVEPOINT and the `set_config` tenant scoping only exist there).
"""

from __future__ import annotations

import importlib
import pathlib
import re

import pytest
from django.apps import apps as django_apps

from apps.audit import models as audit_models
from apps.integrations import models as integration_models
from apps.notifications import models as notification_models
from apps.notifications import sender_config
from apps.notifications import settings_api as api
from tests.test_us_int_helpers_b import *  # noqa: F401,F403 — smtp_adapter
from tests.test_us_int_helpers_b import (
    GOOD_PASSWORD,
    patch_connection,
    post_connect,
    post_credential,
    smtp_adapter,  # noqa: F401 — a FIXTURE
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

BACKEND = pathlib.Path(__file__).resolve().parents[1]
MIGRATION = importlib.import_module(
    "apps.integrations.migrations.0016_def_not_10534_smtp_settings_to_connector"
)

#: What the connector holds (Connectors → Custom SMTP), password included so
#: the connection can actually send.
CONNECTOR_FIELDS = {
    "host": "smtp.office365.com",
    "port": "587",
    "username": "billing@springfieldwater.example",
    "password": GOOD_PASSWORD,
    "send_from": "billing@springfieldwater.example",
}


def _connect(tenant, actor):
    assert post_connect(tenant, actor, "email_smtp", CONNECTOR_FIELDS).status_code == 201
    post_credential(tenant, actor, "email_smtp", {"password": GOOD_PASSWORD})


def _settings_row(tenant) -> notification_models.NotificationSettings:
    row, _ = notification_models.NotificationSettings.objects.get_or_create(tenant_id=tenant.pk)
    return row


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE READ FOLLOWS CONNECTORS
# ══════════════════════════════════════════════════════════════════════════
def test_the_route_reads_the_connector_and_follows_a_change_made_there(brazos, dana, smtp_adapter):
    with tenant_ctx(brazos):
        # A value typed on the OLD form is not a mail server any more.
        row = _settings_row(brazos)
        row.smtp_host = "mail.old-form.example"
        row.sender_from_address = "old@old-form.example"
        row.save()
        before = sender_config.sender_route()
    assert before["mode"] == sender_config.MODE_NOT_CONNECTED
    assert before["configured"] is False
    assert "old-form" not in str(before)

    _connect(brazos, dana)
    with tenant_ctx(brazos):
        connected = sender_config.sender_route()
    assert connected["mode"] == sender_config.MODE_TENANT_SMTP
    assert connected["active"] is True
    assert connected["provider_name"] == "Custom SMTP"
    assert connected["host"] == "smtp.office365.com"
    assert connected["send_from"] == "billing@springfieldwater.example"

    # Change the mail server ON CONNECTORS — the read follows.
    moved = patch_connection(brazos, dana, "email_smtp", {"config": {"host": "smtp.gmail.com"}})
    assert moved.status_code == 200, moved.data
    with tenant_ctx(brazos):
        after = sender_config.sender_route()
    assert after["host"] == "smtp.gmail.com"


def test_def_2472__the_route_sentence_names_no_id_and_no_page(brazos, dana, smtp_adapter):
    with tenant_ctx(brazos):
        unconfigured = sender_config.sender_route()
    _connect(brazos, dana)
    with tenant_ctx(brazos):
        configured = sender_config.sender_route()
    for route in (unconfigured, configured):
        detail = route["detail"]
        for token in ("C-12", "BR-", "OQ-", "CR-", "DEF-", "smtp_", "Settings"):
            assert token not in detail, detail


def test_the_sender_endpoint_serves_the_connector(brazos, dana, smtp_adapter):
    _connect(brazos, dana)
    read = api_call(
        api.notification_sender, "get", user=dana.user, role="system_admin", tenant=brazos
    )
    assert read.status_code == 200
    assert read.data["connection"]["host"] == "smtp.office365.com"
    assert read.data["connection"]["active"] is True
    assert read.data["sender_route"]["send_from"] == "billing@springfieldwater.example"
    assert read.data["editable_fields"] == []
    for retired in sender_config.RETIRED_FIELDS:
        assert retired not in read.data, retired


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE GUARD — the adapter and the route read only the connector
# ══════════════════════════════════════════════════════════════════════════
#: A retired column named as an identifier or a field name — NOT inside a
#: dotted catalogue key such as `integrations.field.smtp_port`, which is the
#: connector's own label for its own port field.
RETIRED = re.compile(
    r"(?<![.\w])(smtp_host|smtp_port|smtp_username|smtp_secret_ref|sender_from_address)\b"
)


def _code_lines(path: pathlib.Path) -> list[str]:
    """Source lines that are CODE — comments and docstrings are prose about
    the retirement and may name the columns."""
    import ast
    import io
    import tokenize

    source = path.read_text(encoding="utf-8")
    docstrings: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr):
            value = body[0].value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                docstrings.update(range(value.lineno, value.end_lineno + 1))
    kept = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type in (tokenize.COMMENT,) or token.start[0] in docstrings:
            continue
        kept.append((token.start[0], token.string))
    return [text for _, text in kept]


def test_the_email_adapter_reads_only_the_connector():
    adapter = BACKEND / "apps" / "integrations" / "adapters" / "email_smtp.py"
    code = " ".join(_code_lines(adapter))
    assert not RETIRED.search(code), "the email adapter reads a retired Notifications column"
    assert "NotificationSettings" not in code
    assert "apps.notifications" not in code and "notifications" not in code.split()


def test_sender_config_names_no_retired_column_outside_its_retirement_list():
    path = BACKEND / "apps" / "notifications" / "sender_config.py"
    source = path.read_text(encoding="utf-8")
    listed = source.index("RETIRED_FIELDS: tuple[str, ...] = (")
    closing = source.index(")", listed + len("RETIRED_FIELDS: tuple[str, ...] = ("))
    outside = source[:listed] + source[closing:]
    stripped = " ".join(
        text
        for text in _code_lines_from_source(outside)
    )
    assert not RETIRED.search(stripped), "sender_config reads a retired column"
    assert "NotificationSettings" not in stripped
    assert "notification_settings" not in stripped


def _code_lines_from_source(source: str) -> list[str]:
    import io
    import tokenize

    out = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError):  # pragma: no cover
        return [source]
    for token in tokens:
        if token.type == tokenize.COMMENT:
            continue
        if token.type == tokenize.STRING and token.string.startswith(('"""', "'''", 'r"""')):
            continue
        out.append(token.string)
    return out


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE REFUSAL — by name, and nothing written
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("field", list(sender_config.RETIRED_FIELDS))
def test_the_sender_api_refuses_a_mail_server_field_by_name(brazos, dana, field):
    value = 587 if field == "smtp_port" else "smtp.evil.example"
    with tenant_ctx(brazos):
        before = _settings_row(brazos)
        snapshot = getattr(before, field)
    response = api_call(
        api.notification_sender,
        "patch",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={field: value},
    )
    assert response.status_code == 422, response.data
    body = response.data["error"] if "error" in response.data else response.data
    assert body["message_key"] == "notifications.sender.movedToConnectors"
    assert [one["field"] for one in body["field_errors"]] == [field]
    with tenant_ctx(brazos):
        assert getattr(_settings_row(brazos), field) == snapshot


def test_the_settings_api_refuses_them_by_name_too(brazos, dana):
    response = api_call(
        api.notification_settings,
        "patch",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={"sender_from_address": "billing@x.example", "dispatch_batch_size": 250},
    )
    assert response.status_code == 422, response.data
    body = response.data["error"] if "error" in response.data else response.data
    assert body["message_key"] == "notifications.sender.movedToConnectors"
    with tenant_ctx(brazos):
        # The whole write is refused — the batch size did not move either.
        assert _settings_row(brazos).dispatch_batch_size != 250


# ══════════════════════════════════════════════════════════════════════════
# 4 · ONE TRUE LINE PER CHANNEL (DEF-NOT-10533)
# ══════════════════════════════════════════════════════════════════════════
def test_email_reads_sending_through_the_connector_with_its_host(brazos, dana, smtp_adapter):
    _connect(brazos, dana)
    with tenant_ctx(brazos):
        row = _settings_row(brazos)
        row.email_dispatch_active = True
        row.save()
    response = api_call(
        api.notification_settings, "get", user=dana.user, role="system_admin", tenant=brazos
    )
    lines = {line["channel"]: line for line in response.data["channel_lines"]}
    assert lines["email"] == {
        "channel": "email",
        "state": "sending",
        "provider": "Custom SMTP",
        "host": "smtp.office365.com",
    }
    assert lines["sms"]["state"] == "off"
    assert lines["pdf_print"]["state"] == "waitingPrintVendor"


def test_email_switched_on_with_no_mail_server_says_so(brazos, dana):
    with tenant_ctx(brazos):
        row = _settings_row(brazos)
        row.email_dispatch_active = True
        row.save()
    response = api_call(
        api.notification_settings, "get", user=dana.user, role="system_admin", tenant=brazos
    )
    lines = {line["channel"]: line for line in response.data["channel_lines"]}
    assert lines["email"]["state"] == "noMailServer"


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE MOVE — integrations/0016
# ══════════════════════════════════════════════════════════════════════════
def _smtp_rows(tenant):
    return list(
        integration_models.IntegrationConnection.objects.filter(
            tenant_id=tenant.pk, provider_key="email_smtp"
        )
    )


def _moved_audits(tenant):
    return audit_models.AuditLog.objects.filter(
        tenant_id=tenant.pk, action=MIGRATION.AUDIT_ACTION
    )


def test_move__a_value_only_the_form_held_creates_a_not_set_up_connector(brazos):
    with tenant_ctx(brazos):
        row = _settings_row(brazos)
        row.smtp_host = "mail.springfield.example"
        row.smtp_port = 465
        row.sender_from_address = "billing@springfieldwater.example"
        row.save()
        assert MIGRATION.move_tenant(django_apps, brazos.pk) == "created"
        rows = _smtp_rows(brazos)
        assert len(rows) == 1
        made = rows[0]
        assert made.status == "not_set_up" and made.enabled is False
        assert made.config["host"] == "mail.springfield.example"
        assert made.config["port"] == "465"
        assert made.config["send_from"] == "billing@springfieldwater.example"
        assert not integration_models.IntegrationCredential.objects.filter(connection=made).exists()
        audit = _moved_audits(brazos).get()
        assert audit.after["outcome"] == "created"
        # The old columns are left as they were — read by nothing, not cleared.
        assert _settings_row(brazos).smtp_host == "mail.springfield.example"


def test_move__the_connectors_own_value_wins_and_a_missing_one_is_filled(brazos):
    """The decision log's worked figure: the connector keeps
    `smtp.office365.com` and gains the sender."""
    with tenant_ctx(brazos):
        integration_models.IntegrationConnection.objects.create(
            tenant_id=brazos.pk,
            provider_key="email_smtp",
            environment="production",
            status="untested",
            enabled=True,
            config={"host": "smtp.office365.com", "port": "587"},
        )
        row = _settings_row(brazos)
        row.smtp_host = "mail.springfield.example"
        row.sender_from_address = "billing@springfieldwater.example"
        row.save()
        assert MIGRATION.move_tenant(django_apps, brazos.pk) == "filled"
        made = _smtp_rows(brazos)[0]
        assert made.config["host"] == "smtp.office365.com"
        assert made.config["send_from"] == "billing@springfieldwater.example"
        audit = _moved_audits(brazos).get()
        assert audit.after["send_from"] == "billing@springfieldwater.example"
        assert "host" not in audit.after
        # Re-running changes nothing and writes no second audit row.
        assert MIGRATION.move_tenant(django_apps, brazos.pk) == "unchanged"
        assert _moved_audits(brazos).count() == 1


def test_move__a_tenant_with_nothing_typed_is_left_alone(brazos):
    with tenant_ctx(brazos):
        _settings_row(brazos)
        assert MIGRATION.move_tenant(django_apps, brazos.pk) == "unchanged"
        assert _smtp_rows(brazos) == []
        assert not _moved_audits(brazos).exists()


def test_move__the_whole_migration_runs_per_tenant(brazos, lonestar):
    """`move()` walks every tenant inside its own savepoint and leaves a
    tenant with nothing typed exactly alone."""
    from django.db import connection

    with tenant_ctx(brazos):
        row = _settings_row(brazos)
        row.sender_from_address = "billing@brazos.example"
        row.save()

    class _Editor:
        pass

    editor = _Editor()
    editor.connection = connection
    MIGRATION.move(django_apps, editor)
    with tenant_ctx(brazos):
        assert _smtp_rows(brazos)[0].config["send_from"] == "billing@brazos.example"
    with tenant_ctx(lonestar):
        assert _smtp_rows(lonestar) == []
