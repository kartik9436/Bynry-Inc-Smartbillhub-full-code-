# ── Trace ──────────────────────────────────────────────
# Change:   CR-054 W4 tasks 14 and 16 — partial posting on a read batch, and
#           the file the held rows come back as.
# Rules:    BR-MET-940 (PARTIAL POSTING — "all or nothing will not work; we
#           accept what is correct and rejct what i not correct", PO, carried
#           into CR-054; supersedes BR-MET-015's ERROR half AT THE POST GATE
#           and nowhere else) · BR-MET-941 (the rejects export: the operator's
#           own columns plus a reason and a fix) · BR-MET-129 (a warned
#           reading posts, so a warning is never a reject) · BR-MET-018 +
#           CLAUDE.md hard rule 6 (a posted batch never posts twice) ·
#           BR-MET-017 (a posted batch is immutable) · CR-016 (no internal
#           reference on a surface a customer reads).
# Tests:    06-backend/tests/test_cr054_w24_backend.py
# Impacts:  apps/metering/services.py (commit_read_batch writes the held
#           record this file reads) · apps/metering/api.py (the route)
# ───────────────────────────────────────────────────────
"""**Why a staged reading did not post, in the clerk's own words — and the
file that hands those rows back.**

⛔ **THE RULING THIS SERVES, VERBATIM.** The Product Owner, carried into
CR-054 from the session that raised it: *"COMMITTING All or nothing... - all
or nothing will not work - we accept what is correct and rejct what i not
correct - then create csv file at loading stage itself so that suer can see
all cases thata re rejcted"*. Both halves are here — `services.commit_read_batch`
posts what is correct and records what is not, and this module is the file.

⚠ **IT IS CR-047's DESIGN, APPLIED, NOT A SECOND ONE.** `import_runs`
already answers the identical question for the account/premises/unit/asset
importer (*"at the end we need 2 CsV file 1 for success record and other for
failed records"*, PO 2026-08-29), and CR-054's own task list says tasks 13–16
*"apply that existing ruling to reads; they do not make a new decision"*. So
the two appended column NAMES, the streaming, the chunk size, the CSV quoting
and the database-refusal sentences are all IMPORTED from that module rather
than re-typed. Three of those imports are private names and each is
deliberate — see `_line`, `_db_sentences` below, which say why re-typing them
would re-create a defect that module already paid for.

⚠ **WHERE READS DIFFERS FROM ACCOUNTS, AND IT IS ONE THING (`DEF-2672`).**
CR-047's failures file is *"the operator's original row, byte for byte, in the
file's own column order"*, because `ImportRunRow.raw` keeps the row as
extracted and `mapping_spec.source_headers` keeps the order. **The reads
importer keeps neither** — `read_import.parse_csv` builds exactly that dict
per row and discards it once the nine mapped targets are read off. So this
file comes back under the PUBLISHED template headers, carrying every value the
clerk typed for every column reads actually uses, and not the columns it does
not. It re-uploads cleanly, because those headers are the first alias of every
`TEMPLATE_COLUMNS` target and are the file the parser reads best; what is lost
is the operator's own header spellings and any extra column they carried.
Filed as `DEF-2672` with the fix costed, rather than left as a surprise.

**THREE THINGS THIS FILE DELIBERATELY DOES NOT DO.**

1. **It never re-judges a row.** Every sentence comes from what the batch
   RECORDED — the validation outcomes stage 3 stored, and the `post` record
   `commit_read_batch` writes as it holds a row. `receipt()`'s posture in
   `import_runs`, for its reason: *"a receipt that said 245 loaded in August
   must still say it in December"*.
2. **It shows no rule id, no message key and no constraint name.** CR-016
   rules out an internal reference on a surface a customer reads, and the
   operator reading this file has never seen `BR-MET-016` or
   `uq_read_import_rows`. The driver's own message is logged by
   `import_runs` and never rendered.
3. **It writes nothing.** Downloading the result of a batch is not an event —
   `import_results_csv` takes the same posture and states it.
"""

from __future__ import annotations

from typing import Any

from apps.metering import models, read_import
from apps.metering import write_modes
from core import errors

# ── What is reused from the account importer, and why each one ──────────────
#
# ⚠ **THE TWO APPENDED COLUMN NAMES ARE IMPORTED, NOT RE-TYPED.** An operator
# who has run the account migration has already learned `why_it_failed` and
# `how_to_fix_it`; a reads file that spelled them differently would teach two
# vocabularies for one idea, and a lane renaming one would leave the other.
#
# ⚠ **`_csv_line` IS A PRIVATE NAME AND IMPORTING IT IS THE LESSER EVIL,
# STATED RATHER THAN HIDDEN** (the `import_receipt` → `import_runs._run`
# precedent, reported the same way). It exists because *"a customer name is
# `\"Harmon, Luis\"` on the very first row of the CR-030 fixture, and a
# hand-joined line would split that account across two columns in the file the
# operator re-uploads"* — and a meter note is exactly as likely to carry a
# comma. A second `csv.writer` wrapper here would be a second place for that
# rule to be got wrong. A public `csv_line` belongs in `import_runs.py`, which
# this lane is not editing while other lanes hold that file.
#
# ⚠ **`_db_state` LIKEWISE, AND MORE STRONGLY.** It walks the `__cause__` /
# `__context__` chain because Django's wrapper is entered more than once, so
# *"the caught `IntegrityError`'s `__cause__` is ANOTHER Django
# `IntegrityError`, and the driver's exception is two or three hops further
# down"* — a one-hop read *"silently produced the generic sentence for every
# row, which is exactly the kind of failure that looks handled"*. Re-typing
# that walk here would re-create `DEF-2519`'s first draft, on the same day the
# module it lives in warns against it.
from apps.metering.import_runs import (  # noqa: F401 — see the note above
    FAILURE_FIX_COLUMN,
    FAILURE_REASON_COLUMN,
    RESULT_CSV_CHUNK,
    _csv_line as _line,
    _db_state,
    _DB_REFUSAL_SENTENCES,
    _DB_REFUSAL_UNKNOWN,
)

# ── The record `commit_read_batch` writes on a row it could not post ────────
#
# ⚠ **IT IS A PSEUDO-RULE IN `rule_outcomes`, AND THE PRECEDENT IS `parse`.**
# `stage_read_batch` has always written `{"rule": "parse", …}` into that list,
# and `parse` is not in `validation.ALL_RULES` either. A post result is NOT a
# validation rule and must not join that catalog: `ALL_RULES` is written out by
# hand precisely so that adding a rule is a deliberate act with respect to
# BR-MET-136, which splits every rule into locked-integrity or
# switchable-judgment — and *"did this row post"* is neither. Putting it here
# instead costs no column, survives on the row for the export to read, and
# renders in the same list a clerk already reads a row's flags from.
POST_OUTCOME = "post"

#: A row a HUMAN kept out — rejected, skipped, sent to the field, or marked for
#: an estimate. Unchanged from before partial posting; `commit_read_batch` has
#: reported it since `DEF-659`.
REASON_DISPOSITIONED_OUT = "not_dispositioned_for_posting"
#: The row has no meter, no date or no reading, so there is nothing to post.
#: Unchanged from before partial posting.
REASON_INCOMPLETE_ROW = "incomplete_row"
#: BR-MET-127 — the reading it would replace is on an issued bill.
REASON_BILLED_READ = write_modes.SKIP_REASON_BILLED
#: ⛔ **THE ONE NEW REASON, AND IT IS THE WHOLE OF TASK 14.** Before
#: BR-MET-940 a row in this state did not get a reason: it REFUSED THE WHOLE
#: BATCH (`errors_need_resolution`), so 1,178 good readings waited on it.
REASON_UNRESOLVED_ERROR = "unresolved_error"
#: A refusal raised by the write itself — a business rule that could only be
#: judged against the head as it is NOW (BR-MET-016's duplicate, a superseded
#: head, a lifecycle that moved between the rehearsal and the commit).
REASON_WRITE_REFUSED = "write_refused"
#: PostgreSQL itself turned the row down: a unique index, a NOT NULL column, a
#: foreign key whose target vanished mid-post.
REASON_DATABASE_REFUSED = "database_refused"

#: The two sentences a held row carries, keyed by the reason above. Templated
#: over `{meter}` and `{read_date}` — the operator's own cells, never a uuid
#: and never a row id, because the person reading this file is looking at their
#: spreadsheet and not at our database (`import_runs`' `DEF-322` note).
_HELD_SENTENCES: dict[str, tuple[str, str]] = {
    REASON_DISPOSITIONED_OUT: (
        "Somebody decided this reading for {meter} should not be filed.",
        "It was rejected, skipped, or sent out for a field visit at the review "
        "step. If that was wrong, upload the reading again on its own; the "
        "batch it came in on is closed.",
    ),
    REASON_INCOMPLETE_ROW: (
        "This row is missing the meter, the date or the reading itself.",
        "A reading needs all three. Fill in the empty cell and upload the file " "again.",
    ),
    REASON_BILLED_READ: (
        "The reading this row would replace for {meter} on {read_date} is " "already on a bill.",
        "A reading a customer has been billed for is never overwritten. Correct "
        "it from the reading's own page, which issues a corrected bill; that is "
        "the only door, and it is deliberately not this one.",
    ),
    REASON_WRITE_REFUSED: (
        "This reading for {meter} on {read_date} was turned down as it was "
        "being filed, and the rest of the file carried on.",
        "Something about this meter changed between the check and the save — "
        "usually another reading landing on the same meter and date. Check the "
        "meter's readings, then upload this row again.",
    ),
}

_HELD_UNKNOWN: tuple[str, str] = (
    "This reading for {meter} was not filed, and the rest of the file was.",
    "Every other row went in normally. Send this row to support with the batch "
    "number on the receipt — they can see exactly what stopped it.",
)

#: The ERROR each rule states, as the clerk would say it. Only the rules that
#: can actually hold a row out are named; everything else takes the honest
#: generic below rather than a guess (`_DB_REFUSAL_SENTENCES`' own posture).
#:
#: ⚠ **THESE ARE THE `not evaluated` OF COPY: A RULE WITH NO SENTENCE HERE
#: STILL GETS A ROW.** A held row with a blank reason is worse than no file —
#: it is `DEF-320`'s *"a path that looks handled and communicates nothing"* —
#: so the fallback names the count and tells the operator where to look.
_ERROR_SENTENCES: dict[str, tuple[str, str]] = {
    "parse": (
        "A cell on this row could not be read at all.",
        "Compare this row against one that went in — the difference is usually "
        "a date written a different way, or a reading with a letter in it. "
        "Correct the cell and upload the file again.",
    ),
    "unknown_meter": (
        "There is no meter called {meter} on this utility.",
        "Check the meter number against the one on the meter itself. If the "
        "meter is genuinely new, add it first — a reading cannot be filed "
        "against a meter that does not exist.",
    ),
    "retired_meter": (
        "Meter {meter} was taken out of service before {read_date}.",
        "Either the number is wrong, or this reading belongs to the meter that "
        "replaced it. Check which meter was on the property that day.",
    ),
    "unit_missing": (
        "Meter {meter} is not on a property, so this reading has nowhere to go.",
        "Put the meter on its unit first — Assets, the meter, then Assign — and "
        "upload the file again.",
    ),
    "duplicate": (
        "There is already a reading on file for {meter} on {read_date}.",
        "If the one on file is wrong, correct it from the reading's own page. "
        "If this row is a second copy of a row already in this file, delete it.",
    ),
    "negative_usage": (
        "The reading for {meter} is lower than the one before it, and the "
        "difference is not a rollover.",
        "Check the number against the meter face. If the meter really was "
        "replaced or wound back, record that first; a reading that goes "
        "backwards would bill a negative amount.",
    ),
    "rollover": (
        "The reading for {meter} looks like the register has turned over, and "
        "that could not be confirmed.",
        "Check the number of digits on the meter face against what is on file "
        "for it, then upload this row again.",
    ),
    "export_not_net": (
        "This row records power sent back to the grid on {meter}, which is not "
        "set up to export.",
        "Either the meter should be marked as a net meter, or this figure "
        "belongs on a different register. Check which before uploading again.",
    ),
    "generation_channel": (
        "This row puts a generation figure on a register that measures what the " "customer used.",
        "A solar or battery figure belongs on its own register. Correct the "
        "register column and upload the file again.",
    ),
}

_ERROR_UNKNOWN: tuple[str, str] = (
    "This reading for {meter} did not pass one of the checks and nobody decided "
    "what to do about it.",
    "Open the batch, look at the flag on this row, and either correct the cell "
    "or accept it with a reason. Then upload it again.",
)


def _facts(row: Any) -> dict[str, str]:
    """The two cells that name this row on the OPERATOR's spreadsheet.

    Their own strings, never ours: `meter_no_raw` is stored *"as typed/uploaded,
    never coerced"*, and the date falls back to `read_at_raw` precisely for the
    row whose date would not parse — which is one of the rows most likely to be
    in this file.
    """
    meter = (row.meter_no_raw or "").strip() or "this meter"
    if row.read_at is not None:
        read_date = row.read_at.date().isoformat()
    else:
        read_date = (row.read_at_raw or "").strip() or "that day"
    return {"meter": meter, "read_date": read_date}


def _render(templates: tuple[str, str], facts: dict[str, str]) -> tuple[str, str]:
    problem, fix_hint = templates
    try:
        return problem.format(**facts), fix_hint.format(**facts)
    except (KeyError, IndexError, ValueError):  # pragma: no cover — defensive
        unknown_problem, unknown_fix = _HELD_UNKNOWN
        return unknown_problem.format(**facts), unknown_fix.format(**facts)


def worst_error_rule(row: Any) -> str | None:
    """The name of the first ERROR outcome on the row, or None.

    FIRST rather than "worst", and the two are the same thing here: the engine
    appends in catalog order and every entry in this list is already the same
    severity. A row held by three errors is described by one sentence, because
    the operator fixes one cell and re-uploads — a wall of three is `CR-054`'s
    own complaint about the copy, one file over.
    """
    for outcome in row.rule_outcomes or []:
        if outcome.get("severity") == "error":
            return str(outcome.get("rule") or "")
    return None


def sentences_for(row: Any, reason: str, *, exc: Exception | None = None) -> tuple[str, str]:
    """`(why_it_failed, how_to_fix_it)` for ONE held row. The single translator.

    It is called from TWO places on purpose and that is the whole point of it
    being a function: `commit_read_batch` calls it as it holds a row, so the
    reason is recorded at the moment it is true (a write refusal cannot be
    re-derived afterwards); the exporter calls it for a batch that was validated
    and never posted, so the rejects file exists at the *"loading stage
    itself"* the PO asked for. Two callers, one wording.
    """
    facts = _facts(row)
    if reason == REASON_DATABASE_REFUSED:
        # The shared table, so a unique-key refusal reads the same sentence
        # whichever importer met it. Its templates name `{row_label}` and the
        # noun; a reading's label is its meter and its date.
        state = _db_state(exc) if exc is not None else ""
        templates = _DB_REFUSAL_SENTENCES.get(state) or _DB_REFUSAL_UNKNOWN
        shared = {
            "noun": "reading",
            "plural": "readings",
            "row_label": f"the reading for {facts['meter']} on {facts['read_date']}",
        }
        return _render(templates, shared)
    if reason == REASON_UNRESOLVED_ERROR:
        rule = worst_error_rule(row)
        return _render(_ERROR_SENTENCES.get(rule or "", _ERROR_UNKNOWN), facts)
    return _render(_HELD_SENTENCES.get(reason, _HELD_UNKNOWN), facts)


def held_record(
    row: Any, reason: str, *, exc: Exception | None = None, **extra: Any
) -> dict[str, Any]:
    """The `post` outcome `commit_read_batch` appends to a row it held.

    Severity `error` deliberately: a row that did not post is a thing to act on,
    and the row's own severity is NOT recomputed from it — the validation
    verdict is what stage 3 said and must keep saying (BR-MET-090's posture).
    """
    problem, fix_hint = sentences_for(row, reason, exc=exc)
    detail: dict[str, Any] = {
        "reason": reason,
        FAILURE_REASON_COLUMN: problem,
        FAILURE_FIX_COLUMN: fix_hint,
    }
    detail.update({key: value for key, value in extra.items() if value is not None})
    return {"rule": POST_OUTCOME, "severity": "error", "detail": detail}


def posted_record(read_id: Any) -> dict[str, Any]:
    """The mirror of `held_record` for a row that DID post.

    ⚠ **IT IS WRITTEN, AND THE REASON IS THAT ITS ABSENCE IS AMBIGUOUS.**
    Without it, "no `post` outcome" means both *"this row posted"* and *"this
    batch was never posted at all"*, and the rejects file has to tell those two
    apart to know whether it is a worklist or a receipt. `meter_read_id` on the
    row says the same thing for the posted half; this says it in the same place
    as the held half, so one reader answers both.
    """
    return {
        "rule": POST_OUTCOME,
        "severity": "ok",
        "detail": {"reason": "posted", "meter_read_id": str(read_id)},
    }


def post_outcome_of(row: Any) -> dict[str, Any] | None:
    """The `post` record on a row, or None when this batch never posted."""
    for outcome in reversed(row.rule_outcomes or []):
        if outcome.get("rule") == POST_OUTCOME:
            return outcome
    return None


# ═══════════════════════════════════════════════════════════════════════════
# THE FILES — CR-054 task 16, on CR-047's shape
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE `kind` VOCABULARY IS CR-047's OWN**, `successes` and `failures`,
# rather than words invented for reads. The two importers answer the same
# question with the same query parameter, and an operator who has run one has
# already learned the other. What each SET means is stated per importer below,
# because reads partitions its rows differently.

#: `kind=` → what it serves. **The two sets PARTITION every row of a POSTED
#: batch**: a row either has a committed reading behind it or it does not.
#:
#: ⚠ **A WARNED ROW IS A SUCCESS, NOT A REJECT**, and that is BR-MET-129 and
#: not a choice made here: *"we cannot reject the reading, when reading are
#: colelcted then only we will know whether there is usage or not"*. A file of
#: 1,180 rows with 400 vacant-unit warnings posts 1,180 readings; the rejects
#: file is empty, and it is right to be.
RESULT_KINDS: tuple[str, ...] = ("failures", "successes")

#: The rejects file's columns: the PUBLISHED template's own headers, in the
#: template's own order, plus the two CR-047 appends. Re-uploadable by
#: construction — these are the first alias of every `TEMPLATE_COLUMNS` target,
#: which is what `detect_mapping` reads best.
REJECT_COLUMNS: tuple[str, ...] = (
    *read_import.PUBLISHED_HEADERS,
    FAILURE_REASON_COLUMN,
    FAILURE_FIX_COLUMN,
)

#: The successes file's columns. What an operator asks of a reads file after a
#: post: *which meter, which register, on what date, reading what, and how much
#: did that turn out to be?* The last two are the WRITER's own figures, carried
#: from the committed reading and never re-derived — `import_runs`' rule for
#: its own successes file, for the same reason.
SUCCESS_COLUMNS: tuple[str, ...] = (
    "meter",
    "register",
    "read_date",
    "reading",
    "consumption",
    "unit",
)


def _rows(batch: Any) -> Any:
    """Every row of the batch, oldest first, STREAMED.

    `.iterator(chunk_size=…)` for `read_import.CSV_ROW_CAP`'s reason: a batch
    may hold 50,000 rows, and a `list()` of them with every row's outcomes is
    `DEF-766`'s payload again in a download.
    """
    return (
        models.ReadImportRow.objects.filter(tenant_id=batch.tenant_id, batch=batch)
        .only(
            "row_no",
            "row_key",
            "meter_no_raw",
            "read_at",
            "read_at_raw",
            "value",
            "raw_value",
            "channel",
            "service",
            "read_method",
            "note",
            "demand_reset_noted",
            "disposition",
            "severity",
            "rule_outcomes",
            "meter_read_id",
        )
        .order_by("row_no")
        .iterator(chunk_size=RESULT_CSV_CHUNK)
    )


def _reject_cells(row: Any, problem: str, fix_hint: str) -> list[Any]:
    """One held row → the operator's own nine cells, plus the two.

    ⚠ **`raw_value` AND NOT `value`.** `value` is what the row carries after a
    clerk's override; `raw_value` is what the FILE said. A rejects file is the
    file the operator re-uploads, so it must hand back what they typed — handing
    back our correction would return a file that was never corrected, which is
    `import_runs`' own `raw` vs `mapped` argument.

    ⚠ **THE DATE FALLS BACK TO `read_at_raw`**, which is stored exactly for the
    row whose date would not parse — one of the likeliest rows to be here. A
    normalised date on that row would hand back a file that no longer shows the
    mistake it was rejected for.
    """
    reading = row.raw_value if row.raw_value is not None else row.value
    read_date = (
        row.read_at.date().isoformat() if row.read_at is not None else (row.read_at_raw or "")
    )
    return [
        row.row_key or "",
        row.meter_no_raw or "",
        read_date,
        "" if reading is None else reading,
        row.channel or "",
        row.service or "",
        row.read_method or "",
        row.note or "",
        "yes" if row.demand_reset_noted else "",
        problem,
        fix_hint,
    ]


def _failures_csv(batch: Any) -> Any:
    """The rows that did NOT post — a generator, never a list."""
    yield _line(list(REJECT_COLUMNS))
    for row in _rows(batch):
        record = post_outcome_of(row)
        if record is not None:
            if record.get("severity") == "ok":
                continue  # it posted
            detail = record.get("detail") or {}
            problem = str(detail.get(FAILURE_REASON_COLUMN) or "")
            fix_hint = str(detail.get(FAILURE_FIX_COLUMN) or "")
        else:
            # The batch has not posted yet — the *"loading stage itself"* half
            # of the ruling. What is a reject NOW is what would be held if the
            # clerk pressed Post right now, judged from the same facts
            # `commit_read_batch` judges: an unresolved error, a human's
            # disposition, or a row too incomplete to file.
            reason = would_hold(row)
            if reason is None:
                continue
            problem, fix_hint = sentences_for(row, reason)
        yield _line(_reject_cells(row, problem, fix_hint))


def would_hold(row: Any) -> str | None:
    """Why this staged row would NOT post if the batch were posted now, or None.

    ⚠ **IT IS THE SAME THREE QUESTIONS `commit_read_batch` ASKS, IN THE SAME
    ORDER, AND THAT IS NOT A COINCIDENCE — IT IS THE REQUIREMENT.** The PO
    asked for the file *"at loading stage itself"*, and a pre-post rejects file
    that disagrees with what the post actually holds is worse than none: the
    clerk fixes rows that would have gone in and re-uploads rows that would not.
    The two lists cannot be one function, because this one is a REHEARSAL over
    staged rows and the other acts inside the transaction with the batch locked
    and the committed heads re-read — the difference is exactly the two facts
    this cannot know (a head billed since stage 3, a write that refuses), and
    those two produce MORE rejects at post, never fewer. Stated rather than
    quietly true.
    """
    disposition = row.disposition or (
        "accept" if row.severity in ("ok", "warning") else None  # BR-MET-129
    )
    if disposition not in models.POSTING_DISPOSITIONS:
        return (
            REASON_UNRESOLVED_ERROR
            if row.disposition is None and row.severity == "error"
            else REASON_DISPOSITIONED_OUT
        )
    if row.meter_read_id is None and (
        row.meter_no_raw is None or row.read_at is None or row.value is None
    ):
        return REASON_INCOMPLETE_ROW
    return None


def _successes_csv(batch: Any) -> Any:
    """The readings that LANDED, one line each.

    Every figure is the COMMITTED reading's own — the consumption in particular
    is what the engine computed at post and is never re-subtracted here. Two
    derivations of one number is how they come to disagree (`import_runs` says
    so in as many words about an opening balance).
    """
    yield _line(list(SUCCESS_COLUMNS))
    posted_ids = [row.meter_read_id for row in _rows(batch) if row.meter_read_id is not None]
    reads = {
        read.id: read
        for read in models.MeterRead.objects.filter(
            tenant_id=batch.tenant_id, id__in=posted_ids
        ).only("id", "channel", "read_at", "current_value", "consumption", "unit")
    }
    for row in _rows(batch):
        read = reads.get(row.meter_read_id)
        if read is None:
            continue
        yield _line(
            [
                row.meter_no_raw or "",
                read_import.channel_label(read.channel),
                read.read_at.date().isoformat() if read.read_at else "",
                "" if read.current_value is None else read.current_value,
                "" if read.consumption is None else read.consumption,
                read.unit or "",
            ]
        )


def _refuse_not_decided(batch: Any) -> None:
    """A batch whose rows have not been judged has no rejects to hand back.

    ⚠ **A ZERO-ROW CSV WOULD BE THE WORSE ANSWER**, and `import_runs` already
    argues why: a clerk who downloads *Rejected rows* and gets a header with
    nothing under it reads *"nothing was rejected"*. A refusal names the state.

    The bar is `validated` or `posted`, NOT `posted` — which is `DEF-2487`'s
    ruling applied here and is also the PO's own instruction, *"create csv file
    at loading stage itself"*. Stage 3 has written a verdict on every row by
    then; before it, nothing has been judged.
    """
    if batch.status not in ("validated", "posted"):
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-941",
            # ⚠ **THIS REUSED THE ACCOUNT IMPORTER'S KEY UNTIL 2026-09-01, AND
            # A CLERK MET THE WRONG NOUN (`DEF-2733`).** It raised
            # `metering.import.not_checked_no_download` — *"That RUN has not
            # been checked, so there is nothing to download."* — right in every
            # respect except the noun, which for reads is a **BATCH**. The debt
            # was recorded honestly at the time and could not be paid, because
            # copy means editing eleven catalogues and G32 is a ratchet at zero,
            # so a key with no catalogue sentence renders as SILENCE
            # (`DEF-322`/`DEF-320`).
            #
            # ⚠ **AND A REUSED REFUSAL KEY IS INVISIBLE TO EVERY GATE THAT
            # CHECKS REFUSALS**, which is the whole of that defect's escape
            # reason: G32 asks whether a raised key RESOLVES and both of these
            # resolved perfectly — to the wrong sentence; G28 asks whether the
            # refusal names an internal reference and neither did; G33 asks
            # whether it is short and both were. **Nothing anywhere asks whether
            # the NOUN is the right noun for the caller**, and a reused key is
            # exactly where that goes wrong.
            #
            # The sentence is now the reads vocabulary's own, written into all
            # eleven catalogues in the commit that points at it. The account
            # importer's key is untouched, where it is correct.
            message_key="metering.read_batch.not_checked_no_download",
        )


def _refuse_not_posted(batch: Any) -> None:
    """The SUCCESSES half needs a post, for `_refuse_not_decided`'s own reason
    turned round: before the commit nothing has landed, so a file of *"the
    readings that were filed"* would be a header and no rows."""
    if batch.status != "posted":
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-941",
            # `DEF-2733`'s second sentence, and it was the wrong VERB as well as
            # the wrong noun: this raised `metering.import.not_loaded_no_download`
            # — *"That run has not been LOADED"* — and a read batch is **POSTED**,
            # which is the word every other sentence in this module uses
            # (`metering.read_batch.already_posted`,
            # `metering.read_batch.certification_required`). One word for one
            # thing, in all eleven catalogues.
            message_key="metering.read_batch.not_posted_no_download",
        )


def results_csv(batch: Any, kind: Any) -> tuple[str, Any]:
    """`(filename, line generator)` for one half of a read batch's result.

    Refused BY NAME on two things, in this order: a `kind` that is not one of
    the two, then whether the batch has reached the state that half describes.
    Order is `import_runs`' and its reason is the same — *"which file did you
    ask for"* has to be answered before *"may you have it"* can be — and an
    unknown `kind` names what IS allowed rather than defaulting to one of them,
    because a typo that quietly served the successes file would tell a clerk
    that nothing was rejected.
    """
    key = str(kind or "").strip().lower()
    if key not in RESULT_KINDS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            # The third reused key, and this one needs no sentence of its own:
            # *"Pick one of: {{allowed}}."* names the allowed values and says
            # nothing about runs or batches.
            message_key="metering.import.kind_unknown",
            params={"allowed": sorted(RESULT_KINDS)},
        )
    if key == "successes":
        _refuse_not_posted(batch)
    else:
        _refuse_not_decided(batch)
    # The batch's OWN number in the name: a clerk downloads both halves of
    # several batches into one folder, and `results.csv` twice is a folder of
    # one file (`reading_sheet_filename`'s precedent, one module over).
    stem = batch.batch_no or str(batch.id)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in stem)
    body = _successes_csv(batch) if key == "successes" else _failures_csv(batch)
    return f"{safe}-{key}.csv", body
