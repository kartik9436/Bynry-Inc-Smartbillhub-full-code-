# ── Trace ──────────────────────────────────────────────
# Story:  US-INT-026 (EP-INT-07) TC-1..6 — the `C35` fold: a mail password
#         typed into the product, not the name of an environment variable.
#         Screens: S8 Notifications (the card that becomes a read) · S141
# Rules:  BR-INT-042 · BR-INT-005 · BR-INT-007 (connection from day one;
#         SENDING activates W6) · BR-INT-008 (the dispatcher is the only
#         sender) · hard-won law 3 (an absent secret is a stated state)
# ───────────────────────────────────────────────────────
"""The fold, run as the migration runs it, and the retirement it makes true."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from apps.integrations import models as integration_models
from apps.notifications import models as notification_models
from apps.notifications import sender_config
from core import crypto
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: A migration module's name starts with a digit, so it cannot be imported by
#: `from … import`. It is imported by name here rather than copied, because a
#: test that re-implements the migration proves the copy and not the migration.
_0004_fold_helper = importlib.import_module(
    "apps.integrations.migrations.0004_c35_fold_sender_secret_ref"
)

BRAZOS_SECRET = "Ew3!kQ9-lockbox"


def _settings_row(tenant, ref: str):
    row, _ = notification_models.NotificationSettings.objects.get_or_create(tenant_id=tenant.pk)
    row.smtp_host = "smtp.brazosbend.example"
    row.smtp_port = 587
    row.smtp_username = "billing@brazosbend.example"
    row.sender_from_address = "billing@brazosbend.example"
    row.smtp_secret_ref = ref
    row.save()
    return row


def test_tc1_a_present_secret_becomes_an_encrypted_credential_and_the_column_is_emptied(
    brazos, monkeypatch
):
    monkeypatch.setenv("SMTP_PASSWORD_BRAZOS", BRAZOS_SECRET)
    _settings_row(brazos, "SMTP_PASSWORD_BRAZOS")

    _0004_fold_helper.fold(_apps(), None)

    connection = integration_models.IntegrationConnection.objects.get(
        tenant_id=brazos.pk, provider_key="email_smtp"
    )
    assert connection.status == "untested"
    assert connection.enabled is True
    assert connection.config["host"] == "smtp.brazosbend.example"
    assert connection.config["port"] == "587"
    assert connection.config["send_from"] == "billing@brazosbend.example"

    credential = integration_models.IntegrationCredential.objects.get(connection=connection)
    assert credential.version == 1 and credential.is_active is True
    assert credential.masked_hint == "••••kbox"
    # Encrypted at rest, and the plaintext is nowhere in the row.
    from django.db import connection as db

    with db.cursor() as cursor:
        cursor.execute("SELECT payload_enc FROM integration_credential")
        stored = cursor.fetchone()[0]
    assert crypto.is_ciphertext(stored)
    assert BRAZOS_SECRET not in stored and "lockbox" not in stored
    assert json.loads(
        crypto.decrypt(stored, context="integration_credential.payload_enc")
    ) == {"password": BRAZOS_SECRET}

    row = notification_models.NotificationSettings.objects.get(tenant_id=brazos.pk)
    assert row.smtp_secret_ref is None


def test_tc2_an_absent_secret_makes_a_not_set_up_connection_and_no_empty_credential(
    brazos, monkeypatch
):
    """Hard-won law 3. No guessed value, no placeholder ciphertext, and a card
    that says what the utility has to do rather than looking ready."""
    monkeypatch.delenv("SMTP_PASSWORD_SILVER", raising=False)
    _settings_row(brazos, "SMTP_PASSWORD_SILVER")

    _0004_fold_helper.fold(_apps(), None)

    connection = integration_models.IntegrationConnection.objects.get(
        tenant_id=brazos.pk, provider_key="email_smtp"
    )
    assert connection.status == "not_set_up"
    assert connection.enabled is False
    assert integration_models.IntegrationCredential.objects.filter(connection=connection).count() == 0
    assert notification_models.NotificationSettings.objects.get(tenant_id=brazos.pk).smtp_secret_ref is None


def test_tc6_two_tenants_get_two_connections_each_under_its_own_tenant(
    brazos, lonestar, monkeypatch
):
    monkeypatch.setenv("SMTP_PASSWORD_BRAZOS", BRAZOS_SECRET)
    monkeypatch.setenv("SMTP_PASSWORD_LSR", "lone-star-secret")
    _settings_row(brazos, "SMTP_PASSWORD_BRAZOS")
    _settings_row(lonestar, "SMTP_PASSWORD_LSR")

    _0004_fold_helper.fold(_apps(), None)

    theirs = {
        str(one.tenant_id): one
        for one in integration_models.IntegrationConnection.objects.filter(provider_key="email_smtp")
    }
    assert set(theirs) == {str(brazos.pk), str(lonestar.pk)}
    for tenant_id, connection in theirs.items():
        credential = integration_models.IntegrationCredential.objects.get(connection=connection)
        assert str(credential.tenant_id) == tenant_id, "a credential is stamped with its own tenant"
    hints = sorted(
        one.masked_hint for one in integration_models.IntegrationCredential.objects.all()
    )
    assert hints == ["••••cret", "••••kbox"]


def test_the_fold_skips_a_tenant_that_has_already_connected_by_hand(brazos, monkeypatch):
    """A person's typing is the newer truth; a migration may not overwrite it."""
    monkeypatch.setenv("SMTP_PASSWORD_BRAZOS", BRAZOS_SECRET)
    _settings_row(brazos, "SMTP_PASSWORD_BRAZOS")
    integration_models.IntegrationConnection.objects.create(
        tenant_id=brazos.pk,
        provider_key="email_smtp",
        environment="production",
        status="working",
        cadence="manual",
        config={"host": "typed.by.hand.example", "port": "465"},
    )

    _0004_fold_helper.fold(_apps(), None)

    rows = list(integration_models.IntegrationConnection.objects.filter(provider_key="email_smtp"))
    assert len(rows) == 1
    assert rows[0].config["host"] == "typed.by.hand.example"
    assert integration_models.IntegrationCredential.objects.count() == 0
    # The column is still emptied — the fold's other half is unconditional.
    assert notification_models.NotificationSettings.objects.get(tenant_id=brazos.pk).smtp_secret_ref is None


def test_tc4_the_retired_field_has_no_reader_left_in_the_application(brazos):
    """*"Only the migration and a `# retired` comment remain."* Asserted by
    reading the module, because a grep in a docstring is not a reader."""
    assert "smtp_secret_ref" not in sender_config.EDITABLE_FIELDS
    # AMENDED 2026-10-22 (`DEF-NOT-10534`): `sender_config()` is gone — the
    # mail server is read from Connectors — so the read asserted is the route.
    with tenant_ctx(brazos):  # the read is tenant-scoped (hard rule 1)
        assert "smtp_secret_ref" not in str(sender_config.sender_route())

    apps_root = Path(sender_config.__file__).resolve().parents[1]
    offenders: list[str] = []
    for path in sorted(apps_root.rglob("*.py")):
        if "migrations" in path.parts or "__pycache__" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if "smtp_secret_ref" not in stripped:
                continue
            # A comment, a docstring line or a field DECLARATION is not a read.
            if stripped.startswith(("#", "*", "'", '"', "This section", "  *")):
                continue
            if stripped.startswith("smtp_secret_ref = models."):
                continue
            offenders.append(f"{path.relative_to(apps_root)}:{number} {stripped}")
    assert offenders == [], "something still reads the retired field: " + "; ".join(offenders)


def test_tc5_the_dispatcher_never_holds_the_plaintext_the_seam_resolves_it(
    brazos, monkeypatch
):
    """The credential is read INSIDE the seam, at use time, for the length of
    one adapter call — never handed to the dispatcher's own process."""
    from apps.integrations.seams import notifications as seam

    source = Path(seam.__file__).read_text(encoding="utf-8")
    assert "services.credential_secrets(connection)" in source
    assert "finally:\n        del secrets" in source
    # And the dispatcher's own module never names the reader.
    dispatcher = Path(sender_config.__file__).with_name("dispatcher.py")
    assert "credential_secrets" not in dispatcher.read_text(encoding="utf-8")


def test_br_int_007_wiring_the_adapter_did_not_switch_email_on(brazos):
    """*"The connection may be made from day one; SENDING activates W6."* A
    tenant with email switched OFF is still not dispatchable, adapter or no
    adapter — the flag is the flip, not the seam."""
    from apps.notifications import provider_seam

    route = provider_seam.channel_route(notification_models.CHANNEL_EMAIL, active=False)
    assert route.dispatchable is False
    assert route.problem["code"] == provider_seam.ROUTE_CHANNEL_DEFERRED
    assert route.problem["deferred_until"] == "W6"


def _apps():
    """The `apps` argument a `RunPython` gets — the live registry is close
    enough for a data migration that touches only concrete model classes."""

    class _Registry:
        @staticmethod
        def get_model(app_label: str, name: str):
            from django.apps import apps as django_apps

            return django_apps.get_model(app_label, name)

    return _Registry()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-026@5bfc2492 (EP-INT-07 story + BR-INT-042 snapshot)
# generated: 2026-09-04 by the CR-069 wave E build lane
# checklist: A✔ B✔ C✔ D=n/a(a migration has no route) E✔(the S8 card reads the connection) F✔ G✔ H=n/a(the 🔒 half is the migration, ledgered there)
# gates: pytest tests/test_us_int_026_fold.py · makemigrations --check
# exceptions: the fold is driven through `_0004_fold_helper.fold` with the LIVE model registry rather than through `migrate`, because the four cases need to set the environment per case; the migration itself calls the same function
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
