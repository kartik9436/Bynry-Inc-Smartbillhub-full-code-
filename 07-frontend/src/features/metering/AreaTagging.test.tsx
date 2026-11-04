// ── Trace ──────────────────────────────────────────────
// Change:  CR-006 (PO ruling 2026-08-17) — *"when we add premises you should
//          allow to select areas and sub areas on premises"*
//          Screens: S16 (add premises) · S14 (edit premises) · S8 (Areas &
//          sub-areas) · r10 SET-06.2 (the picker the tags feed)
// Defects: DEF-220 (no screen could tag a premises, so the area filter could
//          only ever return zero rows) · DEF-221 (no screen could create a
//          sub-area, on a card literally named "Areas & sub-areas")
// Rules:   BR-MET-071 (premises carry an area) · BR-MET-066b (exactly two
//          levels) · BR-MET-083 (tagging is the cascade's entry point) ·
//          BR-TEN-034 (deactivated rows stop being offerable) ·
//          BR-TEN-031 (the OWNING module validates; the screen never re-states
//          a rule the server enforces)
// ───────────────────────────────────────────────────────
// THE POINT OF THIS FILE IS HARD-WON LAW 2: **built is not wired.** Two
// controls existed in spirit for a day — `premises.area_id` was a column with
// no write path and `areas.parent_id` was a column with no screen — and every
// test passed the whole time, because a test that never renders the form cannot
// notice that the form has no field in it.
//
// So the assertions here are deliberately about RENDERED OUTPUT: the two
// selects appear on the add wizard, they carry the tenant's own option list, the
// edit modal re-opens on the right LEVEL, and the reference-data editor draws a
// Parent control. The pure helpers are tested too, but they are the cheap half.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { LookupCard, LookupEntry, Paginated } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { ReferenceDataTab, parentOptionsFor, parentText } from "../tenancy/SettingsReferenceData";
import { referenceCard } from "../tenancy/referenceDataConfig";
import {
  NO_AREA,
  areaPayloadCode,
  areaSelectionFrom,
  subAreasOf,
  topLevelAreas,
} from "./meteringShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const TEST_TENANT = "brazosbend";

function area(code: string, name: string, over: Partial<LookupEntry> = {}): LookupEntry {
  return {
    id: `a-${code}`,
    code,
    name,
    active: true,
    is_system: false,
    used_by: 0,
    parent_code: null,
    parent_name: null,
    is_sub_area: false,
    ...over,
  };
}

/** A sub-area exactly as `AreaLookupHandler.serialize` sends one. */
function subArea(code: string, name: string, parent: LookupEntry): LookupEntry {
  return area(code, name, {
    parent_code: parent.code,
    parent_name: parent.name,
    is_sub_area: true,
  });
}

const SOUTH = area("SOUTH", "South district");
const NORTH = area("NORTH", "North district");
const RETIRED = area("OLDTOWN", "Old town", { active: false });
const SOUTH_EAST = subArea("S-SE", "South East", SOUTH);
const SOUTH_WEST = subArea("S-SW", "South West", SOUTH);
const AREAS: LookupEntry[] = [SOUTH, NORTH, RETIRED, SOUTH_EAST, SOUTH_WEST];

function paged<T>(results: T[]): Paginated<T> {
  return { count: results.length, next: null, previous: null, results };
}

// ── The pure half ──────────────────────────────────────────────────────────

describe("BR-MET-071 — two controls, ONE stored column", () => {
  it("posts the SUB-AREA when one is chosen, and the area when one is not", () => {
    // A premises tagged to a sub-area is by construction inside its parent, so
    // one column answers both levels of BR-MET-072's filter. The sub-area is
    // therefore the more specific fact and the one that gets stored.
    expect(areaPayloadCode({ top: "SOUTH", sub: "S-SE" })).toBe("S-SE");
    expect(areaPayloadCode({ top: "SOUTH", sub: "" })).toBe("SOUTH");
    expect(areaPayloadCode(NO_AREA)).toBe("");
  });

  it("re-opens a SUB-AREA in the sub-area box, not the area box", () => {
    // THE REASON `area_parent_code` IS ON THE WIRE. A bare code cannot say
    // which box it belongs in, and a form that guessed would show "South East"
    // in the Area dropdown and then post `S-SE` as a top-level area — or worse,
    // show its parent and silently re-tag the premises on the next save.
    expect(areaSelectionFrom({ area_code: "S-SE", area_parent_code: "SOUTH" })).toEqual({
      top: "SOUTH",
      sub: "S-SE",
    });
    expect(areaSelectionFrom({ area_code: "SOUTH", area_parent_code: null })).toEqual({
      top: "SOUTH",
      sub: "",
    });
    expect(areaSelectionFrom({ area_code: null, area_parent_code: null })).toEqual(NO_AREA);
  });

  it("offers only ACTIVE top-level rows as areas, and only that area's children as sub-areas", () => {
    // BR-TEN-034: a retired district stops appearing on new work while the
    // premises already tagged to it keep their tag.
    expect(topLevelAreas(AREAS).map((row) => row.code)).toEqual(["SOUTH", "NORTH"]);
    expect(subAreasOf(AREAS, "SOUTH").map((row) => row.code)).toEqual(["S-SE", "S-SW"]);
    expect(subAreasOf(AREAS, "NORTH")).toEqual([]);
    expect(subAreasOf(AREAS, "")).toEqual([]);
  });
});

describe("BR-MET-066b — the reference-data list's own two levels", () => {
  it("names the parent on a sub-area row and an em dash on a top-level one", () => {
    expect(parentText(SOUTH_EAST)).toBe("South district");
    expect(parentText(SOUTH)).toBe("—");
  });

  it("never offers a sub-area, an inactive row, or the row being edited as a parent", () => {
    // Each of the three is a choice the SERVER refuses by name
    // (`settings.areas.parent_is_sub_area`, `settings.areas.parent_self`), and
    // a dropdown that offers a certain refusal is a control that lies. Depth
    // stays enforced in ONE place — this only stops the screen suggesting it.
    expect(parentOptionsFor(AREAS, null).map((row) => row.code)).toEqual(["SOUTH", "NORTH"]);
    expect(parentOptionsFor(AREAS, SOUTH.id).map((row) => row.code)).toEqual(["NORTH"]);
  });
});

// ── The rendered half — hard-won law 2 ─────────────────────────────────────
//
// ⚠ **MOVED 2026-10-09 (`CR-177-BRC10`).** The S16 cases that stood here
// mounted the old four-mode wizard on its step 2. Add a premise is redesigned
// and its Area and Sub-area now sit in a closed *Area & sub-area* section; the
// same three assertions — both controls drawn, only the tenant's ACTIVE areas
// offered, and the empty Sub-area box saying what it waits for (*Choose an
// area first*) — are made against the new page in
// `addPremise/AddPremisePage.dom.test.tsx` ("Area & sub-area: two levels").

// ── S8 — the card that was named after a feature it did not have ───────────

function renderAreasCard(): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const cards: LookupCard[] = [{ list: "areas", owner: "metering", count: AREAS.length, state: "seeded" }];
  queryClient.setQueryData(queryKeys.lookupCards, cards);
  queryClient.setQueryData(queryKeys.lookupEntries("areas", "", 1, 50), paged(AREAS));
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/settings/reference?list=areas`]}>
          <ReferenceDataTab readOnly={false} dateFormat="MM/DD/YYYY" />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("S8 Areas & sub-areas — DEF-221", () => {
  it("declares the areas card as a self-parented list, with its own two nouns", () => {
    // A flag, not a sniff of the payload: a hierarchy is a ruling about one
    // list (BR-MET-066b), the same reason `serviceScoped` is a flag.
    // DEF-TEN-4478: the flag became the block that names this list's two
    // levels ("Area" / "Sub-area"), so it is asserted as declared, not as true.
    //
    // ⚠ THIS TEST WAS CALLED "the ONE hierarchical list" UNTIL 2026-09-07 AND
    // IS NO LONGER — `work_order_types` is the second (`BR-WRK-058`). The
    // assertions never checked the "one" and would have gone on passing while
    // their own name became false, which is the shape hard-won law 7 calls a
    // test named after an assertion it does not make.
    expect(referenceCard("areas")?.hierarchical).toBeDefined();
    expect(referenceCard("uoms")?.hierarchical).toBeUndefined();
  });

  it("shows which rows are sub-areas, and of what", () => {
    const html = renderAreasCard();
    expect(html).toContain(t("settings.reference.col.parent"));
    expect(html).toContain("South East");
  });
});

// ── r10 SET-06.2 — the dead branch, alive ──────────────────────────────────

describe("the route picker's Parent · Child label", () => {
  it("can now be produced at all, because a sub-area can now exist", () => {
    // `RoutesCyclesWizards.tsx` has rendered
    // `parent_name ? "${parent_name} · ${name}" : name` in TWO dropdowns since
    // CR-006, and NOTHING in the product could produce a `parent_name` — a dead
    // branch invisible to the unwired-prop gate, because that gate reads props
    // and this was data. This asserts the data shape the branch needs, which is
    // what the reference-data editor now sends and the handler now returns.
    const label = (row: LookupEntry): string =>
      row.parent_name ? `${String(row.parent_name)} · ${row.name}` : row.name;
    expect(label(SOUTH)).toBe("South district");
    expect(label(SOUTH_EAST)).toBe("South district · South East");
  });
});
