// ── Trace ──────────────────────────────────────────────
// Change:  PO ruling 2026-09-10, asked whether the unit plan picker should
//          filter to the unit's services as the blueprint's frame claims it
//          does — verbatim: *"not required; you should show all plan or allow
//          user to do in-line search it and choose."*
// Rules:   BR-SHL-033 (a long list is a type-to-filter control) · B14 rule 8
//          (5+ options are searchable)
// Screens: S16 Add units · U10 Edit a unit
// ───────────────────────────────────────────────────────
// ⚠ **THE RULING HAS TWO HALVES AND ONLY ONE OF THEM WAS TRUE.**
//
// *Show all plans* was already the case — `getUnitPlanOptions` is not
// premises-scoped, so the frame's claim that the list is filtered to the unit's
// services was never built. That half needed no change and now must not be
// "fixed": a clerk who cannot find the plan they were told to use has no way to
// tell a filtered-out plan from a plan that does not exist, which is the
// indistinguishable-absence defect `DEF-MET-4758` was filed for.
//
// *Or let them search it* was NOT the case. The unit EDIT form has used
// `SearchSelectField` for this field all along; the ADD form used a plain
// `SelectField`, so one product asked one question two ways and the longer the
// tenant's plan list grew the worse the add form got.
//
// ⚠ **THIS READS SOURCE, AND SAYS SO.** Both files mount in different frames
// with different fixtures, and the claim under test is *the same control on
// both screens* — which is a fact about the two files, not about one render.
// It cannot tell you the picker LOOKS right; nothing in this repo can (law 6),
// which is why the ruling was also walked in a browser.
import { describe, expect, it } from "vitest";

import ADD_SOURCE from "./AddUnitsWizard.tsx?raw";
import EDIT_SOURCE from "./UnitEditModal.tsx?raw";

/** The component rendering the field with this `id`, in file order. */
function controlFor(source: string, id: string): string | null {
  const at = source.indexOf(`id="${id}"`);
  if (at === -1) return null;
  const before = source.slice(0, at);
  const open = before.lastIndexOf("<");
  return before.slice(open + 1).trim().split(/\s/)[0] || null;
}

describe("PO 2026-09-10 — the unit plan picker shows every plan and lets you type", () => {
  it("BOTH screens use the searchable control for the plan", () => {
    // ⚠ Spelled out per screen rather than compared to each other: two files
    // that agree on the WRONG control would pass an equality check, which is a
    // check that cannot fail for the reason it exists (hard-won law 7).
    expect(controlFor(ADD_SOURCE, "plan_id")).toBe("SearchSelectField");
    expect(controlFor(EDIT_SOURCE, "tariff_id")).toBe("SearchSelectField");
  });

  it("the plan list is NOT narrowed to the unit's services, deliberately", () => {
    // The frame claims it is. The PO ruled it is not required, so a lane that
    // "fixes" this later against the drawing is reversing a ruling — this case
    // is what tells them so.
    const call = ADD_SOURCE.match(/getUnitPlanOptions\([^)]*\)/) ?? [];
    const editCall = EDIT_SOURCE.match(/getUnitPlanOptions\([^)]*\)/) ?? [];
    for (const found of [call[0], editCall[0]]) {
      expect(found, "the plan options call moved or vanished").toBeTruthy();
      expect(found).not.toMatch(/premises|premise_id|service/);
    }
  });
});
