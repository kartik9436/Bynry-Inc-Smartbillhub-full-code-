# ── Trace ──────────────────────────────────────────────
# Change:   CR-101-BRC03 — Fix a bill becomes the four-step wizard the Product
#           Owner ruled on 2026-09-12 (*"we will ahve to make it wizard - 4 steps"*).
# Rules:    BR-BIL-044 (*"nine sections, all required, none collapsible away"*) ·
#           CLAUDE.md hard-won law 2 (built is not wired) and law 7 (a check
#           must be able to fail, and you must be able to describe a false pass)
# ───────────────────────────────────────────────────────
"""The four-step rail deals BR-BIL-044's nine sections out; it does not drop any.

⚠ **WHY THIS GUARD IS ON THE PYTHON SIDE AND READS A `.tsx` FILE AS TEXT.**

The wizard splits the nine preview sections across steps 2, 3 and 4. The one
thing that must stay true is that **the union of those three lists is exactly
`single_correction.PREVIEW_SECTIONS`** — no section in two steps, and none in
none. A section belonging to no step would vanish from the approval artifact
with `tsc`, eslint, every vitest suite and every gate still green, which is
precisely the partial-artifact failure BR-BIL-044 exists to forbid.

A TypeScript test could only assert the frontend against *a copy of the nine
written in TypeScript*, and a list restated in a test agrees with itself
forever — the same reason `FixABillReasonWords.test.ts` derives the thirteen
reasons from the server's map instead of restating them. So the assertion is
made where the AUTHORITY lives: this file imports `PREVIEW_SECTIONS` and parses
the three lists out of the screen's own source.

**What would make this pass wrongly** (law 7's second habit): if the regex
matched nothing, `dealt` would be empty and the equality would fail — so the
failure mode is red, not a false green. The explicit `assert len(...) == 3`
below is there anyway, because a check that silently measures an empty set is
the shape this repository fails in most often.
"""

from __future__ import annotations

import re
from pathlib import Path

from apps.billing import single_correction

SCREEN = (
    Path(__file__).resolve().parents[2]
    / "07-frontend"
    / "src"
    / "features"
    / "billing"
    / "fixABillContract.ts"
)
# ⚠ The four ids and the three section lists moved from `FixABillTab.tsx` into
# the CONTRACT on 2026-09-15 (`CR-101-BRC03` lane A) — declared once, where the
# lanes building steps 2–4 read them. This guard follows the declaration.

#: The three constants the rail passes to `NineSections`' `only` prop.
STEP_CONSTANTS = ("STEP2_SECTIONS", "STEP3_SECTIONS", "STEP4_SECTIONS")


def _sections_declared(source: str, name: str) -> list[str]:
    """The string literals inside `export const <name> = [ … ] as const;`."""
    match = re.search(
        rf"export const {name} = \[(.*?)\] as const;", source, flags=re.S
    )
    assert match is not None, f"{name} is not declared in {SCREEN.name}"
    return re.findall(r'"([a-z_]+)"', match.group(1))


def test_the_rail_deals_every_one_of_the_nine_and_none_twice() -> None:
    source = SCREEN.read_text(encoding="utf-8")
    per_step = [_sections_declared(source, name) for name in STEP_CONSTANTS]
    assert len(per_step) == 3, "the rail has three section-bearing steps"

    dealt: list[str] = [name for step in per_step for name in step]
    server = [name for _, name in single_correction.PREVIEW_SECTIONS]

    # Nothing dealt twice — a section on two steps reads as two different facts.
    assert len(dealt) == len(set(dealt)), f"a section is dealt to two steps: {dealt}"

    # Nothing dropped, nothing invented.
    assert set(dealt) == set(server), (
        "the wizard's steps and BR-BIL-044's nine have diverged — "
        f"only on a step: {sorted(set(dealt) - set(server))}; "
        f"on no step at all: {sorted(set(server) - set(dealt))}"
    )
    assert len(dealt) == len(server) == 9


def test_the_rail_declares_exactly_four_steps() -> None:
    """The ruling is FOUR. A fifth or a third is the thing that must go red."""
    source = SCREEN.read_text(encoding="utf-8")
    match = re.search(
        r"export const FIX_A_BILL_STEPS = \[(.*?)\] as const;", source, flags=re.S
    )
    assert match is not None, "FIX_A_BILL_STEPS is not declared"
    step_ids = re.findall(r'\{ id: "([a-z-]+)"', match.group(1))
    assert len(step_ids) == 4, f"the rail declares {len(step_ids)} steps; the ruling is four"
    assert len(set(step_ids)) == 4, f"two steps share an id: {step_ids}"


def test_every_step_label_is_a_catalogue_key_present_in_all_eleven() -> None:
    """A missing key reaches a clerk as SILENCE — an unnamed step on the rail.

    The skill file's §7.3, and `DEF-BIL-5233`'s own mechanism one screen over:
    `billing.fix.reason.*` held zero keys in all eleven catalogues and the
    `defaultValue` fallback rendered the enum code instead, in every language,
    for four weeks.
    """
    import json

    source = SCREEN.read_text(encoding="utf-8")
    match = re.search(
        r"export const FIX_A_BILL_STEPS = \[(.*?)\] as const;", source, flags=re.S
    )
    assert match is not None
    label_keys = re.findall(r'labelKey: "([\w.]+)"', match.group(1))
    assert len(label_keys) == 4, label_keys

    locales = SCREEN.parents[2] / "i18n" / "locales"
    files = sorted(locales.glob("*.json"))
    assert len(files) == 11, f"expected eleven catalogues, found {len(files)}"
    for path in files:
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        missing = [key for key in label_keys if key not in catalogue]
        assert not missing, f"{path.name} is missing {missing}"
