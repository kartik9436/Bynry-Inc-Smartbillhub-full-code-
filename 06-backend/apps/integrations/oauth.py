# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-005 (EP-INT-07) — BYO mailbox, the tenant's OWN address ·
#           US-INT-027 — re-authorising keeps the whole run history.
#           CR-069 wave H task H1. Screens: S141 (frame 49.2) · S142
# Rules:    BR-INT-043 (auth has a placement and a MODE, declared per
#           operation; the modal is generated from the manifest — "no code
#           branched to make that true") · BR-INT-005 (BYO mailbox; all
#           customer email from the tenant's own address) · BR-INT-025 (a
#           credential is versioned, never updated; one active) · BR-INT-003
#           (the plaintext exists at one point, for one call) · BR-INT-042
#           (a renewal path that keeps the connection's whole run history) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 7 (audit)
# Tests:    06-backend/tests/test_us_int_005_oauth.py
# Impacts:  apps/integrations/api.py (start + return) · services.py (re-exports
#           so the neighbour's address does not move) · registry.py
#           (`OAuthEndpoints`, the data this reads)
# ───────────────────────────────────────────────────────
"""The sign-in redirect — one round trip, every provider, no branch.

WHAT MAKES THIS FILE SHORT
---------------------------
`BR-INT-043` asks for a connect modal *"generated from the manifest's field
list using a closed vocabulary of field kinds"*, and names the redirect as one
of the three a plain field cannot express: *"a redirect (OAuth — the body is a
button and a return trip)"*. It ends with the sentence that decides this file's
shape: **"no code branched to make that true."**

So there is no `MicrosoftOAuth` class and no `if provider_key == "email_google"`.
There is `Manifest.auth.oauth` — an `OAuthEndpoints` carrying an authorize URL,
a token URL and the scopes we ask for — and the two functions below read it.
Adding Google's mailbox was adding that object to `manifests/email_google.py`
and nothing else, which is `P1`, the requester's own test for the whole change
request: *"every time such integration comes we dont want to change our
integration framework."*

⚠ **IT IS DATA RATHER THAN AN ADAPTER METHOD BECAUSE THE PROTOCOL HAS EXACTLY
FOUR METHODS AND THE CONFORMANCE KIT REFUSES A FIFTH** (`adapters/base.py`,
`PROTOCOL_METHODS`). That constraint pushed the design to the better place.

THE TWO HALVES, AND WHAT EACH IS ALLOWED TO TOUCH
--------------------------------------------------
`start()` builds the URL a person is sent to and mints the `state`. It writes
NO credential — there is nothing to write yet — and it does not create the
connection either.

`complete()` is the return trip. It exchanges the code and writes credential
**v(n+1) on the SAME connection row**, which is the whole of the wave's exit
test. It does that through `services.record_credential`, unchanged, which is
why the history survives: that function deactivates version n and inserts
n+1 against the same `connection_id`, and `integration_run` rows point at the
CONNECTION and not at the credential. **Nothing here deletes a run, and nothing
here creates a second connection.** Twenty runs from before re-authorising are
still twenty runs after it, because no code path exists that could remove one.

⚠ **THE STATE PARAMETER IS A CSRF GUARD AND IT IS CHECKED, NOT DECORATIVE.**
An unsolicited `GET /oauth/return?code=…` is an attacker inviting us to bind
THEIR mailbox to THIS utility's connection — after which every bill the utility
sends leaves through a mailbox somebody else reads. The state is minted here,
kept on the connection's NON-SECRET `config`, and a return trip whose state
does not match the one we minted is refused before the code is exchanged.

⚠ **WHAT WE STORE IS THE REFRESH TOKEN, NOT THE ACCESS TOKEN (BR-INT-047).**
The access token lives about an hour; storing it would mean a credential row
that lapses over lunch and a warning sweep that shouted every day. The refresh
token is the durable consent, and `expires_at` on the credential is when that
CONSENT runs out — which is what a clerk is being warned about and is the date
frame 54.1 puts in the sentence.

⚠ **NO NETWORK IN TESTS, AND THE SEAM FOR THAT IS AN ARGUMENT RATHER THAN A
MONKEYPATCH.** `complete()` takes an `exchange` callable defaulting to the real
HTTP one. `oauth_fixtures.recorded_exchange` is a recorded provider response;
tests pass it in. A test that patched a module attribute would pass while the
real path was broken, and the real path is the one that stores a customer's
credential.
"""

from __future__ import annotations

import json
import secrets as secrets_module
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable
from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone

from apps.integrations import models, services
from apps.integrations.registry import REGISTRY, Manifest, Registry
from core import audit as core_audit, errors

#: `config` keys the round trip owns. NON-SECRET by construction — a one-time
#: nonce and the address we asked the provider to send the person back to.
#: `services.connect` guards that `config` never holds secret material, and
#: neither of these is one.
CONFIG_STATE = "oauth_state"
CONFIG_REDIRECT_URI = "oauth_redirect_uri"

#: The secret field name credential payloads use for the durable consent. One
#: name, so `credential_secrets` hands an adapter the same key whatever
#: provider minted it.
REFRESH_TOKEN_FIELD = "refresh_token"

#: Refusals — catalogue keys, ≤ 6 words each (B14 rule 33), resolved in all
#: eleven catalogues (G32).
REFUSAL_OAUTH_STATE = "integrations.refusal.oauth_state"
REFUSAL_OAUTH_DENIED = "integrations.refusal.oauth_denied"
REFUSAL_OAUTH_NO_TOKEN = "integrations.refusal.oauth_no_token"
REFUSAL_OAUTH_NOT_CONFIGURED = "integrations.refusal.oauth_not_configured"

AUDIT_OAUTH_STARTED = "integration.oauth_started"
AUDIT_OAUTH_RETURNED = "integration.oauth_returned"


@dataclass(frozen=True)
class TokenGrant:
    """What a provider hands back. **No access token is kept** — see above."""

    refresh_token: str
    expires_at: datetime | None = None
    #: The mailbox the person actually signed in as. `US-INT-005` §1 asks for
    #: *Send bills from* to be the SIGNED-IN identity rather than something a
    #: clerk typed, because a mismatch between them is a bounce a utility
    #: cannot diagnose.
    account: str | None = None

    @property
    def masked_hint(self) -> str:
        """`••••A17C` — the display form, and the ONLY form that leaves here."""
        tail = (self.refresh_token or "")[-4:].upper()
        return f"••••{tail}" if tail else "••••"


def _endpoints(manifest: Manifest):
    oauth = manifest.auth.oauth
    if oauth is None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-INT-043",
            message_key=REFUSAL_OAUTH_NOT_CONFIGURED,
            params={"provider": manifest.display_name},
        )
    return oauth


def _client(manifest: Manifest) -> tuple[str, str]:
    """OUR registration with this provider, from settings — never from a file.

    ⚠ Deployment configuration, not repo content: the client secret is a
    secret, and the ids differ between a demo host and production. An absent
    registration is refused BY NAME rather than sending a person to a consent
    screen that will fail with the provider's own opaque error (hard-won law 3
    — the unsafe option must be the one you type).
    """
    registrations = getattr(settings, "INTEGRATION_OAUTH_CLIENTS", {}) or {}
    entry = registrations.get(manifest.key) or {}
    client_id = entry.get("client_id")
    client_secret = entry.get("client_secret")
    if not client_id or not client_secret:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-INT-043",
            message_key=REFUSAL_OAUTH_NOT_CONFIGURED,
            params={"provider": manifest.display_name},
        )
    return str(client_id), str(client_secret)


def start(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    redirect_uri: str,
    registry: Registry = REGISTRY,
) -> dict[str, Any]:
    """`POST /integrations/{key}/oauth/start` — where to send the person.

    Answers `{authorize_url, state}`. The browser goes there; the provider
    brings it back to `redirect_uri` with a code, and `complete()` finishes it.
    """
    manifest = services._live_manifest(actor, provider_key, route="oauth_start", registry=registry)
    endpoints = _endpoints(manifest)
    client_id, _ = _client(manifest)
    row = services._connected_or_refuse(tenant_id, provider_key)

    # A fresh nonce per attempt. `token_urlsafe(32)` is 256 bits — the same
    # generator `services` already uses for issued secrets.
    state = secrets_module.token_urlsafe(32)
    config = dict(row.config or {})
    config[CONFIG_STATE] = state
    config[CONFIG_REDIRECT_URI] = redirect_uri
    row.config = config
    row.save(update_fields=["config", "updated_at"])

    query = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": " ".join(endpoints.scopes),
        # Without this Microsoft returns an access token only and no refresh
        # token, and the connection would lapse in an hour with no way back.
        "access_type": "offline",
        "prompt": "consent",
    }
    core_audit.money_action(
        actor,
        AUDIT_OAUTH_STARTED,
        "integration_connection",
        row.id,
        after={"provider_key": manifest.key, "redirect_uri": redirect_uri},
    )
    return {
        "authorize_url": f"{endpoints.authorize_url}?{urlencode(query)}",
        # The caller echoes this back; it is a nonce, not a secret to protect.
        "state": state,
    }


def _http_exchange(
    *, manifest: Manifest, code: str, redirect_uri: str
) -> TokenGrant:  # pragma: no cover — the network path; tests inject a recording
    """The real token exchange. Never reached by the suite (see the docstring)."""
    import urllib.request

    endpoints = _endpoints(manifest)
    client_id, client_secret = _client(manifest)
    body = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode()
    request = urllib.request.Request(
        endpoints.token_url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    with urllib.request.urlopen(request, timeout=30) as answer:
        payload = json.loads(answer.read().decode())
    return grant_from_payload(payload, endpoints=endpoints, now=timezone.now())


def grant_from_payload(payload: dict[str, Any], *, endpoints, now: datetime) -> TokenGrant:
    """A provider's token response → the two things we keep.

    ⚠ **`expires_in` ON A TOKEN RESPONSE IS THE ACCESS TOKEN'S HOUR, NOT THE
    CONSENT'S NINETY DAYS**, and reading it as the credential's `expires_at`
    is the subtle way to get this wrong: every connection would show *Needs
    re-authorising* an hour after it was made, the sweep would warn daily, and
    a clerk would learn to ignore the box before the first real lapse. So the
    access token's lifetime is deliberately NOT read here. `refresh_token_
    expires_in` — which Microsoft does send — IS the consent, and where a
    provider sends nothing the manifest's `default_lifetime_days` stands in.
    """
    refresh = payload.get("refresh_token")
    if not refresh:
        # No durable consent came back. Refusing is the only honest move: a
        # credential row written from an access token would work for an hour
        # and then fail on a Friday.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-INT-047",
            message_key=REFUSAL_OAUTH_NO_TOKEN,
            params={},
        )
    consent_seconds = payload.get("refresh_token_expires_in")
    if consent_seconds:
        expires_at = now + timedelta(seconds=int(consent_seconds))
    else:
        expires_at = now + timedelta(days=int(endpoints.default_lifetime_days))
    account = payload.get("account") or payload.get("email") or None
    return TokenGrant(refresh_token=str(refresh), expires_at=expires_at, account=account)


def _default_exchanger() -> Callable[..., TokenGrant]:
    """The real network call, unless a walkthrough has asked for the recording.

    ⚠ **THIS HOOK EXISTS BECAUSE AN OAUTH ROUND TRIP CANNOT BE WALKED IN A
    BROWSER OTHERWISE.** `10-scripts/render-checks/cr069-h-token-lapse.mjs` has
    to press the real `POST /oauth/start`, take the real state nonce and call
    the real `GET /oauth/return` — that is the whole point of a rendered-output
    check (hard-won law 6). The only alternative would be dialling
    `login.microsoftonline.com` from a walkthrough, which is not ours to dial.

    ⚠ **AND IT FAILS CLOSED, WHICH IS HARD-WON LAW 3.** The unsafe option is
    the one you type: the flag defaults to False, and it is REFUSED outright
    when `DEBUG` is off. A production deployment that somehow carried the flag
    would raise here rather than quietly store a synthetic token as a real
    utility's mailbox consent — which is the failure this guard is for, and it
    is louder than the mistake it prevents.
    """
    if not getattr(settings, "INTEGRATION_OAUTH_RECORDED", False):
        return _http_exchange
    if not getattr(settings, "DEBUG", False):
        raise RuntimeError(
            "INTEGRATION_OAUTH_RECORDED is set with DEBUG off. The recorded token "
            "exchange is a walkthrough fixture; storing it as a real credential would "
            "give a utility a mailbox consent that cannot send anything."
        )
    from apps.integrations import oauth_fixtures

    return oauth_fixtures.recorded_exchange


def complete(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    code: str,
    state: str,
    now: datetime | None = None,
    registry: Registry = REGISTRY,
    exchange: Callable[..., TokenGrant] | None = None,
) -> models.IntegrationConnection:
    """`GET /integrations/{key}/oauth/return` — credential v(n+1), same row.

    THE EXIT TEST OF THE WHOLE WAVE LIVES IN THREE LINES OF THIS FUNCTION:
    `_connected_or_refuse` finds the EXISTING connection, `record_credential`
    writes v(n+1) against it, and nothing touches `integration_run`. There is
    no branch here that creates a connection, so "re-authorising keeps the
    connection's entire run history" is true by construction rather than by a
    test that remembers to check.
    """
    manifest = services._live_manifest(actor, provider_key, route="oauth_return", registry=registry)
    endpoints = _endpoints(manifest)
    row = services._connected_or_refuse(tenant_id, provider_key)
    moment = timezone.now() if now is None else now

    expected = (row.config or {}).get(CONFIG_STATE)
    # ⚠ CONSTANT-TIME, AND BOTH SIDES CHECKED FOR PRESENCE FIRST. A missing
    # expected state must refuse rather than compare `None` with `None` and
    # pass, which is exactly how a CSRF guard becomes decorative.
    if not expected or not state or not secrets_module.compare_digest(str(expected), str(state)):
        core_audit.money_action(
            actor,
            AUDIT_OAUTH_RETURNED,
            "integration_connection",
            row.id,
            after={"provider_key": manifest.key, "accepted": False, "reason": "state mismatch"},
        )
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-INT-043",
            message_key=REFUSAL_OAUTH_STATE,
            params={"provider": manifest.display_name},
        )
    if not code:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-INT-043",
            message_key=REFUSAL_OAUTH_DENIED,
            params={"provider": manifest.display_name},
        )

    redirect_uri = (row.config or {}).get(CONFIG_REDIRECT_URI) or ""
    caller = exchange if exchange is not None else _default_exchanger()
    grant = caller(manifest=manifest, code=code, redirect_uri=redirect_uri)

    config = dict(row.config or {})
    # The nonce is spent. Leaving it would let one authorisation be replayed.
    config.pop(CONFIG_STATE, None)
    if grant.account:
        # `US-INT-005` §1 — *Send bills from* is the signed-in identity. The
        # provider's answer wins over anything typed, because the mailbox that
        # signed in is the mailbox that can send.
        config["send_from"] = grant.account
    row.config = config
    row.status = models.STATUS_UNTESTED
    row.last_test_ok = None
    row.last_test_text = None
    row.save(
        update_fields=["config", "status", "last_test_ok", "last_test_text", "updated_at"]
    )

    # ⚠ THE ONE PLACE THE TOKEN EXISTS AS PLAINTEXT (BR-INT-003), and it is
    # handed straight to the encrypting write. It is not logged, not returned,
    # not put on the audit row and not on this function's return value.
    services.record_credential(
        actor=actor,
        connection=row,
        payload=json.dumps({REFRESH_TOKEN_FIELD: grant.refresh_token}),
        masked_hint=grant.masked_hint,
        expires_at=grant.expires_at,
    )
    core_audit.money_action(
        actor,
        AUDIT_OAUTH_RETURNED,
        "integration_connection",
        row.id,
        after={
            "provider_key": manifest.key,
            "accepted": True,
            "expires_at": None if grant.expires_at is None else grant.expires_at.isoformat(),
            "send_from": grant.account,
        },
    )
    row.refresh_from_db()
    return row


__all__ = [
    "AUDIT_OAUTH_RETURNED",
    "AUDIT_OAUTH_STARTED",
    "CONFIG_REDIRECT_URI",
    "CONFIG_STATE",
    "REFRESH_TOKEN_FIELD",
    "REFUSAL_OAUTH_DENIED",
    "REFUSAL_OAUTH_NOT_CONFIGURED",
    "REFUSAL_OAUTH_NO_TOKEN",
    "REFUSAL_OAUTH_STATE",
    "TokenGrant",
    "complete",
    "grant_from_payload",
    "start",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-005 (EP-INT-07 — BYO mailbox) · US-INT-027 · BR-INT-043 · BR-INT-047
# generated: 2026-09-06 by the CR-069 wave H build lane
# checklist: A✔ B✔ C✔ D✔(POST /oauth/start and GET /oauth/return) E✔(ConnectModal's Sign in with… and S142's Re-authorise press them) F✔ G✔ H=deferred(🔒 — a customer credential is written here; row in 09-human-review-ledger.md)
# gates: pytest tests/test_us_int_005_oauth.py · G32 (four refusal keys resolve in all eleven catalogues) · G77 (no provider_key branch — the endpoints are manifest data)
# exceptions: `_http_exchange` is the only un-covered function and deliberately so — it is the network call, and the suite injects a recorded response instead of reaching Microsoft
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
