# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-005 (EP-INT-07) — BYO mailbox: "Send bills from is the
#           signed-in identity (the tenant's OWN address)", CR-069 wave H, H1
# Rules:    BR-INT-005 (BYO mailbox — no shared platform sender) · BR-INT-047
#           (a refresh token is exchanged for a short-lived one at send time;
#           the short one is never written to the credential table) ·
#           BR-INT-003 (the plaintext exists at one point, for one call) ·
#           BR-INT-019 (`test()` is the smallest real instance) · BR-INT-037
#           (behaviour comes from the manifest, not from a branch on a key)
# Tests:    06-backend/tests/test_us_int_005_oauth.py
# Impacts:  adapters/email_microsoft.py · adapters/email_google.py (the two
#           thin subclasses) · adapters/__init__.py (two lines in ADAPTERS)
# ───────────────────────────────────────────────────────
"""The shared half of a mailbox you sign in to, rather than type a password for.

WHY THERE IS A BASE CLASS AT ALL
---------------------------------
`adapters/__init__.py` promises that adding a connector is *"ONE file here and
ONE line to `ADAPTERS`"*, which is `P1` — the requester's own test for the whole
change request: *"every time such integration comes we dont want to change our
integration framework."* Microsoft and Google are two files and two lines, and
each file is about thirty lines, because everything they share is here.

⚠ **WHAT THEY SHARE IS THE OAUTH SHAPE; WHAT THEY DO NOT SHARE IS THE SEND
CALL, AND THAT IS THE ONLY THING A SUBCLASS OVERRIDES.** Graph wants a JSON
message at `/me/sendMail`; Gmail wants base64url MIME at `/messages/send`. Both
are one URL and one body-builder, so each subclass is that pair and nothing
else. There is no `if provider_key ==` anywhere in this module (`G77`).

TOKENS: WHAT IS STORED AND WHAT IS NOT (BR-INT-047)
----------------------------------------------------
The credential row holds a **refresh token** — the durable consent, the thing
`expires_at` is about, the thing `BR-INT-042`'s warning counts down to. It is
handed to this adapter for the length of one call by `services.credential_
secrets` and dropped by the caller's `finally`.

The **access token** is minted from it here, in memory, used, and discarded.
It is never returned, never logged, never written, and never put on a run row.
`US-INT-036` states the guarantee in its own words for the walk connector: *"in
memory, re-minted mid-walk, one credential row after two hours"* — the same
rule, and this is the mailbox's version of it.

⚠ **A FAILED SIGN-IN IS A `TestResult`, NEVER AN EXCEPTION** (`adapters/base.py`
is explicit: *"Never raises for a provider's refusal"*). A lapsed consent comes
back from Microsoft as `invalid_grant`, and a clerk needs to read *"Microsoft
needs re-authorising"* rather than see a stack trace — which is also exactly the
sentence `BR-INT-042` asks the lapse path to produce.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

from apps.integrations.adapters import email_format
from apps.integrations.adapters.base import (
    ITEM_FAILED,
    ITEM_SUCCEEDED,
    Adapter,
    ConnectionView,
    FieldError,
    ItemResult,
    RunResult,
    TestResult,
)

#: The one field name a credential payload uses for the durable consent.
#: Imported rather than re-typed so the writer (`oauth.complete`) and the
#: reader (here) cannot drift apart on a string.
REFRESH_TOKEN_FIELD = "refresh_token"

#: ≤ 6 words each (B14 rule 33). These reach a clerk on the card.
SENTENCE_NEEDS_REAUTH = "This mailbox needs re-authorising."
SENTENCE_UNREACHABLE = "The mailbox could not be reached."
SENTENCE_NO_CONSENT = "Sign in to this mailbox first."


class OAuthMailboxAdapter(Adapter):
    """Everything Microsoft 365 and Google Workspace do the same way."""

    #: Set by each subclass. `token_url` is read from the MANIFEST rather than
    #: declared here — one statement of where a provider lives (registry.py's
    #: `OAuthEndpoints`), which `oauth.py` also reads.
    key: ClassVar[str]
    #: The provider's own name for the card's tail — *· Microsoft 365*.
    provider_label: ClassVar[str] = ""
    #: Where a composed message is POSTed once we hold an access token.
    send_url: ClassVar[str] = ""

    # ── the protocol's four, and nothing else (PROTOCOL_METHODS) ────────────

    def validate(self, config: Mapping[str, Any]) -> list[FieldError]:
        """Nothing to check that the manifest has not already checked.

        `send_from` is declared `email` and `validate_fields` has run the shape
        check; whether that mailbox EXISTS is not answerable without the
        network, and `BR-INT-019` says the network question is `test()`'s.
        Returning `[]` here is a finding, not a stub.
        """
        return []

    def test(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        *,
        recipient: str | None = None,
    ) -> TestResult:
        """One real message to a typed address (`test_needs_recipient=True`)."""
        refresh = secrets.get(REFRESH_TOKEN_FIELD)
        if not refresh:
            # No consent at all — the connection exists but nobody signed in.
            return TestResult(ok=False, sentence=SENTENCE_NO_CONSENT)
        sender = str(conn.config.get("send_from") or "")
        to = recipient or sender
        try:
            token = self._access_token(conn, refresh)
        except _ConsentLapsed as lapsed:
            return TestResult(
                ok=False, sentence=SENTENCE_NEEDS_REAUTH, provider_text=lapsed.provider_text
            )
        except Exception as exc:  # noqa: BLE001 — a provider's silence is an outcome
            return TestResult(ok=False, sentence=SENTENCE_UNREACHABLE, provider_text=str(exc)[:200])
        try:
            self._send_one(token, sender=sender, to=to, subject="Test message", body="Test message.")
        except Exception as exc:  # noqa: BLE001
            return TestResult(ok=False, sentence=SENTENCE_UNREACHABLE, provider_text=str(exc)[:200])
        return TestResult(ok=True, sentence=f"Sent one test message to {to}.")

    def execute(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        work: Sequence[Mapping[str, Any]],
    ) -> RunResult:
        """One attempt at a batch, one outcome per message.

        ⚠ **ONE ACCESS TOKEN FOR THE WHOLE BATCH.** Minting one per message
        would be 240 token calls to send 240 bills, and a provider rate-limits
        the token endpoint harder than the send endpoint. It is minted once,
        held in a local, and goes out of scope with the frame.
        """
        rows = list(work)
        refresh = secrets.get(REFRESH_TOKEN_FIELD)
        if not refresh:
            return RunResult(
                items=tuple(
                    ItemResult(
                        ref=str(one.get("ref", index)),
                        outcome=ITEM_FAILED,
                        provider_text=SENTENCE_NO_CONSENT,
                    )
                    for index, one in enumerate(rows)
                ),
                confirmed=True,
            )
        try:
            token = self._access_token(conn, refresh)
        except Exception as exc:  # noqa: BLE001 — every item fails for one reason
            text = (
                SENTENCE_NEEDS_REAUTH
                if isinstance(exc, _ConsentLapsed)
                else SENTENCE_UNREACHABLE
            )
            return RunResult(
                items=tuple(
                    ItemResult(
                        ref=str(one.get("ref", index)), outcome=ITEM_FAILED, provider_text=text
                    )
                    for index, one in enumerate(rows)
                ),
                confirmed=True,
            )
        sender = str(conn.config.get("send_from") or "")
        items: list[ItemResult] = []
        for index, one in enumerate(rows):
            ref = str(one.get("ref", index))
            # ⚠ **THE RENDER'S WORDS OR NOTHING (`DEF-NOT-10420`).** This read
            # `str(one.get("subject") or "")` and `str(one.get("body") or "")`,
            # so a message with no subject went out with an empty one and a dict
            # handed over as the body went out as its own `repr`. `compose`
            # refuses both; the item fails in our words and nothing is dialled.
            try:
                content = email_format.compose(subject=one.get("subject"), body=one.get("body"))
            except email_format.EmailContentMissing as missing:
                items.append(
                    ItemResult(ref=ref, outcome=ITEM_FAILED, provider_text=missing.sentence)
                )
                continue
            try:
                self._send_one(
                    token,
                    sender=sender,
                    to=str(one.get("address") or ""),
                    subject=content.subject,
                    body=content.text,
                    # `DEF-NOT-10460` — the stored files the row encloses.
                    attachments=list(one.get("attachments") or ()),
                    # `DEF-NOT-10571` — the wrapper's `<html lang>`.
                    language=one.get("language"),
                    # `CR-199-BRC10` S6 — the render's branded HTML part,
                    # passed only when there is one, so a subclass whose
                    # `_send_one` predates it keeps working unchanged.
                    **({"html": one["html"]} if one.get("html") else {}),
                )
            except Exception as exc:  # noqa: BLE001 — per-item, never the batch
                items.append(
                    ItemResult(ref=ref, outcome=ITEM_FAILED, provider_text=str(exc)[:200])
                )
            else:
                items.append(ItemResult(ref=ref, outcome=ITEM_SUCCEEDED))
        return RunResult(items=tuple(items), confirmed=True)

    def describe(self, conn: ConnectionView) -> str:
        """*billing@brazosbend.example · Microsoft 365* — the card's line."""
        return f"{conn.config.get('send_from') or '—'} · {self.provider_label}"

    # ── private: everything below is invisible to the conformance kit ───────

    def _token_url(self) -> str:
        """The manifest's own `token_url`. Read at call time so a registry with
        a fixture manifest bound is the registry this obeys."""
        from apps.integrations.registry import REGISTRY

        endpoints = REGISTRY.require(self.key).auth.oauth
        if endpoints is None:  # pragma: no cover — validate() refuses this at load
            raise RuntimeError(f"{self.key} declares no oauth endpoints")
        return endpoints.token_url

    def _access_token(self, conn: ConnectionView, refresh: str) -> str:  # pragma: no cover
        """Refresh → access, in memory, for this call only (BR-INT-047).

        Not covered by the suite on purpose: it is the socket. Every RULE around
        it — that a lapsed consent becomes `SENTENCE_NEEDS_REAUTH` rather than an
        exception, that no token is returned or stored — is asserted through
        the recorded subclasses in `conformance.py`, which override exactly this
        method and nothing else.
        """
        from django.conf import settings

        registration = (getattr(settings, "INTEGRATION_OAUTH_CLIENTS", {}) or {}).get(self.key, {})
        body = urllib.parse.urlencode(
            {
                "client_id": registration.get("client_id", ""),
                "client_secret": registration.get("client_secret", ""),
                "refresh_token": refresh,
                "grant_type": "refresh_token",
            }
        ).encode()
        request = urllib.request.Request(
            self._token_url(),
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as answer:
                payload = json.loads(answer.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:200]
            # `invalid_grant` is the provider's word for *this consent is over*
            # — a lapse, not an outage, and the two need different sentences.
            if "invalid_grant" in detail:
                raise _ConsentLapsed(detail) from exc
            raise
        token = payload.get("access_token")
        if not token:
            raise _ConsentLapsed("no access token in the token response")
        return str(token)

    def _send_one(
        self,
        token: str,
        *,
        sender: str,
        to: str,
        subject: str,
        body: str,
        attachments: Sequence[Mapping[str, Any]] = (),
        language: str | None = None,
        html: str | None = None,
    ) -> None:  # pragma: no cover — the socket; see `_access_token`
        message = self._message(
            sender=sender,
            to=to,
            subject=subject,
            body=body,
            attachments=attachments,
            language=language,
            # Only when there is one, so a subclass `_message` that predates
            # `CR-199-BRC10` keeps working unchanged.
            **({"html": html} if html else {}),
        )
        request = urllib.request.Request(
            self.send_url,
            data=json.dumps(message).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=60):
            return

    def _message(
        self,
        *,
        sender: str,
        to: str,
        subject: str,
        body: str,
        attachments: Sequence[Mapping[str, Any]] = (),
        language: str | None = None,
        html: str | None = None,
    ) -> dict[str, Any]:
        """The provider's own message shape — the ONE thing a subclass owns.

        `attachments` are `[{filename, content_type, content: bytes}]`
        (`DEF-NOT-10460`); each subclass puts them in its own shape with
        `apps.integrations.email_attachments`.

        `subject` and `body` are the rendered subject and PLAIN-TEXT body; a
        subclass builds its HTML alternative from them with
        `email_format.compose`, never by labelling the plain text as HTML (which
        collapsed every line break until `DEF-NOT-10420`).
        """
        raise NotImplementedError


class _ConsentLapsed(Exception):
    """The provider says this consent is over. Becomes a sentence, not a trace."""

    def __init__(self, provider_text: str = "") -> None:
        super().__init__(provider_text)
        self.provider_text = provider_text


__all__ = [
    "REFRESH_TOKEN_FIELD",
    "SENTENCE_NEEDS_REAUTH",
    "SENTENCE_NO_CONSENT",
    "SENTENCE_UNREACHABLE",
    "OAuthMailboxAdapter",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-005 (EP-INT-07 — BYO mailbox) · BR-INT-005 · BR-INT-047
# generated: 2026-09-06 by the CR-069 wave H build lane
# checklist: A✔ B=n/a C✔ D=n/a E✔(the card's describe line and Test it now reach this) F✔ G✔ H=deferred(🔒 — it holds a customer's refresh token for one call; row in 09-human-review-ledger.md)
# gates: pytest tests/test_us_int_005_oauth.py · conformance kit (four public methods and no fifth) · G77 (no provider_key branch)
# exceptions: `_access_token` and `_send_one` are the two network calls and are the only uncovered lines; the recorded subclasses in conformance.py override exactly those and every rule around them is asserted through those
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
