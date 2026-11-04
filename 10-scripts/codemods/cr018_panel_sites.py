#!/usr/bin/env python3
"""CR-018 Phase 4b-2 — rewrite `<div className="met-panel">` to `<Panel>`.

WHY A SECOND CODEMOD RATHER THAN A GENERAL ONE
----------------------------------------------
`cr018_button_sites.py` rewrites an ELEMENT into a component with props derived
from its class string. This one does something simpler and therefore safer: the
element stays a `<div>` inside `Panel`, only the wrapper changes, and the class
string is either gone or carried through verbatim as `className`. Generalising
the two would mean one function with a mode flag, which is how a codemod
acquires the bug that only fires in the mode nobody re-tested.

It reuses the other file's SCANNER, though, because that is where the hard-won
corrections live: comments blanked to same-length spaces before scanning (an
apostrophe in a comment ate three files), brace-aware attribute parsing, and a
self-closing test at [end-2] rather than [end-1].

WHAT IT REWRITES
----------------
    <div className="met-panel">              →  <Panel>
    <div className="met-panel pay-today">    →  <Panel className="pay-today">
    <div className="met-panel" id="x">       →  <Panel id="x">

and the matching `</div>` becomes `</Panel>`.

WHAT IT REFUSES
---------------
Anything where `met-panel` is not a literal in a double-quoted `className` —
there are none today (measured: 149 sites, 0 dynamic), and a codemod that
guesses at a template literal is how a container silently loses its border.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cr018_button_sites import _matching_close, _tag_end  # the corrected scanner

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "07-frontend" / "src"

# ⚠ BOTH ELEMENTS. 47 of the 149 sites are `<section>`, and a codemod that
# saw only `<div>` would have silently left them behind — or, worse, a
# component that hardcoded `<div>` would have changed the element under
# them. The tag is carried through as `as="section"`.
OPEN_TAG = re.compile(r"<(div|section)\b")


def convert(text: str) -> tuple[str, list[str], list[str]]:
    changes: list[str] = []
    refusals: list[str] = []
    out = text
    pos = 0
    while True:
        m = OPEN_TAG.search(out, pos)
        if m is None:
            break
        end = _tag_end(out, m.start())
        if end is None:
            pos = m.end()
            continue
        raw = out[m.end() : end]
        self_closing = raw.rstrip().endswith("/>")
        attrs = raw.rstrip()[:-2] if self_closing else raw.rstrip()[:-1]

        cls = re.search(r'className="([^"]*)"', attrs)
        if cls is None or "met-panel" not in cls.group(1).split():
            pos = m.end()
            continue

        extra = [c for c in cls.group(1).split() if c != "met-panel"]
        tag = m.group(1)
        close_at = None if self_closing else _matching_close(out, m.start(), tag)
        if close_at is None and not self_closing:
            refusals.append(f"line {out[: m.start()].count(chr(10)) + 1}: no matching </{tag}>")
            pos = m.end()
            continue

        new_attrs = attrs.replace(cls.group(0), "")
        if tag == "section":
            new_attrs = ' as="section"' + new_attrs
        if extra:
            new_attrs = f' className="{" ".join(extra)}"' + new_attrs
        new_attrs = re.sub(r"\n[ \t]*(?=\n)", "", new_attrs).rstrip()
        # Removing an attribute leaves the space that separated it. `<Panel
        # role="alert">` reads fine; `<Panel  role="alert">` is the codemod
        # signing its work in whitespace.
        new_attrs = re.sub(r"[ \t]{2,}", " ", new_attrs)

        head = "<Panel" + new_attrs
        indent = " " * (m.start() - out.rfind("\n", 0, m.start()) - 1)
        if self_closing:
            head += " />"
        else:
            head += (("\n" + indent) if "\n" in attrs else "") + ">"

        if close_at is not None:
            out = out[: m.start()] + head + out[end:close_at] + "</Panel>" + out[close_at + len(f"</{tag}>") :]
        else:
            out = out[: m.start()] + head + out[end:]
        changes.append(f'<{tag} "{cls.group(1)}"> -> <Panel{" as=section" if tag == "section" else ""}>')
        pos = m.start() + len(head)
    return out, changes, refusals


def ensure_import(text: str) -> str:
    if re.search(r'^import \{[^}]*\bPanel\b[^}]*\} from "@/components/Panel";', text, re.M):
        return text
    line = 'import { Panel } from "@/components/Panel";'
    # After the LAST `@/components/` import, so the group stays sorted and
    # eslint's import/order does not fail a mechanical change.
    anchors = list(re.finditer(r'^import .*from "@/components/[^"]*";$', text, re.M))
    if anchors:
        after = max(anchors, key=lambda m: m.group(0))
        return text.replace(after.group(0), after.group(0) + "\n" + line, 1)
    last = list(re.finditer(r"^import .*;$", text, re.M))[-1]
    return text[: last.end()] + "\n" + line + text[last.end() :]


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    dry = "--dry-run" in argv
    total = 0
    for name in [a for a in argv if not a.startswith("--")]:
        path = SRC / name
        text = path.read_text("utf-8")
        new, changes, refusals = convert(text)
        if changes:
            new = ensure_import(new)
        total += len(changes)
        if changes or refusals:
            print(f"{name}: {len(changes)} converted, {len(refusals)} refused")
        for r in refusals:
            print(f"   ⚠ {r}")
        if not dry and changes:
            path.write_text(new, encoding="utf-8")
    print(f"total: {total} panel(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
