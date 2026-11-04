// ── Trace ──────────────────────────────────────────────
// Change:  PO on the live product at 2.234.17, looking at Add units → Details:
//          *"Search premises … search does not work"* and, of the plan box,
//          *"it should say - search by inside the box it does not say anything"*.
// Rules:   B14 rule 32 (a row never repeats what its own control offers) ·
//          B14 rule 37 (a drawn value is an illustration) · BR-SHL-033
// Screens: S16 · PRM-07 Add units → Details
// ───────────────────────────────────────────────────────
// ⚠ **TWO REPORTS, THREE FAULTS, AND ONLY ONE OF THEM WAS THE SEARCH.**
//
// 1 · The building box said `Any premise` — the units LIST FILTER's string,
//     borrowed. On a filter that is correct and means *no filter applied*; on a
//     box you must type into it says nothing about typing.
// 2 · Its help promised *"By address, property number or parcel"* and the
//     option labels held only the address and the number, so **a clerk typing a
//     parcel got `No matching options` and always would have**. That is the
//     report *search does not work*, and it was a written promise the control
//     could not keep — not a slow search and not a wrong result, a permanent
//     silent nothing.
// 3 · The plan box said `Set the plan when somebody moves in` — a sentence
//     about leaving it BLANK, on a box you type into, duplicated word for word
//     by the control directly beneath it.
//
// ⚠ **THE PARCEL IS SEARCHABLE AND STILL NOT DRAWN.** Widening the label was
// the wrong fix — the frame draws it as a street address, and a deed reference
// in front of every clerk to serve a minority of searches is a worse screen.
import { describe, expect, it } from "vitest";

import { filterOptions } from "@/components/FormModal";
import { premisesPickerOptions } from "@/features/metering/UnitsListPage";
import type { PremisesRow } from "@/api/endpoints";
import EN from "@/i18n/locales/en.json";
import SOURCE from "@/features/metering/AddUnitsWizard.tsx?raw";

function row(over: Partial<PremisesRow> = {}): PremisesRow {
  return {
    id: "p-1", premise_no: "P-00080", name: null,
    address_line: "412 Cypress Row", city: "Silver Creek", state: "TX",
    postal_code: "78611", premises_type: "apartment", premises_type_name: "Apartment complex",
    services_available: [], owner_manager: "Creekside Holdings LP", external_ref: "R-114-0082-004",
    status: "active", units: 4, ...over,
  } as PremisesRow;
}

describe("DEF-MET-4804 — the building picker keeps the promise its help made", () => {
  const options = premisesPickerOptions([row(), row({ id: "p-2", premise_no: "P-00081", address_line: "9 Elm St", external_ref: "R-200-0001-000", owner_manager: null, city: "Katy" })]);

  it("searches by ADDRESS", () => {
    expect(filterOptions(options, "cypress").map((o) => o.value)).toEqual(["p-1"]);
  });

  it("searches by PROPERTY NUMBER", () => {
    expect(filterOptions(options, "P-00081").map((o) => o.value)).toEqual(["p-2"]);
  });

  it("searches by PARCEL — the leg that never worked", () => {
    // ⚠ RED before this fix: the label carried no parcel, so this returned []
    // for every parcel a clerk could type, on a control whose own help line
    // told them to type one.
    expect(filterOptions(options, "R-114-0082").map((o) => o.value)).toEqual(["p-1"]);
  });

  it("does NOT draw the parcel it searches on", () => {
    // The frame draws `412 Cypress Row`. Searchable text and readable text are
    // two different jobs and this is the case that keeps them apart.
    expect(options[0].label).toBe("412 Cypress Row · P-00080");
    expect(options[0].label).not.toContain("R-114-0082-004");
  });
});

describe("DEF-MET-4804 — both boxes say what you may type into them", () => {
  const en = EN as Record<string, string>;

  it("the building box invites a search instead of describing a filter", () => {
    expect(en["metering.addUnits.building.placeholder"]).toBe(
      "Search by address, number or parcel",
    );
    expect(SOURCE).toContain('placeholder={t("metering.addUnits.building.placeholder")}');
    // The old string is the units LIST's and must not come back here.
    expect(SOURCE).not.toContain('placeholder={t("metering.units.filter.premisePlaceholder")}');
  });

  it("the plan box invites a search instead of describing blankness", () => {
    expect(en["metering.addUnits.plan.placeholder"]).toBe("Search plans");
    expect(SOURCE).toContain('placeholder={t("metering.addUnits.plan.placeholder")}');
  });

  it("the building row no longer says the same thing twice", () => {
    // B14 rule 32. The help read "By address, property number or parcel." and
    // the placeholder now says it, in the box, where a clerk is looking.
    expect(SOURCE).not.toContain('help={t("metering.addUnits.building.searchHelp")}');
  });
});
