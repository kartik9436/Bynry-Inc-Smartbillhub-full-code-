#!/usr/bin/env python3
"""Traceability integrity lint. Fails CI on: duplicate IDs, dangling references,
status inconsistencies. Both agents and humans run this before pushing."""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
errors: list[str] = []

def collect(pattern: str, text: str) -> set[str]:
    return set(re.findall(pattern, text))

# Defined IDs
oq_reg = (ROOT / "12-governance/01-open-questions.md")
oq_defined = collect(r"^\| (OQ-(?:[A-Z]{3}-)?\d{3,6}) \|", oq_reg.read_text(), ) if oq_reg.exists() else set()
oq_defined = {m for m in re.findall(r"^\| (OQ-(?:[A-Z]{3}-)?\d{3,6}) \|", oq_reg.read_text(), re.M)} if oq_reg.exists() else set()

story_ids: dict[str, pathlib.Path] = {}
br_defined: set[str] = set()
for f in ROOT.glob("04-docs/05-modules/*/06-epics/*.md"):
    t = f.read_text()
    for sid in re.findall(r"^id: (US-[A-Z]{3}-\d{3,6}(?!\d))", t, re.M):
        if sid in story_ids:
            errors.append(f"duplicate story id {sid}: {f} and {story_ids[sid]}")
        story_ids[sid] = f
for f in ROOT.glob("04-docs/05-modules/*/02-business-rules.md"):
    br_defined |= set(re.findall(r"BR-[A-Z]{3}-\d{3,6}(?!\d)", f.read_text()))
# BRs may also be defined inline in epic files (§2 tables)
for f in ROOT.glob("04-docs/05-modules/*/06-epics/*.md"):
    br_defined |= set(re.findall(r"BR-[A-Z]{3}-\d{3,6}(?!\d)", f.read_text()))

# References resolve
for f in list(ROOT.glob("04-docs/05-modules/*/06-epics/*.md")):
    t = f.read_text()
    for oq in set(re.findall(r"OQ-(?:[A-Z]{3}-)?\d{3,6}(?!\d)", t)):
        if oq_defined and oq not in oq_defined:
            errors.append(f"{f.name}: references {oq} not in registry")
    for m in re.finditer(r"^blocked_by: \[(.*?)\]", t, re.M):
        refs = [x.strip() for x in m.group(1).split(",") if x.strip()]
        for r in refs:
            if oq_defined and r not in oq_defined:
                errors.append(f"{f.name}: blocked_by {r} not in registry")
    # ready stories must not be blocked
    for block in re.split(r"(?=^---$)", t, flags=re.M):
        if "status: ready" in block and re.search(r"blocked_by: \[.+\]", block):
            sid = re.search(r"^id: (\S+)", block, re.M)
            errors.append(f"{f.name}: {sid.group(1) if sid else '?'} is ready but has blocked_by")

# ── dependency-system checks (PO-confirmed 2026-08-08) ──
import itertools
story_status: dict[str, str] = {}
story_deps: dict[str, list[str]] = {}
for f in ROOT.glob("04-docs/05-modules/*/06-epics/*.md"):
    t = f.read_text()
    for block in re.split(r"(?=^id: US-)", t, flags=re.M):
        m = re.match(r"id: (US-[A-Z]{3}-\d{3,6}(?!\d))", block)
        if not m: continue
        sid = m.group(1)
        sm = re.search(r"^status: (\w+)", block, re.M)
        story_status[sid] = sm.group(1) if sm else "?"
        dm = re.search(r"^depends_on: \[(.*?)\]", block, re.M)
        if dm:
            deps = [x.strip() for x in dm.group(1).split(",") if x.strip()]
            story_deps[sid] = deps
            for d in deps:
                if not re.fullmatch(r"US-[A-Z]{3}-\d{3,6}", d):
                    errors.append(f"{sid}: malformed depends_on entry '{d}'")
for sid, deps in story_deps.items():
    for d in deps:
        if d not in story_ids:
            errors.append(f"{sid}: depends_on {d} does not exist")
        elif story_status.get(sid) in ("ready", "done") and story_status.get(d) in ("draft", "blocked", "deferred"):
            errors.append(f"{sid} is {story_status[sid]} but depends on {d} ({story_status.get(d)}) — build order violation")
for jf in ROOT.glob("08-qa/01-e2e/journeys/J*.md"):
    for ref in set(re.findall(r"US-[A-Z]{3}-\d{3,6}(?![\d*])", jf.read_text())):
        if ref not in story_ids:
            errors.append(f"{jf.name}: references {ref} which does not exist")

if errors:
    print("TRACE LINT FAILED:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print(f"trace_lint OK — {len(story_ids)} stories, {len(br_defined)} BR refs, {len(oq_defined)} OQs")
