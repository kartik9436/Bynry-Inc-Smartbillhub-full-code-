# ── Trace ──────────────────────────────────────────────
# Change:   CR-173-BRC10 — the *Send to City folder* section of a connection:
#           save its settings, test that the folder can be WRITTEN to, resend
#           a day on purpose.
# Rules:    PO 2026-10-07 (*"this is okay"* over the six-item table: Server ·
#           Port · User name · Password — typed once, encrypted, shown only as
#           `••••` + last four, never logged and never returned — · Folder ·
#           *Test connection*, which *"signs in and proves the folder can be
#           WRITTEN to (not merely listed)"*) · PO 2026-10-07 (*"this is
#           tenant/utility data and should be handled from screen itself"*) ·
#           Q4 (a resend is a deliberate act) · BR-INT-003 · hard rule 7
# Tests:    06-backend/tests/test_cr173_newworld_sftp.py
# Impacts:  apps/integrations/file_drop_api.py (the four routes) ·
#           07-frontend/src/features/integrations/SendFilePanel.tsx
# ───────────────────────────────────────────────────────
"""A connection's named field GROUP — read, saved, tested, and (for New World) resent.

Written for the group, not for New World: a group is DATA on a manifest
(`registry.Field.group`), and nothing below names a provider (`BR-INT-037`,
`G77`). New World's *Send to City folder* (`send_file`) is the first and only
group today; its SFTP specifics are read through `adapters.erp_newworld`.

THE PASSWORD
------------
Typed on the form, sent once in the body of `PUT`, written by
`services.record_credential` into the GROUP's own credential slot (encrypted,
`core/crypto.py`), and never read back to any screen: `view()` serves the
masked hint (`••••` + last four) and nothing else. Leaving the box empty on a
later save keeps the stored password — so changing the folder does not mean
typing the password again — and the audit row carries hints, never the value.

THE SERVER KEY
--------------
Changing the SERVER clears a stored server key unless a new one is typed in
the same save: a key confirmed for one host proves nothing about another, and
carrying it across would make the first night against the new host fail with
*Server key does not match.* for no reason the administrator could see — or,
worse, the opposite. **Test connection** with no stored key signs in, writes
the test file, and STORES the key it saw, showing it on the screen; that is
the one moment a key is captured, and a person pressed the button for it
(decision log 2026-10-07).
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from django.db import transaction

from apps.integrations import models, receipt_push, services, sftp
from apps.integrations.adapters.base import FieldError, validate_fields
from apps.integrations.adapters.erp_newworld import is_set_up, place_test_file
from apps.integrations.manifests.erp_newworld import (
    SFTP_HOST,
    SFTP_HOST_KEY,
    SFTP_PASSWORD,
    SFTP_USERNAME,
)
from apps.integrations.registry import REGISTRY, Registry
from core import audit as core_audit
from core import errors
from core.permissions import SYSTEM_ADMIN, require_role

AUDIT_SAVED = "integration.file_drop.saved"
AUDIT_TESTED = "integration.file_drop.tested"
AUDIT_RESENT = "integration.file_drop.resent"

REFUSAL_NO_GROUP = "integrations.refusal.no_group"
REFUSAL_REASON = "integrations.refusal.resend_reason"
FIELD_REQUIRED = "integrations.field.required"
FIELD_HOST_KEY = "integrations.field.host_key"
FIELD_UNKNOWN = "integrations.field.unknown"


def _group_fields(provider_key: str, group: str, registry: Registry) -> dict[str, Any]:
    manifest = registry.require(provider_key)
    found = {one.name: one for one in manifest.fields if one.group == group}
    if not found:
        raise errors.NotFoundError()
    return found


def _connection(tenant_id: Any, provider_key: str) -> models.IntegrationConnection:
    row = services.connection_for(tenant_id, provider_key)
    if row is None or not row.enabled:
        raise errors.BizError(
            errors.BIZ_STATE, br_ref="BR-INT-002", message_key=services.REFUSAL_NOT_CONNECTED
        )
    return row


def _password_hint(conn: models.IntegrationConnection, group: str) -> str | None:
    row = (
        models.IntegrationCredential.objects.filter(connection=conn, is_active=True, slot=group)
        .only("masked_hint")
        .first()
    )
    return row.masked_hint if row is not None else None


def view(
    tenant_id: Any, provider_key: str, group: str, *, registry: Registry = REGISTRY
) -> dict[str, Any]:
    """The section as the screen draws it — settings, the password's HINT, recent files."""
    fields = _group_fields(provider_key, group, registry)
    conn = services.connection_for(tenant_id, provider_key)
    config = dict(conn.config or {}) if conn is not None else {}
    settings = {
        name: config.get(name, one.default or "")
        for name, one in fields.items()
        if not one.is_secret
    }
    return {
        "group": group,
        "connected": conn is not None and conn.enabled,
        "settings": settings,
        "password_hint": _password_hint(conn, group) if conn is not None else None,
        "set_up": conn is not None and is_set_up(config),
        "deliveries": receipt_push.recent_deliveries(conn) if conn is not None else [],
    }


@require_role(SYSTEM_ADMIN)
def save(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    group: str,
    values: dict[str, Any],
    registry: Registry = REGISTRY,
) -> dict[str, Any]:
    """`PUT /integrations/{key}/groups/{group}` — the whole section, one save.

    Refuses by field, every problem at once, before any write: an unknown name;
    a value the field's kind refuses; server, user name and password not all
    present (the password may be the stored one); a server key that is not a
    `SHA256:` fingerprint.
    """
    fields = _group_fields(provider_key, group, registry)
    manifest = registry.require(provider_key)
    conn = _connection(tenant_id, provider_key)
    supplied = dict(values or {})
    problems: list[FieldError] = [
        FieldError(name, FIELD_UNKNOWN) for name in supplied if name not in fields
    ]
    secret_names = {name for name, one in fields.items() if one.is_secret}
    config_part = {
        name: ("" if value is None else str(value).strip())
        for name, value in supplied.items()
        if name in fields and name not in secret_names
    }
    secrets = {
        name: str(value)
        for name, value in supplied.items()
        if name in secret_names and value not in (None, "")
    }
    shaped = {k: v for k, v in config_part.items() if v != ""}
    problems.extend(
        one
        for one in validate_fields(manifest, shaped, secrets=None, require_secrets=False)
        if one.field in fields
    )
    typed_key = config_part.get(SFTP_HOST_KEY, "")
    if typed_key:
        normal = sftp.normalise_fingerprint(typed_key)
        if not normal:
            problems.append(FieldError(SFTP_HOST_KEY, FIELD_HOST_KEY))
        else:
            config_part[SFTP_HOST_KEY] = normal
    host = config_part.get(SFTP_HOST, str((conn.config or {}).get(SFTP_HOST) or ""))
    if host:
        # Server, user name and password together — a half-typed section is
        # one that fails at night, so it is refused now, by field.
        if not config_part.get(SFTP_USERNAME, str((conn.config or {}).get(SFTP_USERNAME) or "")):
            problems.append(FieldError(SFTP_USERNAME, FIELD_REQUIRED))
        if not secrets.get(SFTP_PASSWORD) and _password_hint(conn, group) is None:
            problems.append(FieldError(SFTP_PASSWORD, FIELD_REQUIRED))
    if problems:
        raise services._field_refusal(problems)

    before_config = dict(conn.config or {})
    after_config = dict(before_config)
    for name, value in config_part.items():
        if value == "":
            after_config.pop(name, None)
        else:
            after_config[name] = value
    # A new server forgets the old server's key, unless one was typed now.
    if (
        str(after_config.get(SFTP_HOST) or "") != str(before_config.get(SFTP_HOST) or "")
        and not typed_key
    ):
        after_config.pop(SFTP_HOST_KEY, None)
    with transaction.atomic():
        if after_config != before_config:
            conn.config = after_config
            conn.save(update_fields=["config", "updated_at"])
        hint_before = _password_hint(conn, group)
        hint_after = hint_before
        if secrets:
            credential = services.record_credential(
                actor=actor,
                connection=conn,
                payload=json.dumps(secrets),
                masked_hint=services._hint(secrets),
                slot=group,
                audit_action=None,  # the ONE audit row for this save is below
            )
            hint_after = credential.masked_hint
        changed = {
            name: {"from": before_config.get(name), "to": after_config.get(name)}
            for name in fields
            if name not in secret_names and before_config.get(name) != after_config.get(name)
        }
        if changed or hint_after != hint_before:
            core_audit.money_action(
                actor,
                AUDIT_SAVED,
                "integration_connection",
                conn.id,
                before={"group": group, "password": hint_before},
                after={"group": group, "changed": changed, "password": hint_after},
            )
    return view(tenant_id, provider_key, group, registry=registry)


@require_role(SYSTEM_ADMIN)
def test(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    group: str,
    started_by_name: str | None = None,
    registry: Registry = REGISTRY,
) -> dict[str, Any]:
    """**Test connection** — sign in, WRITE a clearly named file, delete it if allowed.

    Synchronous, inside the web request: a person is looking at the button,
    and the client's own timeouts (`sftp.CONNECT_TIMEOUT` + `AUTH_TIMEOUT`)
    keep the worst case well inside the worker's sixty seconds. The attempt is
    a run row like every other, so the run history shows it.

    With no server key stored, the key the server presented is STORED and
    returned — the one place a key is captured, and only after the sign-in and
    the write both succeeded.
    """
    _group_fields(provider_key, group, registry)
    conn = _connection(tenant_id, provider_key)
    config = dict(conn.config or {})
    stored_key = str(config.get(SFTP_HOST_KEY) or "")
    secrets = services.credential_secrets(conn, slot=group)
    result, seen, where = place_test_file(config, secrets, capture=not stored_key)
    del secrets
    run = services.start_run(
        connection=conn,
        operation=receipt_push.OPERATION,
        direction=models.RUN_DIRECTION_OUTBOUND,
        trigger="manual",
    )
    if started_by_name:
        run.started_by_name = started_by_name
        run.save(update_fields=["started_by_name"])
    captured = None
    if result.ok and seen and not stored_key:
        config[SFTP_HOST_KEY] = seen
        conn.config = config
        conn.save(update_fields=["config", "updated_at"])
        captured = seen
    services.finish_run(
        run,
        attempted=1,
        succeeded=1 if result.ok else 0,
        failed=0 if result.ok else 1,
        skipped=0,
        confirmed=True,
        summary=f"Connection test · {result.sentence}",
        provider_error=result.provider_text,
    )
    core_audit.money_action(
        actor,
        AUDIT_TESTED,
        "integration_connection",
        conn.id,
        after={
            "group": group,
            "ok": result.ok,
            "sentence": result.sentence,
            "server_key_stored": captured,
            "trace_id": run.trace_id,
        },
    )
    return {
        "ok": result.ok,
        "sentence": result.sentence,
        "server_key": captured or stored_key or None,
        "server_key_captured": captured is not None,
        "test_file": where,
        "trace": run.trace_id,
    }


@require_role(SYSTEM_ADMIN)
def resend(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    group: str,
    day: date,
    reason: str,
    started_by_name: str | None = None,
    registry: Registry = REGISTRY,
) -> dict[str, Any]:
    """A person sends a day AGAIN, on purpose, with a reason (PO Q4: a resend is a deliberate act).

    The only caller of `receipt_push.send(resend=True)`. Nothing scheduled can
    reach this function: it is behind a System Admin's session and refuses an
    empty reason.
    """
    _group_fields(provider_key, group, registry)
    _connection(tenant_id, provider_key)
    why = str(reason or "").strip()
    if not why:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key=REFUSAL_REASON,
            field_errors=[FieldError("reason", FIELD_REQUIRED).envelope()],
        )
    result = receipt_push.send(
        day,
        trigger="manual",
        actor=actor,
        started_by_name=started_by_name,
        resend=True,
        reason=why,
    )
    core_audit.money_action(
        actor,
        AUDIT_RESENT,
        "integration_connection",
        services.connection_for(tenant_id, provider_key).id,
        after={"day": day.isoformat(), "reason": why, **result.as_dict()},
    )
    return result.as_dict()
