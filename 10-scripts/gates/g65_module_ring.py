#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2845 (2026-08-31) — "the six-ring rule says billing never
#           imports another module and seven imports in five files do". Its
#           escape_reason is the whole reason this file exists: *"NOTHING
#           ENFORCES THE RING STRUCTURE … The structure is true by habit, so it
#           degrades one import at a time with nothing going red."*
# Rules:    B1 (the module rings) · B2 §2 (cross-module writes are forbidden;
#           cross-module FKs are the REVIEWED interface set) · CLAUDE.md module
#           map (*"Cross-module writes are forbidden"*) · hard-won law 7 (prove
#           a guard RED before trusting it green) · DEF-182 (a check whose
#           output cannot distinguish pass from fail is worse than no check)
# ───────────────────────────────────────────────────────
"""G65 — BILLING REACHES ANOTHER MODULE THROUGH A SEAM, OR THE RING IS A HABIT.

WHAT IT ASKS, IN ONE SENTENCE
-----------------------------
**Which files under `apps/billing` import another module directly**, and is that
set the one we already knew about — or has it grown since anybody looked?

WHY THAT IS A GATE AND NOT A CODE REVIEW
----------------------------------------
`G20` checks a seam has an implementer and `G27` checks a module is not
invisible. **Neither asks whether the seam was BYPASSED.** So the ring structure
holds only for as long as everybody remembers it, and it degrades one import at
a time — every individual import looks reasonable, no test fails, and the
architecture is gone six months later with no commit anybody could point at.

**The sharpest of them is `selectors.py`, and it is worth naming.** The READ
RING is the layer two screens share, so a disagreement there is a disagreement
between screens — not between a screen and a background pass.

⚠ **MEASURED BEFORE IT WAS BUILT, AND THE MEASUREMENT IS THE POINT.** `DEF-2845`
counted **seven imports in five files** on 2026-08-31. One day later there are
**more, in eight files** — `print_api.py`, `print_set.py` and
`resolution_shadow.py` joined in between. Three new ring breaks in a day, with
nothing going red, is exactly the drift the row predicted, and it is why the
baseline is a RATCHET rather than a target: **it may fall and never rise** (the
2026-08-27 ruling on gate families — *"a baseline that may fall and never rise
is a ratchet; a baseline nobody can reach is decoration"*).

⚠ **IT IS KEYED BY SUBMODULE, NOT BY MODULE, AND THAT IS A CORRECTION THIS GATE
MADE TO ITSELF ON ITS FIRST RUN.** The first draft recorded `<file>::<module>`
and immediately flagged the very commit that added it — `apps/billing/exports.py`
importing `apps/tenancy/exports.py`. Reading that as *billing bypassed a tenancy
seam* would have been wrong, and baselining it would have been worse: it would
have put a legitimate registration into a list whose header says every line is a
seam that has not yet been routed.

**`apps.tenancy.exports` IS A PLATFORM FACILITY THAT HAPPENS TO LIVE IN THE
TENANCY APP.** It is the export REGISTRY, and its own published contract is an
invitation to exactly this import — *"Owner modules call this from
AppConfig.ready()"*. **Measured across the whole backend: SEVEN of the twelve
modules import it** (assets, audit, billing, metering, rating, reports, and
tenancy itself). A gate that called that an architecture violation would be
wrong about the architecture, and the honest reading is that the kernel belongs
in `core/` — the shared floor every module stands on — and its home is a naming
accident. So it is exempt BY NAME, in `PLATFORM_FACILITIES`, with that reasoning
attached rather than as a quiet skip.

**NOTHING ELSE IN `apps.tenancy` IS EXEMPT**, and two candidates were considered
and refused: `tenancy.document_storage` (3 modules) and `tenancy.document_store`
(2 modules). Two or three importers is not evidence of a platform facility; it is
what a seam question looks like before anybody has answered it. They stay in the
baseline so somebody does.

WHAT IS DELIBERATELY NOT A FINDING
----------------------------------
* **`*_seam.py`** — the seam files ARE the sanctioned boundary. `DEF-2845`'s own
  prevention says *"outside the seam files"*, and a gate that flagged the seam
  for doing its job would be pointing at the fix. **Measured today: not one seam
  file imports another module at all** — they resolve their counterparts by NAME
  through `gather._resolve` — so nothing is being excused here; the exemption is
  for the day a seam legitimately needs the import.
* **`apps.billing` itself**, and any non-`apps` import. This gate is about the
  ring, not about imports.

WHAT IT CANNOT SEE, STATED SO NOBODY READS A PASS AS MORE THAN IT IS
--------------------------------------------------------------------
A late import resolved by STRING — `import_module("apps.rating.resolution")`, of
which this codebase has several deliberate ones — is not an `import` statement
and does not appear here. That is not an oversight to fix by grepping for the
string: `resolution_switch` resolves rating by name ON PURPOSE, and a gate that
refused it would be refusing the cutover's own design. What this gate holds is
the STATIC import graph, which is the half that drifts by habit.

    python3 10-scripts/gates/g65_module_ring.py
"""

from __future__ import annotations

import ast
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
BILLING = REPO / "06-backend" / "apps" / "billing"
BASELINE = pathlib.Path(__file__).with_name("g65_module_ring_baseline.txt")

#: The other modules of the map. `billing` is absent for the obvious reason and
#: `core` is absent because it is the shared floor every module stands on, not a
#: module in the ring.
OTHER_MODULES: frozenset[str] = frozenset(
    {
        "tenancy",
        "identity",
        "metering",
        "rating",
        "payments",
        "ledger",
        "customers",
        "notifications",
        "audit",
        "assets",
        "reports",
        "integrations",
    }
)

#: Platform facilities that live inside a module's package and are NOT that
#: module's data. Exempt BY NAME with the evidence, never by pattern — the whole
#: value of this gate is that an exemption is a decision somebody wrote down.
#:
#: `tenancy.exports` is the platform's export REGISTRY. Its own contract invites
#: this import (*"Owner modules call this from AppConfig.ready()"*) and SEVEN of
#: the twelve modules take it up. It belongs in `core/`; that it does not is a
#: naming accident, and a gate that called it a violation would be wrong about
#: the architecture rather than strict about it.
PLATFORM_FACILITIES: frozenset[str] = frozenset({"tenancy.exports"})


def _imported_targets(path: pathlib.Path) -> set[str]:
    """Every `<other module>.<submodule>` this file imports, statically.

    Both statement forms, because `import apps.rating.selectors` and
    `from apps.rating import selectors` are the same ring break written twice —
    a check that read only `ImportFrom` would pass over half of them. A bare
    `from apps.rating import models, selectors` names its submodules in the
    ALIASES rather than in the module path, so those are read too; otherwise the
    commonest form in this codebase would collapse to a module name and the
    submodule granularity would be lost exactly where it matters.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as broken:  # pragma: no cover
        raise SystemExit(f"G65 cannot parse {path}: {broken}") from broken

    found: set[str] = set()
    for node in ast.walk(tree):
        entries: list[tuple[str, list[str]]] = []
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            entries.append((node.module, [alias.name for alias in node.names]))
        elif isinstance(node, ast.Import):
            entries.extend((alias.name, []) for alias in node.names)
        for module, aliases in entries:
            parts = module.split(".")
            if len(parts) < 2 or parts[0] != "apps" or parts[1] not in OTHER_MODULES:
                continue
            if len(parts) >= 3:
                found.add(f"{parts[1]}.{parts[2]}")
            else:
                # `from apps.rating import models` — the submodule is the alias.
                # `*` for a bare `import apps.rating`, which names none.
                for alias in aliases or ["*"]:
                    found.add(f"{parts[1]}.{alias}")
    return found


def current() -> set[str]:
    """`{"<path relative to the repo>::<module>.<submodule>"}` for every ring
    break today.

    ⚠ **NO LINE NUMBERS, DELIBERATELY.** A baseline keyed by line churns on every
    edit above it, and a baseline that has to be regenerated to stay green is a
    baseline nobody reads. What is pinned is *this file reaches that submodule*,
    which is the fact the ring rule is about.
    """
    pairs: set[str] = set()
    for path in sorted(BILLING.rglob("*.py")):
        if path.name.endswith("_seam.py"):
            continue
        relative = path.relative_to(REPO).as_posix()
        for target in _imported_targets(path):
            if target in PLATFORM_FACILITIES:
                continue
            pairs.add(f"{relative}::{target}")
    return pairs


def baselined() -> set[str]:
    if not BASELINE.exists():
        return set()
    return {
        line.strip()
        for line in BASELINE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def run() -> tuple[str, str]:
    """`(status, detail)` for `run_gates.py`.

    Both entry points on purpose — `DEF-672` (gates with `run()` and no `main()`,
    exiting 0 with no output when run directly) and `DEF-674` (a gate with
    `main()` and no `run()`, crashing inside the suite for weeks) are one
    convention with two halves. `main()` delegates here so they cannot disagree.
    """
    now = current()
    known = baselined()
    new = sorted(now - known)
    gone = sorted(known - now)

    if new:
        listed = " · ".join(new[:6]) + (f" (+{len(new) - 6} more)" if len(new) > 6 else "")
        return (
            "FAIL",
            f"{len(new)} NEW cross-module import(s) in apps/billing outside the seam "
            f"files: {listed}. B1's rings say billing reaches another module through a "
            "SEAM; a direct import is the seam bypassed, and the read ring is where two "
            "screens then disagree (DEF-2845). Either route it through a seam, or — if "
            "it is a PLATFORM FACILITY rather than that module's data — name it in "
            "PLATFORM_FACILITIES with the evidence, or add it to "
            "g65_module_ring_baseline.txt with the reason, so the next reader meets a "
            "decision rather than a habit."
        )

    detail = (
        f"{len(now)} cross-module import(s) in apps/billing, all baselined "
        f"(baseline holds {len(known)}; the number may fall, never rise); "
        f"{len(PLATFORM_FACILITIES)} platform facility(ies) exempt by name"
    )
    if gone:
        detail += (
            f"; {len(gone)} baselined import(s) are gone — delete them from "
            f"g65_module_ring_baseline.txt to hold the gain: {' · '.join(gone)}"
        )
    return "PASS", detail


def main() -> int:
    status, note = run()
    print(f"G65 {status} — {note}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
