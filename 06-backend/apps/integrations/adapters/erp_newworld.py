# ── Trace ──────────────────────────────────────────────
# Change:   CR-173-BRC10 — New World / Logos's ONE outbound operation, *Send
#           receipt file*: place an already-built file in the City's SFTP
#           folder, and prove the folder can be written to.
# Rules:    PO 2026-10-07 (the *Send to City folder* section: *"a 'Test
#           connection' button that signs in and proves the folder can be
#           WRITTEN to (not merely listed)"*) · BR-INT-019 (`test()` is the
#           smallest REAL instance) · BR-INT-038 (an adapter TRANSLATES: no
#           retry, no scheduling, no persistence) · BR-INT-054 as amended (it
#           places a file and never decides what is in one) · BR-INT-003
# Tests:    06-backend/tests/test_cr173_newworld_sftp.py (conformance kit
#           included, against the in-process fake SFTP server)
# Impacts:  apps/integrations/adapters/__init__.py (the one binding line) ·
#           apps/integrations/file_drop.py · apps/integrations/receipt_push.py
# ───────────────────────────────────────────────────────
"""New World / Logos — the half WE dial: a file placed in the City's folder.

The other two operations on this connector are the City dialling us
(`/partner/v1/receipts`, `/partner/v1/ledger`), and they need no adapter. This
one is ours, which is why `Manifest.we_never_dial` is now False for
`erp_newworld` and this file exists.

WHAT IT DOES AND WHAT IT DOES NOT
---------------------------------
It **places bytes it is given** — `execute(work=[{filename, payload}])` — and
proves it can (`test()` writes a clearly named test file and removes it again).
It does not choose a day, query a payment or render XML: the file is built by
`receipt_push.build_file` from the same filter and the same writer the API
uses, and that is driven by the runbook (`BR-INT-054`, *"conenctor i a
conenctor not a logic to to ETL"*).

THE SERVER KEY
--------------
Read from the connection's `sftp_host_key`. `test()` and `execute()` here never
CAPTURE one: an adapter call is the unattended path, and an unattended path
that accepts whatever key it is shown is the one this connector must never
have. Capture happens only when a person presses **Test connection** on the
*Send to City folder* panel (`file_drop.test`), which shows the key it saw.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from apps.integrations import sftp
from apps.integrations.adapters.base import (
    ITEM_FAILED,
    ITEM_SUCCEEDED,
    Adapter,
    ConnectionView,
    FieldError,
    FieldErrors,
    ItemResult,
    RunResult,
    TestResult,
)
from apps.integrations.manifests.erp_newworld import (
    SFTP_HOST,
    SFTP_HOST_KEY,
    SFTP_PASSWORD,
    SFTP_PATH,
    SFTP_PORT,
    SFTP_USERNAME,
)

#: ≤ 6 words (B14 rule 33).
NO_CLIENT_SENTENCE = "No folder client is installed."
WROTE_SENTENCE = "Signed in and wrote a file."
WROTE_KEPT_SENTENCE = "Wrote a file; could not delete it."
NOT_SET_UP_SENTENCE = "No server set for this."
BAD_KEY_SENTENCE = "Paste the SHA256 server key."

#: The test file's name. It says what it is, so whoever finds it in the City's
#: folder knows at a glance it holds no receipts — and it can never collide
#: with `Receipt_YYYYMMDD.xml`, which New World imports.
TEST_FILE_PREFIX = "SMART360-connection-test"


def target_of(config: Mapping[str, Any], secrets: Mapping[str, str]) -> dict[str, Any]:
    """The client's keyword arguments, from a connection's settings and its group secret."""
    try:
        port = int(str(config.get(SFTP_PORT) or sftp.DEFAULT_PORT))
    except ValueError:
        port = sftp.DEFAULT_PORT
    return {
        "host": str(config.get(SFTP_HOST) or "").strip(),
        "port": port,
        "username": str(config.get(SFTP_USERNAME) or "").strip(),
        "password": str(secrets.get(SFTP_PASSWORD) or ""),
        "path": str(config.get(SFTP_PATH) or "/").strip() or "/",
        "host_key": str(config.get(SFTP_HOST_KEY) or "").strip(),
    }


def is_set_up(config: Mapping[str, Any]) -> bool:
    """A server is typed — the per-utility switch (PO S1). The password is checked
    when it is used, because it is not in `config` and never will be."""
    return bool(str(config.get(SFTP_HOST) or "").strip())


def test_filename(now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    return f"{TEST_FILE_PREFIX}-{stamp}.txt"


def test_payload(now: datetime | None = None) -> bytes:
    stamp = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    return (
        "SMART360 connection test. This file holds no receipts.\n"
        f"Written {stamp}. It may be deleted.\n"
    ).encode("utf-8")


def place_test_file(
    config: Mapping[str, Any], secrets: Mapping[str, str], *, capture: bool
) -> tuple[TestResult, str | None, str | None]:
    """Sign in, write the test file, remove it. → `(result, fingerprint seen, remote path)`.

    Never raises for the far end's refusal. `fingerprint` is None when nothing
    was proved (a refused sign-in proves nothing about which server answered,
    so nothing from it is offered for storing).
    """
    client = sftp.client()
    if client is None:
        return TestResult(ok=False, sentence=NO_CLIENT_SENTENCE), None, None
    if not is_set_up(config):
        return TestResult(ok=False, sentence=NOT_SET_UP_SENTENCE), None, None
    target = target_of(config, secrets)
    try:
        placed, removed = client.write_and_remove(
            **target,
            filename=test_filename(),
            payload=test_payload(),
            capture=capture,
        )
    except sftp.SftpError as refusal:
        return (
            TestResult(ok=False, sentence=refusal.sentence, provider_text=refusal.detail or refusal.code),
            None,
            None,
        )
    sentence = WROTE_SENTENCE if removed else WROTE_KEPT_SENTENCE
    return TestResult(ok=True, sentence=sentence), placed.fingerprint, placed.remote_path


class ErpNewWorldAdapter(Adapter):
    """Four methods. It places a file and proves it can; it builds none."""

    key = "erp_newworld"

    def validate(self, config: Mapping[str, Any]) -> FieldErrors:
        """The server key, when typed, must be a `SHA256:` fingerprint.

        A value without that token could never match any server, so storing it
        would be a setting that silently refuses every night. No network.
        """
        errors: FieldErrors = []
        typed = str(config.get(SFTP_HOST_KEY) or "").strip()
        if typed and not sftp.normalise_fingerprint(typed):
            errors.append(FieldError(SFTP_HOST_KEY, message_key="integrations.field.host_key"))
        return errors

    def test(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        *,
        recipient: str | None = None,
    ) -> TestResult:
        """Write a test file and remove it — with the key the connection already trusts."""
        result, _seen, _where = place_test_file(conn.config or {}, secrets, capture=False)
        return result

    def execute(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        work: Sequence[Mapping[str, Any]],
    ) -> RunResult:
        """Place each already-built file. Per item; a refusal is a failed item, never a raise."""
        if not work:
            return RunResult(items=(), confirmed=True)
        client = sftp.client()
        items: list[ItemResult] = []
        target = target_of(conn.config or {}, secrets)
        for one in work:
            ref = str(one.get("filename") or "")
            if client is None:
                items.append(ItemResult(ref=ref, outcome=ITEM_FAILED, detail=NO_CLIENT_SENTENCE))
                continue
            try:
                client.write(
                    **target,
                    filename=ref,
                    payload=bytes(one.get("payload") or b""),
                )
            except sftp.SftpError as refusal:
                items.append(
                    ItemResult(
                        ref=ref,
                        outcome=ITEM_FAILED,
                        detail=refusal.sentence,
                        provider_text=refusal.detail or refusal.code,
                    )
                )
            else:
                items.append(ItemResult(ref=ref, outcome=ITEM_SUCCEEDED))
        # `confirm=True` on the write compares the file's size on their side:
        # the far end SAID it holds every byte, which is what `confirmed` means.
        return RunResult(items=tuple(items), confirmed=True)

    def describe(self, conn: ConnectionView) -> str:
        """*Sends to sftp.a2gov.org /* — no user name, no password."""
        config = conn.config or {}
        host = str(config.get(SFTP_HOST) or "").strip()
        if not host:
            return "The City reads our receipts"
        folder = str(config.get(SFTP_PATH) or "/").strip() or "/"
        return f"Sends to {host} {folder}"
