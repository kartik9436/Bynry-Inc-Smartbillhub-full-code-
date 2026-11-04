# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-009 (EP-INT-03) — the saved accounting export target:
#           destination × format, no credential for a download. US-INT-033
#           (EP-INT-09) TC-5 — `test()` writes a zero-row export.
#           US-INT-010 (the lifecycle). Screens: S141 (the connect modal,
#           accounting variant) · S142 · S43
# Rules:    BR-INT-010 (accounting v1 is a FILE target) · BR-INT-019 (`test()`
#           is the smallest REAL instance — never a credential parse) ·
#           BR-INT-003 (the plaintext secret lives for one call; the cheapest
#           secret to keep safe is the one we declined to take) ·
#           BR-INT-038 (an adapter TRANSLATES: no retry, no scheduling, no
#           persistence) · BR-INT-043 (field kinds are a closed vocabulary) ·
#           BR-INT-054 as amended (this adapter shapes and places a file; it
#           never decides what belongs in one)
# Tests:    06-backend/tests/test_us_int_038_export_target.py
# Impacts:  apps/integrations/adapters/__init__.py (the one binding line) ·
#           apps/integrations/manifests/accounting_file.py (destination × codec)
#           · apps/integrations/departures.py (the period + target key)
# ───────────────────────────────────────────────────────
"""The accounting export target — a remembered destination and a shape, and nothing more.

WHAT THIS ADAPTER IS FOR
------------------------
A utility hands its month to an accountant. That relationship — *the journal
goes to QuickBooks Desktop, as IIF, and Alex downloads it on the fifth* — is a
CONNECTION, and building and holding it is exactly what `BR-INT-054` leaves
with this module. What is IN the journal is Runbooks'.

So this file can shape a file and place it, and prove it can do both. It cannot
decide which figures belong in one, and it imports no ledger, no chart of
accounts and no projection with which to try.

⚠ **`destination × codec`, AND THE DEFECT THAT SPLIT THEM.** `ledger`'s
`target` column mixes the two — `qbo` and `xero` are accounting SYSTEMS, `csv`
and `iif` are file SHAPES — so a utility wanting a CSV dropped in a folder for
its Xero bookkeeper cannot say so. Filed as `DEF-INT-4243` before this file was
written. Here they are two fields, and `file_format` maps one-for-one onto the
ledger's existing string so no signed idempotency key moves.

⚠ **`test()` WRITES A ZERO-ROW EXPORT (BR-INT-019, `US-INT-033` TC-5).** The
design underlines what a `test()` must not be: *"I have seen this method built
as 'does the API key parse' more times than any other mistake in this space…
A test that cannot fail the way production fails is worse than no test, because
someone trusted it."* For a download target there is no credential to parse and
no far end to dial, so the smallest REAL instance of *export a journal* is
**export a journal with no rows in it**: the codec is asked for bytes, and for
a `drop` destination those bytes are written to the real folder with the real
password. It fails the way production fails — a wrong folder password refuses
here exactly as it would on the fifth of the month.

⚠ **AND A ZERO-ROW FILE IS NOT AN EMPTY FILE.** `!TRNS` … `!ENDTRNS` with no
entries is a valid IIF file that QuickBooks will open and find nothing in. That
distinction is the whole reason this test earns its sentence: *Wrote an empty
QuickBooks file* is a claim about a FILE, and a zero-byte artefact would not
support it.

⚠ **TWO FORMATS THIS CONNECTION OFFERS HAVE NO WRITER, AND `test()` SAYS SO
RATHER THAN PASSING.** `xero`'s column layout is a projection and is Runbooks'
(`CR-069` §20.4); `qbo` is wave I's and has not landed. Both are REGISTERED, so
the picker may offer them and `departures.require_registered_format` accepts
them — and `test()` answers `ok=False` *No writer for that format yet.* That is
hard-won law 7 in its *incapable of failing* shape: a `test()` that reports
success because it never wrote anything is the credential-parse mistake
wearing better manners.

⚠ **AND THERE IS NO FOLDER CLIENT INSTALLED ON THIS DEPLOYMENT.** A `drop`
destination cannot be dialled here for the same reason wave I's bank folder
cannot: `FOLDER_WRITER` is unbound. `test()` answers `ok=False` with a plain
sentence rather than a pass it has not earned, and the gap is recorded in the
wave J walkthrough so it goes red in BOTH directions — install a writer and
leave the gap, and the walkthrough fails for being stale.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from apps.integrations import codecs
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
from apps.integrations.manifests.accounting_file import (
    DESTINATION_DOWNLOAD,
    DESTINATION_DROP,
    DESTINATIONS,
    FILE_FORMATS,
)
from apps.integrations.scrubbing import scrub

#: The fields a `drop` destination needs and a `download` must not carry.
DROP_FIELDS = ("drop_host", "drop_username")
DROP_SECRET = "drop_password"

#: What a clerk calls each format. Used in `describe()` and in `test()`'s
#: sentence; no enum word reaches a screen (B14 rule 32).
FORMAT_NAMES = {
    "qbo": "QuickBooks Online",
    "xero": "Xero",
    "csv": "CSV",
    "iif": "QuickBooks",
}


class FolderWriter:
    """What this adapter needs of an SFTP client, and the whole of it.

    One method. A real client is adapted to this shape in ONE place and bound
    to `FOLDER_WRITER`; nothing else in the product learns that a particular
    library exists. It WRITES — unlike wave I's `FolderClient`, which only
    lists — because a drop target's smallest real instance is placing a file,
    and listing a folder would not prove we may write to it.
    """

    def write(
        self, *, host: str, username: str, password: str, path: str, filename: str, payload: bytes
    ) -> None:
        raise NotImplementedError


#: The seam. `None` on this deployment — no SFTP client is installed. A test
#: binds a recorded writer here; production binds a real one. A module
#: attribute rather than a constructor argument because `services` builds the
#: adapter with no arguments, like every other one.
FOLDER_WRITER: FolderWriter | None = None

#: ≤ 6 words each (B14 rule 33), no rule id and no status code (rule 32).
NO_WRITER_SENTENCE = "No writer for that format yet."
NO_CLIENT_SENTENCE = "No folder client is installed."
REFUSED_SENTENCE = "The folder refused the credential."
UNREACHABLE_SENTENCE = "The folder could not be reached."

#: The name a zero-row test file is written under. It carries the word `test`
#: on purpose: an accountant who finds it in the drop folder should be able to
#: tell at a glance that nobody's July is in it.
TEST_BASENAME = "smartbillhub-test-export"


def folder_writer() -> FolderWriter | None:
    """The bound writer, read at CALL time and never captured at import.

    ⚠ READ THROUGH A FUNCTION ON PURPOSE, and the reason is wave I's. A
    module-level `from … import FOLDER_WRITER` in a test would freeze whatever
    was bound at import, and a test that binds a writer afterwards would
    exercise the *no client* branch while appearing to test the real one — a
    check looking at the wrong thing (hard-won law 7).
    """
    return FOLDER_WRITER


class AccountingFileAdapter(Adapter):
    """Four methods. It shapes a file, places it, and says where it goes."""

    key = "accounting_file"

    # ── validate ────────────────────────────────────────────────────────────

    def validate(self, config: Mapping[str, Any]) -> FieldErrors:
        """Accounting knowledge on top of the manifest's own shape check.

        The manifest already refuses a missing `label`, a `destination` outside
        its two values and a `file_format` outside its four. What it cannot see
        is the RELATIONSHIP between `destination` and the four folder fields —
        that a `drop` destination without a host is not a destination, and that
        folder credentials typed against a `download` are a secret we would be
        holding for no reason at all.

        No network, and none is reachable from here — the conformance kit
        forbids a socket inside `validate()` and asserts it.
        """
        errors: FieldErrors = []
        destination = config.get("destination")

        if destination is not None and destination not in DESTINATIONS:
            errors.append(
                FieldError("destination", message_key="integrations.field.destination")
            )

        file_format = config.get("file_format")
        if file_format is not None and file_format not in FILE_FORMATS:
            errors.append(
                FieldError("file_format", message_key="integrations.field.export_format")
            )

        if destination == DESTINATION_DROP:
            for name in DROP_FIELDS:
                if not _present(config.get(name)):
                    errors.append(
                        FieldError(name, message_key="integrations.field.drop_required")
                    )
        elif destination == DESTINATION_DOWNLOAD:
            # ⚠ REFUSED, NOT IGNORED — wave I's rule, one direction along. A
            # folder password stored against a connection that will never dial
            # a folder is a secret held for no purpose, and the cheapest secret
            # to keep safe is the one we declined to take (BR-INT-003).
            for name in (*DROP_FIELDS, "drop_path", DROP_SECRET):
                if _present(config.get(name)):
                    errors.append(
                        FieldError(name, message_key="integrations.field.drop_not_needed")
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
        """Write a zero-row export. Ask nobody what belongs in one.

        Never raises for the far end's refusal — a wrong folder password is
        `TestResult(ok=False, …)` with the folder's own words underneath, shown
        to the owning tenant only.
        """
        config = conn.config or {}
        file_format = str(config.get("file_format") or "")

        try:
            payload = zero_row_export(file_format)
        except codecs.UnregisteredName as exc:
            #: A format nobody registered at all. Refused by name with the
            #: list, which is `BR-INT-031` outbound and is the same refusal
            #: `departures` gives — said here because a test is the first place
            #: a typo in a config surfaces.
            return TestResult(ok=False, sentence=_unregistered_sentence(exc.asked))
        except NoWriter:
            return TestResult(ok=False, sentence=NO_WRITER_SENTENCE)

        if config.get("destination") != DESTINATION_DROP:
            #: A download has no far end. The file was built, which is the
            #: whole of what a download target can be tested for, and the
            #: sentence says what was built rather than that "the test passed".
            return TestResult(ok=True, sentence=_wrote_sentence(file_format))

        writer = folder_writer()
        if writer is None:
            return TestResult(ok=False, sentence=NO_CLIENT_SENTENCE)

        try:
            writer.write(
                host=str(config.get("drop_host") or ""),
                username=str(config.get("drop_username") or ""),
                password=str(secrets.get(DROP_SECRET) or ""),
                path=str(config.get("drop_path") or "."),
                filename=f"{TEST_BASENAME}.{codecs.CODECS.require(file_format).extension}",
                payload=payload,
            )
        except PermissionError as exc:
            return TestResult(
                ok=False, sentence=REFUSED_SENTENCE, provider_text=scrub(str(exc))
            )
        except Exception as exc:  # noqa: BLE001 — a provider's refusal is a result, never a raise
            return TestResult(
                ok=False, sentence=UNREACHABLE_SENTENCE, provider_text=scrub(str(exc))
            )

        return TestResult(ok=True, sentence=_wrote_sentence(file_format))

    # ── execute ─────────────────────────────────────────────────────────────

    def execute(
        self,
        conn: ConnectionView,
        secrets: Mapping[str, str],
        work: Sequence[Mapping[str, Any]],
    ) -> RunResult:
        """One attempt at a batch of already-built files — PLACE them, build none.

        ⚠ WHAT THIS DELIBERATELY DOES NOT DO IS THE POINT OF THE WAVE. It does
        not read a period, compose a journal, or ask the ledger anything. Each
        item arrives with its BYTES ALREADY BUILT — a `payload` and a
        `filename` — and this places them. Where those bytes came from is
        Runbooks' (`BR-INT-054`, `CR-069` §20.4), and until Runbooks lands
        nothing calls this with a non-empty batch, which is why an empty batch
        is a confirmed success rather than an error.
        """
        if not work:
            return RunResult(items=(), confirmed=True)

        config = conn.config or {}
        if config.get("destination") != DESTINATION_DROP:
            #: A download is placed by the person pressing the button, not by a
            #: runner. There is nothing here to dial and nothing to fail.
            return RunResult(
                items=tuple(
                    ItemResult(ref=_ref(one), outcome=ITEM_SUCCEEDED) for one in work
                ),
                confirmed=True,
            )

        writer = folder_writer()
        if writer is None:
            return RunResult(
                items=tuple(
                    ItemResult(ref=_ref(one), outcome=ITEM_FAILED, detail=NO_CLIENT_SENTENCE)
                    for one in work
                ),
                confirmed=True,
            )

        items: list[ItemResult] = []
        for one in work:
            try:
                writer.write(
                    host=str(config.get("drop_host") or ""),
                    username=str(config.get("drop_username") or ""),
                    password=str(secrets.get(DROP_SECRET) or ""),
                    path=str(config.get("drop_path") or "."),
                    filename=_ref(one),
                    payload=bytes(one.get("payload") or b""),
                )
            except Exception as exc:  # noqa: BLE001 — per-item, never a raise
                items.append(
                    ItemResult(
                        ref=_ref(one), outcome=ITEM_FAILED, provider_text=scrub(str(exc))
                    )
                )
            else:
                items.append(ItemResult(ref=_ref(one), outcome=ITEM_SUCCEEDED))
        return RunResult(items=tuple(items), confirmed=True)

    # ── describe ────────────────────────────────────────────────────────────

    def describe(self, conn: ConnectionView) -> str:
        """*Month-end journal · QuickBooks · downloaded here* — no secret.

        The folder password is not here and cannot be: `ConnectionView` carries
        the connection's non-secret config and the plaintext never travels on
        it (BR-INT-003). The conformance kit asserts that no secret reaches
        this sentence for every adapter, including this one.
        """
        config = conn.config or {}
        parts: list[str] = []
        label = conn.label or config.get("label")
        if label:
            parts.append(str(label))
        file_format = config.get("file_format")
        if file_format:
            parts.append(FORMAT_NAMES.get(str(file_format), str(file_format).upper()))
        if config.get("destination") == DESTINATION_DROP:
            host = config.get("drop_host")
            parts.append(f"dropped at {host}" if host else "dropped in a folder")
        else:
            parts.append("downloaded here")
        return " · ".join(parts) if parts else "Accounting export file"


class NoWriter(LookupError):
    """A registered format with no encoder — said, never silently skipped."""


def zero_row_export(file_format: str) -> bytes:
    """The bytes of an export with no rows in it, in `file_format`.

    ⚠ **NO PROJECTION AND NO BUSINESS DATA REACH THIS FUNCTION**, which is what
    makes it integrations' to write at all. It hands the codec an EMPTY row
    list and the header a journal file declares, and the codec writes its own
    format's grammar around nothing. `departures.journal_rows()` — the door
    Runbooks arrives through — returns `[]` today, and this is the one caller
    for which `[]` is not a shortfall but the answer.

    Raises `codecs.UnregisteredName` for a format nobody registered and
    `NoWriter` for one registered with no encoder.
    """
    codec = codecs.CODECS.require(file_format)
    if codec.encode is None:
        raise NoWriter(file_format)
    return codec.encode((), JOURNAL_HEADER)


#: The columns a journal file declares. ⚠ THESE ARE THE FOUR AN EXPORT BATCH
#: ALREADY RECORDS — `apps/ledger/exports.batch_dict` — rather than a fifth
#: opinion invented here, and they carry NO figure: a zero-row file has a
#: declaration and no entries, so this list decides the file's SHAPE and never
#: its contents. Which of a period's figures fills them is `journal_rows()`'s
#: and is Runbooks' (`BR-INT-054`).
JOURNAL_HEADER = ("account", "name", "date", "amount", "currency", "memo")


def _wrote_sentence(file_format: str) -> str:
    """*Wrote an empty QuickBooks file.* — five words, a real fact, no code."""
    return f"Wrote an empty {FORMAT_NAMES.get(file_format, file_format.upper())} file."


def _unregistered_sentence(asked: str) -> str:
    """*xlsx is not a registered format.* The LIST belongs to the refusal a
    clerk gets from `departures`, which knows this connection's four; a test
    result is one clause (B14 rule 33)."""
    return f"{asked} is not a registered format."


def _present(value: Any) -> bool:
    return value is not None and not (isinstance(value, str) and value.strip() == "")


def _ref(one: Mapping[str, Any]) -> str:
    """The file name — what a clerk would search for, never a database id
    (B14 rule 31)."""
    return str(one.get("filename") or one.get("ref") or "")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-009 · US-INT-033 TC-5 · US-INT-010 (EP-INT-03, EP-INT-09) +
#         BR-INT-010 · 019 · 003 · 038 · 043 + BR-INT-054 as amended
#         2026-09-06 (CR-069 §20.4 wave J)
# generated: 2026-09-06 by the CR-069 wave J build lane
# checklist: A✔ B✔ C✔ D✔ E✔(S141's accounting variant, generated from the
#            manifest) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_038_export_target.py (conformance kit included)
# exceptions: (1) NO FOLDER CLIENT IS INSTALLED on this deployment, so
#             `FOLDER_WRITER` is unbound and a `drop` destination answers
#             ok=False rather than a pass it has not earned — recorded as a
#             known gap so it goes red in both directions · (2) `xero` and
#             `qbo` are registered with no encoder, so `test()` answers *No
#             writer for that format yet.* — `xero`'s layout is a projection
#             and is Runbooks' by ruling, `qbo` is wave I's
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
