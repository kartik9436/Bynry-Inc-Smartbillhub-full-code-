# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-015 (EP-INT-05) — the adapter protocol: four methods and
#           nothing else, `test()` the smallest real instance. US-INT-026
#           (EP-INT-07) — a mail password typed into the product. US-INT-024 —
#           the wrong password on a Friday. Screens: S141 (connect · test) ·
#           S142 (the sentence and their words underneath) · S8 Notifications
#           Frames 25.1 · 49.1 (the field slot) · 52.1 · 52.2 (the two outcomes)
# Rules:    BR-INT-003 (the credential never reaches a sentence, a log line, an
#           audit payload or a describe line — the three exits) · BR-INT-019
#           (`test()` is the smallest REAL instance, answered in one sentence)
#           · BR-INT-038 (an adapter TRANSLATES; it decides nothing) ·
#           BR-INT-040 (per-item results, never a batch boolean) · BR-INT-008
#           (integrations sends nothing on its own — the dispatcher hands work
#           to this) · B14 rule 33 (a refusal sentence is six words or fewer)
#           · CLAUDE.md 🔒 sensitive paths (credentials)
# Tests:    06-backend/tests/test_us_int_026_smtp_adapter.py (a REAL SMTP
#           server stood up in-process — `aiosmtpd`-free, `smtpd`-free: a
#           threaded `socketserver` speaking the eight verbs this uses) ·
#           the conformance kit, unchanged (`apps/integrations/conformance.py`)
# Impacts:  apps/integrations/adapters/__init__.py (the ONE line that binds it)
#           · apps/integrations/manifests/email_smtp.py (the manifest it
#           serves) · apps/notifications/dispatcher.py (through the seam)
# ───────────────────────────────────────────────────────
"""Custom SMTP — the first adapter in this product that talks to a real server.

HUMAN-OWNED (🔒 sensitive path — CLAUDE.md: credentials). HUMAN-REVIEW-PENDING
— AI-authored 2026-09-04 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*), with a row in
`12-governance/09-human-review-ledger.md` stating in plain English, with a
worked figure, what a reviewer is shown. This file HOLDS A UTILITY'S MAIL
PASSWORD IN MEMORY for the length of one call and hands it to a socket; that
is why it is on the guard list and why the three exits below are asserted
rather than described.

WHY THE LEAST GLAMOROUS PROVIDER WENT FIRST (CR-069 §12 phase 2)
-----------------------------------------------------------------
No OAuth, no vendor SDK, no sandbox, no webhook. When something goes wrong in
this file it is the SUBSTRATE that is wrong, not a provider's API — which is
the entire reason phase 2 is SMTP and phase 3 is Google.

THE THREE EXITS A CREDENTIAL MUST NOT TAKE (BR-INT-003, Figure 14)
-------------------------------------------------------------------
1. **A sentence.** Every sentence this file can return is a module constant
   below. None interpolates a secret; the only value ever interpolated is the
   recipient address a person typed.
2. **A log line.** THIS MODULE DOES NOT LOG. There is no logger, deliberately,
   because a logger is the thing a later lane reaches for at 2 a.m. `smtplib`'s
   own debug output is left at level 0 (its default) and is never raised —
   `set_debuglevel(1)` prints the AUTH exchange, base64-encoded, to stderr.
3. **An audit payload.** This file writes no audit row at all; `services.py`
   does, from the masked hint.

⚠ THE PLAINTEXT EXISTS AT EXACTLY ONE POINT AND FOR ONE CALL. The runner reads
it (`services.credential_secrets`), hands it here as an argument, and drops it
in a `finally`. It is never attached to `ConnectionView`, which is why that
dataclass carries `config` and no secrets field.

WHAT WE SAY, AND WHAT THEY SAID (frames 52.1 · 52.2)
------------------------------------------------------
`TestResult.sentence` is OURS — *The mail server rejected the password.* —
six words, no status code, no rule id, and it is what a clerk acts on.
`provider_text` is THEIRS, verbatim — *535 5.7.8 AUTHENTICATION FAILED* — and
it is what support reads. **This file does not scrub it.** The scrub is
applied once, at the write, in `services.finish_run`, and `G84` fails a second
writer; an adapter that scrubbed here would be that second writer.

⚠ A PROVIDER'S REFUSAL IS AN OUTCOME, NOT AN EXCEPTION. `test()` never raises
for anything the mail server says or does — a wrong password, a closed port, a
name that does not resolve, a server that hangs up — because every one of those
is a `TestResult(ok=False, …)` a clerk can read. It raises only for a
programming error, and the job body treats that as the run's failure.

THE TRANSPORT, AND WHY IT IS DECIDED BY THE PORT AND NOT BY A FIELD
--------------------------------------------------------------------
Port 465 is implicit TLS from the first byte (`SMTP_SSL`); 587 and 25 are
plaintext-then-`STARTTLS`. That is not our choice, it is what mail servers do,
so it is read off the port rather than asked as a sixth question in the modal
— the modal has five fields and a person connecting a mailbox knows their port.
A server on 587 that refuses `STARTTLS` is refused BY US: sending a utility's
password across an unencrypted link would be `sslmode=disable` wearing a
different protocol (hard-won law 3).
"""

from __future__ import annotations

import smtplib
import socket
import ssl
from collections.abc import Mapping, Sequence
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Any

from apps.integrations import email_attachments
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

#: How long we wait on a mail server before giving up, in seconds. A ninety-
#: second server is wave F's breaker; this is the socket's own patience and it
#: exists so a worker is never held for ever by a host that accepts a
#: connection and then says nothing.
TIMEOUT_SECONDS = 30.0

#: Implicit TLS from the first byte. Everything else is STARTTLS.
IMPLICIT_TLS_PORTS = frozenset({465})

#: The ports a mail server actually listens on. Provider knowledge, which is
#: exactly what `validate()` is for — the manifest already checked the SHAPE.
KNOWN_PORTS = ("25", "465", "587", "2525")

# ── The sentences. Every one is a constant, none interpolates a secret, and
#    each refusal is six words or fewer (B14 rule 33, G33). ──────────────────
SENT = "Sent one test message to {recipient}."
REJECTED_PASSWORD = "The mail server rejected the password."
NO_ANSWER = "The mail server did not answer."
REFUSED_ADDRESS = "The mail server refused that address."
REFUSED_SENDER = "The mail server refused the sender."
REFUSED_ENCRYPTION = "The mail server refused encryption."
REFUSED_MESSAGE = "The mail server refused the message."

#: The subject and body of the one real message `test()` sends. A person who
#: receives it must be able to tell instantly what it is and that it means
#: nothing is wrong (frame 52.1's note: *a real message to a typed address*).
#: ⚠ **`test()` ONLY (`DEF-NOT-10420`).** Until 2026-10-22 `execute()` also
#: fell back to `TEST_SUBJECT` for a real message with no subject, so every bill
#: the seam handed over without one went to a customer titled *Test message from
#: your billing system*. A real message with no subject is now refused.
TEST_SUBJECT = "Test message from your billing system"
TEST_BODY = (
    "This is the test message you asked for.\n\n"
    "Your mail server accepted it, so bills and notices can go out from this "
    "address.\n\nNothing else has changed and nothing was sent to a customer.\n"
)


class EmailSmtpAdapter(Adapter):
    """Four methods and only four (the conformance kit refuses a fifth)."""

    key = "email_smtp"

    # ── validate — provider knowledge about the NON-SECRET fields ───────────

    def validate(self, config: Mapping[str, Any]) -> list[FieldError]:
        """Cheap, no network. The manifest's own shape check has already run,
        so this is only what a mail server knows that a form cannot."""
        problems: list[FieldError] = []
        port = str(config.get("port", "")).strip()
        if port and port not in KNOWN_PORTS:
            problems.append(FieldError("port", message_key="integrations.field.smtp_port"))
        return problems

    # ── test — the smallest REAL instance (BR-INT-019) ─────────────────────

    def test(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        *,
        recipient: str | None = None,
    ) -> TestResult:
        """One real message to a typed address, and the server's verdict.

        NOT a credential check: a mail server can accept a password and still
        refuse to relay, and only sending finds that out (frame 52.1's note).
        """
        target = (recipient or "").strip() or str(conn.config.get("send_from") or "").strip()
        message = self._message(
            conn, target, email_format.compose(subject=TEST_SUBJECT, body=TEST_BODY, language="en")
        )
        ok, sentence, provider_text = self._deliver(conn, secrets, message, target)
        return TestResult(
            ok=ok,
            sentence=SENT.format(recipient=target) if ok else sentence,
            provider_text=provider_text,
        )

    # ── execute — one attempt at a batch, per-item results ─────────────────

    def execute(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        work: Sequence[Mapping[str, Any]],
    ) -> RunResult:
        """One connection, one login, one item at a time down it (BR-NOT-005
        paces at the PROVIDER's rate; a connection per message is the burst
        that rule forbids).

        ⚠ A REFUSAL OF ONE ADDRESS IS ONE ITEM'S OUTCOME, NEVER THE BATCH'S.
        `smtplib` raises `SMTPRecipientsRefused` per `send_message` call, so
        seven bad addresses out of ninety-three are seven `ItemResult`s and
        eighty-six sends — the *86 of 93 · 7 bad addresses* line on S142. A
        failure that ends the CONNECTION (the server hangs up, the password is
        wrong) fails every item that had not yet gone, each with the same
        provider text, because that is the truth about each of them.
        """
        if not work:
            return RunResult(items=(), confirmed=True)
        items: list[ItemResult] = []
        try:
            with self._session(conn, secrets) as server:
                for index, one in enumerate(work):
                    ref = str(one.get("ref", index))
                    address = str(one.get("address") or "").strip()
                    try:
                        content = email_format.compose(
                            subject=one.get("subject"),
                            body=one.get("body"),
                            language=one.get("language"),
                            html=one.get("html"),  # CR-199-BRC10 S6
                        )
                    except email_format.EmailContentMissing as missing:
                        # Never a made-up subject, never a `str()`-ed dict
                        # (`DEF-NOT-10420`): this one item fails, in our words.
                        items.append(
                            ItemResult(
                                ref=ref,
                                outcome=ITEM_FAILED,
                                detail=address or None,
                                provider_text=missing.sentence,
                            )
                        )
                        continue
                    message = self._message(
                        conn, address, content, attachments=one.get("attachments") or ()
                    )
                    try:
                        server.send_message(message)
                    except smtplib.SMTPRecipientsRefused as refused:
                        items.append(
                            ItemResult(
                                ref=ref,
                                outcome=ITEM_FAILED,
                                detail=address or None,
                                provider_text=self._provider_text(refused),
                            )
                        )
                    else:
                        items.append(
                            ItemResult(ref=ref, outcome=ITEM_SUCCEEDED, detail=address or None)
                        )
        except Exception as broke:  # noqa: BLE001 — the connection ended; every item it owed fails
            text = self._provider_text(broke)
            done = {one.ref for one in items}
            for index, one in enumerate(work):
                ref = str(one.get("ref", index))
                if ref in done:
                    continue
                items.append(
                    ItemResult(
                        ref=ref,
                        outcome=ITEM_FAILED,
                        detail=str(one.get("address") or "").strip() or None,
                        provider_text=text,
                    )
                )
        # `confirmed=True`: SMTP answers 250 per message with its own queue id,
        # so the far end DID say how many it accepted — one at a time. This is
        # the honest opposite of wave C's `no-count 200` fixture.
        return RunResult(items=tuple(items), confirmed=True)

    # ── describe — the masked line on the card ─────────────────────────────

    def describe(self, conn: ConnectionView) -> str:
        """*billing@brazosbend.example · Custom SMTP* — the address a customer
        will see in their inbox, and nothing else. No host, no username, no
        port: the card answers *who do these emails come from*."""
        who = conn.config.get("send_from") or conn.config.get("username") or ""
        return f"{who} · Custom SMTP".strip(" ·") or "Custom SMTP"

    # ── the private half — none of it is part of the protocol ──────────────

    def _message(
        self,
        conn: ConnectionView,
        to: str,
        content: email_format.EmailContent,
        *,
        attachments: Sequence[Mapping[str, Any]] = (),
    ) -> EmailMessage:
        """`multipart/alternative` — the rendered text, and its escaped HTML
        alternative (`email_format`). Never a single part, never a default.
        With attachments (`DEF-NOT-10460`, an agreement's PDF) the message
        becomes `multipart/mixed`, the alternative first (`email_attachments`)."""
        message = email_format.mime_alternative(
            content,
            sender=str(conn.config.get("send_from") or conn.config.get("username") or ""),
            to=to,
        )
        email_attachments.add_to_mime(message, list(attachments))
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid()
        return message

    def _session(self, conn: ConnectionView, secrets: Mapping[str, str]) -> smtplib.SMTP:
        """An open, authenticated session. The password is a local name here
        and in no attribute of anything that outlives the call."""
        host = str(conn.config.get("host") or "").strip()
        port = int(str(conn.config.get("port") or "587").strip() or 587)
        username = str(conn.config.get("username") or "").strip()
        password = str(secrets.get("password") or "")
        if port in IMPLICIT_TLS_PORTS:
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                host, port, timeout=TIMEOUT_SECONDS, context=ssl.create_default_context()
            )
        else:
            server = smtplib.SMTP(host, port, timeout=TIMEOUT_SECONDS)
            server.ehlo()
            if server.has_extn("starttls"):
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            elif not _plaintext_allowed(host):
                # Hard-won law 3: the unsafe option is the one you have to type.
                server.close()
                raise _NoEncryption()
        if username:
            server.login(username, password)
        return server

    def _deliver(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        message: EmailMessage,
        target: str,
    ) -> tuple[bool, str, str | None]:
        """Open, authenticate, send one, close — and turn every way that can
        go wrong into OUR sentence plus THEIR words."""
        try:
            with self._session(conn, secrets) as server:
                server.send_message(message)
        except smtplib.SMTPAuthenticationError as wrong:
            return False, REJECTED_PASSWORD, self._provider_text(wrong)
        except smtplib.SMTPRecipientsRefused as refused:
            return False, REFUSED_ADDRESS, self._provider_text(refused)
        except smtplib.SMTPSenderRefused as sender:
            return False, REFUSED_SENDER, self._provider_text(sender)
        except _NoEncryption:
            return False, REFUSED_ENCRYPTION, "STARTTLS not offered"
        except smtplib.SMTPNotSupportedError as unsupported:
            return False, REFUSED_ENCRYPTION, self._provider_text(unsupported)
        except (
            smtplib.SMTPConnectError,
            smtplib.SMTPServerDisconnected,
            OSError,
            socket.timeout,
        ) as gone:
            # `OSError` covers `socket.gaierror` (the name does not resolve),
            # `ConnectionRefusedError` (nothing is listening) and the timeout.
            return False, NO_ANSWER, self._provider_text(gone)
        except smtplib.SMTPException as other:
            return False, REFUSED_MESSAGE, self._provider_text(other)
        return True, "", None

    @staticmethod
    def _provider_text(error: BaseException) -> str:
        """THEIR words, verbatim and unscrubbed — `services.finish_run` scrubs
        once, at the write, and `G84` fails a second writer.

        `smtplib`'s exceptions carry the server's own bytes; `str()` on them
        renders `(535, b'5.7.8 AUTHENTICATION FAILED')`, so the code and the
        sentence support asks for both survive. **A password is never in one
        of these** — `smtplib` puts the server's RESPONSE in the exception,
        never the credential it sent.
        """
        text = str(error).strip() or error.__class__.__name__
        return text[:500]


class _NoEncryption(Exception):
    """The server offered no STARTTLS on a port where we require it."""


def _plaintext_allowed(host: str) -> bool:
    """The ONE case where a mail server may be spoken to in the clear: a
    server on this machine, which is what a test harness and a development
    stack are. Anything reachable over a network must offer STARTTLS."""
    return host in ("localhost", "127.0.0.1", "::1", "")


__all__ = [
    "IMPLICIT_TLS_PORTS",
    "KNOWN_PORTS",
    "NO_ANSWER",
    "REFUSED_ADDRESS",
    "REFUSED_ENCRYPTION",
    "REFUSED_MESSAGE",
    "REFUSED_SENDER",
    "REJECTED_PASSWORD",
    "SENT",
    "TIMEOUT_SECONDS",
    "EmailSmtpAdapter",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-026@c05e4dd4 (EP-INT-07 story + BR-INT-018..053 snapshot; co-packets US-INT-015@c05e4dd4 · US-INT-024@c05e4dd4)
# generated: 2026-09-04 by the CR-069 wave E build lane
# checklist: A✔ B✔ C✔ D✔(POST /integrations/email_smtp/test and /run reach it through the job body) E✔(S141's Save and test, S142's Replace password) F✔ G✔ H=PENDING(🔒 credentials — human sign-off owed, row in 09-human-review-ledger.md)
# gates: pytest tests/test_us_int_026_smtp_adapter.py tests/test_us_int_024_credentials.py · the conformance kit UNCHANGED (37 cases, run over this class) · G94 (the three exits, permanently) · G32 (every sentence here is a catalogue key on the screen) · G33 (six words) · G84 (this file does not scrub — the seam does)
# exceptions: (1) `smtplib` is imported here and in no other application file — US-INT-015 TC-7's containment. (2) plaintext SMTP is permitted to `localhost` ONLY, so a test harness needs no certificate; every other host must offer STARTTLS or is refused. (3) no logger, on purpose — see the docstring's exit 2.
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
