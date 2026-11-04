# ── Trace ──────────────────────────────────────────────
# Story:  US-INT-005 (EP-INT-07) — BYO mailbox: the round trip, and *Send bills
#         from* as the SIGNED-IN identity. CR-069 wave H task H4.
#         Screens: S141 (frame 49.2) · S142 (frame 54.1)
# Rules:  BR-INT-005 (BYO mailbox, the tenant's OWN address) · BR-INT-043 (a
#         redirect is a button and a return trip; the modal is generated from
#         the manifest, "no code branched to make that true") · BR-INT-025
#         (versioned, never updated) · BR-INT-047 (the refresh token is what
#         is stored; the short-lived one never is) · BR-INT-003
# ───────────────────────────────────────────────────────
"""Signing in to a mailbox, and coming back.

⚠ NO TEST HERE REACHES THE NETWORK, AND THE SEAM FOR THAT IS AN ARGUMENT.
`oauth.complete(exchange=…)` takes its exchanger; `oauth_fixtures.recorded_
exchange` replays a provider's documented response THROUGH the real
`grant_from_payload`. A `mock.patch` would have kept passing the day somebody
renamed what it patched, and the path being covered is the one that stores a
customer's mailbox credential.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from apps.integrations import models, oauth, oauth_fixtures, services
from apps.integrations.registry import REGISTRY
from core import errors
from tests.test_us_int_helpers_b import *  # noqa: F401,F403 — fixtures + request helpers
from tests.test_us_int_helpers_b import post_connect
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

MAILBOX = "email_microsoft"
MAILBOX_FIELDS = {"send_from": "typed@brazosbend.example"}
RETURN_TO = "https://brazosbend.smartbillhub.example/settings/integrations/email_microsoft/return"
NOW = datetime(2026, 9, 1, 17, 0, tzinfo=dt_timezone.utc)


@pytest.fixture()
def registered_client(settings):
    """OUR registration with Microsoft — deployment config, never repo content."""
    settings.INTEGRATION_OAUTH_CLIENTS = {
        MAILBOX: {"client_id": "recorded-client-id", "client_secret": "recorded-client-secret"},
        "email_google": {"client_id": "recorded-client-id", "client_secret": "recorded-secret"},
    }
    return settings


def _recorded(**overrides):
    def exchange(*, manifest, code, redirect_uri):
        return oauth_fixtures.recorded_exchange(
            manifest=manifest, code=code, redirect_uri=redirect_uri, now=NOW, **overrides
        )

    return exchange


def _start(tenant, actor):
    with tenant_ctx(tenant):
        return oauth.start(
            actor=actor, tenant_id=tenant.id, provider_key=MAILBOX, redirect_uri=RETURN_TO
        )


# ── the outward leg ─────────────────────────────────────────────────────────


def test_the_authorise_url_is_built_from_the_manifest_and_nothing_else(
    brazos, dana, microsoft_adapter, registered_client
):
    """`BR-INT-043` — *"no code branched to make that true"*."""
    post_connect(brazos, dana, MAILBOX, MAILBOX_FIELDS)
    answer = _start(brazos, dana)

    endpoints = REGISTRY.require(MAILBOX).auth.oauth
    assert answer["authorize_url"].startswith(endpoints.authorize_url)
    assert "Mail.Send" in answer["authorize_url"], "the manifest's own scopes"
    assert "offline_access" in answer["authorize_url"], "or no refresh token comes back at all"
    assert answer["state"], "a nonce is minted per attempt"
    # ⚠ OUR client SECRET is never in a URL a browser follows.
    assert "recorded-client-secret" not in answer["authorize_url"]


def test_the_state_is_a_fresh_nonce_per_attempt(brazos, dana, microsoft_adapter, registered_client):
    """Two starts, two nonces — a reused one is a replayable authorisation."""
    post_connect(brazos, dana, MAILBOX, MAILBOX_FIELDS)
    first = _start(brazos, dana)
    second = _start(brazos, dana)
    assert first["state"] != second["state"]


def test_an_unregistered_deployment_is_refused_by_name_rather_than_sent_to_a_dead_screen(
    brazos, dana, microsoft_adapter, settings
):
    """Hard-won law 3 — the unsafe option must be the one you type. With no
    client registration we refuse HERE, rather than sending a person to a
    consent screen that fails with the provider's own opaque error."""
    settings.INTEGRATION_OAUTH_CLIENTS = {}
    post_connect(brazos, dana, MAILBOX, MAILBOX_FIELDS)
    with tenant_ctx(brazos), pytest.raises(errors.BizError) as refusal:
        oauth.start(
            actor=dana, tenant_id=brazos.id, provider_key=MAILBOX, redirect_uri=RETURN_TO
        )
    assert refusal.value.message_key == oauth.REFUSAL_OAUTH_NOT_CONFIGURED


# ── the return leg ──────────────────────────────────────────────────────────


def test_the_return_trip_writes_v1_with_the_consent_date_on_the_same_connection(
    brazos, dana, microsoft_adapter, registered_client
):
    """The whole of H1: a code comes back, a credential lands, and it carries
    the date the CONSENT runs out — ninety days, not the access token's hour."""
    post_connect(brazos, dana, MAILBOX, MAILBOX_FIELDS)
    started = _start(brazos, dana)
    with tenant_ctx(brazos):
        row = oauth.complete(
            actor=dana,
            tenant_id=brazos.id,
            provider_key=MAILBOX,
            code="recorded-auth-code",
            state=started["state"],
            now=NOW,
            exchange=_recorded(),
        )
        credential = models.IntegrationCredential.objects.get(connection=row, is_active=True)

    assert credential.version == 1
    assert credential.expires_at == NOW + timedelta(days=90), (
        "Microsoft's stated refresh_token_expires_in, NOT expires_in's 3599 seconds"
    )
    assert credential.masked_hint.startswith("••••")


def test_send_bills_from_becomes_the_signed_in_identity_not_what_was_typed(
    brazos, dana, microsoft_adapter, registered_client
):
    """`US-INT-005` §1 — the mailbox that signed in is the mailbox that can
    send, so the provider's answer wins over the form."""
    post_connect(brazos, dana, MAILBOX, MAILBOX_FIELDS)
    started = _start(brazos, dana)
    with tenant_ctx(brazos):
        row = oauth.complete(
            actor=dana,
            tenant_id=brazos.id,
            provider_key=MAILBOX,
            code="recorded-auth-code",
            state=started["state"],
            now=NOW,
            exchange=_recorded(),
        )
    assert MAILBOX_FIELDS["send_from"] == "typed@brazosbend.example"
    assert row.config["send_from"] == "billing@brazosbend.example", (
        "the provider's signed-in address replaced the typed one"
    )


def test_re_authorising_writes_v2_on_the_same_row_and_keeps_every_run(
    brazos, dana, microsoft_adapter, registered_client
):
    """`BR-INT-042`'s exit test, driven through the REAL return trip."""
    post_connect(brazos, dana, MAILBOX, MAILBOX_FIELDS)
    first = _start(brazos, dana)
    with tenant_ctx(brazos):
        row = oauth.complete(
            actor=dana, tenant_id=brazos.id, provider_key=MAILBOX,
            code="c1", state=first["state"], now=NOW, exchange=_recorded(),
        )
        for _ in range(20):
            run = services.start_run(
                connection=row, operation="send_message",
                direction="outbound", trigger="dispatcher",
            )
            services.finish_run(run, attempted=1, succeeded=1, failed=0, skipped=0, confirmed=True)
        before_id = row.id

    second = _start(brazos, dana)
    with tenant_ctx(brazos):
        again = oauth.complete(
            actor=dana, tenant_id=brazos.id, provider_key=MAILBOX,
            code="c2", state=second["state"], now=NOW, exchange=_recorded(),
        )
        versions = list(
            models.IntegrationCredential.objects.filter(connection=again).order_by("version")
        )
        runs = models.IntegrationRun.objects.filter(connection=again).count()

    assert again.id == before_id, "v2 on the SAME connection — never a second one"
    assert [one.version for one in versions] == [1, 2]
    assert [one.is_active for one in versions] == [False, True], "v1 retained, not overwritten"
    assert runs == 20, "every earlier run is still listed on S142"


# ── the guard that is not decorative ────────────────────────────────────────


def test_a_return_trip_with_the_wrong_state_is_refused_before_the_code_is_exchanged(
    brazos, dana, microsoft_adapter, registered_client
):
    """An unsolicited return is an attacker binding THEIR mailbox to THIS
    utility's connection, after which every bill leaves through a mailbox
    somebody else reads. The exchanger must never even be called."""
    post_connect(brazos, dana, MAILBOX, MAILBOX_FIELDS)
    _start(brazos, dana)
    called: list[str] = []

    def must_not_run(**kwargs):  # pragma: no cover — the assertion is that it is not
        called.append("exchanged")
        raise AssertionError("the code was exchanged despite a bad state")

    with tenant_ctx(brazos), pytest.raises(errors.BizError) as refusal:
        oauth.complete(
            actor=dana, tenant_id=brazos.id, provider_key=MAILBOX,
            code="stolen-code", state="not-the-nonce-we-minted", now=NOW,
            exchange=must_not_run,
        )
    assert refusal.value.message_key == oauth.REFUSAL_OAUTH_STATE
    assert called == [], "refused BEFORE the exchange, not after"


def test_an_empty_state_on_both_sides_is_refused_rather_than_compared_equal(
    brazos, dana, microsoft_adapter, registered_client
):
    """The classic way a CSRF guard becomes decorative: `None == None`."""
    post_connect(brazos, dana, MAILBOX, MAILBOX_FIELDS)
    with tenant_ctx(brazos), pytest.raises(errors.BizError) as refusal:
        oauth.complete(
            actor=dana, tenant_id=brazos.id, provider_key=MAILBOX,
            code="c", state="", now=NOW, exchange=_recorded(),
        )
    assert refusal.value.message_key == oauth.REFUSAL_OAUTH_STATE


def test_the_nonce_is_spent_so_one_authorisation_cannot_be_replayed(
    brazos, dana, microsoft_adapter, registered_client
):
    post_connect(brazos, dana, MAILBOX, MAILBOX_FIELDS)
    started = _start(brazos, dana)
    with tenant_ctx(brazos):
        oauth.complete(
            actor=dana, tenant_id=brazos.id, provider_key=MAILBOX,
            code="c1", state=started["state"], now=NOW, exchange=_recorded(),
        )
        with pytest.raises(errors.BizError) as refusal:
            oauth.complete(
                actor=dana, tenant_id=brazos.id, provider_key=MAILBOX,
                code="c1", state=started["state"], now=NOW, exchange=_recorded(),
            )
    assert refusal.value.message_key == oauth.REFUSAL_OAUTH_STATE


def test_a_provider_that_returns_no_refresh_token_is_refused_rather_than_stored(
    brazos, dana, microsoft_adapter, registered_client
):
    """A credential written from an access token works for an hour and fails on
    a Friday. Refusing is the only honest move."""
    post_connect(brazos, dana, MAILBOX, MAILBOX_FIELDS)
    started = _start(brazos, dana)
    no_refresh = {"token_type": "Bearer", "expires_in": 3599, "access_token": "1.ONLY-AN-ACCESS"}
    with tenant_ctx(brazos), pytest.raises(errors.BizError) as refusal:
        oauth.complete(
            actor=dana, tenant_id=brazos.id, provider_key=MAILBOX,
            code="c", state=started["state"], now=NOW,
            exchange=_recorded(payload=no_refresh),
        )
    assert refusal.value.message_key == oauth.REFUSAL_OAUTH_NO_TOKEN
    with tenant_ctx(brazos):
        assert not models.IntegrationCredential.objects.filter(is_active=True).exists()


# ── the two providers differ by DATA and by nothing else ────────────────────


def test_google_falls_back_to_the_manifest_lifetime_because_it_states_none(
    brazos, dana, registered_client
):
    """The asymmetry the two recordings exist for: Microsoft states its consent
    window, Google does not, and `grant_from_payload` has both branches."""
    google = REGISTRY.require("email_google")
    grant = oauth_fixtures.recorded_exchange(
        manifest=google, code="c", redirect_uri=RETURN_TO, now=NOW
    )
    microsoft = REGISTRY.require(MAILBOX)
    other = oauth_fixtures.recorded_exchange(
        manifest=microsoft, code="c", redirect_uri=RETURN_TO, now=NOW
    )
    assert grant.expires_at == NOW + timedelta(days=90), "the manifest's default"
    assert other.expires_at == NOW + timedelta(days=90), "the provider's own figure"
    # Same answer, two different ROUTES to it — which is why both are asserted.
    assert "refresh_token_expires_in" in oauth_fixtures.MICROSOFT_TOKEN_RESPONSE
    assert "refresh_token_expires_in" not in oauth_fixtures.GOOGLE_TOKEN_RESPONSE


def test_no_token_string_reaches_the_card_or_the_audit_trail(
    brazos, dana, microsoft_adapter, registered_client, audit_rows
):
    """`BR-INT-003`, at the one point in the product where a mailbox token
    exists in the clear."""
    from tests.test_us_int_helpers_b import card

    post_connect(brazos, dana, MAILBOX, MAILBOX_FIELDS)
    started = _start(brazos, dana)
    with tenant_ctx(brazos):
        oauth.complete(
            actor=dana, tenant_id=brazos.id, provider_key=MAILBOX,
            code="c", state=started["state"], now=NOW, exchange=_recorded(),
        )
    token = oauth_fixtures.MICROSOFT_TOKEN_RESPONSE["refresh_token"]
    payload = json.dumps(card(brazos, dana, MAILBOX), default=str)
    trail = json.dumps([str(one) for one in audit_rows], default=str)
    assert token not in payload
    assert token not in trail
    assert "RECORDED-REFRESH-TOKEN" not in payload
    assert "RECORDED-REFRESH-TOKEN" not in trail


def test_the_adapters_expose_the_protocols_four_methods_and_no_fifth():
    """The conformance rule, asserted for the two new adapters. A fifth public
    method is how an adapter starts holding provider policy that belongs in the
    manifest."""
    from apps.integrations.adapters.base import PROTOCOL_METHODS
    from apps.integrations.adapters.email_google import EmailGoogleAdapter
    from apps.integrations.adapters.email_microsoft import EmailMicrosoftAdapter

    for adapter in (EmailMicrosoftAdapter, EmailGoogleAdapter):
        public = {
            name
            for name in dir(adapter)
            if not name.startswith("_") and callable(getattr(adapter, name))
        }
        assert public == PROTOCOL_METHODS, f"{adapter.__name__} exposes {public}"
