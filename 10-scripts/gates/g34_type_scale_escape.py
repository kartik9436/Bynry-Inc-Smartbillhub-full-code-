#!/usr/bin/env python3
"""G34 — the ruled type scale has no back door.

WHY THIS GATE EXISTS (CR-018 Phase 2b, 2026-08-19)
--------------------------------------------------
Phase 0 cleared Tailwind's `--text-*` namespace, and every document written
since has described that as the enforcement point: *"there is no class name to
get wrong because there is no class name"*. **That is half of a fence.** Clearing
the namespace kills `text-2xl`. It does NOT kill `text-[12.5px]` — Tailwind's
arbitrary-value syntax compiles whatever is inside the brackets, from a
namespace no `@theme` block can empty. So every half-step Phase 2 spent a day
absorbing (10.5 · 12.5 · 13.5 · 9px) can come straight back in bracket notation,
and NOTHING in this repo would have seen it: `tsc` is happy, `eslint` was happy,
`vitest` reads no rendered output, and G31 skips Route-B files by design.

⚠ AND IT WAS NOT HYPOTHETICAL. The first run of this gate found **seven** live
uses in `features/rating/RateSchedulesTab.tsx` — `text-[13px]` five times and
`text-[12px]` twice — written by the ONE component Route B has migrated so far.
Both values ARE ruled steps (`--text-base` is 13px, `--text-sm` is 12px), so the
utilities `text-base` and `text-sm` say the same thing by name and could not
drift. Bracket notation said it as a number instead, one commit after the phase
whose entire purpose was removing numbers. That is what an unguarded escape
hatch costs, measured rather than argued.

WHAT IT CHECKS — three things, and the third is the one with teeth
-----------------------------------------------------------------
1. **No arbitrary TYPE value in any frontend source file.** `text-[<length>]`,
   `leading-[…]`, `tracking-[…]`, `font-[…]`. Zero tolerance.

   ⚠ `text-[…]` IS OVERLOADED AND THIS GATE IS DELIBERATELY NARROW. Tailwind's
   `text-` prefix carries BOTH the size and the colour, so
   `text-[color-mix(in_srgb,var(--color-text)_70%,transparent)]` is an arbitrary
   COLOUR and is **not** a violation here — it is in fact the correct spelling,
   because the opacity modifier that would replace it (`text-text/70`) emits
   `color-mix(in oklab)` and this design system writes `in srgb`. A gate that
   fired on it would be switched off inside a week, and a rule nobody runs is
   the defect this gate was written to answer. Only a LENGTH inside the brackets
   is a type value.

2. **No inline `fontSize` in TS/TSX.** `style={{ fontSize: … }}` bypasses both
   the stylesheet and the utility layer. There were zero when this landed, which
   is exactly when a ban is free.

3. **The count of literal `font-size: <n><unit>` declarations in the app's own
   stylesheets is EXACT** — the `surface_debt.txt` discipline. Up means a new
   hand-written size shipped; down means someone fixed one and left the register
   claiming debt it has paid off, and DEF-077 says that is red too.

   The two token files are excluded: `tokens.css` and `tailwind.css` are where a
   size is ALLOWED to be a literal, because they are the one declaration site.
   Comments are stripped first — three of the matches on disk are prose quoting
   the rule, and a gate that counts its own documentation is measuring nothing.

THE SIX THAT ARE LEFT, AND WHY THE RATCHET IS 6 AND NOT 0
----------------------------------------------------------
Phase 2b closed the >=16px tier and stopped at six sites, each with its reason in
its own file and all six raised as **OQ-279**:

  * `DataTable` column-chooser summary 16px and `PricingPage .pricing-lede` 16px
    — a CONTROL and PROSE at `--text-h5`'s value. `tailwind.css` rules that the
    heading steps are pointed at real headings only (they carry the heading
    weight, leading and tracking with them), and the scale has no non-heading
    16px name.
  * `AppShell .sidebar .brand` 18px and `reads .rd-netpair-value` 18px — no 18px
    step exists. r10 sets the brand at exactly 18px, so moving it diverges FROM
    the design authority.
  * `SettingsPage .settings-frame-title` 24px and `RoutesCyclesWizards .rcw-title`
    24px — no 24px step; `--text-h3` is 25 and `--text-metric-sm` is 22 and is a
    metric name, and both are pixel moves nobody ruled.

Answering OQ-279 is what lowers this number. Absorbing one by eye is what the
exact ratchet exists to make visible.

WHAT IT CANNOT SEE, so that nobody trusts it for more than it does
------------------------------------------------------------------
* A size written in a `.css` file as `var(--text-h5)` on a control — the value
  is right and the ROLE is wrong, and no regex can tell a control from a
  heading. That is OQ-279's territory and a human's.
* A size arriving at runtime — a computed style set by JS, or a `font` shorthand.
* Anything outside `07-frontend/src`. The prototype under `05-prototype/` is a
  reference and is deliberately not scanned.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_SRC = REPO_ROOT / "07-frontend" / "src"

# The one declaration site: a literal here is the token, not a hand-nudge.
TOKEN_FILES = {"tokens.css", "tailwind.css"}

# EXACT, not a ceiling (DEF-077). All OQ-279 — see the docstring.
#
# 6 -> 5 on 2026-08-22 (CR-018 long tail round 3, W14). OQ-279 was RULED that day
# (option A: NAME the roles rather than snap the values), and `--text-lead` — 16px
# with none of the heading weight/leading/tracking the `--text-h*` steps carry as
# v4 modifiers — is what `PricingPage .pricing-lede` had been waiting for. That
# stylesheet is deleted and the lede is `text-lead`. The other five are NOT
# blocked on a name any more; they are blocked on their FILE:
#   · `DataTable.css` 16px and `AppShell.css` 18px — `--text-lead` / `--text-brand`
#     answer both, and both files are held by other lanes.
#   · `reads.css` 18px — `--text-brand`; `features/metering` is held by CR-026.
#   · `RoutesCyclesWizards.css` and `SettingsPage.css` 24px — `--text-panel`
#     answers both, and both files ALSO hold `line-height` literals (1.9, and
#     1.6/1.9) that OQ-279's four `--leading-*` names do NOT reach, so neither
#     file can be migrated whole yet. See OQ-337.
#
# 5 -> 4 on 2026-08-22 (CR-018 long tail round 4, W14). OQ-337 was RULED that day
# (option A again: `--leading-prose` 1.6 · `--leading-note` 1.7 ·
# `--leading-sample` 1.9, at the values already in use), which is what released
# `RoutesCyclesWizards.css`: its `.rcw-preview` 1.9 is `leading-sample` now, and
# with the leading answered the 24px `.rcw-title` could finally take
# `--text-panel`. The stylesheet is deleted. The four that remain are each held
# by their FILE, not by a missing name:
#   · `AppShell.css` 18px -> `--text-brand`, and `DataTable.css` 16px ->
#     `--text-lead`; both files are held by the shared-components lane.
#   · `reads.css` 18px -> `--text-brand`; `features/metering` is held by CR-026.
#   · `SettingsPage.css` 24px -> `--text-panel`; 1,115 lines, and its whole
#     `settings-*` vocabulary is named from `features/metering` and
#     `features/customers`, which round 4 may not touch.
LITERAL_FONT_SIZE_BASELINE = 4

_UNIT = r"(?:px|rem|em|ch|ex|vw|vh|vmin|vmax|pt|pc|%)"

# `text-[13px]` / `text-[1.5rem]` — a LENGTH in the brackets. `text-[#fff]` and
# `text-[color-mix(…)]` are colours and are deliberately not matched; see the
# docstring for why narrowing this is what keeps the rule switched on.
ARBITRARY_TYPE = re.compile(
    r"(?<![\w-])(?:"
    rf"text-\[\s*-?[\d.]+{_UNIT}\s*\]"
    r"|leading-\[[^\]]*\]"
    r"|tracking-\[[^\]]*\]"
    r"|font-\[[^\]]*\]"
    r")"
)

INLINE_FONT_SIZE = re.compile(r"\bfontSize\b")

# A declaration, not a token: `font-size: 13px` but never `--table-font-size:`.
LITERAL_FONT_SIZE = re.compile(rf"(?<!-)\bfont-size\s*:\s*-?[\d.]+{_UNIT}")

_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
# ⚠ `[ \t]*`, NOT `\s*`. `\s` matches a newline, so `^\s*` swallowed the blank
# line above a comment and the replacement spaces destroyed it — the first run of
# this gate reported RateSchedulesTab.tsx:414 for a hit on line 419, five lines out
# and getting worse down the file. A gate that names the wrong line sends the next
# lane to edit the wrong code.
_LINE_COMMENT = re.compile(r"^[ \t]*(?://|\*|/\*).*$", re.MULTILINE)


def _source_files(*suffixes: str) -> list[Path]:
    if not FRONTEND_SRC.is_dir():
        return []
    return sorted(p for p in FRONTEND_SRC.rglob("*") if p.suffix in suffixes)


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _strip_comments(text: str, is_css: bool) -> str:
    """Blank out comments, KEEPING newlines so line numbers survive."""
    # ⚠ **LINE COMMENTS GO FIRST ON A .tsx FILE — DEF-741.** `// …/*.json` in a
    # line comment contains `/*`, and blanking block comments first opens one
    # there that closes at the next `*/` below. A .css file has no line
    # comments, so the order only matters for the branch that has both.
    stripped = text
    if not is_css:
        stripped = _LINE_COMMENT.sub(lambda m: " " * len(m.group(0)), stripped)
    return _CSS_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), stripped)


def arbitrary_type_values() -> list[str]:
    found: list[str] = []
    for path in _source_files(".ts", ".tsx", ".css", ".html"):
        text = _strip_comments(path.read_text(encoding="utf-8", errors="replace"), path.suffix == ".css")
        for number, line in enumerate(text.splitlines(), start=1):
            for hit in ARBITRARY_TYPE.findall(line):
                found.append(f"{_rel(path)}:{number}: `{hit}` — an arbitrary type value")
    return found


def inline_font_sizes() -> list[str]:
    found: list[str] = []
    for path in _source_files(".ts", ".tsx"):
        text = _strip_comments(path.read_text(encoding="utf-8", errors="replace"), False)
        for number, line in enumerate(text.splitlines(), start=1):
            if INLINE_FONT_SIZE.search(line):
                found.append(f"{_rel(path)}:{number}: inline `fontSize` — B14 rule 5 forbids inline font sizes")
    return found


def literal_font_sizes() -> list[str]:
    found: list[str] = []
    for path in _source_files(".css"):
        if path.name in TOKEN_FILES:
            continue
        text = _strip_comments(path.read_text(encoding="utf-8", errors="replace"), True)
        for number, line in enumerate(text.splitlines(), start=1):
            for hit in LITERAL_FONT_SIZE.findall(line):
                found.append(f"{_rel(path)}:{number}: `{hit.strip()}`")
    return found


def check() -> tuple[list[str], list[str], list[str]]:
    return arbitrary_type_values(), inline_font_sizes(), literal_font_sizes()


def _summary(arbitrary: list[str], inline: list[str], literals: list[str]) -> tuple[bool, str]:
    if arbitrary:
        return False, (
            f"{len(arbitrary)} arbitrary type value(s) — the ruled scale has a name for every "
            f"step: {arbitrary[0]}"
        )
    if inline:
        return False, f"{len(inline)} inline fontSize: {inline[0]}"
    if len(literals) > LITERAL_FONT_SIZE_BASELINE:
        return False, (
            f"{len(literals)} literal font-size declaration(s), {LITERAL_FONT_SIZE_BASELINE} "
            f"baselined — a new hand-written size shipped: {literals[-1]}"
        )
    if len(literals) < LITERAL_FONT_SIZE_BASELINE:
        return False, (
            f"{len(literals)} literal font-size declaration(s), DOWN from "
            f"{LITERAL_FONT_SIZE_BASELINE} — lower LITERAL_FONT_SIZE_BASELINE to "
            f"{len(literals)} in the same commit as the fix (DEF-077)"
        )
    return True, (
        f"no arbitrary type value, no inline fontSize, {len(literals)} literal font-size "
        "declaration(s) — every one is OQ-279 territory, and OQ-337 for the leadings"
    )


def main() -> int:
    arbitrary, inline, literals = check()
    for violation in arbitrary[:12] + inline[:12]:
        print(f"FAIL: {violation}")
    ok, detail = _summary(arbitrary, inline, literals)
    if not ok:
        print(f"\n{detail}")
        if literals and len(literals) != LITERAL_FONT_SIZE_BASELINE:
            for literal in literals:
                print(f"  literal: {literal}")
        return 1
    print(detail)
    return 0


def run():
    """Runner contract: ('PASS'|'FAIL'|'SKIP', detail)."""
    if not FRONTEND_SRC.is_dir():
        return "SKIP", f"{_rel(FRONTEND_SRC)} does not exist yet"
    ok, detail = _summary(*check())
    return ("PASS" if ok else "FAIL"), detail


if __name__ == "__main__":
    raise SystemExit(main())
