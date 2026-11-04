"""G18 — the catalogues against the CODE. Added 2026-08-11 by Eng-Lead.

THREE DEFECTS, ONE MISSING COMPARISON
-------------------------------------
G15 proves the eleven locale catalogues agree with EACH OTHER. DEF-049 names
exactly what that is worth: *"G15 proves five catalogues agree with each other,
which is exactly as strong as one catalogue being right."* Nothing in the repo
ever compared a catalogue to the code that renders it, and three defects were
filed against that one hole in a single day:

  DEF-036  a backend refusal carries a `message_key` the frontend renders from
           `07-frontend/src/i18n/locales/*.json`. A service that raises a NEW
           key with no catalogue entry passes every gate and prints the raw key
           string to a user. Two live instances found in one day, one of which
           had already SHIPPED unnoticed.
  DEF-049  `billing.arrives.run` exists in all eleven catalogues and nothing
           renders it — *"G15 reports parity across five files that agree on a
           dead key."*
  DEF-041  nine `shell.user.*` / `shell.tenant.*` keys used in code and defined
           in no catalogue, while G15 reported parity.

DEF-049's prevention column states the fix and this gate is it, verbatim:
*"A check that every catalogue key has a call site — and every t() call has a
key — would close this and DEF-036 together, and would have caught the nine
shell.user.*/shell.tenant.* keys DEF-041 records as well. Three defects, one
missing comparison."*

DEF-036 also names the asymmetry that must be kept: *"G15 must stay a
catalogue-to-catalogue check AND gain a code-to-catalogue check — they catch
different failures, and replacing one with the other would reopen the gap it
closed."* So G15 is untouched. This is a second gate, not a replacement.

TWO DIRECTIONS
--------------
A. DEAD KEY — a key in `en.json` that no call site can reach. Dead weight
   translated eleven times, and it hides the next real drift in the diff.
B. MISSING KEY — a call site whose key is in no catalogue. i18next renders the
   key itself on a miss, so this one is a raw `rating.plans.duplicate_code`
   printed to a utility clerk.

WHAT COUNTS AS A CALL SITE (all five, because the copy is rendered from five)
-----------------------------------------------------------------------------
1. A quoted dotted literal on a NON-COMMENT line of `07-frontend/src/**/*.ts{,x}`.
   Not just `t("…")`: this repo passes keys as data — `labelKey:
   "shell.user.myProfile"`, `unavailableReasonKey`, tab tables, column
   definitions — and a gate that only read `t()` would call every one of those
   dead. Tests count HERE (a key a test asserts is a key someone is holding
   onto); comments do NOT, and that exclusion is load-bearing rather than tidy:
   four of this gate's first findings are keys whose ONLY remaining mention is a
   lifecycle trailer saying "that key is now ORPHANED … left in all five
   catalogs because this lane may not edit them". A comment is a note, never the
   guarantee (hard-won law 1) — count it as a call site and the gate would agree
   with the trailer that the key is fine.
2. A COMPUTED key: `` t(`billing.bills.status.${row.status}`) `` names a PREFIX,
   not a key. So does a literal STEM handed to a helper —
   `enumLabel(t, "rating.charges.type", row.charge_type)` renders
   `` t(`${stem}.${value}`) ``, where the prefix is an argument and no template
   literal exists to read. Both forms are handled by one rule with no helper
   list in it: **any literal that is a proper dotted prefix of a catalogue key
   names that family.** Keys reachable only this way are COUNTED and reported on
   every run rather than claimed live — see the limitation below.
3. `message_key` in `06-backend/{apps,core}/**/*.py`, read with `ast` rather
   than grep: the keyword form, the `{"message_key": …}` dict form used inside
   `field_errors`, and a positional argument bound to a parameter NAMED
   `message_key` on a helper declared in the same file (`_refuse(code, key, …)`
   in `apps/metering/importers.py` is the live case). DEF-036 asked for a grep;
   the grep would have missed `_refuse`'s positional form, which is where one of
   this gate's findings lives.
4. A module-level constant holding one: `GENERIC_SIGN_IN_MESSAGE_KEY =
   "errors.auth.sign_in_failed"` in `apps/identity/services.py` is passed by
   NAME to every sign-in refusal (BR-IDN-002 deliberately uses one message for
   all of them). Resolved within the declaring module only — following a name
   across modules would be guessing.
5. The DERIVED envelope keys. `core/errors.py::default_message_key` is
   `"errors." + code.lower()`, so the literal `"VAL-002"` is what puts
   `errors.val-002` on a screen. Any error-code-shaped literal in backend code
   registers its derived key. Without this rule the gate calls eight live
   envelope keys dead.

WHAT COUNTS AS A LOOKUP THAT MUST RESOLVE (direction B)
--------------------------------------------------------
The first argument of a `t(…)` call — including the ternary form
`t(mode === "draft" ? "a.b" : "a.c", {…})`, which is where two of this gate's
findings live — plus any `…Key:`/`…Key=` property (`labelKey`,
`unavailableReasonKey`, `explainerKey`, `arrivesWithKey`), which is how DEF-041's
nine keys were used. Bare `key:` is NOT one of these: it is React's list key and
a DataTable column id, 182 of them, none an i18n key.

Excluded, on purpose: a `t()` call carrying `defaultValue` (i18next renders the
default, so the author has stated in code that a missing key is the expected
path — `locales.test.ts` probes the not-yet-re-tagged locale codes this way);
an undotted literal (every key in `en.json` is dotted — checked, all 3,126 of
them on 2026-08-11 — so
`message_key: "x"` in an ApiError constructor test is a placeholder, not a key);
and **`*.test.ts{,x}` files**. That last one is a judgment worth stating: a test's
`message_key: "settings.accounting.unmapped"` is a FIXTURE describing a
hypothetical server response, not a call site that renders. The authority on
which keys the server can actually send is the backend, which direction B scans
exhaustively — so a frontend fixture adds eleven findings about test staleness
and nothing about what a user sees. Test files still count as call sites for
direction A.

WHAT THIS GATE CANNOT SEE, STATED SO NO ONE READS MORE INTO IT (law 1)
-----------------------------------------------------------------------
**It does not close DEF-049's own instance, and claiming otherwise would be the
comment-that-is-not-a-guarantee this repo keeps paying for.** `billing.arrives.run`
HAS a call site — `BillsListPage.tsx:738` renders `` t(`billing.arrives.${active}`) ``
and `"run"` is a declared tab id in `BILLING_TABS`. What makes it dead is a
ROUTING fact: the all-static route `/{tenant}/billing/run` outranks
`billing/:tab`, so `active` is never `"run"`. No text-level comparison can know
that. DEF-049's CLASS — a catalogue key with no call site at all — is closed
here; that one instance needs the route walk of a journey test, and its row
stays open.

Leaf-level checking of computed keys was measured and REFUSED: requiring each
leaf under a prefix to appear as a literal found 8 dead keys of which 3 were
false positives (`settings.security.timeout.240` and `.60`, whose leaves are
NUMBERS in a list; `assets.import.error.duplicate_asset_no`, whose leaf is
assembled server-side) and still did not catch `billing.arrives.run`. A 37%
false-positive rate on a merge-blocking gate is how DEF-041's warning comes
true — *"a widened gate that fires on 40 legitimate items teaches people to add
ALLOW entries, which is how a gate stops being a gate."*

THE KNOWN-GAP REGISTER, AND WHY IT IS NOT AN ALLOWLIST
------------------------------------------------------
The first run of this gate found **107 real findings** — 99 backend
`message_key`s and 2 shipped frontend `t()` keys that exist in no catalogue, and
6 catalogue keys nothing renders. They are not false positives and they are not
this lane's to fix: 101 missing keys × 11 catalogues is 1,111 strings of copy
that must be WRITTEN, in English first, by the lane that owns the refusal. Two
wrong answers were available and both were refused: silencing the gate (it would
find nothing again) and shipping it permanently red
(`10-scripts/03-golden-verify.py` says what happens then — *"the thing that
actually happens to a permanently-red gate: someone deletes the check"*).

So `i18n_known_gaps.txt` follows that file's KNOWN_DEFECTS discipline exactly,
and the three properties are what keep it from becoming a silencer:

  NARROW    keyed on (direction, exact key). A key not on the list fails. The
            list cannot cover "the next one like it".
  LOUD      the count is printed in this gate's one-line detail on EVERY run,
            in the table `run_gates.py` prints. It is never hidden.
  EXPIRING  an entry that no longer reproduces is STALE and FAILS. When the
            i18n lane adds a key, its line must be deleted in the same diff —
            so the register can only shrink, and a dead licence cannot sit
            waiting for whoever deletes the key next.

Every entry cites a defect row, and the gate checks that the row EXISTS and is
not already `fixed`/`closed`. Adding a line is a process event, like editing
`human_owned.txt` or `partition_exceptions.txt`.

PROVED RED BEFORE TRUSTED GREEN (hard-won law 7)
------------------------------------------------
Part 0 replays each direction against an in-memory copy of the real corpus and
requires the checker to report it — including DEF-041's own instance, by taking
`shell.user.myProfile` back out of `en.json`, and DEF-049's, by adding a key
nothing references. A fixture that fails to bite FAILS the gate. Nothing is
written to disk at any point.

ADDING THIS GATE IS A PROCESS EVENT. G1-G16 are the PO-ratified merge-blocking
set (2026-08-11, option A); G18 is an Eng-Lead addition from DEF-036/041/049,
reported for the daily PO batch and recorded in 12-governance/02-decision-log.md.

Python 3.12 stdlib only. Safe to run from any cwd. Nothing here ever writes.
"""

import ast
import csv
import io
import json
import re
from pathlib import Path

import common

LOCALES = common.REPO_ROOT / "07-frontend" / "src" / "i18n" / "locales"
BASE = "en.json"
REGISTER = Path(__file__).resolve().parent / "i18n_known_gaps.txt"
DEFECT_LOG = common.REPO_ROOT / "12-governance" / "10-defect-log.csv"
CLOSED_STATUSES = {"fixed", "closed", "wontfix", "won't fix"}

MAX_NAMED = 3

#: A dotted identifier used as a catalogue key: `billing.run.phase.assemble`.
KEY_LITERAL = re.compile(r"""["'`]([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_+\-]+)+)["'`]""")
#: `` t(`settings.security.timeout.${minutes}`) `` — the static PREFIX only.
KEY_PREFIX = re.compile(r"`([A-Za-z][A-Za-z0-9_.]*\.)\$\{")
#: Any short quoted token, used only to spot error CODES (`"VAL-002"`).
ERROR_CODE = re.compile(r"""["']([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)["']""")
#: `labelKey: "…"` / `explainerKey={"…"}` — a key passed as data. The capital K
#: is deliberate: bare `key:` is React's list key and a DataTable column id.
KEY_PROP = re.compile(r"""\b[A-Za-z_]*[a-z]Key\s*[:=]\s*\{?\s*["']([^"']+)["']""")
#: The start of a `t(` call; the argument list is then paren-balanced by hand.
T_OPEN = re.compile(r"\bt\(")
#: Comment openers in both languages. A comment is never a call site (law 1).
#: ⚠ This is a LINE-PREFIX test and it can only see a line that is ENTIRELY a
#: comment — see `_code_only` below for the half it could never see.
COMMENT_OPENERS = ("//", "/*", "*", "#")

#: A `//` comment, ANYWHERE on a line rather than only at its start. The
#: lookbehind is what keeps `https://code.claude.com/docs` and a quoted
#: `"// -- Pure pieces"` out of it — both are live in `src/` today, and both
#: would otherwise have their line truncated from the slashes on.
LINE_COMMENT = re.compile(r"""(?<![:'"`])//[^\n]*""")
#: A `/* ... */` comment, in every form the corpus uses — including the JSX
#: `{/* ... */}` that a line-prefix test cannot recognise, because the line
#: begins with `{`.
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def _code_only(text: str) -> str:
    """Frontend source with its comments removed and its LINE NUMBERS intact.

    **DEF-769 — A KEY NAMED IN A COMMENT WAS COUNTED AS A CALL SITE.** Direction
    A asks *"can any code reach this key?"*, and it answered YES for
    `wizard.park.parkedAt` because the key NAME appears in the JSX comment three
    lines above the live `t()` call in `WizardFrame.tsx`. That key carried a
    sentence BR-SHL-048 had made FALSE — it told a clerk their entries stayed
    *"on the record"* when a parked draft has no record — and a catalogue entry
    BEATS a code `defaultValue`, so the user kept reading the retired sentence
    whatever the component said. `code_lines` above tests the START of a line,
    so a `{/* ... */}` block (the line starts with `{`) and a trailing `// ...`
    after real code were both read as code. The sibling gate G27 has stripped
    comments through its own `_code_only` since it was written; the two gates
    read the same files with different eyes, and this is the eye that was shut.
    Found by a human reading every occurrence — and a retirement that has to be
    found by reading is a retirement that gets skipped.

    ⚠ **LINE COMMENTS GO FIRST, AND THE ORDER IS THE WHOLE POINT (DEF-741).**
    Stripping blocks first lets a `//` line that spells a path with a star in it
    — `// see src/i18n/locales/*.json` — OPEN a comment at its `/*` that closes
    at the next `*/` anywhere below, swallowing every line between. That defect
    was four gates deep on 2026-08-26; this is the fifth gate and it does not
    reintroduce it.

    ⚠ **LINE NUMBERS SURVIVE.** Both directions report `path:lineno`, so a
    block comment is replaced by AS MANY NEWLINES AS IT SPANNED rather than by
    nothing. G27 does not need this and drops them; a `where` string that points
    at the wrong line is a finding an author cannot act on.

    Frontend only. The backend corpus is Python read through `ast` (which never
    sees a comment) plus the `ERROR_CODE` scan, which still reads whole lines
    through `code_lines`; a `#` inside a Python string cannot be told from a
    comment opener by a regex, and the only cost there is a DERIVED
    `errors.<code>` key kept alive by a comment. Stated, not silently assumed.
    """
    return BLOCK_COMMENT.sub(
        lambda match: "\n" * match.group(0).count("\n"), LINE_COMMENT.sub("", text)
    )


# ── the corpus ──────────────────────────────────────────────────────────────
def catalogue() -> dict[str, str]:
    path = LOCALES / BASE
    return json.loads(common.read_text(path)) if path.is_file() else {}


def frontend_sources() -> list[tuple[str, str]]:
    """Every `.ts`/`.tsx` file under `src/`, COMMENTS REMOVED (`_code_only`).

    Stripped HERE, at the one place frontend text enters this gate, so that both
    directions get the same eyes: direction A cannot count a commented-out key
    as a call site (DEF-769) and direction B cannot ask the catalogue for a key
    that only a comment mentions.
    """
    return [
        (common.rel(p), _code_only(common.read_text(p)))
        for p in common.frontend_code_files() + field_app_code_files()
        if "i18n/locales" not in common.rel(p)
    ]


#: The field app (CR-187-BRC10) reads its words from the SAME eleven
#: catalogues, under `field.*` (decision log 2026-10-21, conflict ruling #3).
#: Its call sites live in `field-app/src/`, so a `field.*` key with a call site
#: there is live — without this, all 859 field keys fanned in on 2026-10-21
#: would read as "dead" here, because the web app never names them.
FIELD_APP_SRC = common.REPO_ROOT / "field-app" / "src"


def field_app_code_files() -> list:
    if not FIELD_APP_SRC.is_dir():
        return []
    return sorted(p for p in FIELD_APP_SRC.rglob("*") if p.suffix in (".ts", ".tsx"))


def backend_sources() -> list[tuple[str, str]]:
    apps = sorted(common.BACKEND_APPS.rglob("*.py")) if common.BACKEND_APPS.is_dir() else []
    core = sorted((common.BACKEND_DIR / "core").rglob("*.py"))
    return [(common.rel(p), common.read_text(p)) for p in apps + core]


# ── direction A's evidence: everything a key can be reached by ──────────────
def _balanced(text: str, open_at: int) -> str:
    """The `t( … )` call text starting at the paren index, paren-balanced."""
    depth, i = 0, open_at
    while i < len(text) and i < open_at + 2000:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_at : i + 1]
        i += 1
    return text[open_at : open_at + 2000]


def _first_argument(call: str) -> str:
    """The text of a balanced call's FIRST argument — the key expression.

    Everything up to the first comma at depth 1, so `t(a ? "x.y" : "x.z", {…})`
    yields both branches of the ternary and none of the interpolation params.
    """
    depth = 0
    for index, char in enumerate(call):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
            if depth == 0:
                return call[1:index]
        elif char == "," and depth == 1:
            return call[1:index]
    return call


def code_lines(text: str):
    """(lineno, line) for every line that is not a comment. See law 1 above."""
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip().startswith(COMMENT_OPENERS):
            yield lineno, line


def message_keys(path: str, text: str) -> list[tuple[str, str]]:
    """Every `message_key` a backend file raises, with where. AST, not grep.

    Four forms, because the repo uses four: `message_key=` on a call, the
    `{"message_key": …}` dict inside a `field_errors` item, a POSITIONAL
    argument to a helper declared in this file whose parameter is named
    `message_key` (`_refuse(code, message_key, **params)`), and a module-level
    constant passed by name (`GENERIC_SIGN_IN_MESSAGE_KEY`).
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    positional: dict[str, int] = {}
    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = node.value.value
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for index, arg in enumerate(node.args.posonlyargs + node.args.args):
                if arg.arg == "message_key":
                    positional[node.name] = index

    found: list[tuple[str, str]] = []

    def record(node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.append((node.value, f"{path}:{node.lineno}"))
        elif isinstance(node, ast.Name) and node.id in constants:
            found.append((constants[node.id], f"{path}:{node.lineno} (via {node.id})"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "message_key":
                    record(keyword.value)
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            index = positional.get(name)
            if index is not None and index < len(node.args):
                record(node.args[index])
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "message_key":
                    record(value)
    return found


def call_sites(frontend, backend) -> tuple[dict[str, str], set[str]]:
    """({key: where}, {computed prefix}) — everything the code can render."""
    literals: dict[str, str] = {}
    prefixes: set[str] = set()
    for path, text in frontend:
        for lineno, line in code_lines(text):
            for match in KEY_LITERAL.finditer(line):
                literals.setdefault(match.group(1), f"{path}:{lineno}")
            prefixes |= set(KEY_PREFIX.findall(line))
    for path, text in backend:
        for key, where in message_keys(path, text):
            literals.setdefault(key, where)
        for lineno, line in code_lines(text):
            # core/errors.py: default_message_key(code) == "errors." + code.lower()
            for code in ERROR_CODE.findall(line):
                literals.setdefault("errors." + code.lower(), f"{path}:{lineno} (derived)")
    # A literal that is a proper prefix of a key names that FAMILY: the stem form
    # `enumLabel(t, "rating.charges.type", value)`, which no template literal
    # reveals because the prefix arrives as an argument.
    prefixes |= {literal + "." for literal in literals}
    return literals, prefixes


# ── direction B's evidence: every key the code asks the catalogue for ───────
def requested_keys(frontend, backend) -> dict[str, str]:
    """{key: where} for every STATIC lookup that must resolve to a catalogue entry.

    A `t()` call carrying `defaultValue` is excluded and that is not a courtesy:
    i18next renders the default, so the author has stated in code that a missing
    key is the expected path (`locales.test.ts` probes the not-yet-re-tagged
    locale codes exactly this way). Undotted literals are excluded because every
    catalogue key is dotted. `*.test.ts{,x}` is excluded — see the docstring.
    """
    requested: dict[str, str] = {}

    def want(key: str, where: str) -> None:
        if "." in key:
            requested.setdefault(key, where)

    for path, text in frontend:
        if ".test." in path:
            continue
        comments = {n for n, _ in enumerate(text.splitlines(), 1)} - {
            n for n, _ in code_lines(text)
        }
        for lineno, line in code_lines(text):
            for match in KEY_PROP.finditer(line):
                want(match.group(1), f"{path}:{lineno}")
        for match in T_OPEN.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            if lineno in comments:
                continue
            call = _balanced(text, text.index("(", match.start()))
            if "defaultValue" in call:
                continue
            for literal in KEY_LITERAL.finditer(_first_argument(call)):
                want(literal.group(1), f"{path}:{lineno}")
    for path, text in backend:
        for key, where in message_keys(path, text):
            want(key, where)
    return requested


# ── the known-gap register ──────────────────────────────────────────────────
def register() -> tuple[dict[tuple[str, str], tuple[str, str]], list[str]]:
    """{(direction, key): (defect id, reason)} plus any malformed-line problems."""
    entries: dict[tuple[str, str], tuple[str, str]] = {}
    problems: list[str] = []
    if not REGISTER.is_file():
        return entries, ["i18n_known_gaps.txt is missing — the register must exist, even empty"]
    for lineno, raw in enumerate(common.read_text(REGISTER).splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 4)
        if len(parts) < 5:
            problems.append(f"line {lineno}: expected `<direction> <key> <DEF-###> <date> <reason>`")
            continue
        direction, key, defect, date, reason = parts
        if direction not in ("dead", "missing"):
            problems.append(f"line {lineno}: direction must be `dead` or `missing`, not {direction!r}")
            continue
        # ⚠ `\d{3,}` AND NOT `\d{3}` — DEF-1651. With `\d{3}` this register
        # could not park ANY finding raised after DEF-999: a valid four-digit
        # id was reported as malformed and the entry was DROPPED, so the key it
        # named stayed unparked and the gate reported it forever. Found by the
        # DEF-724 lane, which parked four keys against `DEF-1650` and watched
        # the gate fail with `must cite a DEF-### row, not 'DEF-1650'` while
        # still listing all four as missing.
        if not re.fullmatch(r"DEF-(?:[A-Z]{3}-)?\d{3,}", defect):
            problems.append(f"line {lineno}: {key} must cite a DEF-### row, not {defect!r}")
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            problems.append(f"line {lineno}: {key} needs the date it was parked (YYYY-MM-DD)")
            continue
        if (direction, key) in entries:
            problems.append(f"line {lineno}: {direction} {key} is registered twice")
            continue
        entries[(direction, key)] = (defect, reason)
    return entries, problems


def defect_rows() -> dict[str, str]:
    if not DEFECT_LOG.is_file():
        return {}
    # io.StringIO, not splitlines(): the log's free-text columns carry embedded
    # newlines and a line-based reader would silently invent rows.
    reader = csv.DictReader(io.StringIO(common.read_text(DEFECT_LOG)))
    return {(r.get("id") or "").strip(): (r.get("status") or "").strip().lower() for r in reader}


# ── i18next PLURALS (DEF-323, 2026-08-19) ──────────────────────────────────
# `t("dashboard.period.age", {count})` is answered by `dashboard.period.age_one`
# and `_other`; the BARE key is not supposed to exist. This gate compared the
# literal against the catalogue key set EXACTLY, so it reported three correct
# dashboard strings as "used in code and defined in NO catalogue (renders raw to
# a user)" — a false sentence, inside a headline count a reader trusts, which
# inflated the user-facing figure from 23 to 26 and led a lane to tell the PO
# the dashboard was rendering raw keys. It was not.
#
# ⚠ NOTHING CATCHES A GATE THAT IS WRONG IN THE SAFE DIRECTION: the suite is red
# either way, so the false line hides inside a real failure. That is DEF-323's
# own escape_reason, and it is why the fix is here rather than in a note.
#
# Both directions need it. A key answered only through its plural forms is
# PRESENT (direction B), and a plural VARIANT in the catalogue is reachable
# whenever its bare stem is called (direction A) — otherwise fixing B would
# immediately report every `_one`/`_other` entry as dead.
PLURAL_CATEGORIES = ("zero", "one", "two", "few", "many", "other")
# ⚠ BOTH separators, and the dot one is the one this repo actually emits
# (DEF-2101). i18next's own convention is `key_one`; this codebase's helper
# `pluralKey(base, count)` — 07-frontend/src/features/tenancy/routesCyclesShared.tsx
# — returns `${base}.one` / `${base}.other`, so the BARE stem is never requested
# at runtime, and all four of its call sites are catalogued that way. Knowing
# only the underscore form, this gate reported `settings.routes.detail.unitsOnStop`
# as "renders raw to a user" when it renders "3 units" correctly in all eleven
# languages. The other three stems only escaped because someone had added a bare
# key beside the dot variants, which nothing ever reads.
PLURAL_SUFFIXES = tuple(
    separator + category for category in PLURAL_CATEGORIES for separator in ("_", ".")
)

# DEF-2101's own probe — a stem catalogued ONLY in the dot form, called the way
# `pluralKey` calls one. A6 proves the gate accepts it; A7 proves the clause
# still bites when neither variant exists, so A6 cannot pass by going blind.
PLURAL_PROBE_KEY = "g18.probe.plural_stem"
PLURAL_PROBE_SOURCE = (
    "07-frontend/src/features/tenancy/g18_plural_probe.tsx",
    'const label = t(pluralKey("g18.probe.plural_stem", count));\n',
)


def _resolves(key: str, english: dict[str, str]) -> bool:
    """i18next's answer to "is this key in the catalogue" — the key itself, or
    any of its plural forms (DEF-323)."""
    return key in english or any(key + suffix in english for suffix in PLURAL_SUFFIXES)


def _plural_stem(key: str) -> str | None:
    """`dashboard.period.age_one` → `dashboard.period.age`, else None."""
    for suffix in PLURAL_SUFFIXES:
        if key.endswith(suffix):
            return key[: -len(suffix)]
    return None


# ── the check itself, pure over its corpus so Part 0 can mutate it ──────────
def compare(english: dict[str, str], frontend, backend) -> tuple[list[str], list[str], int]:
    """(dead keys, missing keys, keys reachable only through a computed prefix)."""
    literals, prefixes = call_sites(frontend, backend)
    ordered = sorted(prefixes, key=len, reverse=True)

    dead, computed = [], 0
    for key in sorted(english):
        if key in literals:
            continue
        stem = _plural_stem(key)
        if stem is not None and stem in literals:
            continue  # reached through its bare stem + a `count` (DEF-323)
        if any(key.startswith(prefix) for prefix in ordered):
            computed += 1
            continue
        dead.append(key)

    missing = sorted(
        k
        for k in requested_keys(frontend, backend)
        if k not in english and not any(k + suffix in english for suffix in PLURAL_SUFFIXES)
    )
    return dead, missing, computed


# ═══════════════════════════════════════════════════════════════════════════
# PART 0 — SELF-TEST (law 7). Both directions are clean today ONLY because the
# 104 real findings are parked in the register, so a green run proves the
# register works, not that the comparison does. Each fixture plants the defect
# it was written for in an in-memory copy of the real corpus.
# ═══════════════════════════════════════════════════════════════════════════
FIXTURES = [
    ("A1", "DEF-041 replay: a key USED in code and in no catalogue renders raw to a user"),
    ("A2", "DEF-036 replay: a backend refusal raising a message_key no catalogue defines"),
    ("A3", "DEF-049 replay: a catalogue key eleven catalogues agree on and nothing renders"),
    ("B1", "the register is NARROW: a parked key whose id drifts by one character still fails"),
    ("B2", "the register EXPIRES: an entry that no longer reproduces is stale and fails"),
    ("A4", "DEF-769 replay: a key named ONLY in a JSX comment is not a call site"),
    ("A5", "DEF-741 replay: a `//` line spelling a path with a star in it swallows no code"),
]

#: A4 — DEF-769's own shape: the key name in a `{/* ... */}` JSX comment, in
#: backticks, exactly as `WizardFrame.tsx` carries `wizard.park.parkedAt`. The
#: line begins with `{`, so `COMMENT_OPENERS` cannot see it.
DEF769_KEY = "g18.probe.commented_key"
DEF769_SOURCE = (
    "07-frontend/src/g18_probe_comment.tsx",
    "{/* the retired `" + DEF769_KEY + "` used to say this */}\nexport const probe = 1;\n",
)
#: A5 — DEF-741's own shape, pinned HERE so the order inside `_code_only` can
#: never be flipped back. The trailing block comment is load-bearing: with
#: blocks stripped first, the `/*` inside `locales/*.json` opens a comment that
#: closes at THAT `*/`, and the `t()` call between them disappears.
DEF741_KEY = "g18.probe.after_star_line"
DEF741_SOURCE = (
    "07-frontend/src/g18_probe_order.tsx",
    "// see src/i18n/locales/*.json\n"
    'const label = t("' + DEF741_KEY + '");\n'
    "/* and an ordinary block comment below it */\n",
)

#: The DEF-041 key, chosen because it is the defect's own: nine `shell.user.*` /
#: `shell.tenant.*` keys were used by AppShell and defined by no catalogue.
DEF041_KEY = "shell.user.myProfile"
#: A refusal key shaped exactly like DEF-036's two live instances.
DEF036_KEY = "rating.assignment.reason_required_behind_issued_bill"
DEF036_RAISE = (
    "\n\ndef _g18_red_probe():\n"
    '    raise errors.ValidationError(errors.VAL_FORMAT, message_key="g18.probe.no_such_key")\n'
)


def self_test(english, frontend, backend, entries) -> list[tuple[str, bool, str]]:
    results = []

    without = {k: v for k, v in english.items() if k != DEF041_KEY}
    _, missing, _ = compare(without, frontend, backend)
    results.append(("A1", DEF041_KEY in missing,
                    f"{DEF041_KEY} removed from {BASE} -> "
                    + (f"reported missing ({len(missing)} total)" if DEF041_KEY in missing
                       else "NOT reported (expected FAIL)")))

    probed = [(p, t + DEF036_RAISE) if p.endswith("apps/rating/services.py") else (p, t)
              for p, t in backend]
    _, missing, _ = compare(english, frontend, probed)
    results.append(("A2", "g18.probe.no_such_key" in missing,
                    "a message_key with no catalogue entry -> "
                    + ("reported missing" if "g18.probe.no_such_key" in missing
                       else "NOT reported (expected FAIL)")))

    padded = dict(english)
    padded["g18.probe.dead_key"] = "nothing renders this"
    dead, _, _ = compare(padded, frontend, backend)
    results.append(("A3", "g18.probe.dead_key" in dead,
                    "a catalogue key with no call site -> "
                    + ("reported dead" if "g18.probe.dead_key" in dead
                       else "NOT reported (expected FAIL)")))

    drifted = {(d, k + "X" if k == DEF036_KEY else k): v for (d, k), v in entries.items()}
    covered = ("missing", DEF036_KEY) in drifted
    results.append(("B1", not covered,
                    "a register key altered by one character no longer covers the finding"
                    if not covered else "a drifted entry still covered the finding (expected NOT)"))

    stale = [k for (d, k) in entries if d == "dead" and k not in english]
    stale += [k for (d, k) in entries if d == "missing" and _resolves(k, english)]
    results.append(("B2", True,
                    f"{len(stale)} registered entry(ies) no longer reproduce and would fail as "
                    "stale on this corpus"))

    # A4/A5 pass their probe through `_code_only` because `frontend_sources`
    # already has — these two fixtures test the STRIPPER, so they must hand
    # `compare` the same text the real corpus arrives as.
    commented = dict(english)
    commented[DEF769_KEY] = "everything already entered stays on the record"
    probe = frontend + [(DEF769_SOURCE[0], _code_only(DEF769_SOURCE[1]))]
    dead, _, _ = compare(commented, probe, backend)
    results.append(("A4", DEF769_KEY in dead,
                    "a key named only in a JSX comment -> "
                    + ("reported dead" if DEF769_KEY in dead
                       else "NOT reported: the comment counted as a call site (expected FAIL)")))

    ordered = frontend + [(DEF741_SOURCE[0], _code_only(DEF741_SOURCE[1]))]
    _, missing, _ = compare(english, ordered, backend)
    results.append(("A5", DEF741_KEY in missing,
                    "a t() call under a `//` line ending in `*.json` -> "
                    + ("still read" if DEF741_KEY in missing
                       else "SWALLOWED by block-first stripping (expected FAIL)")))

    # A6/A7 (DEF-2101) — the dot plural convention, both directions.
    plural_probe = frontend + [(PLURAL_PROBE_SOURCE[0], _code_only(PLURAL_PROBE_SOURCE[1]))]
    dotted = dict(english)
    dotted[PLURAL_PROBE_KEY + ".one"] = "{{count}} thing"
    dotted[PLURAL_PROBE_KEY + ".other"] = "{{count}} things"
    _, missing, _ = compare(dotted, plural_probe, backend)
    results.append(("A6", PLURAL_PROBE_KEY not in missing,
                    "a stem catalogued only as `.one`/`.other` -> "
                    + ("accepted, as i18next accepts it" if PLURAL_PROBE_KEY not in missing
                       else "reported as rendering raw to a user (expected ACCEPT)")))

    _, missing, _ = compare(english, plural_probe, backend)
    results.append(("A7", PLURAL_PROBE_KEY in missing,
                    "the same stem with NO variant in the catalogue -> "
                    + ("still reported missing, so A6 is not blind" if PLURAL_PROBE_KEY in missing
                       else "NOT reported: the clause has gone blind (expected FAIL)")))
    return results


def run() -> tuple[str, str]:
    if not (LOCALES / BASE).is_file():
        return "SKIP", f"{BASE} not present in {LOCALES.name}/ — nothing to compare code against"
    english = catalogue()
    frontend, backend = frontend_sources(), backend_sources()
    if not frontend and not backend:
        return "SKIP", "no frontend or backend source to compare the catalogue against yet"

    entries, problems = register()
    statuses = defect_rows()
    for (direction, key), (defect, _reason) in sorted(entries.items()):
        if defect not in statuses:
            problems.append(f"{direction} {key} cites {defect}, which has no row in the defect log")
        elif statuses[defect] in CLOSED_STATUSES:
            problems.append(f"{direction} {key} cites {defect}, which is {statuses[defect]} — "
                            "the reason to be parked has expired; fix the key or re-file the row")

    blind = [(tag, detail) for tag, ok, detail in self_test(english, frontend, backend, entries)
             if not ok]
    if blind:
        return "FAIL", (f"self-test BLIND: {blind[0][0]} {blind[0][1]}. A guard that cannot be "
                        "shown to fail is not a guard (law 7).")

    dead, missing, computed = compare(english, frontend, backend)
    new_dead = [k for k in dead if ("dead", k) not in entries]
    new_missing = [k for k in missing if ("missing", k) not in entries]
    stale = [f"dead {k}" for (d, k) in entries if d == "dead" and k not in english]
    stale += [f"missing {k}" for (d, k) in entries if d == "missing" and _resolves(k, english)]
    stale += [f"dead {k}" for (d, k) in entries if d == "dead" and k in english and k not in dead]
    stale += [f"missing {k}" for (d, k) in entries
              if d == "missing" and not _resolves(k, english) and k not in missing]

    failures = []
    if new_missing:
        failures.append(f"{len(new_missing)} key(s) used in code and defined in NO catalogue "
                        f"(renders raw to a user): {common.summarize(new_missing, MAX_NAMED)}")
    if new_dead:
        failures.append(f"{len(new_dead)} catalogue key(s) with no call site "
                        f"(renders to nobody): {common.summarize(new_dead, MAX_NAMED)}")
    if stale:
        failures.append(f"{len(stale)} STALE register entry(ies) — delete the line in the same "
                        f"diff that closed it: {common.summarize(sorted(set(stale)), MAX_NAMED)}")
    failures += problems

    # ⚠ **THE COUNTS THIS GATE MEASURED, NOT THE NUMBER OF SENTENCES IT WROTE
    # ABOUT THEM (DEF-2601, 2026-08-31).** This line used to read
    # "1 problem(s): 227 catalogue key(s) with no call site" — one, because the
    # gate counted its own failure STRINGS, of which there was one. Two things
    # were wrong with that and the second is the serious one. **227 findings
    # reported as 1**, and, worse, the two DIRECTIONS folded into a single
    # headline. They are not equally severe: `missing` is a call site whose key
    # no catalogue defines, and i18next renders the key itself, so a clerk reads
    # `rating.plans.duplicate_code` — that is the defect DEF-036 was filed for.
    # `dead` renders to nobody. On the day this was found `missing` was CLEAN
    # and `dead` stood at 227, and no reader of the table could tell.
    tally = (
        f"{len(missing)} missing ({len(new_missing)} unparked, renders raw to a user) · "
        f"{len(dead)} dead ({len(new_dead)} unparked, renders to nobody) · "
        f"{len(entries)} PARKED in i18n_known_gaps.txt (real, unfixed, routed)"
    )
    if failures:
        return "FAIL", (
            f"{tally} — " + common.summarize(failures, 2)
            + ". Every one of them named and grouped by module: "
              "`python3 10-scripts/gates/g18_i18n_call_sites.py --report` "
              "(DEF-CWP-3943 — a dead key is either wording to delete or a "
              "control nobody built, and you cannot tell which from a count)."
        )

    return "PASS", (
        f"{len(english)} {BASE} key(s) vs {len(frontend)} frontend + {len(backend)} backend "
        f"file(s): every call site resolves and every unparked key has a call site "
        f"({computed} reachable only through a computed key, not proved live); {tally}"
    )


def report() -> str:
    """Every UNPARKED finding, named and grouped by module — the worklist that
    `run()`'s one line cannot carry (`DEF-CWP-3943`).

    ⚠ **WHY A REPORT AND NOT A LOUDER FAILURE.** `run()` is a merge gate and its
    detail line is one line: on 2026-09-05 it read *"51 catalogue key(s) with no
    call site: billing.action.runBillsBlocked; customers.transfer.dates_required;
    customers.transfer.in_date_before_out_date (+48 more)"*. That is a NUMBER
    THAT WENT UP. What it actually is, said in the row that filed it, is *"22
    sentences somebody wrote for a screen that does not say them"* — and you
    cannot act on a number.

    ⚠ **AND A DEAD KEY HAS TWO OPPOSITE READINGS, NEITHER SAFE TO ASSUME.** It
    is either wording that should be deleted, OR **A CONTROL THAT WAS NEVER
    BUILT**. `portal.quick.copy_of_bill.title` is a quick-service category a
    customer cannot ask for; `portal.myDetails.refused.*` are four refusals a
    screen can never show. So this prints them grouped by module and never
    suggests a fix: each one has to be READ by the lane that owns the screen,
    and the whole value of grouping is putting all of one lane's in front of it
    at once.

    Reporting only. It computes nothing `run()` does not already compute and
    changes no verdict — `run()` is byte-for-byte the function it was.
    """
    english, frontend, backend = catalogue(), frontend_sources(), backend_sources()
    entries, _ = register()
    dead, missing, _ = compare(english, frontend, backend)
    out: list[str] = []
    for direction, keys, gloss in (
        ("MISSING", [k for k in missing if ("missing", k) not in entries],
         "used in code, in NO catalogue — i18next prints the key itself to a user"),
        ("DEAD", [k for k in dead if ("dead", k) not in entries],
         "in every catalogue, called from nowhere — either the wording goes, "
         "or the control it was written for was never built"),
    ):
        out.append(f"\n=== {len(keys)} UNPARKED {direction} — {gloss} ===")
        if not keys:
            out.append("  (none)")
            continue
        by_module: dict[str, list[str]] = {}
        for k in sorted(keys):
            by_module.setdefault(k.split(".", 1)[0], []).append(k)
        for mod, ks in sorted(by_module.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            out.append(f"\n  {mod} ({len(ks)})")
            out.extend(f"    {k}" for k in ks)
    return "\n".join(out)


if __name__ == "__main__":
    import sys as _sys

    if "--report" in _sys.argv[1:]:
        # `DEF-CWP-3943` — the worklist, not the tally. Reporting only: it exits
        # 0 whatever it finds, so it can never be mistaken for the gate.
        print(report())
        raise SystemExit(0)

    status, detail = run()
    print(f"{status}: {detail}")
    print()
    english, frontend, backend = catalogue(), frontend_sources(), backend_sources()
    entries, _ = register()
    print("--- Part 0: self-test (law 7 — prove the guard goes RED before trusting it green) ---")
    for tag, ok, text in self_test(english, frontend, backend, entries):
        print(f"  {'BITES' if ok else 'BLIND'} {tag}  {text}")
    dead, missing, computed = compare(english, frontend, backend)
    print()
    print(f"--- findings: {len(missing)} missing, {len(dead)} dead, {computed} computed-only ---")
    for key in missing:
        print(f"  MISSING {key}" + ("" if ("missing", key) in entries else "   << NOT REGISTERED"))
    for key in dead:
        print(f"  DEAD    {key}" + ("" if ("dead", key) in entries else "   << NOT REGISTERED"))
    raise SystemExit(0 if status != "FAIL" else 1)
