#!/usr/bin/env python3
"""Generate the journey<->story wiring index — the ACTIVATION AUTHORITY — in two views.

Single generated source (avoids churning 227 story frontmatters); re-runnable;
trace target for QA automation. Original J1-J6 frontmatter wiring stands.

    python3 10-scripts/07-e2e-wiring-index.py          # write both views
    python3 10-scripts/07-e2e-wiring-index.py --check   # exit 1 if either is stale

TWO VIEWS, ONE GENERATOR (hard-won law 5). `01-journey-story-index.md` is the
human view and `01-journey-story-index.json` is the machine view that gate G12
reads. They are not two sources: both come out of `build_index()` below, and
`--check` (which G12 runs on every merge) re-derives them in memory and fails on
any difference, so a hand-edited or stale committed copy goes RED instead of
quietly disagreeing with the journeys.

WHAT CHANGED 2026-08-11 (the E2E journey-activation lane), and why each matters:

 1. **J-journeys were silently dropped.** The id regex was `^id: (T\\S+)`, so
    every one of the 24 J-tier files — J1..J6 spines, J07..J24 feature journeys —
    was read, matched nothing, and `continue`d. The index that DECIDES ACTIVATION
    (07-frontend/e2e/README.md §"Journey activation") therefore had no row for
    the NSF, payment-plan, budget-billing or first-bill journeys at all, and no
    amount of story-building could ever have activated one. The regex now takes
    `J` and `T` ids both.
 2. **"Activates when its last story is built" had no machine-readable notion of
    BUILT.** This file now computes one and NAMES it, rather than implying it:
    a story counts as built when at least one file of the B12 codebase (backend
    `apps/`, frontend `src/`) cites its US-ID in a `── Trace ──` header — the
    same convention gate G2 already enforces. It is EVIDENCE, not proof: a Trace
    citation says code claims that story, not that the screen a journey clicks
    exists. So the JSON reports `ready_by_stories` (all declared stories cited)
    and keeps it SEPARATE from `activated` (a spec file exists and claims the
    id). Only the second is a claim that anything executes. OQ-172 asks the PO to
    ratify or replace the definition.
 3. **207 of the 303 indexed journey documents declare no `stories:` frontmatter at all**
    (every generated T3M money-triple and every T3P pairwise file). For those the
    "last story is built" test is not false — it is UNDEFINED, and the JSON says
    `ready_by_stories: null` rather than defaulting them to ready or to blocked.
    OQ-173 carries the question of how a generated journey ever activates.

NEVER writes anything outside 08-qa/01-e2e/. Python 3.12 stdlib only.
"""

from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
JOURNEY_DIR = REPO_ROOT / "08-qa" / "01-e2e" / "journeys"
INDEX_MD = REPO_ROOT / "08-qa" / "01-e2e" / "01-journey-story-index.md"
INDEX_JSON = REPO_ROOT / "08-qa" / "01-e2e" / "01-journey-story-index.json"
SPEC_DIR = REPO_ROOT / "07-frontend" / "e2e"

# `J12`, `T3M-001`, `T5-04`, `T3P-00` — the id grammar the catalog uses.
JOURNEY_ID_RE = re.compile(r"^id: ([JT]\S+)", re.M)
US_ID_RE = re.compile(r"US-[A-Z]{3}-\d{3,6}(?!\d)")
BR_ID_RE = re.compile(r"BR-[A-Z]{3}-\d{3,6}(?!\d)")
TIER_RE = re.compile(r"^tier: (\d+)", re.M)
STORIES_RE = re.compile(r"^stories: \[(.*?)\]", re.M | re.S)
TRACE_MARK = "── Trace ──"


def _trace_header_lines(text: str) -> list[str]:
    """The comment lines of a `── Trace ──` block — same reader as gates/common.py.

    Duplicated deliberately rather than imported: this generator is a QA script
    that must run standalone (CI calls it before the gate suite), and the four
    lines below are the whole contract. If B8 changes the marker, both move.
    """
    lines: list[str] = []
    in_block = False
    for line in text.splitlines():
        if not in_block:
            if TRACE_MARK in line:
                in_block = True
            continue
        stripped = line.strip().lstrip("#/ ").strip()
        if not line.strip().startswith(("#", "//", "*")):
            break
        if stripped and set(stripped) <= {"─"}:
            break
        lines.append(line)
    return lines


def built_story_ids() -> set[str]:
    """US-IDs cited in a Trace header somewhere in the B12 codebase.

    THE HONEST LIMIT OF THIS SIGNAL, stated where it is computed: a citation
    proves a code file claims the story, not that the story is finished, wired to
    a screen, or reachable by a human. J09's six stories are five-sixths "built"
    by this measure while no budget-billing screen exists at all. It is the only
    machine-readable build signal this repo has (G2 depends on the same one), and
    naming it in the JSON is what lets a reviewer disagree with it.
    """
    built: set[str] = set()
    roots = [REPO_ROOT / "06-backend" / "apps", REPO_ROOT / "07-frontend" / "src"]
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix not in (".py", ".ts", ".tsx"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if TRACE_MARK not in text:
                continue
            header = "\n".join(_trace_header_lines(text))
            built |= set(US_ID_RE.findall(header))
    return built


def spec_files() -> dict[str, str]:
    """journey-id -> repo-relative spec path, for `<Journey-ID>.spec.ts` files.

    The convention G12 enforces (07-frontend/e2e/README.md §"Journey
    activation"): activating a journey means authoring `<Journey-ID>.spec.ts`.
    A spec whose NAME is not a journey id (W0-smoke, W3-money-render) is not an
    activation and is not counted here — those two say so in their own headers.
    """
    found: dict[str, str] = {}
    if not SPEC_DIR.is_dir():
        return found
    for path in sorted(SPEC_DIR.glob("*.spec.ts")):
        found[path.name[: -len(".spec.ts")]] = str(path.relative_to(REPO_ROOT))
    return found


def build_index() -> dict:
    files = sorted(
        list(JOURNEY_DIR.glob("T*.md")) + list(JOURNEY_DIR.glob("J*.md"))
    )
    built = built_story_ids()
    specs = spec_files()

    journeys: list[dict] = []
    story_map: dict[str, list[str]] = collections.defaultdict(list)
    rule_map: dict[str, list[str]] = collections.defaultdict(list)

    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        match = JOURNEY_ID_RE.search(text)
        # J1..J6 (the T1 spines) carry NO frontmatter block at all — they predate
        # it. Dropping them was the second half of the same bug as the `T\S+`
        # regex: the six oldest journeys in the catalog, the ones every module
        # handoff hangs off, were invisible to the index that decides activation.
        # The filename prefix is their id, and the catalog names files after ids.
        jid = match.group(1) if match else path.name.split("-")[0]
        stories_block = STORIES_RE.search(text)
        declared = sorted(set(US_ID_RE.findall(stories_block.group(1)))) if stories_block else []
        tier = TIER_RE.search(text)
        unbuilt = [s for s in declared if s not in built]
        journeys.append(
            {
                "id": jid,
                "file": str(path.relative_to(REPO_ROOT)),
                "tier": int(tier.group(1)) if tier else None,
                "stories": declared,
                "stories_unbuilt": unbuilt,
                # null = the journey declares no stories, so the B12 r3 §5
                # activation test ("its last story is built") is UNDEFINED here,
                # not false. 207 of the 303 indexed files are in this state — OQ-173.
                "ready_by_stories": (None if not declared else not unbuilt),
                "spec": specs.get(jid),
                "activated": jid in specs,
            }
        )
        for us in set(US_ID_RE.findall(text)):
            story_map[us].append(jid)
        for br in set(BR_ID_RE.findall(text)):
            rule_map[br].append(jid)

    return {
        "generated_by": "10-scripts/07-e2e-wiring-index.py",
        "note": (
            "Machine view of the journey wiring index. `activated` means a "
            "<Journey-ID>.spec.ts exists and claims the id — it is the ONLY field "
            "that asserts something executes. `ready_by_stories` is Trace-header "
            "evidence that a journey's declared stories have code (OQ-172), and "
            "null where the journey declares no stories (OQ-173)."
        ),
        "journey_files": len(files),
        "journeys": sorted(journeys, key=lambda j: j["id"]),
        "activated": sorted(j["id"] for j in journeys if j["activated"]),
        "ready_by_stories": sorted(j["id"] for j in journeys if j["ready_by_stories"]),
        # Spec files that are NOT named for a journey. Not an error and not a
        # gap: `W0-smoke` is the W0 harness proof and `W3-money-render` is the
        # first browser-to-database money proof, and each says in its own header
        # why it claims no catalog id. Listed so the count of browser specs and
        # the count of activations can never be read as the same number.
        "non_journey_specs": sorted(set(specs) - {j["id"] for j in journeys}),
        "story_to_journeys": {us: sorted(v) for us, v in sorted(story_map.items())},
        "rule_to_journeys": {br: sorted(v) for br, v in sorted(rule_map.items())},
    }


def render_markdown(index: dict) -> str:
    story_map = index["story_to_journeys"]
    rule_map = index["rule_to_journeys"]
    out = [
        "# Journey wiring index (GENERATED — 10-scripts/07-e2e-wiring-index.py; do not hand-edit)",
        "",
        f"Catalog: {index['journey_files']} journey files (J-tier + T-tier — the J files were "
        "dropped by this generator until 2026-08-11; see the script docstring). "
        "Story frontmatter keeps J1-J6; the FULL wiring lives here (design §6-as-amended).",
        "",
        "**Activation** (B12 r3 §5): a journey activates when its last story is built, and "
        "activating it means authoring `<Journey-ID>.spec.ts` in `07-frontend/e2e/`. The "
        "machine view of this file — `01-journey-story-index.json` — carries that state per "
        "journey and gate G12 reads it. Today "
        f"**{len(index['activated'])} journey(s) are activated**: "
        f"{', '.join(index['activated']) if index['activated'] else 'none'}.",
        "",
        f"{len(index['ready_by_stories'])} journey(s) have every DECLARED story cited in a code "
        "Trace header (`ready_by_stories`). That is evidence, not activation: a citation says "
        "code claims the story, not that a human can click the flow. "
        f"{sum(1 for j in index['journeys'] if j['ready_by_stories'] is None)} journey(s) declare "
        "no stories at all, so the test is undefined for them (OQ-172, OQ-173).",
        "",
        f"## Story → journeys ({len(story_map)} stories referenced)",
        "",
        "| Story | Journeys |",
        "|---|---|",
    ]
    out += [f"| {us} | {', '.join(js)} |" for us, js in story_map.items()]
    out += ["", f"## Rule → journeys ({len(rule_map)} rules exercised)", "", "| Rule | Journeys |", "|---|---|"]
    for br, js in rule_map.items():
        shown = ", ".join(js[:12]) + (" …" if len(js) > 12 else "")
        out.append(f"| {br} | {shown} |")
    return "\n".join(out) + "\n"


def render_json(index: dict) -> str:
    return json.dumps(index, indent=2, sort_keys=False) + "\n"


def main(argv: list[str]) -> int:
    index = build_index()
    markdown = render_markdown(index)
    payload = render_json(index)

    if "--check" in argv:
        stale = []
        for path, want in ((INDEX_MD, markdown), (INDEX_JSON, payload)):
            have = path.read_text(encoding="utf-8") if path.is_file() else None
            if have != want:
                stale.append(str(path.relative_to(REPO_ROOT)))
        if stale:
            print(f"STALE: {', '.join(stale)} — re-run 10-scripts/07-e2e-wiring-index.py")
            return 1
        print(f"index fresh: {index['journey_files']} journeys, {len(index['activated'])} activated")
        return 0

    INDEX_MD.write_text(markdown, encoding="utf-8")
    INDEX_JSON.write_text(payload, encoding="utf-8")
    print(
        f"index: {index['journey_files']} journeys, "
        f"{len(index['story_to_journeys'])} stories wired, "
        f"{len(index['rule_to_journeys'])} rules exercised, "
        f"{len(index['activated'])} ACTIVATED (spec files), "
        f"{len(index['ready_by_stories'])} story-ready"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
