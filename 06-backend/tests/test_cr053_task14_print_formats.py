# ── Trace ──────────────────────────────────────────────
# Change:   CR-053 task 14 — *"build the PDF set first and the extract behind a
#           named format parameter"*. The PDF set, the manifest and the
#           held-back list shipped as task 13 (`v2.109.0`); this is the named
#           format parameter.   Screens: the Print bills screen (unchanged)
# Rules:    BR-NOT-1030 (an unregistered print file format is REFUSED by name
#           and never substituted; the format is part of the idempotency key) ·
#           BR-NOT-029 (the ratified fourteen manifest columns) ·
#           BR-SHL-020 (a refusal a human can act on) · B14 rule 32 / G28 ·
#           CLAUDE.md hard rule 6 (idempotency)
# Questions: OQ-1167 — OPEN. Which format, which fields, how a batch is
#           delimited: all three are the vendor's and none is decided here.
# Impacts:  apps/billing/print_formats.py · print_set.py · print_api.py
# ───────────────────────────────────────────────────────
"""CR-053 task 14 — the mechanism, with one honest default.

WHAT THIS FILE PROVES:

  tc1   exactly one format is registered, and it is the file this product
        already hands over — not an invention
  tc2   its columns ARE `BR-NOT-029`'s ratified fourteen, in the ruled order,
        taken from one place rather than restated
  tc3   asking for nothing gets the default, and the archive is what task 13
        shipped — same filename, same header, same rows
  tc4   **asking for a format nobody registered REFUSES BY NAME and says which
        formats exist** — never a silent fallback
  tc5   the refusal is a sentence a clerk can act on and carries no internal id
  tc6   registering a new format is the whole of adding one — a registration,
        not a project — and it reaches the archive
  tc7   two formats cannot share one name
  tc8   the FORMAT is part of the print set's idempotency key, so two shapes of
        the same selection are two jobs and not one handed back twice
  tc9   the job body refuses an unknown format too, and a payload written
        before this parameter existed still gets the file it was going to get
  tc10  `OQ-1167` is still OPEN and the code still says what is the vendor's

⚠ **WHAT THIS FILE DELIBERATELY DOES NOT PROVE.** It does not check that any
particular vendor's format is right, because no vendor has told us one. The
decision log of 2026-08-30 refused to mount this behind an EMPTY registry —
*"that route can only ever refuse, and a route that answers 501 is a promise"*
— and the answer here is a registry with one real, already-ratified,
already-shipping format in it. That makes the mechanism honest without
answering a question that is not ours.
"""

import csv
import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from apps.billing import print_formats, print_set
from apps.billing.exceptions import BillingRuleError

REPO = Path(__file__).resolve().parents[2]
OPEN_QUESTIONS = REPO / "12-governance" / "01-open-questions.md"
GENERATED_AT = datetime(2026, 9, 1, 9, 30, tzinfo=timezone.utc)


@pytest.fixture()
def clean_registry():
    """Put the registry back after a case adds to it. It is module state."""
    saved = dict(print_formats._registry)
    yield
    print_formats._registry.clear()
    print_formats._registry.update(saved)


def _an_empty_set(tmp_path, name="set.zip", **kwargs):
    """A print set over NO bills. Enough to prove which file the format wrote.

    Deliberately empty: this file is about the FORMAT, and task 13's own suite
    already proves the rows. An empty set still writes the header, the held
    list and the README, which is everything a format decides.
    """
    return print_set.build_print_set(iter(()), tmp_path / name, generated_at=GENERATED_AT, **kwargs)


def _members(path):
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


# ══════════════════════════════════════════════════════════════════════════
# tc1-tc3 — one format, and it is the one already shipping
# ══════════════════════════════════════════════════════════════════════════
def test_cr053_tc1__exactly_one_format_is_registered_and_it_is_not_an_invention():
    assert print_formats.names() == ("manifest-csv",)
    fmt = print_formats.get(None)
    assert fmt.name == print_formats.DEFAULT_FORMAT_NAME == "manifest-csv"
    assert fmt.filename == "manifest.csv"
    assert fmt.summary and not fmt.summary.endswith(" ")


def test_cr053_tc2__the_columns_are_the_ratified_fourteen_from_one_place():
    """`BR-NOT-029`'s fourteen, and the registry does not hold a second copy.

    A field list restated in the format would be two answers to *"what does a
    print vendor receive"*, and they would drift the first time one moved.
    `columns=None` means *the caller's ratified list*, which is
    `print_set.MANIFEST_HEADER`.
    """
    fmt = print_formats.get(None)
    assert fmt.columns is None
    assert fmt.header_for(print_set.MANIFEST_HEADER) == print_set.MANIFEST_HEADER
    assert len(print_set.MANIFEST_HEADER) == 14
    assert print_set.MANIFEST_HEADER[0] == "account_no"
    assert print_set.MANIFEST_HEADER[-1] == "pdf_filename"


def test_cr053_tc3__asking_for_nothing_gets_what_task_13_already_shipped(tmp_path):
    """The default archive is byte-compatible with the one before this change.

    An existing caller sends no `format`, and everything it knows about the
    file — its name, its header row, its column order — is unchanged.
    """
    result = _an_empty_set(tmp_path)
    members = _members(tmp_path / "set.zip")
    assert "manifest.csv" in members
    assert result.manifest_name == "manifest.csv"
    header = next(csv.reader(io.StringIO(members["manifest.csv"].decode("utf-8"))))
    assert tuple(header) == print_set.MANIFEST_HEADER
    assert "manifest.csv" in members[print_set.README_NAME].decode("utf-8")


# ══════════════════════════════════════════════════════════════════════════
# tc4-tc5 — the refusal, which is the whole point of a NAMED format
# ══════════════════════════════════════════════════════════════════════════
def test_cr053_tc4__an_unregistered_format_refuses_by_name_and_never_falls_back():
    """⚠ **THE ONE BEHAVIOUR THIS FEATURE EXISTS FOR.**

    A print vendor handed a file in a shape their loader does not read either
    stops — a bad day — or reads the wrong field into the wrong place, which is
    bills posted to the wrong people. So an unknown name produces NOTHING, and
    the refusal names what was asked for and what exists.
    """
    with pytest.raises(BillingRuleError) as refused:
        print_formats.get("xml")
    said = str(refused.value)
    assert "'xml'" in said or '"xml"' in said
    assert "manifest-csv" in said, "the refusal must say which formats DO exist"
    # …and it did not quietly hand back the default.
    assert print_formats.get("manifest-csv").name == "manifest-csv"


def test_cr053_tc5__the_refusal_is_clerk_copy():
    """`BR-SHL-020` / B14 rule 32: a person has to be able to act on it."""
    with pytest.raises(BillingRuleError) as refused:
        print_formats.get("fixed-width")
    said = str(refused.value)
    for forbidden in ("BR-", "OQ-", "DEF-", "CR-", "print_formats", "PrintFormat"):
        assert forbidden not in said, f"{forbidden!r} is not something a clerk should read"
    assert "we will not guess" in said


# ══════════════════════════════════════════════════════════════════════════
# tc6-tc7 — adding a vendor's shape is a REGISTRATION
# ══════════════════════════════════════════════════════════════════════════
def test_cr053_tc6__a_new_format_is_a_registration_and_it_reaches_the_archive(
    tmp_path, clean_registry
):
    """The claim the task makes, exercised: a format is a registration.

    This one is a pipe-separated file with its own name, its own field list and
    no header row — three of the things a real vendor spec differs on — and
    nothing in `print_set.py` or `print_api.py` changed to accept it.
    """

    class _PipeWriter:
        def __init__(self, path, header):
            self.handle = path.open("w", encoding="utf-8", newline="")
            self.header = tuple(header)

        def writerow(self, cells):
            self.handle.write("|".join(cells) + "\n")

        def close(self):
            self.handle.close()

    acme = print_formats.PrintFormat(
        name="acme-pipe",
        filename="ACMEBILL.TXT",
        summary="a pipe-separated file with no header line",
        open_writer=_PipeWriter,
        columns=("bill_no", "amount_due"),
    )
    print_formats.register(acme)

    assert "acme-pipe" in print_formats.names()
    assert print_formats.get("acme-pipe") is acme
    assert acme.header_for(print_set.MANIFEST_HEADER) == ("bill_no", "amount_due")

    _an_empty_set(tmp_path, manifest_format=acme)
    members = _members(tmp_path / "set.zip")
    assert "ACMEBILL.TXT" in members
    assert "manifest.csv" not in members
    assert members["ACMEBILL.TXT"] == b""  # no header line, and no bills


def test_cr053_tc7__two_formats_cannot_share_one_name(clean_registry):
    """A file whose shape depends on import order is a file nobody can debug."""
    other = print_formats.PrintFormat(
        name="manifest-csv",
        filename="something-else.csv",
        summary="a second thing wearing the same name",
        open_writer=print_formats.MANIFEST_CSV.open_writer,
    )
    with pytest.raises(BillingRuleError):
        print_formats.register(other)
    assert print_formats.get("manifest-csv").filename == "manifest.csv"


# ══════════════════════════════════════════════════════════════════════════
# tc8-tc9 — the format on the wire: the key, and the worker
# ══════════════════════════════════════════════════════════════════════════
def test_cr053_tc8__the_format_is_part_of_the_idempotency_key():
    """Two shapes of the same selection are two files, so they are two jobs.

    Hard rule 6 makes the scope key the idempotency; leaving the format out of
    it would fold the second caller onto the first one's record and hand them
    an archive in a shape they did not ask for, reported as a success.
    """
    source = Path(print_set.__file__).read_text(encoding="utf-8")
    assert 'scope_key=f"billing:print-set:{fmt.name}:{scope}"' in source, (
        "the print set's scope key no longer carries the format — two vendor "
        "shapes of one selection would fold into one job"
    )


@pytest.mark.django_db
def test_cr053_tc9__the_worker_refuses_an_unknown_format_and_tolerates_an_old_payload(monkeypatch):
    """Both doors, and the deploy case.

    The door check in `enqueue_print_set` is the one a person sees. The worker
    checks again because a payload can be hand-written or replayed — and a
    payload from BEFORE this parameter existed, already sitting in the broker
    during a deploy, carries no `format` at all and must get the file it was
    always going to get.
    """
    assert print_formats.get(None).name == print_formats.DEFAULT_FORMAT_NAME
    assert print_formats.get("").name == print_formats.DEFAULT_FORMAT_NAME
    with pytest.raises(BillingRuleError):
        print_formats.get("no-such-shape")

    source = Path(print_set.__file__).read_text(encoding="utf-8")
    assert 'print_formats.get(payload.get("format"))' in source, (
        "the job body no longer resolves the format from its payload, so a "
        "hand-written payload could produce the wrong file quietly"
    )


# ══════════════════════════════════════════════════════════════════════════
# tc10 — the question this does NOT answer
# ══════════════════════════════════════════════════════════════════════════
def test_cr053_tc10__oq_1167_is_still_open_and_the_code_still_says_so():
    """A working default must not be read as the question being closed.

    The register still carries the question, and the module that could be
    mistaken for the answer still names the three parts that are the vendor's.
    """
    register = OPEN_QUESTIONS.read_text(encoding="utf-8")
    row = [line for line in register.splitlines() if line.startswith("| OQ-1167 ")]
    assert row, "OQ-1167 has left the open-questions register"
    assert "**OPEN**" in row[0], "OQ-1167 was closed by somebody, and no vendor has answered"

    module = Path(print_formats.__file__).read_text(encoding="utf-8")
    assert "OQ-1167" in module
    for still_theirs in ("WHICH FORMAT", "WHICH FIELDS", "DELIMITED"):
        assert still_theirs in module, (
            f"the module no longer states that {still_theirs.lower()} is the vendor's, so a "
            f"reader could take the working default for the answer"
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-053 task 14 (12-governance/11-change-requests.md) + BR-NOT-1030
#         and BR-NOT-029 (04-docs/05-modules/10-notifications/02-business-rules.md)
#         + OQ-1167 (12-governance/01-open-questions.md)
# generated: 2026-09-01 by the CR-051 task 30 / CR-053 task 14 lane
# checklist: A✔ B=n/a(no screen change) C✔ D=n/a E=n/a F✔ G✔
#         H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_cr053_print_set.py unchanged and green ·
#         golden-verify 33 PASS / 0 FAIL before and after.
#         RED PROVED FIRST: `get()` made to return the default for an unknown
#         name → tc4 fails on *"DID NOT RAISE"*; the format dropped from the
#         scope key → tc8 fails. Both quoted in the lane report.
# exceptions: (1) tc8 AND tc9 READ THE SOURCE rather than exercising an
#         enqueue. Both properties live in code that needs a provisioned tenant
#         and a job store to reach, and what they assert is a LITERAL — a scope
#         key's shape and which payload key the body reads — which a behavioural
#         test would restate rather than check. The behaviour either side of
#         them is covered by tests/test_cr053_print_set.py.
#         (2) THE SETS BUILT HERE ARE EMPTY. This file is about which FILE the
#         format wrote and what it is called; task 13's suite owns the rows.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
