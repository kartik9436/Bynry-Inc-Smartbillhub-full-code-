"""Google Workspace — send bills from the utility's own mailbox (Email · LIVE · OAuth redirect).

The same shape as Microsoft 365, and deliberately the same file shape: two
mailbox providers are two manifests and one adapter protocol, not two screens.

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.email_google.*` wins on screen when present, so a
translation is a catalogue line and never an edit to this file.
"""

from apps.integrations.registry import (
    Auth,
    Disposition,
    Field,
    Idempotency,
    Manifest,
    OAuthEndpoints,
    Operation,
)

MANIFEST = Manifest(
    key="email_google",
    category="email",
    display_name="Google Workspace",
    summary="Send bills from your own mailbox.",
    disposition=Disposition(kind="live", phase=3),
    auth=Auth(
        mode="token_exchange",
        placement="redirect",
        # See `email_microsoft.py` — the same three declared strings, a
        # different provider, and no branch anywhere between them.
        oauth=OAuthEndpoints(
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scopes=("https://www.googleapis.com/auth/gmail.send",),
            # A Google refresh token does not expire on a clock the way
            # Microsoft's consent does; it is revoked, or it goes unused for
            # six months. Ninety days is therefore a REVIEW cadence rather than
            # a lapse date, and it is written here so a utility is asked to
            # look rather than told a falsehood about the day it stops.
            default_lifetime_days=90,
        ),
    ),
    fields=(
        #: The PO's phase-1 dummy API — a placeholder address seeded as
        #: data so this connector's operations have a host that resolves
        #: today (`DEF-INT-5488`: fifteen of eighteen manifests named a
        #: host field none of them declared).
        #: NOT required — see `email_microsoft`: one published address for
        #: everybody, so an untouched box is the right outcome.
        Field(
            name="base_url",
            label="Service address",
            kind="url",
            required=False,
            default="https://gmail.googleapis.example",
        ),
        Field(name="sign_in", label="Sign in with Google", kind="redirect"),
        Field(name="send_from", label="Send bills from", kind="email"),
    ),
    operations=(
        Operation(
            name="send_message",
            label="Send messages",
            description="We send bills and notices through this mailbox.",
            direction="out",
            initiative="us",
            transport="https",
            trigger="dispatcher",
            # Thirty a minute, for the reason `email_microsoft` gives in full: a
            # hosted mailbox paces a sender at about that, and matching it is
            # how we stay inside their ceiling instead of finding it.
            rate_limit_per_minute=30,
            idempotency=Idempotency(mode="refuse", source="queue_row_id"),
            completion="immediate",
            codec="mime",
            test_action="Send one real message to an address you type.",
            test_needs_recipient=True,
        ),
    ),
)
