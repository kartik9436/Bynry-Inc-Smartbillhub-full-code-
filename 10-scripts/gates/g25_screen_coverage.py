"""G25 — every screen in the inventory has an owning story. Added 2026-08-16.

THE DEFECT, TWICE, IN ITS OWN WORDS
-----------------------------------
Hard-won law 8: *"Every screen needs a story. S1 shipped built to an endpoint
contract because no epic owned it; the landing page was half-missing for a
week."* That was **DEF-006**.

**DEF-129** is the same shape at a worse address:

    "THE FIRST SCREEN AFTER EVERY SIGN-IN DOES NOT EXIST — the tenant dashboard
     falls through to the catch-all and renders the literal string
     'SMARTBillHub - W0 scaffold'. … THIS IS HARD-WON LAW 8 FOR THE SECOND TIME
     … a screen named in the inventory that **no story owns**, so it is nobody's
     to build and nobody's to notice."

and its PREVENT column asks for exactly this file:

    "law 8's standing rule — every screen in the inventory needs an owning story
     — needs a gate that reads the screen inventory against story coverage,
     because this is the second screen to reach a user unbuilt for exactly the
     same reason."

**DEF-137** is the third, found in review two days later: **S113** (step 4
Review of the signup flow — the per-block Edit links and the due-today /
then-monthly panel) is claimed by no story either.

Three screens, one cause, and nothing in G1–G24 asks the question.

════════════════════════════════════════════════════════════════════════════
WHAT THIS GATE ASSERTS — AND THE HALF IT DOES **NOT**, MEASURED
════════════════════════════════════════════════════════════════════════════
IT ASSERTS: every screen id in `04-docs/01-spec/01-screen-inventory.md` is
claimed by a story's YAML `screens:` frontmatter, or carries a dated line in
`screen_story_coverage.txt` saying why not and what closes it.

IT DOES **NOT** ASSERT that an owned screen actually EXISTS in the app, and that
refusal is DEF-137's own finding rather than a shortcut:

    "SCREENS DO NOT CARRY THEIR ID. Measuring inventory-vs-frontend by searching
     for the literal string S4 reports 19 screens absent — and SignupWizard.tsx
     proves that wrong immediately, because the setup wizard is BUILT, WORKING
     and driven end to end by journey J1; it simply never writes S4 or S5
     anywhere. So the scan over-reports absence for built screens and cannot
     distinguish them from genuinely missing ones."

A gate built on that signal would fire on nineteen working screens, and
DEF-041's prevention column already says what that does: *"a widened gate that
fires on 40 legitimately-later props teaches people to add ALLOW entries, which
is how a gate stops being a gate."* So the code half is deliberately absent, and
this docstring — not a comment claiming otherwise (law 1) — is where the next
agent finds out why.

**THE CONVENTION THAT UNBLOCKS IT**, adopted by this lane in the files it wrote
and stated here so the next lane can follow it: a screen file's Lifecycle
trailer carries a `screens:` line beside its existing `packet:` line —

    # ── Lifecycle ─────────────────────────────────────────────
    # packet: US-REP-019@EP-REP-05 (…)
    # screens: S7
    # generated: 2026-08-16 by story-coder

One line per screen file, and the inventory becomes machine-readable for the
first time. When enough of the tree carries it, the second assertion — every
CLAIMED screen has a file that claims it back — is about ten lines here. It is
NOT switched on today, because a half-stamped tree would fail on every screen
that simply has not been stamped yet, which is the same trap.

**Until that stamp exists, any number quoted for "screens built" is an
ESTIMATE.** The story-based count in `surface_debt.txt` is the only reliable
measure the repo has, and it counts STORIES, not screens (DEF-137).

════════════════════════════════════════════════════════════════════════════
WHY A REGISTER RATHER THAN A CEILING — the G16/G20/G23 discipline
════════════════════════════════════════════════════════════════════════════
`screen_story_coverage.txt` carries ONE LINE PER UNCLAIMED SCREEN with a reason
and what closes it. Exact, never a ceiling, for the reason G23 states: a ceiling
is a number nobody has to look at again, and "nobody looked" is the whole
defect. So:

  · a screen that LOSES its claim must gain a line here, which is the moment
    somebody writes down why;
  · a screen that GAINS a story must lose its line — the register records the
    win and cannot keep claiming debt that is paid off;
  · a line for a screen that IS claimed, or for a screen the inventory does not
    contain, is STALE and fails the gate (DEF-077: a register nobody audits is
    how a gate becomes a hardcoded `return SKIP`).

A reason must be at least 40 characters. A one-word reason is how a register
turns into an allowlist.

════════════════════════════════════════════════════════════════════════════
PROVED RED BEFORE TRUSTED GREEN (hard-won law 7)
════════════════════════════════════════════════════════════════════════════
Run against the tree as it stood on 2026-08-16 with S113's line removed from the
register, this gate failed naming it:

    G25 screen-coverage | FAIL | 1 inventory screen(s) with NO owning story and
    no register line: S113

which is the state DEF-137 found by hand. S113 then got its story (US-TEN-021),
its `screens: [S113]` frontmatter claim, and its line left the register in the
same commit — and the gate went green.

Python 3.12 stdlib only. Safe to run from any cwd. Nothing here ever writes.
"""

import re
from pathlib import Path

import common

INVENTORY = common.REPO_ROOT / "04-docs" / "01-spec" / "01-screen-inventory.md"
REGISTER = Path(__file__).resolve().parent / "screen_story_coverage.txt"

#: A screen row in A1. The first cell is the id, and it may be a RANGE — A1
#: writes the six email designers as one row, `S97–S102`, and the four SMS
#: designers as `S103–S106`. Expanded, because a ticket cites S99 and not the
#: row it was written on, and an unexpanded range would hide five screens.
ROW_RE = re.compile(r"^\|\s*(S\d+(?:\.\d+)?)(?:\s*[–—-]\s*S(\d+))?\s*\|", re.M)

#: A story's machine-readable claim. This is the SAME signal
#: `04-docs/02-decisions/13a-screen-component-map.md` already audits by hand
#: ("no `screens:` frontmatter claim in any epic"), so the gate and the map
#: cannot answer differently.
CLAIM_RE = re.compile(r"^screens:\s*\[([^\]]*)\]", re.M)

SCREEN_RE = re.compile(r"S\d+(?:\.\d+)?")

MIN_REASON = 40


def inventory_screens() -> list[str]:
    """Every screen id A1 declares, in declaration order, ranges expanded."""
    if not INVENTORY.is_file():
        return []
    text = common.read_text(INVENTORY)
    found: list[str] = []
    for match in ROW_RE.finditer(text):
        start, end = match.group(1), match.group(2)
        if end is None:
            candidates = [start]
        else:
            first = int(start[1:].split(".")[0])
            candidates = [f"S{n}" for n in range(first, int(end) + 1)]
        for screen in candidates:
            if screen not in found:
                found.append(screen)
    return found


def claimed_screens() -> dict[str, set[str]]:
    """{screen: {story files that claim it}} from every story's frontmatter."""
    claims: dict[str, set[str]] = {}
    module_docs = common.MODULE_DOCS
    if not module_docs.is_dir():
        return claims
    for path in sorted(module_docs.rglob("*.md")):
        text = common.read_text(path)
        for match in CLAIM_RE.finditer(text):
            for screen in SCREEN_RE.findall(match.group(1)):
                claims.setdefault(screen, set()).add(common.rel(path))
    return claims


def register_rows() -> tuple[dict[str, str], list[str]]:
    """{screen: reason} plus any malformed lines, from the coverage register."""
    rows: dict[str, str] = {}
    problems: list[str] = []
    if not REGISTER.is_file():
        return rows, ["10-scripts/gates/screen_story_coverage.txt is missing"]
    for number, raw in enumerate(common.read_text(REGISTER).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            problems.append(f"line {number}: expected `<screen> <YYYY-MM-DD> <reason>`")
            continue
        screen, dated, reason = parts
        if SCREEN_RE.fullmatch(screen) is None:
            problems.append(f"line {number}: {screen!r} is not a screen id")
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", dated) is None:
            problems.append(f"line {number}: {dated!r} is not a YYYY-MM-DD date")
            continue
        if len(reason) < MIN_REASON:
            problems.append(
                f"line {number}: {screen}'s reason is {len(reason)} characters; a park needs "
                f"at least {MIN_REASON} — a one-word reason is an allowlist"
            )
            continue
        if screen in rows:
            problems.append(f"line {number}: {screen} is registered twice")
            continue
        rows[screen] = reason
    return rows, problems


def run():
    screens = inventory_screens()
    if not screens:
        return "SKIP", "04-docs/01-spec/01-screen-inventory.md not present or has no screen rows"

    claims = claimed_screens()
    parked, problems = register_rows()

    unclaimed = [screen for screen in screens if screen not in claims]

    # 1. THE ASSERTION — an unclaimed screen with no register line. DEF-006,
    #    DEF-129 and DEF-137 are each exactly this.
    for screen in unclaimed:
        if screen not in parked:
            problems.append(
                f"{screen} is in the screen inventory and NO story claims it "
                f"(no `screens:` frontmatter names it) — hard-won law 8. Author its story, "
                f"or register it in screen_story_coverage.txt with a reason"
            )

    # 2. REGISTER INTEGRITY — never parkable, for the DEF-077 reason.
    for screen in sorted(parked):
        if screen in claims:
            owner = ", ".join(sorted(claims[screen]))
            problems.append(
                f"STALE PARK {screen} IS now claimed ({owner}) — delete its register line in "
                f"the same commit that landed the claim, do not leave it to rot"
            )
        elif screen not in screens:
            problems.append(
                f"STALE PARK {screen} is not in the screen inventory at all — the register "
                f"may only carry screens A1 declares"
            )

    covered = len(screens) - len(unclaimed)
    if problems:
        return "FAIL", (
            f"{len(problems)} screen-coverage problem(s): " + common.summarize(problems, 3)
        )
    return "PASS", (
        f"{covered}/{len(screens)} inventory screens claimed by a story; "
        f"{len(parked)} parked with a reason. (Story coverage only — screens carry no id in "
        f"the frontend yet, DEF-137; any 'screens built' figure is an ESTIMATE.)"
    )


if __name__ == "__main__":
    status, detail = run()
    print(f"G25 screen-coverage | {status} | {detail}")
    screens = inventory_screens()
    claims = claimed_screens()
    parked, _ = register_rows()
    print("\n--- unclaimed screens ---")
    for screen in screens:
        if screen not in claims:
            mark = "parked" if screen in parked else "NOT REGISTERED"
            print(f"  {screen:<8} {mark}")
    raise SystemExit(0 if status != "FAIL" else 1)
