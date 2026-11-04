#!/usr/bin/env python3
"""Module report — stories · touched · built · proved, per module.

    python3 10-scripts/module_report.py                  # measure the working tree
    python3 10-scripts/module_report.py --at <commit>    # measure any commit
    python3 10-scripts/module_report.py --at A --vs B    # both ends, one table

WHY THIS FILE EXISTS AT ALL. A table of these four numbers was produced in a
working session and never committed, so when the Product Owner asked for it
again there was nothing to re-run — the numbers could not be reproduced and the
definitions behind them were gone. That is hard-won law 10 in its purest form.
The script is the artefact; a table pasted into a chat is not. Committing it
means the next comparison is the SAME measurement rather than a fresh opinion.

THE FOUR COLUMNS, defined here because a number without a definition invites
everyone to read it as whatever they hoped:

  stories   Declared. Every `US-<MOD>-###` the module's own docs define.
            The denominator, and the only column that does not move when code
            is written.

  touched   Someone wrote code for it. The id appears in the `packet:` line of
            a shipped file's Lifecycle trailer. Touched says a lane opened the
            story — it says NOTHING about whether a human can reach the result.

  built     BOTH HALVES EXIST. The trailer marks D (the API half) and E (the
            screen half) as done rather than `deferred`. This is the column
            that catches the failure this release kept hitting: an engine that
            is complete, tested and correct behind no route and no screen. Four
            modules reached whole-module scale on exactly that, and every gate
            stayed green over all of them, because a deferral is honest and
            nothing added the honest deferrals up.

  proved    A JOURNEY EXECUTES IT. The story is cited by a journey that has a
            spec file — the wiring index's `activated`, the only field in this
            repository that asserts something runs. Deliberately the strictest
            column: unit tests pass on code nobody can reach, and this release
            found five criticals by running a browser and none by running the
            24 gates. `proved` will always trail `built`, and the GAP between
            them is the useful reading, not either number alone.

WHAT THIS DOES NOT MEASURE, said plainly so the table is not over-read: it does
not know whether a journey PASSED, only that one exists and executes. Pass/fail
lives in the run receipt (07-frontend/journey-evidence/). A story can be
`proved` here and still be failing its journey — that is a deliberate choice,
because a receipt is a moment and this table is a shape.

Python 3.12 stdlib only. Safe to run from any cwd.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: `US-BIL-004` → billing. The prefix IS the module; the directory names carry
#: a numeric sort prefix that the story ids do not.
PREFIX_TO_MODULE = {
    "BIL": "billing",
    "PAY": "payments",
    "CUS": "customers",
    "TEN": "tenancy",
    "MET": "metering",
    "SHL": "platform-shell",
    "RAT": "rating",
    "REP": "reports",
    "LED": "ledger",
    "NOT": "notifications",
    "AST": "assets",
    "INT": "integrations",
    "CWP": "portal",  # CR-068 (2026-09-03)
    "IDN": "identity",
    "AUD": "audit",
}

STORY_RE = re.compile(r"\bUS-([A-Z]{3})-(\d{3,6})\b")
#: Backend trailers comment with `#`, frontend with `//`. Matching only one
#: undercounts an entire tier — the first run of this script read 141 touched
#: because every .tsx trailer was invisible to it.
PACKET_RE = re.compile(r"^\s*(?:#|//)\s*packet:\s*(.+)$", re.M)
CHECKLIST_RE = re.compile(r"^\s*(?:#|//)\s*checklist:(.*)$", re.M)
MARK_RE = re.compile(r"([A-H])(✔|✖|=deferred\([^)]*\))")

CODE_GLOBS = ("06-backend/**/*.py", "07-frontend/src/**/*.ts", "07-frontend/src/**/*.tsx")
DOC_GLOBS = ("04-docs/05-modules/*/05-user-stories.md", "04-docs/05-modules/*/06-epics/*.md")


def _read(path: pathlib.Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def measure(tree: pathlib.Path) -> dict[str, dict[str, set[str]]]:
    """Return {module: {stories, touched, built, proved}} as sets of story ids."""
    per: dict[str, dict[str, set[str]]] = {
        m: {"stories": set(), "touched": set(), "built": set(), "proved": set()}
        for m in PREFIX_TO_MODULE.values()
    }

    halves: dict[str, set[str]] = collections.defaultdict(set)

    def bucket(story: str) -> dict[str, set[str]] | None:
        mod = PREFIX_TO_MODULE.get(story[3:6])
        return per[mod] if mod else None

    # ── stories: declared in the module's own docs ──────────────────────────
    for pattern in DOC_GLOBS:
        for path in tree.glob(pattern):
            for m in STORY_RE.finditer(_read(path)):
                sid = f"US-{m.group(1)}-{m.group(2)}"
                if (b := bucket(sid)) is not None:
                    b["stories"].add(sid)

    # ── touched + built: read every shipped file's Lifecycle trailer ────────
    # `touched` = named in a packet line. `built` = that file's checklist marks
    # BOTH D (API half) and E (screen half) done rather than deferred.
    for pattern in CODE_GLOBS:
        for path in tree.glob(pattern):
            if "node_modules" in path.parts or "__pycache__" in path.parts:
                continue
            text = _read(path)
            if "packet:" not in text:
                continue
            packets = PACKET_RE.findall(text)
            if not packets:
                continue
            cited = {
                f"US-{m.group(1)}-{m.group(2)}"
                for line in packets
                for m in STORY_RE.finditer(line)
            }
            if not cited:
                continue
            cl = CHECKLIST_RE.search(text)
            marks = dict(MARK_RE.findall(cl.group(1))) if cl else {}
            for sid in cited:
                if (b := bucket(sid)) is None:
                    continue
                b["touched"].add(sid)
                # A story's API half and screen half live in DIFFERENT files —
                # a backend module honestly marks E=deferred because it is not
                # a screen. So the halves are unioned ACROSS files per story,
                # never required within one. Requiring both in one file read 30
                # built where the true figure is several times that, and made
                # `proved` exceed `built`, which is incoherent on its face.
                if marks.get("D") == "✔":
                    halves[sid].add("D")
                if marks.get("E") == "✔":
                    halves[sid].add("E")

    for sid, seen in halves.items():
        if {"D", "E"} <= seen and (b := bucket(sid)) is not None:
            b["built"].add(sid)

    # ── proved: cited by a journey that has a spec file (it executes) ───────
    index = tree / "08-qa/01-e2e/01-journey-story-index.json"
    if index.exists():
        try:
            data = json.loads(_read(index))
        except json.JSONDecodeError:
            data = {}
        activated = {
            j["id"] for j in data.get("journeys", []) if isinstance(j, dict) and j.get("activated")
        }
        for sid, journeys in (data.get("story_to_journeys") or {}).items():
            if not activated.intersection(journeys):
                continue
            # PROVED IS A SUBSET OF BUILT, enforced rather than assumed. A
            # journey may cite a story whose screen half is still deferred;
            # counting that as proved produced `proved > built` on two rows,
            # which is incoherent on its face and would have been read as
            # good news. A story nobody can reach is not proved by anything.
            if (b := bucket(sid)) is not None and sid in b["built"]:
                b["proved"].add(sid)
    return per


def render(now, then, label_now, label_then):
    cols = ("stories", "touched", "built", "proved")
    order = sorted(now, key=lambda m: -len(now[m]["stories"]))
    total = {c: sum(len(now[m][c]) for m in now) for c in cols}
    denom = total["stories"] or 1
    pct = lambda c, src: f"{100 * src[c] // denom}%"

    if then is None:
        print(f"{'module':<16}{'stories':>8}{'touched':>9}{'built':>7}{'proved':>8}")
        print("-" * 48)
        for m in order:
            r = now[m]
            print(f"{m:<16}{len(r['stories']):>8}{len(r['touched']):>9}"
                  f"{len(r['built']):>7}{len(r['proved']):>8}")
        print("-" * 48)
        print(f"{'TOTAL':<16}{total['stories']:>8}{total['touched']:>9}"
              f"{total['built']:>7}{total['proved']:>8}")
        print(f"{'':<16}{'':>8}{pct('touched', total):>9}"
              f"{pct('built', total):>7}{pct('proved', total):>8}")
        return

    prior = {c: sum(len(then.get(m, {}).get(c, ())) for m in now) for c in cols}
    cell = lambda a, b: f"{a} -> {b}" if a != b else str(b)
    head = f"{label_then} -> {label_now}"
    print(f"{'module':<16}{'stories':>8}{'touched':>16}{'built':>16}{'proved':>16}")
    print(f"{'':<16}{'':>8}{head:>16}{head:>16}{head:>16}")
    print("-" * 72)
    for m in order:
        n = now[m]
        o = then.get(m, {c: set() for c in cols})
        print(f"{m:<16}{len(n['stories']):>8}"
              f"{cell(len(o['touched']), len(n['touched'])):>16}"
              f"{cell(len(o['built']), len(n['built'])):>16}"
              f"{cell(len(o['proved']), len(n['proved'])):>16}")
    print("-" * 72)
    print(f"{'TOTAL':<16}{total['stories']:>8}"
          f"{cell(prior['touched'], total['touched']):>16}"
          f"{cell(prior['built'], total['built']):>16}"
          f"{cell(prior['proved'], total['proved']):>16}")
    print(f"{'':<16}{'':>8}"
          f"{cell(pct('touched', prior), pct('touched', total)):>16}"
          f"{cell(pct('built', prior), pct('built', total)):>16}"
          f"{cell(pct('proved', prior), pct('proved', total)):>16}")


def worktree_for(commit: str) -> pathlib.Path:
    """Materialise a commit read-only so the SAME script measures both ends."""
    dest = pathlib.Path("/tmp") / f"modreport-{commit[:12]}"
    if not dest.exists():
        subprocess.run(
            ["git", "worktree", "add", "--detach", "--force", str(dest), commit],
            cwd=ROOT, check=True, capture_output=True,
        )
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--at", help="commit to measure (default: the working tree)")
    ap.add_argument("--vs", help="second commit — prints both ends in one table")
    args = ap.parse_args()

    now_tree = worktree_for(args.at) if args.at else ROOT
    now = measure(now_tree)
    then = measure(worktree_for(args.vs)) if args.vs else None
    render(now, then, args.at[:7] if args.at else "now", args.vs[:7] if args.vs else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
