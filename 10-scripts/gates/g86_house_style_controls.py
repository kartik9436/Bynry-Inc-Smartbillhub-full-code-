#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  B14 rule 36, ratified by the PO on 2026-09-04: *"you ahve to folow
#          the stylegudie that we have approved from R10; style guide na
#          dtailwind component remain same … also toolkit is not align"*. The
#          rule's own status cell says two of its four breaches are
#          MECHANICALLY CATCHABLE and that a gate is owed for them. This is
#          that gate.
# Defect:  DEF-INT-3721 (a wireframe annotation style shipped as product) ·
#          DEF-3722 (the kit bypassed — four screens, four hand-rolled chips)
# Rules:   r10 UI-RULES rule 4 · 5 · 6 (button grammar, two sizes, the danger
#          tier) · rule 12 (the toolbar owns filter chips) · B14 rule 21
#          (new UI is Tailwind and adds no stylesheet class) · rule 36
#          (the packs give layout, r10 gives the style, the kit is how you
#          comply) · CLAUDE.md hard-won law 6 (no gate here reads rendered
#          output, so a gate must read what it CAN read, and say which half
#          it cannot) · law 7 (proved RED first — see `selftest()`)
# Tests:   selftest() below, which rebuilds BOTH real breaches from the tip
#          and asserts the scanner names them
# Impacts: 07-frontend/src/features/**, 07-frontend/src/portal/** ·
#          10-scripts/gates/g86_handrolled_buttons_baseline.txt
# ───────────────────────────────────────────────────────
"""G86 — a screen may not draw its own controls, and may not ship a wireframe.

WHY THIS GATE EXISTS
--------------------
On 2026-09-04 the Product Owner reviewed eight screens shipped that day and
found every one of them off the house style. Two of the six breaches are
findable by reading source text, and both had passed every check in the repo:

  1. **A WIREFRAME ANNOTATION STYLE SHIPPED AS PRODUCT.** The integrations
     connect modal drew four production panels as `border-dashed
     border-info-700` boxes with `font-mono text-xs uppercase tracking-wider`
     legends — *WHAT THIS CONNECTION NEEDS* in typewriter capitals over a blue
     dashed rectangle. A customer-facing form that looks like a sketch of
     itself. It was worse than unnoticed: the wave's own browser walkthrough
     ASSERTED it, in the words *"the field slot's border is dashed in a real
     engine"*, so the one check that did look at pixels was pointed at the
     defect and reported it green.

  2. **THE KIT IGNORED.** Category chips and segmented controls were
     hand-rolled from raw `<button>` elements while `Button`, `buttonKit` and
     `FilterBar` all existed. Four screens acquired four different chips this
     way, and this gate's own baseline still holds the same twenty-token chip
     string written out FOUR TIMES in four files — which is the defect
     demonstrating itself.

`tsc`, eslint and every `toContain` assertion pass on both, because both are
made of classes that compile. `G31` and `routeBUtilities.test.ts` ask whether a
class is REAL; neither can ask whether it should have been a component.

WHAT IT READS, AND THE TWO CLAUSES
----------------------------------
Every `.tsx` under `07-frontend/src/features/` and `07-frontend/src/portal/`
that is not a test. Those two trees are the SCREENS; `src/components/` is
deliberately outside, because the kit is where a control is allowed to be
drawn by hand — that is what a kit is.

**(a) THE ANNOTATION STYLE — a dashed border AND a monospace uppercase legend,
within 400 characters of each other.** Baseline ZERO, and it must stay zero.

⚠ **IT IS THE COMBINATION, AND THAT IS NOT FUSSINESS — A DASHED BORDER ALONE
IS HOUSE STYLE.** r10 declares `.empty { border: 2px dashed var(--color-divider) }`
for every list's empty state, and the Company screen's logo dropzone is dashed
because that is what a drop target looks like everywhere. Banning `border-dashed`
outright would have flagged both, been wrong twice on the first run, and been
switched off — DEF-323's lesson, which this repo has paid for. What is never
house style is a dashed box LABELLED like a diagram: the pairing is the tell.

**(b) A HAND-ROLLED BUTTON — a `<button>` in a screen file whose own classes
draw a BOX.** A box is: padding that is not zeroed, a border that is not
zeroed, and a background or text colour. All three, together. That is
`<Button>`'s job, and `buttonKit.ts` exists precisely so the answer is written
once.

⚠ **A `<button>` WITH NO CLASSES IS NEVER A FINDING, AND NEITHER IS A
LINK-SHAPED ONE.** `border-0 … p-0 text-accent-700 hover:underline` is
`Surfaces.InlineLink`, a different control with a different tier, and 55
buttons were scanned to establish that the box test separates them cleanly.
A gate with a false positive is worse than no gate, because it gets switched
off.

**(c) A COMPONENT WHOSE NAME THE SHARED KIT ALREADY EXPORTS.** Two components
called `Panel`, in two directories, are two visual decisions wearing one name —
and the second author cannot even see the first, because an import names a
path. This is the drift of clause (b) one level up, and unlike the visual rules
it is readable from two directory listings.

⚠ **IT WOULD HAVE GONE RED THE DAY `portal/components/content.tsx` LANDED.**
That file exports a `Panel` while `components/Panel.tsx` exports one, and a
`Chip` whose own comment says out loud what it is: *"the guest surface's status
chip — the staff kit's tones, its own markup."* The staff kit's `Panel` grew a
`title` prop on 2026-09-04 under this very rule, because *"three screens of
CR-068 wave D had each written their own `<section>` with their own border and
their own small-caps `<h3>`"* — and the portal's own `Panel`, one directory
away, was not part of that pass. The scope of the drift is worth writing down:
`src/portal` is 1,733 lines and imports the shared kit FOUR times.

Only COMPONENT-shaped names count — an initial capital followed by a lower-case
letter. `DEFAULT`, `MONEY`, `RATE` and `WIZARD` are shouty local constants and
the first draft flagged nineteen of them, which is the false-positive rate that
gets a gate switched off.

**THE BASELINE, AND WHY CLAUSES (b) AND (c) HAVE ONE.** Clause (b) found SEVEN
pre-existing hand-rolled boxes in five files no lane was correcting on the day
this landed. Refusing them all immediately would either block five other lanes
or force this one to redraw five screens it had not been asked to look at.
`g86_handrolled_buttons_baseline.txt` names them, the gate refuses anything NOT
on that list, and the file may only SHRINK — the ratchet `G28` already uses
here. A baseline entry is a path plus the class string, never a line number: a
line number moves under an unrelated edit two files away, and a gate that goes
red on somebody else's commit is a gate nobody trusts.

WHAT IT CANNOT SEE, SAID OUT LOUD
---------------------------------
The other four breaches B14 rule 36 records. A wall of checkboxes where r10
rule 9 wants chips; the danger colour on a sign-in; on/off drawn as a word in a
box; and a column so narrow the text wraps one word per line. The last is the
sharpest illustration of law 6 in the whole repository: **every suite here
asserts on text content, and text content is byte-for-byte identical however it
wraps.** Those need a person or a rendered-output check with a wider eye; this
gate does not pretend to cover them, and saying so is the point.
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

import common

FRONTEND = common.FRONTEND_SRC
SCREEN_ROOTS = ("features", "portal")
BASELINE = Path(__file__).with_name("g86_handrolled_buttons_baseline.txt")
NAME_BASELINE = Path(__file__).with_name("g86_kit_name_collisions_baseline.txt")

# `export function Name`, `export const Name`, `export class Name`, and the
# `default` forms. Component-shaped only: an initial capital followed by a
# LOWER-CASE letter, which is what separates `Panel` from `MONEY`.
_EXPORT = re.compile(r"^export (?:default )?(?:function|const|class)\s+([A-Z][a-z][A-Za-z0-9]*)", re.M)

# How far apart a dashed border and a monospace legend may be and still be the
# same panel. 400 characters is about a dozen lines of JSX — a fieldset and its
# legend, or a div and the caption inside it. Measured against the real breach:
# the connect modal's four panels put the two between 60 and 210 characters
# apart, and the widest gap in the tree between an UNRELATED dashed box and an
# unrelated mono legend was over 3,000.
ANNOTATION_SPAN = 400

# `className="…"` or `className={…}`, including a ternary or a template.
_CLASS = re.compile(r'className\s*=\s*(?:"([^"]*)"|\{((?:[^{}]|\{[^{}]*\})*)\})', re.S)
# A `<button …>` opening tag, tolerating one level of braces in its attributes.
_BUTTON = re.compile(r"<button\b((?:[^<>]|\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})*?)>", re.S)
_STRING = re.compile(r'"([^"]*)"|\'([^\']*)\'|`([^`]*)`')

_DASHED = re.compile(r"\bborder-dashed\b")
_MONO_CAPS = re.compile(r"\bfont-mono\b")
_UPPER = re.compile(r"\buppercase\b")

# A box, in three parts. Each is deliberately narrow.
_PAD = re.compile(r"\b(?:p|px|py|pt|pb|pl|pr)-(?!0\b)\[?[\w./]")
_ZERO_BORDER = re.compile(r"\bborder-(?:0|none)\b")
_BORDER = re.compile(
    r"\bborder(?:$|\s)|\bborder-(?:[trbl]-)?(?:\d|\[)"
    r"|\bborder-(?:divider|text|accent|neutral|danger|success|warning|info)"
)
# `text-left` / `text-center` and friends are alignment, not paint.
_PAINT = re.compile(r"\b(?:bg|text)-(?!left\b|right\b|center\b|justify\b|wrap\b|nowrap\b|ellipsis\b)[\w\[]")


def screen_files(root: Path) -> list[Path]:
    """Every screen source file — tests excluded, the kit excluded by path."""
    out: list[Path] = []
    for name in SCREEN_ROOTS:
        base = root / name
        if not base.is_dir():
            continue
        out.extend(p for p in sorted(base.rglob("*.tsx")) if ".test." not in p.name)
        out.extend(p for p in sorted(base.rglob("*.ts")) if ".test." not in p.name)
    return out


def _class_literals(blob: str | None) -> list[str]:
    """Every quoted string inside a `className={…}` expression."""
    if blob is None:
        return []
    return [g for groups in _STRING.findall(blob) for g in groups if g]


def annotation_findings(text: str) -> list[int]:
    """Offsets where a dashed border sits within ANNOTATION_SPAN of a mono legend."""
    dashed: list[int] = []
    legends: list[int] = []
    for m in _CLASS.finditer(text):
        chunk = m.group(1) if m.group(1) is not None else " ".join(_class_literals(m.group(2)))
        if _DASHED.search(chunk):
            dashed.append(m.start())
        if _MONO_CAPS.search(chunk) and _UPPER.search(chunk):
            legends.append(m.start())
    return sorted(d for d in dashed if any(abs(d - g) < ANNOTATION_SPAN for g in legends))


def handrolled_buttons(text: str) -> list[str]:
    """The class string of every `<button>` in this file that draws a box."""
    found: list[str] = []
    for m in _BUTTON.finditer(text):
        cm = _CLASS.search(m.group(1))
        if cm is None:
            continue
        parts = [cm.group(1)] if cm.group(1) is not None else _class_literals(cm.group(2))
        joined = " ".join(" ".join(p.split()) for p in parts if p).strip()
        if not joined:
            continue
        if _ZERO_BORDER.search(joined):
            continue  # link-shaped: Surfaces.InlineLink's job, not Button's
        if _PAD.search(joined) and _BORDER.search(joined) and _PAINT.search(joined):
            found.append(joined)
    return found


def _read_baseline(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def kit_exports(root: Path) -> dict[str, str]:
    """Every component the shared kit exports, and the file it lives in."""
    out: dict[str, str] = {}
    kit = root / "components"
    if not kit.is_dir():
        return out
    for path in sorted(kit.glob("*.tsx")):
        if ".test." in path.name:
            continue
        for name in _EXPORT.findall(common.read_text(path)):
            out.setdefault(name, path.relative_to(root).as_posix())
    return out


def name_collisions(root: Path) -> list[str]:
    """`<path> :: <Name>` for every component outside the kit that takes a
    name the kit already uses. The kit's own sub-folders are excluded: a
    `components/workflow/` part IS the kit."""
    kit = kit_exports(root)
    found: list[str] = []
    for path in sorted(root.rglob("*.tsx")):
        rel = path.relative_to(root).as_posix()
        if ".test." in path.name or rel.startswith("components/"):
            continue
        for name in _EXPORT.findall(common.read_text(path)):
            if name in kit:
                found.append(f"{rel} :: {name}")
    return found


def baseline_keys() -> set[str]:
    return _read_baseline(BASELINE)


def key_for(path: Path, classes: str, root: Path) -> str:
    """A baseline key: the file, and the class string, truncated so an added
    hover state does not silently un-baseline a line — but not so short that
    two different buttons in one file collapse into one entry."""
    return f"{path.relative_to(root).as_posix()} :: {classes[:100]}"


def scan(root: Path) -> tuple[list[str], list[str], int]:
    """(annotation findings, un-baselined button findings, files scanned)."""
    known = baseline_keys()
    annotations: list[str] = []
    buttons: list[str] = []
    files = screen_files(root)
    for path in files:
        text = common.read_text(path)
        rel = path.relative_to(root).as_posix()
        for offset in annotation_findings(text):
            line = text[:offset].count("\n") + 1
            annotations.append(f"{rel}:{line} draws a dashed panel with a monospace uppercase legend")
        for classes in handrolled_buttons(text):
            if key_for(path, classes, root) not in known:
                buttons.append(f"{rel} hand-rolls a button: {classes[:70]}")
    return annotations, buttons, len(files)


def selftest() -> bool:
    """⚠ REBUILT FROM THE TWO REAL BREACHES, NOT FROM AN INVENTED ONE.

    Both blocks below are transcribed from `ConnectModal.tsx` and
    `IntegrationsTab.tsx` as they stood at commit `fcbc7017`, the tip on the
    morning the PO reported them. A gate proved on a sabotage its own author
    designed proves only that the author can write a matching string; proved on
    the thing it was written for, it proves the thing.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        screens = root / "features" / "integrations"
        screens.mkdir(parents=True)
        portal = root / "portal" / "guest"
        portal.mkdir(parents=True)

        clean = screens / "Clean.tsx"
        clean.write_text(
            '<Button variant="primary" size="sm">Connect</Button>\n'
            '<div className="border border-divider bg-surface p-3">ok</div>\n',
            encoding="utf-8",
        )
        if scan(root) != ([], [], 1):
            return False

        # (a) the real one — ConnectModal.tsx's field slot at fcbc7017
        slot = screens / "ConnectModal.tsx"
        slot.write_text(
            '<fieldset className="my-3 border border-dashed border-info-700 p-3" data-field-slot="true">\n'
            '  <legend className="px-1 font-mono text-xs uppercase tracking-wider text-info-700">\n'
            '    {t("integrations.modal.fieldSlot")}\n'
            "  </legend>\n"
            "</fieldset>\n",
            encoding="utf-8",
        )
        annotations, _, _ = scan(root)
        if len(annotations) != 1 or "ConnectModal.tsx" not in annotations[0]:
            return False

        # a dashed EMPTY STATE with no legend is house style and must pass —
        # r10 declares `.empty { border: 2px dashed … }`
        slot.write_text(
            '<div className="border border-dashed border-divider p-10 text-center">nothing yet</div>\n',
            encoding="utf-8",
        )
        # ...and a mono uppercase caption with no dashed box is also fine
        (portal / "Caption.tsx").write_text(
            '<p className="font-mono text-xs uppercase tracking-wider">REF 8891</p>\n', encoding="utf-8"
        )
        annotations, buttons, _ = scan(root)
        if annotations or buttons:
            return False

        # (b) the real one — IntegrationsTab.tsx's coming-soon Connect at fcbc7017
        tab = screens / "IntegrationsTab.tsx"
        tab.write_text(
            "<button\n"
            '  type="button"\n'
            '  className="w-full cursor-not-allowed border border-dashed border-neutral-300 '
            'px-3 py-2 text-sm text-neutral-400"\n'
            ">\n"
            "  {t}\n"
            "</button>\n",
            encoding="utf-8",
        )
        _, buttons, _ = scan(root)
        if len(buttons) != 1 or "IntegrationsTab.tsx" not in buttons[0]:
            return False

        # ...and its category chip, which carried no dashed border at all
        tab.write_text(
            "<button\n"
            '  className="rounded-full border border-neutral-300 px-3 py-1 text-xs '
            'font-medium uppercase tracking-wide text-neutral-600"\n'
            ">chip</button>\n",
            encoding="utf-8",
        )
        _, buttons, _ = scan(root)
        if len(buttons) != 1:
            return False

        # a link-shaped button is NOT a finding — it is Surfaces.InlineLink's
        # shape, and flagging it is the false positive that switches a gate off
        tab.write_text(
            '<button className="cursor-pointer border-0 bg-transparent p-0 text-left '
            'text-accent-700 hover:underline">open</button>\n',
            encoding="utf-8",
        )
        # nor is a button with no classes at all
        (portal / "Bare.tsx").write_text("<button onClick={go}>next</button>\n", encoding="utf-8")
        _, buttons, _ = scan(root)
        if buttons:
            return False

        # (c) the real one — `portal/components/content.tsx` exports a `Panel`
        # while `components/Panel.tsx` exports one, and a `Chip` whose own
        # comment calls it *"the staff kit's tones, its own markup"*.
        kit = root / "components"
        kit.mkdir()
        (kit / "Panel.tsx").write_text("export function Panel() { return null }\n", encoding="utf-8")
        (portal / "content.tsx").write_text(
            "export function Panel() { return null }\n"
            "export const MONEY = 2;\n"  # a shouty constant is NOT a component
            "export function TipBar() { return null }\n",
            encoding="utf-8",
        )
        rows = name_collisions(root)
        if rows != ["portal/guest/content.tsx :: Panel"]:
            return False
        # the kit's own files are never a collision with themselves
        (kit / "Chip.tsx").write_text("export function Chip() { return null }\n", encoding="utf-8")
        if name_collisions(root) != ["portal/guest/content.tsx :: Panel"]:
            return False
    return True


def run() -> tuple[str, str]:
    if not (FRONTEND / "features").is_dir():
        return "SKIP", "07-frontend/src/features is not present"
    if not selftest():
        return "FAIL", (
            "the gate's own self-test does not hold — it cannot tell a wireframe panel from an "
            "empty state, or a hand-rolled button from an inline link, so its verdict is "
            "worthless (DEF-182)"
        )
    annotations, buttons, files = scan(FRONTEND)
    known = baseline_keys()
    known_names = _read_baseline(NAME_BASELINE)
    live_names = name_collisions(FRONTEND)
    names = [
        f"{row.split(' :: ')[0]} exports `{row.split(' :: ')[1]}`, a name the kit already uses"
        for row in live_names
        if row not in known_names
    ]
    if annotations or buttons or names:
        problems = annotations + buttons + names
        return "FAIL", " | ".join(problems[:6]) + (
            f" (+{len(problems) - 6} more)" if len(problems) > 6 else ""
        )
    # The ratchet: a baseline entry that no longer matches anything has been
    # FIXED, and the line must go with the fix (the same instruction G28 gives).
    live = set()
    for path in screen_files(FRONTEND):
        for classes in handrolled_buttons(common.read_text(path)):
            live.add(key_for(path, classes, FRONTEND))
    stale = sorted((known - live) | (known_names - set(live_names)))
    if stale:
        return "FAIL", (
            f"{len(stale)} baseline line(s) match nothing any more — delete them in the commit "
            f"that fixed them, which is how the ratchet comes down: {stale[0]}"
        )
    return "PASS", (
        f"{files} screen file(s) under features/ and portal/ draw no wireframe annotation "
        f"(a dashed panel with a monospace uppercase legend: 0, and it must stay 0), "
        f"hand-roll no button outside the {len(known)} baselined line(s), and add no component "
        f"whose name the kit already exports outside the {len(known_names)} baselined; "
        "self-test: both real breaches of 2026-09-04 are named, and an empty state, a mono "
        "caption, an inline link, a bare button and a shouty constant are not"
    )


def main() -> int:
    status, detail = run()
    print(f"{status}: {detail}")
    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
