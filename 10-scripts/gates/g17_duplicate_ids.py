"""G17 — one ID, one definition. Added 2026-08-11 by Eng-Lead, from DEF-053.

THE DEFECT, IN ITS OWN WORDS
---------------------------
DEF-053: *"Two lanes minted OQ-117 for two different questions in the same hour,
both cited in shipped code — the third instance of this collision."* The bill-
document lane used OQ-117 for "is a bill that cannot print its TOTAL DUE a failed
render?" and the custom-fields lane used it for "how does a non-string
custom-field value become the string a bill prints?". Both were live in code at
the same time. It was the THIRD occurrence: the W5 ledger lane hit exactly this
with OQ-113 and OQ-114 and recorded it in `apps/billing/issue.py`'s trailer,
"where it is prose in one file rather than a check".

The registry is an append-only markdown table and the next free id is chosen by
READING the file, so two lanes working the same afternoon both read 116 as the
tail and both wrote 117. Nothing failed. Each collision was found by accident.

The damage is not cosmetic and DEF-053 spells it out: `common.oq_status_by_id()`
builds a dict keyed on the id, so **one of the two rows silently wins** and G8
can validate a `NotImplementedError("OQ-117")` stub against the WRONG question's
status — a stub can be declared honest against an OQ it has nothing to do with.
A reviewer following a stub to the registry lands on someone else's question.

WHY IT IS A GATE AND NOT A LINT
-------------------------------
DEF-053's prevention column: *"THE DURABLE HALF IS FOUR LINES IN A GATE THAT
ALREADY PARSES THIS FILE: common.oq_status_by_id() reads every row today, so
failing when the same OQ id appears twice is nearly free, and it would have gone
RED within minutes of the second lane's commit instead of being found by a
pipe-count sanity check. Worth pairing with the same assertion over BR-IDs
(DEF-052) and over screen IDs — all three are 'an identifier the whole repo
references is defined more than once', and the repo has now paid for it in two
vocabularies on the same day."*

So this gate is that pairing. EIGHT vocabularies, one rule: **an ID that the
whole repo references by ID must be DEFINED exactly once.** Each vocabulary
names its own definition site, because "defined" means something different in
each one and a gate that guessed would be noise:

  OQ-###          a row in 12-governance/01-open-questions.md
  DEF-###         a row in 12-governance/10-defect-log.csv
  US-<MOD>-###    `id:` in a story's YAML frontmatter (04-docs/05-modules/*/06-epics/*.md)
  BR-<MOD>-###    a row in a module's 02-business-rules.md — the CANONICAL file
  GT-##           a `## GT-n` section in 04-docs/02-decisions/05-golden-tests.md
  ADR-###         one file per ADR in 04-docs/04-adr/
  EP-<MOD>-##     one file per epic in 04-docs/05-modules/*/06-epics/
  S###            a row in 04-docs/01-spec/01-screen-inventory.md

WHAT THIS GATE DELIBERATELY DOES **NOT** CHECK, AND THE MEASUREMENT WHY
-----------------------------------------------------------------------
DEF-052 is a BR-ID defined twice in two DIFFERENT files: the canonical
`07-billing/02-business-rules.md` defines BR-BIL-030 as the locked bill instance
and `EP-BIL-02-invoice-gl.md:219` still defines the same ID as the custom-field
stamp alone. **That case is not checkable this way and the numbers say so.**
Measured across the repo on 2026-08-11, before this gate was written:

    436 BR-IDs are defined in BOTH an epic §2 table and a module rules file
    183 BR-IDs appear in more than one epic §2 table
     13 BR-IDs exist ONLY in an epic §2 table and in no rules file
      0 BR-IDs are defined twice inside the canonical rules files

An epic restating in its §2 table the rule it implements is how this repo is
BUILT, not a defect — so a cross-file BR duplicate check would fire on 619
legitimate rows on its first run. DEF-041's prevention column is explicit about
what that does: *"a widened gate that fires on 40 legitimately-later props
teaches people to add ALLOW entries, which is how a gate stops being a gate."*
So the BR check here is scoped to the ONE authoritative definition site, where it
is exact and where it is currently clean; DEF-052's cross-file case stays open
with its own row and its own named fix (an assertion in 02-trace_lint.py, which
already walks both file sets and can compare the STATEMENTS, not just the IDs).
Writing the measurement down is the point: the next agent should not have to
rediscover why the obvious wider check was refused.

Also not checked: TC-# and IS-## from CLAUDE.md's grammar. Both are scoped to
their parent document (TC-1 means "test case 1 of THIS story"), so repetition
across files is correct and a global uniqueness rule would be wrong.

PROVED RED BEFORE TRUSTED GREEN (hard-won law 7)
------------------------------------------------
All eight vocabularies are clean today — DEF-053 was closed by renumbering the
custom-fields lane's question to OQ-125 — so a green run proves nothing on its
own. Part 0 below replays a collision in EACH vocabulary against an IN-MEMORY
copy of the real corpus (nothing is written; the docs are opened read-only) and
requires the checker to report it. Fixture A1 is DEF-053 itself: a second OQ-117
row, the exact defect. A vocabulary whose fixture fails to bite FAILS the gate,
so this gate cannot rot into one that always passes.

ADDING THIS GATE IS A PROCESS EVENT. G1-G16 are the PO-ratified merge-blocking
set (2026-08-11, option A). G17 is an Eng-Lead addition from DEF-053 and is
merge-blocking from the moment it is wired; it is reported for the daily PO batch
and recorded in 12-governance/02-decision-log.md, not treated as routine.

Python 3.12 stdlib only. Safe to run from any cwd. Nothing here ever writes.
"""

import csv
import io
import re
from pathlib import Path

import common

# ── the corpus: every file that DEFINES one of the eight vocabularies ───────
OQ_REGISTRY = common.REPO_ROOT / "12-governance" / "01-open-questions.md"
DEFECT_LOG = common.REPO_ROOT / "12-governance" / "10-defect-log.csv"
GOLDEN_TESTS = common.REPO_ROOT / "04-docs" / "02-decisions" / "05-golden-tests.md"
SCREEN_INVENTORY = common.REPO_ROOT / "04-docs" / "01-spec" / "01-screen-inventory.md"
ADR_DIR = common.REPO_ROOT / "04-docs" / "04-adr"
MODULES = common.REPO_ROOT / "04-docs" / "05-modules"
CR_DIR = common.REPO_ROOT / "12-governance" / "change-requests"
CR_INDEX = common.REPO_ROOT / "12-governance" / "11-change-requests.md"

MAX_NAMED = 3  # collisions named in the one-line detail before it says "+N more"


def corpus() -> list[tuple[str, str]]:
    """[(repo-relative path, text)] for every definition site, read-only.

    Returned as data rather than read inside the checker so Part 0 can run the
    identical checker over a MUTATED copy without touching a byte on disk.
    """
    paths: list[Path] = [OQ_REGISTRY, DEFECT_LOG, GOLDEN_TESTS, SCREEN_INVENTORY]
    paths += sorted(ADR_DIR.glob("ADR-*.md"))
    paths += sorted(MODULES.glob("*/02-business-rules.md"))
    paths += sorted(MODULES.glob("*/06-epics/*.md"))
    paths += sorted(CR_DIR.glob("CR-*.md"))
    paths.append(CR_INDEX)
    return [(common.rel(p), common.read_text(p)) for p in paths if p.is_file()]


# ── one collector per vocabulary ────────────────────────────────────────────
# Each yields (id, "path:line") for every DEFINITION, never for a reference.


def _rows(path: str, text: str, pattern: re.Pattern) -> list[tuple[str, str]]:
    found = []
    for lineno, line in enumerate(text.splitlines(), 1):
        match = pattern.match(line.strip())
        if match:
            found.append((match.group(1), f"{path}:{lineno}"))
    return found


OQ_ROW = re.compile(r"^\|\s*(OQ-" + common.MOD_SEG + common.ID_DIGITS + r")\s*\|")
US_FRONTMATTER = re.compile(r"^id:\s*(US-[A-Z]{3}-" + common.ID_DIGITS + r")\s*$")
BR_ROW = re.compile(r"^\|\s*\**\s*(BR-[A-Z]{3}-" + common.ID_DIGITS + r")\s*\**\s*\|")
GT_SECTION = re.compile(r"^##\s+(GT-\d+)\b")
SCREEN_ROW = re.compile(r"^\|\s*(S\d{1,3})\s*\|")
ADR_FILE = re.compile(r"^(ADR-" + common.ID_DIGITS + r")")
EP_FILE = re.compile(r"^(EP-[A-Z]{3}-\d{2,5}(?!\d))")
#: ⚠ **THE FILENAME IS THE DEFINITION SITE FOR A CR, NOT THE INDEX ROW** — and
#: that is measured, not preferred. `11-change-requests.md` legitimately carries
#: TWO index rows for one CR when a CR is split (`CR-016` has one for itself and
#: one for its PART F), its index table changed shape partway down (the rows
#: from `CR-085` on carry two cells where the earlier ones carry three), and
#: `CR-071`'s whole text sits INSIDE the index region. A row-based collector
#: reports **4 duplicates on a clean tree** — a gate red from birth, which is
#: how a check earns a silencing comment instead of a fix. One file per CR has
#: been the rule since 2026-09-03, filenames are unambiguous, and this is how
#: `ADR` and `EP` are already collected here.
CR_FILE = re.compile(r"^(CR-\d{3,5}(?:-BRC\d{2})?)(?=-|\.md$)")
#: ⚠ **AND THE FILENAME ALONE LEAVES A HOLE BIG ENOUGH TO DRIVE THE WHOLE RULE
#: THROUGH — MEASURED, NOT FEARED.** One file per CR has been the rule since
#: 2026-09-03 and **eight CRs do not follow it**: `CR-077`…`CR-084` have an
#: index row in `11-change-requests.md` and no file on disk. So two branches
#: could each raise ninety, add only an index row, merge clean, and this gate
#: would stay GREEN over the exact collision it was added to refuse. The index
#: row is therefore a second definition site.
#: ⚠ **SCOPED TO `CR-090` AND UP, AND THE FLOOR IS LOAD-BEARING.** The index
#: legitimately carries two rows for one CR when a CR is split (`CR-016` has one
#: for itself and one for its PART F, and `018`, `051` and `062` are the same
#: shape), so an unscoped row collector reports **4 duplicates on a clean tree**
#: — a gate red from birth, which is how a check earns a silencing comment
#: instead of a fix. The branch-suffix rule starts at `CR-090`; below it, the
#: filename check and history are what apply.
CR_INDEX_ROW = re.compile(r"^\|\s*\**\s*(CR-(\d{3,5})(?:-BRC\d{2})?)\s*\**\s*\|")
CR_SUFFIX_RULE_STARTS_AT = 90


def collect(files: list[tuple[str, str]]) -> dict[str, list[tuple[str, str]]]:
    """{vocabulary: [(id, where)]} — every definition in the corpus."""
    found: dict[str, list[tuple[str, str]]] = {v: [] for v in VOCABULARIES}
    for path, text in files:
        name = path.rsplit("/", 1)[-1]
        if path == common.rel(OQ_REGISTRY):
            found["OQ-###"] += _rows(path, text, OQ_ROW)
        if path == common.rel(GOLDEN_TESTS):
            found["GT-##"] += _rows(path, text, GT_SECTION)
        if path == common.rel(SCREEN_INVENTORY):
            found["S###"] += _rows(path, text, SCREEN_ROW)
        if path == common.rel(DEFECT_LOG):
            # csv, not regex: the log's free-text columns contain embedded
            # newlines and pipes, and a line-based reader would invent rows.
            reader = csv.DictReader(io.StringIO(text))
            for row_no, row in enumerate(reader, 2):
                ident = (row.get("id") or "").strip()
                # ⚠ `\d{3,}` AND NOT `\d{3}` — DEF-1651. This read `\d{3}` from the
                # day it was written and the register passed DEF-999 on
                # 2026-08-27, so **66 of the log's 930 rows were invisible to
                # this check**: every id from `DEF-1000` on was silently not
                # collected, and duplicate-id detection — the one thing this
                # gate exists for — stopped covering the newest and most
                # contested block of ids. `10-scripts/file_defect.py` carries a
                # known allocation bug (DEF-1182), which is exactly the
                # condition a duplicate arises under.
                if re.fullmatch(r"DEF-(?:[A-Z]{3}-)?\d{3,}", ident):
                    found["DEF-###"].append((ident, f"{path}:row {row_no}"))
        if name == "02-business-rules.md":
            found["BR-<MOD>-###"] += _rows(path, text, BR_ROW)
        if "/06-epics/" in path:
            found["US-<MOD>-###"] += _rows(path, text, US_FRONTMATTER)
            match = EP_FILE.match(name)
            if match:
                found["EP-<MOD>-##"].append((match.group(1), path))
        if "/change-requests/" in path:
            match = CR_FILE.match(name)
            if match:
                found["CR-###"].append((match.group(1), path))
        if path == common.rel(CR_INDEX):
            for lineno, line in enumerate(text.splitlines(), 1):
                match = CR_INDEX_ROW.match(line.strip())
                if match and int(match.group(2)) >= CR_SUFFIX_RULE_STARTS_AT:
                    found["CR-### (index row)"].append(
                        (match.group(1), f"{path}:{lineno}")
                    )
        if "/04-adr/" in path:
            match = ADR_FILE.match(name)
            if match:
                found["ADR-###"].append((match.group(1), path))
    return found


#: Vocabulary -> the sentence a reader needs when its check goes red. Ordered
#: the way the failures are reported.
VOCABULARIES = {
    "OQ-###": "12-governance/01-open-questions.md rows (DEF-053: two lanes, one number)",
    "DEF-###": "12-governance/10-defect-log.csv rows",
    "US-<MOD>-###": "story frontmatter `id:` in 04-docs/05-modules/*/06-epics/",
    "BR-<MOD>-###": "rows of a module's CANONICAL 02-business-rules.md",
    "GT-##": "`## GT-n` sections of 04-docs/02-decisions/05-golden-tests.md",
    "ADR-###": "04-docs/04-adr/ADR-###-*.md filenames",
    "EP-<MOD>-##": "04-docs/05-modules/*/06-epics/EP-*.md filenames",
    "S###": "04-docs/01-spec/01-screen-inventory.md rows",
    "CR-###": "12-governance/change-requests/CR-*.md filenames (one file per CR since 2026-09-03)",
    "CR-### (index row)": (
        "12-governance/11-change-requests.md rows from CR-090 up — the second "
        "definition site, because 8 CRs (CR-077..084) have a row and no file"
    ),
}


#: Vocabularies where the RUNNING NUMBER is the unique thing, not the whole id.
#: `CLAUDE.md`, PO ruling 2026-09-03: a question and a defect carry their module
#: — `OQ-<MOD>-nnnn`, `DEF-<MOD>-nnnn` — with **"one running number across the
#: whole register (the register's maximum + 1, so ids stay unique)"**.
#: ⚠ **`CR-###` JOINED THIS TUPLE 2026-09-10, AND IT IS THE WHOLE REASON THE
#: BRANCH SUFFIX IS SAFE TO HAVE.** PO ruling of that day: a CR raised on a
#: branch is written `CR-<nnn>-<BRCnn>` so two branches never write the same
#: id. The cost of that, stated when it was ruled, is that `CR-090-BRC01` and
#: `CR-090-BRC02` are two DIFFERENT ids — they collide in no file, they merge
#: clean (one file per CR means two branches touch two different files, and the
#: index row is an append), and nothing goes red while two unrelated changes are
#: both called ninety. **The suffix is provenance; the NUMBER is the identity**,
#: because a number is what a person says out loud, writes in a commit subject
#: and cites from a business rule. So the number is what this checks.
NUMBERED_VOCABULARIES = ("DEF-###", "OQ-###", "CR-###", "CR-### (index row)")
_RUNNING_NUMBER = re.compile(r"^(?:DEF|OQ|CR)-(?:[A-Z]{3}-)?(\d{3,5})(?:-BRC\d{2})?$")


def number_collisions(files: list[tuple[str, str]]) -> list[str]:
    """One message per running NUMBER claimed by two different ids.

    ⚠ **WHY THIS IS A SECOND FUNCTION AND NOT A TIGHTER `collisions()`
    (`DEF-GOV-4405`).** `collisions()` keys on the whole id string, so
    `DEF-CUS-4396` and `DEF-INT-4396` are two different keys and it reports
    nothing — truthfully, of the question it asks. But the module segment is
    **not part of the number**: the PO's ruling makes the number the running,
    unique thing, and `10-scripts/allocate.py` exists precisely because two
    lanes computing "the register's maximum + 1" in different worlds get the
    same answer.
    **What a shared number costs is not a dangling citation, it is a resolving
    one.** Grep this repository for `4061` and you get `DEF-GOV-4061` (the
    base-is-the-tip check, cited from `CLAUDE.md` itself) and `DEF-WRK-4061` (a
    route constant carrying a tenant segment) — two real rows, one number, and
    nothing to tell a reader which one a bare `4061` meant. That is `OQ-119`'s
    failure, which this gate's own docstring calls the one that is worse than a
    dangling id.
    **Thirteen were already there when this was written** and none of them had
    ever been reported, because nothing had ever asked the question.
    """
    problems = []
    for vocab, definitions in collect(files).items():
        if vocab not in NUMBERED_VOCABULARIES:
            continue
        by_number: dict[str, set[str]] = {}
        for ident, _where in definitions:
            match = _RUNNING_NUMBER.match(ident)
            if match:
                by_number.setdefault(match.group(1), set()).add(ident)
        for number in sorted(k for k, v in by_number.items() if len(v) > 1):
            names = ", ".join(sorted(by_number[number]))
            # The trailing segment has a different NAME per vocabulary and the
            # message has to be true of the one it is reporting: a defect or a
            # question carries its MODULE, a change request carries the BRANCH
            # that raised it. Both are labels, neither is part of the number.
            segment = "branch suffix" if vocab.startswith("CR-") else "module segment"
            problems.append(
                f"{number} is claimed by {len(by_number[number])} different ids ({names}) — "
                f"the {segment} is not part of the number, and a bare citation of it "
                "resolves to two real rows"
            )
    return problems


def collisions(files: list[tuple[str, str]]) -> list[str]:
    """One message per ID defined more than once. Pure function of the corpus."""
    problems = []
    for vocab, definitions in collect(files).items():
        seen: dict[str, list[str]] = {}
        for ident, where in definitions:
            seen.setdefault(ident, []).append(where)
        for ident in sorted(k for k, v in seen.items() if len(v) > 1):
            problems.append(f"{ident} defined {len(seen[ident])}× ({', '.join(seen[ident])})")
    return problems


# ═══════════════════════════════════════════════════════════════════════════
# PART 0 — SELF-TEST. Hard-won law 7: prove the guard goes RED before trusting
# it green. Every vocabulary is clean today (DEF-053 was closed by renumbering
# the second question to OQ-125), so a green run demonstrates nothing by
# itself. Each fixture plants ONE collision in an in-memory copy of the real
# corpus and requires `collisions()` to name it. A fixture that fails to bite
# fails the gate — the same discipline 10-scripts/03-golden-verify.py Part 0
# applies to the frozen figures.
# ═══════════════════════════════════════════════════════════════════════════
#: (tag, vocabulary, why this fixture is the defect it replays)
FIXTURES = [
    ("A1", "OQ-###", "DEF-053 itself: a second row minting an OQ id that already exists"),
    ("A2", "DEF-###", "two lanes appending a defect row with the same DEF number"),
    ("A3", "US-<MOD>-###", "one story id in two epic files (trace_lint's check, now merge-blocking)"),
    ("A4", "BR-<MOD>-###", "a rule number reused inside the canonical rules file (DEF-052's shape)"),
    ("A5", "GT-##", "a golden-test number reused in the FROZEN B5 document"),
    ("A6", "ADR-###", "two architecture decisions filed under one number"),
    ("A7", "EP-<MOD>-##", "two epic files claiming one epic number"),
    ("A8", "S###", "a screen id listed twice in A1 — CLAUDE.md's 'never renumber' vocabulary"),
    ("A9", "CR-###", "two branches raising a change request under one number (PO ruling 2026-09-10)"),
    ("A10", "CR-### (index row)",
     "a branch that adds only an INDEX ROW and no file — 8 CRs (CR-077..084) are "
     "already shaped that way, so the filename check alone would stay green over it"),
]


def _duplicate_one(files: list[tuple[str, str]], vocab: str) -> tuple[list[tuple[str, str]], str]:
    """A copy of the corpus with the FIRST definition of `vocab` planted twice.

    Row/section/frontmatter vocabularies get their defining line appended to the
    file that already holds it; filename vocabularies get a second file bearing
    the same id. Returns (mutated corpus, the id that must now collide).
    """
    # ⚠ **THE INDEX-ROW FIXTURE PLANTS ITS OWN ROWS INSTEAD OF COPYING ONE, AND
    # THAT IS THE POINT.** There are ZERO `CR-090`+ index rows today — the rule
    # starts at ninety and no CR has been raised under it yet — so a fixture that
    # duplicates "the first definition" would find none, report the fixture stale,
    # and fail the gate from the day it was written. Worse, it would go on proving
    # nothing for as long as the register stayed empty above ninety, which is
    # exactly the "structurally incapable of failing" shape law 7 names. Planting
    # the rows makes the probe independent of whether anyone has used the rule yet.
    if vocab == "CR-### (index row)":
        probe = "CR-090-BRC01"
        row = f"| **{probe}** | RED-PROBE — not a real change request | RED-PROBE |"
        mutated = [
            (fp, (text.rstrip("\n") + "\n" + row + "\n" + row + "\n")
                 if fp == common.rel(CR_INDEX) else text)
            for fp, text in files
        ]
        return mutated, probe

    definitions = collect(files).get(vocab) or []
    if not definitions:
        return files, ""
    ident, where = definitions[0]
    path = where.rsplit(":", 1)[0] if ":" in where else where

    if vocab in ("ADR-###", "EP-<MOD>-##", "CR-###"):
        directory, _, name = path.rpartition("/")
        clone = f"{directory}/{name.replace('.md', '')}-RED-PROBE.md"
        return files + [(clone, "")], ident

    mutated = []
    for file_path, text in files:
        if file_path != path:
            mutated.append((file_path, text))
            continue
        if vocab == "DEF-###":
            # A CSV needs a whole row, not a line: re-emit the first row verbatim.
            rows = list(csv.DictReader(io.StringIO(text)))
            first = next(r for r in rows if (r.get("id") or "").strip() == ident)
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=list(first))
            writer.writerow(first)
            mutated.append((file_path, text.rstrip("\n") + "\n" + buf.getvalue()))
            continue
        source = next(
            line for line in text.splitlines()
            if line.strip().startswith(("| " + ident, "|" + ident, "## " + ident, "id: " + ident))
        )
        mutated.append((file_path, text.rstrip("\n") + "\n" + source + "\n"))
    return mutated, ident


def self_test(files: list[tuple[str, str]]) -> list[tuple[str, bool, str]]:
    results = []
    for tag, vocab, why in FIXTURES:
        mutated, ident = _duplicate_one(files, vocab)
        if not ident:
            results.append((tag, False, f"{vocab}: no definition found to duplicate — "
                                        "the fixture is stale, so it proves nothing"))
            continue
        found = [p for p in collisions(mutated) if p.startswith(ident + " ")]
        results.append((tag, bool(found),
                        f"{vocab} {ident}: " + (found[0] if found
                                                else f"NOT reported (expected FAIL) — {why}")))
    return results


def defect_log_shape_problems(text: str) -> list[str]:
    """Every record in the defect register must be exactly header-width.

    ADDED 2026-08-15 (DEF-122), and it is a DATA-LOSS guard rather than an ID
    guard — it lives here because G17 is the only gate that already parses this
    file on every run, and DEF-122's prevention column names exactly this check.

    WHAT IT PREVENTS, measured live and twice in ten minutes: a stray double
    quote inside the final `prevention` field ends that field's quoting early,
    the rest of the sentence splits on its own commas into surplus columns, and
    the record silently becomes 23 or 31 fields wide against a 14-field header.
    `csv.DictReader` tolerates that in silence (it bags the surplus under the
    key `None`), so every reader in the repo looks fine — but the moment a lane
    UPDATES the register with a `csv.DictWriter`, the writer refuses the ragged
    row with *"dict contains fields not in fieldnames: None"* and raises AFTER
    the earlier rows are already on disk. **The file is left holding 30 records
    and the other 87 are gone.** Two lanes lost work to it on 2026-08-15, one of
    them a whole row that had never been read by anyone else.

    A ragged record is therefore not a formatting nit: it is a live grenade with
    the pin out, and it is invisible to every read path. Checked on every gate
    run so the next stray quote fails on the commit that adds it.
    """
    problems = []
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return ["defect log is empty"]
    width = len(header)
    for row_no, row in enumerate(reader, start=2):
        if not row:
            continue
        if len(row) != width:
            ident = (row[0] if row else "?").strip()
            problems.append(
                f"{ident} (record {row_no}) has {len(row)} fields against a {width}-field "
                "header — almost always a stray double-quote inside `prevention` ending "
                "the field early. A csv.DictWriter update TRUNCATES the file at this row "
                "and loses everything after it (DEF-122)"
            )
    return problems


# ═══════════════════════════════════════════════════════════════════════════
# THE ACCEPTED SET — DEF-490, 2026-08-21.
#
# ⚠ THIS GATE FOUND DEF-490 AND NOBODY READ IT, BECAUSE IT WAS ALREADY RED.
# Five rating rules each named two different rules, and `collisions()` printed
# every one of them, correctly, on the commit that introduced them. The report
# was invisible: g17 had been red for weeks on four duplicated OQ rows and one
# tenancy rule, so its exit code carried NO INFORMATION — red before a change,
# red after it, and a lane asking "did I break anything" sees no difference.
# The merging lane compared the FAILURE COUNT (10 before, 10 after) and the
# first names in a truncated list, and concluded "unchanged, pre-existing".
#
# A GATE THAT IS PERMANENTLY RED IS A GATE THAT IS OFF. So the known duplicates
# are baselined the way g31's class ceiling and g38's untracked count are: they
# are still reported, and anything BEYOND them fails.
#
# ⚠ ADD NOTHING HERE TO MAKE A BUILD GREEN. A new duplicate is a renumbering,
# not a baseline entry. Removing one — by renumbering the later definition and
# recording the move in its registry row — must also remove it from this set,
# or the ratchet never tightens.
ACCEPTED_DUPLICATES = {
    # Four questions minted twice by two lanes in one hour (DEF-053's shape),
    # each pair already answered under BOTH numbers. Renumbering them now would
    # break references in shipped code; they are carried, visibly, until the
    # questions close.
    "OQ-253",
    "OQ-254",
    "OQ-255",
    "OQ-268",
    # One tenancy rule defined twice in its own canonical file. Not this lane's
    # module and not this lane's call to merge two versions of someone else's
    # law — carried, and it is the next thing this set should lose.
    "BR-TEN-078",
}


#: ═══════════════════════════════════════════════════════════════════════════
#: THE CARRIED NUMBER SHARES — `DEF-GOV-4405`, 2026-09-07.
#:
#: Thirteen running numbers were each claimed by two ids (4025 by three) on the
#: day `number_collisions()` was written, and **not one had ever been reported**,
#: because until then nothing compared NUMBERS — only whole id strings. They are
#: carried for the same reason `ACCEPTED_DUPLICATES` above carries its five: a
#: gate that is permanently red is a gate that is off, and renumbering thirteen
#: rows of a register six lanes append to is the mass shared-file rewrite law 11
#: exists to prevent.
#:
#: ⚠ ADD NOTHING HERE TO MAKE A BUILD GREEN. A number claimed twice is fixed by
#: renumbering the LATER id against `10-scripts/allocate.py` and writing the move
#: into its own row — this lane did exactly that three times today (4395, 4396,
#: 4398 → 4402, 4403, 4404) rather than adding them here. Removing an entry when
#: it stops colliding is required: the check below fails on a stale entry, so the
#: ratchet can only ever tighten.
#:
#: ⚠ **SEVENTEEN MORE CARRIED ON 2026-10-02, BY COORDINATOR DECISION — AND THE
#: WARNING ABOVE STILL STANDS FOR EVERY NUMBER AFTER THEM.** Between 2026-09-25
#: and 2026-09-30, seventeen running numbers (6554–6558, 6621, 6698, 6729, 6750,
#: 6759, 6760, 6762, 6763, 6766, 6913, 7643, 8836) were each taken by two lanes
#: under different module segments — e.g. `DEF-PAY-6554` and `DEF-SHL-6554` —
#: and clause 3 was red over them, unread, for days. They are CARRIED rather
#: than renumbered for the reason the original thirteen were: the module prefix
#: already tells the two rows apart, and renumbering would move ~50 citations
#: across code, registers and tests that other lanes are editing right now —
#: the mass shared-file rewrite law 11 forbids, CLAUDE.md's "nothing is
#: renumbered". What changed since is that `allocate.py` / `file_defect.py`
#: ask the REMOTE for the next number, so a fresh share is now caught at push
#: time; an 18th share still goes red here, and is fixed by renumbering the
#: later id, never by adding it to this set. Decision log, 2026-10-02.
CARRIED_NUMBER_SHARES = {
    "4003", "4004", "4016", "4019", "4025", "4032", "4033",
    "4036", "4061", "4134", "4216", "4224", "4256",
    # 2026-10-02 — the seventeen above, carried by coordinator decision.
    "6554", "6555", "6556", "6557", "6558", "6621", "6698", "6729",
    "6750", "6759", "6760", "6762", "6763", "6766", "6913", "7643", "8836",
}


def _number(problem: str) -> str:
    """The running number a `number_collisions()` message is about."""
    return problem.split(" ", 1)[0]


def _ident(problem: str) -> str:
    """The id a `collisions()` message is about — its first token."""
    return problem.split(" ", 1)[0]


def run() -> tuple[str, str]:
    """Every clause, every run.

    ⚠ **THIS RETURNED AT ITS FIRST FAILING CLAUSE UNTIL 2026-09-25, AND THAT
    HID A WHOLE PROBLEM BEHIND A NEWER ONE (`DEF-GOV-6795`, lane IDFIX, `C5`).** Three ids each
    named two different defects that morning — `DEF-CUS-6724/6725/6726`, filed
    two minutes apart by two lanes that could not see each other's unpushed rows
    — and the duplicate-ID clause fired and returned. **Fourteen running numbers
    were meanwhile claimed by two ids apiece, eight of them minted the same day,
    and the gate said not one word about them.** A lane repairing the three and
    re-running would have met a red it had never been shown, on a subject it was
    never told about, and would reasonably have read it as damage it had just
    caused.

    That is hard-won law 7's *reporting zero over a scope it silently excludes*,
    one layer up: the gate was not lying, it simply stopped counting. **A clause
    that never ran is not a clause that passed**, and an early return makes the
    two indistinguishable to a reader.

    So every clause now runs and every failing one is reported, each on its own
    line, and the count of failing clauses is stated. **The two clauses that
    genuinely invalidate the rest are still stops** — a ragged register means
    the rows were parsed wrong, and a blind self-test means the collector is
    broken, so any id verdict taken from either is a number nobody should read.
    When one of those fires, the gate says IN WORDS which clauses it did not
    reach, because a declared blind spot with no number beside it is
    indistinguishable from an empty one.
    """
    files = corpus()
    if not files:
        return "SKIP", "no ID registry found — nothing to check for duplicates yet"

    # ── STOPS. These two do not merely fail; they make every clause below
    # unreadable, so they return — and they NAME what was not reached.
    NOT_REACHED = (
        " NOT CHECKED this run (this clause invalidates them): duplicate id "
        "definitions, the accepted-duplicates ratchet, running-number shares, "
        "and the carried-shares ratchet."
    )

    # Shape before ids: a ragged register is a data-loss bug whether or not its
    # ids happen to be unique, and it must not be reported as an id problem.
    for path, text in files:
        if path == common.rel(DEFECT_LOG):
            ragged = defect_log_shape_problems(text)
            if ragged:
                return "FAIL", (
                    f"{len(ragged)} malformed record(s) in the defect register: "
                    + common.summarize(ragged, MAX_NAMED)
                    + " — 4 clause(s)" + NOT_REACHED
                )

    blind = [(tag, detail) for tag, ok, detail in self_test(files) if not ok]
    if blind:
        return "FAIL", (
            f"self-test BLIND: {len(blind)} of {len(FIXTURES)} fixture(s) did not bite — "
            f"{blind[0][0]} {blind[0][1]}. A guard that cannot be shown to fail is not a "
            "guard (law 7); fix the collector, never delete the fixture."
            + " 4 clause(s)" + NOT_REACHED
        )

    # ── THE FOUR ID CLAUSES. All four are computed, always, and every failing
    # one is reported. None of them can invalidate another.
    failures: list[str] = []

    problems = collisions(files)
    fresh = [p for p in problems if _ident(p) not in ACCEPTED_DUPLICATES]
    if fresh:
        failures.append(
            f"[1/4 duplicate id definitions] {len(fresh)} duplicate ID definition(s) BEYOND "
            "the accepted set: " + common.summarize(fresh, MAX_NAMED)
            + " — renumber the LATER one with `python3 10-scripts/renumber_defect.py "
            "--id <old> --to <new> --expect 2 --match <text in the row you mean>` and move "
            "its citations with it (DEF-053)"
        )

    stale = sorted(ACCEPTED_DUPLICATES - {_ident(p) for p in problems})
    if stale:
        failures.append(
            f"[2/4 accepted-duplicates ratchet] {len(stale)} id(s) are baselined as duplicates "
            f"and are NOT duplicates any more ({', '.join(stale)}) — delete them from "
            "ACCEPTED_DUPLICATES to hold the gain. A ratchet that never tightens is a number "
            "nobody reads (DEF-490)."
        )

    # ── the RUNNING NUMBER, not the id string (DEF-GOV-4405) ────────────
    shares = number_collisions(files)
    fresh_shares = [p for p in shares if _number(p) not in CARRIED_NUMBER_SHARES]
    if fresh_shares:
        failures.append(
            f"[3/4 running-number shares] {len(fresh_shares)} running number(s) claimed by more "
            "than one id, BEYOND the carried set: " + common.summarize(fresh_shares, MAX_NAMED)
            + " — take a fresh number with `python3 10-scripts/allocate.py defect` and record "
            "the move in the row itself. The module segment is not part of the number "
            "(CLAUDE.md, PO 2026-09-03)."
        )

    stale_shares = sorted(CARRIED_NUMBER_SHARES - {_number(p) for p in shares})
    if stale_shares:
        failures.append(
            f"[4/4 carried-shares ratchet] {len(stale_shares)} number(s) are carried as shared "
            f"and are NOT shared any more ({', '.join(stale_shares)}) — delete them from "
            "CARRIED_NUMBER_SHARES to hold the gain. A ratchet that never tightens is a number "
            "nobody reads (DEF-490)."
        )

    if failures:
        return "FAIL", (
            f"{len(failures)} of 4 id clause(s) failing, ALL of them reported (an early return "
            "hid 14 number shares behind 3 duplicate ids on 2026-09-25): "
            + " || ".join(failures)
        )

    counts = {v: len(d) for v, d in collect(files).items()}
    total = sum(counts.values())
    carried = f"; {len(problems)} carried duplicate(s): {', '.join(sorted(_ident(p) for p in problems))}" if problems else ""
    return "PASS", (
        f"{total} ID(s) across {len(VOCABULARIES)} vocabularies, each defined exactly once "
        f"outside the accepted set ({', '.join(f'{n} {v}' for v, n in counts.items())}); "
        f"self-test: {len(FIXTURES)}/{len(FIXTURES)} vocabularies bite{carried}; "
        f"{len(shares)} running number(s) claimed twice, all carried (DEF-GOV-4405); "
        "all 4 id clauses ran"
    )


if __name__ == "__main__":
    status, detail = run()
    print(f"{status}: {detail}")
    print()
    print("--- Part 0: self-test (law 7 — prove the guard goes RED before trusting it green) ---")
    for tag, ok, text in self_test(corpus()):
        print(f"  {'BITES' if ok else 'BLIND'} {tag}  {text}")
    raise SystemExit(0 if status != "FAIL" else 1)
