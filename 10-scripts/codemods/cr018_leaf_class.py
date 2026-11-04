#!/usr/bin/env python3
"""CR-018 — rewrite a LEAF class into a component, for the simple ones.

A leaf class styles one element and reaches nothing inside it: `.kicker`,
`.settings-note`, `.settings-refusal`. The rewrite is `<span className="kicker">`
-> `<Kicker>`, with the element carried through as `as="…"` when it is not the
component's default — `Panel` learned that lesson when 47 of its 149 sites
turned out to be `<section>` and both the component and the codemod assumed div.

    cr018_leaf_class.py --class kicker --component Kicker \\
        --module @/components/TextBits --default-tag span <files…>

Everything hard about the scan — comments blanked to same-length spaces before
parsing, brace-aware attributes, the self-closing test at [end-2] — is imported
from `cr018_button_sites.py` rather than written again. Three bugs live in those
few lines and none of them should be rediscovered.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cr018_button_sites import _matching_close, _tag_end

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "07-frontend" / "src"


def convert(text: str, cls: str, component: str, default_tag: str) -> tuple[str, list[str], list[str]]:
    changes: list[str] = []
    refusals: list[str] = []
    out = text
    pos = 0
    # ⚠ CAPITALISED COMPONENTS TOO. The first version matched `<[a-z]…` only,
    # so `<Link className="met-link">` — 21 of the 44 sites — was invisible to
    # it and the run reported "0 site(s)" over a screen full of them. A class
    # does not care what kind of element wears it.
    opener = re.compile(r"<([A-Za-z][A-Za-z0-9]*)\b")
    while True:
        m = opener.search(out, pos)
        if m is None:
            break
        tag = m.group(1)
        end = _tag_end(out, m.start())
        if end is None:
            pos = m.end()
            continue
        raw = out[m.end() : end]
        self_closing = raw.rstrip().endswith("/>")
        attrs = raw.rstrip()[:-2] if self_closing else raw.rstrip()[:-1]

        c = re.search(r'className="([^"]*)"', attrs)
        if c is None or cls not in c.group(1).split():
            pos = m.end()
            continue

        extra = [x for x in c.group(1).split() if x != cls]
        close_at = None if self_closing else _matching_close(out, m.start(), tag)
        if close_at is None and not self_closing:
            refusals.append(f"line {out[: m.start()].count(chr(10)) + 1}: no matching </{tag}>")
            pos = m.end()
            continue

        new_attrs = attrs.replace(c.group(0), "")
        if extra:
            new_attrs = f' className="{" ".join(extra)}"' + new_attrs
        if tag != default_tag:
            new_attrs = f' as="{tag}"' + new_attrs
        new_attrs = re.sub(r"\n[ \t]*(?=\n)", "", new_attrs).rstrip()
        new_attrs = re.sub(r"[ \t]{2,}", " ", new_attrs)

        indent = " " * (m.start() - out.rfind("\n", 0, m.start()) - 1)
        head = f"<{component}{new_attrs}"
        head += " />" if self_closing else ((("\n" + indent) if "\n" in attrs else "") + ">")

        if close_at is not None:
            out = (out[: m.start()] + head + out[end:close_at] + f"</{component}>"
                   + out[close_at + len(f"</{tag}>") :])
        else:
            out = out[: m.start()] + head + out[end:]
        changes.append(f"<{tag} .{cls}> -> <{component}{f' as={tag}' if tag != default_tag else ''}>")
        pos = m.start() + len(head)
    return out, changes, refusals


def ensure_import(text: str, component: str, module: str) -> str:
    have = re.search(rf'^import \{{([^}}]*)\}} from "{re.escape(module)}";', text, re.M)
    if have:
        names = {n.strip() for n in have.group(1).split(",") if n.strip()} | {component}
        return text.replace(have.group(0), f'import {{ {", ".join(sorted(names))} }} from "{module}";')
    line = f'import {{ {component} }} from "{module}";'
    anchors = list(re.finditer(r'^import .*from "@/components/[^"]*";$', text, re.M))
    if anchors:
        after = max(anchors, key=lambda m: m.group(0))
        return text.replace(after.group(0), after.group(0) + "\n" + line, 1)
    last = list(re.finditer(r"^import .*;$", text, re.M))[-1]
    return text[: last.end()] + "\n" + line + text[last.end() :]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="cls", required=True)
    ap.add_argument("--component", required=True)
    ap.add_argument("--module", required=True)
    ap.add_argument("--default-tag", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()

    total = 0
    for name in a.files:
        path = SRC / name
        text = path.read_text("utf-8")
        new, changes, refusals = convert(text, a.cls, a.component, a.default_tag)
        if changes:
            new = ensure_import(new, a.component, a.module)
        total += len(changes)
        for r in refusals:
            print(f"   ⚠ {name}: {r}")
        if not a.dry_run and changes:
            path.write_text(new, encoding="utf-8")
    print(f"{a.cls}: {total} site(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
