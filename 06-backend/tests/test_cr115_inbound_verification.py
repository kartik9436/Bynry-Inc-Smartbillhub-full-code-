# ── Trace ──────────────────────────────────────────────
# Story:    CR-115-BRC05 lane 4 — the inbound door's THREE verification styles
#           (`registry.INBOUND_VERIFICATIONS`) and a field that varies by the
#           kind of message (`registry.Field.per_class`).
# Defects:  DEF-INT-5628 (the door could authenticate only a credential
#           presented in a header, so a signed webhook could be accepted only
#           by turning authentication off).
# Rules:    BR-INT-021 (authenticate before the body is trusted) · BR-INT-030
#           (the reply is a declared position) · BR-INT-037 / G77 (data, never
#           a branch on a provider key) · BR-INT-044 (one refusal, revealing
#           nothing) · BR-INT-003 (a secret lives in payload_enc) ·
#           CLAUDE.md hard rule 1 · law 3 (fail closed) · law 7 (ask what
#           would make this check pass wrongly)
# Impacts:  apps/integrations/registry.py · inbound.py · inbound_api.py ·
#           webhook_secrets.py · seams/notifications.py
# ───────────────────────────────────────────────────────
"""Three ways in, and the three ways a signature check is usually got wrong.

⚠ **THE FOUR CASES THIS FILE EXISTS FOR ARE THE REFUSALS, NOT THE SUCCESS.**
A signature verifier that accepts a correct signature is easy; the ones that
have shipped broken accept a MISSING signature, accept when no secret is
stored, or accept a call captured last year. Each has its own case here, and
each is named in `inbound.signature_verified_secret`'s own docstring as a
*what would make this check pass wrongly* (hard-won law 7, habit 2).

⚠ **THE RED PROOF IS A SABOTAGE RUN AND ITS TRANSCRIPT IS IN
`12-governance/02-decision-log.md` FOR 2026-09-17.** Each false pass is put back
into the verifier one at a time and the matching case here is shown to FAIL,
**through the real view** rather than through a convenient entry point — which is
`DEF-GOV-3733`'s rule, and the reason it is a rule is that two gates were once
announced green while the suite reported they had no callable `run` at all.

⚠ **THREE OF THE FOUR WENT RED. THE FOURTH STAYED GREEN AND THAT IS THE MOST
USEFUL LINE IN THE TRANSCRIPT.** The no-secret false pass is **unreachable**:
`verify()` answers what the caller proved knowledge of rather than *yes*, so an
invented answer hashes to no credential and `resolve_caller` refuses it anyway.
`test_with_no_secret_stored…` and `test_with_no_connection_at_all…` therefore pin
a PROPERTY that two mechanisms hold, and they cannot be made red by breaking
either one alone. Said here so nobody deletes them as untested, and so nobody
records a red proof that did not happen — the first attempt at that sabotage was
itself defective and printed `2 passed` where `2 failed` was expected.

⚠ **THE DOOR CASES GO THROUGH THE REAL VIEW AT THE REAL ADDRESS**, for the
reason `test_us_int_044_inbound_door.py` gives at length: the header name, the
tenant context and the status number are all decided between the wire and the
door, and a test calling `inbound.receive()` directly would assert the door and
prove nothing about the four things around it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest
from django.utils import timezone

from apps.integrations import inbound, models, services, webhook_secrets
from apps.integrations.registry import (
    REGISTRY,
    SIGNATURE_ALGORITHMS,
    Auth,
    Field,
    Idempotency,
    InboundVerification,
    Manifest,
    ManifestError,
    Operation,
    Registry,
    notification_classes,
)
from apps.integrations.runners import serve
from apps.integrations.seams import notifications as notifications_seam
from core import crypto
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SIGNED = "sig_connector"
SECRET_FIELD = "verification_key"
VERIFICATION_KEY = "sbh_verify_4Qd8_do_not_reuse_this_value"
SIG_HEADER = "X-Twilio-Email-Event-Webhook-Signature"
STAMP_HEADER = "X-Twilio-Email-Event-Webhook-Timestamp"
MAX_SKEW = 300

BASIC = "basic_connector"
BASIC_PASSWORD = "sbh_basic_7HhX_do_not_reuse_this_value"
BASIC_USER = "smartbillhub"

EVENT_ID = "EVT-90210"


# ══════════════════════════════════════════════════════════════════════════
# Two fixture connectors — one signs, one presents Basic
# ══════════════════════════════════════════════════════════════════════════


def _feedback_operation(name: str = "delivery_events") -> Operation:
    """One `in · them` operation: the vendor posts delivery events at us."""
    return Operation(
        name=name,
        label="Delivery events",
        direction="in",
        initiative="them",
        transport="https",
        trigger="webhook",
        idempotency=Idempotency(mode="refuse", source="provider_event_id", key_field="sg_event_id"),
        completion="immediate",
        respond_after="dedupe",
        envelope_status={"ok": 200, "duplicate": 409, "refused": 401},
        rate_limit_per_minute=600,
        test_action=None,
    )


def _signing_manifest(**overrides) -> Manifest:
    verification = dict(
        style="signature",
        signature_header=SIG_HEADER,
        timestamp_header=STAMP_HEADER,
        secret_field=SECRET_FIELD,
        algorithm="hmac_sha256",
        signed_payload="timestamp_body",
        encoding="base64",
        max_skew_seconds=MAX_SKEW,
    )
    verification.update(overrides)
    return Manifest(
        key=SIGNED,
        category="email",
        display_name="A connector that signs",
        summary="It signs the body rather than presenting a key.",
        auth=Auth(
            mode="we_hold_theirs", placement="header", inbound=InboundVerification(**verification)
        ),
        fields=(Field(name=SECRET_FIELD, label="Verification key", kind="secret"),),
        operations=(_feedback_operation(),),
    )


def _basic_manifest() -> Manifest:
    return Manifest(
        key=BASIC,
        category="email",
        display_name="A connector that uses Basic",
        summary="Its webhook credentials sit in the URL we gave it.",
        auth=Auth(
            mode="we_hold_theirs", placement="header", inbound=InboundVerification(style="basic")
        ),
        fields=(),
        operations=(_feedback_operation(),),
    )


@pytest.fixture()
def registered():
    """Put the fixture manifests in the registry THE PRODUCT READS, and take
    them out again.

    ⚠ **IT HAS TO BE `REGISTRY` AND NOT A PRIVATE `Registry()`.** The view
    holds the global by name, so a case that drives the real address cannot
    substitute one. `Registry.unregister` exists for exactly this and drops one
    manifest; `clear()` would take the other twenty-nine with it and leave
    every sibling case in the session running against an empty registry.
    """
    REGISTRY.register(_signing_manifest())
    REGISTRY.register(_basic_manifest())
    try:
        yield
    finally:
        REGISTRY.unregister(SIGNED)
        REGISTRY.unregister(BASIC)


def _connect(tenant, actor, provider, *, secret_payload, blind_from, operation="delivery_events"):
    """A connection with a credential whose BLIND INDEX is the thing the door
    will hand `resolve_caller`.

    ⚠ **THAT IS A REAL CONSTRAINT ON THE CONNECTOR LANE AND IT IS WRITTEN HERE
    BECAUSE NOTHING ELSE CAN SAY IT.** For a `signature` connector the blind
    index must be computed over the VERIFICATION KEY, because that is what the
    door proves knowledge of and therefore what identifies the credential row.
    Index some other secret and every correctly signed call is refused — which
    looks exactly like a wrong key, in both directions, with no test anywhere
    noticing (`machine_auth.py`'s own guard-list line records the same trap).
    """
    row = models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=provider,
        label=provider,
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_WORKING,
        enabled=True,
        cadence=models.CADENCE_MANUAL,
        config={},
    )
    services.record_credential(
        actor=actor,
        connection=row,
        payload=secret_payload,
        masked_hint="••••4Qd8",
        blind_index=crypto.blind_index(blind_from, context=serve.ISSUED_KEY_BLIND_INDEX_CONTEXT),
        scope=[operation],
    )
    return row


@pytest.fixture()
def signing_connection(brazos, dana, registered):
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        return _connect(
            brazos,
            dana,
            SIGNED,
            secret_payload=json.dumps({SECRET_FIELD: VERIFICATION_KEY}),
            blind_from=VERIFICATION_KEY,
        )


@pytest.fixture()
def basic_connection(brazos, dana, registered):
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        return _connect(
            brazos,
            dana,
            BASIC,
            secret_payload=json.dumps({"password": BASIC_PASSWORD}),
            blind_from=BASIC_PASSWORD,
        )


def _body(event_id: str = EVENT_ID) -> bytes:
    return json.dumps({"sg_event_id": event_id, "event": "delivered"}).encode()


def _sign(body: bytes, stamp: int, secret: str = VERIFICATION_KEY) -> str:
    digest = hmac.new(secret.encode(), str(stamp).encode() + body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _post(tenant, provider, *, body=None, headers=None, operation="delivery_events"):
    """One call, through the REAL view at the REAL address."""
    from rest_framework.test import APIRequestFactory

    from apps.integrations import inbound_api
    from core import tenancy as core_tenancy

    payload = _body() if body is None else body
    factory = APIRequestFactory()
    request = factory.post(
        f"/api/{tenant.subdomain}/integrations/inbound/{provider}/{operation}",
        data=payload,
        content_type="application/json",
        REMOTE_ADDR="198.51.100.12",
    )
    for name, value in (headers or {}).items():
        request.META["HTTP_" + name.upper().replace("-", "_")] = value
    request.tenant_id = tenant.id
    with core_tenancy.tenant_context(tenant.id):
        return inbound_api.inbound_door(request, key=provider, operation=operation)


def _bytes(response):
    return response.content if hasattr(response, "content") else response.rendered_content


def _signed_headers(body: bytes, *, stamp=None, signature=None):
    stamp = int(timezone.now().timestamp()) if stamp is None else stamp
    return {
        SIG_HEADER: _sign(body, stamp) if signature is None else signature,
        STAMP_HEADER: str(stamp),
    }


# ══════════════════════════════════════════════════════════════════════════
# THE DOOR · a signature that verifies
# ══════════════════════════════════════════════════════════════════════════


def test_a_correctly_signed_webhook_is_admitted_and_lands(brazos, signing_connection):
    """The whole point: a vendor that presents NO credential gets in on its
    signature alone, and the delivery is on disk."""
    body = _body()
    response = _post(brazos, SIGNED, body=body, headers=_signed_headers(body))
    assert response.status_code == 200
    envelope = json.loads(_bytes(response))
    assert envelope["status"] == "ok"
    assert [one["state"] for one in envelope["items"]] == ["landed"]


def test_a_replayed_signed_webhook_answers_duplicate_not_a_refusal(brazos, signing_connection):
    """`BR-INT-045` — a repeat is the manifest's `duplicate` number, and the
    signature is checked again on the way in rather than being trusted because
    we have seen the id before."""
    body = _body()
    first = _post(brazos, SIGNED, body=body, headers=_signed_headers(body))
    second = _post(brazos, SIGNED, body=body, headers=_signed_headers(body))
    assert first.status_code == 200
    assert second.status_code == 409
    assert json.loads(_bytes(second))["status"] == "duplicate"


# ══════════════════════════════════════════════════════════════════════════
# THE DOOR · the three false passes, each proved red before it was trusted
# ══════════════════════════════════════════════════════════════════════════


def test_a_missing_signature_is_refused(brazos, signing_connection):
    """**THE CLASSIC FALSE PASS.** `None == None` is true and an empty
    presented digest compared against an empty computed one is true, so a
    verifier that forgets to DEMAND a signature admits every caller that sends
    none. Nothing else in this suite would notice."""
    body = _body()
    stamp = int(timezone.now().timestamp())
    response = _post(brazos, SIGNED, body=body, headers={STAMP_HEADER: str(stamp)})
    assert response.status_code == 401
    assert json.loads(_bytes(response))["error"] == serve.REFUSAL_SENTENCE


def test_a_wrong_signature_is_refused(brazos, signing_connection):
    """A digest made with somebody else's key."""
    body = _body()
    stamp = int(timezone.now().timestamp())
    response = _post(
        brazos,
        SIGNED,
        body=body,
        headers={SIG_HEADER: _sign(body, stamp, secret="not-the-key"), STAMP_HEADER: str(stamp)},
    )
    assert response.status_code == 401


def test_a_signature_over_a_different_body_is_refused(brazos, signing_connection):
    """The signature is over the BYTES. A correct digest for yesterday's
    payload does not admit today's."""
    signed_for = _body("EVT-00001")
    stamp = int(timezone.now().timestamp())
    response = _post(
        brazos,
        SIGNED,
        body=_body("EVT-99999"),
        headers={SIG_HEADER: _sign(signed_for, stamp), STAMP_HEADER: str(stamp)},
    )
    assert response.status_code == 401


def test_a_stale_timestamp_is_refused_even_though_the_signature_is_perfect(
    brazos, signing_connection
):
    """**THE REPLAY.** This body and this digest verified correctly when they
    were sent; captured and re-sent an hour later they still verify, because an
    HMAC has no clock in it. `max_skew_seconds` is the clock, and without it
    one captured call is a permanent key."""
    body = _body()
    stale = int(timezone.now().timestamp()) - (MAX_SKEW + 60)
    response = _post(brazos, SIGNED, body=body, headers=_signed_headers(body, stamp=stale))
    assert response.status_code == 401


def test_a_timestamp_from_the_future_is_refused_too(brazos, signing_connection):
    """`abs()`, not `now - sent`. A caller that dates its replay next year would
    otherwise buy itself an unlimited window."""
    body = _body()
    ahead = int(timezone.now().timestamp()) + (MAX_SKEW + 60)
    response = _post(brazos, SIGNED, body=body, headers=_signed_headers(body, stamp=ahead))
    assert response.status_code == 401


def test_a_missing_timestamp_is_refused(brazos, signing_connection):
    """No timestamp is no window, and no window is a permanent key."""
    body = _body()
    stamp = int(timezone.now().timestamp())
    response = _post(brazos, SIGNED, body=body, headers={SIG_HEADER: _sign(body, stamp)})
    assert response.status_code == 401


def test_rubbish_in_the_signature_header_is_a_refusal_and_not_a_500(brazos, signing_connection):
    """A base64 decode that raises must be a refusal. A 500 would tell a caller
    it had found something, and would page somebody every time a vendor
    misconfigured a header."""
    body = _body()
    stamp = int(timezone.now().timestamp())
    response = _post(
        brazos,
        SIGNED,
        body=body,
        headers={SIG_HEADER: "!!!not base64!!!", STAMP_HEADER: str(stamp)},
    )
    assert response.status_code == 401


def test_with_no_secret_stored_a_perfect_signature_is_still_refused(brazos, dana, registered):
    """**FAIL CLOSED.** A connector half set up has no verification key, and
    *nothing to check against* must never read as *this one needs no checking*
    (hard-won law 3). There is a connection and a credential here — what is
    missing is the one named value."""
    with tenant_ctx(brazos):
        _connect(
            brazos,
            dana,
            SIGNED,
            secret_payload=json.dumps({"some_other_field": "x"}),
            blind_from=VERIFICATION_KEY,
        )
    body = _body()
    response = _post(brazos, SIGNED, body=body, headers=_signed_headers(body))
    assert response.status_code == 401


def test_with_no_connection_at_all_a_perfect_signature_is_refused(brazos, registered):
    """Nobody has connected this connector in this utility. The signature is
    computed from a key we never stored, so there is nothing to verify against
    and the answer is the same five words."""
    body = _body()
    response = _post(brazos, SIGNED, body=body, headers=_signed_headers(body))
    assert response.status_code == 401


def test_a_signature_valid_at_one_utility_does_not_open_another(
    brazos, lonestar, dana, signing_connection
):
    """CLAUDE.md hard rule 1. Brazos Bend's verification key is not visible
    under Lone Star Ridge's tenant context, so the same call refuses there."""
    body = _body()
    headers = _signed_headers(body)
    assert _post(brazos, SIGNED, body=body, headers=headers).status_code == 200
    assert _post(lonestar, SIGNED, body=body, headers=headers).status_code == 401


def test_every_refusal_is_the_same_bytes(brazos, signing_connection):
    """`BR-INT-044` — a missing signature, a wrong one and a stale one must be
    indistinguishable. Compared byte-for-byte, because a caller holding a
    stolen key reads any difference as a map."""
    body = _body()
    stamp = int(timezone.now().timestamp())
    missing = _post(brazos, SIGNED, body=body, headers={STAMP_HEADER: str(stamp)})
    wrong = _post(
        brazos,
        SIGNED,
        body=body,
        headers={SIG_HEADER: _sign(body, stamp, secret="nope"), STAMP_HEADER: str(stamp)},
    )
    stale = _post(brazos, SIGNED, body=body, headers=_signed_headers(body, stamp=stamp - 4000))
    assert _bytes(missing) == _bytes(wrong) == _bytes(stale)
    assert missing.status_code == wrong.status_code == stale.status_code


def test_the_body_is_hashed_and_never_parsed_before_authentication(
    brazos, signing_connection, monkeypatch
):
    """`BR-INT-021` — the rule is that an unauthenticated caller must not make
    us PARSE arbitrary input, and a signed webhook now hands the bytes to the
    verifier before anybody is let in.

    ⚠ **ASSERTS THE MECHANISM AND NOT A SYMPTOM.** Sending broken JSON proves
    nothing here, because `_parsed` swallows broken JSON on purpose — the
    mistake `test_us_int_044_inbound_door.py` records against its own TC-4. So
    the parser is replaced by a RECORDER and the recording has to be empty on a
    refused call: hashing is fixed work on any input and is not a parse.
    """
    seen: list[bytes] = []
    original = inbound._parsed

    def recording(raw_body):
        seen.append(raw_body)
        return original(raw_body)

    monkeypatch.setattr(inbound, "_parsed", recording)
    body = b'{"sg_event_id": "EVT-1"}'
    refused = _post(brazos, SIGNED, body=body, headers={SIG_HEADER: "AAAA", STAMP_HEADER: "1"})
    assert refused.status_code == 401
    assert seen == []
    # …and the same bytes ARE parsed once the caller is in, so the assertion
    # above is about the ORDER and not about a parser that never runs.
    _post(brazos, SIGNED, body=body, headers=_signed_headers(body))
    assert seen == [body]


# ══════════════════════════════════════════════════════════════════════════
# THE DOOR · HTTP Basic
# ══════════════════════════════════════════════════════════════════════════


def _basic(user: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def test_basic_credentials_in_the_url_are_admitted(brazos, basic_connection):
    response = _post(brazos, BASIC, headers={"Authorization": _basic(BASIC_USER, BASIC_PASSWORD)})
    assert response.status_code == 200
    assert json.loads(_bytes(response))["status"] == "ok"


def test_the_username_is_a_label_and_the_password_is_the_credential(brazos, basic_connection):
    """Any username with the right password gets in, which is the design and
    is stated so that nobody later "hardens" it by comparing the username: the
    entropy is all in the password, and a second comparison would refuse in a
    way nothing could explain to a clerk."""
    response = _post(brazos, BASIC, headers={"Authorization": _basic("anything", BASIC_PASSWORD)})
    assert response.status_code == 200


def test_a_wrong_basic_password_is_refused(brazos, basic_connection):
    response = _post(brazos, BASIC, headers={"Authorization": _basic(BASIC_USER, "wrong")})
    assert response.status_code == 401


def test_a_missing_authorization_header_is_refused(brazos, basic_connection):
    assert _post(brazos, BASIC).status_code == 401


def test_a_bearer_token_does_not_satisfy_a_basic_door(brazos, basic_connection):
    """The scheme is part of the credential's address. A door that accepted any
    `Authorization` header would accept a token meant for something else."""
    response = _post(brazos, BASIC, headers={"Authorization": f"Bearer {BASIC_PASSWORD}"})
    assert response.status_code == 401


def test_basic_rubbish_is_a_refusal_and_not_a_500(brazos, basic_connection):
    for offered in ("Basic !!!!", "Basic " + base64.b64encode(b"no-colon-here").decode(), "Basic "):
        assert _post(brazos, BASIC, headers={"Authorization": offered}).status_code == 401


# ══════════════════════════════════════════════════════════════════════════
# THE REGISTRY · every refusal at LOAD, by name
# ══════════════════════════════════════════════════════════════════════════


def _refuses(manifest, *words):
    registry = Registry()
    with pytest.raises(ManifestError) as raised:
        registry.register(manifest)
    message = str(raised.value)
    for word in words:
        assert word in message, message
    return message


def test_an_explicit_presented_key_is_refused_as_a_second_spelling():
    _refuses(_signing_manifest(style="presented_key"), "presented_key", "ABSENT")


def test_a_style_outside_the_vocabulary_is_refused_by_name():
    _refuses(_signing_manifest(style="mutual_tls"), "auth.inbound.style", "mutual_tls")


def test_an_asymmetric_algorithm_is_refused_by_name():
    """The vocabulary is symmetric-only and says so; a manifest asking for
    ECDSA is refused at load rather than accepted and mis-modelled."""
    _refuses(_signing_manifest(algorithm="ecdsa_p256_sha256"), "auth.inbound.algorithm")


def test_signature_algorithms_are_symmetric_only():
    """**A HOLD WITH A TEST ON IT** (hard-won law 2). The door hands the stored
    secret to `resolve_caller` as *what the caller proved knowledge of*, which
    is true of an HMAC and false of a public key. The day somebody adds an
    asymmetric algorithm this goes RED and the identification question gets
    asked instead of assumed."""
    assert SIGNATURE_ALGORITHMS == ("hmac_sha256",)


def test_a_signature_style_naming_no_secret_field_is_refused():
    _refuses(_signing_manifest(secret_field=None), "secret_field")


def test_a_secret_field_the_manifest_does_not_declare_is_refused():
    _refuses(_signing_manifest(secret_field="nowhere"), "nowhere", "declares no such field")


def test_a_secret_field_of_a_NON_secret_kind_is_refused():
    """`BR-INT-003` — a verification key lands in the encrypted credential
    store. A `text` field would put it in the connection's own settings, where
    every selector that reads a connection can see it."""
    manifest = _signing_manifest()
    leaky = Manifest(
        key=manifest.key,
        category=manifest.category,
        display_name=manifest.display_name,
        summary=manifest.summary,
        auth=manifest.auth,
        fields=(Field(name=SECRET_FIELD, label="Verification key", kind="text"),),
        operations=manifest.operations,
    )
    _refuses(leaky, "encrypted credential store", "'text'")


def test_signing_a_timestamp_with_no_window_is_refused():
    _refuses(_signing_manifest(max_skew_seconds=None), "valid for ever")


def test_a_window_of_no_seconds_is_refused():
    _refuses(_signing_manifest(max_skew_seconds=0), "max_skew_seconds is 0")


def test_a_timestamp_header_on_a_body_only_signature_is_refused_as_dead_data():
    _refuses(
        _signing_manifest(signed_payload="body", max_skew_seconds=None),
        "timestamp_header",
        "nothing reads it",
    )


def test_a_body_only_signature_is_lawful_when_it_names_no_timestamp():
    registry = Registry()
    registry.register(
        _signing_manifest(signed_payload="body", timestamp_header=None, max_skew_seconds=None)
    )
    assert registry.require(SIGNED).auth.inbound.signed_payload == "body"


def test_a_basic_style_carrying_a_signature_knob_is_refused():
    manifest = _basic_manifest()
    wrong = Manifest(
        key=manifest.key,
        category=manifest.category,
        display_name=manifest.display_name,
        summary=manifest.summary,
        auth=Auth(
            mode="we_hold_theirs",
            placement="header",
            inbound=InboundVerification(style="basic", signature_header=SIG_HEADER),
        ),
        fields=(),
        operations=manifest.operations,
    )
    _refuses(wrong, "signature_header", "only 'signature' reads it")


def test_a_verification_on_a_connector_nobody_calls_is_refused():
    """Dead data. A manifest with no `in · them` operation has no door to
    guard, and a later lane would build on the declaration."""
    manifest = _signing_manifest()
    outbound_only = Manifest(
        key=manifest.key,
        category=manifest.category,
        display_name=manifest.display_name,
        summary=manifest.summary,
        auth=manifest.auth,
        fields=(
            Field(name=SECRET_FIELD, label="Verification key", kind="secret"),
            Field(name="base_url", label="Service address", kind="url"),
        ),
        operations=(
            Operation(
                name="send",
                label="Send",
                direction="out",
                initiative="us",
                transport="https",
                trigger="dispatcher",
                idempotency=Idempotency(mode="refuse", source="queue_row_id"),
                completion="immediate",
                rate_limit_per_minute=60,
            ),
        ),
    )
    _refuses(outbound_only, "no operation the partner calls")


def test_every_shipped_manifest_still_loads():
    """Everything in the product loads, and exactly ONE manifest declares an
    inbound verification style.

    ⚠ **THIS ASSERTED *ALL OF THEM ARE ABSENT* UNTIL 2026-09-17, WHICH WAS TRUE
    ON THE DAY THE VOCABULARY LANDED AND FOR A FEW HOURS AFTERWARDS.** The
    vocabulary was built for two named connectors (`DEF-INT-5628`), so a test
    saying *nobody uses it yet* was always going to be met by the first lane
    that did — and the useful version is not *nobody* but **exactly who, and in
    which style**. `postmark` is the declarer: its webhook is HTTP Basic, the
    password is a key we mint, and `basic` is a transport for that key rather
    than a second authenticator.

    ⚠ **`sendgrid` IS DELIBERATELY NOT ONE OF THEM AND THAT IS THE POINT OF
    LISTING THEM.** Its webhook is SIGNED, `SIGNATURE_ALGORITHMS` is symmetric
    only, and whether SendGrid's is asymmetric is `DEF-INT-5630`, OPEN. A
    connector that declared a style it cannot honour would be a control wired
    to nothing (hard-won law 2), so it declares none and the door refuses it —
    which `test_cr115_email_connectors.py` proves against SendGrid's real
    headers.
    """
    assert len(REGISTRY) >= 30
    declared = {
        manifest.key: manifest.auth.inbound.style
        for manifest in REGISTRY.all()
        if manifest.auth.inbound is not None
    }
    assert declared == {"postmark": "basic"}, declared


# ══════════════════════════════════════════════════════════════════════════
# GAP 2 · a field that varies by the KIND OF MESSAGE
# ══════════════════════════════════════════════════════════════════════════


def _stream_field(per_class, *, default="outbound", kind="select"):
    return Field(
        name="message_stream",
        label="Message stream",
        kind=kind,
        options=("outbound", "broadcast"),
        default=default,
        per_class=per_class,
    )


def _with_field(one: Field) -> Manifest:
    return Manifest(
        key="per_class_connector",
        category="email",
        display_name="A connector whose stream varies",
        summary="Transactional mail and bulk mail leave on different streams.",
        auth=Auth(mode="we_hold_theirs", placement="header"),
        fields=(one, Field(name="base_url", label="Service address", kind="url")),
        operations=(
            Operation(
                name="send",
                label="Send",
                direction="out",
                initiative="us",
                transport="https",
                trigger="dispatcher",
                idempotency=Idempotency(mode="refuse", source="queue_row_id"),
                completion="immediate",
                rate_limit_per_minute=60,
            ),
        ),
    )


def test_the_classes_are_notifications_own_list_and_not_a_second_one():
    """One list. `registry.notification_classes()` reads the seam, the seam
    reads `apps.notifications.catalogs.CR_CATEGORIES`, and nothing in
    integrations holds a copy that could drift."""
    from apps.notifications import catalogs

    assert notification_classes() == tuple(catalogs.CR_CATEGORIES)
    assert notifications_seam.notification_classes() == tuple(catalogs.CR_CATEGORIES)
    assert len(notification_classes()) == 5


def test_a_value_per_class_is_declarable_and_resolves():
    one = _stream_field({"billing": "outbound", "payments": "outbound", "collections": "broadcast"})
    registry = Registry()
    registry.register(_with_field(one))
    resolved = registry.require("per_class_connector").fields[0]
    assert resolved.declared_value_for("collections") == "broadcast"
    assert resolved.declared_value_for("billing") == "outbound"
    # A class the map does not name, and an unclassified send, both fall back.
    assert resolved.declared_value_for("service_field") == "outbound"
    assert resolved.declared_value_for(None) == "outbound"


def test_a_class_this_product_does_not_have_is_refused_by_name():
    """The four names the Postmark specification uses — Security, Financial,
    Operational, Internal — are NOT this product's vocabulary, and a manifest
    reaching for one is refused with the list of what exists rather than
    silently storing a setting no sender could ever select."""
    message = _refuses(_with_field(_stream_field({"security": "outbound"})), "security")
    assert "billing" in message and "account_lifecycle" in message


def test_per_class_with_no_default_is_refused():
    message = _refuses(
        _with_field(_stream_field({"billing": "outbound"}, default="")), "no default"
    )
    assert "collections" in message  # it names the classes left with nothing


def test_a_per_class_value_outside_a_selects_options_is_refused():
    _refuses(_with_field(_stream_field({"billing": "urgent"})), "'urgent'", "not one of")


def test_a_blank_per_class_value_is_refused():
    _refuses(_with_field(_stream_field({"billing": "   "})), "blank value", "looks decided")


def test_per_class_values_on_a_secret_field_are_refused():
    secret = Field(
        name="api_key",
        label="API key",
        kind="secret",
        default="",
        per_class={"billing": "one", "payments": "two"},
    )
    _refuses(_with_field(secret), "credential in the repository")


def test_a_field_with_no_per_class_values_is_unchanged():
    """Every existing manifest. `per_class` defaults to empty, the validator
    returns at once, and `declared_value_for` is just the default."""
    plain = Field(name="host", label="Host", kind="host")
    assert plain.per_class == {}
    assert plain.declared_value_for("billing") == ""


def test_an_unreadable_class_list_refuses_rather_than_accepting_anything(monkeypatch):
    """**WHAT WOULD MAKE THIS CHECK PASS WRONGLY** (law 7, habit 2). The class
    list is read through a seam, and a seam that cannot resolve its target
    answers `()`. An unguarded `if classes and key not in classes` would then
    accept EVERY class name. The empty answer is its own refusal."""
    monkeypatch.setattr(notifications_seam, "notification_classes", lambda: ())
    _refuses(_with_field(_stream_field({"billing": "outbound"})), "could not be read")


# ══════════════════════════════════════════════════════════════════════════
# THE SEAM · where a webhook secret lives
# ══════════════════════════════════════════════════════════════════════════


def test_the_secret_seam_answers_per_connection_and_names_the_other_branch():
    assert webhook_secrets.scope_for(_signing_manifest()) == webhook_secrets.SCOPE_PER_CONNECTION
    assert webhook_secrets.SCOPE_PLATFORM in webhook_secrets.SECRET_SCOPES
    assert "platform_number_series" in webhook_secrets.__doc__


def test_the_secret_seam_reads_the_declared_field_and_nothing_else(brazos, signing_connection):
    with tenant_ctx(brazos):
        found = webhook_secrets.secret_for(_signing_manifest())
        assert found is not None
        assert found.secret == VERIFICATION_KEY
        assert found.scope == webhook_secrets.SCOPE_PER_CONNECTION
        # A manifest naming a different (declared, secret) field finds nothing.
        other = _signing_manifest(secret_field="unused")
        renamed = Manifest(
            key=other.key,
            category=other.category,
            display_name=other.display_name,
            summary=other.summary,
            auth=other.auth,
            fields=(Field(name="unused", label="Unused", kind="secret"),),
            operations=other.operations,
        )
        assert webhook_secrets.secret_for(renamed) is None


def test_the_secret_seam_answers_none_with_no_tenant_open(brazos, signing_connection):
    """No tenant, no answer — never everybody's row (hard rule 1, law 3)."""
    assert webhook_secrets.secret_for(_signing_manifest()) is None
