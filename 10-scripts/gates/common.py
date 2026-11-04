"""Shared helpers for the merge-blocking gate suite (B12 Addendum r2, gates G1-G12).

The "codebase" the gates scan is defined by B12 r2: backend app code under
06-backend/apps/ plus frontend code under 07-frontend/src/. Docs-side ID
integrity (duplicates, dangling refs between docs) is trace_lint's job
(10-scripts/02-trace_lint.py); the gates check CODE against the docs.

Entry point: run_gates.py in this directory. Python 3.12 stdlib only.
All paths resolve relative to this file, so the suite runs from any cwd.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "06-backend"
BACKEND_APPS = BACKEND_DIR / "apps"
FRONTEND_SRC = REPO_ROOT / "07-frontend" / "src"
MODULE_DOCS = REPO_ROOT / "04-docs" / "05-modules"
OQ_REGISTRY = REPO_ROOT / "12-governance" / "01-open-questions.md"

# The B8 traceability markers (box-drawing characters, exactly as B8 specifies).
TRACE_MARK = "── Trace ──"
LIFECYCLE_MARK = "── Lifecycle ──"

# ── THE ID GRAMMAR READS FIVE DIGITS ────────────────────────────────────────
# PO ruling 2026-08-31, verbatim: *"next question make them 5 digital"* — said in
# reply to being told our own tooling could only read three-digit question
# numbers and that we had passed 999 some time ago. `DEF-2804`.
#
# ⚠ THESE ARE `SEARCH` PATTERNS, WHICH IS WHY THREE DIGITS WAS WORSE THAN A
# LIMIT — IT WAS A SILENT MISREAD. `re.compile(r"OQ-\d{3}").findall("OQ-1190")`
# returns `['OQ-119']`, and `OQ-119` is a different, real question. A stub
# blocked on one question was recorded against another, and nothing raised.
# `BR-[A-Z]{3}-\d{3}` had the same fault waiting on a money path: `BR-RAT` stood
# at 962 the day this was written, 37 ids from reading `BR-RAT-1000` as
# `BR-RAT-100`.
#
# ⚠ `(?!\d)` IS THE HALF THAT STOPS THIS RECURRING ONE ORDER OF MAGNITUDE UP.
# Without it, `\d{3,6}` reads `OQ-12345667` as `OQ-123456` — the same
# misattribution, six digits later. With it, a run of digits too long to be an
# id matches NOTHING, which is the honest answer.
#
# The lower bound stays THREE: every id ever minted in this repo is at least
# three digits, so `\d{3,6}` still refuses `OQ-1` as the typo it is.
#
# ⚠ NOTHING IS RENUMBERED AND NOTHING IS ZERO-PADDED. `OQ-291` is `OQ-291`, not
# `OQ-00291`. This governs what the tooling can READ and how much room the
# numbering has — not how existing ids are spelled.
ID_DIGITS = r"\d{3,6}(?!\d)"

#: ⚠ AN ID MAY CARRY ITS MODULE — `OQ-INT-1470`, `DEF-WRK-3542` — SINCE 2026-09-03.
#: PO, verbatim: *"going forward OQs: register max - add prefix OQ-Wrk-nnnn to it so
#: that we know which module it is; Same thing with defect - add prefix going forward
#: Def-Wrk-nnnn"*. Applied as an OPTIONAL segment of three capitals between the family
#: and ONE running number shared by the whole register (decision log 2026-09-03), so
#: every id minted before that day, and every governance row that belongs to no module,
#: still parses. Until this segment existed here, 27 register rows were invisible to
#: every gate (DEF-3552): g08 named them, nothing else did.
MOD_SEG = r"(?:[A-Z]{3}-)?"

US_ID_RE = re.compile(r"US-[A-Z]{3}-" + ID_DIGITS)
BR_ID_RE = re.compile(r"BR-[A-Z]{3}-" + ID_DIGITS)
OQ_ID_RE = re.compile(r"OQ-" + MOD_SEG + ID_DIGITS)


def id_number(ident: str) -> int:
    """The running number of an id, whatever family or module segment it carries —
    `OQ-1489`, `OQ-WRK-1490` and `DEF-WRK-3542` give 1489, 1490, 3542. Use this instead
    of `split("-")[1]`, which returns the module code and raises on int()."""
    return int(ident.rsplit("-", 1)[1])


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def rel(path: Path) -> str:
    """Repo-relative path string, for human-readable violation messages."""
    return str(path.relative_to(REPO_ROOT))


def backend_code_files() -> list[Path]:
    if not BACKEND_APPS.is_dir():
        return []
    return sorted(BACKEND_APPS.rglob("*.py"))


def frontend_code_files() -> list[Path]:
    if not FRONTEND_SRC.is_dir():
        return []
    return sorted(p for p in FRONTEND_SRC.rglob("*") if p.suffix in (".ts", ".tsx"))


def code_files() -> list[Path]:
    """Every file in the B12-defined codebase."""
    return backend_code_files() + frontend_code_files()


def files_with_trace_header() -> list[tuple[Path, str]]:
    """(path, text) for every codebase file carrying a `── Trace ──` header."""
    found = []
    for path in code_files():
        text = read_text(path)
        if TRACE_MARK in text:
            found.append((path, text))
    return found


def trace_header_lines(text: str) -> list[str]:
    """The comment lines of the Trace header block (between marker and closing rule).

    The block ends at the first line whose comment content is only ─ characters,
    or at the first non-comment line — whichever comes first.
    """
    lines = []
    in_block = False
    for line in text.splitlines():
        if not in_block:
            if TRACE_MARK in line:
                in_block = True
            continue
        stripped = line.strip().lstrip("#/ ").strip()
        is_comment = line.strip().startswith(("#", "//", "*"))
        if not is_comment:
            break
        if stripped and set(stripped) <= {"─"}:
            break  # closing rule line
        lines.append(line)
    return lines


def lifecycle_block(text: str) -> str | None:
    """Everything from the `── Lifecycle ──` marker to end of file, or None."""
    idx = text.find(LIFECYCLE_MARK)
    if idx == -1:
        return None
    return text[idx:]


def defined_story_ids() -> set[str]:
    """US-IDs defined in story frontmatter (same regex as 02-trace_lint.py)."""
    ids: set[str] = set()
    for path in MODULE_DOCS.glob("*/06-epics/*.md"):
        ids |= set(re.findall(r"^id: (US-[A-Z]{3}-" + ID_DIGITS + ")", read_text(path), re.M))
    return ids


def defined_br_ids() -> set[str]:
    """BR-IDs defined in each module's 02-business-rules.md."""
    ids: set[str] = set()
    for path in MODULE_DOCS.glob("*/02-business-rules.md"):
        ids |= set(BR_ID_RE.findall(read_text(path)))
    return ids


_OQ_ROW_ID_RE = re.compile(r"OQ-" + MOD_SEG + r"\d{3,6}")


def oq_status_by_id() -> dict[str, str]:
    """OQ-ID -> status cell text from the registry table (last cell of each row)."""
    statuses: dict[str, str] = {}
    if not OQ_REGISTRY.is_file():
        return statuses
    for line in read_text(OQ_REGISTRY).splitlines():
        if not line.startswith("| OQ-"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and _OQ_ROW_ID_RE.fullmatch(cells[0]):
            statuses[cells[0]] = cells[-1]
    return statuses


def oq_sections_with_no_table_row() -> list[str]:
    """Questions the register WRITES UP as a `## OQ-####` heading and never puts
    in the TABLE — the only form `oq_status_by_id()` can read.

    ⚠ **THIS IS THE MIRROR OF `oq_rows_the_parser_cannot_see()` AND IT IS THE
    HALF THAT WAS MISSING (`DEF-2820`, 2026-08-31).** That function asks *"is
    there a row this parser cannot see?"*; this one asks *"is there a QUESTION
    with no row at all?"*, and nothing asked it. `OQ-1166` is why: it is cited
    from `apps/rating/pricing/stages/apply_charges.py` — a 🔒 rating-math file —
    and from `apps/billing/gather.py`, it has a long `## OQ-1166` write-up in the
    register, and it has **no `| OQ-1166 |` row**. G8's clause B therefore had
    nothing to resolve the citation against, and with the old three-digit
    pattern it did not even notice: `OQ-\d{3}` read every citation as
    **`OQ-116`**, a real and different question that DOES have a row, so the
    clause resolved it and reported nothing at all for two days.

    **A gate clause that reads only the TABLE, over a register that also uses
    SECTIONS, cannot see this class of gap** — that sentence is DEF-2820's own
    stated durable fix, and this function is it. Measured 2026-08-31 the register
    held 26 sections with 8 orphans; measured again 2026-09-01 it held 27 with
    **9**, so the set GREW by one (`OQ-1221`) in a day with nothing raising —
    which is the argument for a ratchet rather than a note.

    Returns the ids in the order the register writes them up, so the failure
    message names them and a lane can go and add the rows.
    """
    if not OQ_REGISTRY.is_file():
        return []
    text = read_text(OQ_REGISTRY)
    # ⚠ `MOD_SEG` ADDED 2026-09-30 (gate triage T6, DEF-GOV-8533). Both patterns read only the
    # bare `OQ-nnnn` form, so every module-tagged write-up (`## OQ-CUS-12350`,
    # the form ids have carried since 2026-09-03) was invisible here: G106 then
    # reported 13 of them as "cited and never issued" while the register holds
    # each as a section, and G8's orphan clause never counted them at all —
    # law 7's fifth shape, a scope silently excluded. Same family as DEF-3552.
    section_re = re.compile(r"^#{1,6}\s+(OQ-" + MOD_SEG + ID_DIGITS + r")")
    row_re = re.compile(r"^\|\s*(OQ-" + MOD_SEG + ID_DIGITS + r")")
    sections: list[str] = []
    rows: set[str] = set()
    for line in text.splitlines():
        found = section_re.match(line)
        if found:
            sections.append(found.group(1))
        in_table = row_re.match(line)
        if in_table:
            rows.add(in_table.group(1))
    return [one for one in dict.fromkeys(sections) if one not in rows]


def oq_rows_the_parser_cannot_see() -> list[str]:
    """Rows the registry HAS that `oq_status_by_id()` does not return.

    WHY A COUNT CHECK AND NOT JUST A WIDER REGEX (DEF-2804's own prevention).
    The three-digit `fullmatch` above dropped **12 of 434** `| OQ-` rows — every
    four-digit question — and said nothing whatsoever. `oq_is_closed()` then
    answered `False` for questions that were CLOSED, and G8 clause D never
    inspected those cells at all. The failure was invisible because a filter that
    drops a row and a register that never had it are the same shape.

    Widening the regex fixes today. **This function is what stops it happening
    again**: the file's own `| OQ-` rows are compared against what the parser
    returns, so the next id form the parser cannot read reports a NUMBER and a
    LIST instead of vanishing. G8 fails on a non-empty return.

    Returns the raw first-cell text of each unparsed row, so the message can show
    what it actually choked on.
    """
    if not OQ_REGISTRY.is_file():
        return []
    parsed = set(oq_status_by_id())
    unseen = []
    for line in read_text(OQ_REGISTRY).splitlines():
        if not line.startswith("| OQ-"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or cells[0] in parsed:
            continue
        unseen.append(cells[0])
    return unseen


#: The leading STATE TOKEN of a status cell — the bit before any prose.
#: A status cell in this registry reads `**CLOSED(→BR-RAT-046)** — PO said …`,
#: so the state is the first run of letters/spaces, optionally bold-wrapped.
#:
#: ⚠ **THE DECORATION CLASS IS `[^A-Za-z0-9]*` AND `DEF-GOV-4384` IS WHY.** It
#: used to be `\**\s*` — asterisks and whitespace and nothing else — and this
#: register has written a TICK in front of a closed state since 2026-08-24
#: (`OQ-351`). `✅ **CLOSED 2026-09-06 — the default cap is 100**` therefore
#: matched nothing, `oq_state()` returned `''`, and **`oq_is_closed()` answered
#: False for 25 questions the PO had actually ruled.** G8's clause D did report
#: the unreadable cell — but as one of 35 formatting lines inside a gate that
#: has been red for weeks, while clauses A and C (a stub citing a CLOSED
#: question; a story still `blocked_by` one) were switched off for every one of
#: those 25 without saying so. A parser that returns `''` instead of raising
#: turns every caller into a false negative at once, which is hard-won law 7's
#: *reporting zero over a scope it silently excludes*, one layer down.
#:
#: DIGITS ARE DELIBERATELY **NOT** SKIPPED. Widening this to `[^A-Za-z]*` would
#: read `2026-09-06 — CLOSED, option (a)` as the state `CLOSED`, which is a
#: guess about a cell nobody wrote to this convention. A date-first cell stays
#: unparseable and stays REPORTED, which is the answer this file wants: skip
#: DECORATION, never skip CONTENT.
_OQ_STATE_RE = re.compile(r"^[^A-Za-z0-9]*([A-Za-z][A-Za-z ]*)")


def oq_state(status_cell: str | None) -> str:
    """The STATE of an OQ status cell, uppercased — `''` when unparseable.

    WHY THIS EXISTS AND WHY A SUBSTRING TEST IS NOT ALLOWED (DEF-104):
    every consumer used to ask `"CLOSED" in status`, and a status cell is a
    free-text column. A previous session wrote NARRATIVE PROSE into one and G8
    failed a LIVE question because the word "CLOSED" appeared inside a sentence
    describing what closing it would mean. The registry today is clean — every
    one of its 202 cells begins with a state token — but the trap is one careless
    edit away, and `OQ-216`'s cell already carries a trailing sentence that
    happens not to contain the word.

    **A status field is a STATE, not a story.** This reads the leading token and
    nothing else, so prose after it can say anything at all. `PARTIALLY CLOSED`
    is deliberately its OWN state and does NOT count as closed — a question half
    answered still blocks the half that was not. Neither does `CLOSED IN PART`
    nor `CLOSED AS ASKED`: both name a half that is still with the PO.

    ⚠ **AND THE OTHER HALF, `DEF-GOV-4384`: A CELL THIS CANNOT READ IS WORSE
    THAN A CELL THAT LIES.** The sentence above used to end "the registry today
    is clean — every one of its 202 cells begins with a state token". It was
    true when written and it was a comment claiming a guarantee (law 1): the
    register grew past 500 rows, adopted a ✅ in front of the state, and 35
    cells stopped parsing. This returns `''` for an unreadable cell, so every
    consumer's answer becomes "not closed" rather than "I could not tell" —
    which is why the decoration class above is deliberately generous and why
    G8's clause D reports what still will not parse.
    """
    match = _OQ_STATE_RE.match(status_cell or "")
    return match.group(1).strip().upper() if match else ""


def oq_is_closed(status_cell: str | None) -> bool:
    """True only when the state token IS `CLOSED` — never a substring match."""
    return oq_state(status_cell) == "CLOSED"


def summarize(items: list[str], limit: int = 5) -> str:
    """First `limit` items joined for a one-line detail, with an honest count."""
    shown = "; ".join(items[:limit])
    extra = len(items) - limit
    return shown + (f" (+{extra} more)" if extra > 0 else "")


def interpreter_with(*modules: str) -> tuple[str | None, list[str]]:
    """The first interpreter on this machine that can import every named module.

    Returns `(interpreter, tried)` — the interpreter, and the candidate list in
    the order it was searched, so a gate that finds nothing can say WHAT IT
    LOOKED FOR instead of shrugging.

    ⚠ **`sys.executable` IS THE WRONG QUESTION, AND THIS REPO HAS NOW PAID FOR
    THAT ANSWER FOUR TIMES.** `DEF-GOV-4441` (G5, the tenant-isolation gate,
    SKIPPED over 264 runnable tests), `G120` days later (announced that the
    application would not start, over a branch that boots), `DEF-GOV-6691` /
    `DEF-GOV-6698` (five gates at once, because the first two repairs widened
    the list to SYSTEM interpreters and still never looked in the one place a
    Python project installs its dependencies), and `DEF-GOV-6781` — G4, the
    gate that guards the ❄️ FROZEN B5 billing figures, which is the worst of
    the four because it does not skip: bare `python3` HAS pytest and has no
    Django, so the money gate reported **FAIL over 1,180 import errors** while
    the golden suite underneath it was green.

    **THIS FUNCTION EXISTS BECAUSE THE KNOWLEDGE WAS COPIED RATHER THAN
    SHARED.** `DEF-GOV-6698` closed with four open items and (c) was this one,
    verbatim: *"the candidate list belongs in gates/common.py as ONE helper — a
    paragraph in two files is the shape that produced this"*. `g05_isolation.py`
    and `g120_the_application_starts.py` still hold their own literal copies;
    folding them into this helper is the remaining half of that item and is
    deliberately NOT done here, because both files are live under another lane
    (law 11).

    ⚠ The virtualenv is an EXPLICIT PATH and not a `VIRTUAL_ENV` read: a gate
    must find it whether or not the caller activated anything. Measured on this
    machine 2026-09-25 — `06-backend/.venv/bin/python` has pytest 9.1.1 and
    Django 5.2.17; bare `python3` has pytest and no Django.
    """
    import os  # local: common.py is imported by every gate
    import subprocess
    import sys

    tried: list[str] = []
    # ⚠ **AN EXPLICIT OVERRIDE COMES FIRST, AND IT IS THE SAME ONE
    # `10-scripts/11-smoke-stack.sh` ALREADY HONOURS** (`DEF-GOV-7813`). That
    # script's `resolve_python()` tries `${PYTHON:-}` before anything else, so an
    # operator who has already told the smoke stack which interpreter to use has
    # told the gates too. One name, two tools, no third convention —
    # `SBH_GATE_PYTHON` is offered as the gate-only spelling for a machine where
    # `PYTHON` means something else.
    candidates = [os.environ.get("SBH_GATE_PYTHON", ""), os.environ.get("PYTHON", "")]
    candidates += [str(v) for v in _venv_pythons() if v.is_file()]
    candidates += [sys.executable, "python3"] + [
        f"python3.{minor}" for minor in range(14, 9, -1)
    ]
    probe = "import " + ", ".join(modules) if modules else "pass"
    for candidate in candidates:
        if not candidate or candidate in tried:
            continue
        tried.append(candidate)
        try:
            result = subprocess.run(
                [candidate, "-c", probe], capture_output=True, text=True, check=False
            )
        except (FileNotFoundError, OSError):
            # An interpreter this machine does not have is not a failure; the
            # candidate list is a search, not an expectation.
            continue
        if result.returncode == 0:
            return candidate, tried
    return None, tried


def _venv_pythons() -> list[Path]:
    """Every virtualenv interpreter this checkout can legitimately reach.

    Two of them, and the SECOND is the one a lane in this repo actually needs.

    1. `<this checkout>/06-backend/.venv/bin/python` — the ordinary case.
    2. **The MAIN worktree's** `06-backend/.venv/bin/python`, found through
       `git rev-parse --git-common-dir`. CLAUDE.md law 12 tells every lane to
       work in a private `git worktree`, `.venv/` is gitignored, and
       `git worktree add` therefore produces a checkout with **no virtualenv in
       it at all**. A helper that looks only at its own tree finds nothing in
       exactly the place the process tells lanes to stand — which is this
       repo's own "reporting zero over a scope it silently excludes" (law 7).
       Measured 2026-09-25: from a fresh worktree, candidate 1 does not exist
       and candidate 2 has pytest 9.1.1 and Django 5.2.17.

    Order matters: the checkout's own venv wins, because a lane that built one
    deliberately means to use it.
    """
    import subprocess

    out = [REPO_ROOT / "06-backend" / ".venv" / "bin" / "python"]
    try:
        common_dir = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, check=False, cwd=REPO_ROOT,
        )
    except (FileNotFoundError, OSError):
        return out
    if common_dir.returncode != 0:
        return out
    path = Path(common_dir.stdout.strip())
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    main_tree = path.parent  # `<main checkout>/.git` -> `<main checkout>`
    candidate = main_tree / "06-backend" / ".venv" / "bin" / "python"
    if candidate not in out:
        out.append(candidate)

    # ⚠ **AND THE VIRTUALENV IS NOT ALWAYS IN THE CHECKOUT — `DEF-GOV-7813`,
    # 2026-09-28, THE FIFTH TIME THIS ONE LESSON HAS BEEN PAID FOR.** Every
    # repair so far widened the search by asking *where would a Python project
    # put its venv?* and answering `<checkout>/06-backend/.venv`. On THIS
    # machine there is no such directory at all: the interpreter with pytest
    # 9.1.1 and Django 5.2.17 is `/root/.venvs/sbh312/bin/python`, which is
    # what every running backend in every sibling worktree uses and what
    # `11-smoke-stack.sh` is handed by hand.
    #
    # The cost was SIX GATES SKIPPING AT ONCE, measured in the census of
    # 2026-09-28 — `G4`, `G5`, `G49`, `G68`, `G87`, `G120`. **`G5` is the
    # tenant-isolation suite for HARD RULE 1**, so the product's first
    # guarantee had never been verified on this machine, and a `SKIP` reads
    # like *not applicable* rather than *the most important check in the repo
    # has never run here*. Law 7's fifth shape in its politest disguise.
    #
    # So the search now includes the conventional HOME for virtualenvs as well
    # as the conventional place inside a project. Both are guesses; the point
    # is that each is PROBED (`interpreter_with` runs the import) and a wrong
    # guess costs nothing, while a missing one costs six gates.
    for root in (Path.home() / ".venvs", Path("/root/.venvs"), Path("/opt/venvs")):
        try:
            entries = sorted(root.iterdir())
        except (OSError, PermissionError):
            continue
        for entry in entries:
            candidate = entry / "bin" / "python"
            if candidate.is_file() and candidate not in out:
                out.append(candidate)
    return out


def frontend_node_modules(*packages: str) -> tuple[Path | None, list[str]]:
    """The first `07-frontend/node_modules` this checkout can reach that holds
    every named package. Returns `(node_modules, tried)` — `tried` in search
    order, so a gate that finds nothing can say WHERE IT LOOKED.

    ⚠ **THE FRONT-END TWIN OF `_venv_pythons()` ABOVE, FOR THE SAME REASON
    (`DEF-GOV-5918`).** `node_modules/` is gitignored, so `git worktree add`
    produces a checkout with no install in it, and CLAUDE.md law 12 tells every
    lane to stand in exactly such a worktree. `G98` looked only at its own tree
    and SKIPped there; 107 lint errors built up behind that SKIP, read by
    nobody, until a lane happened to symlink an install in.

    Search order, own tree first because a lane that ran `npm ci` meant it:
      1. `$SBH_GATE_NODE_MODULES` — an explicit override, the gate-only
         spelling in the style of `SBH_GATE_PYTHON`;
      2. `<this checkout>/07-frontend/node_modules`;
      3. **the MAIN worktree's** `07-frontend/node_modules`, found through
         `git rev-parse --git-common-dir` — the mechanism `_venv_pythons()`
         already uses, reused rather than reinvented.

    A candidate counts only if `<candidate>/<package>/package.json` exists for
    every package named: a directory that exists but lacks the tool is the
    "found an install, linted nothing" false pass this helper exists to avoid.
    """
    import os
    import subprocess

    candidates: list[Path] = []
    override = os.environ.get("SBH_GATE_NODE_MODULES", "")
    if override:
        candidates.append(Path(override))
    candidates.append(REPO_ROOT / "07-frontend" / "node_modules")
    try:
        common_dir = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, check=False, cwd=REPO_ROOT,
        )
    except (FileNotFoundError, OSError):
        common_dir = None
    if common_dir is not None and common_dir.returncode == 0:
        path = Path(common_dir.stdout.strip())
        if not path.is_absolute():
            path = (REPO_ROOT / path).resolve()
        candidates.append(path.parent / "07-frontend" / "node_modules")

    tried: list[str] = []
    for candidate in candidates:
        if str(candidate) in tried:
            continue
        tried.append(str(candidate))
        if all((candidate / pkg / "package.json").is_file() for pkg in packages):
            return candidate, tried
    return None, tried


class LinkedFrontendInstall:
    """`with LinkedFrontendInstall("vitest") as link:` — make
    `07-frontend/node_modules` EXIST for the duration of a gate that shells a
    Node tool, borrowing the install `frontend_node_modules()` finds when this
    checkout has none. On exit the link is removed — only if it is still OUR
    symlink — so a lane's own later `npm ci` never meets it.

    ⚠ **WHY A LINK AND NOT `NODE_PATH` (`DEF-GOV-9126`).** `G98` borrows through
    `NODE_PATH`, which works for eslint 8's CommonJS plugin loading. A tool that
    loads its config as ESM — vitest's `vitest.config.ts`, vite's
    `vite.config.ts` — does not: Node's ESM resolver ignores `NODE_PATH` and
    only walks up from the importing file looking for a `node_modules`
    directory. So the directory has to be there.

    Attributes after `__enter__`:
      * `ok`       — True when `07-frontend/node_modules` now holds every package;
      * `borrowed` — the install linked in, or None when this checkout's own was used;
      * `tried`    — where it looked, for a SKIP that says so;
      * `problem`  — why it could not link, when `ok` is False;
      * `note`     — a phrase for a PASS detail naming the borrowed install, or "".

    It creates the link only when NOTHING is at that path (not even a dangling
    link), so it can never shadow or replace a real install.
    """

    def __init__(self, *packages: str) -> None:
        self.packages = packages
        self.target = REPO_ROOT / "07-frontend" / "node_modules"
        self.ok = False
        self.borrowed: Path | None = None
        self.tried: list[str] = []
        self.problem = ""
        self.note = ""
        self._made = False

    def __enter__(self) -> "LinkedFrontendInstall":
        found, self.tried = frontend_node_modules(*self.packages)
        if found is None:
            self.problem = "no install holding " + ", ".join(self.packages) + " was found"
            return self
        if found == self.target:
            self.ok = True
            return self
        if self.target.exists() or self.target.is_symlink():
            self.problem = (
                f"{self.target} exists but lacks {', '.join(self.packages)}, so the "
                f"install at {found} cannot be linked over it"
            )
            return self
        try:
            self.target.symlink_to(found, target_is_directory=True)
        except OSError as exc:
            self.problem = f"linking {found} into this checkout failed ({exc})"
            return self
        self._made = True
        self.ok = True
        self.borrowed = found
        self.note = (
            f" — this checkout has no install, so {found} was linked in for the run "
            f"and removed afterwards"
        )
        return self

    def __exit__(self, *exc: object) -> None:
        if self._made and self.target.is_symlink():
            self.target.unlink()
