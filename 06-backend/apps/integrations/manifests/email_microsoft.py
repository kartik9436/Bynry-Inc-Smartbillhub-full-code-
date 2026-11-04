"""Microsoft 365 — send bills from the utility's own mailbox (Email · LIVE · OAuth redirect).

A BYO mailbox (BR-INT-005): the utility signs in to Microsoft and we hold a
refresh token that is exchanged for a short-lived one at send time
(BR-INT-047) — the token is never written to the credential table. The modal
body is a button and a return trip; there is no Save, because the round trip is
the save (49.2). ⚠ A mailbox stops working somewhere around 2,000 external
recipients a day — `OQ-INT-1488` asks whether the bulk connector becomes
mandatory above a bill volume, and this file does not answer it.

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.email_microsoft.*` wins on screen when present, so a
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
    key="email_microsoft",
    category="email",
    display_name="Microsoft 365",
    summary="Send bills from your own mailbox.",
    disposition=Disposition(kind="live", phase=3),
    auth=Auth(
        mode="token_exchange",
        placement="redirect",
        # Where the sign-in button sends a person, and where the code it comes
        # back with is exchanged. DATA, not code: `apps/integrations/oauth.py`
        # serves Microsoft and Google from the same lines and branches on
        # neither (BR-INT-043, BR-INT-037).
        oauth=OAuthEndpoints(
            authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
            # The narrowest pair that sends a bill from the signed-in mailbox.
            # `offline_access` is what makes a REFRESH token come back at all —
            # without it the consent lasts an hour and every utility would be
            # re-authorising before lunch.
            scopes=("https://graph.microsoft.com/Mail.Send", "offline_access"),
            # Microsoft asks for consent again every ninety days (frame 54.1
            # says so to the clerk in those words). Used only when the token
            # response does not carry its own lifetime.
            default_lifetime_days=90,
        ),
    ),
    fields=(
        #: The PO's phase-1 dummy API — a placeholder address seeded as
        #: data so this connector's operations have a host that resolves
        #: today (`DEF-INT-5488`: fifteen of eighteen manifests named a
        #: host field none of them declared).
        #: NOT required: Microsoft publish one address for everybody, so a
        #: clerk who never touches this box is right. CFG-01 draws two
        #: fields and this is not one of them — but the API panel's own
        #: footnote reads *All 1 use the address above* over a form with
        #: no address on it, and that contradiction is what this closes.
        Field(
            name="base_url",
            label="Service address",
            kind="url",
            required=False,
            default="https://graph.microsoft.example",
        ),
        Field(name="sign_in", label="Sign in with Microsoft", kind="redirect"),
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
            # A hosted mailbox throttles a sender at about thirty a minute, so
            # pacing ourselves at the same figure means we are refused by our
            # own ceiling rather than discovering theirs by being cut off.
            # These two mailbox connectors are for the bottom of the ICP;
            # 6,000 bills a cycle is what `email_bulk` exists for.
            rate_limit_per_minute=30,
            idempotency=Idempotency(mode="refuse", source="queue_row_id"),
            completion="immediate",
            codec="mime",
            test_action="Send one real message to an address you type.",
            test_needs_recipient=True,
        ),
    ),
)
