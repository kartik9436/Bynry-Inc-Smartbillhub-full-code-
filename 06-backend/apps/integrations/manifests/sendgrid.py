"""SendGrid — high-volume bulk sending (Email · LIVE · API key + sending domain).

BR-INT-006: the transactional ESP connected AS THE TENANT'S INTEGRATION.
Two operations, one credential: we send, and the provider calls us back with
delivery and bounce feedback (C28) — until that second operation runs, the
delivery dashboard keeps reading *not reported* and never zero (BR-INT-027).
The feedback door replies after `persist` — a generic webhook's 200-then-process
(BR-INT-030) — and answers a replayed event 200, not 409 (BR-INT-045).

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.sendgrid.*` wins on screen when present, so a
translation is a catalogue line and never an edit to this file.

⚠ **THIS FILE WAS `email_bulk` UNTIL 2026-09-17, AND ITS OWN FIRST LINE SAID
`LIVE` WHILE IT DECLARED `coming_soon` (`DEF-INT-5638`).** That is hard-won
law 1 — a comment claiming a guarantee is not the guarantee — sitting in the one
place a reader looks first. The disposition was right and the sentence was
wrong; the sentence is now the disposition's, and the two move together or the
hold test below goes red. `CR-115-BRC05`, and the key moved with it
(`email_bulk` → `sendgrid`).

⚠ **`we_hold_theirs` MEANS THE UTILITY BRINGS ITS OWN SENDGRID ACCOUNT, AND THE
PO RULED FOR SOMETHING ELSE — `DEF-INT-5636`, DEFERRED ON PURPOSE.** On
2026-09-17 the PO said *"our account - we will provide service to utilities as
platform provider"*: OUR credential, sending on every utility's behalf.
**`registry.AUTH_MODES` has no mode for that** — `we_hold_theirs` is the
utility's own credential and `they_hold_ours` is a key we issue to a partner —
and the credential could not live in `integration_credential` anyway, which has
RLS FORCED. So this connector **ships in the tenant-credential shape that works
today**, which is honest and reversible, and the platform-sends-for-you shape is
its own wave: a fifth auth mode, a platform-level table (`platform_number_series`
is the precedent) and a key-rotation story. Inventing it here would have been a
signed vocabulary widened inside a manifest file. `postmark` says the same.

⚠ **THE RENAME WAS FREE BY CONSTRUCTION AND NOT BY AN EMPTY TABLE, WHICH IS THE
STRONGER STATEMENT AND THE ONE WORTH WRITING DOWN.** A key lives in
`integration_connection.provider_key`, so renaming after a single utility had
connected would be a data migration on a tenant-scoped table under RLS. It is
not, because **no code path in this product can ever have written such a row:**

  * the one clerk-reachable path is `POST /integrations/{key}/connect` →
    `services.connect_with_fields`, whose step 1 refuses a `coming_soon` card
    (`BR-INT-001`) and whose step 2 refuses a provider with no adapter bound
    (`DEF-INT-4224`) — **both before the write**, and this connector has always
    failed at least one of them: it has never had an adapter, which
    `test_cr110__a_placeholder_has_no_adapter_bound` asserts;
  * `sample_data` seeds `email_smtp`, `meters_neptune360`, `bank_lockbox_file`;
  * `live_calls.LIVE_CALL_DEFAULTS` seeds `geocoder_census`, `map_tiles_public`.

The development database was also read tenant by tenant under RLS on
2026-09-16 (`manifests/__init__.py` records it): twelve connection rows across
four tenants, none of them this key. **A row count would have proved one
deployment; the refusals above prove every deployment.**

⚠ **THE ONE THING THIS MANIFEST DELIBERATELY DOES NOT SAY IS HOW SENDGRID
SIGNS ITS WEBHOOK — `DEF-INT-5630`, OPEN.** See `receive_feedback` below.
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
    key="sendgrid",
    category="email",
    display_name="SendGrid",
    summary="High-volume bulk sending",
    #: ⚠ **TWO HOLDS HAVE STOOD HERE AND BOTH HAVE NOW EXPIRED. THE HISTORY IS
    #: KEPT BECAUSE IT IS THE ARGUMENT FOR HOW THE NEXT ONE SHOULD BE WRITTEN.**
    #:
    #: The first fired on the DISPLAY NAME — *while the vendor is generic the
    #: card says coming soon* (PO 2026-09-16: *"theya re dummay right now we
    #: will replace them later"*). Naming the vendor on 2026-09-17 outgrew it,
    #: and it could not survive the rename in either direction: left alone it
    #: demanded this card go LIVE with nothing behind it, which is
    #: `DEF-INT-4224` exactly and which the blueprint files as a defect in its
    #: own right (p146); satisfied by adding *SendGrid* to the placeholder map
    #: it would have recorded a real, contracted vendor as a placeholder.
    #:
    #: The second re-aimed it at the thing it was always about — **can this card
    #: be pressed and work** — by firing on `registry.adapter_for()`. That is
    #: the hold below, and it expired on 2026-09-17 when the adapter landed.
    #: **Its test did not need editing, because it was written to assert BOTH
    #: DIRECTIONS**, which is the whole lesson: a hold with a clock in it rots
    #: silently (hard-won law 2's mirror), and a hold written as an
    #: EQUIVALENCE cannot.
    #: ⚠ **LIVE FROM 2026-09-17, AND THE HOLD ABOVE IS NOT DELETED — IT
    #: EXPIRED, WHICH IS A DIFFERENT THING.**
    #: `test_cr115__a_connector_with_no_adapter_says_coming_soon` asserts BOTH
    #: DIRECTIONS: this card is coming-soon for exactly as long as
    #: `registry.adapter_for` answers `None`, and live for exactly as long as it
    #: does not. `adapters/email_sendgrid.py` landed in the same commit as this
    #: line, so the two moved together or that test would have named this file.
    #: `register_adapter` refuses to bind an adapter to a coming-soon provider
    #: (`BR-INT-001`), so this cannot be half-released from either side.
    #:
    #: ⚠ **WHAT *LIVE* PROMISES AND WHAT IT DOES NOT.** It promises that a
    #: utility can connect this card, press *Test*, and have one real message
    #: leave. It promises nothing about DELIVERY: `202` is ACCEPTED, the queue
    #: row becomes `sent`, and `delivered` stays unwritten while
    #: `receive_feedback`'s door is held shut by `DEF-INT-5630` — so
    #: `delivery_counts`' *not reported* sentence goes on being true.
    disposition=Disposition(kind="live", phase=2),
    #: ⚠ **`bearer`, NOT `header` — AND THE CHANGE IS A FACT ARRIVING, NOT A
    #: TIDY.** SendGrid authenticates with `Authorization: Bearer <api key>`.
    #: While the vendor was unnamed this said `header` and named no header,
    #: which `inbound.credential_header` refuses closed and which no adapter
    #: could have acted on. `bearer` needs no `header` name — the header is
    #: `Authorization` by definition — and the registry refuses one here as
    #: dead data.
    #:
    #: ⚠ **`auth.inbound` IS ABSENT ON PURPOSE AND ABSENT MEANS `presented_key`.
    #: THAT IS NOT WHAT SENDGRID DOES.** See `receive_feedback`.
    auth=Auth(mode="we_hold_theirs", placement="bearer"),
    fields=(
        #: ⚠ **A REAL ADDRESS NOW, WHERE THE PLACEHOLDER
        #: `https://api.bulk-email.example` STOOD.** The phase-1 dummy API
        #: (PO 2026-09-16) existed so `DEF-INT-5488`'s *no connection ever
        #: holds a host* stopped being true before a vendor contract was
        #: signed. The contract is signed and the account exists, so the
        #: seeded default is the address the adapter will really dial.
        Field(
            name="base_url",
            label="Service address",
            kind="url",
            required=False,
            default="https://api.sendgrid.com",
        ),
        Field(name="api_key", label="API key", kind="secret"),
        Field(name="sending_domain", label="Sending domain", kind="host"),
        Field(name="send_from", label="Send bills from", kind="email"),
    ),
    operations=(
        Operation(
            name="send_message",
            label="Send messages",
            description="We hand each bill to the service to deliver.",
            direction="out",
            initiative="us",
            transport="https",
            trigger="dispatcher",
            idempotency=Idempotency(mode="refuse", source="queue_row_id"),
            completion="immediate",
            codec="json",
            test_action="Send one real message to an address you type.",
            # An ESP is built for volume and this is one call per bill. 600 a
            # minute puts the largest tenant this product models — 40,000
            # accounts, the top of T5 — through in about an hour. The mailbox
            # connectors' thirty would take a day and a half.
            rate_limit_per_minute=600,
            test_needs_recipient=True,
        ),
        #: ⚠ **NOT A SECOND `test()`, AND THE DISTINCTION IS `BR-INT-019`'S
        #: OWN.** *Does the key parse* is the mistake the design underlines
        #: twice; `test()` therefore sends one REAL message and stays that way.
        #: This asks a different question a clerk actually has — *is the key we
        #: were given any good* — without putting mail in anybody's inbox, which
        #: is what makes it safe to run during set-up and after a rotation.
        #:
        #: ⚠ **A `200` FROM `/v3/scopes` IS NOT A PASS.** A read-only key
        #: answers `200` with a list that does not contain `mail.send`, and the
        #: adapter checks the list rather than the status — a check whose false
        #: pass is the only outcome it would ever see is law 7's *structurally
        #: incapable of failing*.
        Operation(
            name="validate_credentials",
            label="Check the key",
            description="We ask the service whether this key can send mail.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="inline",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            # A person is waiting on a settings screen; `C15`'s budget, not a job.
            latency_budget_ms=1000,
            # Nothing of ours is written — the answer is SHOWN (`C16`).
            result_disposition="offer",
            # A clerk presses this during set-up and after a rotation. Sixty a
            # minute is a person pressing a button; anything more is a script.
            rate_limit_per_minute=60,
        ),
        #: ⚠ **THE LONG POLE, AND IT IS THE UTILITY'S CLOCK RATHER THAN OURS.**
        #: PO, 2026-09-17, on why the emails must say they come from the
        #: utility: *"whoever runs that utility's website must add three short
        #: records to their domain settings. It is a ten-minute job for them;
        #: getting it asked for, approved and done usually takes ONE TO THREE
        #: WEEKS … that wait is theirs and we cannot shorten it, and everything
        #: we build is finished long before those records are."*
        #:
        #: ⚠ **EVERY VALUE IN THE ANSWER COMES OUT OF SENDGRID'S OWN RESPONSE.**
        #: The `em1234` prefix and the DKIM selectors differ per ACCOUNT and
        #: cannot be derived. A composed record publishes cleanly, verifies
        #: never, and costs that one-to-three-week cycle a second time —
        #: which is why `DnsRecord.source` exists and why the only line we
        #: compose (DMARC, which no ESP issues) is marked `ours` on the wire.
        #:
        #: ⚠ **THE KEY NEEDS `whitelabel.read` AND THE ACCOUNT WAS SET UP WITH
        #: `mail.send` ALONE** — `DEF-INT-5649`. A key without it answers `403`,
        #: which reaches a clerk as *The service refused the key.* with
        #: SendGrid's own words underneath. It is a change on SendGrid's screen,
        #: not here.
        Operation(
            name="check_domain_verified",
            label="Check the sending domain",
            description="We ask the service which domain records are published.",
            direction="in",
            initiative="us",
            transport="https",
            trigger="inline",
            idempotency=Idempotency(mode="reconcile", source="none"),
            completion="immediate",
            codec="json",
            latency_budget_ms=1000,
            result_disposition="offer",
            # A panel a person is looking at, plus a periodic re-check while the
            # IT team works. Sixty a minute is generous for both.
            rate_limit_per_minute=60,
        ),
        #: ⚠ **THE DOOR IS DECLARED AND ITS VERIFICATION IS NOT — `DEF-INT-5630`,
        #: OPEN, AND THIS IS THE DELIBERATE HALF-SHIP.**
        #:
        #: SendGrid's Event Webhook presents NO credential: it signs the body
        #: and sends `X-Twilio-Email-Event-Webhook-Signature` plus
        #: `…-Timestamp`. `registry.INBOUND_VERIFICATIONS` has a `signature`
        #: style that fits the SHAPE exactly — but
        #: `registry.SIGNATURE_ALGORITHMS` is `("hmac_sha256",)`, **symmetric
        #: only**, and SendGrid's own set-up screen calls what it issues a
        #: *Verification Key*, which is the word for a PUBLIC key. If it is
        #: ECDSA, verifying proves the sender holds a private half we have
        #: never seen; the public half identifies a connection and proves
        #: possession of nothing, so `serve.resolve_caller`'s *identify the
        #: caller by the blind index of what it proved knowledge of* stops
        #: being true. That is a different security statement, it is
        #: unanswered by the PO, and **it is not settled by widening a signed
        #: vocabulary from inside a manifest.**
        #:
        #: ⚠ **SO NOTHING IS DECLARED, AND THE FAIL-CLOSED DIRECTION IS WHY
        #: THAT IS SAFE RATHER THAN MERELY QUIET.** Absent means
        #: `presented_key`, which reads a bearer token out of `Authorization`
        #: — a header SendGrid does not send — so the door answers `None` and
        #: **refuses**. A real SendGrid call cannot be admitted by accident;
        #: it can only be refused until `DEF-INT-5630` is answered. Declaring
        #: `style="signature", algorithm="hmac_sha256"` instead would have
        #: loaded cleanly, drawn perfectly, and been a control wired to the
        #: wrong maths (hard-won law 2).
        #:
        #: ⚠ **A HOLD WITH A TEST ON IT**:
        #: `test_cr115__sendgrid_declares_no_inbound_verification_while_5630_is_open`
        #: fails the day this manifest declares one OR the day an asymmetric
        #: algorithm joins `SIGNATURE_ALGORITHMS`, so the question is asked
        #: rather than assumed.
        Operation(
            name="receive_feedback",
            label="Delivery feedback",
            description="They tell us what was delivered and what bounced.",
            direction="in",
            initiative="them",
            transport="https",
            trigger="webhook",
            # `sg_event_id` is SendGrid's own unique id per event. The DEDUPE
            # key is independent of how the caller is VERIFIED: the door needs
            # both, and declaring this one costs nothing while 5630 is open.
            idempotency=Idempotency(
                mode="refuse", source="provider_event_id", key_field="sg_event_id"
            ),
            completion="immediate",
            codec="json",
            respond_after="persist",
            envelope_status={"ok": 200, "duplicate": 200, "refused": 401},
            # INWARD — what we allow them, and the half `serve.check_rate_limit`
            # enforces. A bill run of 40,000 messages returns 40,000 receipts
            # in a burst; sixty a minute would refuse them for eleven hours.
            # ⚠ The duplicate guard on this door STAYS: `provider_event_id`
            # is *have I already been handed this exact event*, a fact about
            # the door, not the money-duplicate judgment the PO moved.
            rate_limit_per_minute=600,
        ),
    ),
)

# ═══════════════════════════════════════════════════════════════════════════
# WHAT THIS MANIFEST CANNOT SAY, AND WHY NOTHING WAS ADDED TO LET IT
# ═══════════════════════════════════════════════════════════════════════════
#
# `CR-115-BRC05` named five provider differences that are REAL and that the
# adapter will need. None of them is expressible as manifest data today, and
# **the registry's own history is the argument for leaving them here rather
# than inventing fields for them**: `Field.default` sat in `registry.py` for a
# day claiming a reader it did not have (`DEF-INT-5595`), and that is exactly
# what let nineteen unusable values go unnoticed (`DEF-INT-5590`). A declared
# value nothing reads is not neutral — it is a fact the next lane will build on.
#
#   * **202, not 200**, and the accepted id comes back in the `X-Message-Id`
#     RESPONSE header. `Operation.envelope_status` is the INBOUND door's reply
#     map (`BR-INT-045`) and cannot carry what a partner answers US.
#   * **Sandbox is a flag on the request** (`mail_settings.sandbox_mode`),
#     where Postmark needs a different token. The connection already carries
#     `environment`, so the adapter reads that; nothing is needed here.
#   * **30 MB per request, 1,000 personalisations per call.** There is no
#     batch-size or payload-ceiling vocabulary, and `FetchPlan` is a READ walk
#     (their window, their page size), not a send batch. ⚠ Under the
#     `CR-115-BRC05` ruling that bills travel as **secure links and not as PDF
#     attachments**, the size ceiling stops being a design constraint anyway.
#   * **Validation is `GET /v3/scopes`, and the answer must contain
#     `mail.send`.** That is the adapter's `validate()`, which is one of the
#     four methods the conformance kit fixes.
#
# These are recorded in `DEF-INT-5633` so they are counted rather than trusted
# to this comment (hard-won law 1, and hard rule 4's own lesson: a finding
# recorded only in the file you happen to be in is a finding nobody can count).
