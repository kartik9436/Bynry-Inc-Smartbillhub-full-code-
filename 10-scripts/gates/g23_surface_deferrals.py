"""G23 — surface deferrals, ADDED UP per module.

Added 2026-08-15 by the DEF-112 lane, and the defect's own prevention column is
the specification, verbatim:

    "a story whose trailer says `E=deferred(no-frontend-half)` is not done, and
     nothing today distinguishes it from one that is. Every lane wrote its gap
     down honestly and the module still ended up unreachable, so the missing
     check is one that ADDS UP the deferrals per module and refuses to call a
     module complete while its surface is absent. **The counting was never done,
     by anyone or anything.**"

WHAT HAPPENED. `apps/ledger/close.py` and `apps/ledger/exports.py` shipped
complete, unit-tested, G7-guarded and correct, each carrying
`D=deferred(the S42 close endpoints are the API half — not built by this lane)
E=deferred(no-frontend-half)` in its own Lifecycle trailer. `reporting.py` said
the same for five screens. Every lane was honest. **2,400 unit tests passed
against a module a user could not open**, and the month-close journey booted a
real browser and went red at step 1 on the absence of anything to click.

G1–G22 all passed on it, because each asks about law, traceability, wiring or
output shape within ONE file, and none adds two honest notes together.

════════════════════════════════════════════════════════════════════════════
WHAT THIS GATE COUNTS
════════════════════════════════════════════════════════════════════════════
B12 §5's completion checklist gives every file's Lifecycle trailer a **D** row
(API) and an **E** row (Frontend). This walks every trailer in the codebase,
reads those two marks, and attributes them to the US-IDs in the file's Trace
`Story:` header. A story is then:

    API REACHED      some file citing it marks **D✔**
    SCREEN REACHED   some file citing it marks **E✔**
    UNREACHABLE      it has code, and NEITHER

An UNREACHABLE story is an engine nobody can run: the money math exists, the
tests pass, and there is no route and no screen. That is the DEF-112 shape, and
it is counted per module.

════════════════════════════════════════════════════════════════════════════
WHY THE BUDGET FILE IS AN EXACT COUNT AND NOT A CEILING
════════════════════════════════════════════════════════════════════════════
`surface_debt.txt` carries one line per module: the EXACT number of unreachable
stories and a sentence saying which they are and why. Exact, not "at most",
because a ceiling is a number nobody has to look at again — and "nobody looked"
is the entire defect. With equality:

  · a lane that ADDS a deferral must raise the number, which is the moment
    somebody reads the sentence beside it;
  · a lane that BUILDS a surface must lower it, so the file records the win and
    cannot quietly keep claiming debt that is paid off (the G16/G20 discipline:
    a park cannot outlive the condition that justified it);
  · a module with unreachable stories and NO line fails outright.

A module at zero needs no line, which keeps the file to the modules that owe
something.

Proven RED before trusted green (law 7) — see this file's self-test, which
replays the DEF-112 shape through the same parser the gate uses and asserts it
is counted.

⚠ G23 is an Eng-Lead-class addition and is merge-blocking from the moment it is
wired, so it is REPORTED for the daily PO batch and recorded in
12-governance/02-decision-log.md rather than treated as routine (the G17–G22
route).

Python 3.12 stdlib only. Safe to run from any cwd.
"""

import sys
import re
from pathlib import Path

import common

BUDGET = Path(__file__).resolve().parent / "surface_debt.txt"

#: The two checklist rows this gate reads. B12 §5: D = API, E = Frontend.
MARK_RE = re.compile(r"\b([DE])(✔|✖|=deferred\([^)]*\))")


def module_of(path: Path) -> str:
    """The module a file belongs to — `apps/<mod>/…` or `features/<mod>/…`.

    Backend and frontend halves of one module land under ONE name on purpose:
    the whole point is to compare a module's engines against its surface, and a
    split that counted `ledger` and `ledger-ui` separately would let each look
    complete while the pair was not.
    """
    parts = path.parts
    for anchor in ("apps", "features"):
        if anchor in parts:
            index = parts.index(anchor)
            if index + 1 < len(parts):
                return parts[index + 1]
    return "platform"


def surface_marks() -> dict[str, dict[str, set[str]]]:
    """{story: {"api": {marks}, "ui": {marks}, "modules": {names}}}.

    Reads the Trace `Story:` line for US-IDs and the Lifecycle `checklist:` line
    for the D and E marks. A file citing several stories contributes its marks to
    each of them, which is right: a story is reachable if ANY file that
    implements it serves a route or draws a screen.
    """
    stories: dict[str, dict[str, set[str]]] = {}
    for path, text in common.files_with_trace_header():
        block = common.lifecycle_block(text)
        if block is None:
            continue
        line = re.search(r"checklist:(.*)", block)
        if line is None:
            continue  # G3 owns the missing-checklist failure; this gate does not double-report
        marks = dict(MARK_RE.findall(line.group(1)))
        header = "\n".join(common.trace_header_lines(text))
        ids = set(common.US_ID_RE.findall(header))
        for story in ids:
            entry = stories.setdefault(story, {"api": set(), "ui": set(), "modules": set()})
            entry["modules"].add(module_of(path))
            if "D" in marks:
                entry["api"].add(marks["D"])
            if "E" in marks:
                entry["ui"].add(marks["E"])
    return stories


def unreachable_by_module(stories: dict[str, dict[str, set[str]]]) -> dict[str, list[str]]:
    """Stories with code and NEITHER an API half nor a frontend half."""
    found: dict[str, list[str]] = {}
    for story, entry in sorted(stories.items()):
        if "✔" in entry["api"] or "✔" in entry["ui"]:
            continue  # something reaches it
        if not entry["api"] and not entry["ui"]:
            continue  # no D/E marks at all — G3 reports the malformed checklist
        for module in entry["modules"]:
            found.setdefault(module, []).append(story)
    return found


def declared_budget() -> tuple[dict[str, int], list[str]]:
    """{module: exact count} from surface_debt.txt, plus any parse problems."""
    if not BUDGET.is_file():
        return {}, ["surface_debt.txt is missing — the count must exist, even at zero"]
    budget: dict[str, int] = {}
    problems: list[str] = []
    for lineno, raw in enumerate(common.read_text(BUDGET).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 2)
        if len(parts) < 3 or not parts[1].isdigit():
            problems.append(f"surface_debt.txt:{lineno}: expected `<module> <count> <reason>`")
            continue
        budget[parts[0]] = int(parts[1])
    return budget, problems


def self_test() -> list[str]:
    """Law 7 — the gate is shown to BITE on the shape it was written for.

    DEF-112 itself, replayed through the same comparison the gate runs: a module
    whose stories carry `D=deferred(...) E=deferred(...)` and nothing else must
    be counted as unreachable. A gate that could not be shown to fail on its own
    defect is not a guard.
    """
    blind = []
    ledger_shape = {
        "US-LED-015": {"api": {"=deferred(the S42 close endpoints are the API half)"},
                       "ui": {"=deferred(no-frontend-half)"}, "modules": {"ledger"}},
        "US-LED-016": {"api": {"=deferred(the S42/S43 endpoints are the API half)"},
                       "ui": {"=deferred(no-frontend-half)"}, "modules": {"ledger"}},
    }
    counted = unreachable_by_module(ledger_shape)
    if counted.get("ledger") != ["US-LED-015", "US-LED-016"]:
        blind.append("the DEF-112 shape (D=deferred + E=deferred) is not counted as unreachable")

    served = {
        "US-LED-015": {"api": {"✔"}, "ui": {"=deferred(no-frontend-half)"}, "modules": {"ledger"}},
    }
    if unreachable_by_module(served):
        blind.append("a story WITH an API half is still being counted as unreachable")
    return blind


def run() -> tuple[str, str]:
    stories = surface_marks()
    if not stories:
        return "SKIP", "no Lifecycle checklists cite a story yet — activates with the first one"

    blind = self_test()
    if blind:
        return "FAIL", (
            f"self-test BLIND: {blind[0]}. A guard that cannot be shown to bite is not a "
            f"guard (hard-won law 7) — {len(blind)} shape(s) failed."
        )

    actual = unreachable_by_module(stories)
    budget, problems = declared_budget()

    for module in sorted(actual):
        count = len(actual[module])
        if module not in budget:
            problems.append(
                f"{module}: {count} unreachable stor(ies) — {common.summarize(actual[module], 3)} "
                f"— and surface_debt.txt does not mention the module. An engine no route and no "
                f"screen reaches is DEF-112; declare it with the reason or build the surface."
            )
        elif budget[module] != count:
            direction = "MORE" if count > budget[module] else "FEWER"
            problems.append(
                f"{module}: surface_debt.txt declares {budget[module]} unreachable stor(ies) and "
                f"there are {count} — {direction} than declared "
                f"({common.summarize(actual[module], 3)}). The count is EXACT: raise it with a "
                f"reason, or lower it because a surface landed."
            )
    for module in sorted(set(budget) - set(actual)):
        if budget[module] != 0:
            problems.append(
                f"{module}: surface_debt.txt still claims {budget[module]} unreachable stor(ies) "
                f"and there are none. The debt is paid — delete the line so the file keeps "
                f"stating the truth."
            )

    if problems:
        return "FAIL", common.summarize(problems, 3)
    # ── DISTINCT vs MODULE-SLOTS (added 2026-08-16) ──────────────────────────
    # THE PER-MODULE COUNTS ARE UNCHANGED AND MUST BE: each is that module's
    # own admission of what a user cannot reach, and a story cited from five
    # modules genuinely is unreachable in all five — `assets` could not point at
    # `billing` and call its own line paid.
    #
    # But SUMMING those five gave a headline of "33 unreachable" over 29 real
    # stories, and the gap was invisible. US-BIL-028's snapshot alone was cited
    # from assets, billing, customers, metering and tenancy, so closing ONE
    # story dropped the headline by five and read like five stories of work
    # vanishing. Reporting both figures costs nothing and weakens nothing: the
    # equality check above is per-module and untouched, so a module still cannot
    # under-declare by a single story.
    slots = sum(len(v) for v in actual.values())
    distinct = len({story for found in actual.values() for story in found})
    shared = "" if distinct == slots else (
        f" — {slots} module-slot(s), because {slots - distinct} citation(s) are "
        f"one story owed by several modules"
    )
    return "PASS", (
        f"{len(stories)} stor(ies) counted; {distinct} DISTINCT unreachable across "
        f"{len(actual)} module(s){shared}; every module's count declared in surface_debt.txt"
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
