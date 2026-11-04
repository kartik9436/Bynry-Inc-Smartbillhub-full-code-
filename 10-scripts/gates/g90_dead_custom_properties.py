#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CWP-3736 — the customer portal rendered with none of the
#          utility's own colour. The hex was fetched, threaded through three
#          components and written onto a DOM element as `--brand` / `--accent`,
#          and `--accent` was read by NOTHING anywhere in the product.
# Rules:   CLAUDE.md hard-won law 2 (built is not wired — a prop nothing passes
#          is dead UI; a PROPERTY nothing reads is the same failure one layer
#          down) · law 1 (`GuestFrame`'s docstring described a `var(--brand)`
#          fallback for a `var(--brand)` that did not exist) · law 6 (no gate
#          here reads rendered output, so a gate must read what it CAN read)
#          · law 7 (proved RED first — see `selftest()`)
# Tests:   selftest() below, which rebuilds the real breach from the tip and
#          asserts the scanner names it
# Impacts: 07-frontend/src/**
# ───────────────────────────────────────────────────────
"""A CSS custom property a component SETS and no stylesheet READS is dead wiring.

WHY THIS GATE EXISTS
--------------------
On 2026-09-04 the Product Owner opened the live customer portal and said *"the
Style Guide , coloars are not matching."* The page was drawn in the product's
own red rather than the utility's colour, and part of the reason was a variable
that went nowhere:

    // src/portal/shell/GuestFrame.tsx, as it shipped
    if (tenant.brand_primary_hex) style["--brand"]  = tenant.brand_primary_hex;
    if (tenant.brand_accent_hex)  style["--accent"] = tenant.brand_accent_hex;

`--accent` is read by nothing. Not by a stylesheet, not by a Tailwind arbitrary
value, not by anything. The tenant's second colour was fetched over the wire,
carried through three components, written onto a DOM element — and landed
nowhere at all.

**EVERY CHECK IN THIS REPOSITORY WAS GREEN ON IT, AND NONE OF THEM COULD HAVE
BEEN OTHERWISE.** The fixtures set the hex, and the tests assert that the style
attribute is PRESENT — which it is. `tsc` is happy: a `Record<string, string>`
takes any key. `eslint` is happy. `G31` and `routeBUtilities.test.ts` ask
whether a CLASS is real and know nothing about custom properties. And no gate
here reads rendered output (law 6), so nothing asked the only question that
mattered: *does anything consume this?*

It is hard-won law 2 exactly — built, styled, tested, wired to nothing — and
law 2's own example is a prop nothing passes. This is the same failure one
layer down, in CSS.

WHAT IT READS
-------------
**The SET side** — every `.ts`/`.tsx` under `07-frontend/src` that is not a
test, scanned for a custom property used as an assignment target or an object
key: `style["--brand"] = x` and `{ "--brand": x }` both count, which is the
whole of how React writes one.

**The READ side** — every `var(--name)` anywhere under `07-frontend/src`:
stylesheets **and** markup.

⚠ **THE MARKUP HALF IS NOT OPTIONAL, AND LEAVING IT OUT IS HOW THE ORIGINAL
DIAGNOSIS WENT WRONG.** `DEF-CWP-3736` was filed with a measurement that said
*"a grep for `var(--brand)` across every stylesheet returns nothing"* — true,
and misleading, because this product moved its styles into the markup under
Route B. Fifteen source sites wrote `text-[var(--brand)]`, Tailwind compiled
each into a real declaration, and thirteen elements on `CWP-005` rendered the
tenant's colour. A gate that looked only in `.css` files would have called a
live property dead and been switched off within a week.

A name in the SET set and not in the READ set is the finding.

WHAT IT CANNOT SEE, SAID OUT LOUD
---------------------------------
**The reverse direction: a property READ and never SET.** That one is not
symmetric and must not be added carelessly — `var(--x, fallback)` is a
legitimate pattern, and a property may be set by a stylesheet this scanner does
not treat as a source of writes. It is the smaller hazard anyway: a missing
property falls back visibly, where a dead one fails silently, which is the
whole reason this direction is the one that shipped a defect.

**Whether the property reaches the element that needs it.** `--color-accent`
set on a frame cascades to its descendants; set on a leaf it would not, and
this gate cannot tell the difference. Only a browser can, which is law 6 again
and why the walkthrough beside this gate measures `getComputedStyle` rather
than trusting either of us.

**A property whose only reader is a Tailwind THEME key.** Tailwind emits
`bg-accent` as `background-color: var(--color-accent)`, so in practice every
theme token is already read through a literal `var()` somewhere in this
product and the simple text rule holds. If that ever stops being true the
honest fix is to teach this scanner the theme, not to widen the READ set until
nothing can fail.
"""
from __future__ import annotations

import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
FRONTEND = REPO_ROOT / "07-frontend" / "src"

# `style["--brand"] = x`  ·  `{ "--brand": x }`  ·  `'--brand':`
SET_RE = re.compile(r"""["'](--[A-Za-z0-9_-]+)["']\s*\]?\s*[:=](?!=)""")
VAR_RE = re.compile(r"""var\(\s*(--[A-Za-z0-9_-]+)""")

CODE_SUFFIXES = (".ts", ".tsx")
STYLE_SUFFIXES = (".css",)


def is_test(path: pathlib.Path) -> bool:
    """A test that NAMES a token is not a component WIRING one.

    `styles/tailwindTheme.test.ts` lists every theme key by name to compare the
    two declarations of the token set — including `--text-display`, which no
    utility happens to write. Reading that as dead wiring is a false positive
    on the first run, and a gate with one of those gets switched off (DEF-323).
    """
    name = path.name
    return ".test." in name or ".dom.test." in name or "__fixtures__" in path.parts


def source_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix in CODE_SUFFIXES + STYLE_SUFFIXES
    )


def scan(root: pathlib.Path) -> tuple[dict[str, list[str]], set[str], int]:
    """Returns (property -> the files that SET it, everything READ, files seen)."""
    sets: dict[str, list[str]] = {}
    reads: set[str] = set()
    files = source_files(root)
    for path in files:
        try:
            text = path.read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in VAR_RE.finditer(text):
            reads.add(match.group(1))
        if path.suffix in CODE_SUFFIXES and not is_test(path):
            for match in SET_RE.finditer(text):
                sets.setdefault(match.group(1), []).append(
                    str(path.relative_to(root)).replace("\\", "/")
                )
    return sets, reads, len(files)


def dead(root: pathlib.Path) -> list[str]:
    sets, reads, _ = scan(root)
    return sorted(
        f"{name} is set in {sorted(set(where))[0]} and read by no `var({name})` anywhere"
        for name, where in sets.items()
        if name not in reads
    )


def selftest() -> bool:
    """Law 7, and law 7's OTHER half: the breach is rebuilt from the real code.

    Both fixtures below are the shipped `GuestFrame` and its fix, written out
    rather than referenced, so this proof does not evaporate the moment the
    file it was written for is corrected.
    """
    import tempfile

    shipped = (
        'export function brandStyle(t: X) {\n'
        '  const style: Record<string, string> = {};\n'
        '  if (t.brand_primary_hex) style["--brand"] = t.brand_primary_hex;\n'
        '  if (t.brand_accent_hex) style["--accent"] = t.brand_accent_hex;\n'
        "  return style;\n}\n"
    )
    # The markup half — this is what makes `--brand` LIVE and `--accent` dead,
    # and a scanner that reads only stylesheets gets this case backwards.
    markup = '<span className="shrink-0 font-bold text-[var(--brand)]">i</span>\n'
    fixed = (
        'export function brandStyle(t: X) {\n'
        '  const style: Record<string, string> = {};\n'
        '  if (t.brand_primary_hex) style["--color-accent"] = t.brand_primary_hex;\n'
        "  return style;\n}\n"
    )
    sheet = ".btn-primary { background: var(--color-accent) }\n"
    # A test file naming a token it does not wire is NOT a finding.
    a_test = 'const KEYS = { "--text-display": "48px" };\n'

    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "shell").mkdir()
        (root / "shell" / "GuestFrame.tsx").write_text(shipped + markup, "utf-8")
        (root / "theme.css").write_text(sheet, "utf-8")
        (root / "tokens.test.ts").write_text(a_test, "utf-8")
        found = dead(root)
        # RED on the real breach, and on the right ONE of the two.
        if not any(line.startswith("--accent ") for line in found):
            return False
        # `--brand` is READ, in the markup. Naming it would be the false
        # positive that gets a gate switched off.
        if any(line.startswith("--brand ") for line in found):
            return False
        # A test file that names a token is not a component wiring one.
        if any(line.startswith("--text-display ") for line in found):
            return False

        (root / "shell" / "GuestFrame.tsx").write_text(fixed, "utf-8")
        (root / "markup.tsx").write_text(markup.replace("--brand", "--color-accent"), "utf-8")
        if dead(root):
            return False
    return True


def run() -> tuple[str, str]:
    if not FRONTEND.is_dir():
        return "SKIP", "07-frontend/src is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a property read only in "
            "the MARKUP from one read nowhere, so its verdict is worthless (DEF-182)"
        )
    findings = dead(FRONTEND)
    if findings:
        return "FAIL", (
            f"{len(findings)} custom propert(y/ies) set by a component and consumed by nothing "
            "— the colour is fetched, threaded and written, and lands nowhere (hard-won law 2, "
            f"DEF-CWP-3736): {' | '.join(findings[:4])}"
            + (f" (+{len(findings) - 4} more)" if len(findings) > 4 else "")
        )
    sets, reads, files = scan(FRONTEND)
    return "PASS", (
        f"{files} frontend source file(s): every one of the {len(sets)} custom propert(y/ies) a "
        f"component writes is consumed by a `var()` somewhere among the {len(reads)} read, "
        "stylesheets AND markup — self-test: the shipped `--accent` is named, the `--brand` that "
        "was read only from a Tailwind arbitrary value is not, and a token named in a test is not"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
