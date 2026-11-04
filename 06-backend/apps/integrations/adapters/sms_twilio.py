"""Twilio (text messages) — what is true of Twilio and of nothing else.

HUMAN-OWNED (🔒 sensitive path — CLAUDE.md: credentials, webhook keys).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-29 (`CR-198-BRC10`) under the PO
ruling of 2026-08-09, with a row in `12-governance/09-human-review-ledger.md`.

The four methods every adapter has, over Twilio's Messages API:

  * send     `POST /2010-04-01/Accounts/{AccountSid}/Messages.json`, FORM-encoded
             (`To`, exactly one of `From` / `MessagingServiceSid`, `Body`, and
             `StatusCallback` when the server has a public address). `201` with
             an `SM…` sid is ACCEPTED, never delivered — the sid is kept as the
             provider reference and only a signed callback may write delivered.
  * login    `GET /2010-04-01/Accounts/{AccountSid}.json` — *is this login any
             good*, without texting anybody.
  * test     one real text to a number the admin types.

⚠ **THE CREDENTIAL IS THE PLATFORM'S** (`platform_sms.py`) and arrives as the
`secrets` argument for one call. HTTP Basic: the Account SID with the Auth Token,
or the API key SID with its secret when both are set. Never returned, never in a
sentence, never logged (this module has no logger).

⚠ **NOTHING IN THIS ENVIRONMENT HAS EVER REACHED TWILIO.** Every shape below is
Twilio's published API, and every test runs against a mocked transport. A green
run is evidence about OUR code and about nothing of Twilio's.

OUR SENTENCES AND THEIR WORDS
-----------------------------
A clerk reads one of the sentences below (B14 rule 33 — a FACT, ≤ 6 words, no
code); Twilio's own `code: message` goes underneath as `provider_text`, which is
what support quotes back to them. The codes that decide what WE do:

    20003            wrong login                      retry (ours to fix)
    21211 21614 21217  not a textable number          do NOT retry
    21608            trial account, unverified number do NOT retry
    21610            the person replied STOP          do NOT retry · suppress
    21606 21212 21659  our sender cannot send          retry (ours to fix)
"""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlencode

from apps.integrations.adapters.base import (
    ITEM_FAILED,
    ITEM_SUCCEEDED,
    Adapter,
    ConnectionView,
    FieldError,
    FieldErrors,
    ItemResult,
    RunResult,
    TestResult,
)
from apps.integrations.adapters.esp_email import (
    PROVIDER_TEXT_CAP,
    HttpAnswer,
    Transport,
    _urllib_transport,
)
from apps.integrations.runtime import ProviderTimeout

OP_SEND = "send_message"
OP_VALIDATE = "validate_credentials"
TIMEOUT_SECONDS = 15.0
API_VERSION = "2010-04-01"
DEFAULT_BASE_URL = "https://api.twilio.com"

#: Twilio's codes we act on — named once, read by `refusal()` and by the
#: notifications side through `ItemResult.provider_code`.
CODE_WRONG_LOGIN = "20003"
CODE_BAD_NUMBERS = frozenset({"21211", "21614", "21217", "21401", "21421"})
CODE_TRIAL_UNVERIFIED = "21608"
CODE_OPTED_OUT = "21610"
CODE_SENDER_CANNOT = frozenset({"21606", "21212", "21659", "21602", "21603"})

SENT = "Sent one test text."
LOGIN_OK = "The login works."
WRONG_LOGIN = "The text service refused the login."
BAD_NUMBER = "That phone number cannot get texts."
TRIAL_ACCOUNT = "A trial account texts verified numbers only."
OPTED_OUT = "This person has opted out of texts."
SENDER_CANNOT = "Our sending number cannot send texts."
REFUSED = "The text service refused the message."
NO_ANSWER = "The text service did not answer."
NO_NUMBER = "Type a phone number to text."
NO_SENDER = "No sending number is set up."
NO_BODY = "The text has no words."

#: Twilio's message statuses → our three words. `None` = not an outcome.
IN_TRANSIT = "in_transit"
DELIVERED = "delivered"
FAILED = "failed"
STATUS_MAP: dict[str, str | None] = {
    "accepted": IN_TRANSIT,
    "scheduled": IN_TRANSIT,
    "queued": IN_TRANSIT,
    "sending": IN_TRANSIT,
    "sent": IN_TRANSIT,
    "delivered": DELIVERED,
    "undelivered": FAILED,
    "failed": FAILED,
    "canceled": FAILED,
    "receiving": None,
    "received": None,
    "read": DELIVERED,
}

#: Twilio's standard opt-out words (their Advanced Opt-Out defaults). A message
#: that IS one of these — trimmed, any case — is a STOP. START and HELP are NOT
#: acted on (PO 2026-10-29: *"ONly Stop option is required"*); Twilio answers
#: those at the carrier level.
STOP_KEYWORDS = frozenset({"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"})


def map_status(twilio_status: Any) -> str | None:
    return STATUS_MAP.get(str(twilio_status or "").strip().lower())


def is_stop(body: Any, opt_out_type: Any = None) -> bool:
    """Is this incoming text a STOP? Twilio's own `OptOutType=STOP` (Advanced
    Opt-Out) counts as one too."""
    if str(opt_out_type or "").strip().upper() == "STOP":
        return True
    return str(body or "").strip().upper() in STOP_KEYWORDS


def refusal(code: str | None, status: int) -> tuple[str, bool]:
    """(our sentence, retryable) for one Twilio refusal."""
    if code == CODE_WRONG_LOGIN or status == 401:
        return WRONG_LOGIN, True
    if code in CODE_BAD_NUMBERS:
        return BAD_NUMBER, False
    if code == CODE_TRIAL_UNVERIFIED:
        return TRIAL_ACCOUNT, False
    if code == CODE_OPTED_OUT:
        return OPTED_OUT, False
    if code in CODE_SENDER_CANNOT:
        return SENDER_CANNOT, True
    if status == 429 or status >= 500:
        return NO_ANSWER, True
    if 400 <= status < 500:
        return REFUSED, False
    return REFUSED, True


def _scrubbed(text: str, secrets: Mapping[str, str]) -> str:
    out = text
    for one in secrets.values():
        if one and len(one) >= 4:
            out = out.replace(one, "••••")
    return out[:PROVIDER_TEXT_CAP]


def _their_words(answer: HttpAnswer, secrets: Mapping[str, str]) -> str | None:
    body = answer.body if isinstance(answer.body, Mapping) else {}
    code = body.get("code")
    message = body.get("message")
    if code is not None or message:
        text = f"{code}: {message}" if code is not None else str(message)
    else:
        text = answer.text or f"HTTP {answer.status}"
    return _scrubbed(str(text), secrets) or None


def _code_of(answer: HttpAnswer) -> str | None:
    body = answer.body if isinstance(answer.body, Mapping) else {}
    code = body.get("code")
    return None if code is None else str(code)


class SmsTwilioAdapter(Adapter):
    """Twilio's Messages API. `transport` is the seam a test mocks."""

    key = "sms_twilio"

    def __init__(self, transport: Transport | None = None) -> None:
        self._transport = transport

    # ── the four ───────────────────────────────────────────────────────────
    def validate(self, config: Mapping[str, Any]) -> FieldErrors:
        """Exactly one sender. Both or neither is a configuration a request
        could not be built from."""
        problems: FieldErrors = []
        service = str(config.get("messaging_service_sid") or "").strip()
        number = str(config.get("from_number") or "").strip()
        if bool(service) == bool(number):
            problems.append(FieldError("from_number", message_key="integrations.field.oneSender"))
        if service and not service.upper().startswith("MG"):
            problems.append(
                FieldError("messaging_service_sid", message_key="integrations.field.messagingService")
            )
        return problems

    def test(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        *,
        recipient: str | None = None,
    ) -> TestResult:
        to = (recipient or "").strip()
        if not to:
            return TestResult(ok=False, sentence=NO_NUMBER)
        item = self._send_item(
            conn,
            secrets,
            {"address": to, "body": "Test text from your utility's billing system."},
            "test",
            TIMEOUT_SECONDS,
        )
        if item.outcome == ITEM_SUCCEEDED:
            return TestResult(ok=True, sentence=SENT)
        return TestResult(
            ok=False,
            sentence=item.detail or REFUSED,
            provider_text=item.provider_text or item.detail or REFUSED,
        )

    def execute(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        work: Sequence[Mapping[str, Any]],
    ) -> RunResult:
        items: list[ItemResult] = []
        for index, one in enumerate(work):
            ref = str(one.get("ref", index))
            operation = str(one.get("operation") or OP_SEND)
            timeout_s = float(one.get("timeout_s") or TIMEOUT_SECONDS)
            if operation == OP_SEND:
                items.append(self._send_item(conn, secrets, one, ref, timeout_s))
            elif operation == OP_VALIDATE:
                items.append(self._login_item(conn, secrets, ref, timeout_s))
            else:
                items.append(
                    ItemResult(
                        ref=ref,
                        outcome=ITEM_FAILED,
                        detail=f"{operation} is not one this connector asks for",
                    )
                )
        return RunResult(items=tuple(items), confirmed=True)

    def describe(self, conn: ConnectionView) -> str:
        if conn.config.get("messaging_service_sid"):
            return "Twilio · messaging service"
        if conn.config.get("from_number"):
            return "Twilio · sending number"
        return "Twilio"

    # ── the calls ──────────────────────────────────────────────────────────
    def _base(self, conn: ConnectionView) -> str:
        return str(conn.config.get("base_url") or DEFAULT_BASE_URL).rstrip("/")

    def _account(self, conn: ConnectionView, secrets: Mapping[str, str]) -> str:
        return str(secrets.get("account_sid") or conn.config.get("account_sid") or "").strip()

    def _auth_header(self, conn: ConnectionView, secrets: Mapping[str, str]) -> str:
        key_sid = str(secrets.get("api_key_sid") or "")
        key_secret = str(secrets.get("api_key_secret") or "")
        if key_sid and key_secret:
            user, password = key_sid, key_secret
        else:
            user, password = self._account(conn, secrets), str(secrets.get("auth_token") or "")
        token = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
        return f"Basic {token}"

    def _call(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        method: str,
        url: str,
        form: Mapping[str, str] | None,
        timeout_s: float,
    ) -> HttpAnswer:
        headers = {"Accept": "application/json", "Authorization": self._auth_header(conn, secrets)}
        payload: bytes | None = None
        if form is not None:
            payload = urlencode([(k, v) for k, v in form.items() if v]).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        send = self._transport or _urllib_transport
        answer = send(method, url, headers, payload, timeout_s)
        if answer.body is None and answer.text:
            try:
                answer = HttpAnswer(
                    status=answer.status,
                    body=json.loads(answer.text),
                    headers=answer.headers,
                    text=answer.text,
                )
            except ValueError:
                pass
        return answer

    def _send_item(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        one: Mapping[str, Any],
        ref: str,
        timeout_s: float,
    ) -> ItemResult:
        to = str(one.get("address") or "").strip()
        body = str(one.get("body") or "").strip()
        if not to:
            return ItemResult(ref=ref, outcome=ITEM_FAILED, detail=NO_NUMBER, retryable=False)
        if not body:
            return ItemResult(ref=ref, outcome=ITEM_FAILED, detail=NO_BODY, retryable=False)
        service = str(conn.config.get("messaging_service_sid") or "").strip()
        number = str(conn.config.get("from_number") or "").strip()
        if not service and not number:
            return ItemResult(ref=ref, outcome=ITEM_FAILED, detail=NO_SENDER, retryable=True)
        form: dict[str, str] = {"To": to, "Body": body}
        # EXACTLY ONE sender: the Messaging Service wins (A2P 10DLC needs it).
        if service:
            form["MessagingServiceSid"] = service
        else:
            form["From"] = number
        callback = str(conn.config.get("status_callback") or "").strip()
        if callback:
            form["StatusCallback"] = callback
        url = f"{self._base(conn)}/{API_VERSION}/Accounts/{self._account(conn, secrets)}/Messages.json"
        try:
            answer = self._call(conn, secrets, "POST", url, form, timeout_s)
        except ProviderTimeout:
            return ItemResult(ref=ref, outcome=ITEM_FAILED, detail=NO_ANSWER, retryable=True)
        body_map = answer.body if isinstance(answer.body, Mapping) else {}
        sid = str(body_map.get("sid") or "").strip()
        # ⚠ A `201` WITH NO SID IS NOT A SUCCESS (`BR-INT-018`): accepted means
        # Twilio SAID what it accepted, and the sid is what a callback names.
        if answer.ok and sid[:2] in ("SM", "MM"):
            return ItemResult(ref=ref, outcome=ITEM_SUCCEEDED, provider_reference=sid)
        code = _code_of(answer)
        sentence, retryable = refusal(code, answer.status if not answer.ok else 502)
        return ItemResult(
            ref=ref,
            outcome=ITEM_FAILED,
            detail=sentence,
            provider_text=_their_words(answer, secrets),
            provider_code=code,
            retryable=retryable,
        )

    def _login_item(
        self, conn: ConnectionView, secrets: Mapping[str, str], ref: str, timeout_s: float
    ) -> ItemResult:
        url = f"{self._base(conn)}/{API_VERSION}/Accounts/{self._account(conn, secrets)}.json"
        try:
            answer = self._call(conn, secrets, "GET", url, None, timeout_s)
        except ProviderTimeout:
            return ItemResult(ref=ref, outcome=ITEM_FAILED, detail=NO_ANSWER, retryable=True)
        if answer.ok:
            return ItemResult(ref=ref, outcome=ITEM_SUCCEEDED, detail=LOGIN_OK)
        sentence, retryable = refusal(_code_of(answer), answer.status)
        return ItemResult(
            ref=ref,
            outcome=ITEM_FAILED,
            detail=sentence,
            provider_text=_their_words(answer, secrets),
            provider_code=_code_of(answer),
            retryable=retryable,
        )


__all__ = [
    "CODE_OPTED_OUT",
    "DELIVERED",
    "FAILED",
    "IN_TRANSIT",
    "STOP_KEYWORDS",
    "SmsTwilioAdapter",
    "is_stop",
    "map_status",
    "refusal",
]
