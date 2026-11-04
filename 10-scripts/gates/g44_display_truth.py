#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   the Product Owner, 2026-08-27, on the live deployment — *"previous
#           and current reading still showing 4 decimal - why this decimal case
#           keep happen and databse keys - I ahve observe this is a common
#           mistake how we cn ahndle it , find it on our won all errors and fix
#           it across applcaition"*
# Rules:    BR-SHL-250 (WHERE a value is formatted — the house rule this gate
#           enforces) · BR-MET-144 (a quantity: at most 2dp, trailing zeros
#           trimmed, and its unit) · CLAUDE.md hard rule 2 (money 4 / percent 6,
#           both DISPLAY 2) · hard rule 3 (a quantity carries its unit) ·
#           DEF-206 (a database key is never the visible value)
# Defects:  DEF-1086 (the reads list printed `1008.000000`) · DEF-894 (the
#           consumption sweep) · DEF-968 (the money sweep) · DEF-899 / DEF-937
#           (the database-key sweeps) · DEF-646 (the Meters tab) — five fixes,
#           one class, and no check ever asked the general question
# ───────────────────────────────────────────────────────
"""G44 — a stored value may not reach a screen wearing its storage.

WHY THIS GATE EXISTS
--------------------
**Five separate fixes have now been made to the same defect and the sixth
instance was still live.** Each fix named the columns it knew about:

* `DEF-646` fixed the Meters tab — `1016.000000`, `8.000000 kgal`.
* `DEF-894` fixed CONSUMPTION and built `apps/metering/quantity_display.py`,
  wiring six surfaces.
* `DEF-968` fixed MONEY and PERCENTAGE inside priced sentences on three
  billing surfaces.
* `DEF-899` and `DEF-937` fixed DATABASE KEYS, each on its own screen.
* `DEF-1086` was a REGISTER READING — a fourth kind of number, in none of
  those four searches — and it printed `1008.000000` two columns away from a
  cell that was right.

**Nothing in this repo asked the general question: does any stored value reach
a screen unformatted.** A grep run by hand at the moment of a fix measures that
moment and decays from the next commit. This gate asks on every commit, which
is the only mechanism here that has ever held a whole-tree property still
(G31's ceiling, G38's notes, G43's two clauses — the three files this one is
built on).

THE HOUSE RULE IT ENFORCES — BR-SHL-250
----------------------------------------
Two patterns existed in this codebase and they disagreed, because nobody had
ever said which was for what. BR-SHL-250 says it: **a value is formatted where
the FACTS needed to format it live.**

    quantity      SERVER   needs the tenant's UoM label (hard rule 3)
    database key  SERVER   needs a JOIN to read `CODE — Name` (DEF-206)
    percentage    SERVER   already composed into priced sentences
    money         CLIENT   needs the tenant's number format (session)
    date / time   CLIENT   needs the tenant timezone + date format (session)

WHAT IT CHECKS — THREE CLAUSES, DELIBERATELY DIFFERENT SHAPES
--------------------------------------------------------------
**(a) A CELL RENDERER MAY NOT INDEX ITS ROW BY A VARIABLE. HARD, BASELINE 0.**
This is DEF-1086's exact mechanism and it is worth its own clause because it is
the one shape that can never be fixed in place: a renderer written as

    value: (row, field) => <span>{row[field]}</span>

does not KNOW which field it holds, so it cannot know whether the value is
money, a quantity or a key — and therefore cannot format it, whatever anyone
later decides the rule is. Naming the field is the precondition for having a
treatment at all. Baseline zero because after DEF-1086's fix there are none,
and the 25th list must name its fields like the other 24.

**(b) A FIELD THE SERVER SERVES WITH A `_display` SIBLING MAY NOT BE RENDERED
     RAW. HARD, BASELINE 0.** Once the server has composed the string — with
its unit, at the ruled precision — printing the raw number beside it is not a
judgment call, it is the sibling being ignored. This clause is exact, not
heuristic: the pairing is read out of `07-frontend/src/api/endpoints.ts`, where
an interface that declares both `x` and `x_display` has stated its own
contract. **It is what makes BR-SHL-250 self-enforcing**: a lane that adds a
sibling to the server automatically forbids the raw field on every screen.

**(c) A CLASSIFIED VALUE REACHING A TEXT POSITION WITH NO TREATMENT AT ALL.
     RATCHETED.** Money, quantity, percentage and database keys, recognised by
field name, interpolated straight into JSX text or into a rendered template
literal. This one CANNOT be an invariant today — there is a real backlog, and
a gate that is red from birth earns a `# noqa` instead of a fix (G31's lesson,
in its own words). The count may FALL and may never RISE, and a fall that is
not banked is also a failure (DEF-490: a ratchet that never tightens is a
number nobody reads).

WHAT IT DELIBERATELY DOES NOT CHECK
-----------------------------------
**Whether the rendered string is CORRECT.** Nothing that reads source can tell
`$64.57` from `$64.6`; only `06-backend/tests/test_def_894_quantity_display.py`
and `07-frontend/src/components/MoneyCell.test.tsx` can, and they do. This gate
asks whether a treatment is REACHED, never what it produced. A check whose
output cannot distinguish pass from fail is worse than no check, because it is
trusted (DEF-182).

**A value inside a CSV export or a `print` template.** Those are backend
surfaces with their own kinds (IS-9 `MONEY`/`NUMBER`), and IS-9 declares no
QUANTITY and no PERCENT kind at all — which is a real gap, filed as DEF-1123
and OQ-620 rather than papered over by a check that cannot see it.

COMMENTS ARE STRIPPED, AND THAT IS NOT FUSSINESS
------------------------------------------------
Several files carry a comment explaining why a particular field is shown raw —
`ReadsListPage`'s batch-id note, `AuditLogPage`'s `entityLabel` docstring, this
gate's own docstring. **Prose ABOUT the rule must never trip the rule** (G31
was tripped from a comment twice; G37 and G43 both carry this guard).
⚠ LINE COMMENTS ARE STRIPPED FIRST (DEF-741): a `//` line spelling a path with
a star in it contains `/*`, so stripping BLOCK first opens a comment that
closes at the next `*/` anywhere below and blanks every line between.

PROVED RED (hard-won law 7) — the verbatim failures are in the `# RED PROOF`
blocks beside each clause.

⚠ **AND ONE MORE RED THAT ONLY `run_gates.py` COULD SEE — READ THIS BEFORE
WRITING THE NEXT GATE.** This module's first commit had `run()` return
`(True, detail)` instead of `("PASS", detail)`. Run on its own it printed
`G44 display-truth: PASS` and exited 0, because `main()` reads the first
element as truthy. In the runner — the file CI actually executes — it printed:

    G44 display-truth  FAIL   gate returned invalid status True
                              ((a) 0/0 · (b) 0/0 · (c) untreated 33/33)

**A gate that is not correctly plugged into the runner is a script with a
gate's docstring**, and that is hard-won law 2 (built is not wired) wearing
this file's own subject matter. It is also precisely what G42 exists to catch
and could not: G42 asks whether `run()` and a `__main__` block EXIST, not what
`run()` returns. So: `run()` returns one of `"PASS"` / `"FAIL"` / `"SKIP"` and
a detail string, and the only trustworthy proof of a new gate is running
`run_gates.py`, never the module alone.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "07-frontend" / "src"
ENDPOINTS = SRC / "api" / "endpoints.ts"

# ── Clause (a) · a renderer that cannot name its field ─────────────────────
#
# ⚠ DO NOT RAISE THIS. DEF-1086 was the only one and it is fixed. A list that
# genuinely needs one renderer for two columns passes the field name and reads
# it explicitly, exactly as `ReadsListPage`'s `value` cell now does.
#
# RED PROOF (run against the tree before DEF-1086's fix):
#   G44 clause (a) FAIL — 1 cell renderer indexes its row by a variable:
#     07-frontend/src/features/metering/ReadsListPage.tsx:583  {row[field]}
#       value: (row, field) => (row[field] === null ? <Dash /> : <span>{row[field]}</span>),
DYNAMIC_KEY_BASELINE = 0

# ── Clause (b) · the server composed it; print THAT ────────────────────────
#
# ⚠ DO NOT RAISE THIS EITHER. It is an invariant by construction: the pairing
# only exists because a lane deliberately added a `_display` sibling, and
# adding one is a statement that the raw field is not for reading.
#
# RED PROOF (run against the tree before this lane's fix, once
# `prior_value_display` / `current_value_display` existed on `ReadRow` and the
# cells still printed the raw fields):
#   G44 clause (b) FAIL — 3 raw renders of a field that HAS a server sibling:
#     07-frontend/src/features/metering/ReadsListPage.tsx:583  ReadRow.prior_value
#     07-frontend/src/features/metering/ReadDetailPage.tsx:527 ReadDetail.prior_value
#     07-frontend/src/features/metering/ReadDetailPage.tsx:538 ReadDetail.current_value
SIBLING_IGNORED_BASELINE = 0

# ── Clause (c) · the heuristic backlog, ratcheted ──────────────────────────
#
# The number that survived this lane's sweep. Every remaining hit carries a
# defect row; the list and its reasons are in `g44_display_truth_baseline.txt`,
# beside this file, so a lane fixing one knows what it is looking at.
UNTREATED_BASELINE = 0  # set by _measure() below at first run; see the txt file

BASELINE_FILE = Path(__file__).resolve().parent / "g44_display_truth_baseline.txt"

# ── The classifier ─────────────────────────────────────────────────────────
#
# A field name decides its KIND. This is a heuristic and it is allowed to be,
# because it feeds the RATCHET only — clauses (a) and (b) are exact and use
# none of it.
#
# ⚠ THE SUFFIX WINS OVER THE TOKEN, AND THAT ORDER IS THE WHOLE ACCURACY OF
# THE THING. `revenue_code`, `payment_no`, `tax_exempt_ref` and `taxName` all
# contain a money token and are all TEXT: an identifier that happens to be
# spelled after a money concept is still an identifier. Reversing these two
# tests produced four false positives in the first draft, which is four more
# than this gate may have.
#
# ⚠ `_authority` ADDED 2026-08-31 (`DEF-2713`). `tax_authority` is BR-BIL-069's
# *"whose tax this line is"* — the NAME of a revenue authority, e.g. *"Bexar
# County Tax Office"* — and it fell straight through this test to the `tax`
# money token, so the first screen ever to render it (CR-053 task 6) reported a
# proper noun as an untreated money value and turned this gate red. It is
# exactly the class the paragraph above names, and the entry is the narrowest
# possible: it matches only a field ENDING in `_authority`, so it can hide no
# money figure.
IDENTIFIER_SUFFIX = re.compile(
    r"(?:_(?:code|no|ref|name|label|key|type|status|text|title|note|unit|"
    r"currency|method|reason|url|slug|by|state|kind|mode|tag|desc|description|"
    r"scope|source|number|token|hash|version|authority)$)"
    r"|(?:(?:Name|Code|Ref|Label|Type|Status|Text|Unit|Currency|No|Key)$)"
)
MONEY_TOKENS = (
    "amount", "balance", "total", "price", "charge", "fee", "due", "paid",
    "credit", "debit", "subtotal", "tax", "revenue", "cost", "payment",
    "arrears", "refund", "deposit", "adjustment", "writeoff", "penalty",
    "invoiced", "billed",
)
QUANTITY_TOKENS = (
    "usage", "consumption", "quantity", "qty", "reading", "volume", "kwh",
    "kgal", "therm", "demand",
)
# `*_value` is NOT a quantity token — `sample_value`, `action_value` and
# `premises_scope_value` are all text. The register-reading family is named
# exactly instead, which is what DEF-1086 actually was.
QUANTITY_EXACT = frozenset({
    "prior_value", "current_value", "register_value", "reading_value",
    "prior_reading", "current_reading", "master_consumption", "gap_quantity",
    "billed_quantity", "sub_total_consumption",
})
PERCENT_TOKENS = ("percent", "pct")
# ── A RATE IS A THIRD KIND OF NUMBER (OQ-620(a), PO 2026-08-27) ────────────
#
# *"What does a tariff rate show? Four ($0.1420). A rate is not money and not a
# quantity - 4 decimal places"*. Before that ruling this gate classified
# `unit_price` as MONEY, which was the closest available answer and the wrong
# one: money displays two places and a rate displays four with its zeros KEPT,
# so a `MoneyCell` on a rate renders `$0.14` — a well-formed currency string
# that cannot reproduce the line it priced.
#
# The kind is checked BEFORE money because every rate name here also contains a
# money token (`unit_price`, `rate_per_unit`), and the more specific test has
# to win. It changes no COUNT — a rate was already being counted, under the
# wrong label — but a mislabelled hit sends the lane that picks it up to
# `MoneyCell`, which is the defect rather than the fix.
RATE_EXACT = frozenset({
    "unit_price", "rate_per_unit", "energy_rate_per_kwh", "demand_rate_per_kw",
    "pf_penalty_rate_per_kw", "per_unit_amount", "price_per_unit",
})
RATE = "rate"
DATE_TOKENS = ("_at", "_on", "_date")

KEY = "key"
MONEY = "money"
QUANTITY = "quantity"
PERCENT = "percent"
DATE = "date"
TEXT = "text"
FORMATTED = "formatted"


def classify(field: str) -> str:
    """What KIND of thing this field name holds. `text` means: render it raw."""
    low = field.lower()
    if low.endswith("_display") or low.endswith("display") or low.endswith("_label"):
        return FORMATTED
    if low in ("id", "uuid") or low.endswith("_id") or low.endswith("_uuid"):
        return KEY
    if low in RATE_EXACT:
        return RATE
    if low in QUANTITY_EXACT:
        return QUANTITY
    if IDENTIFIER_SUFFIX.search(field):
        return TEXT
    if any(t in low for t in DATE_TOKENS):
        return DATE
    if any(t in low for t in PERCENT_TOKENS):
        return PERCENT
    if any(t in low for t in MONEY_TOKENS):
        return MONEY
    if any(t in low for t in QUANTITY_TOKENS):
        return QUANTITY
    return TEXT


# ── Reading the source ─────────────────────────────────────────────────────
LINE_COMMENT = re.compile(r"//[^\n]*")
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)


def strip_comments(text: str) -> str:
    """⚠ LINE FIRST, THEN BLOCK — DEF-741. Reversing these blanks whole files.

    Each comment is replaced by newlines so line numbers survive.
    """
    def blank(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    return BLOCK_COMMENT.sub(blank, LINE_COMMENT.sub(blank, text))


def sources() -> list[Path]:
    return [
        path
        for path in sorted(SRC.rglob("*.tsx"))
        if ".test." not in path.name and "__fixtures__" not in path.parts
    ]


MEMBER = r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+"
# A JSX text interpolation: `{x.y}` or `{x.y ?? …}`, the brace NOT preceded by
# `=` (an attribute) or `$` (a template hole, handled separately).
JSX_TEXT = re.compile(r"(?<![=$])\{\s*(" + MEMBER + r")\s*(?:\?\?[^{}]*)?\}")
DYNAMIC = re.compile(r"(?<![=$])\{\s*([A-Za-z_]\w*)\[([A-Za-z_]\w*)\]\s*(?:\?\?[^{}]*)?\}")
TEMPLATE_HOLE = re.compile(r"\$\{\s*(" + MEMBER + r")\s*\}")
# A template literal whose value is plainly machinery: a DOM id, a React key,
# a route, a translation key. Its holes are not read by a person.
MACHINE_CONTEXT = re.compile(
    r"(?:\b(?:id|key|htmlFor|to|href|src|name|data-[a-z-]+|className|style|form|"
    r"list|aria-[a-z]+)\s*=\s*\{?\s*$)"
    r"|(?:\b(?:navigate|tenantPath|t|translate|push|replace|useMemo)\s*\(\s*$)"
    # A CSS length inside a `style={{ … }}` object: `width: `${row.bar_pct}%``
    # is a bar's geometry, not a percentage anybody reads.
    r"|(?:\b(?:width|height|top|left|right|bottom|flexBasis|transform|"
    r"gridTemplateColumns|maxWidth|minWidth)\s*:\s*$)",
    re.I,
)
# ⚠ AND THE CONTEXT TEST IS NOT ENOUGH ON ITS OWN, because the machinery is
# often built mid-expression: `navigate(tenantPath(x === "a" ? "/p" : `/p/${x}`))`
# puts a colon, not `tenantPath(`, in front of the backtick. So the literal's
# own SHAPE is read as well: a template whose static text carries no space and
# is made only of route/identifier punctuation is a URL, a DOM id or a React
# key — never a sentence a person reads. `"42864 kWh"` has a space; `/billing/`
# and `-expanded-` do not.
TEMPLATE_BODY = re.compile(r"`([^`]*)`")
MACHINERY_SHAPE = re.compile(r"^[-_/.:#?=&a-zA-Z0-9${}\[\]]*$")


def field_of(expr: str) -> str:
    return re.split(r"[.\[]", expr)[-1].rstrip("]")


def _scan(path: Path):
    """Yield (line_no, expr, kind, source_line) for every text-position render."""
    text = strip_comments(path.read_text())
    for number, line in enumerate(text.splitlines(), 1):
        for match in JSX_TEXT.finditer(line):
            expr = match.group(1)
            yield number, expr, classify(field_of(expr)), line.strip()
        for match in TEMPLATE_HOLE.finditer(line):
            tick = line.rfind("`", 0, match.start())
            if tick == -1:
                continue
            if MACHINE_CONTEXT.search(line[:tick].rstrip() + " "):
                continue
            body = TEMPLATE_BODY.match(line[tick:])
            if body is not None and MACHINERY_SHAPE.match(body.group(1)):
                continue
            expr = match.group(1)
            yield number, expr, classify(field_of(expr)), line.strip()


# ── Clause (b)'s exact pairing, read from the API contract ─────────────────
INTERFACE = re.compile(r"^export interface ([A-Za-z0-9_]+)\s*\{", re.M)
FIELD_DECL = re.compile(r"^\s{2}([a-z][A-Za-z0-9_]*)\??\s*:", re.M)


def _interface_pairs() -> dict[str, set[str]]:
    """Per API interface, the base names it serves a `_display` sibling for.

    ⚠ **READ PER INTERFACE, NEVER AS ONE GLOBAL SET, AND THAT IS THE WHOLE
    ACCURACY OF THIS CLAUSE.** `DiscountRow` declares `value` and
    `value_display`; `value` is also the commonest React prop name in the
    product. A global set flagged **30 sites** on the first run and every one
    of them was a local `props.value` — thirty false positives, in a gate whose
    own docstring says a check that cannot distinguish pass from fail is worse
    than none (DEF-182). Bound to the interface, and the interface bound to the
    file that imports it, the same scan reports **0**, which is the true
    number: every screen that consumes a pairing already renders the sibling.
    """
    if not ENDPOINTS.exists():
        return {}
    text = strip_comments(ENDPOINTS.read_text())
    starts = [(m.start(), m.group(1)) for m in INTERFACE.finditer(text)]
    pairs: dict[str, set[str]] = {}
    for index, (start, name) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(text)
        fields = set(FIELD_DECL.findall(text[start:end]))
        paired = {
            field[: -len("_display")]
            for field in fields
            if field.endswith("_display") and field[: -len("_display")] in fields
        }
        if paired:
            pairs[name] = paired
    return pairs


API_IMPORT = re.compile(
    r"import\s+(?:type\s+)?\{([^}]*)\}\s*from\s*\"@/api/endpoints\";", re.S
)


def siblings_in_scope(path: Path, text: str, pairs: dict[str, set[str]]) -> set[str]:
    """The paired base names THIS file could be holding.

    A file can only render a shape it imports, so the pairings in scope are the
    union of the pairings of the API types it names. Nothing here resolves a
    variable to a type — that would need a TypeScript program, and the import
    list is the 95% of the answer that costs one regex.
    """
    names: set[str] = set()
    for match in API_IMPORT.finditer(text):
        for token in match.group(1).replace("\n", " ").split(","):
            token = token.strip()
            if token:
                names.add(token.split()[-1])
    bases: set[str] = set()
    for name in names:
        bases |= pairs.get(name, set())
    return bases


# ── The three measurements ─────────────────────────────────────────────────
def _measure():
    dynamic: list[str] = []
    ignored: list[str] = []
    untreated: list[str] = []
    pairs = _interface_pairs()

    for path in sources():
        rel = path.relative_to(ROOT)
        text = strip_comments(path.read_text())
        siblings = siblings_in_scope(path, text, pairs)
        for number, line in enumerate(text.splitlines(), 1):
            for match in DYNAMIC.finditer(line):
                dynamic.append(f"{rel}:{number}  {match.group(0)}\n      {line.strip()[:100]}")
        for number, expr, kind, source in _scan(path):
            field = field_of(expr)
            if field in siblings:
                ignored.append(f"{rel}:{number}  {expr}  (sibling: {field}_display)")
            elif kind in (MONEY, QUANTITY, PERCENT, RATE, KEY):
                untreated.append(f"{rel}:{number}  [{kind}] {expr}\n      {source[:100]}")
    return dynamic, ignored, untreated


def run() -> tuple[str, str]:
    """`("PASS"|"FAIL"|"SKIP", detail)` — the runner's contract, not a bool.

    ⚠ **THIS RETURNED `(True, …)` IN ITS FIRST COMMIT AND THE RUNNER REJECTED
    IT AS `gate returned invalid status True`.** Standalone the module printed
    PASS, because `main()` reads the first element as truthy; only
    `run_gates.py` — the file CI actually runs — could tell the difference. It
    is the same shape as hard-won law 2 (built is not wired) and the reason
    G42 exists: a gate that is not correctly plugged into the runner is a
    script with a gate's docstring.
    """
    if not SRC.exists():
        return "SKIP", "07-frontend/src does not exist yet"

    dynamic, ignored, untreated = _measure()
    failures: list[str] = []
    details: list[str] = []

    if len(dynamic) > DYNAMIC_KEY_BASELINE:
        failures.append(
            f"clause (a) — {len(dynamic)} cell renderer(s) index a row by a "
            f"variable (baseline {DYNAMIC_KEY_BASELINE}). A renderer that does "
            "not NAME its field cannot format it (DEF-1086):\n    "
            + "\n    ".join(dynamic)
        )
    details.append(f"(a) dynamic-key renders {len(dynamic)}/{DYNAMIC_KEY_BASELINE}")

    if len(ignored) > SIBLING_IGNORED_BASELINE:
        failures.append(
            f"clause (b) — {len(ignored)} raw render(s) of a field the server "
            f"already composes (baseline {SIBLING_IGNORED_BASELINE}). Render "
            "the `_display` sibling; it carries the unit and the ruled "
            "precision (BR-SHL-250):\n    " + "\n    ".join(ignored)
        )
    details.append(f"(b) siblings ignored {len(ignored)}/{SIBLING_IGNORED_BASELINE}")

    banked = _read_baseline()
    if len(untreated) > banked:
        failures.append(
            f"clause (c) — {len(untreated)} classified value(s) reach a text "
            f"position untreated; the banked ratchet is {banked}. A NEW one was "
            "added:\n    " + "\n    ".join(untreated)
        )
    elif len(untreated) < banked:
        failures.append(
            f"clause (c) — the ratchet is stale: {len(untreated)} untreated "
            f"render(s) remain and {banked} are banked. A fall that is not "
            "banked is a number nobody reads (DEF-490). Update "
            f"{BASELINE_FILE.name}."
        )
    details.append(f"(c) untreated {len(untreated)}/{banked}")

    if failures:
        return "FAIL", "\n  ".join(failures)
    return "PASS", " · ".join(details)


def _read_baseline() -> int:
    if not BASELINE_FILE.exists():
        return UNTREATED_BASELINE
    for line in BASELINE_FILE.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("COUNT"):
            return int(stripped.split()[-1])
    return UNTREATED_BASELINE


def main() -> int:
    status, detail = run()
    print(f"G44 display-truth: {status} — {detail}")
    return 0 if status in ("PASS", "SKIP") else 1


if __name__ == "__main__":
    sys.exit(main())
