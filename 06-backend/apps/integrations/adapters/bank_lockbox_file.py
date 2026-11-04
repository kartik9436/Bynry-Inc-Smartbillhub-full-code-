# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-008 (EP-INT-09) — the bank connection: label · format ·
#           upload-or-SFTP source. US-INT-010 (the lifecycle: deactivate
#           first). Screens: S141 (the connect modal, bank variant) · S142
# Rules:    BR-INT-009 (bank side v1 is a FILE) · BR-INT-019 (`test()` is the
#           smallest REAL instance — list one folder — never a credential
#           parse) · BR-INT-003 (the plaintext secret lives for one call and is
#           never in a sentence, a log or `describe()`) · BR-INT-038 (an
#           adapter TRANSLATES: no retry, no scheduling, no persistence) ·
#           BR-INT-043 (field kinds are a closed vocabulary) ·
#           BR-INT-054 as amended (this adapter opens a door; it reads no row
#           out of a file and never learns what one means)
# Tests:    06-backend/tests/test_us_int_008_bank_adapter.py
# Impacts:  apps/integrations/adapters/__init__.py (the one binding line) ·
#           apps/integrations/manifests/bank_lockbox_file.py (its field list is
#           what `validate_fields` already checks; this adds bank knowledge) ·
#           apps/integrations/arrivals.py (the arrival path this feeds)
# ───────────────────────────────────────────────────────
"""The bank & lockbox connection — a named folder or a named upload, and nothing more.

WHAT THIS ADAPTER IS FOR
------------------------
A utility banks with somebody. That relationship — *this is our Chase lockbox,
the files are CSV, they land in `/outgoing/lockbox`, here is the folder
password* — is a CONNECTION, and building and holding it is exactly what
`BR-INT-054` leaves with this module. Everything that happens to a row inside
one of those files is Runbooks'.

So this file can open the folder, prove it can open the folder, and say in one
masked sentence what it is connected to. It cannot read a payment out of a
file, and it does not import a codec or a parser with which to try.

⚠ `test()` LISTS ONE REAL FOLDER (BR-INT-019). The design underlines this
twice: *"I have seen this method built as 'does the API key parse' more times
than any other mistake in this space… A test that cannot fail the way
production fails is worse than no test, because someone trusted it."* So
`test()` here dials the host with the credential and asks for a directory. It
imports nothing. It is refused by the far end when the password is wrong, and
that is the point.

⚠ AND THERE IS NO SFTP CLIENT INSTALLED ON THIS DEPLOYMENT, WHICH IS SAID
OUT LOUD RATHER THAN PAPERED OVER. `FOLDER_CLIENT` below is the seam a client
binds to. When nothing is bound, `test()` answers **`ok=False`** with a plain
sentence — it does NOT return a green result it has not earned. That is
hard-won law 7 in its *incapable of failing* shape: a `test()` that reports
success because it never dialled is precisely the credential-parse mistake
`BR-INT-019` was written against, wearing better manners. The gap is recorded
in `10-scripts/render-checks/lib/knownGaps.mjs` so it goes red in BOTH
directions — if a client is ever installed and this sentence stays, the gap
fails for being stale.

⚠ AN UPLOAD SOURCE HAS NO FOLDER AND THEREFORE NO SAFE INSTANCE. `BR-INT-019`
says a provider with no safe instance declares it in its MANIFEST
(`Operation.test_action = None`) — but testability here is a fact about the
CONNECTION, not the provider: the same bank card is an SFTP folder for one
utility and a monthly drag-and-drop for the next, and a manifest is data read
once at `ready()` and cannot branch on a config field. The manifest keeps its
`test_action` (SFTP, the case that CAN be tested) and this adapter answers an
upload connection honestly. The distinction is recorded in the decision log
for 2026-09-06; it is not a gap in the rule so much as a case the rule did not
reach.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

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
from apps.integrations.scrubbing import scrub

#: The ONE format the manifest registers — CSV, the only one
#: `apps/payments/lockbox.py` reads (PO Q2 = A, 2026-10-30; `DEF-INT-10702`).
#: It was six until then. A connection still carrying a stored `bai2` is
#: refused here by name rather than left looking connected. Kept as a name
#: rather than reached for through the registry so `validate()` stays cheap
#: and network-free.
FILE_FORMATS = ("csv",)

SOURCE_UPLOAD = "upload"
SOURCE_SFTP = "sftp"
SOURCES = (SOURCE_UPLOAD, SOURCE_SFTP)

#: The fields an SFTP source needs and an upload source must not carry.
SFTP_FIELDS = ("sftp_host", "sftp_username")
SFTP_SECRET = "sftp_password"


class FolderClient:
    """What this adapter needs of an SFTP client, and the whole of it.

    One method. A real client (paramiko, say) is adapted to this shape in ONE
    place and bound to `FOLDER_CLIENT`; nothing else in the product learns that
    a particular library exists. `listdir` returns the names in the folder — it
    reads no file and downloads nothing, because `test()` must be safe to press
    on a live production folder at four in the afternoon.
    """

    def listdir(self, *, host: str, username: str, password: str, path: str) -> Sequence[str]:
        raise NotImplementedError


#: The seam. `None` on this deployment — no SFTP client is installed. A test
#: binds a recorded client here; production binds a real one. It is a module
#: attribute rather than a constructor argument because `services` builds the
#: adapter with no arguments, like every other one.
FOLDER_CLIENT: FolderClient | None = None

#: ≤ 6 words each (B14 rule 33), no rule id and no status code (rule 32).
NO_CLIENT_SENTENCE = "No folder client is installed."
UPLOAD_SENTENCE = "Nothing to test until first use."
REFUSED_SENTENCE = "The folder refused the credential."
UNREACHABLE_SENTENCE = "The folder could not be reached."

#: The folder a test lists when the connection names none. A bank's own root
#: is the one path every SFTP account has.
DEFAULT_PATH = "."


def folder_client() -> FolderClient | None:
    """The bound client, read at CALL time and never captured at import.

    ⚠ READ THROUGH A FUNCTION ON PURPOSE. A module-level `from … import
    FOLDER_CLIENT` in a test would freeze whatever was bound at import, and
    a test that binds a client afterwards would exercise the *no client*
    branch while appearing to test the real one — a check looking at the
    wrong thing (hard-won law 7).
    """
    return FOLDER_CLIENT


class BankLockboxFileAdapter(Adapter):
    """Four methods. It opens a folder and it says what it is connected to."""

    key = "bank_lockbox_file"

    # ── validate ────────────────────────────────────────────────────────────

    def validate(self, config: Mapping[str, Any]) -> FieldErrors:
        """Bank knowledge on top of the manifest's own shape check.

        The manifest already refuses a missing `label`, an undeclared field
        (`file_format` has been one since 2026-10-30 — CSV is the only format,
        so there is no picker) and a `sftp_host` with a scheme in it. A stored
        non-CSV `file_format` is still refused below, by name. What it cannot see
        is the RELATIONSHIP between `source` and the three folder fields — that
        an SFTP source without a host is not a connection, and that folder
        credentials typed against an upload source are a secret we would be
        holding for no reason.

        No network, and none is reachable from here — the conformance kit
        forbids a socket inside `validate()` and asserts it.
        """
        errors: FieldErrors = []
        source = config.get("source")

        file_format = config.get("file_format")
        if file_format is not None and file_format not in FILE_FORMATS:
            errors.append(
                FieldError("file_format", message_key="integrations.field.bank_format")
            )

        if source == SOURCE_SFTP:
            for name in SFTP_FIELDS:
                if not _present(config.get(name)):
                    errors.append(
                        FieldError(name, message_key="integrations.field.sftp_required")
                    )
        elif source == SOURCE_UPLOAD:
            # ⚠ REFUSED, NOT IGNORED. A folder password stored against a
            # connection that will never dial a folder is a secret held for no
            # purpose — and the cheapest secret to keep safe is the one we
            # declined to take (BR-INT-003).
            for name in (*SFTP_FIELDS, SFTP_SECRET):
                if _present(config.get(name)):
                    errors.append(
                        FieldError(name, message_key="integrations.field.sftp_not_needed")
                    )
        return errors

    # ── test ────────────────────────────────────────────────────────────────

    def test(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        *,
        recipient: str | None = None,
    ) -> TestResult:
        """List one folder. Import nothing.

        Never raises for the far end's refusal — a wrong password is
        `TestResult(ok=False, …)` with the bank's own words underneath, shown
        to the owning tenant only.
        """
        source = (conn.config or {}).get("source")

        if source != SOURCE_SFTP:
            #: An upload connection has no folder to list. Answered honestly
            #: rather than dressed as a pass — see this module's docstring.
            return TestResult(ok=False, sentence=UPLOAD_SENTENCE)

        client = folder_client()
        if client is None:
            return TestResult(ok=False, sentence=NO_CLIENT_SENTENCE)

        config = conn.config or {}
        try:
            names = client.listdir(
                host=str(config.get("sftp_host") or ""),
                username=str(config.get("sftp_username") or ""),
                password=str(secrets.get(SFTP_SECRET) or ""),
                path=str(config.get("sftp_path") or DEFAULT_PATH),
            )
        except PermissionError as exc:
            return TestResult(
                ok=False, sentence=REFUSED_SENTENCE, provider_text=scrub(str(exc))
            )
        except Exception as exc:  # noqa: BLE001 — a provider's refusal is a result, never a raise
            return TestResult(
                ok=False, sentence=UNREACHABLE_SENTENCE, provider_text=scrub(str(exc))
            )

        #: ⚠ THE COUNT, NEVER THE NAMES. A directory listing at a bank carries
        #: other people's file names, and a sentence this product shows on a
        #: card is not the place for them.
        count = len(list(names))
        return TestResult(ok=True, sentence=_listed_sentence(count))

    # ── execute ─────────────────────────────────────────────────────────────

    def execute(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        work: Sequence[Mapping[str, Any]],
    ) -> RunResult:
        """One attempt at a batch of files — CONFIRM EACH IS THERE, read none.

        ⚠ WHAT THIS DELIBERATELY DOES NOT DO IS THE POINT OF THE WAVE. It does
        not open a file, decode it, or hand its rows anywhere. An item here
        succeeds when the folder HAS the named file and fails when it does
        not; what the file contains is a question this module is not allowed to
        ask (`BR-INT-054`(2)). The bytes are read by the arrival path
        (`apps/integrations/arrivals.py`), which hashes them before anything
        parses them, and what becomes of the rows inside is Runbooks'.
        """
        if not work:
            return RunResult(items=(), confirmed=True)

        client = folder_client()
        config = conn.config or {}
        if (config.get("source") != SOURCE_SFTP) or client is None:
            return RunResult(
                items=tuple(
                    ItemResult(
                        ref=_ref(one),
                        outcome=ITEM_FAILED,
                        detail=UPLOAD_SENTENCE
                        if config.get("source") != SOURCE_SFTP
                        else NO_CLIENT_SENTENCE,
                    )
                    for one in work
                ),
                confirmed=True,
            )

        try:
            names = set(
                client.listdir(
                    host=str(config.get("sftp_host") or ""),
                    username=str(config.get("sftp_username") or ""),
                    password=str(secrets.get(SFTP_SECRET) or ""),
                    path=str(config.get("sftp_path") or DEFAULT_PATH),
                )
            )
        except Exception as exc:  # noqa: BLE001 — per-item, never a raise
            return RunResult(
                items=tuple(
                    ItemResult(ref=_ref(one), outcome=ITEM_FAILED) for one in work
                ),
                confirmed=False,
                provider_text=scrub(str(exc)),
            )

        return RunResult(
            items=tuple(
                ItemResult(
                    ref=_ref(one),
                    outcome=ITEM_SUCCEEDED if _ref(one) in names else ITEM_FAILED,
                )
                for one in work
            ),
            confirmed=True,
        )

    # ── describe ────────────────────────────────────────────────────────────

    def describe(self, conn: ConnectionView) -> str:
        """*Chase lockbox · BAI2 · folder at sftp.chase.example* — no secret.

        The password is not here and cannot be: `ConnectionView` carries the
        connection's non-secret config and the plaintext never travels on it
        (BR-INT-003). The conformance kit asserts that no secret reaches this
        sentence for every adapter, including this one.
        """
        config = conn.config or {}
        parts: list[str] = []
        label = conn.label or config.get("label")
        if label:
            parts.append(str(label))
        file_format = config.get("file_format")
        if file_format:
            parts.append(str(file_format).upper())
        if config.get("source") == SOURCE_SFTP:
            host = config.get("sftp_host")
            parts.append(f"folder at {host}" if host else "folder")
        else:
            parts.append("uploaded by hand")
        return " · ".join(parts) if parts else "Bank & lockbox file"


def _present(value: Any) -> bool:
    return value is not None and not (isinstance(value, str) and value.strip() == "")


def _ref(one: Mapping[str, Any]) -> str:
    """The file name — what a clerk would search for, never a database id
    (B14 rule 31)."""
    return str(one.get("filename") or one.get("ref") or "")


def _listed_sentence(count: int) -> str:
    """*The folder has 4 files.* One clause, a real number, no status code."""
    if count == 0:
        return "The folder is empty."
    if count == 1:
        return "The folder has 1 file."
    return f"The folder has {count} files."


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-008 · US-INT-010 (EP-INT-09) + BR-INT-009 · 019 · 003 · 038 ·
#         043 + BR-INT-054 as amended 2026-09-06 (CR-069 §20.4 wave I)
# generated: 2026-09-06 by the CR-069 wave I build lane
# checklist: A✔ B✔ C✔ D✔ E✔(S141's bank variant, generated from the manifest)
#            F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_008_bank_adapter.py (conformance kit included)
# exceptions: NO SFTP CLIENT IS INSTALLED on this deployment, so `FOLDER_CLIENT`
#             is unbound and `test()` answers ok=False *No folder client is
#             installed.* rather than a pass it has not earned. Recorded as a
#             known gap so it goes red in both directions.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
