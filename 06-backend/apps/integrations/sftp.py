# ── Trace ──────────────────────────────────────────────
# Change:   CR-173-BRC10 — the ONE real SFTP client in the product, adapted to
#           the `FolderWriter` shape `adapters/accounting_file.py` already
#           declared (*"A real client is adapted to this shape in ONE place"*).
# Rules:    PO 2026-10-07 S1 (*"this path is specific for 1 tenant/utility and
#           not common for everyone"* — the library is installed once and does
#           nothing where no utility configured it) · BR-INT-003 (the plaintext
#           secret lives for one call; never logged, never returned) · B14 rule
#           33 (every sentence a clerk can read is ≤ 6 words) · CLAUDE.md
#           hard-won law 3 (defaults fail closed — an unknown server key is
#           REFUSED, never silently accepted)
# Tests:    06-backend/tests/test_cr173_newworld_sftp.py (against the in-process
#           fake server in tests/fake_sftp_server.py — never the City's)
# Impacts:  apps/integrations/receipt_push.py · apps/integrations/file_drop.py ·
#           apps/integrations/adapters/erp_newworld.py
# ───────────────────────────────────────────────────────
"""The SFTP client — sign in, check the server is the one we were told it is, place a file.

HUMAN-OWNED (🔒 credentials — a City's SFTP password, and whether a server key
is trusted). HUMAN-REVIEW-PENDING — AI-authored 2026-10-07 under the PO ruling
of 2026-08-09; the review-ledger row is in `12-governance/09-human-review-ledger.md`.

ONE CLIENT, BOUND IN ONE PLACE
------------------------------
`CLIENT` below is the one bound instance. Every caller reaches it through
`client()`, read at CALL time and never captured at import, for the reason
`accounting_file.folder_writer()` gives: a test that binds a recorded client
after an import-time capture would exercise the real one while appearing to
test the fake. A test rebinds `sftp.CLIENT`; nothing else in the product learns
that `paramiko` exists.

⚠ **IT IS NOT BOUND TO `accounting_file.FOLDER_WRITER` OR
`bank_lockbox_file.FOLDER_CLIENT`, DELIBERATELY.** Both of those connectors'
manifests declare no server-key field, so binding this client there would have
to either accept any server key (the thing this file exists to refuse) or
refuse every connection. Each is a one-line binding plus one manifest field
the day a utility asks for it — recorded in the decision log of 2026-10-07,
not done silently here.

THE SERVER KEY — NEVER SILENTLY ACCEPTED
---------------------------------------
An SFTP server proves who it is with a host key. A client that accepts whatever
key it is shown will hand the City's password to anybody who can answer on
port 22. So:

* A connection with a stored fingerprint REFUSES a server presenting any other
  key — *"Server key does not match."* — before the password is sent.
* A connection with NO stored fingerprint is refused too — *"Server key not
  confirmed yet."* — **except** when a person presses **Test connection**,
  which is the one call made with `capture=True`. That call signs in, writes
  the test file, and hands back the fingerprint it saw, which the screen then
  SHOWS and stores. The unattended nightly upload never captures.
* An administrator can instead TYPE the fingerprint the City gives them, and
  then the very first connection is already checked.

The choice and its reasoning are a decision-log row of 2026-10-07.

THE PASSWORD
------------
Passed in, used for `auth_password`, and dropped. It is never in an exception
message, a log line, a return value or a sentence: every failure below is
re-raised as one of the typed errors carrying a FIXED sentence, and the far
end's own words go through `scrubbing.scrub` before anything keeps them.
`paramiko` itself logs at DEBUG to its own logger and never logs a password.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import posixpath
import socket
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from apps.integrations.adapters.accounting_file import FolderWriter
from apps.integrations.scrubbing import scrub

#: Seconds. A connect, a banner, a sign-in and a channel each get this long,
#: so a dead server costs at most a minute of a worker — and a person pressing
#: **Test connection** waits at most CONNECT_TIMEOUT + AUTH_TIMEOUT before they
#: read a sentence, well inside the web worker's sixty.
CONNECT_TIMEOUT = 15
AUTH_TIMEOUT = 15
CHANNEL_TIMEOUT = 30

DEFAULT_PORT = 22

# ── the sentences a clerk reads — ≤ 6 words each (B14 rule 33) ────────────

UNREACHABLE_SENTENCE = "The server could not be reached."
LOGIN_SENTENCE = "User name or password refused."
KEY_UNKNOWN_SENTENCE = "Server key not confirmed yet."
KEY_MISMATCH_SENTENCE = "Server key does not match."
WRITE_SENTENCE = "The folder refused the file."
INCOMPLETE_SENTENCE = "Server, user and password needed."


class SftpError(Exception):
    """A refusal with a fixed sentence. `detail` is the far end's own words, scrubbed."""

    sentence = UNREACHABLE_SENTENCE
    code = "unreachable"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(self.sentence)
        self.detail = scrub(detail) if detail else None


class Unreachable(SftpError):
    sentence = UNREACHABLE_SENTENCE
    code = "unreachable"


class LoginRefused(SftpError, PermissionError):
    sentence = LOGIN_SENTENCE
    code = "login_refused"


class HostKeyUnknown(SftpError):
    sentence = KEY_UNKNOWN_SENTENCE
    code = "host_key_unknown"


class HostKeyMismatch(SftpError):
    sentence = KEY_MISMATCH_SENTENCE
    code = "host_key_mismatch"


class WriteRefused(SftpError):
    sentence = WRITE_SENTENCE
    code = "write_refused"


class Incomplete(SftpError):
    sentence = INCOMPLETE_SENTENCE
    code = "incomplete"


@dataclass(frozen=True)
class Placed:
    """What a successful write proved: where the file went and which key answered."""

    remote_path: str
    fingerprint: str
    size: int


def fingerprint_of(key: Any) -> str:
    """`SHA256:<base64, unpadded>` — the spelling `ssh-keygen -lf` prints."""
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def normalise_fingerprint(text: str | None) -> str:
    """What an administrator pasted, reduced to `SHA256:…` — or `""`.

    Accepts the bare token or a whole `ssh-keygen` line
    (`256 SHA256:abc… host (ED25519)`), because that is what the City is most
    likely to paste back. Anything without a `SHA256:` token is `""`, which the
    settings form refuses by name rather than storing a value that can never
    match.
    """
    for part in str(text or "").replace(",", " ").split():
        if part.upper().startswith("SHA256:") and len(part) > len("SHA256:"):
            return "SHA256:" + part.split(":", 1)[1].rstrip("=")
    return ""


def remote_path(folder: str | None, filename: str) -> str:
    """`/` + name for an empty folder; never a path that climbs out of it."""
    name = posixpath.basename(filename)
    base = str(folder or "/").strip() or "/"
    return posixpath.join(base, name)


class ParamikoFolderWriter(FolderWriter):
    """`FolderWriter`'s one method, plus `delete`, on top of `paramiko`."""

    @contextlib.contextmanager
    def _session(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        host_key: str,
        capture: bool,
    ) -> Iterator[tuple[Any, str]]:
        import paramiko  # deferred: nothing pays for the import until a utility dials

        if not host or not username or not password:
            raise Incomplete()
        expected = normalise_fingerprint(host_key)
        if not expected and not capture:
            # Refused BEFORE a socket is opened: an unattended run with no
            # confirmed key must not even announce our user name to whoever
            # answers.
            raise HostKeyUnknown()
        try:
            sock = socket.create_connection((host, int(port or DEFAULT_PORT)), timeout=CONNECT_TIMEOUT)
        except OSError as exc:
            raise Unreachable(str(exc)) from None
        transport = paramiko.Transport(sock)
        transport.banner_timeout = CONNECT_TIMEOUT
        transport.auth_timeout = AUTH_TIMEOUT
        try:
            try:
                transport.start_client(timeout=CONNECT_TIMEOUT)
            except (paramiko.SSHException, OSError, EOFError) as exc:
                raise Unreachable(str(exc)) from None
            seen = fingerprint_of(transport.get_remote_server_key())
            if expected and seen != expected:
                # ⚠ BEFORE `auth_password`: the password never reaches a server
                # that is not the one we were told about.
                raise HostKeyMismatch()
            try:
                transport.auth_password(username, password)
            except paramiko.AuthenticationException:
                raise LoginRefused() from None
            except (paramiko.SSHException, OSError, EOFError) as exc:
                raise Unreachable(str(exc)) from None
            if not transport.is_authenticated():
                raise LoginRefused()
            try:
                client = paramiko.SFTPClient.from_transport(transport)
            except (paramiko.SSHException, OSError, EOFError) as exc:
                raise Unreachable(str(exc)) from None
            if client is None:
                raise Unreachable()
            client.get_channel().settimeout(CHANNEL_TIMEOUT)
            try:
                yield client, seen
            finally:
                with contextlib.suppress(Exception):
                    client.close()
        finally:
            with contextlib.suppress(Exception):
                transport.close()

    def write(
        self,
        *,
        host: str,
        username: str,
        password: str,
        path: str,
        filename: str,
        payload: bytes,
        port: int = DEFAULT_PORT,
        host_key: str = "",
        capture: bool = False,
    ) -> Placed:
        """Place `payload` at `path/filename`. Returns what was proved.

        `put` with `confirm=True` stats the file afterwards and compares its
        size, so a write the server truncated is a refusal and not a success.
        """
        import io

        target = remote_path(path, filename)
        with self._session(
            host=host,
            port=port,
            username=username,
            password=password,
            host_key=host_key,
            capture=capture,
        ) as (client, seen):
            try:
                client.putfo(io.BytesIO(payload), target, file_size=len(payload), confirm=True)
            except (OSError, IOError, EOFError) as exc:
                raise WriteRefused(str(exc)) from None
            except Exception as exc:  # noqa: BLE001 — paramiko's own SSHException family
                raise WriteRefused(str(exc)) from None
        return Placed(remote_path=target, fingerprint=seen, size=len(payload))

    def write_and_remove(
        self,
        *,
        host: str,
        username: str,
        password: str,
        path: str,
        filename: str,
        payload: bytes,
        port: int = DEFAULT_PORT,
        host_key: str = "",
        capture: bool = False,
    ) -> tuple[Placed, bool]:
        """The **Test connection** call: write a file, then try to delete it.

        Returns `(placed, removed)`. A folder that lets us write and not delete
        is still a folder we can deliver to, so `removed=False` is reported in
        words and is not a failure.
        """
        import io

        target = remote_path(path, filename)
        with self._session(
            host=host,
            port=port,
            username=username,
            password=password,
            host_key=host_key,
            capture=capture,
        ) as (client, seen):
            try:
                client.putfo(io.BytesIO(payload), target, file_size=len(payload), confirm=True)
            except Exception as exc:  # noqa: BLE001
                raise WriteRefused(str(exc)) from None
            removed = True
            try:
                client.remove(target)
            except Exception:  # noqa: BLE001 — not allowed to delete is not a failure
                removed = False
        return Placed(remote_path=target, fingerprint=seen, size=len(payload)), removed


#: THE binding. Tests rebind this to a client pointed at the in-process fake.
CLIENT: ParamikoFolderWriter | None = ParamikoFolderWriter()


def client() -> ParamikoFolderWriter | None:
    """The bound client, read at call time (see the module docstring)."""
    return CLIENT
