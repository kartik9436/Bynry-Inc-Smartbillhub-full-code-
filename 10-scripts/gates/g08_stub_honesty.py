"""G8 - stub honesty (B12 r2 / prime directive).

Four clauses, all over data both sides already publish:

  A. Every `NotImplementedError(… "OQ-###" …)` stub must cite an OQ that
     (a) exists in 12-governance/01-open-questions.md and (b) is NOT closed — a
     stub citing a CLOSED OQ is stale: the question was answered, so the stub
     must be replaced by the ruled implementation (or re-routed to a new OQ).
  B. Every OQ-### appearing ANYWHERE in 06-backend/, 07-frontend/ or 04-docs/
     resolves to a registry row. This is the REVERSE of what G17 does, and it is
     the direction that catches MINTING.
  C. Every `blocked_by:` entry in a 06-epics story frontmatter names an OQ that
     is not CLOSED.
  D. Every registry status cell parses to a known STATE token.

The reverse check for clause A — an OPEN OQ whose code path contains real code
instead of a stub (an agent decided a question) — needs semantic knowledge of
which code belongs to which OQ; that remains REVIEWER DUTY until the packet
tooling maps OQs to code paths.

WHY CLAUSE A IS MULTI-LINE (DEF-096)
-------------------------------------
It was LINE-SCOPED until 2026-08-15, and `apps/payments/credit.py` puts
`raise NotImplementedError(` on one line and `"OQ-195: …"` on the next — so a
perfectly ordinary wrapped raise walked straight past the gate written to read
it. That is not an exotic formatting choice; it is what `black` produces the
moment the message is long enough, which every honest stub message is. MEASURED
before this change: 11 citations were visible line-scoped and 18 exist, so
**7 of 18 OQ-cited stubs were invisible to G8** — in customers/services.py,
ledger/chart.py, ledger/cost_capture.py and payments/credit.py.

WHY CLAUSE B EXISTS (DEF-096, and it is the sharper half)
---------------------------------------------------------
The registry ended at OQ-194, so OQ-195 looked free. It was not: OQ-195 was
raised by name in `apps/payments/credit.py` and OQ-196/197 about twenty times
across the notifications app, with no registry row for any of them — and later
the same day five MORE were found (OQ-127/128/129/130/185, a contiguous block,
which is the tell that they were minted in one conversation and the batch was
never written down). Eight orphans across five modules.

**Both gates that look like they cover this missed it, for different reasons,
and that is the finding.** G17 compares registry rows to registry rows, so an OQ
minted in CODE and never registered is invisible to it by construction. G8 read
only the stub lines. The general law: *a gate that checks a registry is
internally consistent has not checked that the registry is COMPLETE.*

The cost is not hypothetical — the next lane needing a number reads the registry,
sees the highest row, and mints a DUPLICATE that two lanes then use to mean two
different things. Nine collisions or orphans in one session is not a discipline
problem; it is a missing gate.

WHY CLAUSE C EXISTS (DEF-104)
------------------------------
The registry's own lifecycle says *"Answers enter HERE first, then the BR flips
to CONFIRMED, then story frontmatter updates — one commit, all three"*, and only
the first step happened. Nothing mechanically compared a story's `blocked_by`
list against the registry, so a closed question sat in frontmatter indefinitely
and G8 only caught it once somebody wrote the stub the stale text asked for.
MEASURED on 2026-08-15: SIX stale entries across four stories (US-SHL-018,
US-TEN-017, US-NOT-016 and all four EP-RAT-07 stories on OQ-095), each naming a
question closed on 2026-08-10 — and two of them carried a TEST CASE instructing
`NotImplementedError("OQ-075")` / `("OQ-077")` by name, an instruction that
fails clause A on the spot for any agent that follows it.

WHY THE STATE IS PARSED AND NEVER SUBSTRING-MATCHED (clause D)
--------------------------------------------------------------
Clauses A and C both ask "is this OQ closed", and the old test was
`"CLOSED" in status`. A status cell is FREE TEXT. A previous session wrote
narrative prose into one and G8 failed a LIVE question because the word CLOSED
appeared inside a sentence. `common.oq_is_closed()` reads the leading STATE
TOKEN and nothing else — **a status field is a state, not a story** — and
clause D fails the run if any cell stops parsing to a known state, so the
registry cannot quietly drift back into prose.
"""
import io
import sys
import re
import tokenize
from pathlib import Path

import common

STUB_RE = re.compile(r"NotImplementedError\s*\(")
#: How far past `NotImplementedError(` clause A looks for the citation. A stub
#: message is one to three wrapped lines; 5 is generous and still cannot reach
#: an unrelated OQ mentioned further down the function.
STUB_LOOKAHEAD_LINES = 5

#: Clause B's search space, as DEF-096's prevention column names it.
OQ_SCAN_ROOTS = ("06-backend", "07-frontend", "04-docs")
OQ_SCAN_SUFFIXES = {".py", ".ts", ".tsx", ".md", ".sql", ".json", ".yml", ".yaml", ".css", ".html"}
OQ_SCAN_SKIP_DIRS = {
    "node_modules", "__pycache__", ".ruff_cache", ".pytest_cache", ".mypy_cache",
    "dist", "build", "coverage", "playwright-report", "test-results", ".venv",
}

#: The states a registry cell may parse to (clause D). `PARTIALLY CLOSED` is its
#: own state on purpose and is NOT treated as closed anywhere.
#:
#: `ROUTED` WAS MISSING UNTIL 2026-09-04 (DEF-GOV-3763), AND THE REGISTER'S OWN
#: HEADER HAS NAMED IT SINCE THE FILE WAS WRITTEN: *"Lifecycle: OPEN → ROUTED →
#: ANSWERED → CLOSED"*. The gate knew three of the four. It went unnoticed
#: because nothing had ever USED the state — the first question routed outside
#: this team (`OQ-INT-1477`, to the card processor, by PO instruction) failed the
#: gate for spelling its own lifecycle correctly. The general form is worth
#: naming: a gate carrying its OWN copy of a vocabulary the document also
#: declares will drift from it silently, and the drift only shows the first time
#: somebody uses the part that was dropped.
KNOWN_OQ_STATES = frozenset(
    {"OPEN", "ROUTED", "CLOSED", "PARTIALLY CLOSED", "SUPERSEDED",
     "SUPERSEDED DUPLICATE OF OQ", "ANSWERED", "DEFERRED", "BLOCKED",
     "PROPOSED", "WITHDRAWN"}
)

# ── Clause B's parked orphans ───────────────────────────────────────────────
#: An OQ cited in code that has NO registry row yet, parked with the reason it
#: cannot simply be registered by this lane — and EXPIRING: the moment the id
#: appears in the registry, its park is stale and this gate FAILS until the line
#: is deleted in that same diff. The register can therefore only shrink. Same
#: discipline as i18n_known_gaps.txt and seam_known_gaps.txt; a parked line is a
#: defect with a route, not a permission.
#:
#: WHY PARKING AND NOT REGISTERING, which is a rule learned by causing harm
#: (DEF-096): registering an orphan retrospectively while the lane that minted it
#: is STILL RUNNING created a duplicate — that lane minted its own id for the
#: same question and repointed every citation, so one question ended up with two
#: ids. **Register an orphan only when no live lane owns the code that cites it,
#: or tell that lane the moment you do.**
#: EMPTY, and that is the register working exactly as designed. OQ-217 was
#: parked here on 2026-08-15 by this gate's own lane, which found it cited in a
#: live lane's `apps/billing/issue.py` and `payments_seam.py` with no registry
#: row and correctly refused to register another lane's id (DEF-096: doing that
#: once produced one question with two ids). The park carried its own expiry —
#: *"the moment OQ-217 gains a registry row this park is stale and G8 fails
#: until this entry is deleted in the same diff"* — and that is this diff: the
#: DEF-116 lane registered OQ-217 in `12-governance/01-open-questions.md` and
#: removed its park in the same commit, which is the handshake the expiry
#: clause was written to force.
#:
#: ── RE-OPENED 2026-08-31 BY THE FIVE-DIGIT WIDENING (DEF-2804) ──────────────
#: `OQ-1166` is the FIRST orphan this clause has ever been able to see, and the
#: reason it could not see it before is the whole of DEF-2804: `OQ_ID_RE` was
#: `OQ-\d{3}`, so every citation of `OQ-1166` in the codebase was read as
#: **`OQ-116`** — a real, different question about `tax_authority_gl_map` — which
#: HAS a registry row, so clause B resolved it and reported nothing. The
#: misattribution was not theoretical: it was live for two days on a 🔒 rating-math
#: file.
#: Clause D1's ratchet — questions written up as a `## OQ-` SECTION with no
#: `| OQ- |` TABLE row. **Measured 2026-09-01: 9** (OQ-387, 388, 504, 590, 600,
#: 680, 681, 1166, 1221). DEF-2820 counted 8 on 2026-08-31 and `OQ-1221` joined
#: them the next day with nothing raising, which is the argument for the ratchet.
#: It may FALL and never RISE: add the missing row in the same diff that lowers
#: it. Lowering it is the whole repair — the park below is a mitigation for ONE
#: of the nine and says so.
#:
#: PROVED RED (law 7): set to 8 and run, the clause reported — verbatim —
#: "9 question(s) are written up as a `## OQ-` SECTION of the register with NO
#: `| OQ- |` table row, against a baseline of 8 that may fall and never rise —
#: OQ-387 … OQ-1221."
OQ_SECTION_ORPHAN_BASELINE = 9

OQ_PARKED_ORPHANS: dict[str, str] = {
    "OQ-1166": (
        "Cited by `apps/rating/pricing/stages/apply_charges.py` (🔒 rating math, B4) "
        "and `apps/billing/gather.py`, and written up at length as a `## OQ-1166` "
        "SECTION of the register — but it has no `| OQ-1166 |` TABLE ROW, which is "
        "the only form this clause reads. "
        "⚠ PARKED AND NOT REGISTERED, DELIBERATELY, AND THE REASON IS A ❄️ FROZEN "
        "FIGURE. The PO answered it on 2026-08-30 (*\"when units are vacant - at that "
        "time, we are only charging base rates…\"*), and the decision-log entry that "
        "records the answer also records that it COLLIDES WITH GT-19/WE-3 — a frozen "
        "B5 worked example that applies a minimum to a TIERED plan, which the ruling "
        "says cannot happen. So the question is ANSWERED and NOT CLOSED: it is owed a "
        "finance re-sign through HUMAN-GUIDE §6. Writing a status cell for it here "
        "would be this lane deciding what that cell says about a frozen figure, which "
        "is precisely the decision CLAUDE.md reserves. "
        "EXPIRY, as this register requires: the moment `OQ-1166` gains a table row "
        "this park is stale and G8 FAILS until the line is deleted in that same diff."
    ),
}


def _stub_window(lines: list[str], index: int) -> str:
    """The text of ONE `NotImplementedError(...)` call, however it is wrapped.

    Bounded by the CALL's own parentheses, not by a fixed line count. A fixed
    window is what made the first run of this clause report a false positive:
    it ran off the end of a one-line raise, swept into the NEXT comment block
    and attributed an unrelated OQ to the stub (ledger/chart.py, OQ-188). The
    window closes the moment the parens balance, so a stub can only ever be
    charged with the ids inside its own message.
    """
    depth = 0
    started = False
    collected = []
    for line in lines[index : index + STUB_LOOKAHEAD_LINES]:
        collected.append(line)
        for char in line:
            if char == "(":
                depth += 1
                started = True
            elif char == ")":
                depth -= 1
        if started and depth <= 0:
            break
    return "\n".join(collected)


# ── Clause A's parked stale stubs ───────────────────────────────────────────
#: A stub that cites a CLOSED OQ and cannot be fixed by the lane that FOUND it.
#: Keyed on (repo-relative path, OQ id) — never on a line number, which drifts.
#:
#: EXPIRING IN BOTH DIRECTIONS, which is what makes this a route and not a
#: permission: if the citation is fixed, the park no longer matches a real
#: finding and this gate FAILS until the entry is deleted; if the file is
#: renamed away, likewise. The register can only shrink.
STALE_STUB_PARK: dict[tuple[str, str], str] = {}
#: ⚠ **EMPTIED 2026-09-07 (`DEF-CUS-4631`). IT HELD THREE AND THEY EXPIRED
#: EXACTLY AS THIS REGISTER PROMISED THEY WOULD.**
#:
#: The three were `("06-backend/apps/customers/services.py", "OQ-133" | "OQ-136"
#: | "OQ-137")` — one stub, `send_disconnect_notice`, raising with all three ids
#: after they had been CLOSED on 2026-08-12. The park recorded two reasons for
#: not fixing it, and it is worth keeping both here because **the first one went
#: stale in the same way the stub did**:
#:
#:   1. *"three of its six blockers are STRUCTURAL — there is no
#:      `notice_history` table, no medical-hold column and no tenant charge-code
#:      read for the reconnect fee … the rulings are answered; the schema to
#:      honour them is not built."* **All three are built now**:
#:      `payments.collections_models.NoticeHistory` (`db_table =
#:      "notice_history"`), `customers.disconnects.medical_hold_for`, and
#:      `disconnects.reconnection_terms` reading the tenant's `CC-RECON` code.
#:      The park was written when that sentence was true and nothing brought
#:      anybody back to it — which is the SAME defect the park was parking.
#:   2. *"`apps/customers/services.py` is being edited by a LIVE lane in the
#:      shared working tree as this gate lands."* Still a real hazard; answered
#:      by doing the work in a private `git worktree`, which is CLAUDE.md law
#:      12's own advice.
#:
#: The stub is re-cited: it names no open question, states that it is superseded,
#: and points at the mounted disconnect-case routes. Nothing is parked, so this
#: register is empty and the gate has no exemptions to grant.
def _python_string_spans(text: str) -> list[tuple[tuple[int, int], tuple[int, int]]] | None:
    """Every STRING token in a Python source, as ((row, col), (row, col)) spans.

    `None` when the file will not tokenize — a syntax error is somebody else's
    gate, and this one must not silently skip a file it could not read.
    """
    spans: list[tuple[tuple[int, int], tuple[int, int]]] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.STRING:
                spans.append((token.start, token.end))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return None
    return spans


def _inside_a_string(spans, row: int, col: int) -> bool:
    """Is (row, col) inside one of those spans? Column-aware, and that matters.

    A one-line `raise NotImplementedError("OQ-195")` HAS a string token on its
    own line — the message. Testing the LINE would throw away every real stub
    in the repository; testing the POSITION of the `NotImplementedError` text
    keeps them and drops only the ones written inside a docstring.
    """
    for start, end in spans:
        if (row, col) < start:
            continue
        if (row, col) < end:
            return True
    return False


def _oq_citations_in_stubs() -> tuple[list[tuple[str, int, str]], int]:
    """Clause A: (path, lineno, oq_id) for every OQ cited by a stub, and the
    number of PROSE mentions skipped on the way.

    MULTI-LINE by construction — the citation may sit on the `raise` line or on
    any of the next few, because that is what a wrapped message looks like and
    what `black` produces for any honest stub message.

    COMMENT LINES ARE SKIPPED, the same posture G6 takes: prose that DESCRIBES a
    stub elsewhere (`… which raises \\`NotImplementedError("OQ-200")\\` at that
    boundary`) is a note about the guard, not the guard. Judging it would make
    the gate fire on documentation of itself, which is how a gate teaches people
    to stop reading it.

    ⚠ **AND A DOCSTRING IS PROSE TOO — `DEF-GOV-4385`, MEASURED AT 20 OF 32.**
    The paragraph above was the whole rule until 2026-09-07 and it names ONE
    shape of prose: a line starting `#`, `//` or `*`. This repository's
    docstrings routinely QUOTE the stub they replaced — *"THIS RAISED
    `NotImplementedError("OQ-790")` UNTIL 2026-09-01"* — and such a line starts
    with a warning sign or a back-tick, so every one of them was charged as a
    live stub. The gate then said *"32 OQ-cited stub(s) all open"* over **12**,
    overstating its own reach by 167%.
    **It never turned anything red, which is exactly why it survived** — a guard
    that over-reports its coverage looks like a guard doing more work. It became
    load-bearing the moment `DEF-GOV-4384` taught `oq_is_closed()` to read a
    ✅-prefixed cell: the three loudest of those docstrings are ones saying *the
    question CLOSED*, so the parser fix alone would have arrived as three brand
    new FALSE failures naming code that is correct.
    So the position of the `NotImplementedError` text is now checked against
    Python's own tokenizer, and the count that was skipped is REPORTED beside
    the count that was checked — a check that cannot cover its whole subject
    must print what it left out (law 7).
    """
    citations = []
    prose_skipped = 0
    for path in common.code_files():
        text = common.read_text(path)
        lines = text.splitlines()
        spans = _python_string_spans(text) if path.suffix == ".py" else None
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(("#", "//", "*")):
                continue
            match = STUB_RE.search(line)
            if not match:
                continue
            if spans is not None and _inside_a_string(spans, index + 1, match.start()):
                prose_skipped += 1
                continue
            for oq_id in dict.fromkeys(common.OQ_ID_RE.findall(_stub_window(lines, index))):
                citations.append((common.rel(path), index + 1, oq_id))
    return citations, prose_skipped


def _oq_mentions_everywhere() -> dict[str, list[str]]:
    """Clause B: OQ-ID -> the files that name it, across the three roots."""
    mentions: dict[str, list[str]] = {}
    for root_name in OQ_SCAN_ROOTS:
        root = common.REPO_ROOT / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in OQ_SCAN_SUFFIXES:
                continue
            if any(part in OQ_SCAN_SKIP_DIRS for part in path.parts):
                continue
            for oq_id in set(common.OQ_ID_RE.findall(common.read_text(path))):
                mentions.setdefault(oq_id, []).append(common.rel(path))
    return mentions


def _blocked_by_entries() -> list[tuple[str, int, str, str]]:
    """Clause C: (path, lineno, story_id, oq_id) from story frontmatter.

    Matches `blocked_by:` at COLUMN ZERO only. Both frontmatter conventions in
    this repo put it there (```yaml fences and `---` delimiters); prose that
    talks ABOUT a blocked story writes it inline and backticked, indented under a
    `>` quote, so column zero is what separates the data from the discussion.
    A trailing `# …` comment is stripped — that is where an amended story records
    the ids it USED to carry, and reading those back would re-report every entry
    the moment it was fixed.
    """
    entries = []
    for path in sorted(common.MODULE_DOCS.glob("*/06-epics/*.md")):
        story = None
        for lineno, line in enumerate(common.read_text(path).splitlines(), start=1):
            id_match = re.match(r"^id:\s*(US-[A-Z]{3}-" + common.ID_DIGITS + r")", line)
            if id_match:
                story = id_match.group(1)
            blocked = re.match(r"^blocked_by:\s*(.*)$", line)
            if blocked:
                value = blocked.group(1).split("#", 1)[0]
                for oq_id in common.OQ_ID_RE.findall(value):
                    entries.append((common.rel(path), lineno, story or "?", oq_id))
    return entries


# ── Self-test (hard-won law 7) ──────────────────────────────────────────────
def self_test() -> list[str]:
    """Blind spots this gate must not have. Empty list = every clause bites."""
    blind = []
    # The DEF-096 shape, verbatim: a wrapped raise. Line-scoped reading misses it.
    wrapped = 'raise NotImplementedError(\n    "OQ-195: a refund against a credit balance"\n)'
    lines = wrapped.splitlines()
    window = "\n".join(lines[0:STUB_LOOKAHEAD_LINES])
    if "OQ-195" not in common.OQ_ID_RE.findall(window):
        blind.append(
            "BLIND (clause A): a wrapped `raise NotImplementedError(` with its OQ on the "
            "next line is not read — that is DEF-096's exact escape"
        )
    # A status cell is a STATE, not a story (DEF-104).
    if common.oq_is_closed("**OPEN** — reopening this would mean the CLOSED ruling no longer holds"):
        blind.append(
            "BLIND (clause D): an OPEN question whose prose contains the word CLOSED is "
            "read as closed — that is the live failure DEF-104 warns about"
        )
    if not common.oq_is_closed("**CLOSED(→BR-RAT-046)** — PO 2026-08-10"):
        blind.append("BLIND (clause D): an ordinary CLOSED cell is not read as closed")
    if common.oq_is_closed("**PARTIALLY CLOSED(→BR-TEN-069)** — the PLACEMENT is ruled"):
        blind.append(
            "FALSE NEGATIVE (clause D): PARTIALLY CLOSED is its own state — the half that "
            "was not answered still blocks"
        )
    # ── DEF-GOV-4384: the register writes a TICK in front of a closed state ──
    # This is the case that was live for eleven days. `oq_state()` skipped only
    # asterisks and whitespace, so a ✅-prefixed cell parsed to '' and
    # `oq_is_closed()` said False — switching clauses A and C off for 25 ruled
    # questions WITHOUT REPORTING THAT IT HAD. Removing the decoration class
    # from `common._OQ_STATE_RE` makes this line fire, which is its red proof.
    if not common.oq_is_closed("✅ **CLOSED 2026-09-06 — the default cap is 100**"):
        blind.append(
            "BLIND (clause D): a CLOSED cell written with the register's own ✅ prefix is "
            "not read as closed — 25 ruled questions read as OPEN to clauses A and C "
            "(DEF-GOV-4384)"
        )
    if common.oq_state("⏳ OPEN — raised 2026-08-25") != "OPEN":
        blind.append(
            "BLIND (clause D): an OPEN cell written with the register's ⏳ prefix does not "
            "parse to OPEN"
        )
    if common.oq_is_closed("⚠ **CLOSED IN PART 2026-08-27 — the axis is ruled, the rest is not**"):
        blind.append(
            "FALSE NEGATIVE (clause D): CLOSED IN PART is its own state — widening the "
            "decoration class must not widen what counts as CLOSED"
        )
    if common.oq_state("2026-09-06 — CLOSED, option (a)") == "CLOSED":
        blind.append(
            "TOO WIDE (clause D): a date-first cell was read as CLOSED. The decoration "
            "class skips symbols, never CONTENT — a cell nobody wrote to the convention "
            "must stay unparseable and stay reported"
        )
    # ── DEF-GOV-4385: a docstring quoting a raise is not a raise ─────────────
    # Deleting the tokenizer check in `_oq_citations_in_stubs` makes this fire.
    prose = 'x = """\n⚠ THIS RAISED `NotImplementedError("OQ-790")` UNTIL 2026-09-01.\n"""\n'
    spans = _python_string_spans(prose)
    if spans is None or not _inside_a_string(spans, 2, prose.splitlines()[1].index("NotImplementedError")):
        blind.append(
            "BLIND (clause A): a `NotImplementedError(` quoted inside a docstring is still "
            "charged as a live stub — 20 of 32 citations were prose (DEF-GOV-4385)"
        )
    live = 'raise NotImplementedError("OQ-195")\n'
    spans = _python_string_spans(live)
    if spans is None or _inside_a_string(spans, 1, live.index("NotImplementedError")):
        blind.append(
            "FALSE NEGATIVE (clause A): a one-line raise carries a string token ON ITS OWN "
            "LINE, so a line-scoped skip would throw away every real stub in the repository"
        )
    # A parked orphan that has since been registered must not stay parked.
    registry = common.oq_status_by_id()
    for oq_id in OQ_PARKED_ORPHANS:
        if oq_id in registry:
            blind.append(
                f"STALE PARK: {oq_id} now HAS a registry row, so its park in "
                "OQ_PARKED_ORPHANS expired — delete that entry in the diff that registered it"
            )
    return blind


def run() -> tuple[str, str]:
    blind = self_test()
    if blind:
        return "FAIL", (
            f"self-test BLIND: {blind[0]}. A guard that cannot be shown to bite is not "
            f"a guard (hard-won law 7) — {len(blind)} shape(s) failed."
        )

    registry = common.oq_status_by_id()
    if not registry:
        citations, _ = _oq_citations_in_stubs()
        if citations:
            return "FAIL", "codebase cites OQs but 12-governance/01-open-questions.md is missing/empty"
        return "PASS", "no OQ registry and no OQ-cited stubs"

    problems = []

    # ── clause D0: every `| OQ-` ROW must reach the parser ───────────────────
    # DEF-2804's own prevention column asked for this, and it is the half that
    # matters: widening the regex fixed today, but the failure it fixed was
    # SILENT, and a silent filter is indistinguishable from a register that
    # never had the row. 12 of 434 rows were dropped for days and clause D below
    # simply never saw those cells. This makes the next unreadable id form
    # report a NUMBER and a LIST instead of vanishing.
    unseen = common.oq_rows_the_parser_cannot_see()
    if unseen:
        problems.append(
            f"{len(unseen)} `| OQ-` row(s) in the register never reach "
            f"oq_status_by_id() — {common.summarize(unseen, 8)}. A row the parser "
            "cannot see is a question no gate can enforce, and nothing else reports "
            "it (DEF-2804)"
        )

    # ── clause D1: a QUESTION written up as a SECTION must have a ROW ────────
    # ⚠ **DEF-2820's OWN STATED DURABLE FIX, AND IT IS THE MIRROR OF D0.**
    # D0 asks "is there a row this parser cannot see?"; this asks "is there a
    # QUESTION with no row at all?", and until 2026-09-01 nothing asked it.
    # `OQ-1166` is why the difference matters: cited from a 🔒 rating-math file
    # and from `apps/billing/gather.py`, written up at length as a `## OQ-1166`
    # SECTION, and carrying NO `| OQ-1166 |` row — so clause B below had nothing
    # to resolve those citations against. With the old `OQ-\d{3}` pattern it did
    # not even fail: every citation read as **`OQ-116`**, a real and different
    # question that DOES have a row, so the clause resolved it and reported
    # nothing for two days, on a money path.
    #
    # RATCHET, NOT A CLIFF, per the 2026-08-27 ruling on why gates breach: "a
    # baseline that may fall and never rise is a ratchet; a baseline nobody can
    # reach is decoration." Baselined at what is actually there. The number is
    # not decoration either — it MOVED between the two measurements: 8 on
    # 2026-08-31 (DEF-2820's own count) and 9 on 2026-09-01, `OQ-1221` having
    # been written up as a section with no row in between, with nothing raising.
    orphan_sections = common.oq_sections_with_no_table_row()
    if len(orphan_sections) > OQ_SECTION_ORPHAN_BASELINE:
        problems.append(
            f"{len(orphan_sections)} question(s) are written up as a `## OQ-` SECTION "
            f"of the register with NO `| OQ- |` table row, against a baseline of "
            f"{OQ_SECTION_ORPHAN_BASELINE} that may fall and never rise — "
            f"{common.summarize(orphan_sections, 10)}. The table is the only form "
            "`oq_status_by_id()` reads, so a section-only question is a question no "
            "gate can enforce and no citation can resolve to (DEF-2820)"
        )

    # ── clause D: the registry's own states must parse ───────────────────────
    for oq_id, cell in registry.items():
        state = common.oq_state(cell)
        if state not in KNOWN_OQ_STATES and not any(state.startswith(k) for k in KNOWN_OQ_STATES):
            problems.append(
                f"registry {oq_id}: status does not begin with a state token "
                f"(reads {cell[:60]!r}) — a status field is a STATE, not a story"
            )

    # ── clause A: stubs cite a registered, open OQ ───────────────────────────
    citations, prose_skipped = _oq_citations_in_stubs()
    stale_seen = set()
    for path, lineno, oq_id in citations:
        where = f"{path}:{lineno}"
        cell = registry.get(oq_id)
        if cell is None:
            problems.append(f"{where}: cites {oq_id} which is not in the registry")
        elif common.oq_is_closed(cell):
            stale_seen.add((path, oq_id))
            if (path, oq_id) in STALE_STUB_PARK:
                continue
            problems.append(f"{where}: cites {oq_id} which is CLOSED — stale stub, implement the ruling")
    for key in STALE_STUB_PARK:
        if key not in stale_seen:
            problems.append(
                f"STALE PARK: {key[0]} no longer has a stub citing {key[1]} — the park "
                "expired, delete its STALE_STUB_PARK entry in the diff that fixed it"
            )

    # ── clause B: every OQ mentioned anywhere resolves to a row ──────────────
    mentions = _oq_mentions_everywhere()
    orphans = sorted(oq for oq in mentions if oq not in registry)
    for oq_id in orphans:
        if oq_id in OQ_PARKED_ORPHANS:
            continue
        where = ", ".join(sorted(mentions[oq_id])[:3])
        problems.append(
            f"{oq_id} is cited in {len(mentions[oq_id])} file(s) ({where}) and has NO "
            "registry row — an OQ minted in code that the next lane cannot see is how "
            "two lanes end up using one id for two questions (DEF-096)"
        )

    # ── clause C: no story is blocked by a question that closed ──────────────
    blocked_entries = _blocked_by_entries()
    for path, lineno, story, oq_id in blocked_entries:
        cell = registry.get(oq_id)
        if cell is None:
            problems.append(f"{path}:{lineno}: {story} blocked_by {oq_id}, which is not in the registry")
        elif common.oq_is_closed(cell):
            problems.append(
                f"{path}:{lineno}: {story} still blocked_by {oq_id}, which is CLOSED — "
                "clear the frontmatter and implement the ruling (the registry, the BR and "
                "the story move in ONE commit)"
            )

    if problems:
        return "FAIL", common.summarize(problems)
    parked = f", {len(OQ_PARKED_ORPHANS)} orphan(s) parked" if OQ_PARKED_ORPHANS else ""
    return "PASS", (
        f"{len(citations)} OQ-cited stub(s) all open ({prose_skipped} prose mention(s) of a "
        f"stub skipped — a docstring quoting a raise is not a guard, DEF-GOV-4385); "
        f"{len(mentions)} OQ id(s) referenced "
        f"across backend/frontend/docs all resolve{parked}; {len(blocked_entries)} "
        f"blocked_by entr(y/ies) all open (registry holds {len(registry)} OQs)"
    )


def main() -> int:
    """Run this gate from the command line.

    ⚠ ADDED 2026-08-25 (DEF-672). Sixteen gate modules defined `run()` and NO
    main block, so `python3 10-scripts/gates/<gate>.py` imported the module,
    defined a function and exited **0 with no output** — indistinguishable from
    a gate that ran and passed, to the eye and to `$?`. Two commit messages on
    this branch claim a G7 PASS obtained exactly that way.

    `run_gates.py` was never affected: it imports `run()` directly, which is why
    the real stack stayed honest while every direct invocation lied.
    """
    status, message = run()
    print(f"{status}: {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
