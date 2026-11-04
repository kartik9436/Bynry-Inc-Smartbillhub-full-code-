# ── Trace ──────────────────────────────────────────────
# Change:   P4.2 (Finance blueprint p017) — "the export batch WRITES A FILE:
#           CSV · IIF · QBO · Xero from the STORED PAYLOAD, so the file is
#           hash-stable and a later reference edit cannot rewrite a sent
#           batch". P4.7 is the proof of that last clause.
# Rules:    BR-LED-004 (a batch is recorded once, and re-DOWNLOAD is the
#           ratified door) · BR-LED-020 (v1 is FILE/batch export; direct
#           QBO/Xero OAuth is v2 — NOT this phase) · BR-TEN-020 (a recorded
#           batch keeps the refs it had AT SEND) · CLAUDE.md rule 4 (financial
#           immutability — a sent file may not move) · rule 2 (money 4dp
#           stored, 2dp displayed) · BR-INT-054 as amended, CR-069 §20.4 (a
#           CODEC shapes bytes; a PROJECTION decides which of our fields is
#           which — the split this module observes rather than blurs)
# Tests:    06-backend/tests/test_p4_2_export_files.py ·
#           06-backend/tests/test_p4_7_hash_stable_regeneration.py
# Impacts:  apps/ledger/finance_api.py (GET …/batches/{id}/file) ·
#           apps/integrations/codecs.py (the IIF and CSV encoders, reused) ·
#           07-frontend hand-over history (the File column, P4.5)
# ───────────────────────────────────────────────────────
"""Turn a recorded hand-over into bytes an accountant can actually open.

`apps/ledger/exports.py` has carried this sentence since 2026-08-15, under a
heading that says *"WHAT IS NOT BUILT HERE, NAMED SO SILENCE IS NOT READ AS
DONE"*:

    **No file is written and nothing is sent.** … What exists is the RECORDED
    BATCH and its payload — which is what BR-LED-004 makes the durable
    artifact, and what a file is rendered FROM.

This module is that render. It is the whole of `P4.2`, and the phase's own
sentence for why it matters is *"today the handover is RECORDED and nothing is
written or emailed"*.

════════════════════════════════════════════════════════════════════════════
NOTHING IS STORED, AND THAT IS THE DESIGN RATHER THAN A SHORTCUT
════════════════════════════════════════════════════════════════════════════
The obvious build is to write the file at send time and keep it. **It is the
wrong one here, and the reason is the property `P4.7` exists to prove.**

A batch's `payload` is FROZEN at send (`exports.create_export_batch`) and its
`content_hash` is a SHA-256 over that payload's canonical JSON. So a file
rendered from the payload by a deterministic function is byte-identical every
time it is asked for, **by construction** — there is no second copy that could
drift from the first, no storage key that could 404, and no retention window
after which the accountant's file stops existing. `J19` step 7 asks that *"the
export file re-generated from the batch is identical (hash-stable)"*, and the
cheapest way to satisfy that is to have exactly one thing in the world that the
file is derived from.

It also settles `US-LED-006` TC-4 for free: change `4100`'s QBO ref from 79 to
101 the month after July's batch, and July's file still says 79, because the
ref it holds is the one written into the payload at send — `BR-TEN-020`. A
renderer that went back to the chart would silently start saying 101, which is
CLAUDE.md rule 4 broken by a report rather than by an UPDATE.

⚠ **THIS IS THEREFORE A PURE FUNCTION AND MUST STAY ONE.** It takes a payload
and a target and returns bytes. It reads no table, no setting and no clock. If
a later lane needs a tenant's name or the send date in the file, it must come
IN as an argument — a read inside here is a way for two downloads of one batch
to differ.

════════════════════════════════════════════════════════════════════════════
THE FOUR TARGETS, AND WHAT EACH FILE HONESTLY IS
════════════════════════════════════════════════════════════════════════════
`models.EXPORT_TARGETS` is `qbo · xero · csv · iif`, and the blueprint draws
them on 6·2's *Send it to* picker as *QuickBooks Online · Xero journal file ·
QuickBooks Desktop file (IIF) · Plain spreadsheet file (CSV)*.

**csv** — the generic spreadsheet. Our own columns, our own names, no vendor
    shape at all. `A14 §Accounting exports` calls it *"CSV (generic)"*.
**iif** — QuickBooks Desktop's tab-separated journal. The GRAMMAR (the `!TRNS`
    declarations, the tab, `ENDTRNS`) is the vendor's and is already
    implemented in `apps/integrations/codecs._encode_iif`, so it is REUSED
    rather than written a second time. What we supply is the header and the
    rows, which is the projection below.
**qbo** — QuickBooks Online's **journal-entry import sheet**, which is a CSV
    with QuickBooks' own column names.
**xero** — Xero's **manual-journal import sheet**, likewise a CSV with Xero's
    own column names.

⚠ **NEITHER `qbo` NOR `xero` HAS EVER BEEN ROUND-TRIPPED AGAINST THE REAL
PRODUCT, AND SAYING SO IS THE POINT.** Each column layout below is written from
the vendor's published import template and each is a PLAUSIBLE file; none is a
file this repo has watched QuickBooks or Xero accept. A utility going live on
one of them will find out first, and the honest place to record that is here
rather than in a release note nobody reads. **It does not block the download**,
because a plausible file an accountant can inspect and adjust is strictly better
than the disabled button it replaces, and the CSV and IIF targets are not
affected at all.

⚠⚠ **`OQ-LED-12635` IS CLOSED AND THE RISK ABOVE IS NOT — IT IS ACCEPTED.
CLOSED 2026-09-25, AND NOT BY BEING ANSWERED.** The question asked for one real
attempt: somebody with a QuickBooks Online or Xero login importing one of our
files and telling us what happened. **The PO was asked whether they could supply
a sandbox account or one real exported file and answered, verbatim, *"no"*.** So
the input will not arrive, the question is closed, and **every sentence above
stays true** — a closed question here means nobody is waiting for an answer, not
that the layouts have been verified.

**The consequence, plainly, because this is the sentence that gets lost:** *we
generate the hand-over file and it has never been imported into QuickBooks or
Xero. The first person to find out whether it works will be a customer at month
end.* The worked case put to the PO: July's hand-over is **$15,066.00 across ten
accounts**; if Xero reads our *Amount* column as all-positive the ten lines do
not cancel and Xero refuses the file, which is noisy and safe — and if it reads
our account code column as a NAME it may create ten new accounts called *79*,
*80*, *84*, post the money into them, and report a balanced month, which looks
right on every screen either side. **They were shown that and accepted it.**

⚠ **IT RE-OPENS ON CONTACT WITH A REAL FILE.** The PO ruled only that they
cannot supply one; they did NOT rule that these two layouts are correct. The
moment anyone — a customer, a partner, a bookkeeper — gets hold of a real
QuickBooks Online or Xero login or a real exported file, one attempt still
settles it, and this comment is what tells them the attempt has never been
made. Recorded in `12-governance/02-decision-log.md` (2026-09-25, RULING 4).

⚠ **`codecs.qbo` IS A DIFFERENT THING FROM `EXPORT_QBO` AND THE TWO SHARE A
NAME ON A MONEY PATH.** `apps/integrations/codecs.py` registers `qbo` as *"the
bank-statement file QuickBooks reads"* — an OFX document coming IN from a bank.
`models.EXPORT_QBO` is an accounting hand-over going OUT. They are unrelated,
they are three letters apart in two registries, and a lane reaching for
`codecs.require("qbo")` here would have shipped an OFX bank statement to an
accountant. Filed as `DEF-LED-6608`; this module does not use the codec
registry for `qbo` or `xero` and says why in `_ENCODERS`.

⚠ **DIRECT OAUTH SYNC IS EXPLICITLY v2 AND IS NOT HERE** (`BR-LED-020`, and
`P4.2`'s own row says *"not this phase"* in bold). Nothing in this module
speaks to QuickBooks or Xero. It writes a file; a person carries it.

════════════════════════════════════════════════════════════════════════════
THE COST-OF-SERVICE SECTION IS IN THE CSV AND NOT IN THE OTHER THREE
════════════════════════════════════════════════════════════════════════════
A stored payload holds TWO kinds of row: the journal summary
(`exports._payload`) and `BR-LED-039`'s cost-of-service extract
(`exports._cost_payload`), the second marked `section: "cost_of_service"` and
carrying a single `amount` where a journal row carries `debit` and `credit`.

`US-LED-021` TC-7 is explicit that the cost total is **NOT** added to
`total_debits` / `total_credits` — *"an unlabelled mixed total is a figure no
reader can reconcile, and that is the failure this separation exists to
catch"*. An accounting import file is, by construction, a set of lines that
must foot; putting an unbalanced register extract into one would make every
QuickBooks and Xero import fail, and — worse — a file that happened to import
would double-book the payables the tenant's own AP already holds
(`cost_capture` records the PO's ruling on exactly that).

So: **CSV carries the whole payload with its `section` column and its own
`amount` column. IIF, QBO and Xero carry the journal rows only.** That is not
silent — `omitted_cost_rows()` reports the count, `GET …/batches/{id}/file`
puts it in a response header, and the hand-over history says so beside the
download. A reader who needs the payable side takes the CSV, which is the one
target that was never a vendor import sheet in the first place.
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal
from typing import Any, Mapping, Sequence

from apps.integrations import codecs

from . import models

ZERO = Decimal("0")

#: What `content_disposition` offers the browser, per target.
EXTENSIONS: dict[str, str] = {
    models.EXPORT_CSV: "csv",
    models.EXPORT_IIF: "iif",
    models.EXPORT_QBO: "csv",
    models.EXPORT_XERO: "csv",
}

MEDIA_TYPES: dict[str, str] = {
    models.EXPORT_CSV: "text/csv; charset=utf-8",
    models.EXPORT_IIF: "text/plain; charset=utf-8",
    models.EXPORT_QBO: "text/csv; charset=utf-8",
    models.EXPORT_XERO: "text/csv; charset=utf-8",
}


class ExportFileError(RuntimeError):
    """A file this module will not render, with the reason a human can act on."""


# ═══════════════════════════════════════════════════════════════════════════
# MONEY ON THE PAGE — 2 decimals, no symbol, no separator
# ═══════════════════════════════════════════════════════════════════════════
def _money(value: Any) -> str:
    """CLAUDE.md rule 2's DISPLAY half, and a payload value is a JSON string.

    A blank rather than `0.00` for an absent figure, and `0.00` for a real
    zero — the two are different statements and an importer reads them
    differently. The payload writes Decimals as strings, so this parses rather
    than assuming, and a value it cannot parse is passed through UNCHANGED
    rather than silently becoming zero: a visible oddity in one cell beats a
    plausible number nobody questions.
    """
    if value is None or value == "":
        return ""
    try:
        return str(Decimal(str(value)).quantize(Decimal("0.01")))
    except (ArithmeticError, TypeError, ValueError):
        return str(value)


def _positive(value: Any) -> str:
    """A debit or credit cell: the figure when it is non-zero, else blank.

    Every accounting importer in this list reads an empty debit cell as *this
    line is a credit*. Writing `0.00` into both columns of one line makes a
    balanced entry that moves nothing, which imports cleanly and is wrong.
    """
    rendered = _money(value)
    if not rendered:
        return ""
    return "" if Decimal(rendered) == ZERO else rendered


# ═══════════════════════════════════════════════════════════════════════════
# THE PROJECTIONS — which of OUR fields is which of THEIRS
# ═══════════════════════════════════════════════════════════════════════════
# ⚠ A projection is a BUSINESS decision and a codec is not (BR-INT-054 as
#   amended, CR-069 §20.4 — `codecs.py` states the split in as many words and
#   declines to hold Xero's layout for exactly this reason). These four live
#   in the LEDGER because the ledger owns the figures being projected: which
#   of our columns is an account code, and whether a hand-over row is a debit
#   or a credit, are questions only this module can answer.
#
# Each returns (header, rows) of plain strings. Nothing below reads a table.


#: ⚠ **A PAYLOAD HOLDS TWO KINDS OF ROW AND THEY ARE NOT INTERCHANGEABLE.**
#: `create_export_batch` stores `_payload(journal rows) + _cost_payload(cost
#: rows)`, and `BR-LED-039` / `US-LED-021` TC-7 are emphatic that the cost
#: total is carried SEPARATELY and is **NOT** added to `total_debits` /
#: `total_credits`: *"an unlabelled mixed total is a figure no reader can
#: reconcile, and that is the failure this separation exists to catch."*
#:
#: The two shapes differ in the database too — a journal row has `debit` and
#: `credit`, a cost row has a single `amount` and a `section` marker — so a
#: renderer that read `row["debit"]` over the whole payload would emit every
#: cost row with two empty money cells. **That is a silent loss**, which is why
#: this split is a named function rather than a filter inline.
def _split(payload: Sequence[Mapping[str, Any]]):
    """(journal rows, cost-of-service rows), by the marker the writer stamps."""
    journal, cost = [], []
    for row in payload:
        (cost if row.get("section") == models_cost_marker() else journal).append(row)
    return journal, cost


def models_cost_marker() -> str:
    """`exports.COST_SECTION_MARKER`, imported lazily.

    `apps.ledger.exports` imports `chart`, `close`, `cost_capture` and
    `reporting` at module scope, so importing it from here at module scope
    would drag a quarter of the ledger into a file whose whole contract is
    *reads nothing*. One string, fetched once per call, named in ONE place so
    the writer and this reader cannot drift apart.
    """
    from . import exports as ledger_exports

    return ledger_exports.COST_SECTION_MARKER


_CSV_HEADER = (
    "section",
    "gl_account",
    "name",
    "account_type",
    "target_ref",
    "debit",
    "credit",
    "amount",
    "window_start",
    "window_end",
    "source",
)


def _csv_projection(
    payload: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    """Our own columns, our own names. `A14`'s *"CSV (generic)"*.

    **THIS IS THE ONLY TARGET THAT CARRIES THE WHOLE PAYLOAD**, journal rows
    and cost-of-service rows alike, each in its own `section` and with the cost
    figure in its OWN `amount` column rather than mixed into debit/credit.

    ⚠ **`source` IS CARRIED AND IT IS NOT DECORATION.** `BR-LED-039` puts the
    cost section into the same payload with its own `source` label,
    deliberately, *"so a reader of the payload — an accountant, an auditor, a
    re-generated file — can tell a register extract from a journal summary
    without going back to the code"*. A file that dropped the label would put a
    payable beside a receivable with nothing to tell them apart, and
    `US-LED-021` TC-7 is explicit that the two totals must never be added.
    """
    marker = models_cost_marker()
    rows = [
        {
            "section": str(row.get("section") or "journal"),
            "gl_account": str(row.get("code") or ""),
            "name": str(row.get("name") or ""),
            "account_type": str(row.get("type") or ""),
            "target_ref": str(row.get("target_ref") or ""),
            "debit": _positive(row.get("debit")),
            "credit": _positive(row.get("credit")),
            "amount": _money(row.get("amount")) if row.get("section") == marker else "",
            "window_start": str(row.get("window_start") or ""),
            "window_end": str(row.get("window_end") or ""),
            "source": str(row.get("source") or "journal"),
        }
        for row in payload
    ]
    return _CSV_HEADER, rows


#: QuickBooks Desktop's journal columns, in its own vocabulary. The GRAMMAR
#: around them is `codecs._encode_iif`'s and is not rewritten here.
_IIF_HEADER = ("DATE", "ACCNT", "AMOUNT", "MEMO")


def _iif_projection(
    payload: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    """One IIF line per GL row, SIGNED — IIF has no debit/credit pair.

    QuickBooks Desktop reads a single `AMOUNT` and takes its SIGN as the side:
    positive is a debit, negative is a credit. So the two columns collapse into
    one signed figure here, which is a projection decision and is why it lives
    in this module rather than in the codec.

    **IIF addresses an account by its NAME, never by a ref** — `US-LED-006`
    TC-5's second sentence is that *"CSV and IIF address accounts by code+name
    and remain available"* when a QBO ref is missing, and this is that sentence
    implemented: the ACCNT cell is `code · name` and no `target_ref` appears in
    an IIF file at all.

    ⚠ **A TAB OR A NEWLINE IN A NAME IS REFUSED BY THE CODEC, NOT ESCAPED**, and
    that refusal is correct — IIF has no quoting, so a tab would shift every
    later column one place left and post an amount into a date field with
    nothing going red. The refusal surfaces here as an `ExportFileError`.
    """
    payload, _cost = _split(payload)  # see `_split`: the three accounting
    rows = []  # targets carry the JOURNAL rows only
    for row in payload:
        debit = Decimal(_money(row.get("debit")) or "0")
        credit = Decimal(_money(row.get("credit")) or "0")
        amount = debit - credit
        code = str(row.get("code") or "")
        name = str(row.get("name") or "")
        rows.append(
            {
                "DATE": str(row.get("window_end") or row.get("window_start") or ""),
                "ACCNT": f"{code} · {name}".strip(" ·"),
                "AMOUNT": str(amount.quantize(Decimal("0.01"))),
                "MEMO": str(row.get("source") or "journal"),
            }
        )
    return _IIF_HEADER, rows


#: QuickBooks Online's journal-entry import sheet. See the module docstring:
#: written from the published template, never round-tripped (`OQ-LED-12635`).
_QBO_HEADER = ("*JournalNo", "*JournalDate", "*AccountName", "Debits", "Credits", "Description")


def _qbo_projection(
    payload: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    """QuickBooks Online addresses an account by the REF the tenant typed.

    `exports.REF_FIELD_BY_TARGET` maps this target to `qbo_ref`, and
    `create_export_batch`'s gate 4 has ALREADY refused the whole hand-over if
    any row lacked one — atomically, by name. So a `target_ref` is present on
    every row of a `qbo` payload by the time this function sees it, and a blank
    here would mean the gate was bypassed rather than that the ref is optional.
    The name is appended after the ref so a human reading the file can tell
    which account `79` is; QuickBooks matches on the leading ref.
    """
    payload, _cost = _split(payload)  # see `_split`: the three accounting
    rows = []  # targets carry the JOURNAL rows only
    for row in payload:
        ref = str(row.get("target_ref") or "")
        name = str(row.get("name") or "")
        rows.append(
            {
                "*JournalNo": "",  # filled per batch by `render`, which knows the number
                "*JournalDate": str(row.get("window_end") or row.get("window_start") or ""),
                "*AccountName": f"{ref} {name}".strip(),
                "Debits": _positive(row.get("debit")),
                "Credits": _positive(row.get("credit")),
                "Description": str(row.get("source") or "journal"),
            }
        )
    return _QBO_HEADER, rows


#: Xero's manual-journal import sheet — `*Narration · *Date · Description ·
#: *AccountCode · *TaxRate · *Amount`. Also never round-tripped.
_XERO_HEADER = ("*Narration", "*Date", "Description", "*AccountCode", "*TaxRate", "*Amount")


def _xero_projection(
    payload: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    """Xero takes ONE SIGNED `*Amount`, like IIF, and its own account code.

    ⚠ **`*TaxRate` IS WRITTEN AS `No Tax` ON EVERY LINE, DELIBERATELY.** Our
    hand-over already carries tax as its OWN GL rows — the `2200-nn` payable
    accounts `BR-BIL-069` makes the authority's identity in the books — so
    asking Xero to compute tax on top of these lines would book it twice. A
    blank cell would let Xero apply the account's default rate, which is the
    same double-booking arrived at by omission. `No Tax` is the only value that
    states what is true: the tax is already in the file, on its own line.
    """
    payload, _cost = _split(payload)  # see `_split`: the three accounting
    rows = []  # targets carry the JOURNAL rows only
    for row in payload:
        debit = Decimal(_money(row.get("debit")) or "0")
        credit = Decimal(_money(row.get("credit")) or "0")
        rows.append(
            {
                "*Narration": "",  # filled per batch by `render`
                "*Date": str(row.get("window_end") or row.get("window_start") or ""),
                "Description": str(row.get("name") or ""),
                "*AccountCode": str(row.get("target_ref") or ""),
                "*TaxRate": "No Tax",
                "*Amount": str((debit - credit).quantize(Decimal("0.01"))),
            }
        )
    return _XERO_HEADER, rows


# ⚠ **THE CODEC REGISTRY IS USED FOR `iif` AND FOR NOTHING ELSE, ON PURPOSE.**
#   `codecs.csv` would produce the same bytes as the local writer below and is
#   a perfectly good encoder; it is not used here because `qbo` and `xero` MUST
#   NOT go through the registry — `codecs.qbo` is an OFX BANK STATEMENT and
#   `codecs.xero` is registered name-only with no encoder at all — and three
#   targets taking one path while a fourth takes another is how the wrong one
#   gets reached for. One local writer, one vendor grammar borrowed where a
#   vendor grammar exists.
_PROJECTIONS = {
    models.EXPORT_CSV: _csv_projection,
    models.EXPORT_IIF: _iif_projection,
    models.EXPORT_QBO: _qbo_projection,
    models.EXPORT_XERO: _xero_projection,
}


def _write_csv(header: Sequence[str], rows: Sequence[Mapping[str, str]]) -> bytes:
    """UTF-8, comma, exactly ONE header row, `\\n` endings.

    `lineterminator="\\n"` is load-bearing for hash stability: `csv.writer`
    defaults to `\\r\\n`, which is fine, but a default is a thing that can
    change under you and this function's whole contract is that its output
    never moves. Pinned rather than inherited.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(list(header))
    for row in rows:
        writer.writerow([row.get(name, "") for name in header])
    return buffer.getvalue().encode("utf-8")


def render(batch: Mapping[str, Any]) -> bytes:
    """The bytes of ONE recorded hand-over. Deterministic, and reads nothing.

    `batch` is a `batch_dict()` — or any mapping carrying `target`, `payload`
    and `batch_no`. The target decides the shape; the payload decides every
    figure in it; the batch number rides in the vendor columns that want a
    journal reference, and is `""` rather than invented when the `EXP-` series
    is not seeded (`BR-TEN-035` — a composed number is how two batches end up
    as EXP-7).
    """
    target = str(batch.get("target") or "")
    projection = _PROJECTIONS.get(target)
    if projection is None:
        raise ExportFileError(
            f"{target!r} is not one of the four hand-over targets. "
            f"BR-LED-020 names {', '.join(models.EXPORT_TARGETS)}, and direct QBO/Xero "
            "sync is v2 — this phase writes files."
        )
    payload = list(batch.get("payload") or ())
    header, rows = projection(payload)

    reference = str(batch.get("batch_no") or "")
    for row in rows:
        if "*JournalNo" in row:
            row["*JournalNo"] = reference
        if "*Narration" in row:
            row["*Narration"] = reference

    if target == models.EXPORT_IIF:
        try:
            return codecs.CODECS.require("iif").encode(rows, header)
        except ValueError as refusal:
            # The codec refuses a tab or a newline inside a value rather than
            # escaping it, because IIF has no quoting. Re-raised in this
            # module's own exception so the API layer has one type to catch.
            raise ExportFileError(
                f"this hand-over cannot be written as IIF: {refusal}"
            ) from refusal
    return _write_csv(header, rows)


def omitted_cost_rows(batch: Mapping[str, Any]) -> int:
    """How many payload rows this target's file LEAVES OUT. Zero for CSV.

    ⚠ **THIS FUNCTION IS THE WHOLE REASON THE OMISSION IS NOT A DEFECT.** An
    accounting import file must foot, so the three vendor targets carry the
    journal rows only (see the module docstring); a file that quietly held
    fewer rows than the batch it claims to be would be `DEF-2345`'s shape — a
    true statement about part of the data, presented as a statement about all
    of it. The count travels with the file, on the response and on the screen,
    so *"seven rows"* and *"seven of nine rows"* can never read the same.
    """
    if str(batch.get("target") or "") == models.EXPORT_CSV:
        return 0
    _journal, cost = _split(list(batch.get("payload") or ()))
    return len(cost)


def filename(batch: Mapping[str, Any]) -> str:
    """`{batch_no or id}_{target}_{start}_{end}.{ext}` — context in the NAME.

    The same discipline `IS-11` applies to every other file this product
    writes: no metadata rows inside the data, because a metadata row is a row
    an importer tries to import. A bookkeeper holding July's QuickBooks file
    beside July's Xero file can tell them apart without opening either.
    """
    target = str(batch.get("target") or "")
    period = batch.get("period") or ["", ""]
    stem = str(batch.get("batch_no") or batch.get("batch_id") or "batch")
    return f"{stem}_{target}_{period[0]}_{period[1]}.{EXTENSIONS.get(target, 'csv')}"


def media_type(batch: Mapping[str, Any]) -> str:
    return MEDIA_TYPES.get(str(batch.get("target") or ""), "text/csv; charset=utf-8")


# ── Lifecycle ─────────────────────────────────────────────
# packet: P4.2 (05-prototype/07 Finance Blueprint.pdf p017 · p069 "Download and Send stay apart" · p070 row 8 "File … is a stated absence until P4.2" · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-004/014/017/020 · 08-qa/01-e2e/journeys/J19-month-end-close.md step 7 · apps/integrations/codecs.py, whose IIF grammar this reuses)
# screens: 6·2 Export · 6·2a Hand over
# generated: 2026-09-24 by lane FIN-P4
# checklist: A✔ B✔ C✔ D✔ E=deferred(the History table's File column is P4.5, in this lane) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: (1) the `qbo` and `xero` COLUMN LAYOUTS have never been round-tripped against the real product — written from each vendor's published import template, stated in the module docstring rather than implied — `OQ-LED-12635` is CLOSED 2026-09-25 as an ACCEPTED RISK rather than answered (the PO was asked for a sandbox account or one real exported file and said *"no"*), so the layouts remain unverified and the first person to find out whether they work will be a customer at month end; CSV and IIF are unaffected · (2) `codecs.qbo` is an OFX BANK STATEMENT and shares its name with `EXPORT_QBO`, an accounting hand-over — filed as `DEF-LED-6608`, and this module deliberately does not reach into the codec registry for `qbo` or `xero` · (3) NOTHING IS STORED: the file is re-derived from the frozen payload on every request, which is what makes `J19` step 7's hash-stability true by construction rather than by a copy nobody re-checks · (4) no OAuth, no send — `BR-LED-020` puts direct sync in v2 and `P4.2` says "not this phase"
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
