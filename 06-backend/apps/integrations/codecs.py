# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-039 (EP-INT-10) — format is a parameter: projection × codec
#           × packaging, and one projection proved through two codecs.
#           Screens: S141 (the format picker, only where more than one codec is
#           registered) · S142 (the codec named on a run)
# Rules:    BR-INT-033 (format is a REGISTERED codec, separate from the
#           projection; an unregistered name is refused BY NAME with the list
#           of what exists; a picker only where more than one is registered; a
#           codec with no recorded fixture is NOT a supported format) ·
#           BR-INT-038 (a partner's rename touches the projection, never a
#           model) · BR-NOT-1030 (the print-vendor half of the same rule — an
#           unregistered format is refused by name and never substituted) ·
#           CLAUDE.md hard rule 2 (money displays at two decimals; a file that
#           leaves the building is a display)
# Questions: OQ-1167 — still the vendor's (which print format, which fields,
#           how a batch is delimited). This module is the mechanism their
#           answer arrives through, not the answer.
# Tests:    06-backend/tests/test_us_int_039_codecs.py (TC-1..6) ·
#           06-backend/tests/test_cr053_task14_print_formats.py (unchanged and
#           green — the print registry now reads from here)
# Impacts:  apps/integrations/registry.py (a manifest's codec names are
#           validated against `CODECS` here, at load) · apps/billing/print_formats.py
#           (its registry IS a `NamedRegistry` from here — one registry, not
#           two) · apps/integrations/fixtures/<codec>/ (the recorded files)
# ───────────────────────────────────────────────────────
"""integrations codecs — three registries, one refusal, and no format written twice.

WHAT THIS IS, IN ONE SENTENCE
════════════════════════════════════════════════════════════════════════════
The same fact leaves this product in different SHAPES for different partners —
a payment as JSON to one finance system and as XML to another — and this is
where the shapes are declared, so that **asking for a format is asking for a
name**, a name nobody registered is REFUSED with the list of names that exist,
and adding a partner's shape is a registration rather than a second copy of the
projection.

Three declared values on an operation (US-INT-039, design §2.17.3):

  * a **PROJECTION** — which of our fields, under which external names, in
    which order (`gl_payment_v1`, `bill_message_v1`). When a partner renames
    `paymentDate` to `postedDate`, that is ONE edit here and nothing else moves
    — not a model, not a migration, not a codec (BR-INT-038, TC-5).
  * a **CODEC** — how those fields become bytes (`json · xml · csv · mime`), or
    how a partner's bytes become fields on the way in (`bai2 · camt053 · ofx`).
  * a **PACKAGING** — what wraps the bytes (`none · zip · pgp`).

`emit(projection, codec, objects)` is the one function a runner calls, and it
cannot be called with a name that was never registered.

LIFTED FROM `apps/billing/print_formats.py`, AND WHY IT IS NOT A COPY
════════════════════════════════════════════════════════════════════════════
`CR-053` task 14 shipped the pattern on 1 September for the print vendor: a
registry keyed by name, a refusal that lists what exists, a `register()` that
refuses to replace a name. `US-INT-039` says that registry *"becomes the
module's"*. It does, literally: `NamedRegistry` below is that mechanism made
generic, and `print_formats.NAMED_FORMATS` is an instance of it — so there is
ONE registry implementation in this repository and the print vendor's formats
and the integration codecs are two lists on it, not two mechanisms (TC-6).

WHAT *SUPPORTED* MEANS, AND WHY IT IS NARROWER THAN *REGISTERED*
════════════════════════════════════════════════════════════════════════════
`BR-INT-033`: *"a codec with no recorded fixture from the real provider is not
a supported format."* So a codec has two independent properties:

  * **REGISTERED** — its name is known here. A manifest may name it, and S141's
    picker may offer it (a picker appears only where a manifest registers more
    than one). Registration is what makes the refusal-by-name possible.
  * **SUPPORTED** — a recorded fixture exists under `fixtures/<codec>/`, and
    the codec carries an encoder or a decoder. `check_fixtures()` is the
    conformance kit's reading of it, and a registered codec with no fixture is
    reported as *not a supported format* (TC-4).

⚠ **THE HONEST STATE AT HEAD, WRITTEN DOWN RATHER THAN IMPLIED — AND WAVE J
ADDED A THIRD STATE, WHICH IS THE PART A READER WILL NOT EXPECT.** Registered
and supported are not two halves of one line; there are three positions:

  * **SUPPORTED** — code AND a recorded fixture: `json · xml · csv · mime`,
    and now `iif`. For every one of those WE are the emitter, so the fixture is
    our own recorded output (the worked payment `PAY-2609-0311 · $142.18`, and
    for `iif` the worked July journal), checked byte-for-byte by the tests.
  * **CODE, NO RECORDED FILE** — `camt053` since wave J. It decodes, and
    `is_supported()` still answers **False**, because no real bank's statement
    has been recorded yet. `check_fixtures()` says *not a supported format*
    about it, truthfully, and that is `US-INT-038` TC-6's exact shape.
  * **NAME ONLY** — `xero · qbo · ofx · qfx · bai2 · pdf`: no encoder and no
    decoder, each saying in `arrives` what brings it. ⚠ For `xero` that is no
    longer a wave but a MODULE — its column layout is a projection and
    projections are Runbooks' (`BR-INT-054`, `CR-069` §20.4).

A manifest may name a codec in any of the three states, which is what lets the
accounting card register four and the bank card six without a screen change on
the day the file arrives. **Nothing here pretends to read a BAI2 file.** A
fixture folder that holds only a `PROVENANCE` line is a declared absence, not a
sample somebody typed.

A SILENT FALLBACK IS THE ONE THING THIS MUST NEVER DO
════════════════════════════════════════════════════════════════════════════
`NamedRegistry.require()` refuses an unregistered name and names the
registered ones. It never falls back to a default. A file that reaches a
partner's loader in a shape they did not expect either stops or **reads the
wrong field into the wrong place** — money posted to the wrong account with
nothing going red. A refusal costs one attempt; a substitution costs a close.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from collections.abc import Iterator, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from email import message_from_bytes
from email.message import EmailMessage
from email.policy import default as _email_policy
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree as ET

from core.money import finalize

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"

#: Files in a fixture folder that DESCRIBE rather than ARE a fixture.
_NOT_A_FIXTURE = frozenset({"PROVENANCE", "README.md", ".gitkeep"})


class UnregisteredName(LookupError):
    """A name nobody registered. Carries what was asked and what exists, so a
    caller can phrase the refusal for its own audience without losing either."""

    def __init__(self, what: str, asked: str, available: Sequence[str]) -> None:
        self.what = what
        self.asked = asked
        self.available = tuple(available)
        listed = ", ".join(self.available) if self.available else "(nothing is registered)"
        super().__init__(
            f"there is no {what} called {asked!r}, so nothing has been produced. "
            f"The {what}s this system knows are: {listed}."
        )


class AlreadyRegistered(ValueError):
    """Two different things under one name — a shape that would depend on
    import order, so it is refused."""


class NamedRegistry(MutableMapping):
    """Name → object. Refuses an unknown name BY NAME with the list of what
    exists; refuses to replace a name with a DIFFERENT object.

    A `MutableMapping`, so a test may `dict()` it, `clear()` it and `update()`
    it back — the print-vendor tests have done exactly that since 1 September
    and they keep working unchanged against this class.
    """

    def __init__(self, what: str) -> None:
        self.what = what
        self._entries: dict[str, Any] = {}

    # ── the registry contract ────────────────────────────────────────────
    def register(self, name: str, obj: Any) -> Any:
        existing = self._entries.get(name)
        if existing is not None and existing is not obj and existing != obj:
            raise AlreadyRegistered(
                f"a {self.what} called {name!r} is already registered. Two different "
                f"{self.what}s cannot share one name — give the new one its own."
            )
        self._entries[name] = obj
        return obj

    def names(self) -> tuple[str, ...]:
        """Every registered name, in a stable order a refusal can print."""
        return tuple(sorted(self._entries))

    def require(self, name: str) -> Any:
        """The object called `name`, or `UnregisteredName` — never a default."""
        found = self._entries.get(name)
        if found is None:
            raise UnregisteredName(self.what, name, self.names())
        return found

    def all(self) -> tuple[Any, ...]:
        return tuple(self._entries[name] for name in self.names())

    # ── MutableMapping ───────────────────────────────────────────────────
    def __getitem__(self, name: str) -> Any:
        return self._entries[name]

    def __setitem__(self, name: str, obj: Any) -> None:
        self.register(name, obj)

    def __delitem__(self, name: str) -> None:
        del self._entries[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


# ── projections ─────────────────────────────────────────────────────────────


def _render(value: Any) -> str:
    """One string per cell. Money is DISPLAYED at two decimals here because a
    file that leaves the building is a display (hard rule 2); nothing is
    rounded before this point."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return str(finalize(value))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _read_path(obj: Any, path: str) -> Any:
    """`method.name` → obj.method.name; a mapping is read by key. A missing
    step reads as None — a partner's file carries an empty cell, never a crash
    on the first of the month."""
    current = obj
    for step in path.split("."):
        if current is None:
            return None
        if isinstance(current, Mapping):
            current = current.get(step)
        else:
            current = getattr(current, step, None)
    return current


def _is_name(token: str) -> bool:
    """A field's external name must be a legal XML element name and a legal
    JSON key that no codec has to escape: letters, digits, underscore."""
    return bool(token) and token.replace("_", "a").isalnum() and not token[0].isdigit()


@dataclass(frozen=True)
class ProjectedField:
    """One column of a projection: THEIR name for it, and where OURS lives."""

    external_name: str
    source: str
    summary: str = ""


@dataclass(frozen=True)
class Projection:
    """A named view of one of our things, in a partner's words (C8).

    `fields` is ordered — a CSV column order, an XML element order — and every
    external name is unique. Renaming a field for a partner is a new
    `ProjectedField` here and nothing anywhere else (BR-INT-038).
    """

    name: str
    summary: str
    fields: tuple[ProjectedField, ...]

    def __post_init__(self) -> None:
        if not _is_name(self.name):
            raise ValueError(f"projection name {self.name!r} is not a plain identifier")
        seen: set[str] = set()
        for one in self.fields:
            if not _is_name(one.external_name):
                raise ValueError(
                    f"{self.name}: external name {one.external_name!r} is not a plain identifier"
                )
            if one.external_name in seen:
                raise ValueError(f"{self.name}: external name {one.external_name!r} declared twice")
            seen.add(one.external_name)
        if not self.fields:
            raise ValueError(f"{self.name}: a projection with no fields projects nothing")

    @property
    def header(self) -> tuple[str, ...]:
        return tuple(one.external_name for one in self.fields)

    def project(self, obj: Any) -> dict[str, str]:
        """One row: external name → rendered string, in declared order."""
        return {one.external_name: _render(_read_path(obj, one.source)) for one in self.fields}

    def project_all(self, objects: Sequence[Any]) -> list[dict[str, str]]:
        return [self.project(one) for one in objects]


# ── codecs ──────────────────────────────────────────────────────────────────

Encoder = Callable[[Sequence[Mapping[str, str]], Sequence[str]], bytes]
Decoder = Callable[[bytes], list[dict[str, str]]]


@dataclass(frozen=True)
class Codec:
    """How projected rows become bytes, or how a partner's bytes become rows.

    `encode(rows, header) -> bytes` and `decode(data) -> rows` are each
    Optional: an inbound bank format has no encoder, an outbound message
    format has no decoder, and a codec registered BY NAME ONLY has neither and
    says in `arrives` which wave brings its code.

    `summary` is ONE SENTENCE for a person — no rule id, no register id (B14
    rule 32) — the words a picker puts beside the name.
    """

    name: str
    summary: str
    media_type: str
    extension: str
    encode: Encoder | None = None
    decode: Decoder | None = None
    #: Which wave brings the code, for a name-only registration. None once it
    #: has an encoder or a decoder.
    arrives: str | None = None

    @property
    def name_only(self) -> bool:
        return self.encode is None and self.decode is None

    def describe(self) -> dict[str, Any]:
        """What a picker needs. No internal ids."""
        return {
            "name": self.name,
            "summary": self.summary,
            "media_type": self.media_type,
            "extension": self.extension,
            "supported": is_supported(self.name),
        }


def _encode_json(rows: Sequence[Mapping[str, str]], header: Sequence[str]) -> bytes:
    ordered = [{name: row.get(name, "") for name in header} for row in rows]
    return (json.dumps(ordered, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _decode_json(data: bytes) -> list[dict[str, str]]:
    parsed = json.loads(data.decode("utf-8"))
    if not isinstance(parsed, list):
        raise ValueError("a JSON file of records is a list of objects")
    return [{str(k): _render(v) for k, v in one.items()} for one in parsed]


def _encode_xml(rows: Sequence[Mapping[str, str]], header: Sequence[str]) -> bytes:
    root = ET.Element("records")
    for row in rows:
        record = ET.SubElement(root, "record")
        for name in header:
            ET.SubElement(record, name).text = row.get(name, "")
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n").encode("utf-8")


def _decode_xml(data: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(data)
    rows: list[dict[str, str]] = []
    for record in root.findall("record"):
        rows.append({child.tag: child.text or "" for child in record})
    return rows


def _encode_csv(rows: Sequence[Mapping[str, str]], header: Sequence[str]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(list(header))  # exactly one header row (IS-9)
    for row in rows:
        writer.writerow([row.get(name, "") for name in header])
    return buffer.getvalue().encode("utf-8")


def _decode_csv(data: bytes) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
    return [dict(one) for one in reader]


#: The four headers a `bill_message_v1` row must carry for MIME to be a message.
_MIME_HEADERS = ("to", "sender", "subject")


def _encode_mime(rows: Sequence[Mapping[str, str]], header: Sequence[str]) -> bytes:
    """ONE message per call. A MIME file is a message, not a table; a runner
    that has ninety-three messages calls this ninety-three times."""
    if len(rows) != 1:
        raise ValueError(f"mime encodes exactly one message per call, not {len(rows)}")
    row = rows[0]
    missing = [name for name in _MIME_HEADERS if not row.get(name)]
    if missing:
        raise ValueError(f"a message needs {list(_MIME_HEADERS)}; missing {missing}")
    message = EmailMessage(policy=_email_policy)
    message["To"] = row["to"]
    message["From"] = row["sender"]
    message["Subject"] = row["subject"]
    if row.get("reference"):
        message["X-Bill-Reference"] = row["reference"]
    message.set_content(row.get("body", ""))
    return message.as_bytes()


#: IIF's own three declaration lines. QuickBooks Desktop reads a general
#: journal as a TRNS/SPL/ENDTRNS group per entry, and the `!`-prefixed lines at
#: the top DECLARE which columns follow. Tabs, never commas — a memo with a
#: comma in it is ordinary and would split the row.
_IIF_TRNS = "TRNS"
_IIF_SPL = "SPL"
_IIF_END = "ENDTRNS"
_IIF_SEPARATOR = "\t"


def _encode_iif(rows: Sequence[Mapping[str, str]], header: Sequence[str]) -> bytes:
    """The tab-separated journal QuickBooks Desktop imports (`CR-069` wave J).

    ⚠ **THE COLUMNS ARE THE PROJECTION'S AND THE GRAMMAR IS THE VENDOR'S, AND
    THAT SPLIT IS THE WHOLE REASON THIS FUNCTION IS ALLOWED TO EXIST HERE.**
    `BR-INT-054` as amended (`CR-069` §20.4) keeps codecs with integrations —
    *"a codec is how bytes are shaped on the wire"* — and moves projections to
    Runbooks, because deciding WHICH of our fields is the account number and
    which is the amount builds a business record. This function decides
    neither. It is handed a header and rows and writes IIF's declaration lines,
    its tab separator and its `ENDTRNS` terminator around whatever it is given.

    ⚠ **A ZERO-ROW FILE IS THE DECLARATION LINES AND NOTHING ELSE, AND IT IS A
    VALID IIF FILE.** That is what `adapters/accounting_file.test()` writes: it
    proves this system can shape and place a file without asking anybody what
    belongs in one. `US-INT-033` TC-5.

    ⚠ **A TAB INSIDE A VALUE IS REFUSED, NOT ESCAPED.** IIF has no quoting: a
    tab in a memo silently shifts every later column one place left, which
    posts an amount into a date field with nothing going red. There is no safe
    substitution — dropping the tab changes the memo a person typed — so the
    row is refused and named.
    """
    lines: list[str] = [
        _IIF_SEPARATOR.join([f"!{_IIF_TRNS}", *header]),
        _IIF_SEPARATOR.join([f"!{_IIF_SPL}", *header]),
        f"!{_IIF_END}",
    ]
    for index, row in enumerate(rows):
        values = [str(row.get(name, "")) for name in header]
        for name, value in zip(header, values, strict=True):
            if _IIF_SEPARATOR in value or "\n" in value or "\r" in value:
                raise ValueError(
                    f"row {index + 1} field {name!r} holds a tab or a newline, and IIF has "
                    "no quoting — every later column would shift one place left. Refused "
                    "rather than escaped, because there is no substitution that keeps the "
                    "value a person typed."
                )
        lines.append(_IIF_SEPARATOR.join([_IIF_TRNS, *values]))
        lines.append(_IIF_END)
    return ("\n".join(lines) + "\n").encode("utf-8")


#: The ISO 20022 namespaces a camt.053 statement is served under. A bank picks
#: its own version — `.02` and `.08` are both common in North America — so the
#: decoder matches on the LOCAL tag name and never on the full namespaced one.
#: Pinning a namespace would make a perfectly good statement from a bank that
#: upgraded read as an empty file, which is the worst of the two failures: it
#: is silent.
_CAMT_ENTRY = "Ntry"


def _camt_local(tag: str) -> str:
    """`{urn:iso:std:iso:20022:tech:xsd:camt.053.001.02}Ntry` → `Ntry`."""
    return tag.rsplit("}", 1)[-1]


def _camt_first(element: Any, *path: str) -> str:
    """The text of the first descendant matching a chain of LOCAL names, or ``.

    Walks by local name at every step, so it is version-agnostic in the same
    way `_CAMT_ENTRY` is.
    """
    current = element
    for name in path:
        found = None
        for child in current.iter():
            if child is current:
                continue
            if _camt_local(child.tag) == name:
                found = child
                break
        if found is None:
            return ""
        current = found
    return (current.text or "").strip()


def _decode_camt053(data: bytes) -> list[dict[str, str]]:
    """A bank's ISO 20022 statement as flat rows — one row per `<Ntry>`.

    ⚠ **THIS READS BYTES INTO FIELDS AND STOPS THERE (`BR-INT-054`).** A row
    that comes out of here says *$142.18 credited on 1 September, the bank's
    reference is `20260901-000318`, the payer wrote `ACC-1048 SEPTEMBER`*.
    Which of our accounts that is, and whether a payment gets written, is
    Runbooks' — this function does not know a customer exists.

    ⚠ **`CdtDbtInd` IS CARRIED, NEVER APPLIED AS A SIGN.** A camt.053 states
    the amount unsigned and the direction beside it. Folding the two into a
    negative number here would decide, in a codec, that a debit means money
    leaving us — which is true of a bank account and false of a lockbox, and
    is exactly the kind of meaning `BR-INT-054` puts on the other side of the
    line. The two fields travel together and separately.

    ⚠ **THE AMOUNT IS THE BANK'S OWN STRING.** Not a `Decimal`, not rounded,
    not reformatted: hard rule 2 governs what we STORE and what we DISPLAY, and
    this is neither — it is what the bank said, on its way to somebody who will
    decide what it means.
    """
    root = ET.fromstring(data)
    rows: list[dict[str, str]] = []
    for element in root.iter():
        if _camt_local(element.tag) != _CAMT_ENTRY:
            continue
        amount_text = ""
        currency = ""
        for child in element.iter():
            if _camt_local(child.tag) == "Amt":
                amount_text = (child.text or "").strip()
                currency = child.attrib.get("Ccy", "")
                break
        rows.append(
            {
                "amount": amount_text,
                "currency": currency,
                "direction": _camt_first(element, "CdtDbtInd"),
                "status": _camt_first(element, "Sts"),
                "booking_date": _camt_first(element, "BookgDt", "Dt"),
                "value_date": _camt_first(element, "ValDt", "Dt"),
                "bank_reference": _camt_first(element, "AcctSvcrRef"),
                "end_to_end_id": _camt_first(element, "EndToEndId"),
                "remittance": _camt_first(element, "RmtInf", "Ustrd"),
            }
        )
    return rows


def _decode_mime(data: bytes) -> list[dict[str, str]]:
    message = message_from_bytes(data, policy=_email_policy)
    body_part = message.get_body(preferencelist=("plain",))
    body = body_part.get_content() if body_part is not None else ""
    row = {
        "to": str(message["To"] or ""),
        "sender": str(message["From"] or ""),
        "subject": str(message["Subject"] or ""),
        "body": body.rstrip("\n"),
    }
    if message["X-Bill-Reference"]:
        row["reference"] = str(message["X-Bill-Reference"])
    return [row]


# ── packaging ───────────────────────────────────────────────────────────────

Wrapper = Callable[[bytes, str], bytes]


@dataclass(frozen=True)
class Packaging:
    """What wraps the bytes. `none` is the identity and is a registration too,
    so that a manifest naming it is validated like any other name."""

    name: str
    summary: str
    extension: str  # appended to the file name, "" for none
    wrap: Wrapper | None = None
    arrives: str | None = None

    @property
    def name_only(self) -> bool:
        return self.wrap is None


def _wrap_none(payload: bytes, filename: str) -> bytes:
    return payload


def _wrap_zip(payload: bytes, filename: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, payload)
    return buffer.getvalue()


# ── the three registries ────────────────────────────────────────────────────

PROJECTIONS = NamedRegistry("projection")
CODECS = NamedRegistry("file format")
PACKAGINGS = NamedRegistry("packaging")


def register_projection(projection: Projection) -> Projection:
    return PROJECTIONS.register(projection.name, projection)


def register_codec(codec: Codec) -> Codec:
    return CODECS.register(codec.name, codec)


def register_packaging(packaging: Packaging) -> Packaging:
    return PACKAGINGS.register(packaging.name, packaging)


def names() -> tuple[str, ...]:
    """Every registered codec name — what `registry.py` validates a manifest
    against at load, and what a refusal lists."""
    return CODECS.names()


def describe_codecs(only: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """What a picker draws. `only` narrows to a manifest's list, in ITS order,
    so the picker's order is the manifest's and not the alphabet's."""
    if only is None:
        return [one.describe() for one in CODECS.all()]
    return [CODECS.require(name).describe() for name in only]


# ── fixtures: the difference between registered and supported ───────────────


def fixture_paths(codec_name: str, root: Path = FIXTURES_ROOT) -> list[Path]:
    """The recorded files for a codec — everything in its folder that is not a
    note ABOUT the folder."""
    folder = root / codec_name
    if not folder.is_dir():
        return []
    return sorted(
        one for one in folder.iterdir() if one.is_file() and one.name not in _NOT_A_FIXTURE
    )


def provenance(codec_name: str, root: Path = FIXTURES_ROOT) -> str | None:
    """The folder's own account of where its files came from, or None."""
    note = root / codec_name / "PROVENANCE"
    if not note.is_file():
        return None
    return note.read_text(encoding="utf-8").strip()


def is_supported(
    codec_name: str, root: Path = FIXTURES_ROOT, *, registry: NamedRegistry | None = None
) -> bool:
    """BR-INT-033 — a fixture exists AND the codec carries code to run on it."""
    codec = (registry if registry is not None else CODECS).get(codec_name)
    if codec is None or codec.name_only:
        return False
    return bool(fixture_paths(codec_name, root))


def supported_names(root: Path = FIXTURES_ROOT) -> tuple[str, ...]:
    return tuple(name for name in names() if is_supported(name, root))


@dataclass(frozen=True)
class FixtureFinding:
    codec: str
    status: str  # "supported" | "not_supported"
    reason: str


def check_fixtures(
    root: Path = FIXTURES_ROOT, *, registry: NamedRegistry | None = None
) -> list[FixtureFinding]:
    """The conformance kit's reading of every registered codec (TC-4).

    A registered codec with no recorded fixture is *not a supported format*
    — said in those words, so a kit that prints this report says what the
    rule says. A name-only codec is reported with the wave that brings it.
    `registry` and `root` exist so a test can prove the kit goes red on a
    codec that has code and no file, without touching the shipped folders.
    """
    findings: list[FixtureFinding] = []
    for codec in (registry if registry is not None else CODECS).all():
        files = fixture_paths(codec.name, root)
        if codec.name_only:
            findings.append(
                FixtureFinding(
                    codec.name,
                    "not_supported",
                    f"registered by name only — no encoder and no decoder; arrives with "
                    f"{codec.arrives or 'a later wave'}",
                )
            )
            continue
        if not files:
            findings.append(
                FixtureFinding(
                    codec.name,
                    "not_supported",
                    f"not a supported format: no recorded fixture under fixtures/{codec.name}/",
                )
            )
            continue
        findings.append(
            FixtureFinding(
                codec.name,
                "supported",
                f"{len(files)} recorded fixture(s): {[f.name for f in files]}",
            )
        )
    return findings


# ── emit: the one call a runner makes ───────────────────────────────────────


@dataclass(frozen=True)
class Emitted:
    """Bytes with the two facts a file needs beside it."""

    payload: bytes
    filename: str
    media_type: str


def emit(
    projection_name: str,
    codec_name: str,
    objects: Sequence[Any],
    *,
    packaging_name: str = "none",
    basename: str | None = None,
) -> Emitted:
    """Project, encode, wrap. Every name is REQUIRED from its registry first —
    an unregistered name refuses before a single row is read (BR-INT-033).

    A name-only codec refuses too, naming the wave that brings its code: a
    manifest may register `bai2` for the picker's sake, but nothing may be
    asked to WRITE a BAI2 file until somebody has built and recorded it.
    """
    projection: Projection = PROJECTIONS.require(projection_name)
    codec: Codec = CODECS.require(codec_name)
    packaging: Packaging = PACKAGINGS.require(packaging_name)
    if codec.encode is None:
        raise UnregisteredName(
            "file format this system can write",
            codec_name,
            tuple(one.name for one in CODECS.all() if one.encode is not None),
        )
    if packaging.wrap is None:
        raise UnregisteredName(
            "packaging this system can apply",
            packaging_name,
            tuple(one.name for one in PACKAGINGS.all() if one.wrap is not None),
        )
    rows = projection.project_all(objects)
    payload = codec.encode(rows, projection.header)
    filename = f"{basename or projection.name}.{codec.extension}"
    wrapped = packaging.wrap(payload, filename)
    return Emitted(
        payload=wrapped,
        filename=filename + packaging.extension,
        media_type=codec.media_type if packaging.name == "none" else "application/zip",
    )


def parse(codec_name: str, data: bytes) -> list[dict[str, str]]:
    """The way back: a partner's bytes as rows. Refuses a codec with no decoder
    by name, listing the ones that have one."""
    codec: Codec = CODECS.require(codec_name)
    if codec.decode is None:
        raise UnregisteredName(
            "file format this system can read",
            codec_name,
            tuple(one.name for one in CODECS.all() if one.decode is not None),
        )
    return codec.decode(data)


# ── the shipped registrations ───────────────────────────────────────────────

#: A payment as a finance system wants it. The field ORDER is the CSV column
#: order and the XML element order; the NAMES are the partner-facing ones.
#: `partner_account` is the partner's own string for our GL account, resolved
#: by the runner through `selectors.mappings()` (BR-INT-032) before the object
#: reaches `project()` — the projection reads it, it does not look it up.
GL_PAYMENT_V1 = Projection(
    name="gl_payment_v1",
    summary="One payment, as a finance system posts it.",
    fields=(
        ProjectedField("paymentNumber", "payment_no", "our receipt number"),
        ProjectedField("paymentDate", "posted_at", "the day it was posted, ISO"),
        ProjectedField("amount", "amount", "two decimals, the display of the stored figure"),
        ProjectedField("currency", "currency", "CHAR(3)"),
        ProjectedField("tender", "method.name", "our payment method, in our words"),
        ProjectedField("account", "account_code", "our GL account code"),
        ProjectedField("partnerAccount", "partner_account", "THEIR string for that account"),
        ProjectedField("customerAccount", "account_no", "the customer's account number"),
    ),
)

#: A bill notice as a mail server wants it — the four headers and a body.
BILL_MESSAGE_V1 = Projection(
    name="bill_message_v1",
    summary="One bill notice, as a message.",
    fields=(
        ProjectedField("to", "to", "the recipient"),
        ProjectedField("sender", "sender", "the utility's send-from address"),
        ProjectedField("subject", "subject", ""),
        ProjectedField("reference", "reference", "the bill number, for the customer"),
        ProjectedField("body", "body", "plain text"),
    ),
)

for _projection in (GL_PAYMENT_V1, BILL_MESSAGE_V1):
    register_projection(_projection)

#: The four with code and a recorded fixture — we are the emitter, so the
#: fixture is our own output on the worked payment, checked byte-for-byte.
for _codec in (
    Codec(
        name="json",
        summary="a list of records, one object each, with the field names as keys.",
        media_type="application/json",
        extension="json",
        encode=_encode_json,
        decode=_decode_json,
    ),
    Codec(
        name="xml",
        summary="a records element holding one record element per row.",
        media_type="application/xml",
        extension="xml",
        encode=_encode_xml,
        decode=_decode_xml,
    ),
    Codec(
        name="csv",
        summary="comma-separated, one row per record, the field names on the first line.",
        media_type="text/csv",
        extension="csv",
        encode=_encode_csv,
        decode=_decode_csv,
    ),
    Codec(
        name="mime",
        summary="an email message with its headers and a plain-text body.",
        media_type="message/rfc822",
        extension="eml",
        encode=_encode_mime,
        decode=_decode_mime,
    ),
    #: `CR-069` wave J. WE are the emitter, so the fixture is our own recorded
    #: output — the README's rule for `json · xml · csv · mime`, and it applies
    #: here for the same reason: there is no "real provider" file to record for
    #: a format WE write and QuickBooks reads.
    Codec(
        name="iif",
        summary="the tab-separated journal QuickBooks Desktop imports.",
        media_type="text/plain",
        extension="iif",
        encode=_encode_iif,
    ),
):
    register_codec(_codec)

#: ⚠ `camt053` IS REGISTERED SEPARATELY BECAUSE IT IS IN A THIRD STATE THIS
#: FILE HAD NO WORD FOR UNTIL WAVE J, AND THE STATE IS WORTH NAMING RATHER THAN
#: ROUNDING TO EITHER NEIGHBOUR.
#:
#:   * name-only     — no code at all; `arrives` says which wave brings it
#:   * supported     — code AND a recorded fixture
#:   * **this one**  — CODE, and NO recorded file from a real bank
#:
#: `is_supported()` therefore answers **False** for it, and `check_fixtures()`
#: reports *not a supported format: no recorded fixture*. That is the honest
#: reading and it is `US-INT-038` TC-6 exactly: a codec with code and no file
#: fails the kit. The decoder is proved against a structural fixture held under
#: `tests/`, deliberately OUTSIDE `fixtures/`, so that the kit cannot be fooled
#: by a sample somebody typed — which is the failure `BR-INT-033` was written
#: against and which a test file cannot cause.
#:
#: ⚠ **WHAT IS STILL OWED IS AN ARTEFACT, NOT A DECISION.** A redacted
#: statement from a real bank is a thing a going-live utility hands us; it is
#: not a question anybody can rule. Recorded as a known gap in the wave J
#: walkthrough so it goes red in BOTH directions — record the file and leave
#: the gap, and the walkthrough fails for being stale.
register_codec(
    Codec(
        name="camt053",
        summary="the newer ISO bank statement, as XML.",
        media_type="application/xml",
        extension="xml",
        decode=_decode_camt053,
    )
)

def _encode_form(rows: Sequence[Mapping[str, str]], header: Sequence[str]) -> bytes:
    """ONE record as `application/x-www-form-urlencoded` — the only body Twilio's
    Messages API accepts (`CR-198-BRC10`). A form carries one record, so more
    than one is refused rather than silently joined."""
    from urllib.parse import urlencode

    if len(rows) != 1:
        raise ValueError("a form body carries exactly one record")
    row = rows[0]
    return urlencode([(name, row.get(name, "")) for name in header if row.get(name, "") != ""]).encode(
        "utf-8"
    )


def _decode_form(data: bytes) -> list[dict[str, str]]:
    """A form-encoded body (a Twilio callback) as ONE record. A repeated key
    keeps its LAST value; the signature check reads the raw pairs, not this."""
    from urllib.parse import parse_qsl

    return [dict(parse_qsl(data.decode("utf-8"), keep_blank_values=True))]


#: `CR-198-BRC10` — `form`, the third state `camt053` names above: CODE, and no
#: recorded file from the real provider (nothing in this environment has ever
#: reached Twilio). Twilio's Messages API takes and its callbacks send
#: `application/x-www-form-urlencoded`; declaring `json` for it (as the
#: placeholder manifest did) was a codec the wire never speaks.
register_codec(
    Codec(
        name="form",
        summary="one record as web-form fields, the way a web page posts a form.",
        media_type="application/x-www-form-urlencoded",
        extension="txt",
        encode=_encode_form,
        decode=_decode_form,
    )
)

#: Registered BY NAME so a manifest may cite them and a picker may offer them;
#: each says which wave builds its code and records its first real file.
#: ⚠ Nothing here reads or writes any of these formats today.
for _codec in (
    #: ⚠ **STILL NAME-ONLY AFTER WAVE J, AND THE REASON CHANGED — WHICH IS WHY
    #: THIS NOTE IS LONGER THAN A WAVE LABEL.** `iif` landed here because IIF's
    #: grammar (the `!TRNS` declarations, the tab, `ENDTRNS`) is the VENDOR's and
    #: is generic over whatever header it is handed. Xero's manual-journal CSV
    #: is not like that: its `*Narration · *Date · *AccountCode · *TaxRate ·
    #: *Amount` columns are a layout OUR figures have to be arranged into, and
    #: choosing which of our fields is `*AccountCode` is a PROJECTION.
    #: `CR-069` §20.4 puts projections in Runbooks in as many words. So this is
    #: a **deliberate absence with a reason**, not an unfinished stub: nothing
    #: is blocked, no question is open, and a lane finding it should leave it
    #: alone until Runbooks has a projection to plug in.
    Codec(
        name="xero",
        summary="the comma-separated journal Xero imports.",
        media_type="text/csv",
        extension="csv",
        arrives="Runbooks — its column layout is a projection (BR-INT-054, CR-069 §20.4)",
    ),
    Codec(
        name="qbo",
        summary="the bank-statement file QuickBooks reads.",
        media_type="application/x-ofx",
        extension="qbo",
        arrives="wave I (the same bank file twice)",
    ),
    Codec(
        name="ofx",
        summary="the older bank-statement exchange file.",
        media_type="application/x-ofx",
        extension="ofx",
        arrives="wave I (the same bank file twice)",
    ),
    Codec(
        name="qfx",
        summary="the bank-statement file Quicken reads.",
        media_type="application/x-ofx",
        extension="qfx",
        arrives="wave I (the same bank file twice)",
    ),
    Codec(
        name="bai2",
        summary="the fixed-record bank statement most US banks send.",
        media_type="text/plain",
        extension="bai",
        arrives="wave I (the same bank file twice)",
    ),
    Codec(
        name="pdf",
        summary="a printed page, as the print set builds it.",
        media_type="application/pdf",
        extension="pdf",
        arrives="the billing print set (CR-053), which builds the PDF set itself",
    ),
):
    register_codec(_codec)

for _packaging in (
    Packaging(name="none", summary="the file as it is.", extension="", wrap=_wrap_none),
    Packaging(
        name="zip", summary="one file inside a zip archive.", extension=".zip", wrap=_wrap_zip
    ),
    Packaging(
        name="pgp",
        summary="the file encrypted to the partner's key.",
        extension=".pgp",
        arrives="wave K (the walk: token exchange, the fetch plan, and the file they build)",
    ),
):
    register_packaging(_packaging)


__all__ = [
    "AlreadyRegistered",
    "BILL_MESSAGE_V1",
    "CODECS",
    "Codec",
    "Emitted",
    "FIXTURES_ROOT",
    "FixtureFinding",
    "GL_PAYMENT_V1",
    "NamedRegistry",
    "PACKAGINGS",
    "PROJECTIONS",
    "Packaging",
    "ProjectedField",
    "Projection",
    "UnregisteredName",
    "check_fixtures",
    "describe_codecs",
    "emit",
    "fixture_paths",
    "is_supported",
    "names",
    "parse",
    "provenance",
    "register_codec",
    "register_packaging",
    "register_projection",
    "supported_names",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-039@87b94265 (EP-INT-10 story + BR-INT-033 · BR-INT-038 verbatim; co-packet CR-053 task 14's print_formats.py, the lifted pattern)
# generated: 2026-09-03 by the CR-069 wave D build lane
# checklist: A✔ B✔ C✔ D✔(GET /integrations serves each card's `codecs`; the picker reads them) E=deferred(S141's picker is B4's modal, which had not landed at HEAD when this was written — see the decision log 2026-09-03) F✔ G✔ H=n/a(no RLS, no money math beyond the display half of hard rule 2, no key)
# gates: pytest tests/test_us_int_039_codecs.py · tests/test_cr053_task14_print_formats.py unchanged and green · ruff · black · RED PROVED FIRST: with `require()` returning None instead of raising, TC-2's refusal case fails — quoted in the lane report
# exceptions: seven vendor codecs and `pdf` are NAME-ONLY registrations, each naming the wave that brings its code — recorded in the docstring, not implied · the fixtures for json · xml · csv · mime are OUR recorded output, because we are the emitter; the vendor folders hold a PROVENANCE line and no sample anybody typed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
