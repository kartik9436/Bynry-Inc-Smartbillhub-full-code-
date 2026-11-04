# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-005 (EP-INT-07) — "recorded fixtures, no network in tests",
#           CR-069 wave H task H1
# Rules:    BR-INT-019 (`test()` is the smallest real instance) · BR-INT-003
#           (a secret never leaves this module in the clear)
# Tests:    06-backend/tests/test_us_int_005_oauth.py
# Impacts:  apps/integrations/oauth.py (`complete(exchange=…)`) ·
#           10-scripts/render-checks/cr069-h-token-lapse.mjs (the walkthrough
#           drives the same recording through the real endpoint)
# ───────────────────────────────────────────────────────
"""Recorded provider answers, so no test ever dials Microsoft.

WHY A FILE AND NOT A `mock.patch`
----------------------------------
`oauth.complete()` takes its exchanger as an ARGUMENT. A test that patched a
module attribute instead would keep passing on the day somebody changed the
name it patched, and the path it is covering is the one that stores a real
customer's mailbox credential. An argument cannot silently stop being used.

WHAT THESE ARE
--------------
The shapes below are the token responses Microsoft and Google document, reduced
to the keys `oauth.grant_from_payload` actually reads. They are RECORDINGS in
the sense that matters — the field names and their types are the provider's,
not ours — and they are deliberately NOT real tokens: the values are obviously
synthetic so that nobody can mistake a fixture for a leaked secret, which is a
mistake that has cost other projects a credential rotation.

⚠ **THE MICROSOFT RECORDING CARRIES `refresh_token_expires_in` AND THE GOOGLE
ONE DOES NOT, AND THAT ASYMMETRY IS THE POINT OF HAVING BOTH.** It is what
exercises the two halves of `grant_from_payload`: a provider that states its
consent lifetime, and a provider that says nothing and falls back to the
manifest's `default_lifetime_days`. A single fixture would have covered one
branch and left the other to the first real utility to find.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.utils import timezone

from apps.integrations import oauth
from apps.integrations.registry import Manifest

#: Ninety days, in seconds — Microsoft's consent window, stated by Microsoft.
NINETY_DAYS_SECONDS = 90 * 24 * 60 * 60

#: ⚠ Synthetic by construction. `1.` prefixes and the word `RECORDED` make it
#: impossible to mistake either of these for a live token in a grep or a log.
MICROSOFT_TOKEN_RESPONSE: dict[str, Any] = {
    "token_type": "Bearer",
    # The access token's own hour. `grant_from_payload` deliberately does NOT
    # read this as the credential's expiry — see its docstring.
    "expires_in": 3599,
    "refresh_token_expires_in": NINETY_DAYS_SECONDS,
    "access_token": "1.RECORDED-ACCESS-TOKEN-NOT-A-REAL-CREDENTIAL",
    "refresh_token": "1.RECORDED-REFRESH-TOKEN-NOT-A-REAL-A17C",
    "scope": "https://graph.microsoft.com/Mail.Send offline_access",
    "account": "billing@brazosbend.example",
}

GOOGLE_TOKEN_RESPONSE: dict[str, Any] = {
    "token_type": "Bearer",
    "expires_in": 3599,
    # No `refresh_token_expires_in` — Google does not send one. The manifest's
    # `default_lifetime_days` is what dates the warning for this provider.
    "access_token": "1.RECORDED-ACCESS-TOKEN-NOT-A-REAL-CREDENTIAL",
    "refresh_token": "1.RECORDED-REFRESH-TOKEN-NOT-A-REAL-B28D",
    "scope": "https://www.googleapis.com/auth/gmail.send",
    "email": "billing@brazosbend.example",
}

RECORDINGS: dict[str, dict[str, Any]] = {
    "email_microsoft": MICROSOFT_TOKEN_RESPONSE,
    "email_google": GOOGLE_TOKEN_RESPONSE,
}


def recorded_exchange(
    *,
    manifest: Manifest,
    code: str,
    redirect_uri: str,
    now: datetime | None = None,
    payload: dict[str, Any] | None = None,
) -> oauth.TokenGrant:
    """Stand in for the network call, through the REAL parsing path.

    ⚠ It calls `oauth.grant_from_payload`, which is the same function
    `_http_exchange` calls. So a test using this exercises every line of the
    token handling except the socket — which is the only line a recording
    cannot cover and the only one that has nothing to do with our rules.

    `payload` lets a test hand in a deliberately awkward answer (no refresh
    token, say) without inventing a second exchanger.
    """
    answer = payload if payload is not None else RECORDINGS.get(manifest.key)
    if answer is None:  # pragma: no cover — a manifest with no recording
        raise KeyError(
            f"no recorded OAuth response for {manifest.key!r}; add one here rather than "
            "letting a test reach the network"
        )
    endpoints = manifest.auth.oauth
    return oauth.grant_from_payload(
        answer, endpoints=endpoints, now=timezone.now() if now is None else now
    )


__all__ = [
    "GOOGLE_TOKEN_RESPONSE",
    "MICROSOFT_TOKEN_RESPONSE",
    "NINETY_DAYS_SECONDS",
    "RECORDINGS",
    "recorded_exchange",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-005 (EP-INT-07 — "recorded fixtures, no network in tests")
# generated: 2026-09-06 by the CR-069 wave H build lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=n/a(the values are synthetic by construction and say so)
# gates: pytest tests/test_us_int_005_oauth.py · a grep for `urlopen` in the suite returns nothing from this path
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
