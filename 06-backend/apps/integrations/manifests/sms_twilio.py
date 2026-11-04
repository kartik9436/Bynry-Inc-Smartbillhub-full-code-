"""Text messages (Twilio) — send a text and hear whether it arrived (Messaging · LIVE, PROVIDED BY THE PLATFORM).

⚠ **LIVE FROM 2026-10-29 (`CR-198-BRC10`), AND `BR-INT-001`'s *Twilio SMS
(v1.1)* IS SUPERSEDED.** PO, verbatim: *"1A 2A 4B 5 US 6A(ONly Stop option is
required), start"* — build SMS now (it was *"later"* on 2026-09-17), every
existing text goes, through ONE SHARED PLATFORM Twilio account, US first (A2P
10DLC — so a Messaging Service is supported), STOP only.

⚠ **`platform_holds_ours` — THE PLATFORM HOLDS THE CREDENTIAL, NOT THE UTILITY.**
The Account SID, the Auth Token and the senders are SERVER secrets read by
`apps/integrations/platform_sms.py`. The fields below DESCRIBE what that file
reads, so the adapter and the conformance kit have one shape; no utility types
any of them, `services.connect_with_fields` refuses a connect by name, and the
card reads *Provided by the platform*.

THREE THINGS HAPPEN. We send; Twilio tells us what happened to each text; a
customer's reply comes back to us (and only STOP is acted on). Twilio posts
FORM-encoded bodies and signs them with `X-Twilio-Signature` — HMAC-SHA1 over
the full URL plus every field sorted by name, keyed by the Auth Token — which
`apps/integrations/platform_door.py` checks before anything is read. Their
statuses repeat one message id (`sent`, then `delivered`), so a status is
deduped on `MessageSid` + `MessageStatus`, never on the id alone.

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.sms_twilio.*` wins on screen when present, so a
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
    key="sms_twilio",
    category="messaging",
    #: ⚠ RENAMED FROM *Text messages* (`CR-110-BRC04`). CFG-05 draws the page
    #: head as **Twilio**.
    display_name="Twilio",
    summary="Send a text and hear whether it arrived.",
    #: ⚠ WAS `coming_soon · v1.1` UNTIL 2026-10-29. The adapter
    #: (`adapters/sms_twilio.py`) landed in the same commit, so the
    #: adapter ⇔ live equivalence holds in the new direction.
    disposition=Disposition(kind="live", phase=2),
    #: `platform_holds_ours` (`registry.MODE_PLATFORM_HOLDS_OURS`): our own
    #: account, server-held. `native`: the credential is HTTP Basic, built by
    #: the adapter from the platform's secrets — no position a utility fills.
    auth=Auth(mode="platform_holds_ours", placement="native"),
    fields=(
        #: The real address, where the phase-1 placeholder
        #: `https://api.twilio.example` stood. The server may point it at a fake
        #: for a test or a walkthrough (`TWILIO_API_BASE_URL`).
        Field(
            name="base_url",
            label="Service address",
            kind="url",
            required=False,
            default="https://api.twilio.com",
        ),
        Field(name="account_sid", label="Account SID", kind="text"),
        Field(name="auth_token", label="Auth token", kind="secret"),
        #: EXACTLY ONE of the next two is used per text — the Messaging Service
        #: when set (A2P 10DLC needs one), else the number.
        Field(
            name="messaging_service_sid",
            label="Messaging service",
            kind="text",
            required=False,
        ),
        Field(name="from_number", label="Send from number", kind="text", required=False),
    ),
    operations=(
        Operation(
            name="send_message",
            label="Send texts",
            description="We send a text through their service.",
            direction="out",
            initiative="us",
            transport="https",
            trigger="dispatcher",
            # A long code sends about one message a second, and Twilio queues
            # beyond that rather than refusing — so a higher ceiling here
            # would only build a backlog we cannot see. A 10DLC campaign may
            # allow more; raise this once its approved throughput is known.
            rate_limit_per_minute=60,
            idempotency=Idempotency(mode="refuse", source="queue_row_id"),
            completion="immediate",
            codec="form",
            test_action="Send one real text to a number you type.",
            test_needs_recipient=True,
        ),
        Operation(
            name="validate_credentials",
            label="Check the login",
            description="We ask the service whether our login works.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="inline",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            latency_budget_ms=1000,
            result_disposition="offer",
            rate_limit_per_minute=60,
        ),
        Operation(
            name="receive_status",
            label="Delivery status",
            description="They tell us whether each text arrived.",
            direction="in",
            initiative="them",
            transport="https",
            trigger="webhook",
            # ⚠ `MessageSid` ALONE IS NOT A KEY: Twilio posts `sent` and then
            # `delivered` for ONE sid. The door composes `MessageSid|MessageStatus`
            # (`platform_door.status_key`) — so both land, and a retried
            # `delivered` lands once.
            idempotency=Idempotency(
                mode="refuse", source="provider_event_id", key_field="MessageSid"
            ),
            completion="immediate",
            codec="form",
            respond_after="persist",
            # INWARD. A text run's delivery statuses arrive in a burst behind the
            # messages, so this matches the email receipts door rather than
            # the sixty we send at.
            rate_limit_per_minute=600,
            envelope_status={"ok": 200, "duplicate": 200, "refused": 401},
        ),
        Operation(
            name="receive_reply",
            label="Replies",
            description="A customer's reply; STOP stops their texts.",
            direction="in",
            initiative="them",
            transport="https",
            trigger="webhook",
            idempotency=Idempotency(
                mode="refuse", source="provider_event_id", key_field="MessageSid"
            ),
            completion="immediate",
            codec="form",
            respond_after="persist",
            rate_limit_per_minute=600,
            envelope_status={"ok": 200, "duplicate": 200, "refused": 401},
        ),
    ),
)
