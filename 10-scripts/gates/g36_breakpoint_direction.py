#!/usr/bin/env python3
"""G36 — every responsive rule is DESKTOP-FIRST, and every width is a ruled step.

WHY THIS GATE EXISTS
--------------------
OQ-274 ratified desktop-first: every `@media` width query in this product is
`max-width`, the `--breakpoint-*` namespace is CLEARED so Tailwind's own
MIN-width defaults cannot form a second scale, and authoring reads
`max-lg:grid-cols-1` — never `lg:grid-cols-2`.

**Nothing had ever read a media query's DIRECTION.** Thirteen `max-width` rules
and two `min-width` ones coexisted for months, because each is individually
valid CSS: no lint rule, no test and no gate looks at the SHAPE of a breakpoint.
The two mobile-first survivors in `payments.css` were found by grepping for a
report, not by a check (DEF-345).

⚠ AND THE MISMATCH IS SILENT BY CONSTRUCTION. Tailwind's defaults are
min-width. With both directions live, `lg:` and `max-lg:` both compile and mean
different viewports — so a mistake reads as a working utility. That is why the
namespace is cleared and why this gate exists to keep it that way.

WHAT IT CHECKS
--------------
1. **No `min-width` media query** anywhere in `07-frontend/src`. Ratcheted at 0:
   the two that existed are converted, so any new one is a regression.
2. **Every width is a ruled step** — 720, 900, 1024, 1100, 1440 — or the
   half-open complement of one (`899.98px`, which is how a `min-width: 900`
   inversion is spelled exactly; `max-width: 900px` would apply AT 900 as well
   and both rules would live at that one width).
3. The declared `--breakpoint-*` keys still MATCH those widths, so the theme and
   the stylesheets cannot drift apart.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not judge `min-width` on a CSS PROPERTY (`min-width: 220px` on an
element) — that is a completely different thing that happens to share a name,
and a gate that confused the two would be switched off within a day.

⚠ 760px IS A KNOWN EXCEPTION, not an oversight: one rule in `global.css`
(`.chooser`/`.kv`). Absorbing it into `sm` moves pixels between 720 and 760, so
it is filed (DEF-345) rather than rounded, and allowlisted here BY NAME so that
the exception is a decision someone wrote down rather than a hole.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent / "07-frontend" / "src"
THEME = SRC / "styles" / "tailwind.css"

RULED = {720, 900, 1024, 1100, 1440}
# the exact complement of a ruled step, for an inverted mobile-first rule
COMPLEMENTS = {w - 0.02 for w in RULED}
# one rule, one width, filed as DEF-345 — an exception with a name
ALLOWED_ORPHANS = {760.0: "global.css .chooser/.kv — DEF-345, absorbing it moves pixels"}

MEDIA_WIDTH = re.compile(r"@media[^{]*?\((max|min)-width:\s*([0-9.]+)px\)")
THEME_KEY = re.compile(r"^\s*--breakpoint-([a-z0-9]+):\s*([0-9]+)px", re.MULTILINE)


def scan() -> tuple[list[tuple[str, float, str]], list[tuple[str, float, str]]]:
    mins, maxes = [], []
    for path in sorted(SRC.rglob("*.css")):
        for direction, width in MEDIA_WIDTH.findall(path.read_text("utf-8", errors="replace")):
            row = (direction, float(width), str(path.relative_to(SRC)))
            (mins if direction == "min" else maxes).append(row)
    return mins, maxes


def run() -> tuple[str, str]:
    mins, maxes = scan()

    if mins:
        detail = "; ".join(f"{f} has min-width: {int(w)}px" for _, w, f in mins)
        return "FAIL", (
            f"{len(mins)} MOBILE-FIRST media quer(ies) — OQ-274 ratifies desktop-first, so "
            f"every width query is max-width: {detail}. Invert it: put the wide value in the "
            f"base rule and use max-width at the step BELOW (e.g. 899.98px, not 900px, or both "
            f"rules apply at exactly 900)."
        )

    orphans = [
        (f, w) for _, w, f in maxes
        if w not in RULED and w not in COMPLEMENTS and w not in ALLOWED_ORPHANS
    ]
    if orphans:
        return "FAIL", (
            f"width(s) off the ruled scale {sorted(RULED)}: "
            + "; ".join(f"{f} at {w}px" for f, w in orphans)
            + ". Use a ruled step, or add it to ALLOWED_ORPHANS with a reason and a defect."
        )

    declared = {int(px) for _, px in THEME_KEY.findall(THEME.read_text("utf-8"))}
    if declared != RULED:
        return "FAIL", (
            f"the theme declares {sorted(declared)} and this gate rules {sorted(RULED)} — "
            f"one was changed without the other, so a `max-lg:` utility and a `@media` rule "
            f"now mean different widths"
        )

    print(
        f"note: {len(maxes)} max-width rule(s), 0 min-width; widths "
        f"{sorted({int(w) for _, w, _ in maxes})}; {len(ALLOWED_ORPHANS)} named exception(s)"
    )
    return "PASS", "every responsive rule is desktop-first and on the ruled scale"


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
