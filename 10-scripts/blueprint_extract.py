#!/usr/bin/env python3
"""Extract a blueprint PDF into greppable text in the repo, one file per screen.

WHY THIS EXISTS
---------------
`DEF-GOV-5006` (2026-09-12, severity **high**, open): *"four more PO rulings of
2026-09-10 exist only in the Accounts blueprint and in no file of this
repository — and they are the rules the whole account-detail redesign is drawn
to."* Its escape_reason is the general form: **a document nobody can grep is a
document the next agent does not have.**

⚠ **AND THAT ROW'S OWN DIAGNOSIS IS WRONG, WHICH IS WHY THIS TOOL IS SIX LINES
OF `pypdf` RATHER THAN AN OCR PIPELINE.** It says *"101 of its 242 pages extract
under 150 characters and every digit extracts as '&'"*. Measured on 2026-09-13:
**11 pages are thin and 231 read fine**, digits included. The blueprint was
readable all along and nobody read it. The row is corrected where it is filed;
this docstring records the measurement so the next reader does not inherit the
wrong reason for the right fix.

WHAT IT COSTS TO NOT HAVE THIS, MEASURED ON ONE SCREEN
------------------------------------------------------
`ACC-02` was redesigned on 2026-09-10 under four PO rulings and **nothing was
ever scoped to it**. The screen rendered 20 label/value rows at the commit the
blueprint audited and the identical 20 three days later — so this was never
drift, it was a drawing treated as a document instead of as work. Of the eleven
served fields the blueprint counted as reaching no screen, **eight were still
referenced nowhere** in the account-detail files on 2026-09-13.

⚠ **AND IT COST THREE WRONG ANSWERS IN ONE HOUR**, all the same shape: a lane
read ONE frame of a 242-page PDF, called it "the design", reported the product
as having drifted from it, and proposed reversing a PO ruling — because reading
a PDF means opening it at a page, and `grep` means seeing every occurrence. **A
fragment generalised is this repository's most expensive front-end failure and
an un-greppable source is what makes it easy.**

WHAT IT WRITES
--------------
    04-docs/05-modules/<module>/blueprint/00-index.md      the entry list
    04-docs/05-modules/<module>/blueprint/<nn>-<slug>.md   one file per screen

⚠ **IT USED TO ALSO WRITE `99-full.txt` — EVERY PAGE AGAIN — AND THAT IS GONE.**
It was 628K of bytes the nineteen screen files already held, on a repository the
PO had just asked to keep small (*"I dont want to write lot of content in
repo"*). A second copy of a document is a second copy free to drift, which is
hard-won law 5 in a folder rather than in a build. **Where a screen's pages are
shared with a sibling entry, the text is written ONCE and the sibling names the
file that holds it** — the same reasoning, one level down: the Accounts
blueprint prints `16` and `17` over one page span and writing both cost another
280K for the same words.

Each screen file carries the blueprint's own heading, the pages it spans, and
the extracted text of those pages VERBATIM. **Nothing is summarised, reworded or
tidied** — a summary is a second artefact free to be wrong on its own, which is
the fault this whole tool exists to remove. Where extraction is poor the file
says so with its character count rather than quietly presenting a thin page as a
complete one (law 7: a check that cannot cover its subject must print what it
skipped beside what it checked).

USAGE
-----
    python3 10-scripts/blueprint_extract.py <pdf> <module-folder> [--dry-run]

    # the PDF may live on another branch — read it without checking it out:
    git show origin/<branch>:'05-prototype/02 Accounts Menu Blueprint.pdf' > /tmp/b.pdf
    python3 10-scripts/blueprint_extract.py /tmp/b.pdf 03-customers

⚠ **IT NEVER WRITES INTO `05-prototype/`.** The PDF is the source and stays
wherever it is; this writes only under the module's own `blueprint/` folder, so
a re-run after the PO re-uploads a blueprint is a clean overwrite of derived
text and touches nothing anybody authored.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODULES = REPO / "04-docs" / "05-modules"

# A screen entry heads a page with `NN Title ...` — two digits, a space, then a
# capital.
#
# ⚠ **THE SHAPE ALONE IS NOT ENOUGH AND THE FIRST VERSION OF THIS PATTERN PROVED
# IT ON THE FIRST RUN.** `^\d{2} [A-Z]` matched **`18 Cedar Ridge Way`** and
# **`88 Quarry Lane, Silver Creek, TX 78611`** — street addresses inside the
# drawings — and a prose line beginning `10 CloseOutPage.tsx's Story line…`.
# Three false entries, and worse, each one SWALLOWED the real screens after it:
# the run reported 18 entries and lost `06`, `17`, and the true `10` and `18`
# inside spans that began at an address. A count that looks plausible while
# silently excluding part of its subject is law 7's fifth shape exactly.
#
# **WHAT ACTUALLY MARKS AN ENTRY IS THE ROUTE UNDERNEATH IT.** Every screen in
# these blueprints prints its address on the next line or two — `/:tenant/…` in
# the register, `/brazosbend/…` in the drawings — and no address or prose line
# does. The status vocabulary (`EXISTS BEHIND`, `NEW BUILD`, `BLOCKED`,
# `NO COMMITMENT`) is accepted as a second witness for an entry whose route sits
# further down the page.
ENTRY = re.compile(r"^(\d{2}) ([A-Z][^\n]{6,})$")
ROUTE = re.compile(r"/:?[a-z]+[a-z-]*/")
STATUS = re.compile(r"\b(EXISTS BEHIND|NEW BUILD|BLOCKED|NO COMMITMENT|NOT DRAWN)\b")
THIN = 150  # chars below which a page carried no readable text


def slug(text: str) -> str:
    """`Account detail EXISTS BEHIND ACC-03` -> `account-detail`."""
    words = re.split(r"\s+", text.strip())
    keep: list[str] = []
    for w in words:
        # Stop at the blueprint's own status vocabulary — it is metadata about
        # the entry, not part of the screen's name.
        if w.isupper() and len(w) > 2:
            break
        keep.append(w)
    s = re.sub(r"[^a-z0-9]+", "-", " ".join(keep).lower()).strip("-")
    return s[:48] or "screen"


def read_pages(pdf: Path) -> list[str]:
    try:
        import pypdf
    except ImportError:  # pragma: no cover - environment
        sys.exit("pypdf is not installed: python3 -m pip install pypdf")
    return [(p.extract_text() or "") for p in pypdf.PdfReader(str(pdf)).pages]


def find_entries(pages: list[str]) -> list[tuple[int, str, str]]:
    """(page index, number, title) for every screen entry, in page order."""
    found: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for i, text in enumerate(pages):
        for line in text.split("\n"):
            m = ENTRY.match(line.strip())
            if not m:
                continue
            num, title = m.group(1), m.group(2).strip()
            # An entry number appears once, at its first page. A later match on
            # the same number is a running header or a coincidence.
            if num in seen:
                continue
            # The two witnesses, either of which is enough — see ENTRY above.
            rest = "\n".join(text.split("\n")[text.split("\n").index(line) + 1:][:3])
            if not (STATUS.search(title) or ROUTE.search(rest)):
                continue
            seen.add(num)
            found.append((i, num, title))
            # ⚠ **NO `break` — TWO ENTRIES CAN SHARE A PAGE, AND THE FIRST
            # VERSION BROKE OUT AFTER ONE AND LOST THREE SCREENS.** On the
            # Accounts blueprint, `05 Move-in wizard · standalone` and
            # `06 Service request capture` are six lines apart on one page, as
            # are `08`/`10` and `16`/`17`. Breaking took the first of each pair
            # and then SWALLOWED the second into the previous screen's page
            # span — so the run reported a plausible 16 entries while three
            # screens had silently no file at all. **A count that looks right
            # over a scope it quietly excludes is law 7's fifth shape**, and it
            # is the second time this one function produced it.
    return sorted(found, key=lambda e: (e[0], e[1]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("pdf", type=Path)
    ap.add_argument("module", help="folder under 04-docs/05-modules, e.g. 03-customers")
    ap.add_argument("--dry-run", action="store_true", help="report and write nothing")
    args = ap.parse_args()

    if not args.pdf.exists():
        sys.exit(f"no such file: {args.pdf}")
    out = MODULES / args.module / "blueprint"
    if not (MODULES / args.module).is_dir():
        sys.exit(f"no such module folder: {MODULES / args.module}")

    pages = read_pages(args.pdf)
    entries = find_entries(pages)
    thin = [i + 1 for i, p in enumerate(pages) if len(p.strip()) < THIN]
    print(f"{args.pdf.name}: {len(pages)} pages, {len(entries)} screen entries, "
          f"{len(thin)} page(s) under {THIN} chars")
    if not entries:
        sys.exit("no screen entries found — check the entry pattern against this document")

    # Each entry runs to the page the NEXT DISTINCT start page begins on.
    #
    # ⚠ **"THE NEXT ENTRY'S PAGE" IS WRONG WHENEVER TWO ENTRIES SHARE ONE, AND
    # IT EMITS AN EMPTY FILE RATHER THAN FAILING.** `05` and `06` both begin on
    # page 75 of the Accounts blueprint, so pairing each entry with its
    # immediate successor gave `05` the span 75–74 — a negative range, silently
    # slicing to nothing, written out as a 0-character screen file that looks
    # like a screen with no content instead of like a bug. Grouping by DISTINCT
    # start page gives both entries the real span and records that they share
    # it, which is the truth: the blueprint prints them on one page.
    starts = sorted({e[0] for e in entries})
    next_start = {p: (starts[i + 1] if i + 1 < len(starts) else len(pages))
                  for i, p in enumerate(starts)}
    shared = {p: [e for e in entries if e[0] == p] for p in starts}
    bounds = [(e, next_start[e[0]]) for e in entries]

    index = [
        f"# {args.pdf.name} — every screen, extracted\n",
        "**Derived text. Do not edit — re-run `10-scripts/blueprint_extract.py` instead.**",
        "The PDF is the source; this is what makes it greppable (`DEF-GOV-5006`).\n",
        f"- pages: **{len(pages)}** · entries: **{len(entries)}** · "
        f"pages under {THIN} chars: **{len(thin)}**",
        f"- thin pages (little or no extractable text): {thin or 'none'}\n",
        "| # | Screen | Pages | Chars | File |",
        "|---|---|---|---|---|",
    ]
    for (start, num, title), end in bounds:
        name = f"{num}-{slug(title)}.md"
        siblings_pre = [x for x in shared[start] if x[1] != num]
        # The FIRST entry on a shared span carries the text; the others carry a
        # pointer. Writing it once per entry duplicated 280K on the Accounts
        # blueprint for two entries that print over the same pages.
        owner = shared[start][0]
        body = "\n".join(pages[start:end]) if owner[1] == num else ""
        siblings = [x for x in shared[start] if x[1] != num]
        share_note = (f" (shares these pages with {', '.join(x[1] for x in siblings)})"
                      if siblings else "")
        index.append(f"| {num} | {title} | {start + 1}–{end}{share_note} | {len(body):,} | `{name}` |")
        if args.dry_run:
            continue
        out.mkdir(parents=True, exist_ok=True)
        (out / name).write_text(
            f"# {num} · {title}\n\n"
            f"**Source:** `{args.pdf.name}`, pages {start + 1}–{end}. "
            f"Extracted text, verbatim — **derived, do not edit.**\n\n"
            f"**{len(body):,} characters over {end - start} page(s).**"
            + (f"\n\n⚠ **The blueprint prints this entry on the same page as "
               f"{', '.join(x[1] + ' · ' + x[2] for x in siblings)}**, so the "
               f"text below covers all of them. Read the heading you want.\n"
               if siblings else "")
            + ("\n\n⚠ **Some of these pages carry little extractable text** "
               "(a drawing rather than prose); read the PDF for those.\n"
               if any(len(pages[p].strip()) < THIN for p in range(start, end)) else "\n")
            + ("\n---\n\n```\n" + body.replace("```", "'''") + "\n```\n"
               if body else
               f"\n---\n\n**The text for these pages is in "
               f"`{owner[1]}-{slug(owner[2])}.md`** — the first entry on this "
               f"span. The blueprint prints both over the same pages, so it is "
               f"written once rather than twice.\n"),
            encoding="utf-8",
        )
    if not args.dry_run:
        out.mkdir(parents=True, exist_ok=True)
        (out / "00-index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
        print(f"wrote {len(entries) + 1} file(s) to {out.relative_to(REPO)}")
    else:
        print("\n".join(index))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
