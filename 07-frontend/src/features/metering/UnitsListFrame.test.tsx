// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 U1 — the units list against its drawn frame.
// Drawn:   04-docs/05-modules/04-metering/conformance/CR-089-p050-units-list.md
//          (blueprint *Premises & Units Blueprint 2*, pages 50-53)
// Screens: S15 · PRM-01U
// Rules:   B14 rule 15 (row actions are icons, max 2 visible then `…`) ·
//          B14 rule 32 (a description budget) · BR-MET-094 + BR-CUS-170 (a
//          vacancy IS billed, to the owner) · BR-MET-101 (a common area is a
//          unit with a FLAG) · DEF-127 / DEF-138 (an absence is never `0.00`)
// ───────────────────────────────────────────────────────
//
// WHY THIS IS ITS OWN FILE. `UnitsPage.test.tsx` is open in front of at least
// one other lane this session — its working copy already carries hunks that are
// not this lane's — and a pathspec commit takes the WHOLE file, so everything
// NEW is written here where this lane is the only author (CLAUDE.md law 11,
// mechanisms two and five). The cases that had to MOVE, because they asserted
// the superseded design, were edited there because they could not stay.
//
// ⚠ **WHAT THIS FILE CANNOT TELL YOU.** It renders to static markup, so it
// proves PRESENCE, ORDER and the exact STRING of a drawn label — three of the
// seven checks the UI skill's §4 comparison asks for. Alignment, spacing,
// weight and colour need a browser and a person; they are reported as
// unverified rather than asserted here in a form that would pass over a wrong
// screen.
//
// ⚠ **AND NO DRAWN NUMBER IS ASSERTED ANYWHERE BELOW (PO ruling 2026-09-10:
// *"Treat every number drawn in a wireframe as an illustration, never a fact to
// build to."*)** `U-01144`, `1,109` and `Page 1 of 23` are examples of a SHAPE.
// What is pinned is the shape: a count where the frame draws a count, a
// sentence where the frame draws a sentence.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { Paginated, PremisesRow, UnitRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";

import { PremisesTabsPage, premisesRollupQueryKey } from "./PremisesTabsPage";
import {
  unitPremisesPickerKey,
  unitPlanOptionsKey,
  unitsQueryKey,
  unitsTableConfig,
} from "./UnitsListPage";
import { PREMISES_TAB_UNITS } from "./meteringShared";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function unit(over: Partial<UnitRow> = {}): UnitRow {
  return {
    id: "u-1",
    unit_no: "U-00101-A",
    premises_id: "p-1",
    premise_no: "P-00101",
    premise_address: "412 Cypress Row",
    label: "1",
    unit_type: "residential",
    floor_label: null,
    square_feet: null,
    rate_plan_id: "rp-1",
    plan_effective_from: null,
    plan_locked: false,
    vacant_standby_auto: false,
    is_common_area: false,
    lat: null,
    lng: null,
    point: { lat: null, lng: null, source: "premises" as const },
    active: true,
    services: ["electric", "water"],
    meters: [
      { id: "a1", asset_no: "M-7001", qualifier: null },
      { id: "a2", asset_no: "M-7204", qualifier: "sub" },
    ],
    occupancy: "occupied",
    occupant: "M. Alvarez",
    account_no: "A-10517",
    status: "active",
    metered_services: [],
    sub_metered: true,
    ...over,
  };
}

const PREMISES: PremisesRow[] = [];

const CELLS_STUB = {
  select: () => <span />,
  unitNo: () => <span />,
  premise: () => <span />,
  owed: () => <span />,
  label: () => <span />,
  type: () => <span />,
  services: () => <span />,
  offered: () => <span />,
  missing: () => <span />,
  meters: () => <span />,
  occupancy: () => <span />,
  occupant: () => <span />,
  status: () => <span />,
  actions: () => <span />,
};
const CONFIG = unitsTableConfig(t, [], [], CELLS_STUB);

function paged<T>(rows: T[]): Paginated<T> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

/** ONE `<tr>`, sliced before anything is asserted about it. A row assertion
 *  made over the whole document reads the toolbar and the filter chips too
 *  (`DEF-MET-4718`). */
function rowFor(html: string, marker: string): string {
  const at = html.indexOf(marker);
  if (at < 0) {
    throw new Error(`no row containing ${marker}`);
  }
  return html.slice(html.lastIndexOf("<tr", at), html.indexOf("</tr>", at));
}

function renderUnits(rows: UnitRow[], access = "Full"): string {
  void access;
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = parseTableParams(new URLSearchParams(), CONFIG);
  queryClient.setQueryData(unitsQueryKey(serializeTableParams(state, CONFIG).toString()), paged(rows));
  queryClient.setQueryData(unitPremisesPickerKey, { ...paged(PREMISES), rollup: null });
  queryClient.setQueryData(unitPlanOptionsKey, paged([]));
  queryClient.setQueryData(premisesRollupQueryKey, { ...paged(PREMISES), rollup: null });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/premises/units`]}>
          <Routes>
            <Route
              path="/:tenant/premises/units"
              element={<PremisesTabsPage tab={PREMISES_TAB_UNITS} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-089 U1 — the units list's drawn columns", () => {
  it("the sixth column is headed `Occupant`, not `Occupant / Account`", () => {
    // The frame's own note: the account is still IN the cell, quiet, under the
    // name. A header naming both halves of one cell is double-labelling.
    const html = renderUnits([unit()]);
    expect(html).toContain(`>${t("metering.units.col.occupant")}<`);
    expect(html).not.toContain("Occupant / Account");
    // …and the account did not leave the row with the header.
    expect(rowFor(html, "U-00101-A")).toContain("A-10517");
  });

  it("`Meters` is how many, and an empty one says `none` rather than a nought", () => {
    // ⚠ DEF-075's shape: a nought reads as a measured quantity. An absence is
    // drawn as an absence.
    const html = renderUnits([unit(), unit({ id: "u-2", unit_no: "U-00101-B", label: "2", meters: [] })]);
    const withTwo = rowFor(html, "U-00101-A");
    expect(withTwo).toContain(">2<");
    expect(withTwo).not.toContain("M-7001");
    const withNone = rowFor(html, "U-00101-B");
    expect(withNone).toContain(t("metering.meters.none"));
    expect(withNone).not.toContain(">0<");
  });

  it("a common area says so in the `Type` column, from the FLAG and not the typing", () => {
    // `BR-MET-101` makes `is_common_area` the fact and `unit_type` the legacy
    // typing, so a common area imported as `residential` is still a common
    // area. Asserting the flag alone would pass on a screen reading the code.
    const html = renderUnits([
      unit({ id: "u-3", unit_no: "U-00101-C", label: "Laundry", is_common_area: true }),
    ]);
    expect(rowFor(html, "U-00101-C")).toContain(t("metering.units.type.common_area"));
  });

  it("a vacant unit says who pays IN THE CELL, and the money column never invents a zero", () => {
    // Two ruled facts in one sentence (`BR-MET-094`, `BR-CUS-170`) and the PO's
    // 2026-09-10 ruling on the money beside it: `0.00` only when the balance
    // really is zero. The markup is stripped first — the sentence used to live
    // in a `title=` attribute, which a keyboard never reaches and which every
    // `toContain` over raw HTML reads as though it were on screen.
    const html = renderUnits([
      unit({ occupancy: "vacant", occupant: null, account_no: null, owed: null }),
    ]);
    const text = rowFor(html, "U-00101-A").replace(/<[^>]*>/g, " ");
    expect(text).toContain(t("metering.units.owed.vacantOwnerBilled"));
    expect(text).toContain(t("metering.units.owed.notMeasured"));
    expect(text).not.toContain("0.00");
  });
});

describe("CR-089 U1 — the row actions are three and an overflow (B14 rule 15)", () => {
  it("two glyphs and the `…` are on the row; the other four are behind it", () => {
    const html = renderUnits([unit()]);
    const row = rowFor(html, "U-00101-A");
    // The frame draws `👁 ✎ …`. The eye is a LINK so middle-click works.
    expect(row).toContain(`aria-label="${t("metering.units.action.open")}"`);
    expect(row).toContain(`href="/${TENANT}/premises/units/u-1"`);
    expect(row).toContain(`aria-label="${t("metering.action.edit")}"`);
    expect(row).toContain(`aria-label="${t("table.rowActions.more")}"`);
    // ⚠ **THE COUNT IS THE ASSERTION.** Presence checks pass on the five-glyph
    // cell this replaces; what B14 rule 15 caps is HOW MANY are visible, so the
    // controls outside the overflow are counted — and counted inside the
    // ACTIONS cell alone, because a whole row also carries the select
    // checkbox's name and one per service badge.
    const cell = row.slice(row.lastIndexOf("<td", row.indexOf("<details")));
    const visible = cell.slice(0, cell.indexOf("<details"));
    expect(visible.match(/aria-label=/g) ?? []).toHaveLength(2);
  });

  it("nothing was removed — every action that was on the row is still reachable", () => {
    // A capability cut needs a ruling and the frame does not ask for one. Four
    // actions moved; none left.
    const row = rowFor(renderUnits([unit()]), "U-00101-A");
    const menu = row.slice(row.indexOf("<details"));
    for (const label of [
      t("metering.units.action.assignPlan"),
      t("metering.units.action.move"),
      t("metering.action.deactivate"),
      t("metering.action.delete"),
    ]) {
      expect(menu).toContain(label);
    }
  });
});
