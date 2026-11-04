# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 2 · `P2.8` (the third of the three retirements —
#           the customer statement becomes a definition rendered by 2·1) and
#           `P2.16`.  Screens: 2·1 Report viewer, opened at `/reports/statement`.
# Rules:    **BR-REP-038** (CONFIRMED 2026-09-27, PO ruling verbatim: *"it
#           should be like bank statement. this si correct - Build it on the
#           ledger — the account's running record, which holds both sides"*) ·
#           BR-REP-001 (every money report states its date basis) ·
#           BR-REP-002 (read models over the books) · BR-LED-010 (the running
#           balance, `r_n = r_{n−1} + charge_n − payment_n`) ·
#           CLAUDE.md hard rule 5 (ONLY the ledger posting service writes
#           journal lines — this READS them and writes nothing) · hard rule 2
#           (money to 4 decimals, displayed at 2; never a float) ·
#           hard-won law 2's MIRROR (never a control the query cannot honour —
#           a subject with no read model refuses BY NAME) · B14 rule 31.
# Tests:    06-backend/tests/test_br_rep_038_statement.py
#           10-scripts/rep_p2_statement_pg_proof.py (real PostgreSQL)
# Impacts:  apps/reports/runner.py (`_RUN_CONTROLS` gains `subject` and
#           `subject_id`; `queries_for` consults `MODULE_VIEWERS`) ·
#           apps/reports/migrations/0007_br_rep_038_statement_on_ledger.py
# ───────────────────────────────────────────────────────
"""A CUSTOMER STATEMENT IS A BANK STATEMENT: BOTH SIDES, IN DATE ORDER.

WHAT THE RULING CHANGED, AND WHY IT IS A MIGRATION AND NOT AN EDIT
─────────────────────────────────────────────────────────────────
`reports/0003_seed_catalogue.py` seeded `R24 statement` onto the **invoices**
dataset. Invoices are CHARGES. A statement built on them shows every bill, no
payment at all, and still prints a closing balance — which is the sentence the
invoices dataset already published when it refused this definition by name. The
seed has run on every database, so moving it is `0007`, not an edit.

BR-REP-038 puts the statement on the **ledger**: an opening balance, every
charge and every payment in date order, and a closing balance.

WHAT THIS MODULE IS AND IS NOT
──────────────────────────────
It is a THIN VIEWER. It computes no money. `apps.ledger.reporting.account_ledger`
already is the engine BR-REP-038 describes — it sums the opening position from
every posted AR line before the window, carries `r_n = r_{n−1} + charge_n −
payment_n` across a SQL page, and publishes the WINDOW's totals rather than the
page's. Re-deriving any of that here would be a second reading of one account's
money, which is how two reports come to disagree about one customer.

So this file resolves the SUBJECT, hands the ledger the window and the page, and
shapes the answer into the one wire shape S46 renders. Everything else is
ledger's, through `report_seams` — `apps/reports` imports no other module's
models (`CR-142-BRC07` §3).

⚠ **THREE OF THE FOUR SUBJECTS REFUSE BY NAME, AND THAT IS DELIBERATE.**
`P2.14` built the four-subject vocabulary; the ledger publishes a running record
for ONE of them, `account`. A statement served at the `customer` grain by
quietly reporting one of that customer's accounts would be hard-won law 2's
mirror on a money screen — a live control answering a different question with a
confident head above it. `customer`, `premises` and `unit` each raise
`queries.DatasetCannotServe` naming what is missing, so the card is marked
unavailable rather than opening onto the wrong account's money. `P2.15` is the
`unit` one.

⚠ **NO SUBJECT ID, NO ROWS — AND IT SAYS SO RATHER THAN SHOWING THE TENANT.**
A bank statement is about ONE account. Handed no `subject_id` this returns zero
rows with a stated absence, never every account's lines under one heading. The
`account_ledger` refusal sentence names that exact failure as the reason the
`journal_lines` DATASET may not serve R25, and it would be the same failure here.

⚠ **WHY `basis` IS THE LEDGER'S AND NOT THE SEED'S.** `0003` seeded R24 at the
EVENT basis, labelled *Statement date*. The ledger strikes every figure on
`journal_entries.entry_date`, the BOOK date, and publishes `posting`. R39
`regulatory_filing` is refused by the `journal_lines` dataset for precisely this
mismatch — *"serving it here would answer a filing with a period the regulator
did not ask about"* — so shipping a statement claiming EVENT over posting-dated
rows would repeat that defect rather than avoid it. `0007` moves the basis with
the dataset and this viewer serves the read model's own word, never a stored
one. That is a CONSEQUENCE of BR-REP-038, recorded in the decision log of
2026-09-27; it is not a lane choosing a value.
"""

from __future__ import annotations

from typing import Any

from core import errors

from apps.reports import (
    datasets,
    queries,
    report_seams as seams,
    subject as subject_module,
    subject_head,
)

#: The definition key this viewer serves. `catalog.py`'s constants are being
#: deleted by `P0.7`; the key is the ROW's and is spelled here once.
KEY_STATEMENT = "statement"

#: The one subject whose read model, columns and head differ (`P2.15`).
#: Spelled once here rather than compared as a bare string in four places — a
#: subject name typed inline is a silent no-op the day it is misspelled, and
#: every branch below would fall through to the account read model.
SUBJECT_UNIT = "unit"

#: The columns R24 heads, in a reader's order. A statement reads left to right
#: as a bank statement does: when, what, which document, then the two sides and
#: where that leaves you.
STATEMENT_COLUMNS: tuple[str, ...] = (
    "entry_date",
    "type",
    "reference",
    "description",
    "charge",
    "payment",
    "running_balance",
)

#: `P2.15` · `BR-REP-043` — the UNIT subject's columns, and the ONE place this
#: report's shape depends on its subject.
#:
#: ⚠ **THE OCCUPANT COLUMN APPEARS ON THIS SUBJECT AND NO OTHER**, because it is
#: only here that one document's rows can belong to different people: a unit
#: outlives its tenants. Adding it everywhere would put a column headed with a
#: person's name over an account statement where every row is the same person —
#: a column that is always the same value is not information, it is furniture.
#:
#: ⚠ **IT SITS BEFORE THE MONEY, NOT AMONG IT.** The three money columns are
#: read as a block (`charge`, `payment`, `running_balance`) and a text column
#: dropped between them breaks the one visual grouping a statement has.
#:
#: `account` is the unit's ACCOUNT NUMBER for the row, not a uuid (B14 rule 31):
#: a unit with two tenancies has two account numbers over one window, and a
#: reader tracing a figure needs to know which one carried it.
UNIT_STATEMENT_COLUMNS: tuple[str, ...] = (
    "entry_date",
    "type",
    "reference",
    "description",
    "occupant",
    "account",
    "charge",
    "payment",
    "running_balance",
)

#: `P2.23`'s line under the title — and it is a **CODE**, never a sentence.
#:
#: ⚠ **`ReportGrainLine` TRANSLATES `reports.grain.<code>` WITH AN EMPTY
#: DEFAULT.** A grain published as English prose would therefore render as
#: NOTHING on screen while every test of the payload passed — law 2's mirror,
#: one key away from `DEF-REP-6900`, where three basis codes with no catalogue
#: entry reached a clerk as raw dotted identifiers. The sentence is the eleven
#: catalogues', per B14 rule 35.
#:
#: ⚠ **AND IT IS `posting`, NOT THE SUBJECT.** The report is ABOUT an account
#: and one ROW is one posting against it. Serving the subject's own grain here
#: would print *"One row per account"* over a table with two rows for one
#: account — a confident wrong fact, which `queries._report`'s own comment says
#: is worse than having none.
GRAIN = "posting"

#: Subject -> why the ledger cannot draw a running record at that grain. The
#: sentence is what a clerk reads on the card, so it says what is missing and
#: what IS served, never a rule id (B14 rule 33: rationale is zero words on
#: screen; these reach the `unavailable` channel a developer and the catalogue
#: read, in the same shape `queries.JOURNAL_LINES_DEFINITIONS_NOT_SERVED` uses).
SUBJECTS_NOT_SERVED: dict[str, str] = {
    "customer": (
        "Statement at the CUSTOMER grain is one running record across every account "
        "that customer holds, and the ledger publishes a running balance for one "
        "account at a time. Serving it here would print one of their accounts under "
        "a heading naming the person — and a jointly-held account belongs in full to "
        "each holder (BR-CUS-054), so the arithmetic is not a sum either. The "
        "account subject serves each of their accounts today."
    ),
    "premises": (
        "Statement at the PREMISES grain is one running record for a building. "
        "`apps.ledger.reporting.by_premises_summary` publishes billed, collected and "
        "owed per premises — three totals, not an ordered sequence with a carry "
        "forward — so there is no opening balance and no row order to run a balance "
        "along. A running record at this grain is a read model nobody has built."
    ),
    # ⚠ **`unit` LEFT THIS TABLE ON 2026-09-27 (`P2.15`, `BR-REP-043`).** Its
    # sentence read *"the one subject nobody built … what does not exist is a
    # read model that opens, orders and carries a balance over them"*. It exists
    # now — `apps.ledger.reporting.unit_ledger` — so the sentence would be a
    # refusal that outlives what it refused over, which is `DEF-CWP-3925`'s
    # shape and the most-filed failure in this repo. It is DELETED rather than
    # reworded, and `statement_subject_unit` is the test that would have named
    # it if it had been left.
}


def _subject_of(params: Any) -> subject_module.Subject:
    """The subject this run asks for, or the definition's default.

    ⚠ **IT DOES NOT FALL BACK ON AN UNKNOWN VALUE.** `subject.resolve` raises,
    and `subject.py` says why in full: `BR-SHL-011`'s fall-back rule is about
    FILTERS, and a subject decides what the report is ABOUT. Answering a
    question nobody asked with a confident head above it is *"worse than one
    that refuses"*.
    """
    raw = params.get("subject") or params.get("f.subject")
    if raw in (None, ""):
        return subject_module.resolve(subject_module.DEFAULT)
    return subject_module.resolve(raw)


def _subject_id_of(params: Any) -> str | None:
    """The one account this statement is about, however the wire spelled it.

    Both spellings, for the reason every query in this module reads both: the
    shipped screens send filters dotted and `runner.bind` passes the ORIGINAL
    key through, so a reader of one spelling is handed a request with the
    parameter missing and reports the wrong scope under a heading that says
    otherwise.

    ⚠ **B14 RULE 31.** This is an id and it travels in the URL, where the clerk
    never reads it — exactly as the retired `CustomerStatementPage` put a
    customer id there. It is NEVER a visible value: the head is composed from
    the subject's own `head_from` fields.
    """
    for name in ("subject_id", "f.subject_id", "account", "f.account"):
        found = params.get(name)
        if found not in (None, ""):
            return str(found)
    return None


#: What a statement with no subject id says instead of showing the tenant.
NO_SUBJECT_ID = {
    "code": "a_statement_names_one_account",
    "br_ref": "BR-REP-038 · BR-LED-010",
    "detail": (
        "A statement is one account's running record, so it opens on the account "
        "the URL names. No account was named, so no rows were read — the "
        "alternative is every account's postings under one account's heading, "
        "which is the failure the journal-lines dataset refuses R25 over."
    ),
}


def statement(params: Any) -> dict[str, Any]:
    """R24 — the account's running record over a window, both sides, in order.

    BR-REP-038, and the worked case the PO was shown: Dana opens Alia's
    statement for September and reads the September bill of `$84.20`, the
    payment of `$84.20` on the 14th, and the balance carried forward.

    ⚠ **IT PAGES (`NFR-3`) AND THE CARRY-FORWARD SURVIVES THE PAGE.** `per` and
    `page` go to the read model, which cuts the page in SQL and sums the rows
    BEFORE the offset in the same total order — so row 51's balance is the same
    figure whether it was read on page two or in an unpaged run. `totals` is the
    WINDOW's, never the page's, so the closing balance is what the account owes
    and not what the rows in front of the clerk come to.

    ⚠ **EXPORTING IS `statement_stream`, A SEPARATE FUNCTION AND NOT A FLAG** —
    brief §8.2, *"the left path never fetches more than a page; the right path
    never holds one"* — so an export cannot reach a paging function and inherit
    a screen's page size.
    """
    start, end = queries._checked_window(params)
    chosen = _subject_of(params)

    refusal = SUBJECTS_NOT_SERVED.get(chosen.name)
    if refusal is not None:
        raise queries.DatasetCannotServe(KEY_STATEMENT, refusal)

    subject_id = _subject_id_of(params)
    page_no, per = _paging(params)

    if subject_id is None:
        return _shaped(
            view=None,
            chosen=chosen,
            start=start,
            end=end,
            page_no=1,
            per=per,
            # No record was named, so `compose` publishes no head — the screen
            # draws nothing rather than a heading over nobody's money.
            subject_id=None,
            extra_unavailable=[NO_SUBJECT_ID],
        )

    # ⚠ **THE SUBJECT PICKS THE READ MODEL, AND THE UNIT'S IS ITS OWN.**
    # `BR-REP-043` — the subject scopes the SET. A unit's set spans its
    # tenancies, so its opening balance is the unit's rather than the sitting
    # tenant's, which is why `unit_ledger` exists instead of a filter on
    # `account_ledger` (that would strike one account's opening over several
    # accounts' rows — a document that does not add up).
    if chosen.name == SUBJECT_UNIT:
        view = seams.unit_ledger(subject_id, start=start, end=end, page=page_no, per=per)
    else:
        view = seams.account_ledger(
            subject_id, start=start, end=end, page=page_no, per=per
        )
    if view is None:  # pragma: no cover — ledger publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.statement.unavailable")
    return _shaped(
        view=view,
        chosen=chosen,
        start=start,
        end=end,
        page_no=page_no,
        per=per,
        subject_id=subject_id,
    )


def statement_stream(params: Any) -> Any:
    """EVERY row of the statement, from a generator — the export path.

    A separate lookup and a different kind of object from `statement`, for the
    reason `runner.stream_for` records: an export that reached the paging
    function would write a valid-looking fifty rows over a thousand-row account.

    ⚠ **IT STILL DOES NOT HOLD THE BOOK.** `per=None` asks the read model for
    the window unpaged, which is one ACCOUNT's AR lines over one window — the
    grain `NFR-5` cares about is a cap, and there is none here.
    """
    payload = statement({**_as_dict(params), "per": "all"})
    for row in payload["rows"]:
        yield row


def _as_dict(params: Any) -> dict[str, Any]:
    return dict(params) if params else {}


def _paging(params: Any) -> tuple[int, int | None]:
    """`(page, per)`. `per="all"` — what `runner.run(whole=True)` sets — is None.

    `BR-SHL-011`: an unreadable value clamps rather than erroring, so a saved
    link carrying `page=frog` opens on page one.
    """
    raw_per = params.get("per")
    if raw_per in (None, "", "all"):
        per: int | None = None
    else:
        try:
            per = max(1, int(str(raw_per)))
        except (TypeError, ValueError):
            per = None
    return queries._page_number(params.get("page")), per


def _shaped(
    *,
    view: dict[str, Any] | None,
    chosen: subject_module.Subject,
    start: Any,
    end: Any,
    page_no: int,
    per: int | None,
    subject_id: Any = None,
    extra_unavailable: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The one wire shape S46 renders, built through `queries._report`.

    Built there rather than assembled here so `BR-REP-001` cannot be forgotten:
    `basis` is a required argument of that function, and a report without one
    does not compile into an answer.
    """
    is_unit = chosen.name == SUBJECT_UNIT
    rows = [] if view is None else [_row(row, unit=is_unit) for row in view["rows"]]
    opening = None if view is None else view["opening_balance"]
    page_opening = None if view is None else view["page_opening_balance"]
    totals = {} if view is None else view["totals"]
    closing = totals.get("closing_balance") if totals else None
    charges = totals.get("charges") if totals else None
    payments = totals.get("payments") if totals else None

    unavailable = list(extra_unavailable or ())
    unavailable.extend(dict(gap) for gap in (() if view is None else view.get("unavailable") or ()))

    return queries._report(
        KEY_STATEMENT,
        # The READ MODEL's word, never the stored one — see this module's
        # docstring on why `0007` moved the seeded basis to match it.
        basis=datasets.BASIS_POSTING if view is None else view["basis"],
        window={"start": queries._iso(start), "end": queries._iso(end)},
        currency=None if view is None else view.get("currency"),
        columns=UNIT_STATEMENT_COLUMNS if is_unit else STATEMENT_COLUMNS,
        # ⚠ **THE THREE MONEY COLUMNS ARE TYPED AT SOURCE, AND UNTIL NOW THEY
        # WERE NOT TYPED ANYWHERE ON THE SERVER.** `charge`, `payment` and
        # `running_balance` are this viewer's OWN derived columns — no dataset
        # declares them — so `runner`'s defaulting loop omits them, and its own
        # comment says an omitted column means *render it as text*.
        #
        # They render correctly today ONLY because `ReportViewerPage.tsx` keeps
        # a hand-typed map with `statement: ["charge","payment","running_balance"]`
        # in it. That map is the SECOND precedence and the fallback; a report
        # whose columns live only there is one rename away from printing
        # `84.200000` at a clerk, which is `DEF-REP-6902`'s exact shape one
        # report over (*"one row carried two precisions for the same kind of
        # figure"*). Declaring them here makes the server the source of the
        # type, which is what the front end asks for first.
        #
        # ⚠ **AND IT IS WHAT MAKES THE UNIT SUBJECT SAFE.** That map is keyed by
        # report KEY, not by subject, so the unit statement inherits the same
        # three names — but `occupant` and `account` are TEXT and must NOT be
        # money, and a future money column added to this subject would have
        # been typed by nobody. The declaration below is per column and says so.
        column_meta={
            name: {
                "type": datasets.TYPE_MONEY,
                "unit": None,
                "unit_from": None,
                "money_basis": datasets.BASIS_POSTING if view is None else view["basis"],
                "scale": 4,  # hard rule 2: stored to 4, DISPLAYED at 2.
            }
            for name in ("charge", "payment", "running_balance")
        },
        rows=rows,
        grain=GRAIN,
        # ── `DEF-REP-7070` · THE REPORT DECLARES WHAT IT CANNOT RUN WITHOUT ──
        #
        # ⚠ **THE REQUIREMENT WAS ONLY EVER STATED AS A REFUSAL, AFTER THE
        # FACT.** `NO_SUBJECT_ID` is published in `unavailable` once a run has
        # already happened and returned nothing — so the screen could say
        # *why* the table was empty, and could never say *what to do first*.
        # The Product Owner opened `/reports/statement?edit=1` and read four
        # tiles of *Not counted yet* over *No rows match*, with the one
        # sentence that explains it four scroll-lengths below the fold:
        # *"A statement opens on one account."*
        #
        # ⚠ **A DECLARATION IS NOT A SECOND COPY OF THE REFUSAL.** They are
        # different facts and both are needed: this says *this report is about
        # one record and here is which kind*, and it is TRUE on every run,
        # including the ones that succeed. The refusal says *you did not name
        # one*, and it is true on some. A screen that had only the refusal
        # could not draw a chooser until after it had asked a question it knew
        # would be refused.
        #
        # ⚠ **IT IS THE RUNNER'S VOCABULARY AND NOT A DATASET'S FILTER.**
        # `subject_id` is in `runner._RUN_CONTROLS` for the reason recorded
        # there; `finds` is the SUBJECT this run resolved, so a definition
        # drawn at the premises grain asks for a premises rather than for an
        # account. The screen holds no table of which report needs what.
        #
        # ⚠ **`sorts`/`searchable` ARE FALSE BECAUSE THEY ARE FALSE, not to
        # fill the shape.** `queries._report` published no `controls` for this
        # report at all until now and the viewer read `controls?.sorts ?? []`,
        # so the table drew no carets and no search box. Saying so out loud
        # changes nothing on screen and stops the absence being an inference.
        controls={
            "sorts": [],
            "sort": "",
            "dir": "asc",
            "searchable": False,
            "requires": [{"param": "subject_id", "finds": chosen.name}],
        },
        kpis=[
            queries._kpi(
                "opening_balance",
                queries._money(opening),
                reason_code=None if opening is not None else NO_SUBJECT_ID["code"],
            ),
            queries._kpi(
                "charges",
                queries._money(charges),
                reason_code=None if charges is not None else NO_SUBJECT_ID["code"],
            ),
            queries._kpi(
                "payments",
                queries._money(payments),
                reason_code=None if payments is not None else NO_SUBJECT_ID["code"],
            ),
            queries._kpi(
                "closing_balance",
                queries._money(closing),
                reason_code=None if closing is not None else NO_SUBJECT_ID["code"],
            ),
        ],
        totals={
            "opening_balance": queries._money(opening),
            # ⚠ **THE PAGE's opening is published BESIDE the window's.** They
            # are the same figure only on page one, and a statement printing
            # the window's opening over page two is a document that does not
            # add up (`apps.ledger.reporting.account_ledger` strikes both).
            "page_opening_balance": queries._money(page_opening),
            "charges": queries._money(charges),
            "payments": queries._money(payments),
            "closing_balance": queries._money(closing),
            "subject": chosen.name,
            # ⚠ **THE HEAD, AND ON THIS SUBJECT ONLY — HARD RULE 8.**
            # `subject.Subject.head_from` for a unit is
            # `("premises_address", "unit_label")`: *a unit refines a premises
            # by LABEL, not by address*, so the address is the BUILDING's,
            # walked to through the ledger's dimension seam, and the unit
            # contributes its label. There is no `unit_address` here and there
            # must never be one.
            **(
                {
                    "premises_address": view.get("premises_label"),
                    "unit_label": view.get("unit_label"),
                    # ⚠ **PLURAL, AND OVER THE WINDOW RATHER THAN THE PAGE.**
                    # A unit outlives its tenants, so a window spanning a
                    # move-out names BOTH occupants — that is the PO's worked
                    # case. Computed from a DISTINCT over the whole window, so
                    # page two does not name a different person from page one.
                    "occupants": list(view.get("occupants") or ()),
                }
                if is_unit and view is not None
                else {}
            ),
        },
        # ── `DEF-REP-7052` · WHOSE MONEY THIS IS ─────────────────────────
        # ⚠ **THE STATEMENT HAS NEVER NAMED THE RECORD IT IS ABOUT**, and the
        # data to do it has been published since `P2.14`: `Subject.head_from`
        # names the fields, in order, and NOTHING read it — not the server, not
        # the screen. A clerk printed a page of somebody's money with the
        # report's name above it and no indication whose. The brief draws it
        # (p69 `100244 · Ruiz, Marisol`) and p71 states it in prose: *"The head
        # reads 1408 Elm Street · Unit 3."*
        #
        # ⚠ **IT IS COMPOSED BY `subject_head`, NOT HERE, AND THAT IS THE
        # POINT.** This module knows two subjects; the head must be right for
        # every subject anyone adds. `subject_head.compose` walks the SUBJECT's
        # own declaration and asks a registered resolver for the values, so a
        # new grain publishes a correct head by adding one resolver and nothing
        # else — no branch here and no table on any screen.
        head=subject_head.compose(chosen, subject_id, view),
        # ⚠ **WHAT THE EDITOR MAY OFFER ON THIS RUN** (`DEF-REP-7072`). The
        # SUBJECT decides: the unit statement has `occupant` and `account` and
        # no other subject does, so offering them everywhere would be a tick
        # box for a column the run cannot serve. `runner.served_columns` stays
        # the union — that is what may be ASKED for — and this is what is DRAWN.
        column_choices=UNIT_STATEMENT_COLUMNS if is_unit else STATEMENT_COLUMNS,
        page=(
            None
            if view is None
            else {
                "page": view["page"],
                "per": view["per"],
                "total": view["total"],
            }
        ),
        unavailable=unavailable,
    )


def _row(row: Any, *, unit: bool = False) -> dict[str, Any]:
    """One ledger row on the wire, at hard rule 2's precision.

    Money leaves as its EXACT decimal string through `queries._money` — B4
    rounds at finalization and at display, and this is neither.

    ⚠ **NO `entry_id` AND NO `source_id` — B14 rule 31.** The read model carries
    both for a drill-back; a statement's visible Reference is the DOCUMENT
    NUMBER the ledger resolved (`P5.8`), and `None` where a document kind has
    no number, never the uuid standing in for one.
    """
    shaped = {
        "entry_date": queries._iso(row.entry_date),
        "type": row.type,
        "reference": row.reference,
        "description": row.description,
        "charge": queries._money(row.charge),
        "payment": queries._money(row.payment),
        "running_balance": queries._money(row.running_balance),
    }
    if unit:
        # ⚠ **`None` AND NEVER A DASH OR AN EMPTY STRING.** A line posted before
        # the books carried a customer has NO occupant, and that is a different
        # fact from an occupant whose name is blank. The viewer renders an
        # absent value as an absence; a placeholder typed here would be this
        # module inventing a value for a question it cannot answer, and the
        # named gap `GAP_OCCUPANT_NOT_STAMPED` is what says so.
        shaped["occupant"] = row.occupant
        shaped["account"] = row.account_label
    return shaped


#: KEY -> every column name this module's viewer can serve, for `DEF-REP-7072`.
#:
#: ⚠ **THE EDITOR AND THE RUNNER SHARED ONE WORD OUT OF SEVEN, AND NEITHER WAS
#: WRONG ABOUT ITSELF.** `runner._requested_columns` checked a run's ticked
#: columns against the DATASET's declaration, which is right for the nine
#: dataset-backed reports and has nothing to say about a report served by a
#: viewer of its own. A statement serves seven names; the `journal_lines`
#: dataset declares five (`posted_on`, `account_code`, `account_name`,
#: `reference`, `narrative`); the two lists intersect in `reference` and in
#: nothing else. So opening `?edit=1` — which is the only thing that sends a
#: `columns` control — cut a seven-column statement to ONE column, measured on
#: real PostgreSQL 16 before this constant existed.
#:
#: **THE FIX IS A DECLARATION RATHER THAN A FALL-BACK**: a viewer that owns a
#: report owns its column vocabulary, exactly as `MODULE_VIEWERS` means it owns
#: the read. `runner.served_columns()` is the ONE function that answers *what
#: may this report be asked for*, and the editor, the render narrowing and
#: `validate()` at save all read it — so the control cannot offer a name the
#: read cannot honour, which is the failure that produced this defect.
#:
#: ⚠ **IT IS THE UNION OF BOTH SUBJECTS AND NOT ONE OF THEM.** `occupant` and
#: `account` exist on the unit statement only; a vocabulary that changed with
#: the subject would refuse a bookmarked `columns` the moment a clerk switched
#: grain, and the render narrowing already keeps a name that this RUN did not
#: serve off the table (`_shaped` intersects with the payload's own `columns`).
MODULE_COLUMNS: dict[str, tuple[str, ...]] = {
    KEY_STATEMENT: tuple(
        dict.fromkeys(STATEMENT_COLUMNS + UNIT_STATEMENT_COLUMNS)
    ),
}


#: KEY -> viewer, owned by THIS module rather than by `queries.VIEWERS`.
#:
#: ⚠ **BECAUSE A VIEWER WINS, A ROLLBACK OF `0007` ALONE IS NOT A ROLLBACK.**
#: `runner.queries_for` asks here BEFORE it asks the dataset, so migrating the
#: definition back to `invoices` leaves this viewer serving posting-dated rows
#: under a row that says `event`, beside a catalogue card that says the report
#: cannot be produced. Undoing BR-REP-038 means reverting this registration too.
#:
#: ⚠ **`runner.queries_for` CONSULTS IT FIRST AND IT IS ONE LOOKUP, NOT A
#: SEVENTH DISPATCH TABLE.** `queries.py` holds four shipped per-report viewers
#: and the nine dataset queries; a module that owns a report owns its
#: registration, which is what keeps `queries.py` from becoming the file every
#: report lane edits at once. The rule `runner` enforces is unchanged: a
#: per-REPORT viewer wins, then the DATASET's own query.
MODULE_VIEWERS: dict[str, Any] = {KEY_STATEMENT: statement}

#: KEY -> the streaming read, same contract as `queries.DATASET_STREAMS`.
MODULE_STREAMS: dict[str, Any] = {KEY_STATEMENT: statement_stream}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · P2.8 / P2.16 · BR-REP-038 (PO ruling 2026-09-27)
# screens: 2·1 Report viewer at /reports/statement
# generated: 2026-09-27 by lane REP-P2-LAST; amended 2026-09-28 by lane REP-STMT-SCREEN (`DEF-REP-7072` `MODULE_COLUMNS` · `DEF-REP-7052` the subject head · `DEF-REP-7053` the export resource)
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED MEASURED FIRST, THROUGH THE RUNNER, on real PostgreSQL 16 before a line of this file was written — `runner.run("statement")` raised `DatasetCannotServe: Statement draws a running balance … The invoices dataset produces charges only, so serving it here would show every bill and no payment and still print a closing balance.` Re-measured green after `0007`: 6 rows, 3 charges, 3 payments, closing 0.00 (`10-scripts/rep_p2_statement_pg_proof.py`)
# note: the pytest file was ALSO run red before the wiring landed, but that run stopped at `-x` on a broker error (`JOBS_EAGER=false` with no Redis), so it is NOT quoted as the red proof — a red for the wrong reason is not evidence about the right one. A later red WAS this lane's own fault and is in the decision log: the both-sides case compared money as TEXT (`!= "0.000000"`) and `_money` serves the exact decimal, so `"0"` counted as a charge.
# exceptions: (1) three of the four subjects refuse BY NAME — `customer`, `premises` and `unit` have no running-record read model and `P2.15` is the unit one · (2) this module READS journal lines and writes nothing (hard rule 5)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
