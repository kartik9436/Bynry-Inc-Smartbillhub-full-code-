#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects: DEF-CWP-3925 (six doors shut over live screens) · DEF-CWP-3959 (a
#          card greyed 32 hours over a live screen) · DEF-CWP-3962 (the bills
#          list held *Pay* after Pay now shipped) · DEF-CWP-3824 (a disabled
#          CTA over a served endpoint) · DEF-CWP-3988 (ten drawn-but-unbuilt
#          screens — the holds pointing at them are the ones that rot next)
# Rules:   CLAUDE.md hard-won law 2, mirror clause (*"when you write a hold,
#          write the test that fires when the hold expires, in the same
#          commit"*) · law 7 (proved RED first, through run_gates and not
#          through __main__ — DEF-GOV-3733) · law 1 (a comment claiming a
#          guarantee is not the guarantee) · CR-068 R3 · B14 rule 33
# Tests:   selftest() below
# Impacts: 07-frontend/src/portal/routing/holds.ts · screenIds.ts ·
#          06-backend/apps/** · every file drawing a held control
# ───────────────────────────────────────────────────────
"""G103 — a hold states what would release it, and has not been released yet.

WHY THIS EXISTS
---------------
A hold is a rule with a **clock** in it. It is true the day it is written and
false the day the thing it waits for arrives, and **landing a screen and
releasing the control that points at it are two acts — only the first feels
like the work.** In one week on this product that cost four customer-facing
defects:

  * `DEF-CWP-3925` — the portal front page had **two working doors out of
    eight**; five cards and the sign-in bar refused over screens shipped days
    earlier.
  * `DEF-CWP-3959` — `CWP-046`'s *Something else* was grey with *"Not online
    yet — ring us"* for **32 hours** over a screen headed ASK US SOMETHING that
    had landed 73 minutes after the hold was written.
  * `DEF-CWP-3962` — the bills list held *Pay* saying *"Online payment arrives
    later this year"* after `CWP-038` *Pay now* had shipped.
  * `DEF-CWP-3824` — Settings' *New answer* disabled over `create_answer`,
    which is routed, audited and working.

**Every check in this repo was green over all four.** `tsc` passes. 42 portal
test files and 391 cases pass — because each wave tested ITS OWN screen at ITS
OWN address. `G13` passes: it asks whether a prop is *passed*, never whether a
refusal is still *true*. `G100` passes: it asks whether anything *points* at a
screen, and it credits a held control as a pointer — it says so itself under
WHAT IT CANNOT SEE. The gap is not an oversight in any of them; **nobody owned
the question "is this refusal still true".** This gate owns it.

WHAT IT ASSERTS
---------------
Three things, and the first is what makes the other two possible:

  1. **Every hold in the portal has a row in `holds.ts`.** A hold is found by
     its reason's i18n key; the convention every catalogue already follows
     without exception is that such a key contains `Held`/`held`/`Blocked`.
     A lane that adds a held control adds a row saying what would release it,
     or its merge fails. This is the half that keeps the register from
     silently stopping covering the holds — *a gate that cannot fail*.
  2. **A row of kind `screen` names a `CWP-###` that is NOT in
     `PORTAL_SCREENS`.** The day it appears there, the hold has rotted and
     this gate names the control. That is `DEF-CWP-3959` and `DEF-CWP-3962`
     caught the morning they happened instead of a day or a week later.
  3. **A row of kind `endpoint` names a Python symbol that is NOT defined
     under `06-backend/apps/`.** The day it is, the hold has rotted. That is
     `DEF-CWP-3824`: a disabled CTA over a served endpoint.

Rows of kind `server`, `form`, `policy` and `fact` **cannot rot** — the server
re-answers them on every draw, or the person has not filled the form in, or a
ruling settles it, or it was never a refusal. They still need a row, because
classifying a hold is what makes the ones that CAN rot visible.

WHAT IT CANNOT SEE, STATED PLAINLY (hard-won law 1)
---------------------------------------------------
  * **`unwatched` rows.** A capability with no screen id and no symbol — a PDF
    download, SMS activating in W8 — has nothing mechanical to watch. The kind
    exists so the admission is COUNTED and printed rather than implied; it is
    the same admission `ERRAND_HELD_UNTIL`'s `null` already makes. **13 of the
    36 live holds are in this state**, and that number is the honest measure of
    how much of this problem a gate can reach.
  * **A symbol landing under a name the row did not guess.** A row therefore
    only names a symbol that is already defined (the hold has ALREADY rotted,
    and this gate is red today) or one the seam convention forces.
  * **Whether a hold's WORDS are true** — only whether the condition it claims
    is still unmet. B14 rule 33 (five or six words) is `G37`'s.
  * **Rendered output.** Nothing in this repo reads it; that is the
    walkthrough's job and it is why these four defects reached a customer.

PROVEN RED FIRST (law 7, both halves)
-------------------------------------
`selftest()` replays seven cases on in-memory sources:

  1. a clean world — silent;
  2. a hold with no row in the register — named;
  3. **a `screen` row whose screen has landed** — the `DEF-CWP-3962` shape;
  4. **an `endpoint` row whose symbol is served** — the `DEF-CWP-3824` shape;
  5. **a key that appears only inside a comment** — must NOT be treated as a
     hold. `G100` learned this the hard way: a gate that reads the sentence
     describing a defect as the defect teaches the next lane to delete the
     explanation to make it pass;
  6. a register row nothing uses any more — a released hold whose copy is
     still being carried, named so the catalogue can be cleaned.

The RED PROOF ON THE REAL TREE is `settings.portalHelp.addHeld`, which is red
on the day this gate lands and stays red until `DEF-CWP-3824` is fixed.

Both proofs are run **through the `run_gates` registry**, never through
`__main__` — `DEF-GOV-3733` is a gate announced green on a proof that exercised
only the path a person uses by hand.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FRONTEND = REPO / "07-frontend" / "src"
HOLDS = FRONTEND / "portal" / "routing" / "holds.ts"
REGISTER = FRONTEND / "portal" / "routing" / "screenIds.ts"
BACKEND = REPO / "06-backend" / "apps"

#: `{ path: "/bills", id: "CWP-027", blueprint: "P13", … }` — the same shape
#: `g100` and `tests/test_cwp_holds_expire.py` parse, deliberately: one
#: literal, three readers, and a divergence in the regex is a divergence in the
#: answer.
REGISTER_ROW = re.compile(
    r'\{\s*path:\s*"([^"]*)",\s*id:\s*"(CWP-\d{3,5}(?!\d))",\s*blueprint:\s*"([^"]*)"', re.S
)

#: `"portal.money.receiptHeld": { kind: "screen", screen: "CWP-035", …` — a row
#: of the register. `kind` is read; the rest of the object is prose for a human.
HOLD_ROW = re.compile(
    r'"([A-Za-z][\w.*]*)"\s*:\s*\{\s*kind:\s*"(\w+)"'
    r'(?:\s*,\s*screen:\s*"([^"]*)")?'
    r'(?:\s*,\s*symbol:\s*"([^"]*)")?',
    re.S,
)

#: A hold's reason key, as it is written at a call site. Two spellings, because
#: a template literal CONTAINS quotes — ``t(`portal.methods.autopayBlocked.${x ?? "unknown"}`)`` —
#: and one pattern that tried to cover both stopped at the `"` inside and
#: reported a live hold as absent. That is `G100`'s own two-group lesson.
HOLD_KEY_QUOTED = re.compile(r"""["']((?:portal|settings)\.[\w.]+)["']""")
HOLD_KEY_TEMPLATE = re.compile(r"`((?:portal|settings)\.[^`]*)`")

#: ⚠ **THE TEST IS APPLIED TO THE NORMALISED KEY, NEVER TO THE RAW TEXT, AND
#: THE ORDER IS THE WHOLE POINT.** `Overdue.tsx` writes
#: ``t(`portal.protections.kind.${held.kind}`)`` — the INTERPOLATION is named
#: `held`, so a pattern that looked for the word inside the backticks reported
#: a live protections label as an unregistered hold. Strip `${…}` first, then
#: ask whether what remains is a hold key. Same class as `G100`'s comment case:
#: a gate that reads the wrong span of text cannot distinguish pass from fail.
IS_HOLD_KEY = re.compile(r"(?:[Hh]eld|[Bb]locked)")

#: `data-screen="CWP-071"` — a file that DECLARES a portal screen is in scope
#: wherever it lives, which is how the staff-side `CWP-071`/`CWP-073` settings
#: screens are covered without dragging in the whole staff app.
DECLARES_SCREEN = re.compile(r'data-screen="CWP-\d+"')

#: `def create_answer(` anywhere under `06-backend/apps/`.
def _py_defines(symbol: str, sources: dict[str, str]) -> bool:
    pattern = re.compile(rf"^\s*def\s+{re.escape(symbol)}\s*\(", re.M)
    return any(pattern.search(text) for text in sources.values())


BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"^\s*//.*$", re.M)


def strip_comments(text: str) -> str:
    """Prose is not code.

    ⚠ **A GATE THAT READS THE SENTENCE DESCRIBING A DEFECT AS THE DEFECT
    TEACHES THE NEXT LANE TO DELETE THE EXPLANATION TO MAKE IT PASS.** `G100`'s
    self-test caught exactly this before it was trusted. Here it is not
    hypothetical: `PayNow.tsx` explains at length that `heldNoPreview` was
    REMOVED and why (`DEF-CWP-3970`), and a scan that counted that mention
    would demand a register row for a hold that no longer exists.
    """
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", text))


def _family(key: str) -> str:
    """`portal.payNow.held.${code}` → `portal.payNow.held.*`.

    A key built from a server code is one hold with many sentences, and the
    register carries the FAMILY. A fully-written member of a family that is
    already registered (`portal.payNow.held.no_saved_payment_method`) resolves
    to the same row rather than demanding its own.
    """
    return re.sub(r"\$\{[^}]*\}", "*", key)


def read_holds(text: str) -> dict[str, tuple[str, str | None, str | None]]:
    """`{reason key: (kind, screen, symbol)}` from `holds.ts`."""
    return {m.group(1): (m.group(2), m.group(3), m.group(4)) for m in HOLD_ROW.finditer(text)}


def read_screens(text: str) -> set[str]:
    return {m.group(2) for m in REGISTER_ROW.finditer(text)}


def find_holds(sources: dict[str, str]) -> dict[str, set[str]]:
    """`{reason key family: the files that draw it}` — comments already gone."""
    out: dict[str, set[str]] = {}
    for name, raw in sources.items():
        if name.endswith("routing/holds.ts"):
            continue  # the register is not a call site
        text = strip_comments(raw)
        for pattern in (HOLD_KEY_QUOTED, HOLD_KEY_TEMPLATE):
            for m in pattern.finditer(text):
                key = _family(m.group(1))
                if IS_HOLD_KEY.search(key) is None:
                    continue
                out.setdefault(key, set()).add(name)
    return out


def check(
    front: dict[str, str],
    holds_ts: str,
    register_ts: str,
    backend: dict[str, str],
) -> tuple[list[str], dict[str, int]]:
    """Returns (problems, how many holds of each kind).

    ⚠ **THE TALLY IS THE POINT OF THE PASS LINE, NOT DECORATION.** A first
    draft printed *"N are watched mechanically"* and counted `server`, `form`,
    `policy` and `fact` among them — which reads as *this gate is guarding 23
    holds* when it is guarding one. A summary that cannot distinguish what is
    checked from what merely cannot rot is `DEF-182`'s flaw: a check that is
    trusted because its output looks like a pass.
    """
    problems: list[str] = []
    # ⚠ **THE REGISTER'S COMMENTS COME OFF HERE, AND THEY DID NOT UNTIL
    # 2026-09-06 (`DEF-CWP-4149`).** `holds.ts` was the ONE file this gate read
    # raw: every call site goes through `strip_comments` in `find_holds`, and
    # the register — the most prose-heavy file of the lot, by its own house
    # style — did not. `HOLD_ROW` wants `kind:` after the opening brace across
    # WHITESPACE, so a single `//` line inside a row made that row invisible and
    # the gate reported *"no row in holds.ts"* about a row plainly in the file.
    # ⚠ **AND `_selftest` COULD NEVER HAVE FOUND IT**: it passes `clean_holds`,
    # comment-free fixture text, so all four of its cases exercised a path the
    # real run does not take (CLAUDE.md law 7 — prove it in the harness that
    # will run it). Case 5 now puts a comment inside a row.
    registry = read_holds(strip_comments(holds_ts))
    screens = read_screens(register_ts)
    tally: dict[str, int] = {}
    if not registry:
        return ["holds.ts parsed to no rows — the literal's shape moved"], tally
    if not screens:
        return ["screenIds.ts parsed to no rows — the literal's shape moved"], tally

    drawn = find_holds(front)

    # 1 · every hold drawn has a row saying what would release it
    for key in sorted(drawn):
        if key in registry:
            continue
        # a fully-written member of a registered family is covered by it
        if any(fam.endswith(".*") and key.startswith(fam[:-1]) for fam in registry):
            continue
        where = ", ".join(sorted(drawn[key]))
        problems.append(
            f"{key} is a hold drawn in {where} with no row in "
            f"07-frontend/src/portal/routing/holds.ts. Add one saying what would "
            f"release it — a hold with no stated expiry is a promise nobody is keeping."
        )

    # 2 · a row nothing draws any more — a released hold still carrying its copy
    for key in sorted(registry):
        if key in drawn:
            continue
        if key.endswith(".*") and any(d.startswith(key[:-1]) for d in drawn):
            continue
        problems.append(
            f"{key} has a row in holds.ts and nothing draws it. If the hold was "
            f"released, drop the row AND the key from all eleven catalogues; if it "
            f"moved, update the row."
        )

    for key, (kind, screen, symbol) in sorted(registry.items()):
        tally[kind] = tally.get(kind, 0) + 1
        # 3 · a hold waiting on a screen that has landed
        if kind == "screen":
            if not screen:
                problems.append(f"{key} is kind 'screen' with no screen id")
            elif screen in screens:
                problems.append(
                    f"THE HOLD ON {key} HAS ROTTED: it waits for {screen}, and {screen} "
                    f"is now a routed screen in screenIds.ts. Release the control — give "
                    f"it a link to that screen — and drop this row. "
                    f"(hard-won law 2's mirror; DEF-CWP-3925, DEF-CWP-3959, DEF-CWP-3962.)"
                )
        # 4 · a hold waiting on an endpoint that is served
        elif kind == "endpoint":
            if not symbol:
                problems.append(f"{key} is kind 'endpoint' with no symbol")
            elif _py_defines(symbol, backend):
                problems.append(
                    f"THE HOLD ON {key} HAS ROTTED: it says a capability is not built, "
                    f"and `def {symbol}` is defined under 06-backend/apps/. Release the "
                    f"control or rewrite the reason to something that cannot rot. "
                    f"(DEF-CWP-3824 — the third disabled CTA over a served endpoint.)"
                )
        elif kind not in {"server", "form", "policy", "fact", "unwatched"}:
            problems.append(f"{key} has kind '{kind}', which is not one of the seven")

    return problems, tally


def _load(root: Path, suffixes: tuple[str, ...], keep) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.suffix not in suffixes or not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if ".test." in rel:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if keep(rel, text):
            out[rel] = text
    return out


def run() -> tuple[str, str]:
    """⚠ **`tuple[str, str]`, NOT AN EXIT CODE.** `run_gates` does
    `status, detail = module.run()`; a gate returning an int unpacks into
    nothing and is reported as *gate returned invalid status*. The first draft
    of this file returned `int` and was green by hand and broken in the suite —
    `DEF-GOV-3733` exactly, caught here by reading the runner rather than by
    trusting `python3 g103_holds_cannot_rot.py`."""
    ok, detail = selftest()
    if not ok:
        return "FAIL", f"self-test: {detail}"
    if not HOLDS.exists():
        return "FAIL", f"{HOLDS} is missing; it is the register this gate reads"
    front = _load(
        FRONTEND,
        (".ts", ".tsx"),
        lambda rel, text: rel.startswith("portal/") or DECLARES_SCREEN.search(text) is not None,
    )
    backend = _load(BACKEND, (".py",), lambda rel, text: True)
    holds_text = HOLDS.read_text(encoding="utf-8")
    problems, tally = check(front, holds_text, REGISTER.read_text(encoding="utf-8"), backend)
    if problems:
        head = " | ".join(problems[:4])
        more = f" (+{len(problems) - 4} more)" if len(problems) > 4 else ""
        return "FAIL", head + more
    total = sum(tally.values())
    guarded = tally.get("screen", 0) + tally.get("endpoint", 0)
    blind = tally.get("unwatched", 0)
    return "PASS", (
        f"all {total} holds in the customer portal state what would release them and none has "
        f"rotted; {guarded} {'waits' if guarded == 1 else 'wait'} on a screen id or a served "
        f"symbol and {'is' if guarded == 1 else 'are'} guarded here, "
        f"{blind} {'waits' if blind == 1 else 'wait'} on something nothing mechanical can see "
        f"and {'says' if blind == 1 else 'say'} so, and "
        f"{total - guarded - blind} cannot rot at all (the server re-answers them, the form is "
        f"unfinished, a ruling settles it, or it was never a refusal); self-test: an "
        f"unregistered hold, a screen that landed, a symbol that is served, a key that is only "
        f"in a comment and a row nothing draws all bite"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: G103 — {detail}")
    return 1 if status == "FAIL" else 0


def selftest() -> tuple[bool, str]:
    """Six cases, on in-memory sources. Cases 4 and 5 are the ones that bite."""
    reg = (
        '{ path: "/pay-now", id: "CWP-038", blueprint: "P24", title: "Pay now" },\n'
        '{ path: "/bills", id: "CWP-027", blueprint: "P13", title: "Bills" },'
    )
    served = {"portal/x.py": "def create_answer(actor):\n    pass\n"}
    bare: dict[str, str] = {"portal/x.py": "pass\n"}

    clean_holds = (
        '{ "portal.a.fooHeld": { kind: "screen", screen: "CWP-035", note: "x" },\n'
        '  "portal.b.barHeld": { kind: "form", note: "y" } }'
    )
    clean_front = {
        "portal/A.tsx": 't("portal.a.fooHeld")',
        "portal/B.tsx": 't("portal.b.barHeld")',
    }

    # 1 · clean world
    problems, _tally = check(clean_front, clean_holds, reg, bare)
    if problems:
        return False, f"case 1 (clean) should be silent, got {problems}"

    # 2 · a hold nothing registered
    problems, _ = check(
        {**clean_front, "portal/C.tsx": 't("portal.c.newHeld")'}, clean_holds, reg, bare
    )
    if not any("portal.c.newHeld" in p and "no row" in p for p in problems):
        return False, f"case 2 (unregistered hold) did not bite: {problems}"

    # 3 · a screen row whose screen has landed — DEF-CWP-3962's shape
    rotted = clean_holds.replace('screen: "CWP-035"', 'screen: "CWP-038"')
    problems, _ = check(clean_front, rotted, reg, bare)
    if not any("HAS ROTTED" in p and "CWP-038" in p for p in problems):
        return False, f"case 3 (screen landed) did not bite: {problems}"

    # 4 · an endpoint row whose symbol is served — DEF-CWP-3824's shape
    ep = clean_holds.replace(
        '{ kind: "form", note: "y" }', '{ kind: "endpoint", symbol: "create_answer", note: "y" }'
    )
    problems, _ = check(clean_front, ep, reg, served)
    if not any("HAS ROTTED" in p and "create_answer" in p for p in problems):
        return False, f"case 4 (symbol served) did not bite: {problems}"
    problems, _ = check(clean_front, ep, reg, bare)
    if problems:
        return False, f"case 4b (symbol absent) should be silent, got {problems}"

    # 5 · a key that appears ONLY in a comment is not a hold
    commented = {
        **clean_front,
        "portal/D.tsx": '/* until 2026-09-05 this used portal.d.goneHeld */\n// t("portal.d.goneHeld")\n',
    }
    problems, _ = check(commented, clean_holds, reg, bare)
    if problems:
        return False, f"case 5 (key only in a comment) should be silent, got {problems}"

    # 6 · a register row nothing draws any more
    problems, _ = check({"portal/A.tsx": 't("portal.a.fooHeld")'}, clean_holds, reg, bare)
    if not any("portal.b.barHeld" in p and "nothing draws it" in p for p in problems):
        return False, f"case 6 (orphan row) did not bite: {problems}"

    # 7 · A ROW CARRYING A COMMENT IS STILL A ROW (DEF-CWP-4149). This case
    #     exists because cases 1-6 all run on comment-free text and the real
    #     register is prose. Proved RED against the pre-fix `read_holds(holds_ts)`:
    #     `case 7 (a commented row) did not resolve: ['portal.a.fooHeld is a hold
    #     drawn in portal/A.tsx with no row in 07-frontend/src/portal/routing/
    #     holds.ts. …']`
    commented = clean_holds.replace(
        '"portal.a.fooHeld": {', '"portal.a.fooHeld": {\n    // why this is held\n'
    )
    problems, _ = check(clean_front, commented, reg, bare)
    if any("portal.a.fooHeld" in p and "no row" in p for p in problems):
        return False, f"case 7 (a commented row) did not resolve: {problems}"

    return True, "seven cases"


if __name__ == "__main__":
    sys.exit(main())
