"""Postmark — high-volume bulk sending (Email · LIVE · server token + sending domain).

BR-INT-006: the transactional ESP connected AS THE TENANT'S INTEGRATION. The
same two operations as its sibling `sendgrid` — we send, and they call us back
with delivery and bounce feedback (C28) — because the SHAPE of an ESP
relationship is the same and only the wire details differ (BR-INT-027,
BR-INT-030, BR-INT-045).

Data, not code (BR-INT-037). Read by `apps/integrations/registry.py` at
`AppConfig.ready()`; refused there, by name, if anything below is missing or
outside a closed vocabulary. Display text here is the ENGLISH fallback — the
catalogue key `integrations.provider.postmark.*` wins on screen when present, so a
translation is a catalogue line and never an edit to this file.

⚠ **A SECOND ESP IS NOT A DUPLICATE — IT IS THE SECOND HALF OF A CHOICE.**
`CR-115-BRC05`: both accounts exist today, and which one a utility sends
through is a decision per utility rather than a decision for the platform. The
two manifests are deliberately near-identical, and **every line where they
differ is a real difference on the wire** — commented as such below, so a
reader can tell a genuine divergence from a copy that drifted.

⚠ **WHAT IS THE SAME, STATED SO IT IS NOT MISTAKEN FOR AN OVERSIGHT:** both are
`we_hold_theirs` (the utility brings its own account), both are `coming_soon`
with no adapter bound, both dedupe an inbound event on the provider's own event
id, and both reply after `persist`.

⚠ **AND `we_hold_theirs` IS NOT THE SHAPE THE PO RULED FOR — `DEF-INT-5636`,
DEFERRED.** *"our account - we will provide service to utilities as platform
provider"* (2026-09-17) means OUR credential sending on every utility's behalf,
and `registry.AUTH_MODES` has no mode for it; nor could such a credential live
in `integration_credential`, which has RLS FORCED. Both ESPs therefore ship in
the tenant-credential shape that works today. See `sendgrid.py` for the whole
of it — it is one deferral, not two.
"""

from apps.integrations.registry import (
    Auth,
    Disposition,
    Field,
    Idempotency,
    InboundVerification,
    Manifest,
    Operation,
)

MANIFEST = Manifest(
    key="postmark",
    category="email",
    display_name="Postmark",
    summary="High-volume bulk sending",
    #: ⚠ **LIVE FROM 2026-09-17, BECAUSE THE HOLD EXPIRED RATHER THAN BEING
    #: LIFTED.** It fired on `registry.adapter_for()` and asserted BOTH
    #: DIRECTIONS — coming-soon for exactly as long as no adapter is bound, live
    #: for exactly as long as one is — so `adapters/email_postmark.py` and this
    #: line moved in the same commit or
    #: `test_cr115__a_connector_with_no_adapter_says_coming_soon` would have
    #: named this file. `register_adapter` refuses to bind an adapter to a
    #: coming-soon provider (`BR-INT-001`), so it cannot be half-released from
    #: either side.
    #:
    #: ⚠ **WHAT *LIVE* PROMISES HERE IS NARROWER THAN AT `sendgrid`, AND THE
    #: DIFFERENCE IS DOMAIN VERIFICATION.** A utility can connect this card,
    #: press *Test*, and have one real message leave — that much is the same.
    #: **It cannot be told which DNS records to publish**, because Postmark's
    #: `/domains` API takes an ACCOUNT token and this connector holds a SERVER
    #: token (`DEF-INT-5650`), and the account token belongs to the PLATFORM,
    #: which `AUTH_MODES` cannot express (`DEF-INT-5636`). So
    #: `check_domain_verified` is NOT DECLARED below — a card that offered it
    #: and refused every press would be `DEF-INT-4224` one operation down —
    #: and `sending_domain.py` says so on the wire, with the DMARC record,
    #: which is ours to give and needs no provider at all.
    disposition=Disposition(kind="live", phase=2),
    #: ⚠ **DIFFERENCE 1 — A NAMED HEADER, WHERE SENDGRID IS A BEARER TOKEN.**
    #: Postmark authenticates with `X-Postmark-Server-Token: <token>`. The
    #: header is NAMED here because the inbound door has to be able to read a
    #: credential position without branching on a provider key (`G77`,
    #: `BR-INT-037`), and `inbound.credential_header` refuses CLOSED — rather
    #: than guessing — when a `header` placement names none.
    #:
    #: ⚠ **DIFFERENCE 2 — THE WEBHOOK IS HTTP BASIC, SO THE INBOUND STYLE IS
    #: DECLARED WHERE SENDGRID'S CANNOT BE.** Postmark puts basic credentials
    #: in the URL WE give it, so both halves are ours to choose and the
    #: PASSWORD is a key we minted: `basic` is a TRANSPORT for that key, not a
    #: second authenticator, and the value reaches `serve.resolve_caller`
    #: exactly as a header-borne key does. This is the whole reason
    #: `VERIFY_BASIC` exists (`DEF-INT-5628`), and it needs no new maths and no
    #: new vocabulary — unlike SendGrid's signature, which is `DEF-INT-5630`
    #: and is OPEN.
    #:
    #: ⚠ **AND THE PASSWORD CANNOT BE MINTED YET — `DEF-INT-5634`, FILED, NOT
    #: DESIGNED AROUND.** `machine_auth.issue` refuses any connection whose
    #: manifest is not `they_hold_ours` (`_partner_manifest`), and this one is
    #: `we_hold_theirs` because we hold Postmark's server token. So this
    #: connector needs BOTH credentials at once, which is `DEF-INT-4118`'s open
    #: limit — one `Manifest.auth`, and a shipped `EXCLUDE` that permits one
    #: active credential per connection — reached from a second direction.
    #: **Declaring `basic` is still right**: it is a true fact about Postmark,
    #: the door already dispatches on it correctly, and the card is held, so
    #: nothing is offered that cannot be completed. What is missing is upstream
    #: of this file and is recorded where it can be counted.
    auth=Auth(
        mode="we_hold_theirs",
        placement="header",
        header="X-Postmark-Server-Token",
        inbound=InboundVerification(style="basic"),
    ),
    fields=(
        Field(
            name="base_url",
            label="Service address",
            kind="url",
            required=False,
            default="https://api.postmarkapp.com",
        ),
        #: ⚠ **DIFFERENCE 3 — *Server token*, NOT *API key*, AND THE WORD IS
        #: THE PRODUCT'S.** Postmark scopes a token to a SERVER (its unit of
        #: separation), and a clerk copying a value out of Postmark's screen is
        #: looking at something labelled *Server API token*. Calling it *API
        #: key* here would make them hunt for a thing that does not exist.
        Field(name="server_token", label="Server token", kind="secret"),
        Field(name="sending_domain", label="Sending domain", kind="host"),
        Field(name="send_from", label="Send bills from", kind="email"),
        #: ⚠ **DIFFERENCE 4 — POSTMARK PUTS A MESSAGE STREAM ON EVERY REQUEST
        #: AND SENDGRID HAS NO SUCH CONCEPT.** `outbound` is the transactional
        #: stream every Postmark server starts with; `broadcast` is the bulk
        #: one.
        #:
        #: ⚠ **`text` AND NOT `select`, AND THAT IS MEASURED RATHER THAN
        #: CASUAL.** A `select` is a CLOSED list — `registry.validate` refuses
        #: a default outside `options` and refuses a per-class value outside it
        #: too — and a Postmark customer may create streams of their own with
        #: ids we cannot know. A closed list would refuse a utility its own
        #: stream, which is a field that cannot hold the one value the customer
        #: has (`DEF-INT-5589`'s shape, one field along).
        #:
        #: ⚠ **`per_class` IS DELIBERATELY EMPTY, AND THIS IS THE ONE PLACE
        #: THIS CONNECTOR WAS EXPECTED TO USE IT.** `Field.per_class` exists
        #: BECAUSE of Postmark's streams — `registry.py` says so in its own
        #: comment — so leaving it empty needs the reason written down:
        #: **the axis does not line up.** `per_class` keys on
        #: `notification_classes()`, which is `catalogs.CR_CATEGORIES` —
        #: `billing · collections · payments · service_field ·
        #: account_lifecycle`, five BUSINESS AREAS. Postmark splits
        #: TRANSACTIONAL from BULK. Four of the five classes are wholly
        #: transactional, and the fifth is not one thing: `service_field` holds
        #: `service_outage_notice` (*"Outage and broadcast messages"*, which is
        #: the broadcast case) beside `service_appointment`,
        #: `service_work_completed` and `service_door_hanger`, which are
        #: per-recipient transactional mail. So **no value is right for the
        #: class**: `broadcast` would put appointment reminders on a stream
        #: that carries unsubscribe handling and bulk filtering, and a missed
        #: appointment reminder is a real customer harm. The split Postmark
        #: needs is per TEMPLATE, not per CATEGORY. Filed as `DEF-INT-5635`
        #: rather than approximated here — and the outage flow it would matter
        #: for is not built (*"the wording is ready; sending is not switched on
        #: yet"*), so the safe default costs nothing today.
        Field(
            name="message_stream",
            label="Message stream",
            kind="text",
            required=False,
            default="outbound",
        ),
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
            # ⚠ SAME CEILING AS `sendgrid`, AND THE 500-PER-BATCH FIGURE DOES
            # NOT CHANGE IT. Postmark's batch endpoint takes 500 messages a
            # call — but `source="queue_row_id"` is *per-item queue row id*,
            # which is ONE CALL PER MESSAGE by construction, so a batch size
            # describes an endpoint this operation does not use. Making the
            # send batched is a different idempotency key and a different
            # operation shape; it is `DEF-INT-5633` and not a number quietly
            # written here.
            rate_limit_per_minute=600,
            test_needs_recipient=True,
        ),
        #: ⚠ **NOT A SECOND `test()` (`BR-INT-019`).** `test()` sends one REAL
        #: message and stays that way; this answers *is the token we were given
        #: any good* without putting mail in anybody's inbox, which is what
        #: makes it safe during set-up and after a rotation.
        #:
        #: ⚠ **AND IT IS A WEAKER QUESTION THAN SENDGRID'S, WHICH IS A REAL
        #: DIFFERENCE AND NOT A GAP.** SendGrid has SCOPES, so `GET /v3/scopes`
        #: can be asked *may this key send mail* and the adapter reads the list
        #: rather than the status. Postmark has none: a Server token either
        #: names a Server or it does not, and `GET /v3/server` is the whole of
        #: what can be asked. Pretending otherwise would be a check whose only
        #: possible outcome is a pass (hard-won law 7).
        Operation(
            name="validate_credentials",
            label="Check the token",
            description="We ask the service whether this token names a server.",
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
        #: ⚠ **THERE IS NO `check_domain_verified` HERE AND ITS ABSENCE IS THE
        #: DELIBERATE HALF-SHIP — `DEF-INT-5650`.** Postmark's Domains API is
        #: gated behind an ACCOUNT token; this connector holds a SERVER token,
        #: and a connector holds ONE credential (`DEF-INT-4118`, reached from a
        #: third direction). The account token is also a PLATFORM credential —
        #: PO 2026-09-17, *"our account - we will provide service to utilities
        #: as platform provider"* — and `AUTH_MODES` has no mode for a
        #: credential belonging to no tenant (`DEF-INT-5636`).
        #:
        #: **Declaring it anyway would be a control wired to a door we cannot
        #: open** (hard-won law 2): the card would offer a check, every press
        #: would answer `401`, and the sentence a clerk read would be *The
        #: service refused the key* about a key that is perfectly good. The
        #: absence is served with its reason instead, and the DMARC record —
        #: which no ESP issues and which we can therefore always give — goes out
        #: on day one regardless.
        Operation(
            name="receive_feedback",
            label="Delivery feedback",
            description="They tell us what was delivered and what bounced.",
            direction="in",
            initiative="them",
            transport="https",
            trigger="webhook",
            # ⚠ **DIFFERENCE 5 — `MessageID`, WHERE SENDGRID SENDS
            # `sg_event_id`.** Postmark's webhook body names the message it is
            # about; the door reads ONE declared name rather than guessing at
            # three (`BR-INT-037`), and `inbound.py` fails closed and names
            # this field when it is absent.
            idempotency=Idempotency(
                mode="refuse", source="provider_event_id", key_field="MessageID"
            ),
            completion="immediate",
            codec="json",
            respond_after="persist",
            envelope_status={"ok": 200, "duplicate": 200, "refused": 401},
            # INWARD — what we allow them, and the half `serve.check_rate_limit`
            # enforces. A bill run of 40,000 messages returns 40,000 receipts
            # in a burst; sixty a minute would refuse them for eleven hours.
            rate_limit_per_minute=600,
        ),
    ),
)

# ═══════════════════════════════════════════════════════════════════════════
# WHAT THIS MANIFEST CANNOT SAY — the Postmark half of `sendgrid`'s list
# ═══════════════════════════════════════════════════════════════════════════
#
# Recorded here and counted in `DEF-INT-5633`, for the reason `registry.py`
# learned the hard way (`DEF-INT-5595`, `DEF-INT-5590`): **a declared value
# nothing reads is not neutral, it is a fact the next lane will build on.** No
# vocabulary was added to hold any of these.
#
#   * **200, not SendGrid's 202**, and the accepted id comes back as
#     `MessageID` in the response BODY rather than in a header.
#     `Operation.envelope_status` is the inbound door's reply map
#     (`BR-INT-045`) and cannot carry what a partner answers US.
#   * **Sandbox is a SEPARATE SERVER or a test token — never a flag on the
#     request**, which is the sharpest operational difference between the two.
#     ⚠ **This one needs nothing new and the existing model fits it exactly:** a
#     connection is keyed on `(tenant, provider_key, environment)`, so a
#     utility's sandbox is a second connection holding the test token, and the
#     `environment` it already carries is the whole answer. SendGrid's flag is
#     the case that does NOT fit the key, and it is the adapter's to set.
#   * **10 MB per message.** ⚠ Moot: `CR-115-BRC05` rules that bills travel as
#     **secure links, not PDF attachments**, so the ceiling stops being a
#     design constraint. Written down because it was a stated worry, and a
#     worry that has been answered should be recorded as answered rather than
#     left to be raised again.
#   * **500 per batch** — see `send_message` above; unusable while the send is
#     keyed per queue row.
#   * **Validation is `GET /v3/server`**, and it doubles as the *does this
#     token point at a real server* check. That is the adapter's `validate()`.
#   * **A Server must exist before a domain can be verified.** This is an
#     ORDERING constraint on set-up, not a field: it belongs to domain
#     verification, which `CR-115-BRC05` holds out as its own wave.
