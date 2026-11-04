#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CWP-3655 §(2) — *"a gate is owed and is mechanically easy where
#          the visual rules are not: fail a file under src/ that EXPORTS a
#          component whose name the shared kit already exports"*. The portal
#          had grown a SECOND kit — its own `Panel`, `Chip` and `PageHead`
#          beside the shared ones — and nothing in the repo could see it.
# Rules:   B14 rule 36 (compose the kit; a missing piece is ADDED to the kit,
#          not drawn on the screen that wants it) · CLAUDE.md hard-won law 5
#          (one source, never two copies that drift) · law 7 (prove a guard RED
#          first, in the harness that will run it — DEF-GOV-3733) · DEF-182 (a
#          check whose output cannot distinguish pass from fail is worse than
#          no check)
# Tests:   `selftest()` below — `run()` refuses to report until it has passed
# ───────────────────────────────────────────────────────
"""G104 — ONE DECLARATION PER COMPONENT NAME.

WHY THIS GATE EXISTS
--------------------
`DEF-CWP-3655`: the customer portal grew a second component kit. Its own
`Panel`, its own `Chip`, its own `PageHead`, one directory away from the shared
ones that already did those jobs — and every check in this repo was green over
it for days.

**Nothing could see it, and the reason is worth stating.** `tsc` cannot: each
screen imports its own and both are valid. eslint cannot: they are different
modules. A rendering check cannot: both render. `vitest` cannot: each file's
own tests pass. The two components are never in the same place at the same
time *except* in a listing of what each file declares — so that is what this
reads.

⚠ **IT COMPARES DECLARATIONS, NOT EXPORTS, AND THAT DISTINCTION IS THE WHOLE
DESIGN.** The defect row asks for a check on what a file "exports", and a
literal reading of that is wrong in a way that would have made this gate
useless. `portal/components/primitives.tsx` carries

    export { ConsequenceBox } from "@/components/ConsequenceBox";

which is the shared kit's component, re-exported under the portal kit's roof.
That is **exactly what B14 rule 36 asks for** — one implementation, composed —
and a gate that failed on it would be refusing the correct answer and would be
switched off within a week (DEF-323). So a re-export is invisible here; only a
second `export function` / `export const` / `export class` of the name counts.

⚠ **A NAME SHARED BY TWO DIFFERENT JOBS IS NOT THE SAME FAULT AS A COPY, AND
THIS GATE CANNOT TELL THEM APART.** `CustomFieldsView` names two genuinely
different components — the kit's renders a record's custom field VALUES, the
Settings screen's administers their DEFINITIONS — and their props differ, so
`tsc` would catch a wrong import. That is a naming collision, not duplication.
`WriteModeField` and `WriteModeStated` are thin wrappers that import the kit's
under an alias and delegate to it, which is composition wearing a confusing
name. Only `Panel` is a true second implementation. **So the baseline below
records a VERDICT per entry rather than a number**, because "four" would say
nothing about which of them is a defect.

THE BASELINE IS AN EXACT SET, NOT A CEILING
-------------------------------------------
Measured 2026-09-05. A collision that is not in `KNOWN` fails. An entry in
`KNOWN` that has stopped colliding ALSO fails, asking for its row to be
removed — the `surface_debt.txt` discipline, and the reason is the 871 -> 870
lesson recorded in G31: a ratchet that only counts upward reads a fix and a
regression as the same number.
"""

from __future__ import annotations

import pathlib
import re
import sys

SRC = pathlib.Path(__file__).resolve().parents[2] / "07-frontend" / "src"
KIT = SRC / "components"

#: A DECLARATION — `export function Foo`, `export const Foo`, `export class
#: Foo`. Upper-case initial, so a helper like `formatQuantity` is out of scope;
#: this gate is about components. A re-export (`export { Foo } from "…"`) does
#: not match, deliberately — see the module docstring.
_DECLARATION = re.compile(
    r"^export\s+(?:default\s+)?(?:async\s+)?(?:function|const|class)\s+([A-Z][A-Za-z0-9_]*)",
    re.M,
)

#: Every collision alive on 2026-09-05, with what it actually is. The verdict
#: matters more than the count: three of these four are not duplication.
#:
#: ⚠ **KEYED BY (NAME, FILE) AND NOT BY NAME, AND THIS GATE'S OWN RED PROOF IS
#: WHY.** The first draft keyed on the name alone. Planting a second `Panel` in
#: `portal/components/content.tsx` — the literal defect this gate is written
#: for — then reported **PASS**, because `Panel` was already baselined for
#: `settingsShared.tsx` and the name matched. A baseline keyed loosely is
#: exactly "somewhere for the next one to hide" (CLAUDE.md), and the only
#: reason it was found is that the guard was proved red before it was trusted
#: green (hard-won law 7).
KNOWN: dict[tuple[str, str], str] = {
    ("Panel", "features/tenancy/settingsShared.tsx"): (
        "features/tenancy/settingsShared.tsx declares a SECOND Panel beside "
        "components/Panel.tsx — a true duplicate, the DEF-CWP-3655 shape in the "
        "staff app. 187 files import settingsShared; folding it is a lane of its "
        "own and is filed rather than done at speed."
    ),
    ("CustomFieldsView", "features/tenancy/SettingsCustomFields.tsx"): (
        "two different components sharing a name — the kit's renders a record's "
        "custom field VALUES, features/tenancy/SettingsCustomFields.tsx "
        "administers their DEFINITIONS. Their props differ, so tsc catches a "
        "wrong import. A rename, not a fold."
    ),
    ("WriteModeField", "features/metering/readsImportRail.tsx"): (
        "features/metering/readsImportRail.tsx imports the kit's as "
        "SharedWriteModeField and delegates to it — composition under a "
        "confusing name, not a second implementation."
    ),
    ("WriteModeStated", "features/metering/readsImportRail.tsx"): (
        "as WriteModeField above — a wrapper around the kit's, imported as "
        "SharedWriteModeStated."
    ),
}


def _declarations(text: str) -> set[str]:
    return set(_DECLARATION.findall(text))


def _sources() -> list[pathlib.Path]:
    files = list(SRC.rglob("*.tsx")) + list(SRC.rglob("*.ts"))
    return sorted(f for f in files if ".test." not in f.name and ".stories." not in f.name)


def collisions() -> dict[tuple[str, str], str]:
    """(name, the file that re-declares it) -> the shared kit file that declares it.

    ⚠ EVERY site, not the first: a name declared a third time is a third
    finding, and `setdefault` on the name alone would swallow it.
    """
    kit: dict[str, str] = {}
    for path in _sources():
        if KIT not in path.parents:
            continue
        for name in _declarations(path.read_text("utf-8", errors="replace")):
            kit.setdefault(name, str(path.relative_to(SRC)))
    found: dict[tuple[str, str], str] = {}
    for path in _sources():
        if KIT in path.parents:
            continue
        where = str(path.relative_to(SRC))
        for name in _declarations(path.read_text("utf-8", errors="replace")):
            if name in kit:
                found[(name, where)] = kit[name]
    return found


def selftest() -> tuple[bool, str]:
    """Both directions, because either alone passes a sabotage the other catches."""
    caught = _declarations('export function Panel(props: {}) { return null; }')
    if "Panel" not in caught:
        return False, "a second declaration was not read as one"
    reexport = _declarations('export { ConsequenceBox } from "@/components/ConsequenceBox";')
    if reexport:
        return False, f"a RE-EXPORT was read as a declaration ({sorted(reexport)}) — rule 36's correct answer would fail"
    helper = _declarations("export const formatQuantity = (n: number) => n;")
    if helper:
        return False, "a lower-case helper was read as a component"
    return True, "a second declaration is caught, a re-export and a helper are not"


def run() -> tuple[str, str]:
    ok, how = selftest()
    if not ok:
        return "FAIL", f"self-test failed, so nothing below is trustworthy: {how}"

    found = collisions()
    new = {key: kit_file for key, kit_file in found.items() if key not in KNOWN}
    gone = sorted(f"{name} in {where}" for (name, where) in KNOWN if (name, where) not in found)

    if new:
        detail = "; ".join(
            f"{name} — declared in {kit_file} AND in {other}" for (name, other), kit_file in sorted(new.items())
        )
        return "FAIL", (
            f"{len(new)} component name(s) declared twice: {detail}. B14 rule 36 — compose the "
            f"shared kit; where it genuinely lacks a variant, ADD the piece to the kit rather "
            f"than declaring a second one beside it (DEF-CWP-3655). tsc cannot see this, because "
            f"each file imports its own. If you meant to re-use the kit's, import it — a re-export "
            f"is not a declaration and this gate ignores it."
        )
    if gone:
        return "FAIL", (
            f"{len(gone)} baselined collision(s) no longer exist ({', '.join(gone)}) — delete their "
            f"rows from KNOWN so the set keeps meaning what it says. A baseline that only counts "
            f"upward reads a fix and a regression as the same number (G31's 871 -> 870 lesson)."
        )
    return "PASS", (
        f"no component name is declared twice outside the {len(KNOWN)} recorded on 2026-09-05 "
        f"(1 true duplicate — staff Panel; 2 wrappers; 1 name shared by different jobs). "
        f"self-test: {how}"
    )


if __name__ == "__main__":
    status, detail = run()
    print(f"{status}  {detail}")
    sys.exit(0 if status == "PASS" else 1)
