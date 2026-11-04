"""Custom SMTP — any mail server with a host and a password (Email · LIVE · password).

The first adapter this product will connect (phase 2's launch). The password
lands in `integration_credential.payload_enc` and nowhere else; `host`, `port`,
`username` and `send_from` are non-secret and live in `config`. Placement is
`native` — SMTP AUTH carries the credential in the protocol handshake, not in
an HTTP header (registry docstring).

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.email_smtp.*` wins on screen when present, so a
translation is a catalogue line and never an edit to this file.
"""

from apps.integrations.registry import (
    Auth,
    Disposition,
    Field,
    Idempotency,
    Manifest,
    Operation,
)

MANIFEST = Manifest(
    key="email_smtp",
    category="email",
    display_name="Custom SMTP",
    summary="Any mail server with a host and a password.",
    disposition=Disposition(kind="live", phase=2),
    auth=Auth(mode="we_hold_theirs", placement="native"),
    fields=(
        Field(name="host", label="Mail server", kind="host"),
        Field(name="port", label="Port", kind="port"),
        Field(name="username", label="Username", kind="text"),
        Field(name="password", label="Password", kind="secret"),
        Field(name="send_from", label="Send bills from", kind="email"),
    ),
    operations=(
        Operation(
            name="send_message",
            label="Send messages",
            description="We send bills and notices through this server.",
            direction="out",
            initiative="us",
            transport="smtp",
            trigger="dispatcher",
            # ⚠ THE ADDRESS THIS CONNECTOR ALREADY COLLECTS. CFG-03 draws its
            # one operation against a different, made-up web address while the
            # form asks for a mail server on line one; the form wins, because
            # a clerk who typed a server expects it to be used.
            host_field="host",
            # A utility's own mail server, not a bulk service: paced, but under
            # our own control rather than a hosted mailbox's. Two a second.
            rate_limit_per_minute=120,
            idempotency=Idempotency(mode="refuse", source="queue_row_id"),
            completion="immediate",
            codec="mime",
            test_action="Send one real message to an address you type.",
            test_needs_recipient=True,
        ),
    ),
)
