#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects: DEF-1787 (two lanes correctly computed the same defect id) ·
#          DEF-CWP-3734 (THREE lanes correctly computed the same gate number) ·
#          DEF-GOV-3756 (two lanes both shipped 2.141.0). One cause, three
#          registers, one afternoon.
# Rules:   CLAUDE.md hard-won law 11's last clause — "at push time, re-derive
#          BOTH: the file content AND the ids" · law 12 (only what is pushed
#          survives, so the remote is the only place worth asking)
# Tests:   selftest() below
# ───────────────────────────────────────────────────────
"""THE NEXT FREE NUMBER, ASKED OF THE REMOTE RATHER THAN OF THIS CHECKOUT.

WHY THIS EXISTS, AND WHY THE OBVIOUS VERSION OF IT DOES NOT WORK
----------------------------------------------------------------
Three collisions happened in one afternoon — a defect id, a gate number and a
version — and every lane involved computed **max + 1 correctly**. That is the
whole difficulty: the arithmetic was never wrong. What was wrong is *which world
the maximum was taken from*.

A sibling lane working in its own `git worktree` has its rows in **none** of the
places a listing can see — not the working tree, not `HEAD`, not `@{upstream}`
— until it pushes. So two lanes read the same register at the same moment, both
get 3740, and both are right.

`file_defect.py` already solved this for ONE of the three families, and the
shape of its answer is what this generalises: **fetch first, then ask every
remote branch**, because `@{upstream}` is a local tracking ref and is only as
fresh as the last fetch (`DEF-325`).

⚠ **IT STILL CANNOT RESERVE, AND SAYING SO IS THE POINT.** Nothing here writes
to the remote, so two lanes calling this within the same second still get the
same answer. What it removes is the STALE read, which is the common case; what
it adds is `--verify`, the check that catches the rare one **at push time**,
which is the only moment the answer can be final. A tool that claimed to
reserve would be a comment claiming a guarantee (law 1).

USE
---
    allocate.py defect                  -> 3758
    allocate.py gate                    -> 93
    allocate.py version --bump change   -> 2.144.0
    allocate.py defect --verify 3758    -> exit 0 if still free, 1 if taken
    allocate.py --selftest

`--verify` is the one that matters. Take a number when you start, and verify it
in the same breath as you re-derive your blobs from the pinned tip — law 11 says
those are one act, and this makes them one command.

⚠ **`--verify` ASKS THE REMOTE BRANCHES AND NOTHING ELSE — YOUR OWN ROW DOES NOT
COUNT AGAINST YOU (`DEF-GOV-3843`, 2026-09-05).** It used to include the working
tree, where by push time the row and the version bump already are, so it
answered TAKEN for every number a lane could ever ask about, and *free* for a
version a sibling had genuinely shipped. Both directions were wrong on the
version family at once, measured while 2.163.0 was live on the branch tip.
Allocation still reads every world; only verification narrows.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: family -> (path in the tree, pattern whose first group is the number)
FAMILIES: dict[str, tuple[str, str]] = {
    # Every defect id, module-tagged or not. The module segment is a LABEL and
    # never a namespace: `DEF-CWP-3740` and `DEF-GOV-3740` are one number.
    "defect": ("12-governance/10-defect-log.csv", r'^"?DEF-(?:[A-Z]{3}-)?(\d{3,5})'),
    # A gate's number is how this repo cites it — CLAUDE.md and the business
    # rules write `G84`, never `G84 provider-error-seam`.
    "gate": ("10-scripts/gates/run_gates.py", r'\("G(\d+) '),
    # ⚠ **ADDED 2026-09-04 BECAUSE OQ IDS COLLIDED TWICE IN TWENTY MINUTES** —
    # one lane took 1563, a sibling landed 1563, it took 1565, four more
    # landed. The register is the file, and the pattern matches the id wherever
    # it appears in a row, because a question is cited far more often than it
    # is defined and every citation is a number somebody could reuse.
    "oq": ("12-governance/01-open-questions.md", r"OQ-(?:[A-Z]{3}-)?(\d{3,5})(?!\d)"),
    # ⚠ **ADDED 2026-09-10 — A CHANGE REQUEST'S NUMBER, WHATEVER BRANCH SUFFIX
    # IT CARRIES.** PO ruling of that day: a CR raised on a branch is written
    # `CR-<nnn>-<BRCnn>` so two branches never write the same id. **The suffix
    # is provenance and NOT a namespace** — `CR-090` and `CR-090-BRC01` are ONE
    # number, so two branches both reaching for ninety collide here even though
    # their ids differ as strings. That is the whole reason this family exists:
    # the strings would merge clean and a person saying "CR-90" would mean two
    # different changes. The register is the INDEX; every CR has a row there
    # whether or not its text lives in its own file.
    "cr": ("12-governance/11-change-requests.md", r"CR-(\d{3,5})(?!\d)"),
}


#: family -> the POSIX-ERE form of CLAUDE.md's own search pattern, used to find
#: the id ANYWHERE rather than only in its register. `git grep` is BRE/ERE, not
#: Python, so `(?:…)` and the `(?!\d)` lookahead are not available here; the
#: over-match a missing lookahead causes is handled by `_claimed_elsewhere`,
#: which takes the digits it finds and lets the register's own stricter Python
#: pattern decide the maximum. Over-reading a claim is SAFE — it can only make
#: the allocator skip a number — while under-reading is the bug being fixed.
CLAIM_PATTERNS: dict[str, str] = {
    "defect": r"DEF-([A-Z]{3}-)?[0-9]{3,5}",
    "oq": r"OQ-([A-Z]{3}-)?[0-9]{3,5}",
    # ⚠ **THE PROTOTYPE PLANTS `CR-`-SHAPED STRINGS THAT ARE NOT IDS OF OURS** —
    # `CR-2028015` and `CR-2028018` are credit-note numbers in `05-prototype/`,
    # three files. This ERE has no lookahead, so it reads them, and it reads
    # them as **20280** (leftmost-longest takes five digits, never three) —
    # which lands far above `ceiling`, so they are DISCARDED rather than
    # believed. Named here because the safety is the ceiling's and not this
    # pattern's: tighten the pattern and you lose the protection, widen the
    # ceiling past 20280 and the allocator burns the id space.
    "cr": r"CR-([0-9]{3,5})",
}
#: How far back commit MESSAGES are read. The collision this closes was an id
#: that lived in a commit SUBJECT and in no file at all, so the tree scan alone
#: would not have caught it.
LOG_DEPTH = 4000


def git(*args: str, ok: tuple[int, ...] = (0,)) -> bytes:
    r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True)
    return r.stdout if r.returncode in ok else b""


def _sources() -> list[str]:
    """Every world worth asking, freshest first. `HEAD` and the working tree are
    included because a lane's own uncommitted row is real to that lane."""
    git("fetch", "--quiet", "origin")
    refs = git("for-each-ref", "--format=%(refname)", "refs/remotes/origin").decode().split()
    return ["", "HEAD", *refs]  # "" = the working tree


def _claimed_elsewhere(
    family: str, *, tip_only: bool, ceiling: int | None = None
) -> tuple[set[int], list[str]]:
    """Numbers claimed OUTSIDE the register — in code, in docs, in a commit
    message.

    ⚠ **THE REGISTER IS NOT THE ONLY PLACE AN ID IS CLAIMED, AND THIS FILE READ
    NOTHING ELSE UNTIL 2026-09-05 (`DEF-GOV-3936`).** Two lanes were handed
    `3932` an hour apart: the sibling had pushed `05ec78f2` — *"DEF-CWP-3932:
    G95 read a glob as a path"* — and that id was in a commit SUBJECT and in
    source comments, and in no register row this allocator could see. Both
    lanes computed `max + 1` correctly over the file they were told to read.
    **A claim anywhere counts as a claim**, which is the whole of the fix.

    Three worlds, and each is cheap enough to be unconditional (~1.5s all told):
      * the WORKING TREE — this lane's own uncommitted claims, and skipped for
        `--verify`, which asks the opposite question (see `numbers`);
      * the TIP's tree — every claim standing in pushed code right now. Older
        commits are deliberately NOT walked: a citation deleted since is no
        longer a claim, and the tip already holds every live one;
      * commit MESSAGES across every ref, to `LOG_DEPTH`, which is the world the
        tree cannot see and the one that caused the collision.

    ⚠ **A MISS HERE IS SILENT AND A FALSE HIT IS *ALMOST* HARMLESS**, so this
    reads generously — but not without a `ceiling`, and the first draft had
    none. **The repo plants SYNTHETIC ids on purpose**: `DEF-99999` in `G62`'s
    self-test, `DEF-12345` and `DEF-XYZ-9999` in `test_def2804_id_width.py`,
    each one a fixture proving an id READER works. Counting those as claims
    made the allocator answer **`next = 100000`**, which is not a conservative
    error — it is a wrong answer delivered confidently, and it would have
    burned the whole id space on the first lane that trusted it.

    **The ceiling is the allocator's own in-flight limit and not a guess:**
    `BLOCK_SIZE × BLOCK_LANES` is the most any set of lanes can legitimately be
    ahead of the register at one moment. A claim further out than that is a
    fixture, because no real allocation could have got there. A claim inside it
    is exactly the in-flight sibling this function exists to see.
    """
    pattern = CLAIM_PATTERNS.get(family)
    if not pattern:
        return set(), []
    found: set[int] = set()
    seen: list[str] = []
    # ⚠ THE FULL ID, THEN ITS DIGITS — NEVER DIGITS OUT OF RAW TEXT. A first
    # draft ran the digit pattern straight over `git log --format=%B`, which is
    # whole commit BODIES, and swallowed every three-to-five digit number any
    # lane had ever written in prose: line numbers, row counts, dollar figures.
    # It answered `next = 100000`. The family prefix is what makes a number an
    # ID rather than a number, so it is matched first, every time.
    family_re = re.compile(pattern.replace("[0-9]", r"\d"))
    digits = re.compile(r"(\d{3,5})(?!\d)")

    def take(blob: bytes, label: str) -> None:
        text = blob.decode("utf-8", "replace")
        ids = family_re.findall(text) if False else [m.group(0) for m in family_re.finditer(text)]
        new = {int(d) for one in ids for d in digits.findall(one)} - found
        if ceiling is not None:
            new = {n for n in new if n <= ceiling}
        if new:
            seen.append(f"{label} (+{len(new)})")
        found.update(new)

    if not tip_only:
        take(git("grep", "-h", "-o", "-E", pattern), "working tree code")
    # ⚠ **`HEAD` AND `--all` ARE THIS LANE'S OWN WORLDS THE MOMENT IT COMMITS,
    # AND UNDER `tip_only` THAT IS THE ONE THING THEY MUST NOT BE
    # (`DEF-GOV-4095`).** `DEF-GOV-3843` fixed exactly this for the REGISTER
    # read in `numbers()` — its docstring is where the failure mode is named,
    # *"a check that cannot pass, which law 11 says is worse than no check
    # because it is trusted"* — and then `DEF-GOV-3936` added these two claim
    # sources reading `HEAD` and `--all`, which put the hole straight back for
    # every id a lane cites in its own code or its own commit message.
    #
    # It is not theoretical: law 11 tells a lane to verify **at push time**,
    # which is precisely when its row is written AND committed AND unpushed. So
    # `--verify` answered TAKEN for the caller's own number every time, and the
    # prescribed response — *"Renumber before you commit"* — burns a fresh id
    # that the next verify calls taken for the same reason. A check that cannot
    # pass trains the lane to ignore it, and then the real collision goes
    # through.
    take(git("grep", "-h", "-o", "-E", pattern, _pushed_tree() if tip_only else "HEAD"), "pushed code")
    # One traversal over the remote refs, not 46 greps: `--remotes=origin` is
    # 0.09s where `git grep` across every remote tree is 13.8s (measured
    # 2026-09-05), and a check nobody can afford to run is a check nobody runs.
    log_scope = ["--remotes=origin"] if tip_only else ["--all"]
    take(git("log", "--format=%B", *log_scope, f"-n{LOG_DEPTH}"), "commit messages")
    return found, seen


def _pushed_tree() -> str:
    """The newest ancestor of `HEAD` that a remote ref also carries.

    ⚠ **NOT `HEAD`, AND THE DIFFERENCE IS THE WHOLE OF `DEF-GOV-4095`.** A lane
    that has committed and not yet pushed has its own claims in `HEAD`'s tree,
    so grepping `HEAD` answers *"a sibling has this"* about the lane's own work.
    Walking back to the last commit any remote ref holds gives the world as
    everybody else can see it, which is the question `--verify` is asking.

    Falls back to `HEAD` when nothing is local-only (nothing to subtract) and
    when the walk cannot be done at all — a slightly over-eager TAKEN is the
    safe direction for an allocator, and it is what this returned before.
    """
    local_only = git("rev-list", "HEAD", "--not", "--remotes=origin", ok=(0, 128)).decode().split()
    if not local_only:
        return "HEAD"
    # `rev-list` is newest-first, so the LAST entry is this lane's earliest
    # unpushed commit; its parent is the newest commit the remotes hold.
    base = git("rev-parse", f"{local_only[-1]}^", ok=(0, 128)).decode().strip()
    return base or "HEAD"


#: The register of lane BLOCKS, and the id prefix each family writes there.
#: `cr` is deliberately included: `13-change-process.md` step 0 makes a disjoint
#: CR block per branch the mechanism that keeps CR numbers unique, and that
#: block is recorded in exactly this file.
RESERVATIONS_PATH = "12-governance/14-id-reservations.md"
RESERVATION_PREFIX: dict[str, str] = {"defect": "DEF", "oq": "OQ", "cr": "CR"}

#: `DEF-CUS-7600–7629`, `OQ-CUS-12770–12779`, `DEF-1793…1796`, `CR-090`–`094`.
#: The separator is usually an EN DASH — this file is written by people — so all
#: of en dash, em dash, hyphen, ellipsis and `..` are accepted, with optional
#: spaces and optional backticks around the second number.
_RESERVED_RANGE = re.compile(
    r"(?:DEF|OQ|CR)-(?:[A-Z]{3}-)?(\d{3,5})\s*[`]?\s*(?:[–—…]|\.\.|-)\s*[`]?(\d{3,5})(?!\d)"
)

#: A reservation wider than this is not a reservation, it is two numbers that
#: happen to sit either side of a dash in prose. The widest real block is 40.
_MAX_RESERVED_SPAN = 60


def _reserved(family: str, *, sources: list[str], ceiling: int) -> tuple[set[int], list[str]]:
    """Numbers a lane has RESERVED in `14-id-reservations.md` but not yet USED.

    ⚠ **THIS IS THE GAP THAT CAUSED ALL FOUR OF 2026-09-28's COLLISIONS
    (`DEF-GOV-7814`).** Everything else in this file asks *which numbers are
    USED* — it reads registers and greps the tree for citations. A lane that
    does the right thing and RESERVES a block first is therefore invisible to
    it: on 2026-09-28 a lane reserved `7700`–`7709` and **pushed the
    reservation row before starting work**, `allocate.py --verify` still
    answered *"7700: still free on every branch"*, and a sibling took
    `DEF-CUS-7700`, `DEF-CUS-7701` and `DEF-INF-7702` out of the middle of it.
    The second lane then renumbered by hand to `7800`–`7803`, moving sixteen
    citations and two filenames.

    **The reservation was doing its job and the tool could not see it.** That is
    hard-won law 7's fifth shape — the allocator was not lying, it was answering
    truthfully about everything it looked at — and the census of the same day
    found the footprint in `G17`: the live number collisions cluster in RUNS
    (`6554`–`6558`, `6759`–`6763`), which is the signature of two lanes taking
    the same BLOCK rather than of fifteen separate mistakes.

    ⚠ **IT STILL CANNOT RESERVE, AND NOTHING HERE PRETENDS OTHERWISE.** Two
    lanes writing a reservation row in the same second still collide; what this
    closes is the much commoner case where one lane reserved and PUSHED and the
    other simply could not see it.

    ⚠ **IT REFUSES THE WHOLE BLOCK, NOT ONLY ITS FIRST NUMBER, AND THAT IS THE
    POINT RATHER THAN A DETAIL.** Every number in a reserved range is returned,
    so `--verify` refuses `7618` exactly as it refuses `7617`; and because these
    numbers join `found`, `block()`'s floor — `((max(found) // 100) + 1) * 100`
    — is pushed ABOVE any open block, so a new block cannot overlap one either.
    Refusing only the first id of a range would simply move the collision to the
    second, which is precisely the shape the register already shows: the live
    number collisions run in unbroken sequences (`6554`–`6558`, `6759`–`6763`),
    because two lanes took the same BLOCK and then walked it id by id.

    ⚠ **READING GENEROUSLY IS THE SAFE DIRECTION, AND IT IS BOUNDED TWICE.** A
    false hit here only makes the allocator skip a number, which costs nothing;
    a miss is the bug. So the pattern accepts every dash this file is written
    with — but a span wider than `_MAX_RESERVED_SPAN` is discarded as prose, and
    every number is held under the same `ceiling` the citation scan uses, so a
    typo cannot burn the id space.
    """
    prefix = RESERVATION_PREFIX.get(family)
    if prefix is None:  # `gate` and `version` have no block register
        return set(), []
    found: set[int] = set()
    seen: list[str] = []
    for ref in sources:
        blob = (
            (REPO / RESERVATIONS_PATH).read_bytes()
            if ref == ""
            else git("show", f"{ref}:{RESERVATIONS_PATH}", ok=(0, 128))
        )
        if not blob:
            continue
        text = blob.decode("utf-8", "replace")
        new: set[int] = set()
        for line in text.splitlines():
            # The family has to appear on the LINE, so a defect block is not
            # read as an OQ one on a page that lists both.
            if f"{prefix}-" not in line:
                continue
            for lo_s, hi_s in _RESERVED_RANGE.findall(line):
                lo, hi = int(lo_s), int(hi_s)
                if not lo < hi <= lo + _MAX_RESERVED_SPAN:
                    continue
                new |= {n for n in range(lo, hi + 1) if n <= ceiling}
        new -= found
        if new:
            seen.append(f"{ref or 'working tree'} reservations (+{len(new)})")
        found |= new
    return found, seen


def numbers(family: str, *, sources: list[str] | None = None) -> tuple[set[int], list[str]]:
    """Every number this family has anywhere, and which worlds contributed.

    ⚠ **`sources` EXISTS SO `--verify` CAN LEAVE THIS LANE'S OWN WORLDS OUT
    (`DEF-GOV-3843`).** Allocation wants every world, this one included — that
    is why the default reads the working tree. **Verification wants the
    opposite question**: *did a SIBLING take this while I worked?* By the time a
    lane verifies, its own row is written and committed, so counting its own
    worlds answers TAKEN for every number it could ever ask about — a check
    that cannot pass, which law 11 says is worse than no check because it is
    trusted. `main` passes the remote refs alone for that reason.
    """
    path, pattern = FAMILIES[family]
    found: set[int] = set()
    seen: list[str] = []
    for ref in sources if sources is not None else _sources():
        blob = (REPO / path).read_bytes() if ref == "" else git("show", f"{ref}:{path}", ok=(0, 128))
        if not blob:
            continue
        new = {int(m) for m in re.findall(pattern, blob.decode("utf-8", "replace"), re.M)} - found
        if new:
            seen.append(f"{ref or 'working tree'} (+{len(new)})")
        found |= new
    # ⚠ AND EVERYWHERE ELSE THE ID IS CLAIMED (`DEF-GOV-3936`). `sources` being
    # restricted to remote refs is how `--verify` says *do not count my own
    # worlds*, so the working tree is skipped on exactly that signal.
    tip_only = sources is not None and all(s.startswith("refs/remotes/") for s in sources)
    ceiling = (max(found) if found else 0) + BLOCK_SIZE * BLOCK_LANES
    claimed, claim_seen = _claimed_elsewhere(family, tip_only=tip_only, ceiling=ceiling)
    found |= claimed
    seen += claim_seen
    # ⚠ AND EVERY NUMBER A LANE HAS RESERVED (`DEF-GOV-7814`). Reserving a block
    # and pushing the row is the CORRECT thing to do and was invisible here, so
    # the tool punished the careful lane. Read from the same worlds as the
    # register above, under the same ceiling.
    reserved, reserved_seen = _reserved(
        family, sources=sources if sources is not None else _sources(), ceiling=ceiling
    )
    found |= reserved
    seen += reserved_seen
    return found, seen


#: How wide a lane's private block is, and how many lanes fit above one floor.
#: Twenty ids is more than any wave has ever needed; eight lanes is twice the
#: most we have run at once.
BLOCK_SIZE = 20
BLOCK_LANES = 8


def block(
    family: str, lane: str, size: int = BLOCK_SIZE, roster: list[str] | None = None
) -> tuple[int, int, list[str], str | None]:
    """A range of ids THIS LANE alone may use — the cure for the collisions.

    ⚠ **`--verify` CATCHES A COLLISION; THIS PREVENTS ONE, AND THE DIFFERENCE
    IS WHERE THE COST LANDS.** Verify fires at push time, after the id is
    already written into a register row, a code comment, a docstring and three
    citations — so acting on it means renumbering all of them. On 2026-09-04
    that happened FIVE times in one day across three families, and one lane hit
    it twice in twenty minutes.

    **How two lanes get disjoint blocks from the same reading.** Round the
    current maximum UP to the next hundred — every lane that reads a maximum
    anywhere in that hundred agrees on the same floor, which is what makes this
    work when they read at different moments — then give each lane its own
    twenty-wide window above it.

    ⚠ **THE SLOT COMES FROM THE ROSTER, NOT FROM A DIGEST OF THE NAME, AND THE
    FIRST DRAFT GOT THIS WRONG IN A WAY WORTH KEEPING.** Hashing the lane name
    into eight slots is the obvious design and it is the birthday problem: with
    six lanes it collided TWICE on the first try — `usage` and `documents` both
    landed on `3940-3959`. A collision-prevention tool that collides is worse
    than none, because it is trusted. Pass `--lanes a,b,c,d` and the slot is the
    lane's index in the sorted roster: **disjoint by construction, for any
    number of lanes up to the roster's length.** The digest remains only as a
    fallback for a lane dispatched alone, and it says so out loud.

    ⚠ **THE NUMBERS ARE NOT RESERVED, AND THEY DO NOT NEED TO BE.** Nothing is
    written to the remote here either. What removes the collision is that the
    two lanes are no longer reaching for the same number in the first place —
    the gap the floor leaves is deliberate slack, not waste, and ids are free.
    """
    found, seen = numbers(family)
    floor = ((max(found) // 100) + 1) * 100 if found else 100
    warning = None
    if roster:
        names = sorted({one.strip() for one in roster if one.strip()})
        if lane not in names:
            # ⚠ **REFUSED RATHER THAN ADDED, AND THE ORCHESTRATOR WALKED INTO
            # THIS WITHIN THE HOUR (2026-09-04).** A first version appended the
            # missing lane and re-sorted — which silently RESHUFFLES every
            # other lane's block, so a seventh lane asking for a block moved
            # the six already building. The blocks are stable only while the
            # roster is; a tool that hides that is the same trap this whole
            # family of fixes is about.
            raise SystemExit(
                f"allocate: lane {lane!r} is not in --lanes ({', '.join(names)}). "
                "Adding it would reshuffle every other lane's block. Pass the SAME roster "
                "to every lane in the wave, with every lane in it from the start."
            )
        slot = names.index(lane)
    else:
        slot = int(hashlib.sha256(lane.encode()).hexdigest(), 16) % BLOCK_LANES
        warning = (
            "no --lanes roster given, so the slot came from a digest of the name — "
            "that CAN collide with another lane (it did, twice, on six lanes). "
            "Pass --lanes with every lane in this wave."
        )
    start = floor + slot * size
    return start, start + size - 1, seen, warning


#: Every file that carries the product version — `07-frontend/package.json` and
#: its lockfile, `06-backend/pyproject.toml`, and (since 2026-10-21) the native
#: field app's `field-app/package.json` and its lockfile — which is what `G35`
#: compares. Named here because this file COMPUTES the number and
#: a lane that is handed a number without being told where to write it will
#: write it in one place (`DEF-GOV-4023`, the FOURTH lockstep break; `DEF-341`
#: is the first three and `DEF-347` is the lockfile drifting thirteen releases).
VERSION_FILES = (
    ("07-frontend/package.json", r'"version"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"'),
    ("07-frontend/package-lock.json", r'"version"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"'),
    ("06-backend/pyproject.toml", r'^version\s*=\s*["\']([0-9]+\.[0-9]+\.[0-9]+)["\']'),
    # The native field app (CR-187-BRC10) — decision log 2026-10-21, twelve
    # conflicts, #4: *"one product version … `field-app/package.json` joins `G35`
    # and `allocate.py version`"*. Its own manifest and lockfile, because it is on
    # React 19 and the web app on React 18 (#1). The lockfile's FIRST `"version"`
    # is the package's own; G35 clause 6 checks both of its copies.
    ("field-app/package.json", r'"version"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"'),
    ("field-app/package-lock.json", r'"version"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"'),
)


#: The two literals a lane AUTHORS. The lockfile is derived from `package.json`
#: and pins a `"version"` for every dependency, so it answers the disagreement
#: question and never the "what number is next" one.
AUTHORITATIVE = tuple(f for f in VERSION_FILES if "lock" not in f[0])


def version_literals() -> dict[str, str | None]:
    """What each version file says RIGHT NOW, in this working tree.

    ⚠ **THIS IS THE QUESTION `--verify` DOES NOT ASK AND READS AS THOUGH IT
    DID.** `--verify` answers *has a sibling taken this number*; it said *"still
    free on every branch"* to a lane three times in a row while, in that same
    tree, `package.json` read `2.178.1` and `pyproject.toml` read `2.177.0`.
    A lane reading that as *the version is fine* is making the mistake this repo
    files as *a check's name is not its behaviour* — so the two questions are
    now asked together and the answers printed together.
    """
    out: dict[str, str | None] = {}
    for rel, pattern in VERSION_FILES:
        try:
            text = (REPO / rel).read_text(encoding="utf-8")
        except OSError:
            out[rel] = None
            continue
        m = re.search(pattern, text, re.MULTILINE)
        out[rel] = m.group(1) if m else None
    return out


def lockstep_complaint() -> str | None:
    """One sentence when the literals disagree, else None. `G35`'s question,
    asked at the moment a lane can act on it for free rather than seventeen
    minutes later in a suite with 29 other reds."""
    found = version_literals()
    distinct = {v for v in found.values() if v is not None}
    if len(distinct) <= 1 and None not in found.values():
        return None
    parts = ", ".join(f"{rel}={v or 'NO LITERAL'}" for rel, v in found.items())
    return (
        f"VERSION LOCKSTEP IS BROKEN IN THIS TREE: {parts}. One bump moved and another "
        f"did not (DEF-GOV-4023). Move EVERY file above, forward for all and backward "
        f"for none — G35 blocks the merge until they agree."
    )


def version_literal() -> str:
    text = (REPO / "07-frontend" / "package.json").read_text(encoding="utf-8")
    m = re.search(r'"version"\s*:\s*"([0-9]+)\.([0-9]+)\.([0-9]+)"', text)
    if not m:
        raise SystemExit("allocate: package.json carries no version literal")
    return ".".join(m.groups())


def version_shipped() -> dict[str, str]:
    """Every version literal ANYWHERE BUT THIS WORKING TREE, and where it is.

    ⚠ **THE WORKING TREE IS EXCLUDED ON PURPOSE, AND UNTIL 2026-09-05 IT WAS THE
    ONLY THING `--verify` READ — SO THE ONE CHECK THIS FILE EXISTS FOR WAS
    INVERTED IN BOTH DIRECTIONS ON THE VERSION FAMILY (`DEF-GOV-3843`).**
    `--verify` is run by a lane at push time, on the number that lane is
    holding — which by then it has already written into its own
    `package.json`. Comparing against that literal therefore answered *TAKEN —
    somebody shipped it* for every number a lane could ever ask about, and
    *free* for a version a sibling had genuinely shipped. Measured on
    2026-09-05 with 2.163.0 live on the branch tip and 2.164.0 only in this
    tree: `--verify 2.163.0` said **free** and `--verify 2.164.0` said
    **TAKEN**, both exactly backwards.

    The other families never had this because `numbers()` reads the register
    from every world and takes the UNION — a lane's own row is one entry among
    many. A version is a single literal, so including the working tree does not
    add to the answer, it REPLACES it.

    ⚠ **AND `package.json` ALONE IS NOT ENOUGH EITHER, WHICH THE FIRST DRAFT OF
    THIS FIX GOT WRONG IN THE HOUR IT WAS WRITTEN.** A branch's literal is only
    its LATEST version; every version shipped before it has scrolled into
    history and would read as free. `2.163.0` had been shipped by a sibling
    twenty minutes earlier and the draft called it free the moment the tip moved
    to `2.164.0` — the same collision, one commit later. **`CHANGELOG.md` is the
    register of shipped versions** and it accumulates, so its headings are read
    alongside the literal and history is covered without walking commits.
    """
    where: dict[str, str] = {}
    for ref in _sources():
        if not ref.startswith("refs/remotes/"):
            continue  # not the working tree, not local HEAD — see above
        short = ref.replace("refs/remotes/", "")
        pkg = git("show", f"{ref}:07-frontend/package.json", ok=(0, 128)).decode("utf-8", "replace")
        log = git("show", f"{ref}:CHANGELOG.md", ok=(0, 128)).decode("utf-8", "replace")
        for shipped in versions_in(pkg, log):
            where.setdefault(shipped, short)
    return where


def versions_in(package_json: str, changelog: str) -> set[str]:
    """Every version one branch has ever shipped: its literal plus its history."""
    found = set(re.findall(r"^## \[([0-9]+\.[0-9]+\.[0-9]+)\]", changelog, re.M))
    m = re.search(r'"version"\s*:\s*"([0-9]+\.[0-9]+\.[0-9]+)"', package_json)
    if m:
        found.add(m.group(1))
    return found


def claims_at_or_above(literal: str, want: str) -> bool:
    """Does a version literal already claim `want`, or a number past it?

    Pure, so `selftest` holds it. Compared as a TUPLE OF INTEGERS and never as
    text: `"2.9.0" > "2.10.0"` is true as strings and false as versions, and a
    check that got that backwards would stay silent on exactly the collisions it
    exists to catch.
    """
    try:
        return tuple(int(x) for x in literal.split(".")) >= tuple(int(x) for x in want.split("."))
    except ValueError:
        return False


def tree_claim(want: str) -> str | None:
    """What THIS WORKING TREE already claims, said out loud beside the verdict.

    ⚠ **THIS IS THE HALF `--verify` COULD NOT SEE, AND IT IS WHERE THE
    COLLISIONS ACTUALLY HAPPEN (`DEF-GOV-5139`, three in one afternoon).**
    `version_shipped()` excludes this tree deliberately and correctly — at push
    time a lane's OWN number is already written into `package.json`, so counting
    it answered *TAKEN* for every number a lane could ask about
    (`DEF-GOV-3843`). The cost of that exclusion is the blind spot: **a version
    is CLAIMED by editing three tracked files in a shared tree, long before
    anybody pushes**, and the tree is the one place the verdict does not look.
    With one lane that is a rare race; with eight it is the ordinary case.

    So this does not change the VERDICT — that inversion is exactly what
    `DEF-GOV-3843` cost — it prints what the tree holds and lets the person
    decide, because the person is the only one who knows whether the literal in
    `package.json` is their own bump or a sibling's.

    Returns None when the tree is behind the number being verified, which is the
    ordinary case and needs no sentence.
    """
    for rel, value in version_literals().items():
        if not value or rel not in dict(AUTHORITATIVE):
            continue
        if not claims_at_or_above(value, want):
            continue
        if True:
            same = "the SAME number" if value == want else f"{value}, at or above it"
            return (
                f"\u26a0 THIS TREE ALREADY READS {same} in {rel}. `--verify` never counts "
                f"this tree (DEF-GOV-3843), so the line above is about branches only. "
                f"If you did not write that literal yourself, A SIBLING IN THIS TREE HOLDS "
                f"IT \u2014 re-bump before you commit. Three lanes collided this way on "
                f"2026-09-13 (DEF-GOV-5139) and every allocation was arithmetically right."
            )
    return None


def version_verdict(want: str, shipped: dict[str, str]) -> tuple[bool, str]:
    """(is it taken, the sentence to print) — pure, so `selftest` can hold it."""
    ref = shipped.get(want)
    if ref:
        return True, f"{want}: TAKEN — {ref.replace('refs/remotes/', '')} carries it. Re-bump before you commit."
    return False, f"{want}: still free on every branch (this tree not counted)"


def next_version(bump: str) -> str:
    """The next number, above EVERY literal in EVERY world.

    ⚠ **Read from EVERY remote branch, not just this checkout** — two lanes both
    shipped 2.141.0 because each read its own `package.json` (`DEF-GOV-3756`).

    ⚠ **AND FROM EVERY VERSION FILE, NOT JUST `package.json` — WHICH THIS
    FUNCTION LEARNED BY CAUSING THE THING IT WAS BEING FIXED FOR
    (`DEF-GOV-4023`).** The commit that taught this file about
    `pyproject.toml` computed its own version by reading `package.json` alone,
    exactly as before. At that moment the branch tip carried `package.json`
    2.179.0 and `pyproject.toml` **2.180.0** — lockstep broken the other way by
    a sibling — so the bump returned 2.179.1 and the fix for backwards version
    moves MOVED A LITERAL BACKWARDS, from 2.180.0 to 2.179.1. The gate did not
    object, because `G35` compares the literals for AGREEMENT and says nothing
    about direction; only reading the numbers by hand caught it.
    **So the maximum is taken over the whole matrix — every AUTHORITATIVE file,
    in this tree and on every remote ref.** A number that is only ahead of one
    file is not ahead.

    (That particular 2.180.0 turned out to be an orphan — no `CHANGELOG` entry,
    no `package.json` anywhere carrying it, i.e. the sibling's own one-sided
    bump rather than a release — so nothing real went backwards. The arithmetic
    was still wrong, and it was wrong in a way that would have moved a REAL
    version the next time it happened.)
    """
    highest = (0, 0, 0)
    for rel, value in version_literals().items():
        if value and rel in dict(AUTHORITATIVE):
            highest = max(highest, tuple(int(x) for x in value.split(".")))
    for ref in _sources()[1:]:
        for rel, pattern in AUTHORITATIVE:
            blob = git("show", f"{ref}:{rel}", ok=(0, 128)).decode("utf-8", "replace")
            # ⚠ **FIRST MATCH ONLY, AND NOT THE LOCKFILE — `re.finditer` OVER
            # `package-lock.json` RETURNED `7946.0.17`.** A lockfile carries a
            # `"version"` for every dependency it pins, so scanning all of them
            # takes the maximum over npm's registry rather than over this
            # product. The lockfile mirrors `package.json` and adds nothing to
            # this question; it stays in `VERSION_FILES` because the
            # DISAGREEMENT check must still see it (`DEF-347`).
            m = re.search(pattern, blob, re.MULTILINE)
            if m:
                highest = max(highest, tuple(int(x) for x in m.group(1).split(".")))
    r, c, f = highest
    return {"release": f"{r + 1}.0.0", "change": f"{r}.{c + 1}.0", "fix": f"{r}.{c}.{f + 1}"}[bump]


def selftest() -> int:
    """The arithmetic, on synthetic input — never on the real registers."""
    failed = 0
    cases = [
        ('"DEF-CWP-3740","x"\n"DEF-GOV-3740","y"\n', r'^"?DEF-(?:[A-Z]{3}-)?(\d{3,5})', {3740},
         "a module-tagged pair is ONE number, not two"),
        ('DEF-3739,a\n"DEF-WRK-3741",b\n', r'^"?DEF-(?:[A-Z]{3}-)?(\d{3,5})', {3739, 3741},
         "quoted and unquoted, tagged and untagged, all counted"),
        ('    ("G27 engine-surface", x),\n    ("G27 translation-keys", y),\n    ("G91 z", z),\n',
         r'\("G(\d+) ', {27, 91}, "two rows sharing G27 are one number"),
    ]
    for text, pattern, want, label in cases:
        got = {int(m) for m in re.findall(pattern, text, re.M)}
        if got != want:
            print(f"selftest FAILED: {label} — got {sorted(got)}, wanted {sorted(want)}")
            failed = 1
        else:
            print(f"selftest ok — {label}")
    for literal, want, expect, label in [
        ("2.246.0", "2.246.0", True, "the tree holding the SAME number is a claim"),
        ("2.247.0", "2.246.0", True, "the tree holding a LATER number is a claim"),
        ("2.245.0", "2.246.0", False, "the tree behind the number is not a claim"),
        ("2.10.0", "2.9.0", True, "compared as numbers, not as text — 2.10.0 is past 2.9.0"),
        ("2.9.0", "2.10.0", False, "and 2.9.0 is not, which string comparison gets backwards"),
    ]:
        got = claims_at_or_above(literal, want)
        if got != expect:
            print(f"selftest FAILED: {label} — {literal} vs {want} gave {got}")
            failed = 1
        else:
            print(f"selftest ok — {label}")
    for cur, bump, want in [("2.141.0", "change", "2.142.0"), ("2.141.0", "fix", "2.141.1"),
                            ("2.141.3", "release", "3.0.0")]:
        r, c, f = (int(p) for p in cur.split("."))
        got = {"release": f"{r+1}.0.0", "change": f"{r}.{c+1}.0", "fix": f"{r}.{c}.{f+1}"}[bump]
        if got != want:
            print(f"selftest FAILED: {cur} {bump} -> {got}, wanted {want}"); failed = 1
    if not failed:
        print("selftest ok — every version bump lands where it should")
    # ⚠ **THE VERDICT, BOTH WAYS ROUND — `DEF-GOV-3843` HAD IT BACKWARDS IN BOTH
    # AND NOTHING NOTICED, BECAUSE THERE WAS NO CASE FOR IT HERE.**
    # A branch whose literal has already moved past the version it shipped
    # twenty minutes ago — the case the first draft of this fix called free.
    ever = versions_in('{"version": "2.164.0"}', "## [2.164.0] — x\n\n## [2.163.0] — y\n")
    if ever != {"2.163.0", "2.164.0"}:
        print(f"selftest FAILED: a shipped version must survive the literal moving on — got {sorted(ever)}")
        failed = 1
    else:
        print("selftest ok — a shipped version survives the literal moving on")
    shipped = {"2.163.0": "origin/claude/product-version-gh1br4"}
    for want, expect, label in [
        ("2.163.0", True, "a version a sibling has already shipped is TAKEN"),
        ("2.164.0", False, "a version nobody has shipped is free, even when this tree holds it"),
    ]:
        got, _ = version_verdict(want, shipped)
        if got != expect:
            print(f"selftest FAILED: {label}")
            failed = 1
        else:
            print(f"selftest ok — {label}")
    return failed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("family", nargs="?", choices=[*FAMILIES, "version"])
    ap.add_argument("--verify", metavar="N", help="exit 1 if N is already taken somewhere")
    ap.add_argument(
        "--lane",
        metavar="NAME",
        help="reserve a private block of ids for this lane, so two lanes cannot collide",
    )
    ap.add_argument("--size", type=int, default=BLOCK_SIZE, help=f"block width (default {BLOCK_SIZE})")
    ap.add_argument(
        "--lanes",
        metavar="A,B,C",
        help="every lane in this wave — the slot is this lane's index in it, so blocks cannot collide",
    )
    ap.add_argument("--bump", choices=("release", "change", "fix"), default="change")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if args.family is None:
        ap.print_help()
        return 2

    if args.family == "version":
        # ⚠ **BOTH QUESTIONS, ALWAYS, BECAUSE ANSWERING ONE READS AS ANSWERING
        # BOTH (`DEF-GOV-4023`).** "Is this number free" and "do the files in
        # this tree agree" are different questions, and a lane that hears a
        # clean answer to the first assumes the second.
        complaint = lockstep_complaint()
        if args.verify:
            taken, sentence = version_verdict(args.verify, version_shipped())
            print(sentence)
            # The blind spot, said out loud. It does not move the verdict — see
            # `tree_claim`'s docstring for why that would re-create DEF-GOV-3843.
            claim = tree_claim(args.verify)
            if claim:
                print(claim, file=sys.stderr)
            if complaint:
                print(complaint, file=sys.stderr)
            return 1 if (taken or complaint) else 0
        if not args.quiet:
            found = version_literals()
            print(
                "# write it in ALL of these: "
                + ", ".join(f"{rel} (now {v or 'NO LITERAL'})" for rel, v in found.items()),
                file=sys.stderr,
            )
        if complaint:
            print(f"# {complaint}", file=sys.stderr)
        print(next_version(args.bump))
        return 0

    if args.lane:
        roster = args.lanes.split(",") if args.lanes else None
        lo, hi, seen, warning = block(args.family, args.lane, args.size, roster)
        if warning:
            print(f"# WARNING: {warning}", file=sys.stderr)
        if not args.quiet:
            print(f"# {args.family} block for lane {args.lane!r}, read across: {', '.join(seen)}", file=sys.stderr)
            print(f"# use {lo}..{hi} and nothing else; --verify each one at push time", file=sys.stderr)
        print(f"{lo}-{hi}")
        return 0

    if args.verify:
        # ⚠ **REMOTE BRANCHES ONLY — not this tree, not local HEAD**
        # (`DEF-GOV-3843`). See `numbers`: by push time this lane's own row is
        # written, so counting its own worlds answers TAKEN every time.
        remotes = [r for r in _sources() if r.startswith("refs/remotes/")]
        found, _ = numbers(args.family, sources=remotes)
        n = int(re.sub(r"\D", "", args.verify))
        if n in found:
            # ⚠ SAY WHICH KIND OF TAKEN IT IS (`DEF-GOV-7814`). A number inside
            # somebody's RESERVED block is not a number a sibling pushed a row
            # for, and telling a reader it was pushed sends them looking for a
            # register row that does not exist. Law 7 habit 3: the output has to
            # distinguish the cases to a READER, not merely to an exit code.
            reserved, _ = _reserved(args.family, sources=remotes, ceiling=max(found))
            if n in reserved:
                print(
                    f"{args.family} {args.verify}: TAKEN — it is inside a block another lane "
                    f"RESERVED in {RESERVATIONS_PATH} (no row for it yet, which is exactly why "
                    f"a register-only check missed this and 7700-7702 collided on 2026-09-28). "
                    f"Take a number outside every open block."
                )
            else:
                print(f"{args.family} {args.verify}: TAKEN — a sibling pushed it. Renumber before you commit")
            return 1
        print(f"{args.family} {args.verify}: still free on every branch (this tree not counted)")
        return 0
    found, seen = numbers(args.family)
    nxt = (max(found) + 1) if found else 1
    if not args.quiet:
        print(f"# {len(found)} {args.family} number(s) across: {', '.join(seen)}", file=sys.stderr)
    print(nxt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
