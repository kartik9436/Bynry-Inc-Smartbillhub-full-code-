"""An in-process SFTP server over a temporary folder — for tests and the local walkthrough.

CR-173-BRC10. **NEVER the City's server.** The suite and the browser walkthrough
dial this on 127.0.0.1 with obviously fake credentials (`test-password-not-real`).

It is the real SSH protocol through `paramiko`'s own server classes, so the
client in `apps/integrations/sftp.py` is exercised end to end — key exchange,
host-key fingerprint, password sign-in, `putfo` with its size check, `remove` —
rather than through a mock that agrees with whatever the client sends.

Run it standalone for a browser walkthrough:

    python3 06-backend/tests/fake_sftp_server.py --port 2222 --root /tmp/x \
        --user Bynry-test --password test-password-not-real

It prints its port and host-key fingerprint and serves until killed.
`--readonly` refuses every write (the *folder refused the file* case) and
`--no-delete` refuses removes (the *could not delete the test file* case).
"""

from __future__ import annotations

import argparse
import os
import socket
import threading
from pathlib import Path

import paramiko
from paramiko import SFTPAttributes, SFTPHandle, SFTPServer, SFTPServerInterface
from paramiko.sftp import SFTP_FAILURE, SFTP_NO_SUCH_FILE, SFTP_OK, SFTP_PERMISSION_DENIED

from apps.integrations.sftp import fingerprint_of


class _Auth(paramiko.ServerInterface):
    def __init__(self, user: str, password: str) -> None:
        self.user = user
        self.password = password

    def check_auth_password(self, username: str, password: str) -> int:
        if username == self.user and password == self.password:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username: str) -> str:
        return "password"

    def check_channel_request(self, kind: str, chanid: int) -> int:
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED


class _Handle(SFTPHandle):
    pass


def _make_sftp(root: Path, readonly: bool, no_delete: bool) -> type:
    class _Sftp(SFTPServerInterface):
        def _real(self, path: str) -> Path:
            clean = os.path.normpath("/" + path.lstrip("/")).lstrip("/")
            return root / clean

        def stat(self, path: str):
            real = self._real(path)
            if not real.exists():
                return SFTP_NO_SUCH_FILE
            return SFTPAttributes.from_stat(real.stat())

        lstat = stat

        def list_folder(self, path: str):
            real = self._real(path)
            if not real.is_dir():
                return SFTP_NO_SUCH_FILE
            out = []
            for name in sorted(os.listdir(real)):
                attr = SFTPAttributes.from_stat((real / name).stat())
                attr.filename = name
                out.append(attr)
            return out

        def open(self, path: str, flags: int, attr):
            real = self._real(path)
            writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
            if writing and readonly:
                return SFTP_PERMISSION_DENIED
            if writing and not real.parent.is_dir():
                return SFTP_NO_SUCH_FILE
            try:
                fd = os.open(real, flags | getattr(os, "O_BINARY", 0), 0o644)
                mode = "wb" if writing and not (flags & os.O_RDWR) else ("r+b" if writing else "rb")
                if flags & os.O_APPEND:
                    mode = "ab"
                handle = _Handle(flags)
                fobj = os.fdopen(fd, mode)
                handle.filename = str(real)
                if writing:
                    handle.writefile = fobj
                if "r" in mode or "+" in mode:
                    handle.readfile = fobj
                return handle
            except OSError:
                return SFTP_FAILURE

        def remove(self, path: str) -> int:
            if readonly or no_delete:
                return SFTP_PERMISSION_DENIED
            try:
                self._real(path).unlink()
            except OSError:
                return SFTP_NO_SUCH_FILE
            return SFTP_OK

    return _Sftp


class FakeSftpServer:
    """`with FakeSftpServer(root, user=…, password=…) as server:` → `server.port`, `.fingerprint`."""

    def __init__(
        self,
        root: Path | str,
        *,
        user: str = "Bynry-test",
        password: str = "test-password-not-real",
        port: int = 0,
        readonly: bool = False,
        no_delete: bool = False,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.user = user
        self.password = password
        self.readonly = readonly
        self.no_delete = no_delete
        found = _key_file()
        self.host_key = paramiko.RSAKey.from_private_key_file(found) if found else None
        if self.host_key is None:
            self.host_key = paramiko.RSAKey.generate(2048)
        self.fingerprint = fingerprint_of(self.host_key)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", port))
        self._sock.listen(8)
        self.port = self._sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.connections = 0

    def files(self) -> dict[str, bytes]:
        return {
            str(p.relative_to(self.root)): p.read_bytes()
            for p in sorted(self.root.rglob("*"))
            if p.is_file()
        }

    def _serve_one(self, conn: socket.socket) -> None:
        transport = paramiko.Transport(conn)
        transport.add_server_key(self.host_key)
        transport.set_subsystem_handler(
            "sftp", SFTPServer, _make_sftp(self.root, self.readonly, self.no_delete)
        )
        try:
            transport.start_server(server=_Auth(self.user, self.password))
            channel = transport.accept(20)
            if channel is None:
                return
            while transport.is_active() and not self._stop.is_set():
                self._stop.wait(0.05)
        except Exception:  # noqa: BLE001 — a client hanging up is not the server's failure
            pass
        finally:
            transport.close()

    def _loop(self) -> None:
        self._sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except (socket.timeout, OSError):
                continue
            self.connections += 1
            threading.Thread(target=self._serve_one, args=(conn,), daemon=True).start()

    def start(self) -> FakeSftpServer:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        finally:
            if self._thread is not None:
                self._thread.join(timeout=2)

    def __enter__(self) -> FakeSftpServer:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()


def _key_file() -> str | None:
    """An optional fixed host key for the walkthrough, so the fingerprint a
    screenshot shows is stable across restarts. Tests generate a fresh one."""
    found = os.environ.get("FAKE_SFTP_HOST_KEY")
    return found if found and Path(found).is_file() else None


if __name__ == "__main__":  # pragma: no cover — the walkthrough's server
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=2222)
    parser.add_argument("--root", required=True)
    parser.add_argument("--user", default="Bynry-test")
    parser.add_argument("--password", default="test-password-not-real")
    parser.add_argument("--readonly", action="store_true")
    parser.add_argument("--no-delete", action="store_true")
    args = parser.parse_args()
    server = FakeSftpServer(
        args.root,
        user=args.user,
        password=args.password,
        port=args.port,
        readonly=args.readonly,
        no_delete=args.no_delete,
    ).start()
    print(f"fake sftp on 127.0.0.1:{server.port} root={server.root} key={server.fingerprint}", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        server.stop()
