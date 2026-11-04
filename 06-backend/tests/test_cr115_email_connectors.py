"""`CR-115-BRC05` — the two email connectors, and the four holds they carry.

⚠ **EVERY TEST HERE IS A HOLD WITH A TEST ON IT** (hard-won law 2's mirror
clause: *"WHEN YOU WRITE A HOLD, WRITE THE TEST THAT FIRES WHEN THE HOLD
EXPIRES, in the same commit"*). None of them asserts that something works.
Each asserts that something is still DEFERRED, and goes RED on the day it stops
being — which is the only kind of deferral anybody is actually keeping.

The four:

  1. **No adapter → the card says *coming soon*.** This REPLACES the
     name-shaped hold in `test_cr110_connectors.py`, which could not survive
     the rename: it fired on the display name, so naming the vendor demanded
     these cards go LIVE with nothing behind them (`DEF-INT-4224` exactly).
  2. **SendGrid declares no inbound verification while `DEF-INT-5630` is
     open** — and the door is proved to REFUSE its real headers, so the
     absence is a closed door rather than an open one.
  3. **Postmark cannot mint its Basic password yet** (`DEF-INT-5634`).
  4. **`message_stream` declares no per-class map** (`DEF-INT-5635`), because
     the class axis is not the axis Postmark's streams split on.

Plus one guard that is not a hold: the runbook's hardcoded delivery-provider
list has to keep resolving against the registry. It did not go red when this
rename happened, and that is precisely why it is here now.
"""

from __future__ import annotations

import base64
import datetime

import pytest

from apps.integrations import inbound, machine_auth
from apps.integrations.manifests import register_all
from apps.integrations.registry import REGISTRY, SIGNATURE_ALGORITHMS, Registry

#: The two email service providers `CR-115-BRC05` named. `sendgrid` is row 04
#: renamed from `email_bulk`; `postmark` is the thirtieth connector.
ESPS = ("sendgrid", "postmark")


@pytest.fixture
def registry() -> Registry:
    """Every MANIFEST, registered together, exactly as `AppConfig.ready()` does.

    ⚠ Validation is a WHOLE-SET act: `register_all` refuses the FIRST bad
    manifest by name, so a file validated on its own proves nothing about the
    set the product loads.

    ⚠⚠ **IT HOLDS NO ADAPTERS, AND TWO HOLDS IN THIS FILE USED TO ASK IT ABOUT
    ONE — `DEF-INT-5651`.** `manifests.register_all` registers manifests;
    `adapters.register_all` is a DIFFERENT function and `AppConfig.ready()`
    calls both. So `Registry()` built here answers `adapter_for(...) is None`
    for every key that has ever existed, whatever the product does. That made
    `test_cr115__a_held_esp_is_still_offered_honestly` **structurally incapable
    of failing** (hard-won law 7's second shape) and made the hold below
    measure a registry no request is ever served from (law 7's fourth: looking
    at the wrong thing). Both passed green for the fortnight the hold was true,
    which is exactly how a check like this is never noticed. **Anything asking
    *is an adapter bound* now uses `PRODUCT` below.**
    """
    return register_all(Registry())


#: The registry the PRODUCT actually serves from — filled by
#: `IntegrationsConfig.ready()` with the manifests AND the adapters, in that
#: order. `services.connect` reads this one, so a hold about whether a card can
#: be pressed has to read it too.
PRODUCT = REGISTRY


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


# ═══════════════════════════════════════════════════════════════════════════
# HOLD 1 — no adapter, no live card
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("key", ESPS)
def test_cr115__a_connector_with_no_adapter_says_coming_soon(
    registry: Registry, key: str
) -> None:
    """The hold that replaces *is the vendor still unnamed*.

    ⚠ **THE ASSERTION RUNS BOTH WAYS ON PURPOSE**, exactly as the hold it
    replaces did. Binding an adapter and forgetting the disposition leaves a
    connector nobody can reach; setting the disposition and forgetting the
    adapter is `DEF-INT-4224` — a card a utility can press that cannot work,
    which the blueprint files as a defect in its own right (p146).
    """
    manifest = PRODUCT.require(key)
    has_adapter = PRODUCT.adapter_for(key) is not None
    assert manifest.disposition.coming_soon != has_adapter, (
        f"{key}: the card is {manifest.disposition.kind!r} and an adapter is "
        f"{'bound' if has_adapter else 'NOT bound'}. If the adapter has landed, this "
        "connector is ready to be made live — set the disposition and give it a real "
        "test action. If it has not, the card must keep saying so."
    )
    if manifest.disposition.coming_soon:
        assert manifest.disposition.wave, key


@pytest.mark.parametrize("key", ESPS)
def test_cr115__a_held_esp_is_still_offered_honestly(key: str) -> None:
    """⚠ **THIS HOLD EXPIRED ON 2026-09-17 AND THE ASSERTION IS NOW ITS
    OPPOSITE. THE NAME IS KEPT ON PURPOSE.**

    It read `adapter_for(key) is None` — *a coming-soon card is refused at the
    service boundary and the registry refuses to bind an adapter to one, so this
    cannot be half-released by editing one of the two.* True, and it asked a
    registry that holds no adapters at all (`DEF-INT-5651`, and the `registry`
    fixture's docstring above), so it was a check with no possible failure.

    **What replaces it is the same rule read the other way round**, against the
    registry the product serves from: both ESPs are LIVE, both have an adapter,
    and `BR-INT-001` is still what ties the two together — `register_adapter`
    refuses a coming-soon provider, so there is no state in which one of these
    is true and the other is not.

    The NAME is unchanged because renaming it would lose the link between this
    assertion and the deferral it used to keep, and because a test whose
    docstring records what it used to assert is how the next lane finds out that
    a hold was honoured rather than quietly deleted.
    """
    assert PRODUCT.adapter_for(key) is not None
    assert not PRODUCT.require(key).disposition.coming_soon


# ═══════════════════════════════════════════════════════════════════════════
# HOLD 2 — SendGrid's signature, `DEF-INT-5630`, OPEN
# ═══════════════════════════════════════════════════════════════════════════


def test_cr115__sendgrid_declares_no_inbound_verification_while_5630_is_open(
    registry: Registry,
) -> None:
    """**The question gets asked instead of assumed.**

    SendGrid's Event Webhook signs the body; its own set-up screen calls what
    it issues a *Verification Key*, which is the word for a PUBLIC key. If that
    is ECDSA then verifying proves the sender holds a private half we have
    never seen, and `serve.resolve_caller`'s *identify the caller by the blind
    index of what it proved knowledge of* stops being true — a different
    security statement, unanswered by the PO.

    So this manifest declares NOTHING, and this test fails the day either half
    of that changes: the manifest declaring a style, or an asymmetric algorithm
    joining the signed vocabulary.
    """
    assert registry.require("sendgrid").auth.inbound is None, (
        "sendgrid now declares an inbound verification style. If DEF-INT-5630 has been "
        "answered, say so here and in the manifest's own comment; if it has not, this "
        "connector must not claim a verification it cannot honour (hard-won law 2)."
    )
    assert SIGNATURE_ALGORITHMS == ("hmac_sha256",), (
        "an algorithm joined SIGNATURE_ALGORITHMS. If it is asymmetric, DEF-INT-5630's "
        "question — WHICH CREDENTIAL ROW IS THIS CALLER, when the stored value proves "
        "no possession — has to be answered before sendgrid declares a signature style."
    )


def test_cr115__sendgrid_inbound_fails_closed_on_its_real_headers(
    registry: Registry,
) -> None:
    """**An undeclared style is a CLOSED door, not an open one** — which is the
    whole reason the half-ship above is safe rather than merely quiet.

    Absent means `presented_key`, which reads a bearer token out of
    `Authorization`. SendGrid sends no such header — it sends a signature and a
    timestamp — so the door answers `None`, and `None` is a refusal.
    """
    got = inbound.verify(
        registry.require("sendgrid"),
        {
            "HTTP_X_TWILIO_EMAIL_EVENT_WEBHOOK_SIGNATURE": "MEUCIQDdUXG2Aq8Kk",
            "HTTP_X_TWILIO_EMAIL_EVENT_WEBHOOK_TIMESTAMP": "1600112502",
        },
        b'[{"sg_event_id":"ZGVsaXZlcmVk","event":"delivered"}]',
        received_at=_now(),
    )
    assert got is None, (
        "a real SendGrid webhook call was ADMITTED by the door while DEF-INT-5630 is "
        f"open — verify() answered {got!r}. It must refuse until the signature question "
        "is answered."
    )


# ═══════════════════════════════════════════════════════════════════════════
# HOLD 3 — Postmark's Basic password cannot be minted, `DEF-INT-5634`
# ═══════════════════════════════════════════════════════════════════════════


def test_cr115__postmark_declares_basic_and_the_door_reads_it(registry: Registry) -> None:
    """The half that IS wired. `basic` is a transport for a key we minted, so
    the door reads the password out of the Basic scheme and hands it on exactly
    as a header-borne key. No new authenticator, no new maths."""
    manifest = registry.require("postmark")
    assert manifest.auth.inbound is not None
    assert manifest.auth.inbound.style == "basic"
    token = base64.b64encode(b"postmark:the-key-we-minted").decode()
    assert (
        inbound.verify(
            manifest,
            {"HTTP_AUTHORIZATION": f"Basic {token}"},
            b'{"RecordType":"Bounce"}',
            received_at=_now(),
        )
        == "the-key-we-minted"
    )


def test_cr115__postmark_cannot_mint_its_basic_password_yet(registry: Registry) -> None:
    """**`DEF-INT-5634` — the door is wired and the key it needs cannot exist.**

    `machine_auth` issues a key only where the MANIFEST says we issue one, read
    off `auth.mode` (`_partner_manifest`), and Postmark is `we_hold_theirs`
    because we hold THEIR server token. So this connector needs two credentials
    at once — `DEF-INT-4118`'s open limit, reached from a second direction.

    ⚠ **THIS TEST ASSERTS THE LIMITATION, SO IT GOES RED WHEN THE LIMITATION
    LIFTS** and names the manifest that has been waiting for it. Without it the
    fix for 4118 could land and nobody would come back here.
    """
    manifest = registry.require("postmark")
    assert manifest.auth.mode == "we_hold_theirs"
    assert machine_auth.issued_key_field(manifest) is None
    with pytest.raises(Exception) as caught:
        machine_auth._partner_manifest(manifest)
    assert "not_a_partner_connection" in str(getattr(caught.value, "message_key", "")), (
        "machine_auth now mints a key for a we_hold_theirs connector. If DEF-INT-4118 / "
        "DEF-INT-5634 have been fixed, postmark's webhook password can finally be issued "
        "— wire it and update this test and the manifest's comment."
    )


# ═══════════════════════════════════════════════════════════════════════════
# HOLD 4 — the stream axis does not line up, `DEF-INT-5635`
# ═══════════════════════════════════════════════════════════════════════════


def test_cr115__postmark_declares_no_per_class_stream_map(registry: Registry) -> None:
    """`Field.per_class` exists BECAUSE of Postmark's Message Streams, and
    Postmark ships declaring none. That needs a test or it reads as an
    oversight.

    The axis does not line up: `per_class` keys on `notification_classes()` —
    five BUSINESS AREAS — and Postmark splits TRANSACTIONAL from BULK. Four of
    the five classes are wholly transactional and the fifth, `service_field`,
    holds an outage broadcast beside three per-recipient transactional
    templates, so **no value is right for the class**. Filed as `DEF-INT-5635`.
    """
    stream = next(
        one for one in registry.require("postmark").fields if one.name == "message_stream"
    )
    assert stream.default == "outbound"
    assert dict(stream.per_class) == {}, (
        "postmark's message_stream declares a per-class map. Check DEF-INT-5635 first: "
        "mapping the whole `service_field` class to 'broadcast' puts appointment "
        "reminders on a bulk stream, which is a real customer harm. The split Postmark "
        "needs is per TEMPLATE, not per CATEGORY."
    )
    #: ⚠ `text` and not `select` — a Postmark customer may create streams of
    #: their own, and a `select` is a CLOSED list the registry enforces.
    assert stream.kind == "text"
    assert stream.options == ()


# ═══════════════════════════════════════════════════════════════════════════
# NOT A HOLD — the list that did not go red when it should have
# ═══════════════════════════════════════════════════════════════════════════


def test_cr115__the_runbook_names_every_delivery_manifest(registry: Registry) -> None:
    """**A hardcoded key list that silently stops matching is worse than a
    crash, and this one nearly did it.**

    `runbooks/definitions/undeliverable_contacts.DELIVERY_PROVIDER_KEYS` names
    manifest keys as VALUES rather than importing them — by design, because
    `G115` refuses a runbook importing `apps.integrations.manifests`
    (`BR-RBS-039`). So a rename does not reach it and NOTHING GOES RED: the
    card would go on reporting *no feedback door* for a utility that had one,
    truthfully counting everything it could see. That is hard-won law 7's
    *reporting zero over a scope it silently excludes*.

    The seam stays a seam — this test imports both sides and compares, which is
    a TEST importing two modules rather than a runbook importing a registry.
    """
    from apps.runbooks.definitions.undeliverable_contacts import DELIVERY_PROVIDER_KEYS

    unknown = [key for key in DELIVERY_PROVIDER_KEYS if registry.get(key) is None]
    assert unknown == [], (
        f"the undeliverable-contacts runbook names {unknown}, which no manifest declares. "
        "A key that matches nothing makes the card report 'no feedback door' for a "
        "utility that has one, and nothing else in this repo would notice."
    )


def test_cr115__both_esps_are_reachable_as_email_providers(registry: Registry) -> None:
    """The positive half: the two ESPs are IN that list, so a utility on either
    one is seen by the runbook. Renaming row 04 and adding a second vendor is
    exactly when this stops being true by accident."""
    from apps.runbooks.definitions.undeliverable_contacts import DELIVERY_PROVIDER_KEYS

    for key in ESPS:
        assert key in DELIVERY_PROVIDER_KEYS, key
        assert registry.require(key).category == "email"


# ═══════════════════════════════════════════════════════════════════════════
# THE TWO MANIFESTS DIFFER ONLY WHERE THE WIRE DIFFERS
# ═══════════════════════════════════════════════════════════════════════════


def test_cr115__the_five_declared_provider_differences(registry: Registry) -> None:
    """Two near-identical manifests are the shape a copy-paste drifts in.

    ⚠ **SIX SINCE 2026-09-17, AND THE NAME IS LEFT ALONE DELIBERATELY.** The
    sixth is domain verification, which only SendGrid can be asked about. The
    function name is not renamed because renaming a test is a mass edit to
    every citation of it and this repo has been burned by exactly that
    (`CLAUDE.md`'s id-padding reasoning); the COUNT that matters is asserted
    below, not spelled in the name.

    Each assertion below is a REAL difference on the wire, named in
    `CR-115-BRC05`. If one of them changes, it changed because a vendor did —
    or because somebody copied a line from the sibling by mistake, which is the
    case this exists to catch.
    """
    sg = registry.require("sendgrid")
    pm = registry.require("postmark")

    # 1 · how OUR request authenticates
    assert (sg.auth.placement, sg.auth.header) == ("bearer", None)
    assert (pm.auth.placement, pm.auth.header) == ("header", "X-Postmark-Server-Token")

    # 2 · how THEIR call back authenticates (and SendGrid's is DEF-INT-5630)
    assert sg.auth.inbound is None
    assert pm.auth.inbound is not None and pm.auth.inbound.style == "basic"

    # 3 · the secret's own name, because a clerk is copying it off a screen
    assert [one.name for one in sg.fields if one.is_secret] == ["api_key"]
    assert [one.name for one in pm.fields if one.is_secret] == ["server_token"]

    # 4 · the stream, which SendGrid has no concept of.
    #: ⚠ Compared over the NON-SECRET fields on purpose. A raw set difference
    #: also reports `server_token`, which is not an extra field at all — it is
    #: the same credential under the vendor's own word, and assertion 3 above
    #: is where that is checked. Two assertions answering for one fact is how
    #: one of them ends up being "fixed" by loosening it.
    def plain(manifest):
        return {one.name for one in manifest.fields if not one.is_secret}

    assert plain(pm) - plain(sg) == {"message_stream"}
    assert plain(sg) - plain(pm) == set()

    # 5 · the inbound event id each one sends
    def feedback_key(manifest):
        op = next(one for one in manifest.operations if one.name == "receive_feedback")
        return op.idempotency.key_field

    assert feedback_key(sg) == "sg_event_id"
    assert feedback_key(pm) == "MessageID"

    # 6 · ⚠ **A SIXTH, ADDED 2026-09-17: ONLY ONE OF THEM CAN BE ASKED ABOUT A
    #     SENDING DOMAIN.** Postmark's `/domains` API takes an ACCOUNT token and
    #     this connector holds a SERVER token (`DEF-INT-5650`), and the account
    #     token is a PLATFORM credential `AUTH_MODES` cannot express
    #     (`DEF-INT-5636`). The blocker is expressed as an operation Postmark
    #     does NOT declare, so no code anywhere branches on a provider key to
    #     know it (`G77`) — `sending_domain._why_not_askable` reads exactly this.
    def names(manifest):
        return {one.name for one in manifest.operations}

    assert "check_domain_verified" in names(sg)
    assert "check_domain_verified" not in names(pm)
    assert "validate_credentials" in names(sg) and "validate_credentials" in names(pm)

    # …and what is deliberately the SAME, so it is not mistaken for an oversight
    for manifest in (sg, pm):
        assert manifest.auth.mode == "we_hold_theirs"
        assert manifest.category == "email"
        assert manifest.summary == "High-volume bulk sending"
        assert [one.name for one in manifest.operations] == [
            "send_message",
            "validate_credentials",
            *(["check_domain_verified"] if manifest.key == "sendgrid" else []),
            "receive_feedback",
        ]
