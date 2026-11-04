# ── Trace ──────────────────────────────────────────────
# Story:  US-INT-026 · US-INT-015 (CR-069 wave E) — the first adapter that
#         opens a socket needs something on the other end of it.
# Rules:  BR-INT-019 (`test()` is the smallest REAL instance) · hard-won law 2
#         (built is not wired — a stub that always says yes proves nothing
#         about a real conversation)
# ───────────────────────────────────────────────────────
"""A real SMTP server, in-process, for the length of one test.

WHY NOT A MOCK, AND WHY NOT `smtpd`
-------------------------------------
A double that returns `TestResult(ok=True)` proves the runtime, not the
adapter: it never opens a socket, never speaks `EHLO`, never gets a `535` back
and never finds out that `smtplib.SMTP_SSL` needs a certificate. The bugs this
wave is most likely to have are in the eight lines that talk to a mail server,
so the tests talk to one.

`smtpd` was removed from the standard library in Python 3.12 and `aiosmtpd` is
not a declared dependency of this repo, so this is forty lines of
`socketserver` speaking the eight verbs `smtplib` actually sends for a plain
`send_message`: EHLO, AUTH LOGIN (two base64 turns), MAIL FROM, RCPT TO, DATA,
the dot, QUIT — and RSET, which `smtplib` sends after a refusal.

⚠ **PLAINTEXT, ON `localhost`, AND THE ADAPTER ALLOWS THAT DELIBERATELY.** The
adapter refuses a server that offers no `STARTTLS` on any host it can reach
over a network; `localhost` is the one exception and it exists exactly so a
harness needs no certificate. That carve-out is asserted by name in
`test_us_int_026_smtp_adapter.py` rather than left implicit.
"""

from __future__ import annotations

import base64
import socketserver
import threading
from dataclasses import dataclass, field


@dataclass
class Delivered:
    """What the server actually received — the proof a message went."""

    sender: str = ""
    recipients: list[str] = field(default_factory=list)
    data: str = ""


class _Handler(socketserver.StreamRequestHandler):
    def _send(self, line: str) -> None:
        self.wfile.write((line + "\r\n").encode())
        self.wfile.flush()

    def handle(self) -> None:  # noqa: C901 — a protocol is a sequence of cases
        server = self.server  # type: ignore[assignment]
        self._send("220 test.invalid ESMTP")
        message = Delivered()
        while True:
            raw = self.rfile.readline()
            if not raw:
                return
            line = raw.decode(errors="replace").rstrip("\r\n")
            upper = line.upper()
            if upper.startswith("EHLO") or upper.startswith("HELO"):
                self._send("250-test.invalid")
                # ⚠ `AUTH LOGIN` ONLY, AND THE NARROWNESS IS THE POINT. The
                # first draft advertised `LOGIN PLAIN`; `smtplib` prefers
                # PLAIN, this handler had no branch for it, the fall-through
                # answered `250` instead of `235`, `smtplib` fell back to
                # LOGIN — and the username the server recorded was the
                # PASSWORD, because the fallback sends the username inline and
                # the handler prompted for it anyway. A harness that lies
                # about which credential it saw is worse than no harness.
                self._send("250 AUTH LOGIN")
            elif upper.startswith("AUTH LOGIN"):
                inline = line[len("AUTH LOGIN") :].strip()
                if inline:
                    user = base64.b64decode(inline).decode()
                else:
                    self._send("334 " + base64.b64encode(b"Username:").decode())
                    user = base64.b64decode(self.rfile.readline().strip()).decode()
                self._send("334 " + base64.b64encode(b"Password:").decode())
                password = base64.b64decode(self.rfile.readline().strip()).decode()
                server.seen_username = user  # type: ignore[attr-defined]
                if password == server.password:  # type: ignore[attr-defined]
                    self._send("235 2.7.0 Authentication successful")
                else:
                    # The exact sentence frame 52.2 shows under ours.
                    self._send("535 5.7.8 AUTHENTICATION FAILED")
            elif upper.startswith("MAIL FROM"):
                message.sender = line.split(":", 1)[1].strip()
                self._send("250 2.1.0 Ok")
            elif upper.startswith("RCPT TO"):
                who = line.split(":", 1)[1].strip()
                if any(bad in who for bad in server.refuse_recipients):  # type: ignore[attr-defined]
                    self._send("550 5.1.1 No such mailbox")
                else:
                    message.recipients.append(who)
                    self._send("250 2.1.5 Ok")
            elif upper == "DATA":
                self._send("354 End data with <CR><LF>.<CR><LF>")
                body: list[str] = []
                while True:
                    chunk = self.rfile.readline().decode(errors="replace")
                    if chunk.rstrip("\r\n") == "." or not chunk:
                        break
                    body.append(chunk)
                message.data = "".join(body)
                server.delivered.append(message)  # type: ignore[attr-defined]
                message = Delivered()
                self._send("250 2.0.0 Ok: queued as ABC123")
            elif upper == "RSET":
                message = Delivered()
                self._send("250 2.0.0 Ok")
            elif upper == "QUIT":
                self._send("221 2.0.0 Bye")
                return
            else:
                self._send("250 2.0.0 Ok")


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class SmtpTestServer:
    """`with SmtpTestServer(password=…) as mail:` — `mail.port`, `mail.delivered`."""

    def __init__(
        self,
        *,
        password: str,
        refuse_recipients: tuple[str, ...] = (),
        port: int = 0,
    ) -> None:
        """`port=0` takes any free one, which is right for almost every case.

        ⚠ ONE CASE NEEDS A REAL MAIL PORT AND IT IS WORTH SAYING WHY. The
        adapter's `validate()` refuses a port no mail server listens on — 25,
        465, 587, 2525 and nothing else — which is exactly the provider
        knowledge `validate` exists to hold. So the conformance kit, which
        checks that the fixture-valid config passes `validate`, cannot be
        handed an ephemeral port like 43217: the kit would be red on the
        adapter being RIGHT. That case asks for 2525, the one unprivileged
        member of the set."""
        self._server = _Server(("127.0.0.1", port), _Handler)
        self._server.password = password  # type: ignore[attr-defined]
        self._server.refuse_recipients = refuse_recipients  # type: ignore[attr-defined]
        self._server.delivered = []  # type: ignore[attr-defined]
        self._server.seen_username = None  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self) -> SmtpTestServer:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    @property
    def delivered(self) -> list[Delivered]:
        return self._server.delivered  # type: ignore[attr-defined,no-any-return]

    @property
    def seen_username(self) -> str | None:
        return self._server.seen_username  # type: ignore[attr-defined,no-any-return]
