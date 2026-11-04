# ── Trace ──────────────────────────────────────────────
# Story:    `CR-115-BRC05` §7 — the two email connectors learn to SEND, and
#           domain verification (the Product Owner's long pole).
# Rules:    US-INT-015 (four methods and nothing else) · BR-INT-018 (a provider
#           that would not say what it accepted has not succeeded) · BR-INT-019
#           (`test()` sends one REAL message) · BR-INT-022 (a refusal is not a
#           timeout) · BR-INT-004 (no provider vocabulary escapes its adapter) ·
#           BR-NOT-1032 (PROPOSED — the six normalised outcomes) · BR-NOT-013
#           (only a feedback door may write `delivered`)
# Tests:    this file · the conformance kit, run UNCHANGED over both classes
# ───────────────────────────────────────────────────────
"""The two ESP adapters — what they send, what they say, and what they refuse.

⚠⚠ **WHAT NOT ONE CASE IN THIS FILE PROVES: THAT SENDGRID OR POSTMARK BEHAVES
THE WAY WE THINK.** Neither is reachable from this build environment; every case
runs against `esp_fixtures.py`, which is HAND-SHAPED from `CR-115-BRC05` §7's
written specification and says so first in its own docstring. If SendGrid puts
its accepted id under a different header, every case here still passes and the
product still fails on the first real bill. **Said out loud rather than left to
be discovered**, exactly as `CR-112`'s GIS lane was required to say it about the
City of Ann Arbor.

What these cases DO prove is our half: the request we build, the answer we read,
the words we refuse in, the vocabulary we do not leak, and the DNS records we
never compose.

**Every guard here was proved RED first** — the transcript is in the lane report
and each case that was hard to get red carries a note saying what the wrong
version did.
"""

from __future__ import annotations

import json

import pytest

from apps.integrations import esp_fixtures as fixtures
from apps.integrations import models as integration_models
from apps.integrations.adapters import ADAPTERS, esp_email
from apps.integrations.adapters.base import (
    PROTOCOL_METHODS,
    ConnectionView,
    feedback_normaliser,
)
from apps.integrations.adapters.email_postmark import EmailPostmarkAdapter
from apps.integrations.adapters.email_sendgrid import EmailSendgridAdapter
from apps.integrations.conformance import Fixture, failures, run_kit
from apps.integrations.registry import REGISTRY
from apps.notifications import models as notification_models
from apps.notifications import suppression
from apps.integrations.runtime import ProviderTimeout

DOMAIN = "ottumwawater.gov"
SENDER = f"billing@{DOMAIN}"
RECIPIENT = "alex@example.test"

SENDGRID_CONFIG = {
    "base_url": "https://api.sendgrid.com",
    "sending_domain": DOMAIN,
    "send_from": SENDER,
}
POSTMARK_CONFIG = {
    "base_url": "https://api.postmarkapp.com",
    "sending_domain": DOMAIN,
    "send_from": SENDER,
    "message_stream": "outbound",
}
SENDGRID_SECRETS = {"api_key": "SG.a-real-looking-key-value"}
POSTMARK_SECRETS = {"server_token": "0f3a1c88-postmark-server-token"}


def view(key: str, config: dict, environment: str = "production") -> ConnectionView:
    return ConnectionView(
        provider_key=key, environment=environment, config=config, label="Bills"
    )


def sendgrid(transport=None) -> EmailSendgridAdapter:
    return EmailSendgridAdapter(transport or fixtures.sendgrid_transport())


def postmark(transport=None) -> EmailPostmarkAdapter:
    return EmailPostmarkAdapter(transport or fixtures.postmark_transport())


# ═══════════════════════════════════════════════════════════════════════════
# THE PROTOCOL — four methods, and the kit that refuses a fifth
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("cls", "key"), [(EmailSendgridAdapter, "sendgrid"), (EmailPostmarkAdapter, "postmark")]
)
def test_cr115__an_esp_adapter_has_exactly_four_public_methods(cls, key) -> None:
    """⚠ **THE FIRST DRAFT OF THESE ADAPTERS FAILED THIS WITH SEVEN EXTRA.**

    The shared base asks a subclass seven provider questions — the auth header,
    the send shape, the accepted id, the two checks, the two domain hooks — and
    written as ordinary methods they are PUBLIC, so `dir()` saw eleven names and
    the conformance kit refuses anything but four. They are underscore-prefixed
    for exactly that reason, which is the same device `base.TOKEN_MINT_METHOD`
    already established for a `token_exchange` provider's minter.

    Proved red by renaming one hook back: `found ['_ ... ', 'auth_headers', ...]`.
    """
    public = {
        name
        for name in dir(cls)
        if not name.startswith("_") and callable(getattr(cls, name)) and name != "key"
    }
    assert public == PROTOCOL_METHODS, sorted(public)
    assert cls.key == key


def test_cr115__both_esps_are_bound_and_their_manifests_are_live() -> None:
    """Binding an adapter and making the card live are ONE act, not two.

    `register_adapter` refuses a coming-soon provider (`BR-INT-001`), so the
    product would not start if these disagreed — which is the strongest form
    this guarantee can take and the reason `DEF-INT-4224` cannot recur here.
    """
    for key, cls in (("sendgrid", EmailSendgridAdapter), ("postmark", EmailPostmarkAdapter)):
        assert ADAPTERS[key] is cls
        assert REGISTRY.adapter_for(key) is cls
        assert not REGISTRY.require(key).disposition.coming_soon


@pytest.mark.parametrize("key", ["sendgrid", "postmark"])
def test_cr115__the_conformance_kit_runs_over_both_classes_unchanged(key) -> None:
    """The kit every adapter passes, run over these two with nothing adjusted.

    ⚠ **THE KIT IS NOT EDITED AND MUST NOT BE.** The design's own sentence is
    *"if a new connector requires the suite to change, that is the signal"*. It
    asserts the four-method surface, that `validate` names bad fields without a
    network, that `test` never raises for a provider's refusal, that `execute`
    returns per-item outcomes, and — the three exits — that the credential
    reaches no sentence, no log line and no describe line.
    """
    cls = EmailSendgridAdapter if key == "sendgrid" else EmailPostmarkAdapter
    config = SENDGRID_CONFIG if key == "sendgrid" else POSTMARK_CONFIG
    secrets = SENDGRID_SECRETS if key == "sendgrid" else POSTMARK_SECRETS
    transport = (
        fixtures.sendgrid_transport() if key == "sendgrid" else fixtures.postmark_transport()
    )

    class Bound(cls):  # the REAL class; only the socket is replaced
        def __init__(self) -> None:
            super().__init__(transport)

    Bound.__name__ = cls.__name__
    fixture = Fixture(
        config=dict(config),
        good_secrets=dict(secrets),
        bad_secrets={name: "wrong-" + value for name, value in secrets.items()},
        work=({"ref": "q-1", "address": RECIPIENT, "subject": "S", "body": "B"},),
        recipient=RECIPIENT,
    )
    findings = run_kit(Bound, REGISTRY.require(key), fixture)
    assert failures(findings) == [], failures(findings)


# ═══════════════════════════════════════════════════════════════════════════
# SENDING — the request we build
# ═══════════════════════════════════════════════════════════════════════════


def test_cr115__sendgrid_sends_with_our_tracking_reference_on_the_message() -> None:
    """⚠ **`custom_args.tracking_ref` IS HOW A BOUNCE FINDS ITS QUEUE ROW.**

    Without it a feedback event arrives naming a message id we never stored and
    matches nothing — which looks exactly like a provider that is quiet, and is
    the failure mode this one line prevents.
    """
    transport = fixtures.sendgrid_transport()
    result = sendgrid(transport).execute(
        view("sendgrid", SENDGRID_CONFIG),
        SENDGRID_SECRETS,
        [{"ref": "queue-row-7", "address": RECIPIENT, "subject": "Your bill", "body": "Hello"}],
    )
    assert [one.outcome for one in result.items] == ["succeeded"]
    assert result.confirmed is True
    method, url, headers, body = transport.sent[-1]
    assert (method, url) == ("POST", "https://api.sendgrid.com/v3/mail/send")
    assert headers["Authorization"] == f"Bearer {SENDGRID_SECRETS['api_key']}"
    assert body["personalizations"][0]["custom_args"] == {"tracking_ref": "queue-row-7"}
    assert body["personalizations"][0]["to"] == [{"email": RECIPIENT}]
    assert body["from"] == {"email": SENDER}
    # Production: NO sandbox flag. The next case is the other half.
    assert "mail_settings" not in body


def test_cr115__a_sandbox_sendgrid_connection_sets_the_sandbox_flag() -> None:
    """Sandbox is a FLAG on the request at SendGrid and a SEPARATE SERVER at
    Postmark — the sharpest operational difference between the two, and the one
    the connection's existing `environment` already answers."""
    transport = fixtures.sendgrid_transport()
    sendgrid(transport).test(
        view("sendgrid", SENDGRID_CONFIG, environment="sandbox"),
        SENDGRID_SECRETS,
        recipient=RECIPIENT,
    )
    assert transport.sent[-1][3]["mail_settings"] == {"sandbox_mode": {"enable": True}}


def test_cr115__postmark_sends_with_metadata_and_a_stream_and_never_a_sandbox_flag() -> None:
    transport = fixtures.postmark_transport()
    result = postmark(transport).execute(
        view("postmark", POSTMARK_CONFIG, environment="sandbox"),
        POSTMARK_SECRETS,
        [{"ref": "queue-row-9", "address": RECIPIENT, "subject": "Your bill", "body": "Hello"}],
    )
    assert [one.outcome for one in result.items] == ["succeeded"]
    method, url, headers, body = transport.sent[-1]
    assert (method, url) == ("POST", "https://api.postmarkapp.com/email")
    assert headers["X-Postmark-Server-Token"] == POSTMARK_SECRETS["server_token"]
    assert body["Metadata"] == {"tracking_ref": "queue-row-9"}
    assert body["MessageStream"] == "outbound"
    assert body["From"] == SENDER
    # ⚠ A sandbox CONNECTION and still no flag: Postmark has no such field and
    # writing one would be a control wired to nothing.
    assert "mail_settings" not in body and "SandboxMode" not in body


def test_cr115__a_happy_status_with_no_accepted_id_is_not_a_success() -> None:
    """`BR-INT-018` — a provider that answered `202` and would not say what it
    accepted has not succeeded.

    ⚠ **THE WRONG VERSION OF THIS CHECKS ONLY THE STATUS**, and it is the
    version anybody writes first. Proved red by making `_accepted()` return
    `answer.status == self._accepted_status`: both cases below went green while
    the product would have marked a bill `sent` on no evidence at all.
    """
    def silent(method, url, headers, body, timeout_s):  # noqa: ANN001, ARG001
        return esp_email.HttpAnswer(status=202, body=None, headers={}, text="")

    result = sendgrid(silent).execute(
        view("sendgrid", SENDGRID_CONFIG),
        SENDGRID_SECRETS,
        [{"ref": "q", "address": RECIPIENT}],
    )
    assert result.items[0].outcome == "failed"

    # Postmark's own version: `200` with a non-zero `ErrorCode` and no MessageID.
    refused = postmark(fixtures.postmark_transport(message_id="", error_code=406))
    result = refused.execute(
        view("postmark", POSTMARK_CONFIG),
        POSTMARK_SECRETS,
        [{"ref": "q", "address": RECIPIENT}],
    )
    assert result.items[0].outcome == "failed"


@pytest.mark.parametrize("key", ["sendgrid", "postmark"])
def test_cr115__a_provider_refusal_is_an_answer_and_never_an_exception(key) -> None:
    """A `401` is something they SAID. `BR-INT-022`: *a timeout counts towards
    the breaker and a refusal does not*, so a refusal must not arrive as the
    exception type the breaker is keyed on."""
    adapter = (sendgrid if key == "sendgrid" else postmark)(
        fixtures.refusing_transport(401, {"errors": [{"message": "unauthorized"}]})
    )
    config = SENDGRID_CONFIG if key == "sendgrid" else POSTMARK_CONFIG
    secrets = SENDGRID_SECRETS if key == "sendgrid" else POSTMARK_SECRETS
    answer = adapter.test(view(key, config), secrets, recipient=RECIPIENT)
    assert answer.ok is False
    assert answer.sentence == esp_email.REFUSED_KEY
    assert "unauthorized" in (answer.provider_text or "")
    # And the credential is nowhere near either string (BR-INT-003).
    for secret in secrets.values():
        assert secret not in answer.sentence
        assert secret not in (answer.provider_text or "")


@pytest.mark.parametrize("key", ["sendgrid", "postmark"])
def test_cr115__a_socket_that_never_opens_is_a_timeout_and_not_a_refusal(key) -> None:
    """`DEF-INT-5599`'s distinction, one module over: *we never got in* is not
    *they said no*, and only the first may move a breaker."""
    adapter = (sendgrid if key == "sendgrid" else postmark)(fixtures.unreachable_transport())
    config = SENDGRID_CONFIG if key == "sendgrid" else POSTMARK_CONFIG
    with pytest.raises(ProviderTimeout):
        adapter.test(view(key, config), {}, recipient=RECIPIENT)


@pytest.mark.parametrize("key", ["sendgrid", "postmark"])
def test_cr115__accepted_is_never_delivered(key) -> None:
    """⚠ **`202` AND `200` MEAN ACCEPTED, AND NOTHING IN A SEND MAY SAY
    `delivered`.**

    The queue row becomes `sent`; only the feedback webhook may ever write
    `delivered` (`BR-NOT-013`). This asserts the word appears nowhere in what a
    successful SEND produces — the sentence, the detail, the provider text —
    because the way this goes wrong is a helpful-looking string, not a
    deliberate decision.
    """
    adapter = (sendgrid if key == "sendgrid" else postmark)()
    config = SENDGRID_CONFIG if key == "sendgrid" else POSTMARK_CONFIG
    secrets = SENDGRID_SECRETS if key == "sendgrid" else POSTMARK_SECRETS
    result = adapter.execute(
        view(key, config), secrets, [{"ref": "q", "address": RECIPIENT, "subject": "Your bill", "body": "x"}]
    )
    said = " ".join(
        f"{one.outcome} {one.detail} {one.provider_text}" for one in result.items
    )
    # A SUCCESSFUL send is the subject here — the item carries a subject so it
    # is not refused before dialling (DEF-NOT-10420), which would pass vacuously.
    assert [one.outcome for one in result.items] == ["succeeded"]
    assert "delivered" not in said.lower()
    tested = adapter.test(view(key, config), secrets, recipient=RECIPIENT)
    assert "delivered" not in (tested.sentence + str(tested.provider_text)).lower()


# ═══════════════════════════════════════════════════════════════════════════
# THE CREDENTIAL CHECK — a new OPERATION, not a fifth method
# ═══════════════════════════════════════════════════════════════════════════


def test_cr115__sendgrid_reads_the_scope_list_and_not_the_status() -> None:
    """⚠ **A `200` FROM `/v3/scopes` PROVES THE KEY EXISTS AND NOTHING ELSE.**

    A read-only key answers `200` with a list that has no `mail.send` in it, and
    a check that read the status would pass on it — law 7's *structurally
    incapable of failing*, on the one question this operation exists to ask.
    Proved red by returning `answer.ok`: the second half went green.
    """
    good = sendgrid().execute(
        view("sendgrid", SENDGRID_CONFIG),
        SENDGRID_SECRETS,
        [{"ref": "k", "operation": "validate_credentials"}],
    )
    assert good.items[0].outcome == "succeeded"

    read_only = sendgrid(
        fixtures.sendgrid_transport(scopes=fixtures.SENDGRID_SCOPES_READ_ONLY)
    ).execute(
        view("sendgrid", SENDGRID_CONFIG),
        SENDGRID_SECRETS,
        [{"ref": "k", "operation": "validate_credentials"}],
    )
    assert read_only.items[0].outcome == "failed"
    assert read_only.items[0].detail == esp_email.MISSING_SCOPE


def test_cr115__postmark_asks_a_weaker_question_and_says_so() -> None:
    """Postmark has no scopes: a Server token either names a Server or it does
    not. Asserted so the weaker check is a recorded DIFFERENCE rather than
    something a later lane "fixes" by inventing a scope list."""
    ok = postmark().execute(
        view("postmark", POSTMARK_CONFIG),
        POSTMARK_SECRETS,
        [{"ref": "k", "operation": "validate_credentials"}],
    )
    assert ok.items[0].outcome == "succeeded"

    nameless = postmark(fixtures.postmark_transport(server={})).execute(
        view("postmark", POSTMARK_CONFIG),
        POSTMARK_SECRETS,
        [{"ref": "k", "operation": "validate_credentials"}],
    )
    assert nameless.items[0].outcome == "failed"


def test_cr115__an_operation_this_connector_does_not_ask_for_is_named() -> None:
    """An unknown operation fails BY NAME rather than silently doing a send —
    which is what a default of *send* would have done, and the reason `execute`
    defaults to send only where no operation is named at all."""
    result = sendgrid().execute(
        view("sendgrid", SENDGRID_CONFIG),
        SENDGRID_SECRETS,
        [{"ref": "x", "operation": "collect_readings"}],
    )
    assert result.items[0].outcome == "failed"
    assert "collect_readings" in (result.items[0].detail or "")


# ═══════════════════════════════════════════════════════════════════════════
# THE LONG POLE — the DNS records
# ═══════════════════════════════════════════════════════════════════════════


def _records(result) -> list[dict]:
    return json.loads(result.items[0].detail)["records"]


def test_cr115__every_provider_record_is_read_out_of_their_answer() -> None:
    """⚠ **THE SINGLE MOST IMPORTANT CASE IN THIS FILE.**

    The `em1234` prefix and the DKIM selectors differ per SendGrid ACCOUNT. A
    composed record publishes cleanly, verifies never, and costs the utility's
    one-to-three-week cycle a SECOND time. So this moves the fixture's values to
    something no pattern could produce and asserts the served records follow
    them exactly — a test against the real-looking fixture alone would pass just
    as happily over a composer.
    """
    strange = json.loads(json.dumps(fixtures.SENDGRID_DOMAINS))
    strange[0]["dns"]["mail_cname"]["host"] = "zz9-plural-z.ottumwawater.gov"
    strange[0]["dns"]["mail_cname"]["data"] = "u00000.wl.sendgrid.net.example"
    strange[0]["dns"]["dkim1"]["host"] = "wibble._domainkey.ottumwawater.gov"
    result = sendgrid(fixtures.sendgrid_transport(domains=strange)).execute(
        view("sendgrid", SENDGRID_CONFIG),
        SENDGRID_SECRETS,
        [{"ref": DOMAIN, "operation": "check_domain_verified"}],
    )
    hosts = {one["host"] for one in _records(result)}
    assert "zz9-plural-z.ottumwawater.gov" in hosts
    assert "wibble._domainkey.ottumwawater.gov" in hosts
    values = {one["value"] for one in _records(result)}
    assert "u00000.wl.sendgrid.net.example" in values


def test_cr115__the_dmarc_record_is_ours_and_is_marked_as_ours() -> None:
    """DMARC is a statement the DOMAIN's owner makes; no ESP issues one, so no
    provider answer can carry it. It is therefore the ONE composed value in the
    product, and `source` is what lets a reader — and a panel — tell the
    difference."""
    result = sendgrid().execute(
        view("sendgrid", SENDGRID_CONFIG),
        SENDGRID_SECRETS,
        [{"ref": DOMAIN, "operation": "check_domain_verified"}],
    )
    records = _records(result)
    ours = [one for one in records if one["source"] == esp_email.SOURCE_OURS]
    assert len(ours) == 1
    assert ours[0]["purpose"] == esp_email.PURPOSE_DMARC
    assert ours[0]["type"] == "TXT"
    assert ours[0]["host"] == f"_dmarc.{DOMAIN}"
    assert ours[0]["value"] == "v=DMARC1; p=none;"
    # ⚠ And its `verified` is NULL, not False: the provider does not look at it,
    # and *unknown* and *not published* are different facts.
    assert ours[0]["verified"] is None
    assert all(
        one["source"] == esp_email.SOURCE_PROVIDER
        for one in records
        if one["purpose"] != esp_email.PURPOSE_DMARC
    )


def test_cr115__a_domain_with_two_of_three_published_is_partial() -> None:
    """The state a utility is actually in for most of the wait.

    ⚠ **THE RECORDS WE COMPOSED DO NOT VOTE.** DMARC's `verified` is `None` and
    counting it either way would make the panel lie in one of two directions:
    all-verified while a DKIM record is missing, or never-verified once the
    provider says everything is fine.
    """
    result = sendgrid().execute(
        view("sendgrid", SENDGRID_CONFIG),
        SENDGRID_SECRETS,
        [{"ref": DOMAIN, "operation": "check_domain_verified"}],
    )
    answer = json.loads(result.items[0].detail)
    assert answer["state"] == esp_email.DOMAIN_PARTIAL
    assert [one["verified"] for one in answer["records"]] == [True, True, False, None]

    published = json.loads(json.dumps(fixtures.SENDGRID_DOMAINS))
    published[0]["dns"]["dkim2"]["valid"] = True
    done = sendgrid(fixtures.sendgrid_transport(domains=published)).execute(
        view("sendgrid", SENDGRID_CONFIG),
        SENDGRID_SECRETS,
        [{"ref": DOMAIN, "operation": "check_domain_verified"}],
    )
    assert json.loads(done.items[0].detail)["state"] == esp_email.DOMAIN_VERIFIED_STATE


def test_cr115__a_domain_sendgrid_has_never_heard_of_is_not_an_error() -> None:
    """Day one for every utility. A failed item here would put a red run row on
    a connector on the day it is set up and every day of the wait — and the
    panel needs this state in order to ASK for the domain to be added."""
    result = sendgrid(fixtures.sendgrid_transport(domains=[])).execute(
        view("sendgrid", SENDGRID_CONFIG),
        SENDGRID_SECRETS,
        [{"ref": DOMAIN, "operation": "check_domain_verified"}],
    )
    assert result.items[0].outcome == "succeeded"
    answer = json.loads(result.items[0].detail)
    assert answer["state"] == esp_email.DOMAIN_NOT_FOUND
    # ⚠ And the DMARC line is STILL there — a third of the long pole can be
    # handed over before the provider knows the domain exists at all.
    assert [one["purpose"] for one in answer["records"]] == [esp_email.PURPOSE_DMARC]


def test_cr115__postmark_refuses_the_domain_check_in_words() -> None:
    """`DEF-INT-5650` — the Domains API takes an ACCOUNT token and this
    connector holds a SERVER token.

    ⚠ **THE MANIFEST IS WHERE THE REFUSAL LIVES**, not a branch on a provider
    key (`G77`): Postmark simply does not declare the operation, so nothing that
    reads the registry can offer it. This asserts BOTH — the absence on the
    manifest and the adapter's own six-word refusal if anything asks anyway.
    """
    assert not any(
        one.name == esp_email.OP_CHECK_DOMAIN
        for one in REGISTRY.require("postmark").operations
    )
    result = postmark().execute(
        view("postmark", POSTMARK_CONFIG),
        POSTMARK_SECRETS,
        [{"ref": DOMAIN, "operation": "check_domain_verified"}],
    )
    assert result.items[0].outcome == "failed"
    assert result.items[0].detail == esp_email.DOMAIN_NOT_OFFERED
    assert len(esp_email.DOMAIN_NOT_OFFERED.split()) <= 6  # B14 rule 33


def test_cr115__the_model_and_the_adapter_agree_about_the_four_states() -> None:
    """`models.py` keeps its own copy so the ORM does not import the transport
    layer, and says in its own comment that this test is what stops them
    drifting. Two hand-maintained tuples is how a fifth state becomes a database
    constraint violation nobody predicted."""
    assert tuple(integration_models.SENDING_DOMAIN_STATES) == tuple(esp_email.DOMAIN_STATES)


# ═══════════════════════════════════════════════════════════════════════════
# THE FEEDBACK VOCABULARY — normalised INSIDE the adapter, or not at all
# ═══════════════════════════════════════════════════════════════════════════

#: What each fixture event must become. The two lists are the SAME words in the
#: same order on purpose: the whole point is that a bill's history reads
#: identically whichever provider a utility is on.
EXPECTED = [
    "delivered",
    "bounced_hard",
    "bounced_soft",  # SendGrid `bounce/blocked` · Postmark `Bounce/SoftBounce`
    "bounced_soft",  # SendGrid `deferred`       · Postmark `Bounce/Blocked`
    "failed",  # SendGrid `dropped`         · Postmark an unknown bounce type
    "complained",
    "unsubscribed",
    None,
    None,
]


@pytest.mark.parametrize("key", ["sendgrid", "postmark"])
def test_cr115__two_vocabularies_become_one(key) -> None:
    """⚠ **THE WHOLE OF `BR-INT-004` ON THIS PATH.** SendGrid says
    `delivered · bounce · deferred · dropped · spamreport · unsubscribe`;
    Postmark says `Delivery · Bounce(+Type) · SpamComplaint ·
    SubscriptionChange`. **The same nine situations must come out identical.**
    """
    adapter = sendgrid() if key == "sendgrid" else postmark()
    events = fixtures.SENDGRID_EVENTS if key == "sendgrid" else fixtures.POSTMARK_EVENTS
    normalise = feedback_normaliser(adapter)
    assert normalise is not None
    outcomes = [normalise(one) for one in events]
    assert [None if one is None else one.status for one in outcomes] == EXPECTED
    for one in outcomes:
        if one is None:
            continue
        assert one.status in notification_models.PROVIDER_OUTCOME_STATUSES


@pytest.mark.parametrize("key", ["sendgrid", "postmark"])
def test_cr115__no_provider_word_escapes_the_adapter(key) -> None:
    """Nothing outside the adapter may ever see `spamreport` or `SpamComplaint`.

    ⚠ **THE FIRST DRAFT OF `FeedbackOutcome` CARRIED A `provider_event` FIELD**
    — for the record, it seemed — and it would have put SendGrid's vocabulary on
    a dataclass the whole product reads. It is not there, and this is the case
    that would have caught it coming back.
    """
    adapter = sendgrid() if key == "sendgrid" else postmark()
    events = fixtures.SENDGRID_EVENTS if key == "sendgrid" else fixtures.POSTMARK_EVENTS
    normalise = feedback_normaliser(adapter)
    #: ⚠ **`bounce` AND `unsubscribe` ARE DELIBERATELY NOT ON THIS LIST**, and
    #: the reason is worth a line: they are SUBSTRINGS of our own words
    #: (`bounced_hard`, `unsubscribed`), so including them makes this case
    #: impossible to pass — law 7's *incapable of passing*, which is what the
    #: first draft of it was. Every word below is one only a provider uses.
    forbidden = (
        "spamreport", "deferred", "dropped", "blocked",
        "spamcomplaint", "subscriptionchange", "hardbounce", "softbounce",
        "manuallydeactivated", "recordtype", "group_unsubscribe",
    )
    for event in events:
        outcome = normalise(event)
        if outcome is None:
            continue
        rendered = " ".join(
            str(one) for one in (outcome.status, outcome.tracking_ref, outcome.address)
        )
        for word in forbidden:
            assert word.lower() not in rendered.lower(), (event, word)


@pytest.mark.parametrize("key", ["sendgrid", "postmark"])
def test_cr115__our_reference_comes_back_so_a_bounce_can_find_its_row(key) -> None:
    """The reference we put on the message is the reference we read off the
    event — one spelling, or the feedback path matches nothing and looks exactly
    like a provider that is quiet."""
    adapter = sendgrid() if key == "sendgrid" else postmark()
    events = fixtures.SENDGRID_EVENTS if key == "sendgrid" else fixtures.POSTMARK_EVENTS
    normalise = feedback_normaliser(adapter)
    refs = [normalise(one).tracking_ref for one in events if normalise(one) is not None]
    assert refs == ["q-1", "q-2", "q-3", "q-4", "q-5", "q-6", "q-7"]


def test_cr115__a_soft_bounce_can_never_suppress_and_a_hard_one_always_does() -> None:
    """⚠ **THE RULE THAT DECIDES WHETHER A REAL CUSTOMER LOSES THEIR BILLS FOR
    EVER**, asserted against the ONE policy that owns it rather than restated.

    `suppression.SUPPRESSING_OUTCOMES` is the single table; this adapter lane
    writes no second one. A hard bounce and a complaint suppress; a soft bounce
    must not, and `suppression.suppress()` refuses an explicit soft-bounce
    suppression BY NAME so an adapter that dropped SendGrid's bounce TYPE meets
    an error rather than a silent success.
    """
    suppressing = suppression.SUPPRESSING_OUTCOMES
    assert notification_models.STATUS_BOUNCED_HARD in suppressing
    assert notification_models.STATUS_COMPLAINED in suppressing
    assert notification_models.STATUS_UNSUBSCRIBED in suppressing
    assert notification_models.STATUS_BOUNCED_SOFT not in suppressing
    assert notification_models.STATUS_FAILED not in suppressing
    assert notification_models.STATUS_DELIVERED not in suppressing

    # And every word the two adapters can produce is one this table knows about
    # — a status with no entry here would silently never suppress.
    produced = {one for one in EXPECTED if one is not None}
    assert produced <= set(notification_models.PROVIDER_OUTCOME_STATUSES)


def test_cr115__an_unknown_postmark_bounce_type_is_failed_and_not_a_guess() -> None:
    """⚠ **A JUDGMENT WE MADE, NOT A RULE WE WERE GIVEN** — decision log,
    2026-09-17.

    Postmark documents twenty-odd bounce types and adds to them. The truthful
    word for one we cannot read is `bounced`, *a bounce of unknown kind*, and
    `DEF-NOT-5626` ruled that word may never be written again. Of the six that
    remain, `failed` is the only one that takes no irreversible action:
    `bounced_hard` would suppress a possibly-live consumer on a word we could
    not read, and `bounced_soft` would retry into a possibly-dead mailbox for
    ever. Neither is recoverable by a clerk; `failed` puts it on their list.
    """
    normalise = feedback_normaliser(postmark())
    outcome = normalise({"RecordType": "Bounce", "Type": "SomethingPostmarkAddedInMarch"})
    assert outcome is not None and outcome.status == notification_models.STATUS_FAILED
    assert outcome.status not in suppression.SUPPRESSING_OUTCOMES


def test_cr115__neither_feedback_door_is_open_and_that_is_stated() -> None:
    """⚠ **THE NORMALISERS ABOVE HAVE NO CALLER ON THIS DEPLOYMENT** (hard-won
    law 2, stated rather than implied).

    SendGrid's inbound verification is `DEF-INT-5630` — its webhook signature is
    believed asymmetric and `SIGNATURE_ALGORITHMS` is symmetric only, so the
    manifest declares nothing and the door refuses. Postmark's Basic password
    cannot be minted (`DEF-INT-5634`). **So no `delivered`, `bounced_hard`,
    `bounced_soft`, `complained` or `unsubscribed` is written anywhere in this
    product today**, and this case goes RED the day either changes — which is
    when somebody has to wire the normaliser to the door and to
    `suppression.suppress_for_outcome`.
    """
    assert REGISTRY.require("sendgrid").auth.inbound is None
    assert REGISTRY.require("postmark").auth.inbound.style == "basic"
    # The half that is genuinely missing: nothing calls a normaliser.
    from apps.integrations import inbound

    assert inbound.runbooks_apply.__doc__ is not None
    assert inbound.runbooks_apply(None) is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 §7 · the decision log of 2026-09-17 (five PO rulings on email; DEF-NOT-5626's six outcomes) · US-INT-015 · BR-NOT-1032 (PROPOSED)
# generated: 2026-09-17 by the CR-115-BRC05 email-adapter lane
# checklist: A✔ B=n/a C✔ D=PARTIAL(neither provider is reachable from this environment — every case runs against hand-shaped fixtures and the module docstring says so first) E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr115_esp_adapters.py · the conformance kit UNCHANGED over both classes
# exceptions: NOTHING HERE IS EVIDENCE ABOUT SENDGRID OR POSTMARK — see the module docstring. The two `no caller` cases assert an ABSENCE and go red the day either feedback door opens, which is the point of them.
# ──────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════
# THE WIRE THE DNS PANEL IS BUILT AGAINST — `GET|POST /integrations/{key}/sending-domain`
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **ANOTHER LANE IS DRAWING THE PANEL AGAINST THIS SHAPE RIGHT NOW**, so the
# cases below pin the ENVELOPE and not only the behaviour. A field that
# disappears here is a panel that renders blank, and the two lanes cannot both
# find that out at merge.

from apps.integrations import sending_domain as sending_domain_service  # noqa: E402
from apps.integrations import api as integrations_api  # noqa: E402
from tests.test_us_int_helpers_b import call, patch_connection, post_connect  # noqa: E402,F401
from tests.test_us_met_helpers import *  # noqa: E402,F401,F403 — brazos · dana · audit_rows

SENDGRID_FIELDS = {
    "base_url": "https://api.sendgrid.com",
    "api_key": fixtures.SENDGRID_GOOD_KEY,
    "sending_domain": DOMAIN,
    "send_from": SENDER,
}
POSTMARK_FIELDS = {
    "base_url": "https://api.postmarkapp.com",
    "server_token": fixtures.POSTMARK_GOOD_TOKEN,
    "sending_domain": DOMAIN,
    "send_from": SENDER,
    "message_stream": "outbound",
}

#: Every key the panel may read. ⚠ Asserted as an EXACT set: a lane adding a
#: field here has to come and say so, and a lane removing one cannot do it
#: silently.
ENVELOPE_KEYS = {
    "provider_key",
    "connected",
    "available",
    "reason",
    "domain",
    "state",
    "checked_at",
    "verified_at",
    "records",
    "provider_text",
    "last_attempt",
}
RECORD_KEYS = {"purpose", "type", "host", "value", "verified", "source"}


def _bind(key: str, cls, transport):
    class Bound(cls):
        def __init__(self) -> None:
            super().__init__(transport)

    Bound.key = key
    Bound.__name__ = cls.__name__
    REGISTRY.register_adapter(key, Bound)
    return Bound


@pytest.fixture()
def sendgrid_bound():
    """The REAL class with only the socket replaced, bound to the REAL registry.

    ⚠ A mock adapter here would prove the route calls SOMETHING. Binding the
    product's own class proves the route calls the product's own code — the
    reason `conformance.RecordedSmtpAdapter` is shaped the same way.
    """
    transport = fixtures.sendgrid_transport()
    bound = _bind("sendgrid", EmailSendgridAdapter, transport)
    bound.transport = transport
    yield bound
    REGISTRY.register_adapter("sendgrid", EmailSendgridAdapter)


@pytest.fixture()
def postmark_bound():
    transport = fixtures.postmark_transport()
    bound = _bind("postmark", EmailPostmarkAdapter, transport)
    bound.transport = transport
    yield bound
    REGISTRY.register_adapter("postmark", EmailPostmarkAdapter)


def get_domain(tenant, actor, key):
    return call(integrations_api.sending_domain, "get", tenant, actor, key=key)


def post_domain(tenant, actor, key):
    return call(integrations_api.sending_domain, "post", tenant, actor, data={}, key=key)


@pytest.mark.django_db
def test_cr115__the_panel_gets_the_dmarc_record_before_anybody_checks_anything(
    brazos, dana, sendgrid_bound
) -> None:
    """⚠ **THE LONG POLE STARTS HERE AND THIS IS THE CASE THAT PROVES IT.**

    PO 2026-09-17: the utility's IT team takes *"one to three weeks"* and
    Production waits on them, so *"it is worth starting on day one rather than
    at the end"*. A `GET` on a connector nobody has ever checked therefore
    answers instantly, dials nothing, and already carries the one record no ESP
    issues — a third of the work, in the IT team's hands before any button
    exists to press.
    """
    assert post_connect(brazos, dana, "sendgrid", SENDGRID_FIELDS).status_code == 201
    answer = get_domain(brazos, dana, "sendgrid")
    assert answer.status_code == 200
    assert set(answer.data) == ENVELOPE_KEYS
    assert answer.data["connected"] is True
    assert answer.data["available"] is True
    assert answer.data["reason"] is None
    assert answer.data["domain"] == DOMAIN
    assert answer.data["checked_at"] is None
    assert answer.data["verified_at"] is None
    assert answer.data["state"] == esp_email.DOMAIN_UNVERIFIED
    assert [one["purpose"] for one in answer.data["records"]] == [esp_email.PURPOSE_DMARC]
    assert set(answer.data["records"][0]) == RECORD_KEYS
    assert answer.data["records"][0]["source"] == esp_email.SOURCE_OURS
    # ⚠ A `GET` never dials, so it never reports a press.
    assert answer.data["last_attempt"] is None
    # ⚠ AND NOTHING WAS DIALLED. A `GET` that spent a utility's rate limit on
    # every screen refresh is `BR-INT-041`'s problem arriving through a read.
    assert sendgrid_bound.transport.sent == []


@pytest.mark.django_db
def test_cr115__a_check_stores_what_the_provider_said_and_the_get_serves_it(
    brazos, dana, sendgrid_bound
) -> None:
    """`POST` asks, `GET` answers from what was stored — and the row is real."""
    post_connect(brazos, dana, "sendgrid", SENDGRID_FIELDS)
    checked = post_domain(brazos, dana, "sendgrid")
    assert checked.status_code == 200
    assert checked.data["state"] == esp_email.DOMAIN_PARTIAL
    assert checked.data["checked_at"] is not None
    assert checked.data["verified_at"] is None  # partial is not finished
    assert checked.data["last_attempt"] == {"ok": True, "provider_text": None}
    purposes = [one["purpose"] for one in checked.data["records"]]
    assert purposes == ["return_path", "dkim", "dkim", "dmarc"]

    row = integration_models.IntegrationSendingDomain.objects.get(
        tenant_id=brazos.id, domain=DOMAIN
    )
    assert row.state == esp_email.DOMAIN_PARTIAL and row.checked_at is not None

    served = get_domain(brazos, dana, "sendgrid")
    assert served.data["records"] == checked.data["records"]
    assert served.data["checked_at"] == checked.data["checked_at"]


@pytest.mark.django_db
def test_cr115__saving_a_setting_does_not_delete_the_dns_records(
    brazos, dana, sendgrid_bound
) -> None:
    """⚠ **THE REASON THIS IS A TABLE AND NOT `connection.config`.**

    `services.update_connection` PRUNES the stored config to the names the
    manifest still declares (`DEF-INT-5582`) — right, and fatal for anything
    parked there by the server. Records on the connection would have survived
    every test in this file and vanished the first time a clerk pressed Save on
    a real deployment, with a correct file count and a green suite.

    Proved red by moving the answer onto `connection.config`: this case failed
    with an empty record list and every other case in the file stayed green.
    """
    post_connect(brazos, dana, "sendgrid", SENDGRID_FIELDS)
    post_domain(brazos, dana, "sendgrid")
    assert patch_connection(brazos, dana, "sendgrid", {"label": "Bills"}).status_code == 200
    after = get_domain(brazos, dana, "sendgrid")
    assert [one["purpose"] for one in after.data["records"]] == [
        "return_path", "dkim", "dkim", "dmarc",
    ]
    assert after.data["checked_at"] is not None


@pytest.mark.django_db
def test_cr115__postmark_says_it_cannot_be_asked_and_still_gives_the_dmarc_line(
    brazos, dana, postmark_bound
) -> None:
    """⚠ **AN ABSENCE WITH ITS REASON, NEVER AN EMPTY PANEL** (`DEF-INT-5650`).

    An empty box reads as a bug and generates a support call; *we cannot ask
    Postmark this with the token we hold* is a fact somebody can act on. And the
    DMARC record still goes out, so a Postmark utility starts its IT ticket on
    day one with the same third of the work a SendGrid utility gets.
    """
    assert post_connect(brazos, dana, "postmark", POSTMARK_FIELDS).status_code == 201
    answer = get_domain(brazos, dana, "postmark")
    assert answer.data["connected"] is True
    assert answer.data["available"] is False
    assert answer.data["reason"] == sending_domain_service.REASON_PROVIDER_CANNOT_BE_ASKED
    assert [one["purpose"] for one in answer.data["records"]] == [esp_email.PURPOSE_DMARC]
    # ⚠ And a press changes nothing rather than raising — the panel may offer
    # the button or not, and neither choice can break the route.
    pressed = post_domain(brazos, dana, "postmark")
    assert pressed.status_code == 200
    assert pressed.data["reason"] == sending_domain_service.REASON_PROVIDER_CANNOT_BE_ASKED
    assert postmark_bound.transport.sent == []


def test_cr115__the_route_resolves_through_the_real_urlconf() -> None:
    """⚠ **`integrations/<str:key>` WOULD SWALLOW THIS PATH IF IT WERE LISTED
    FIRST**, reading `sending-domain` as a provider key and answering with the
    connection route's `PATCH`/`DELETE`. Django matches in order, and
    `config/urls.py`'s own comment records that exact collision being found by a
    browser rather than by reasoning (`integrations/subprocessors`).

    `test_us_int_042_gis.py` set the precedent of resolving through the REAL
    URLconf so a future insertion above it cannot pass silently; this is the
    same guard for the DNS route. It checks the METHODS as well as the match,
    because both routes take one `key` and a wrong match looks identical
    otherwise.
    """
    from django.urls import resolve

    ours = resolve("/api/brazosbend/integrations/sendgrid/sending-domain")
    assert ours.kwargs == {"key": "sendgrid"}
    assert sorted(ours.func.cls.http_method_names) == ["get", "options", "post"]

    # …and the two-segment route it sits above is untouched.
    theirs = resolve("/api/brazosbend/integrations/sendgrid")
    assert sorted(theirs.func.cls.http_method_names) == ["delete", "options", "patch"]


@pytest.mark.django_db
def test_cr115__a_connector_nobody_has_connected_says_so(brazos, dana) -> None:
    """The panel has to draw this state too, and `connected: false` is what says
    to send the clerk to Connect rather than to their IT team."""
    answer = get_domain(brazos, dana, "sendgrid")
    assert answer.status_code == 200
    assert answer.data["connected"] is False
    assert answer.data["available"] is False
    assert answer.data["reason"] == sending_domain_service.REASON_NOT_CONNECTED
    assert answer.data["records"] == []


@pytest.mark.django_db
def test_cr115__a_connected_esp_is_what_the_dispatcher_will_actually_send_through(
    brazos, dana, sendgrid_bound
) -> None:
    """⚠ **BUILT IS NOT WIRED (hard-won law 2), AND THIS IS THE CASE THAT SAYS
    WHICH ONE THIS IS.**

    An adapter that passes the conformance kit and is never reached by the
    dispatcher is dead code with a green suite — four defects in one day, once.
    `seams/notifications.dispatch_outbound_batch` picks the tenant's enabled
    PRODUCTION connection for the channel's category **with an adapter bound and
    an active credential**; every one of those is a reason a batch could not go,
    and until this commit an ESP failed the adapter clause silently.

    This asserts the seam resolves to the connection a clerk just made and that
    the operation it would run under is the SEND one — not `validate_credentials`,
    which is also `us`-initiated and which a naive *first operation* pick would
    have chosen on a manifest where it happened to be listed first.
    """
    from apps.integrations.seams import notifications as seam
    from core.tenancy import tenant_context

    post_connect(brazos, dana, "sendgrid", SENDGRID_FIELDS)
    with tenant_context(brazos.id):
        row = seam._connection_for_channel("email")
        assert row is not None and row.provider_key == "sendgrid"
        operation = seam._sending_operation(row)
        assert operation.name == esp_email.OP_SEND
        assert (operation.direction, operation.initiative) == ("out", "us")
        # ⚠ And the provider is reported as one that WILL report feedback —
        # true of the vendor, and the delivery rail deliberately keeps saying
        # *not reported* until a door actually opens (`BR-INT-027`).
        assert seam.reports_feedback(row) is True


@pytest.mark.django_db
def test_cr115__a_refused_check_keeps_the_records_and_says_the_press_failed(
    brazos, dana
) -> None:
    """⚠ **A BUTTON THAT CHANGES NOTHING LOOKS EXACTLY LIKE ONE THAT WORKED**
    (hard-won law 2's mirror), and this is the case that stops it.

    A refused check must NOT overwrite what we hold: a utility's own DNS records
    are the one screen their IT team works from, and replacing them with *we
    could not ask* over a thirty-second outage is the worse failure. But leaving
    it there means the whole reply is byte-identical to the one before the
    press, so the clerk cannot tell a refusal from *nothing has changed*.
    `last_attempt` is the difference, and `ok: false` beside an unchanged
    `checked_at` is precisely *we asked and could not find out*.

    The refusal used here is the REAL one this connector will meet first:
    `403`, because `DEF-INT-5649` records that the platform SendGrid key was
    issued with `mail.send` and `GET /v3/whitelabel/domains` needs
    `whitelabel.read`.
    """
    try:
        # …a healthy check first, so there is something real to lose.
        _bind("sendgrid", EmailSendgridAdapter, fixtures.sendgrid_transport())
        post_connect(brazos, dana, "sendgrid", SENDGRID_FIELDS)
        first = post_domain(brazos, dana, "sendgrid")
        assert first.data["state"] == esp_email.DOMAIN_PARTIAL
        assert first.data["last_attempt"]["ok"] is True
        held = first.data["records"]
        stamp = first.data["checked_at"]

        # …then the same connection, refused.
        _bind(
            "sendgrid",
            EmailSendgridAdapter,
            fixtures.refusing_transport(403, {"errors": [{"message": "access forbidden"}]}),
        )
        after = post_domain(brazos, dana, "sendgrid")
    finally:
        # ⚠ ONE restore, in a `finally` that covers BOTH bindings. An earlier
        # draft wrote `del good`, which unbinds nothing at all — it drops a
        # local name while the registry keeps the fixture class for every case
        # that runs after this one.
        REGISTRY.register_adapter("sendgrid", EmailSendgridAdapter)

    assert after.status_code == 200
    # what we hold is untouched…
    assert after.data["records"] == held
    assert after.data["checked_at"] == stamp
    assert after.data["state"] == esp_email.DOMAIN_PARTIAL
    # …and the press is reported, in THEIR words.
    assert after.data["last_attempt"]["ok"] is False
    assert "access forbidden" in after.data["last_attempt"]["provider_text"]
