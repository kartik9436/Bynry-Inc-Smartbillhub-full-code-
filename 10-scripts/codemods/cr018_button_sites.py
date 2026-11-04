#!/usr/bin/env python3
"""CR-018 Phase 4a — rewrite `className="btn …"` call sites to the Button kit.

WHY A CODEMOD AND NOT 161 HAND EDITS
------------------------------------
Phase 3 built `components/buttonKit.ts` and proved it equal to the legacy class
names property by property, in a browser, in every state. Then it migrated ONE
file. **Seventy files still write `className="btn btn-primary"`**, which is why
the 28 button CSS rules are still declared and why the bundle has GROWN rather
than shrunk: the shrink only arrives when the last call site is gone.

The edit is mechanical and the shapes are few — 137 of the 161 sites are exactly
`btn btn-secondary`, `btn btn-primary` or `btn btn-ghost` — so the risk is not
in any one edit, it is in doing the same edit 161 times by hand.

WHAT IT REWRITES, AND WHAT IT REFUSES
-------------------------------------
`<button className="btn btn-primary" …>` → `<Button variant="primary" …>`
`<Link className="btn btn-ghost" …>`     → `<ButtonLink variant="ghost" …>`

⚠ IT REFUSES ANYTHING IT CANNOT READ WITH CERTAINTY and prints why. A dynamic
class (`className={cond ? "btn btn-primary" : "btn btn-ghost"}`) is left alone:
the kit takes a `variant` UNION, so the ternary has to move inside the prop, and
a codemod guessing at that is how a plausible button of the wrong colour ships
with every gate green (buttonKit.ts's header documents that exact failure).

⚠ `type` IS NOT DROPPED BLINDLY. `Button` defaults to `type="button"`, so an
explicit `type="button"` is redundant and removed — but `type="submit"` changes
what the element DOES inside a form and is carried through untouched.

⚠ EXTRA CLASSES SURVIVE as `className`. `btn btn-secondary table-columns-reset`
keeps `table-columns-reset`, because that class is declared by a stylesheet and
positions the button; `mergeExtra` in the kit drops the kit's own token when the
caller fills the same slot.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "07-frontend" / "src"

VARIANTS = {
    "btn-primary": "primary",
    "btn-secondary": "secondary",
    "btn-ghost": "ghost",
    "btn-danger": "danger",
    "btn-link": "link",
}
SIZES = {"btn-sm": "sm"}

OPEN_TAG = re.compile(r'<(button|Link)\b')


def _matching_close(text: str, start: int, tag: str) -> int | None:
    """Index of the `</tag>` that closes the element opening at `start`."""
    scan = _blank_comments(text)
    depth = 0
    i = start
    open_re = re.compile(rf"<{tag}\b")
    close = f"</{tag}>"
    while i < len(scan):
        if scan.startswith(close, i):
            depth -= 1
            if depth == 0:
                return i
            i += len(close)
            continue
        m = open_re.match(scan, i)
        if m:
            depth += 1
            tag_end = _tag_end(text, i)
            # ⚠ `tag_end` is one PAST the `>`, so a self-closing tag ends
            # `…/>` at [end-2]. The first draft read [end-1], which is always
            # `>`, so a nested self-closing element pushed depth up and never
            # brought it down.
            if tag_end is not None and text[tag_end - 2] == "/":
                depth -= 1
            i = m.end()
            continue
        i += 1
    return None


def _blank_comments(text: str) -> str:
    """A SAME-LENGTH copy with `//` and `/* */` comments blanked to spaces.

    ⚠ THIS EXISTS BECAUSE AN APOSTROPHE IN A COMMENT ATE THREE FILES. The first
    scanner treated `'` as a string delimiter at brace depth 0 and jumped to the
    next one — so `// surface that quietly lacks it (DEF-196's shape).` sent it
    hunting for a closing quote four hundred lines away, and the tag it
    "closed" ended in the middle of `now={() =>`. tsc reported the damage forty
    lines from the cause, in a file the codemod had not visibly touched.

    Same length, so every index the caller computes still points at real text.
    Blanking rather than deleting is the whole trick.
    """
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif text[i] == '"':
            j = text.find('"', i + 1)
            i = n if j == -1 else j + 1
        else:
            i += 1
    return "".join(out)


def _tag_end(text: str, start: int) -> int | None:
    """Index just past the `>` of the tag opening at `start`, brace-aware.

    Only `"` delimits a string here. JSX allows single quotes, this codebase
    does not use them for attributes, and treating them as delimiters is what
    broke it — see `_blank_comments`.
    """
    scan = _blank_comments(text)
    depth = 0
    i = start
    while i < len(scan):
        c = scan[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == ">" and depth == 0:
            return i + 1
        elif c == '"' and depth == 0:
            close = scan.find('"', i + 1)
            if close == -1:
                return None
            i = close
        i += 1
    return None


def convert(text: str) -> tuple[str, list[str], list[str]]:
    """Returns (new text, changes, refusals)."""
    changes: list[str] = []
    refusals: list[str] = []
    out = text
    pos = 0
    while True:
        m = OPEN_TAG.search(out, pos)
        if m is None:
            break
        tag = m.group(1)
        end = _tag_end(out, m.start())
        if end is None:
            pos = m.end()
            continue
        # ⚠ `end` is just PAST the `>`, so the raw slice carries the closer.
        # Leaving it in produced `<Button …>\n>` — a duplicated `>` that tsc
        # reports 40 lines away from the cause. Strip it and remember the shape.
        raw = out[m.end() : end]
        self_closing = raw.rstrip().endswith("/>")
        attrs = raw.rstrip()[:-2] if self_closing else raw.rstrip()[:-1]
        cls = re.search(r'className="([^"]*)"', attrs)
        if cls is None or "btn" not in (cls.group(1) or "").split():
            if 'className={' in attrs and "btn" in attrs:
                line = out[: m.start()].count("\n") + 1
                refusals.append(f"line {line}: dynamic className, left alone")
            pos = m.end()
            continue

        tokens = cls.group(1).split()
        variant = next((VARIANTS[t] for t in tokens if t in VARIANTS), None)
        size = next((SIZES[t] for t in tokens if t in SIZES), None)
        extra = [t for t in tokens if t != "btn" and t not in VARIANTS and t not in SIZES]
        if variant is None:
            line = out[: m.start()].count("\n") + 1
            refusals.append(f"line {line}: `btn` with no known variant ({cls.group(1)!r})")
            pos = m.end()
            continue

        close_at = None if self_closing else _matching_close(out, m.start(), tag)
        if close_at is None and not self_closing:
            line = out[: m.start()].count("\n") + 1
            refusals.append(f"line {line}: no matching </{tag}>")
            pos = m.end()
            continue

        # Drop the className and the redundant `type`, then collapse the blank
        # line each removal leaves behind — a diff full of orphaned whitespace
        # is a diff nobody reads, and this codemod's output is meant to be read.
        new_attrs = attrs.replace(cls.group(0), "")
        # `type="button"` is the kit's default; `type="submit"` is behaviour.
        new_attrs = re.sub(r'\s*type="button"', "", new_attrs)
        new_attrs = re.sub(r"\n[ \t]*(?=\n)", "", new_attrs).rstrip()
        props = [f'variant="{variant}"']
        if size:
            props.append(f'size="{size}"')
        if extra:
            props.append(f'className="{" ".join(extra)}"')
        component = "Button" if tag == "button" else "ButtonLink"

        indent = " " * (m.start() - out.rfind("\n", 0, m.start()) - 1)
        joiner = "\n" + indent + "  " if "\n" in attrs else " "
        head = f"<{component}{joiner}{joiner.join(props)}{new_attrs}"
        head = head.rstrip()
        if self_closing:
            head = head[:-1].rstrip() + (joiner + "/>" if "\n" in attrs else " />")
        else:
            head += (("\n" + indent) if "\n" in attrs else "") + ">"

        tail_len = len(f"</{tag}>") if close_at is not None else 0
        if close_at is not None:
            out = out[: m.start()] + head + out[end:close_at] + f"</{component}>" + out[close_at + tail_len :]
        else:
            out = out[: m.start()] + head + out[end:]
        changes.append(f'{tag} "{cls.group(1)}" -> <{component} variant="{variant}">')
        pos = m.start() + len(head)
    return out, changes, refusals


def ensure_import(text: str, needs: set[str]) -> str:
    have = re.search(r'^import \{([^}]*)\} from "@/components/Button";', text, re.M)
    if have:
        names = {n.strip() for n in have.group(1).split(",") if n.strip()} | needs
        return text.replace(have.group(0), f'import {{ {", ".join(sorted(names))} }} from "@/components/Button";')
    anchor = re.search(r'^import .*from "@/components/[^"]*";$', text, re.M)
    line = f'import {{ {", ".join(sorted(needs))} }} from "@/components/Button";'
    if anchor:
        return text.replace(anchor.group(0), line + "\n" + anchor.group(0), 1)
    last = list(re.finditer(r"^import .*;$", text, re.M))[-1]
    return text[: last.end()] + "\n" + line + text[last.end() :]


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    dry = "--dry-run" in argv
    for name in [a for a in argv if not a.startswith("--")]:
        path = SRC / name
        text = path.read_text("utf-8")
        new, changes, refusals = convert(text)
        if changes:
            needs = set()
            if "<Button" in new and "<ButtonLink" not in "".join(changes):
                pass
            if any("<Button " in c or "<Button>" in c or 'variant' in c and "ButtonLink" not in c for c in changes):
                needs.add("Button")
            if any("ButtonLink" in c for c in changes):
                needs.add("ButtonLink")
            needs = {n for n in needs if f"<{n}" in new}
            new = ensure_import(new, needs)
        print(f"{name}: {len(changes)} converted, {len(refusals)} refused")
        for c in changes:
            print(f"   ✓ {c}")
        for r in refusals:
            print(f"   ⚠ {r}")
        if not dry and changes:
            path.write_text(new, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
