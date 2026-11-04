#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-039 finding 1 — *"an electric+gas tenant signs up successfully
#           and gets nothing"*. PO 2026-08-17 (CR-010 B-9 + mandate 4), verbatim:
#           *"full list for all services - they can always select what they want
#           out of it; more is better ; less is contraint"*, re-confirmed
#           2026-08-27 (*"yes I already confirmed it"*).
# Rules:    BR-RAT-024 (CONFIRMED — the platform catalogue is TEN services, in
#           the seed order) · BR-MET-003 (a tenant may only hold a service point
#           for a service it has ENABLED) · CLAUDE.md line 1 (*"ten, not six"*)
# Defects:  DEF-1706 (names the ten-services signup lane) · the CR-039 A2 escape
#           itself: SIGNUP_SERVICES held SIX for ten days after the ruling, and
#           `SignupWizard.tsx` says why in its own comment — *"no gate in this
#           repo compares a frontend constant to a database seed"*
# ───────────────────────────────────────────────────────
"""G47 — a hand-written service list must be the platform's ten.

WHY THIS GATE EXISTS, IN THE WORDS OF THE FILE IT WAS WRITTEN FOR
------------------------------------------------------------------
`07-frontend/src/features/tenancy/SignupWizard.tsx` carries this comment above
the constant that was wrong:

    **Only this constant stayed at six**, so a storm-water, solar, thermal or
    battery utility signed up successfully and got every service it sells
    `enabled=False` — silently, because the chip was never on the page. […]
    and **no gate in this repo compares a frontend constant to a database
    seed**, which is why it survived ten days after being ruled.

That last clause is this gate's whole specification. The platform has seeded ten
services since migration 0001; a screen offered six with a green tick; and every
existing gate compares a frontend artefact to another frontend artefact
(G13/G40/G15/G18/G31/G43/G44/G45) or a document to a document (G1/G2/G12/G28).
**Nothing crossed into the database.** The check is therefore not a widening of
any of them; it is the first of a different kind.

WHY IT IS NOT `signupServices.test.ts`, WHICH ALREADY EXISTS
-------------------------------------------------------------
CR-039 A2 shipped a vitest test that parses `SERVICE_SEED` out of the Django
migration and asserts `SIGNUP_SERVICES` deep-equals it. **That test is correct
and this gate does not replace it** — it also asserts ORDER, which this gate
deliberately does not (see below).

It checks **one constant in one file.** DEF-1702's lesson, quoted in G45's own
docstring, is *"the whole argument for a sweep over a walk"*: G45's sweep found
a THIRD offender that neither the CR nor the Product Owner had named. The same
is true here — the repo holds **fourteen** hand-written enumerations of the
service catalogue across the frontend, the backend, a fixture and a migration,
and a test pinned exactly one of them. A test guards the file it names. A gate
asks the whole tree, on every commit, including files that do not exist yet.

WHAT IT CHECKS — TWO CLAUSES, BOTH HARD ZERO
---------------------------------------------
The authority is read at run time from
`06-backend/apps/tenancy/migrations/0001_initial.py::SERVICE_SEED`. It is never
typed here: a gate that carries its own copy of the list it is policing is the
fifteenth copy, and would go green on the day the seed changed underneath it.

**(a) A FILE THAT ENUMERATES THE CATALOGUE MUST ENUMERATE ALL OF IT.**
A *catalogue enumeration* is a bracketed collection — `[…]`, `{…}`, `(…)` — in
which **three or more distinct seed codes appear, each exactly once**. The file
holding one must name all ten somewhere in it.

Three design decisions there, each earning its place:

* **Three, not two.** Two codes together are a pair with a reason (`("sewer",
  "trash")` is BR-RAT-015's companion pair, `["electric", "water"]` is one
  fixture account's two services). Three is where a list starts claiming to be
  *the list*.
* **Each exactly once.** This is what separates an ENUMERATION from data
  ANNOTATED by service, and it is load-bearing rather than tidy. Without it the
  26-entry `uoms` array in `lookup_defaults.json` — where `"service": "trash"`
  appears three times and `"storm_water"` twice, because units are scoped to
  services — reads as an eight-of-ten catalogue and fails. It is a list of
  UNITS. A catalogue names each service once.
* **The union across the FILE, not the collection.** `newConnectShared.tsx`
  declares `METERED_SERVICES` (4), `DERIVED_SERVICES` (1), `CAPACITY_SERVICES`
  (2) and `FLAT_SERVICES` (3) — a deliberate PARTITION, and a per-collection
  rule would fail all four while the file is exhaustively correct. Summing the
  file is what makes a partition lawful and an omission visible, which is
  exactly the distinction the escape turned on.

**(b) AN ENUMERATION MAY NOT NAME A SERVICE THE SEED DOES NOT HAVE.**
The same boundary, travelled the other way. A code the platform never seeded is
a chip that posts a value `_validate_signup` refuses, or a map key nothing will
ever look up — dead in exactly the way clause (a)'s absences are dead, and
invisible for the same reason. Measured at zero today; `"stormwater"` (no
underscore) exists in one test file and is the near-miss this clause is shaped
for.

WHAT IT DELIBERATELY DOES NOT CHECK — AND THIS ONE WAS TRIED FIRST
-------------------------------------------------------------------
**ORDER.** CLAUDE.md fixes the seed order and it was the obvious third clause.
It was written, run, and **withdrawn on the evidence**, because it fails two
places that are deliberately and correctly not in seed order:

* `features/rating/ratingShared.tsx` groups **r10's six first, then the four
  OQ-273 added afterwards**, and says so at length — the six carry r10's own
  one-letter badges and the four carry two-letter badges precisely because they
  are a later group.
* `apps/ledger/chart.py` orders services by **GL account code**, which is the
  chart's order and not the catalogue's.

Both are ruled. G45's docstring states the principle and it applies here
verbatim: *"a gate that argues with a ruling gets switched off."* Order on the
one list where it is signed — the signup chips — is already asserted by
`signupServices.test.ts`, which is the right instrument for a per-file rule.

**WHETHER A TENANT HAS ENABLED THE SERVICE.** That is `tenant_services` at run
time and no source-reading check can see it. BR-MET-003 governs it and
`apps/metering/seams.enabled_service_codes` answers it.

PARTIAL BY RULE — FOUR NAMED FILES, EACH WITH ITS RULING
----------------------------------------------------------
Four backend files hold a *deliberately* partial list. Every one states its
reason in prose already — and **a comment claiming a guarantee is not the
guarantee** (hard-won law 1), which is why the exemption lives here, in the
check, where changing it is a diff someone reviews. They are named, never
pattern-matched, on the precedent of G45's `NOT_A_LIST_SCREEN` and G37's icon
allowlist.

⚠ **THE LIST MAY SHRINK AND MAY NEVER GROW.** A fifth entry is a new partial
list, which is the defect this gate exists to catch.

COMMENTS AND DOCSTRINGS ARE STRIPPED (DEF-741)
-----------------------------------------------
Prose ABOUT the rule must never satisfy or trip the rule. This is not
theoretical here: `apps/metering/import_rules.py` carries a measured worked
example in a **docstring** — *"the row goes from `['water','sewer','trash']` to
`['water']`"* — and the first run of this gate reported that paragraph as a
three-of-ten catalogue enumeration. Python docstrings are STRINGS, not `#`
comments, so stripping `#` alone is not enough; both triple-quote forms go too.
⚠ Block-first stripping is a bug on the TS side (G45 carries the same note): a
`//` line spelling a path with a star in it contains `/*`, which opens a comment
that closes at the next `*/` anywhere below. Line comments first.

BASELINE ZERO, HARD, ON BOTH CLAUSES
-------------------------------------
Not a debt register. The tree is at zero because the CR-039 A2 lane fixed the
frontend on 2026-08-27; this gate is what stops it drifting back, and what
extends the guarantee to the thirteen enumerations that lane did not touch.

PROVED RED BEFORE TRUSTED GREEN (hard-won law 7) — the verbatim failure is in
the `RED PROOF` block below, taken in a throwaway `git worktree` at `97e745c~1`,
the commit before the signup list was widened, so the shared tree was never
mutated.

Python 3.12 stdlib only. Safe to run from any cwd. Nothing here ever writes.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
#: ⚠ **THE AUTHORITY IS THE MIGRATIONS DIRECTORY AND NOT ONE FILE, AND THIS GATE
#: READ ONE FILE UNTIL 2026-09-02 (`DEF-3092`, third site).** `0001_initial.py`
#: has run on every database that exists and can therefore never gain a row, so
#: an ELEVENTH service has to arrive in its own migration — `CR-063` put `fire`
#: in `0033_cr063_fire_service.py`. **This gate is the merge-blocking check whose
#: entire job is "the platform catalogue and every enumeration of it agree", and
#: pointed at `0001` alone it reported PASS at TEN services while the catalogue
#: held eleven and every front-end list was missing fire.** A gate that cannot
#: see the thing it polices is worse than no gate, because it is trusted — the
#: same lesson `DEF-524` taught with a hardcoded prototype path.
SEED_MIGRATIONS_DIR = ROOT / "06-backend" / "apps" / "tenancy" / "migrations"
#: Kept so the SKIP branch below still names a concrete file when the tree is
#: not a checkout of this repo at all.
SEED_MIGRATION = SEED_MIGRATIONS_DIR / "0001_initial.py"
BACKEND = ROOT / "06-backend"
FRONTEND_SRC = ROOT / "07-frontend" / "src"

#: Fewer than this many distinct codes in one collection is a PAIR with a
#: reason, not a claim to be the catalogue. See the docstring.
ENUMERATION_FLOOR = 3

#: 0 after CR-039 A2. An invariant, not a debt register — do NOT raise either.
INCOMPLETE_BASELINE = 0
UNKNOWN_CODE_BASELINE = 0

#: `SERVICE_SEED = [ ("code", "Name"), … ]` inside the platform migration.
#: `SERVICE_SEED = [ … ]` in `0001_initial.py`, `FIRE_SEED = [ … ]` in
#: `0033_cr063_fire_service.py`, and whatever a twelfth service names its own.
#: The alternation is what stops this gate needing an edit per service.
#: ⚠ **THE CLOSING BRACKET IS NOT ANCHORED TO A LINE START, AND THAT IS A FIX
#: RATHER THAN A LOOSENING.** The old pattern ended `^\]`, so it matched only a
#: list formatted one entry per line — and `FIRE_SEED = [("fire", "Fire")]` is a
#: single line, so this gate went on reporting TEN services with the eleventh
#: sitting in the file it was reading. **A gate that depends on somebody's
#: formatting is a gate that fails silently**, which is the whole of `DEF-3092`.
#: Non-greedy `(.*?)\]` is safe here because a service seed holds tuples of
#: string literals and no nested bracket, so the first `]` IS the closing one.
SEED_BLOCK = re.compile(
    r"^(?:SERVICE_SEED|FIRE_SEED)\s*[:=][^=]*?\[(.*?)\]", re.M | re.S
)
SEED_ENTRY = re.compile(r"""\(\s*["']([a-z_]+)["']\s*,""")

#: A quoted literal, OR a bare identifier in object-key / assignment position at
#: the start of a line. The second form is how `SERVICE_BADGES` and
#: `RATIFIED_SERVICE_SEED` name their services — TS and Python object keys are
#: unquoted, so a literal-only reader is blind to half the enumerations here.
CODE_TOKEN = re.compile(r"""["']([A-Za-z0-9_\-]+)["']|^[ \t]*([A-Za-z0-9_]+)\s*[:=]""", re.M)
BRACKETS = re.compile(r"[\[\]{}()]")
SCAN = re.compile(CODE_TOKEN.pattern + r"|[\[\]{}()]", re.M)

#: DELIBERATELY PARTIAL, each by a ruling quoted in the named file. The list may
#: SHRINK and may never GROW (see the docstring).
PARTIAL_BY_RULE: dict[str, str] = {
    # CR-068 wave A (2026-09-03): the customer portal's demo utility SELLS four of
    # the eleven — Water · Sewer · Trash · Electric — by the stories' own signed
    # test data (US-CWP-001 §4, US-CWP-070 §4: *"Services Water, Sewer, Trash,
    # Electric"*), and Oak Ridge sells one. A fixture that named all eleven would
    # be a different utility from the one seventy-four stories are written
    # against. The catalogue itself is read at run time (`tenancy_seam.
    # enabled_services`), never enumerated by the portal.
    "06-backend/apps/portal/sample_data.py": "US-CWP-001 §4 · US-CWP-070 §4 (Pine Hill sells four; Oak Ridge one)",
    # ⚠ **THE PLATFORM'S OWN FIRST MIGRATION IS PARTIAL AND MUST STAY PARTIAL
    # (`CR-063`, 2026-09-02).** `SERVICE_SEED` in `0001_initial.py` names TEN and
    # the catalogue is ELEVEN, and that is not a gap to close: **`0001` has run
    # on every database that exists, so editing it changes nothing anywhere and
    # a service appended to it would never reach a single tenant.** An eleventh
    # service therefore arrives in its own migration — `fire` is in
    # `0033_cr063_fire_service.py` — which is exactly how `BR-RAT-024`'s
    # "APPENDED, never inserted, nothing renumbered" is achieved in a database
    # that is already live for a customer.
    #
    # This gate READS every migration in that directory, so the catalogue it
    # polices is complete; what is exempt is the expectation that any ONE
    # migration enumerates the whole of it. A twelfth service will make `0033`
    # partial in the same way and for the same reason, and it belongs here too.
    "06-backend/apps/tenancy/migrations/0001_initial.py": (
        "SERVICE_SEED — the ORIGINAL ten, and it can never be more. This migration "
        "has already run on every database in existence, so a row added here reaches "
        "nobody; BR-RAT-024's eleventh service (`fire`, CR-063, PO 2026-09-02) is "
        "seeded by `0033_cr063_fire_service.py` instead. The catalogue this gate "
        "checks against is the UNION of every tenancy migration, which is why the "
        "count above reads eleven while this file names ten"
    ),
    # ⚠ **SEWER HAS NO SIZE CLASSES BY RULING, AND THAT IS THE WHOLE ABSENCE
    # (`CR-065`, 2026-09-02).** `RATIFIED_CODES` maps each service to the size
    # classes the ratified list gives it, and sewer is priced as a SHARE of the
    # water usage charge (`BR-RAT-015`, PO Q&A R1 closing `OQ-008`) — it reads no
    # register of its own, so there is nothing for a size class to size. Adding
    # `"sewer": ()` would say "we checked and there are none", which is true;
    # naming it here says the same thing where a reader looks for it, and keeps
    # the dict a map of services that HAVE sizes.
    #
    # Thermal STEAM is absent for the OTHER reason and it matters that the two
    # never collapse: it was put to the PO as a DIMENSION with no boundaries
    # (`OQ-560`, OPEN), so nobody has ruled it. One is a finished decision, the
    # other is money nobody has priced.
    "06-backend/apps/tenancy/migrations/0035_cr065_size_class_service_backfill.py": (
        "RATIFIED_CODES — the size classes each service has, transcribed from "
        "BR-TEN-171. TEN services because SEWER IS RULED TO HAVE NONE: it is a share of "
        "the water usage charge (BR-RAT-015) and reads no register, so there is nothing "
        "to size. Naming sewer here would seed a service with an empty tuple and change "
        "no row in any database"
    ),
    "06-backend/apps/tenancy/services.py": (
        "SERVICE_DEFAULT_UOMS — US-TEN-007 TC-1. Six services because r10 SET-03 draws a "
        "primary UoM for exactly six; sewer is an em-dash and solar/thermal_heat/battery are "
        "drawn Off with no units. Its own comment: 'A service absent from this map is a "
        "service the DESIGN has not named units for, not one we forgot.' Adding the four "
        "would be inventing units, which rule 3 forbids"
    ),
    "06-backend/apps/metering/services.py": (
        "RATIFIED_SERVICE_SEED — CR-038 A1, BR-MET-120. Seven services, and the three "
        "absences are each ratified: trash and storm_water are never READ (no read-validation "
        "row can exist for an unread service) and broadband is DEFERRED under CR-038 Open 7 "
        "(no register exists to read). tests/test_cr038_s64_service_settings.py asserts every "
        "figure, so drift there goes RED on its own"
    ),
    "06-backend/apps/metering/migrations/_0031_helpers.py": (
        "the migration that PLANTS the seed above — same seven services, same three ratified "
        "absences. A migration must write what the ratified table holds, not more"
    ),
    "06-backend/apps/rating/sample_data.py": (
        "BR-RAT-088's `is_base` charge codes, and THE FILE ALREADY NAMES ALL TEN — in "
        "THREE literals, split by the ROLE a service plays in the seeded estate rather "
        "than by the catalogue. `BASE_CHARGE_CODES` holds water (twice — BR-RAT-108's "
        "residential $8.00 and commercial $15.00), sewer and trash; `BACKBONE_BASE_CODE` "
        "holds the four METERED backbones; `CAPACITY_BASE_CODE` holds the three CAPACITY "
        "companions (DEF-3156). **The detector cannot see the first one**: its `all(n == "
        "1)` clause drops any literal naming a code twice, which is exactly what "
        "BR-RAT-108's one-service-two-classes shape does to water. So the three absences "
        "are an artefact of the scan and not a partial list — merging the maps to satisfy "
        "it would put a base that varies by customer class beside one that does not, "
        "which is the distinction BR-RAT-088's own docstring warns fails silently. "
        "ADDED 2026-09-02; this file was ALREADY an offender at 4/10 before that lane "
        "touched it, and the entry closes a pre-existing FAIL rather than a new one"
    ),
    "06-backend/core/sample_fixture.py": (
        "CR030_OVERFLOW_SERVICES — B18 TC-ACC-4, as corrected 2026-08-24: the '+3' overflow "
        "chip needs EXACTLY EIGHT services on one unit ('6 - 5 = 1, not 3 - the [shot]'s +3 "
        "needs EIGHT'). Eight is the assertion, not an omission; its own comment reads 'These "
        "are CLAUDE.md's ten in seed order, first eight'"
    ),
    # Added 2026-09-30 by the final bulk-run lane. A TEST-DATA seed, and the four
    # are the journey's own world, not a catalogue somebody can pick from.
    "06-backend/apps/tenancy/management/commands/_j73_scale.py": (
        "J73's scale world (08-qa/01-e2e/journeys/J73-bulk-run-breakdown-and-scale.md, "
        "'--accounts N'): every cloned account is on ONE four-service plan — water, "
        "electric, trash, sewer — because S1-S4 time a Check over a known shape. The "
        "catalogue is read from tenancy at run time; this file enumerates a plan, not it"
    ),
}


def _blank(match: re.Match[str]) -> str:
    """Replace a comment with spaces, preserving every offset and newline."""
    return re.sub(r"\S", " ", match.group(0))


def _strip_ts(text: str) -> str:
    """Blank TS/JS comments, LINE COMMENTS FIRST (DEF-741 — see the docstring)."""
    text = re.sub(r"//[^\n]*", lambda m: " " * len(m.group(0)), text)
    return re.sub(r"/\*.*?\*/", _blank, text, flags=re.S)


def _strip_py(text: str) -> str:
    """Blank Python docstrings AND `#` comments.

    Docstrings first: they are STRINGS, so a `#` inside one is not a comment and
    blanking `#` lines first would leave the docstring's own quotes unbalanced.
    """
    text = re.sub(r'"""(?:[^"\\]|\\.|"(?!""))*"""', _blank, text)
    text = re.sub(r"'''(?:[^'\\]|\\.|'(?!''))*'''", _blank, text)
    return re.sub(r"#[^\n]*", lambda m: " " * len(m.group(0)), text)


def seed_codes() -> list[str]:
    """The platform catalogue, READ from the migrations that seed it.

    Never a literal in this file: a gate carrying its own copy of the list it
    polices is one more copy to drift, and would pass on the day the seed moved.

    ⚠ **EVERY tenancy migration, in migration-number order — see the note on
    `SEED_MIGRATIONS_DIR` for why one file was not enough and what it cost.**
    The order is the DATABASE's order, which is also `BR-RAT-024`'s seed order,
    so a code appended in a later migration lands at the end of this list exactly
    as it lands at the end of the catalogue. Duplicates are impossible by
    construction (a code is seeded once) and are dropped rather than trusted, so
    a migration that re-states an existing code cannot inflate the count.
    """
    codes: list[str] = []
    for path in sorted(SEED_MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.py")):
        for block in SEED_BLOCK.finditer(path.read_text("utf-8", errors="replace")):
            for code in SEED_ENTRY.findall(block.group(1)):
                if code not in codes:
                    codes.append(code)
    return codes


def catalogue_enumerations(text: str, codes: set[str]) -> list[set[str]]:
    """Every SMALLEST bracketed collection naming >=3 seed codes, each once.

    Smallest-enclosing rather than outermost: `SIGNUP_SERVICES` is an ARRAY of
    per-service OBJECTS, so its codes sit one level deeper than the collection
    that means "the catalogue". A collection that does not itself qualify hands
    its codes up to its parent, which is what makes the array the answer there
    and the object the answer in `SERVICE_BADGES`.
    """
    stack: list[list[str]] = []
    found: list[set[str]] = []
    for match in SCAN.finditer(text):
        token = match.group(0)
        if token in "[{(":
            stack.append([])
            continue
        if token in "]})":
            if not stack:
                continue
            inner = stack.pop()
            counts = Counter(inner)
            if len(counts) >= ENUMERATION_FLOOR and all(n == 1 for n in counts.values()):
                found.append(set(counts))
            elif stack:
                stack[-1].extend(inner)
            continue
        name = match.group(1) or match.group(2)
        if name in codes and stack:
            stack[-1].append(name)
    return found


def _sources() -> list[tuple[str, str]]:
    """Every non-test frontend and backend source, comments already blanked."""
    out: list[tuple[str, str]] = []
    if FRONTEND_SRC.exists():
        for path in sorted(FRONTEND_SRC.rglob("*.ts")) + sorted(FRONTEND_SRC.rglob("*.tsx")):
            rel = path.relative_to(ROOT).as_posix()
            if ".test." in path.name or "/i18n/" in rel:
                continue
            out.append((rel, _strip_ts(path.read_text("utf-8", errors="replace"))))
    if BACKEND.exists():
        for path in sorted(BACKEND.rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if "/tests/" in rel or path.name.startswith("test_"):
                continue
            out.append((rel, _strip_py(path.read_text("utf-8", errors="replace"))))
    return out


def measure(sources: list[tuple[str, str]], seed: list[str]) -> tuple[list[str], list[str]]:
    """`(incomplete, unknown)` — clause (a)'s files and clause (b)'s files."""
    codes = set(seed)
    incomplete: list[str] = []
    unknown: list[str] = []
    for rel, text in sources:
        enumerations = catalogue_enumerations(text, codes)
        if not enumerations:
            continue
        named: set[str] = set().union(*enumerations)
        missing = [code for code in seed if code not in named]
        if missing and rel not in PARTIAL_BY_RULE:
            incomplete.append(f"{rel} (names {len(named)}/{len(seed)}, missing {', '.join(missing)})")
    # Clause (b) reads the whole token stream: a code the seed does not have is
    # not a seed code, so it can never appear inside a detected enumeration.
    near_miss = re.compile(
        r"""["'](%s)["']""" % "|".join(re.escape(c) for c in _near_misses(seed))
    )
    for rel, text in sources:
        for match in near_miss.finditer(text):
            unknown.append(f"{rel}: `{match.group(1)}` is not a seeded service code")
    return incomplete, unknown


def _near_misses(seed: list[str]) -> list[str]:
    """Spellings a service code is plausibly mistyped as, derived FROM the seed.

    Derived rather than listed, so a new service brings its own near-misses
    with it. DEF-050's lesson, in G19's words: *"a search shaped by the bug you
    already know about finds only that bug."*
    """
    out: set[str] = set()
    for code in seed:
        if "_" in code:
            out.add(code.replace("_", ""))
            out.add(code.replace("_", "-"))
            out.add(code.split("_")[0])
            out.add(code.split("_")[-1])
    return sorted(out - set(seed))


def selftest(seed: list[str]) -> list[str]:
    """Shown to BITE on planted text before it is trusted on the real tree.

    A gate that has never failed has not been shown to be able to. This runs on
    every invocation, so a refactor that blinded the reader is a FAIL here
    rather than a silent green — G45's `selftest()` shape.
    """
    problems: list[str] = []
    # ⚠ **ELEVEN SINCE 2026-09-02 (`CR-063`, `BR-RAT-024` amended, `fire` APPENDED
    # at position 11).** This is a COUNT and not a list on purpose — the list is
    # what the gate reads and pinning it here would be the second copy the whole
    # file exists to avoid — and it is here so that a refactor which BLINDS the
    # reader fails loudly. It did exactly that today: the reader was widened to
    # the whole migrations directory, this clause said 10, and the FAIL is what
    # proved the eleventh service had become visible.
    if len(seed) != 11:
        problems.append(
            f"read {len(seed)} service(s) out of the tenancy migrations, expected 11 "
            "(BR-RAT-024 as amended 2026-09-02). If a TWELFTH has been ruled, move "
            "this number with it; if not, the reader has been blinded."
        )
        return problems
    codes = set(seed)
    # ⚠ **EVERY PLANTED FIXTURE BELOW IS DERIVED FROM `seed`, NEVER FROM A COUNT
    # TYPED HERE (`CR-063`).** These clauses used to read `seed[0]` … `seed[9]` and
    # split the list into literal groups of 3/3/4, so on the day an ELEVENTH
    # service arrived the "complete" fixtures covered ten of eleven and this gate
    # failed its own self-test — correctly, and for a reason that had nothing to
    # do with what it was checking. **A self-test wired to a specific catalogue
    # size stops being a self-test the first time the catalogue moves.**
    short = "".join(f'  {{ code: "{c}", labelKey: "x.{c}" }},\n' for c in seed[:6])
    whole = "".join(f'  {{ code: "{c}", labelKey: "x.{c}" }},\n' for c in seed)

    # ⚠ THE ESCAPE ITSELF: the signup wizard's six-of-N array.
    if not measure([("planted.tsx", f"const S = [\n{short}]\n")], seed)[0]:
        problems.append("does not bite the six-of-N array that was the CR-039 escape")
    if measure([("planted.tsx", f"const S = [\n{whole}]\n")], seed)[0]:
        problems.append("bites a COMPLETE array — false positive")

    # A PARTITION across one file is lawful; the union is what is checked.
    # Three groups covering the WHOLE seed, however long it is.
    cut = len(seed) // 3
    groups = [seed[:cut], seed[cut : 2 * cut], seed[2 * cut :]]
    partition = "".join(
        "const %s = [%s]\n" % (name, ", ".join(f'"{c}"' for c in group))
        for name, group in zip("ABC", groups)
    )
    if measure([("planted.tsx", partition)], seed)[0]:
        problems.append(
            "bites a file whose partitions cover the WHOLE catalogue — the "
            "newConnectShared shape"
        )
    if not measure([("planted.tsx", partition.rsplit("const C", 1)[0])], seed)[0]:
        problems.append("passes a file whose partitions leave a group out")

    # A PAIR is not a claim to be the catalogue.
    if measure([("planted.tsx", f'const P = ["{seed[3]}", "{seed[4]}"]\n')], seed)[0]:
        problems.append("bites a two-service pair — the floor is not being applied")

    # ⚠ DATA ANNOTATED BY SERVICE IS NOT AN ENUMERATION. This is the
    # `lookup_defaults.json` uoms shape: a repeated code means a list OF
    # SOMETHING ELSE, scoped by service.
    annotated = (
        f'const U = [\n  {{ code: "cart", service: "{seed[4]}" }},\n'
        f'  {{ code: "pickup", service: "{seed[4]}" }},\n'
        f'  {{ code: "yd3", service: "{seed[4]}" }},\n'
        f'  {{ code: "ERU", service: "{seed[5]}" }},\n'
        f'  {{ code: "ksf", service: "{seed[5]}" }},\n'
        f'  {{ code: "EDU", service: "{seed[3]}" }},\n]\n'
    )
    if measure([("planted.tsx", annotated)], seed)[0]:
        problems.append("reads service-SCOPED data as a catalogue enumeration (the uoms shape)")

    # Prose can neither trip the rule nor satisfy it — BOTH languages.
    if measure([("planted.tsx", _strip_ts(f"// const S = [\n{short}// ]\n"))], seed)[0]:
        problems.append("counts a COMMENTED partial list as a real one (TS)")
    doc = f'def f():\n    """the row goes from [{", ".join(chr(34)+c+chr(34) for c in seed[:3])}] to it."""\n    return 1\n'
    if measure([("planted.py", _strip_py(doc))], seed)[0]:
        problems.append("counts a partial list inside a PYTHON DOCSTRING as a real one")

    # Clause (b): a code the seed does not have.
    typo = _near_misses(seed)[0]
    if not measure([("planted.tsx", f'const s = "{typo}"\n')], seed)[1]:
        problems.append(f"does not bite `{typo}`, a code the platform never seeded")
    if measure([("planted.tsx", f'const s = "{seed[0]}"\n')], seed)[1]:
        problems.append("bites a real seed code as unknown — false positive")

    # An exempted file is exempt, and only by NAME.
    exempt = next(iter(PARTIAL_BY_RULE))
    if measure([(exempt, f"S = [\n{short}]\n")], seed)[0]:
        problems.append("does not honour PARTIAL_BY_RULE")
    return problems


def run() -> tuple[str, str]:
    """`("PASS"|"FAIL"|"SKIP", detail)` — the runner's contract, not a bool."""
    if not SEED_MIGRATIONS_DIR.is_dir():
        return "SKIP", f"{SEED_MIGRATIONS_DIR.relative_to(ROOT).as_posix()} does not exist"

    seed = seed_codes()
    if not seed:
        return (
            "FAIL",
            "could not read any service seed out of "
            f"{SEED_MIGRATIONS_DIR.relative_to(ROOT).as_posix()} — this gate's authority is "
            "those migrations and it will not fall back to a copy of its own (see the "
            "docstring)",
        )

    broken = selftest(seed)
    if broken:
        return "FAIL", "the gate's own self-test did not bite: " + "; ".join(broken)

    incomplete, unknown = measure(_sources(), seed)
    note = (
        f"BR-RAT-024: the platform seeds {len(seed)} service(s); "
        f"(a) {len(incomplete)} incomplete enumeration(s) (baseline {INCOMPLETE_BASELINE}), "
        f"(b) {len(unknown)} unseeded code(s) (baseline {UNKNOWN_CODE_BASELINE}); "
        f"{len(PARTIAL_BY_RULE)} file(s) partial by a named ruling; self-test: 11/11 clauses bite"
    )

    # ── RED PROOF ─────────────────────────────────────────────────────────
    # Run in a throwaway `git worktree` at 97e745c~1 — the commit before
    # CR-039 A2 widened the signup chips — so the shared tree was never
    # touched. It names the file the Product Owner's escape was in, and the
    # four services a utility could not tick:
    #
    #   FAIL: BR-RAT-024: the platform seeds 10 service(s); (a) 1 incomplete
    #   enumeration(s) (baseline 0), (b) 0 unseeded code(s) (baseline 0);
    #   4 file(s) partial by a named ruling; self-test: 11/11 clauses bite.
    #   1 file(s) enumerate the service catalogue and do not enumerate all of
    #   it. A list that names some of the ten is a list a utility selling the
    #   others cannot use: the chip is never on the page, signup succeeds, and
    #   every service it sells lands enabled=False (CR-039 finding 1). Add the
    #   missing codes, or — if the list is partial by a RULING — name the file
    #   in PARTIAL_BY_RULE with that ruling. Offender(s):
    #   07-frontend/src/features/tenancy/SignupWizard.tsx (names 6/10, missing
    #   storm_water, solar, thermal_heat, battery)
    failures: list[str] = []
    if len(incomplete) > INCOMPLETE_BASELINE:
        failures.append(
            f"{len(incomplete)} file(s) enumerate the service catalogue and do not enumerate "
            "all of it. A list that names some of the ten is a list a utility selling the "
            "others cannot use: the chip is never on the page, signup succeeds, and every "
            "service it sells lands enabled=False (CR-039 finding 1). Add the missing codes, "
            "or — if the list is partial by a RULING — name the file in PARTIAL_BY_RULE with "
            "that ruling. Offender(s):\n    " + "\n    ".join(incomplete)
        )
    if len(unknown) > UNKNOWN_CODE_BASELINE:
        failures.append(
            f"{len(unknown)} reference(s) to a service code the platform never seeded. It "
            "cannot match a `services.code` row, so it is a chip that posts a value "
            "`_validate_signup` refuses, or a map key nothing will ever read. Use the seeded "
            "spelling. Offender(s):\n    " + "\n    ".join(unknown)
        )
    if failures:
        return "FAIL", f"{note}. " + "\n  ".join(failures)
    return "PASS", note


def main() -> int:
    """Run this gate from the command line.

    ⚠ A `run()` with no main block exits 0 with no output, which is
    indistinguishable from a pass to the eye and to `$?` (DEF-672).
    """
    status, message = run()
    print(f"{status}: {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
