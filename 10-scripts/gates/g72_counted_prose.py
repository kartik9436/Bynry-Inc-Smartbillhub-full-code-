#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-3320 (2026-09-02) — the sample estate has EIGHTEEN blocks and
#          five sentences in `apps/tenancy/sample_data.py` still said SEVENTEEN,
#          including the one the sign-up screen narrates from. `SAMPLE_MODULES`
#          gained `rating:seed_sample_enrolments` at position 6 (CR-062 addendum
#          J2, the Municipal discount) and the prose did not move with it.
#          It survived because EVERY test asserts against `len(SAMPLE_MODULES)`,
#          so the suite was green and stayed green — hard-won law 1 exactly:
#          a comment claiming a guarantee is not the guarantee.
# Rules:   CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
#          guarantee) · hard-won law 9/10 (the repo is what the next agent
#          reads) · CLAUDE.md law 7 (prove a guard RED first) · B14 rule 32
#          (a screen's copy is what a clerk reads, so a count on it is a claim)
# Tests:   `selftest()` in this file — five lines it must read as a claim of
#          seventeen and five it must read as no claim at all, run by `run()`
#          before any finding is reported.
# Impacts: 06-backend/apps/tenancy/sample_data.py · apps/tenancy/api.py ·
#          apps/tenancy/selectors.py · 07-frontend/src/features/tenancy/
#          SignupWizard.tsx · 07-frontend/src/api/client.ts · endpoints.ts
# ───────────────────────────────────────────────────────
"""G72 — A COUNT WRITTEN IN PROSE MUST BE THE COUNT THE CODE ACTUALLY HOLDS.

**MOST OF THE FAILURE THIS EXISTS FOR IS NOT A WRONG TEST — IT IS A RIGHT ONE.**
The tests that touch the seeding estate largely assert against
`len(SAMPLE_MODULES)`. That is the correct way to write them, and it is exactly
why sentences went on saying SEVENTEEN with a green suite behind them: a derived
assertion can never disagree with the thing it derives from.

⚠ **`DEF-3320`'s ROW SAYS *"every"* TEST DERIVES AND THAT IS NOT TRUE — NINE DID
NOT, AND THEY WERE RED.** Eight literals in
`06-backend/tests/test_cr064_seventeen_steps.py` (two of them POSITIONS, which an
INSERTION at position 6 broke rather than an append) and one in
`07-frontend/src/features/tenancy/provisioningSteps.test.ts`, which is the one
check in the repository that parses `SAMPLE_MODULES` out of Python and compares
it with the screen's hand-typed list — and which did its job. All nine derive
now. **That correction does not remove the need for this gate**: not one of them
reads a SENTENCE, and eleven sentences across six files were wrong.

So the gap is not in the tests. It is that **nothing in this repository reads
prose for truth**, which is r11 step 0's own warning turned into a defect, and
it is the same shape as three other things this repo has already been bitten by:

  * `CLAUDE.md`'s services line, wrong THREE times — six, then ten, then ten
    again while the seed carried eleven;
  * `B14`'s rule count, wrong three times — twenty, twenty-nine, thirty-one;
  * `G64`'s golden numbers, where `33/33` was quoted as engine proof for weeks.

**WHAT IS CHECKED.** For each registered COUNTED COLLECTION: read its length
from the source with `ast` (never by importing — a gate that imports Django is a
gate that does not run), then scan every registered prose file for the count
PHRASES that claim it, and require each claimed number to equal that length.
Numbers may be written as digits or as English words; both are read.

⚠ **A VERBATIM QUOTE IS NOT A CLAIM, AND THIS IS THE ONE PLACE THE GATE MUST NOT
BITE.** The Product Owner said *"can you show all 17 step - -list down all 17
steps and show 1 by 1 when they finish"*, and CR-064 records that sentence in
six places. **Those are the requester's words and law 9/10 requires them
verbatim** — rewriting one to keep a gate green would falsify the record to
protect a check, which is the wrong way round. each entry's `exempt` tuple
holds the fragments that mark a line as somebody else's words, and a matching
line is skipped with no exemption count kept, because it is not debt.

⚠ **WHAT IT CANNOT SEE, SAID PLAINLY (hard-won law 1 applied to this file).**
It reads the PHRASES it is given. A sentence that states the count some other
way — "one row for each of the steps below", a number spelled inside a longer
compound — is invisible to it, and so is any file not on the list. It is a
tripwire on the sentences that have actually gone wrong, not a proof that every
count in the repository is true. When a new count sentence is written, ADD ITS
PHRASE HERE; that is the maintenance this gate costs and it is the whole cost.

⚠ **AND THE FIRST DRAFT OF THIS GATE FAILED THE ONE TEST A GATE MUST PASS — ITS
OUTPUT COULD NOT TELL A PASS FROM A FAIL.** `\b<number>\s+steps?\b` reported
**45** findings on a tree with **eleven** real ones: "the refund's four steps",
"seven steps green, step 8 stopped", "SET-06 step 2", "RAT-03 step 4",
"CR-049 step 5d". That is `DEF-182`'s lesson — *a check whose output cannot
distinguish pass from fail is worse than no check, because it is trusted* — and
it was caught by running the gate before trusting it, which is law 7. Two
narrowings fixed it and both are load-bearing:

  1. **`MIN_CLAIM`** — a generic `<n> steps` phrase is only read as a claim when
     `n >= 10`. Every real claim about this estate is a teen; every false
     positive above was a small ordinary number. A count that legitimately falls
     below ten needs an ANCHORED phrase instead, not a lower threshold.
  2. **`(?<![\\w-])`** before the number — so `CR-049 step 5d` and `SET-06 step 2`
     are not read as "49 steps" and "6 steps". A digit hanging off an identifier
     is part of the identifier.
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: English number words this gate can read, both directions. Stops at thirty
#: deliberately: past that a count is written as digits everywhere in this repo,
#: and a longer table would be vocabulary nobody uses pretending to be coverage.
WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "twenty-one": 21,
    "twenty-two": 22,
    "twenty-three": 23,
    "twenty-four": 24,
    "twenty-five": 25,
    "twenty-six": 26,
    "twenty-seven": 27,
    "twenty-eight": 28,
    "twenty-nine": 29,
    "thirty": 30,
}

#: One alternation matching a number in either spelling. Longest-first so that
#: `twenty-seven` is not read as `twenty`. The lookbehind refuses a number that
#: is hanging off an identifier — `CR-049`, `SET-06`, `RAT-03` — because there
#: the digits are part of a name and not a count of anything.
_NUMBER = r"(?<![\w-])(" + "|".join(sorted(WORDS, key=len, reverse=True)) + r"|\d{1,3})"

#: A GENERIC phrase (`<n> steps`, `<n> blocks`) is only read as a claim when the
#: number is at least this big. See the docstring: every false positive the first
#: draft produced was an ordinary small number, and every real claim about a
#: counted collection in this repo is in the teens or above. An ANCHORED phrase —
#: one that names its subject — carries no threshold and is checked at any size.
MIN_CLAIM = 10


def _read_number(token: str) -> int | None:
    """`"eighteen"` and `"18"` both become `18`; anything else becomes `None`."""
    lowered = token.strip().lower()
    if lowered.isdigit():
        return int(lowered)
    return WORDS.get(lowered)


@dataclass(frozen=True)
class Counted:
    """One collection whose length is claimed in prose somewhere."""

    label: str
    #: The file holding the collection, and the module-level name to measure.
    source: str
    symbol: str
    #: The prose files whose count sentences are checked.
    prose: tuple[str, ...]
    #: GENERIC phrases — `<n> steps`, `<n> blocks`. They do not name their
    #: subject, so a number below `MIN_CLAIM` in one of them is ordinary English
    #: about something else and is ignored. One capture group, the number.
    generic: tuple[str, ...]
    #: ANCHORED phrases — the wording names the collection, so any number in one
    #: is a claim about it whatever its size. One capture group, the number.
    anchored: tuple[str, ...] = field(default=())
    #: Lines carrying one of these are somebody else's words, quoted verbatim,
    #: and are never a claim of ours. See the docstring.
    exempt: tuple[str, ...] = field(default=())


REGISTRY: tuple[Counted, ...] = (
    Counted(
        label="the sample-data seeding estate",
        source="06-backend/apps/tenancy/sample_data.py",
        symbol="SAMPLE_MODULES",
        prose=(
            "06-backend/apps/tenancy/sample_data.py",
            "06-backend/apps/tenancy/api.py",
            "06-backend/apps/tenancy/selectors.py",
            "07-frontend/src/features/tenancy/SignupWizard.tsx",
            "07-frontend/src/api/client.ts",
            "07-frontend/src/api/endpoints.ts",
        ),
        generic=(
            # "the SEVENTEEN steps", "all seventeen steps", "17 steps"
            rf"{_NUMBER}\s+steps?\b",
            # ⚠ `<n> blocks` IS DELIBERATELY NOT HERE. It was, and it produced
            # three findings that are all legitimate: *"0 of 17 blocks failed"*
            # (a dated measurement of one real incident), *"ten blocks landed
            # and the eleventh failed"* (a hypothetical in a docstring) and
            # *"41 s on this stack for the full ten blocks (CR-017 profile,
            # 2026-08-19)"* (a dated profile). A past measurement is a RECORD
            # and correcting it would be falsifying it — the same reason the
            # change register leaves superseded paragraphs standing. The word
            # `block` is how this repo talks about the seam generally, and the
            # word `step` is how it talks about the CATALOGUE, so `step` is the
            # one that carries claims.
        ),
        anchored=(
            rf"catalogue holds all\s+{_NUMBER}\b",
            rf"SAMPLE_MODULES`?\s+stays\s+{_NUMBER}\b",
            rf"THE LENGTH IS ALWAYS\s+{_NUMBER}\b",
            rf"All\s+{_NUMBER},\s+always\b",
            rf"no blocks and\s+{_NUMBER}\b",
            rf"[Oo]ne row of the\s+{_NUMBER}\b",
            rf"WHICH\s+{_NUMBER},\s+and in which order\b",
            rf"CR-064 · THE\s+{_NUMBER}\b",
            rf"[Tt]he\s+{_NUMBER},\s+in creation order\b",
        ),
        exempt=(
            # PO verbatim, CR-064, 2026-09-02 — quoted in six places and not
            # ours to correct. Law 9/10: the requester's words, unedited.
            "can you show all 17 step",
            "list down all 17 steps",
            "17 steps and show 1 by 1",
            # PO verbatim, DEF-3500, 2026-09-03 — the same sentence quoted in
            # three places in `SignupWizard.tsx`. The PO counted 18 because the
            # plant walked 18 that day; it walks 21 now, and editing the number
            # inside their quotation marks would make the record say something
            # they did not say. Every DESCRIPTIVE "eighteen" around these quotes
            # was corrected to twenty-one in the same commit — an exemption is
            # for somebody else's words, never for our own prose.
            "does not complete all 18 steps on screen",
            "want to complete all 18 steps on this screen itself",
        ),
    ),
    Counted(
        label="the platform utility service catalogue",
        source="06-backend/apps/tenancy/services.py",
        symbol="SERVICE_DEFAULT_UOMS",
        prose=(
            "06-backend/apps/tenancy/services.py",
            "07-frontend/src/features/tenancy/SignupWizard.tsx",
        ),
        generic=(),
        anchored=(
            rf"{_NUMBER}\s+utility services\b",
            rf"for all\s+{_NUMBER}\s+services\b",
        ),
    ),
)


def _collection_length(source: Path, symbol: str) -> int:
    """The number of elements in a module-level tuple/list literal.

    Read with `ast` and never by importing: a gate must run with nothing
    installed and nothing configured, and importing `apps.tenancy.sample_data`
    would need a settings module, a database URL and a Django app registry.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == symbol:
                if isinstance(value, (ast.Tuple, ast.List)):
                    return len(value.elts)
                if isinstance(value, ast.Dict):
                    return len(value.keys)
                raise SystemExit(
                    f"G72: {symbol} in {source} is not a literal tuple, list or "
                    "dict, so its length cannot be read without importing it. "
                    "Either make it a literal or take it out of the registry."
                )
    raise SystemExit(f"G72: {symbol} not found in {source}")


def findings() -> tuple[list[str], int]:
    """Every stale count claim, and how many claims were read to find them.

    Split out of `main()` so `run()` can call it, so `--report` can print it,
    and so `selftest()` can exercise the matcher without touching the tree.
    """
    failures: list[str] = []
    checked = 0

    for entry in REGISTRY:
        source = ROOT / entry.source
        if not source.exists():
            failures.append(f"{entry.label}: source {entry.source} is missing")
            continue
        truth = _collection_length(source, entry.symbol)

        for relative in entry.prose:
            path = ROOT / relative
            if not path.exists():
                failures.append(f"{entry.label}: prose file {relative} is missing")
                continue
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                for claimed, token in claims_in(line, entry):
                    checked += 1
                    if claimed != truth:
                        finding = (
                            f"{relative}:{lineno} claims {token!r} "
                            f"where {entry.symbol} holds {truth} "
                            f"({entry.label}) — {line.strip()[:96]}"
                        )
                        # Two phrases can match one sentence; report the SENTENCE
                        # once. A gate that double-counts inflates its own finding
                        # count, which is the shape DEF-2377 spent a commit
                        # correcting in a different register.
                        if finding not in failures:
                            failures.append(finding)

    return failures, checked


def claims_in(line: str, entry: Counted) -> list[tuple[int, str]]:
    """The count claims one line makes about one collection.

    Empty for a line carrying somebody else's verbatim words, and empty for a
    generic phrase whose number is below `MIN_CLAIM` — see the module docstring
    for why both of those exemptions are load-bearing rather than convenient.
    """
    if any(fragment in line for fragment in entry.exempt):
        return []
    found: list[tuple[int, str]] = []
    compiled = [(re.compile(p, re.IGNORECASE), MIN_CLAIM) for p in entry.generic] + [
        (re.compile(p, re.IGNORECASE), 0) for p in entry.anchored
    ]
    for pattern, floor in compiled:
        for match in pattern.finditer(line):
            claimed = _read_number(match.group(1))
            if claimed is None or claimed < floor:
                continue
            found.append((claimed, match.group(1)))
    return found


#: The gate's own proof that it bites — five lines it MUST read as a claim of
#: seventeen, and five it must read as no claim at all. The second half is the
#: half that matters: the first draft of this gate reported 45 findings where
#: eleven were real, and every false positive it produced is in this list
#: (DEF-182 — a check whose output cannot distinguish pass from fail is worse
#: than no check, because it is trusted).
_SELFTEST_ESTATE = REGISTRY[0]
_MUST_BITE: tuple[str, ...] = (
    '"""The SEVENTEEN steps, in creation order, BEFORE anything has run.',
    "#: block that HAS run; the catalogue holds all seventeen; the difference is",
    "⚠ **THE LENGTH IS ALWAYS SEVENTEEN AND THAT IS THE POINT.** It is the",
    "All seventeen, always, in creation order, each carrying what the run",
    "* CR-064 task A1 — the seventeen, in creation order, WITH NO OUTCOME.",
)
_MUST_NOT_BITE: tuple[str, ...] = (
    # ordinary small numbers about other things
    "# and drives its own services (B1 / BR-TEN-013). The refund's four steps are",
    "*   3. **Exactly one step is Working**, and it is the one after the last the",
    "# seven steps green, step 8 stopped on an unset DOCUMENT_STORAGE_BUCKET,",
    # digits hanging off an identifier
    "/** SET-06 step 2 — one row of the dual-pane premises picker (BR-MET-074). */",
    # the Product Owner's own words, quoted verbatim
    "//          17 steps and show 1 by 1 when they finish - if step breaks",
)


def selftest() -> bool:
    """Prove the matcher separates a claim from ordinary prose, both ways."""
    for line in _MUST_BITE:
        claims = claims_in(line, _SELFTEST_ESTATE)
        if not claims or claims[0][0] != 17:
            return False
    for line in _MUST_NOT_BITE:
        if claims_in(line, _SELFTEST_ESTATE):
            return False
    return True


def run() -> tuple[str, str]:
    if not (ROOT / REGISTRY[0].source).exists():
        return "SKIP", f"{REGISTRY[0].source} is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not bite: it must read five real count "
            "sentences as claims of seventeen and must read five ordinary lines — "
            "'the refund's four steps', 'SET-06 step 2', the Product Owner's own "
            "quoted words — as no claim at all. A check that cannot distinguish "
            "pass from fail is worse than no check, because it is trusted (DEF-182)."
        )

    failures, checked = findings()
    if failures:
        shown = "; ".join(failures[:4])
        return "FAIL", (
            f"{len(failures)} stale count claim(s) in prose. A count written in a "
            f"sentence is a CLAIM and nothing else in this repository reads prose "
            f"for truth (hard-won law 1). Correct the sentence, or — if it is "
            f"somebody's verbatim words — add the fragment to that entry's "
            f"`exempt` tuple with the reason. {shown}"
        )

    return "PASS", (
        f"{checked} count claim(s) agree with the {len(REGISTRY)} registered "
        f"collection(s). Self-test: five real claims bite and five ordinary lines "
        f"do not. ⚠ IT READS THE PHRASES IT IS GIVEN — a count stated some other "
        f"way, or in a file not on the list, is invisible to it."
    )


def main() -> int:
    if "--report" in sys.argv:
        failures, checked = findings()
        for line in failures:
            print(line)
        print(f"{checked} claim(s) read, {len(failures)} stale")
        return 0
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
