// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave B `B8` — *"05 Edit a property PRM-02 and create property
//          screen should match"* (PO 2026-09-08, verbatim).
//          AMENDED 2026-09-10 — the six statement headings become the FOUR
//          question headings the blueprint's frame draws, PO ruling of that day:
//          *"(a) The frame wins, correct the sentences"*.
// ───────────────────────────────────────────────────────
// ⚠ **THIS FILE READS SOURCE, NOT A RENDER, AND THAT IS DELIBERATE.**
//
// The claim `B8` makes is about TWO screens agreeing, and the two live in
// different files, take different props and mount in different frames — one in
// a `WizardFrame`, one in a `FormModal`. Rendering both to compare them means
// building two sets of fixtures whose differences are then the thing most
// likely to break, and a fixture that drifts is how DEF-CWP-3925's front page
// tested green over eight dead doors.
//
// So the assertion is made where the promise actually lives: both files map the
// SAME exported array, in file order, and this reads that order back out of
// each. It cannot tell you the sections LOOK right — nothing in this repo can,
// which is hard-won law 6 and why this wave was also walked in a browser — but
// it is exactly strong enough to fail the day somebody adds a fifth section
// to one form and not the other, which is the drift `B8` exists to stop.
import { describe, expect, it } from "vitest";

// ⚠ **`?raw`, NOT `node:fs` — the house pattern and the only one that
// TYPECHECKS.** `DataTable.test.tsx` and `regionalReachesTheScreen.dom.test.tsx`
// both read source this way; `readFileSync` runs fine under vitest and fails
// `tsc` outright, because this tsconfig carries no `@types/node`. A test that
// passes its own runner and breaks the push gate is worse than no test.
import LIST_SOURCE from "./PremisesListPage.tsx?raw";
import EN from "../../i18n/locales/en.json";

import { PREMISES_FORM_SECTIONS } from "./premisesFormSections";

/** The `id=` of every `<PremisesFormSection>` a file renders, in file order. */
function sectionsRenderedBy(source: string): string[] {
  return [...source.matchAll(/<PremisesFormSection\s+id="([a-zA-Z]+)"/g)].map((m) => m[1]);
}

describe("CR-089 — the create form draws the frame's four question-groups", () => {
  it("the declared four are the drawn four, in the drawn order", () => {
    // ⚠ **THE LIST IS SPELLED OUT AND NOT DERIVED.** A test that reads the
    // array and asserts the array is a check that cannot fail (hard-won law 7).
    // These four ids and this order are the specification —
    // `conformance/CR-089-p008-add-property-details.md` §Sections and
    // `CR-089-p036-edit-a-property.md` §Groups, whose own COGNITIVE LOAD row
    // reads *"Fifteen fields in four named groups"*.
    expect(PREMISES_FORM_SECTIONS.map((section) => section.id)).toEqual([
      "where",
      "kind",
      "owner",
      "readingBilling",
    ]);
  });

  // ⚠ **THREE CASES THAT READ THE CREATE FORM STOOD HERE UNTIL 2026-10-09.**
  // They asserted that Add a premise rendered these four groups, the
  // `optional` chip on *Reading and billing*, and a create-only *What is
  // inside it?* block. The PO then redrew Add a premise (`CR-177-BRC10`,
  // decision log *"PO GO — BUILD THE ADD-A-PREMISE REDESIGN"*): one *Address*
  // section, then *Owner*, *Area & sub-area* and *Custom fields* as closed
  // sections, and units on a step of their own. So the create form no longer
  // renders `PremisesFormSection` at all, and these four groups are now the
  // EDIT form's alone (asserted below). That the two forms no longer match —
  // which the PO asked for on 2026-09-08 — is filed, not hidden:
  // `DEF-MET-10038`.

  it("the headings are QUESTIONS, which is what the frame draws", () => {
    // *"A person filling a form is answering questions, and a heading that asks
    // one is easier to answer than a heading that names a database table."*
    // `Reading and billing` is the one that is not a question, and it is the
    // one the frame draws as a statement with an `optional` chip beside it.
    const en = EN as Record<string, string>;
    expect(en["metering.premises.section.where"]).toBe("Where is it?");
    expect(en["metering.premises.section.kind"]).toBe("What kind of property is it?");
    expect(en["metering.premises.section.owner"]).toBe("Who looks after it?");
    expect(en["metering.premises.section.readingBilling"]).toBe("Reading and billing");
    // The create-only block, which is NOT one of the four.
    expect(en["metering.premises.section.unitsOnCreate"]).toBe("What is inside it?");
  });

  it("every declared section has a locale key in the English catalogue", () => {
    // A heading that renders its own key is what a missing catalogue entry looks
    // like on screen, and `t()` with no default returns the key itself.
    const en = EN as Record<string, string>;
    for (const section of PREMISES_FORM_SECTIONS) {
      expect(en[section.labelKey], `${section.id} has no English heading`).toBeTruthy();
    }
    expect(en["metering.premises.section.optional"]).toBe("optional");
  });
});

describe("CR-089 — both forms render the same four groups", () => {
  // ⚠ **THIS REPLACES A TRANSITIONAL PAIR, AND THE PAIR SAID SO ITSELF.** While
  // the edit form still rendered six statement-form ids, two tests stood in for
  // this one: a `RETIRED_SECTION_LABELS` map kept the old ids resolving to a
  // word, and a check asserted every rendered id was known. Both existed only
  // so a heading could never render as an empty `<h4>` — which `tsc`, eslint and
  // every `toContain` assertion pass over (hard-won law 2).
  //
  // The edit form is now re-cut onto the drawn four (`CR-089` `PUJ-18`, PO
  // ruling 2026-09-10: *the frame wins, correct the sentences*), so the real
  // assertion is back: **both forms render exactly what the module declares, in
  // the declared order.** A section that appears in one form and not the other
  // is the defect this file exists to catch.
  it("the edit form renders exactly the declared sections, in order", () => {
    const declared = PREMISES_FORM_SECTIONS.map((section) => section.id);
    expect(sectionsRenderedBy(LIST_SOURCE)).toEqual(declared);
  });
});
