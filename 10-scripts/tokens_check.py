#!/usr/bin/env python3
"""tokens_check.py — WHICH HAND-WRITTEN LENGTHS IN OUR STYLESHEETS ARE OFF THE RULED SCALE.

WHY THIS FILE EXISTS, AND THE FINDING IS THE REASON (`P2.17`, Finance blueprint
p15, 2026-09-24)
--------------------------------------------------------------------------------
`P2.17`'s REFERENCE column names `tokens_check.py` as though it were a tool this
repository already owns. **It was not.** `find . -iname "*token*"` over the tree
returned `tokens.css`, a render-check, a portal draft-token module, a backend
test and a journey — and no such script, at any path, in any revision. This is
`P2.14`'s finding one row further down the same table: *"This document named the
component before checking it was real"*, and the blueprint said it of itself.

So this is the tool, written to the description the blueprint gives it: **an
AUDIT that is triaged per file, and deliberately NOT a gate.** It prints and it
exits 0. Nothing in `run_gates` imports it.

⚠ **IT IS AN AUDIT ON PURPOSE AND MUST STAY ONE.** B14 rule 44 (PO 2026-09-24,
*"please use our ui, styleguide, spacing specifications. all the time"*) is
RATIFIED and UNENFORCED, and the honest reason is in B14's own status table: no
gate in this repo reads rendered output. A number in a stylesheet is not a
rendered pixel — a value can be off the scale and correct (a hairline border, a
`translate` nudge, an icon's optical centring), and a value can be on the scale
and wrong for the element it is on. **A tool that cannot tell those apart must
not be allowed to fail a merge**, or the first false positive gets it switched
off and the rule goes with it (G34's own docstring makes the same argument about
a gate nobody runs).

⚠ **AND A COUNT WITHOUT ITS SCOPE BESIDE IT IS WORTHLESS — hard-won law 7's
fifth variant.** `G32` reported `0 unresolved` truthfully over 21 live refusals
it could not see. So this script prints **what it skipped beside what it
checked**, every run, as the last two lines of `--report`. A reader who cannot
see the denominator cannot tell an empty result from a blind one.

WHAT IS ON THE SCALE
--------------------
Read from `07-frontend/src/styles/tokens.css` at run time, never hardcoded — a
copy of the scale in this file is a second source of truth and would go stale
the first time a step moved.

  spacing   `--space-1..8`       4 · 8 · 12 · 16 · 20 · 24 · 32
  type      `--text-*`           11 · 12 · 13 · 14 · 15 · 16 · 20 · 22 · 25 · 26 · 32 · 40 · 56
  radius    `--radius-*`         0

`0` is always on the scale: it is the absence of a length, not a choice of one.

WHAT IT LOOKS AT
----------------
Literal `<n>px` values in `padding`, `margin`, `gap`, `row-gap`, `column-gap`
and `font-size` declarations, in the app's own stylesheets under
`07-frontend/src`. Those six properties are the ones B14 rule 44 names —
*spacing, sizes, the type scale* — and they are the ones the Finance blueprint
measured its 65 over.

WHAT IT DELIBERATELY DOES NOT LOOK AT, each with its reason
-----------------------------------------------------------
  * `tokens.css` and `tailwind.css` — the one place a length is ALLOWED to be a
    literal, because they are the declaration site. G34 excludes them for the
    same reason and says so.
  * `border`, `outline`, `box-shadow`, `top/left/right/bottom`, `transform`,
    `width`, `height`, `min-*`, `max-*`, `flex-basis` — a hairline is 1px
    because a hairline is 1px, and a frame width is BR-SHL-001's business rule,
    not a spacing choice. Counting them would bury the signal.
  * `.tsx` / `.ts` — Tailwind utilities are checked by G34 (arbitrary type
    values) and G31 (declared classes). This script reads STYLESHEETS.
  * anything inside a `@media`, `@supports` or `@keyframes` block is still read;
    a breakpoint does not license an off-scale gap.

USAGE
-----
    python3 10-scripts/tokens_check.py                     # default root
    python3 10-scripts/tokens_check.py --report            # + the two scope lines
    python3 10-scripts/tokens_check.py --root 07-frontend/src
    python3 10-scripts/tokens_check.py --file-summary      # per-file counts only

Exit status is ALWAYS 0. See the audit-not-a-gate note above.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO / "07-frontend" / "src"
TOKENS = REPO / "07-frontend" / "src" / "styles" / "tokens.css"

#: The declaration-site stylesheets. A literal length is correct in these.
EXCLUDED_FILES = {"tokens.css", "tailwind.css"}

#: The properties B14 rule 44 names: spacing, sizes, the type scale.
PROPERTIES = ("padding", "margin", "gap", "row-gap", "column-gap", "font-size")

_DECL = re.compile(
    r"(?P<prop>" + "|".join(re.escape(p) for p in PROPERTIES) + r")"
    r"(?P<side>-top|-right|-bottom|-left|-inline|-block|-inline-start|"
    r"-inline-end|-block-start|-block-end)?"
    r"\s*:\s*(?P<value>[^;{}]+)",
    re.IGNORECASE,
)
_PX = re.compile(r"(?<![\w.-])(-?\d+(?:\.\d+)?)px\b")
_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_TOKEN_DECL = re.compile(r"^\s*--(?P<name>[\w-]+)\s*:\s*(?P<value>[^;]+);", re.MULTILINE)


def read_scale(tokens_css: Path) -> tuple[set[float], dict[str, set[float]]]:
    """The ruled steps, READ from tokens.css rather than copied into this file.

    Returns (every allowed px value, {family: its own steps}) so a reader can be
    told which family a value missed as well as that it missed one.
    """
    text = tokens_css.read_text(encoding="utf-8")
    families: dict[str, set[float]] = {"space": set(), "text": set(), "radius": set()}
    for m in _TOKEN_DECL.finditer(text):
        name, value = m.group("name"), m.group("value").strip()
        px = _PX.fullmatch(value)
        if not px:
            continue
        step = float(px.group(1))
        for family in families:
            if name == family or name.startswith(family + "-"):
                families[family].add(step)
                break
    allowed = {0.0}
    for steps in families.values():
        allowed |= steps
    return allowed, families


def stylesheets(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*.css")
        if p.name not in EXCLUDED_FILES and "node_modules" not in p.parts
    )


def allowed_for(prop: str, families: dict[str, set[float]]) -> tuple[set[float], str]:
    """The steps THIS property may use, and the family's name for the message.

    ⚠ **THE FAMILIES ARE NOT POOLED, AND THE FIRST DRAFT OF THIS FILE POOLED
    THEM.** Unioning every `--*` step into one allowed set lets a TYPE step
    license a SPACING value: `--text-md` is 14px, so `gap: 14px` — one of the
    three occurrences the Finance blueprint had already verified by hand — came
    back CLEAN. The tool reported 63 where the blueprint had counted 65, and the
    two it had lost were exactly the ones a reader could check.

    That is hard-won law 7's *what would make this check pass wrongly*, found by
    asking the question rather than by the check failing — because a check of
    this shape does not fail, it quietly under-reports. A spacing property is
    measured against the spacing scale and a `font-size` against the type scale,
    and neither borrows from the other.
    """
    if prop.startswith("font-size"):
        return families["text"] | {0.0}, "the type scale"
    return families["space"] | {0.0}, "the spacing scale"


def audit(
    root: Path, families: dict[str, set[float]]
) -> tuple[list[tuple[Path, int, str, str, float, str]], int]:
    """Every off-scale occurrence, and how many declarations were read in total."""
    findings: list[tuple[Path, int, str, str, float, str]] = []
    declarations = 0
    for path in stylesheets(root):
        raw = path.read_text(encoding="utf-8")
        # Blank comments rather than dropping them, so line numbers survive.
        text = _COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), raw)
        starts = [0]
        for line in text.splitlines(keepends=True):
            starts.append(starts[-1] + len(line))
        for m in _DECL.finditer(text):
            declarations += 1
            value = m.group("value")
            prop = m.group("prop") + (m.group("side") or "")
            line = next(i for i, s in enumerate(starts) if s > m.start()) - 1
            allowed, scale_name = allowed_for(prop, families)
            for px in _PX.finditer(value):
                step = float(px.group(1))
                if step not in allowed:
                    findings.append((path, line + 1, prop, value.strip(), step, scale_name))
    return findings, declarations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--report", action="store_true", help="print the scope lines")
    ap.add_argument("--file-summary", action="store_true", help="per-file counts only")
    args = ap.parse_args(argv)

    root = Path(args.root)
    if not root.is_absolute():
        root = (Path.cwd() / root).resolve()
    _allowed, families = read_scale(TOKENS)
    findings, declarations = audit(root, families)

    by_file: dict[Path, int] = {}
    for path, *_ in findings:
        by_file[path] = by_file.get(path, 0) + 1

    if args.file_summary:
        for path, count in sorted(by_file.items(), key=lambda kv: (-kv[1], str(kv[0]))):
            print(f"{count:4d}  {path.relative_to(REPO)}")
    else:
        for path, line, prop, value, step, scale_name in findings:
            print(
                f"{path.relative_to(REPO)}:{line}  {prop}: {value}"
                f"   ← {step:g}px is not on {scale_name}"
            )

    print()
    print(f"OFF-SCALE OCCURRENCES: {len(findings)} in {len(by_file)} files")
    if args.report:
        scale = " · ".join(
            f"--{k}: {', '.join(f'{v:g}' for v in sorted(steps))}"
            for k, steps in families.items()
            if steps
        )
        print(f"SCALE READ FROM {TOKENS.relative_to(REPO)}: {scale} (and 0)")
        print(
            f"CHECKED: {declarations} {'/'.join(PROPERTIES)} declarations "
            f"across {len(stylesheets(root))} stylesheets under {root.relative_to(REPO)}"
        )
        print(
            "SKIPPED, and each for a reason in this file's docstring: "
            f"{'/'.join(sorted(EXCLUDED_FILES))} (the declaration site) · "
            "border/outline/shadow/position/transform/width/height lengths "
            "(a hairline and a frame width are not spacing choices) · "
            "every .ts and .tsx file (G34 and G31 own those)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
