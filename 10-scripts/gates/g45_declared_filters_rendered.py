#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-045 (the toolbar standard) · DEF-1701 prevention column, verbatim:
#           "Extend G13 to the config direction: a TableConfig declaring filters
#           whose screen never passes filterBarSlot is dead configuration and
#           must fail."
# Rules:    BR-SHL-010 (only DECLARED capabilities render — and everything
#           declared IS a capability) · B14 rule 12 (the toolbar's grammar)
# Defects:  DEF-1701 (assets: 7 filters declared, no control on 4 tabs;
#           Settings > Custom fields identical) · DEF-007..010 (the
#           unwired-prop class G13 was written for) · DEF-520 (the unmounted
#           class G40 was written for)
# ───────────────────────────────────────────────────────
"""G45 — a `TableConfig` that declares filters must render a filter control.

WHY A SIBLING AND NOT A WIDENING OF G13
---------------------------------------
Hard-won law 2 — *"built is not wired"* — names G13 as its enforcement, and
G13 missed this completely. **The reason is worth stating exactly, because it
is the reusable part:**

    G13 asks *"does every optional PROP have a non-test caller?"*
    This is the MIRROR IMAGE — a CONFIG KEY populated with nobody reading it.

`AssetRegistryPage` set `TableConfig.filters` to SEVEN groups — status, type,
meter_type, service, premises_id, assigned, test_due, every one of them
genuinely matched by `assets.selectors.asset_list` — and never passed
`DataTable`'s `filterBarSlot`. There is no prop for G13 to ask about: the prop
is *absent*, which is the legal state of an optional prop. `filters: [...]`
type-checks, renders, and passes every test, **because the absent control
asserts nothing**. The Product Owner found it by looking at four screens:
*"on assets - tookkit dont have filters; same is the case with sub meters,
devices, investory"*.

A SIBLING GATE, on the precedent G40 set. G13 is PO-RATIFIED (2026-08-11,
option A — *"keep all four blocking"*) and its own docstring says editing its
question is a change to a ratified decision. G40 was added rather than folding
the mount question into G13, for exactly this reason, and its docstring says so.
This is the third question in that family:

    G13  a PROP nothing passes         → dead UI behind a prop
    G40  a COMPONENT nothing mounts    → dead UI behind an import
    G45  a CONFIG KEY nothing reads    → dead UI behind a declaration

WHAT IT CHECKS
--------------
For every non-test `.ts`/`.tsx` under `07-frontend/src`, with comments blanked:
**count the `filters:` ARRAY declarations and count the `filterBarSlot`
passes. More declarations than passes is a FAIL.**

**Counted, not `key in file`**, and that is load-bearing rather than tidy: two
screens declare TWO tables in one file (`SettingsRoutesCyclesTab` — routes and
cycles — and `PaymentsPage`). A `"filterBarSlot" in text` check would go green
on a file whose SECOND table renders no control, which is the DEF-337/G37
lesson: check the thing that carries the guarantee, not a string that happens to
appear nearby. G43 clause (a) counts `searchFields` against `searchPlaceholder`
for the same reason and this clause is deliberately its twin.

**The ARRAY form only — `filters:` followed by `[`.** `filters: state.filters`
and `filters: { ...state.filters, tab }` are request-param plumbing, not
capability declarations, and both appear in the very files this gate is about.
Matching the bare key would fire on every list in the product.

BASELINE ZERO, HARD — NO LEGACY TO GRANDFATHER
-----------------------------------------------
The sweep found **THREE** offenders, and the third is why the sweep exists:
`ServiceRequestsListPage` had the same shape, was never in a PO screenshot, and
carried a lifecycle comment SAYING SO — *"the segment FILTER is still not
reachable from either copy: this screen passes no `filterBarSlot`, which
predates this packet and is untouched by it"*. A comment naming a gap is a note,
never a plan (hard-won law 1). All three are fixed in the same commit as this
file, so the number is an invariant and not a debt register.

⚠ **DO NOT RAISE IT.** A screen that genuinely offers no filterable dimension
declares no `filters` — BR-SHL-010 says an undeclared capability does not
render, and the converse is what this gate is: a DECLARED capability must.

WHAT IT DELIBERATELY DOES NOT CHECK
-----------------------------------
**Whether the rendered control can reach every declared group.** `chipFilters`
legitimately drops a group with no options (BR-SHL-010) and reduces
`premises_id` to a removable chip because B14 rule 9 refuses a 500-checkbox
wall. A gate that demanded a one-to-one mapping would fail those two ruled
behaviours, and a gate that argues with a ruling gets switched off (G43's own
statement of the same limit). This gate answers exactly one question — *is a
filter control rendered at all* — and answers it completely.

**Whether the server honours the filter.** BE-05 ignores an undeclared `f.`
param, so a declared group the endpoint does not match returns everything
silently. No source-reading check can compare a TS array to a Django `Q()`;
DEF-950 and G43's docstring settle that this belongs to r11 discipline, and
pretending otherwise would be DEF-182's "a check that cannot distinguish pass
from fail is worse than none".

COMMENTS ARE STRIPPED, LINE COMMENTS FIRST (DEF-741)
-----------------------------------------------------
Prose ABOUT the rule must never satisfy or trip the rule — G31 was tripped from
a comment twice, and G37/G43 both carry this guard. Three of the files this gate
touches now carry a long comment naming `filterBarSlot`, so without stripping,
this gate would report every one of them fixed by its own explanation.
⚠ BLOCK-FIRST STRIPPING IS A BUG: a `//` line spelling a path with a star in it
contains `/*`, which opens a comment that closes at the next `*/` anywhere below.

PROVED RED BEFORE TRUSTED GREEN (hard-won law 7) — the verbatim failure is in
the `RED PROOF` block below, taken in a throwaway `git worktree` against the
tree AS THE PRODUCT OWNER PHOTOGRAPHED IT, so the shared tree was never mutated.

Python 3.12 stdlib only. Safe to run from any cwd. Nothing here ever writes.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "07-frontend" / "src"

#: 0 after DEF-1701 wired AssetRegistryPage, SettingsCustomFields and
#: ServiceRequestsListPage. See the docstring: this is an invariant, not a debt.
UNRENDERED_BASELINE = 0

#: `filters:` opening an ARRAY, at an object-key position (line start +
#: whitespace). Excludes `filters: state.filters` and
#: `filters: { ...state.filters, tab }`, which are request params.
DECLARES_FILTERS = re.compile(r"^\s*filters\s*:\s*\[", re.M)

#: `filterBarSlot={…}` as a JSX prop, or `filterBarSlot:` on a props object.
PASSES_SLOT = re.compile(r"\bfilterBarSlot\s*[:=]")

#: The frame itself, not a list screen: `tableTypes.ts` DECLARES the field and
#: `DataTable.tsx` READS the slot. Named rather than pattern-matched, exactly as
#: G43's `NOT_A_LIST_SCREEN` and G37's icon allowlist are.
NOT_A_LIST_SCREEN = {
    "components/tableTypes.ts",  # the interface `filters` is declared ON
    "components/DataTable.tsx",  # the consumer: `{props.filterBarSlot}`
    "components/FilterBar.tsx",  # the control itself
}


def _strip_comments(text: str) -> str:
    """Blank out comments, preserving offsets, LINE COMMENTS FIRST (DEF-741)."""
    text = re.sub(r"//[^\n]*", lambda m: " " * len(m.group(0)), text)
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"\S", " ", m.group(0)), text, flags=re.S)


def _sources() -> list[tuple[str, str]]:
    """Every non-test source under `src/`, comments already blanked."""
    out: list[tuple[str, str]] = []
    for path in sorted(SRC.rglob("*.ts")) + sorted(SRC.rglob("*.tsx")):
        rel = str(path.relative_to(SRC)).replace("\\", "/")
        if ".test." in path.name or rel.startswith("i18n/"):
            continue
        out.append((rel, _strip_comments(path.read_text("utf-8", errors="replace"))))
    return out


def unrendered_filters(sources: list[tuple[str, str]]) -> list[str]:
    """Files declaring MORE filter sets than they pass filter controls."""
    offenders: list[str] = []
    for rel, text in sources:
        if rel in NOT_A_LIST_SCREEN:
            continue
        declared = len(DECLARES_FILTERS.findall(text))
        rendered = len(PASSES_SLOT.findall(text))
        if declared > rendered:
            offenders.append(f"{rel} ({declared} filter set(s) declared, {rendered} rendered)")
    return offenders


def selftest() -> list[str]:
    """Shown to BITE on planted text before it is trusted on the real tree.

    A gate that has never failed has not been shown to be able to. This runs on
    every invocation, so a refactor that blinded the reader is a FAIL here
    rather than a silent green — G31's `grammar_corpus_selftest()` shape.
    """
    problems: list[str] = []

    declared_only = (
        "const config = {\n"
        "    screenId: 'S49',\n"
        "    filters: [\n"
        "      { name: 'status', label: 'Status', options: [] },\n"
        "    ],\n"
        "  }\n"
        "  return <DataTable config={config} downloadSlot={<X />} />\n"
    )
    if not unrendered_filters([("planted.tsx", declared_only)]):
        problems.append("does not bite a config that declares filters and renders none")

    both = declared_only.replace(
        "downloadSlot={<X />}", "filterBarSlot={<FilterBar />} downloadSlot={<X />}"
    )
    if unrendered_filters([("planted.tsx", both)]):
        problems.append("bites a screen that declares AND renders — false positive")

    # ⚠ THE TWO-TABLE FIXTURE. A `key in file` check passes on this and it is
    # the exact shape `SettingsRoutesCyclesTab` and `PaymentsPage` have.
    two_tables = declared_only + both
    if not unrendered_filters([("planted.tsx", two_tables)]):
        problems.append("counts per FILE, not per TABLE — a second bare table would pass")

    # Request-param plumbing is not a declaration.
    plumbing = (
        "  return {\n"
        "    filters: state.filters,\n"
        "    filters: { ...state.filters, tab },\n"
        "  }\n"
    )
    if unrendered_filters([("planted.tsx", plumbing)]):
        problems.append("reads `filters: state.filters` as a capability declaration")

    # A comment can neither trip the rule nor satisfy it.
    commented_decl = _strip_comments("// filters: [\n//   { name: 'x' },\n// ]\n")
    if unrendered_filters([("planted.tsx", commented_decl)]):
        problems.append("counts a COMMENTED filter declaration as a real one")
    commented_slot = _strip_comments(
        declared_only + "  // filterBarSlot is passed by the wrapper\n"
    )
    if not unrendered_filters([("planted.tsx", commented_slot)]):
        problems.append("accepts a COMMENTED filterBarSlot as a rendered control")

    return problems


def run() -> tuple[str, str]:
    broken = selftest()
    if broken:
        return "FAIL", "the gate's own self-test did not bite: " + "; ".join(broken)

    offenders = unrendered_filters(_sources())
    note = (
        f"BR-SHL-010: {len(offenders)} screen(s) declaring `TableConfig.filters` with no "
        f"`filterBarSlot` (baseline {UNRENDERED_BASELINE}); self-test: 6/6 clauses bite"
    )

    # ── RED PROOF ─────────────────────────────────────────────────────────
    # Run in a throwaway `git worktree` at the tree the PO photographed
    # (v2.75.0, before DEF-1701 was fixed). It names THREE files where CR-045
    # and the PO between them named two — the third had never been looked at,
    # which is the whole argument for a sweep over a walk (DEF-1702's lesson,
    # one defect earlier):
    #
    #   FAIL: BR-SHL-010: 3 screen(s) declaring `TableConfig.filters` with no
    #   `filterBarSlot` (baseline 0); self-test: 6/6 clauses bite. 3 more than
    #   the baseline of 0. A `TableConfig` that declares filters and renders no
    #   filter control is dead configuration: the capability exists in the
    #   config, the feature does not exist on screen, and every test passes
    #   because an absent control asserts nothing (hard-won law 2, DEF-1701).
    #   Pass `DataTable`'s `filterBarSlot` — `PremisesListPage` is the reference
    #   — or delete the declaration. Offender(s):
    #   features/assets/AssetRegistryPage.tsx (1 filter set(s) declared, 0 rendered),
    #   features/customers/ServiceRequestsListPage.tsx (1 filter set(s) declared, 0 rendered),
    #   features/tenancy/SettingsCustomFields.tsx (1 filter set(s) declared, 0 rendered)
    if len(offenders) > UNRENDERED_BASELINE:
        return (
            "FAIL",
            f"{note}. {len(offenders) - UNRENDERED_BASELINE} more than the baseline of "
            f"{UNRENDERED_BASELINE}. A `TableConfig` that declares filters and renders no "
            f"filter control is dead configuration: the capability exists in the config, "
            f"the feature does not exist on screen, and every test passes because an "
            f"absent control asserts nothing (hard-won law 2, DEF-1701). Pass "
            f"`DataTable`'s `filterBarSlot` — `PremisesListPage` is the reference — or "
            f"delete the declaration. Offender(s): {', '.join(offenders)}",
        )

    return "PASS", note


def main() -> int:
    """Run this gate from the command line.

    ⚠ A `run()` with no main block exits 0 with no output, which is
    indistinguishable from a pass to the eye and to `$?` (DEF-672).
    """
    status, message = run()
    print(f"{status}: {message}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
