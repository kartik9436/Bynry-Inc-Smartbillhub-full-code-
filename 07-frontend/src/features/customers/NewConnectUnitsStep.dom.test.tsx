// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  `CR-150-BRC09` task T3 — **STEP 3 ABSORBS TWO WHOLE STEPS**, and
//          their step ids are gone. PO, verbatim: *"we dont want any
//          information to be reduced or lost - 8 steps → 5"*.
// Rules:   B14 rule 31 (no database id is ever the visible value of a field) ·
//          rule 32 (a stated absence) · rule 33 (a LABEL ≤ 3 words) ·
//          BR-WRK-013 (the completing job is the TEMPLATE's flag) ·
//          BR-SHL-025 (a control that cannot act says why) ·
//          hard-won law 2 (built is not wired) · law 6 (no gate reads rendered
//          output) · law 7 (know what would make this pass wrongly)
// Questions: `OQ-CUS-12770` OPEN — no `Qty` column, and a case asserts it is
//          ABSENT so the day it is built somebody has to come here.
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS FILE CAN AND CANNOT SEE — READ IT BEFORE TRUSTING IT GREEN
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THIS HARNESS DOES NO LAYOUT. EVERY ELEMENT HERE IS ZERO BY ZERO**, so it
// can never see a clipped table, a column out of order on screen, or a folded
// group that does not unfold. It reads RENDERED OUTPUT and never props, which
// is the most it can honestly claim.
//
// **WHAT WOULD MAKE THESE CASES PASS WRONGLY** (law 7's second habit), written
// out rather than left to be discovered:
//
//   * a column header present in the DOM while the cells under it render
//     nothing — so the cell cases below assert the CONTROL, by its
//     `data-cell` handle, and not the header;
//   * `toContain("Occupancy")` passing off the common selection's FIELD while
//     the table column vanished — so the column case counts `data-cell` and
//     names the table;
//   * the `Qty` absence case passing because the whole table failed to render
//     — so it asserts the eight columns that ARE there in the same case;
//   * every absorbed-field case passing on a string that happens to appear in
//     a comment or an aria-label — so each asserts a HANDLE where one exists.
//
// **The rendered proof is a browser and there is no substitute** — law 6.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render as renderDom, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { createApiClient } from "@/api/client";
import type { TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import type { ProposedWorkOrder } from "@/features/work/workEndpoints";

import { commitPlanOf, emptyDraft } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";
import type { DraftUnit } from "./newConnectShared";
import { UnitsStep } from "./NewConnectUnitsStep";

const TEST_TENANT = "brazosbend";
const t = (key: string, options?: Record<string, unknown>) => String(i18next.t(key, options));

function proposedOrder(over: Partial<ProposedWorkOrder>): ProposedWorkOrder {
  return {
    template_id: "00000000-0000-0000-0000-000000000000",
    template_no: null,
    name: "Service drop",
    service: { id: "svc", code: "electric", name: "Electric" },
    scope: "per_premise",
    sequence: 1,
    job_type: null,
    is_gate: false,
    version: 1,
    est_duration_minutes: null,
    ...over,
  };
}
/** The job that COMPLETES the connection — `BR-WRK-013`, the template's flag. */
const DROP = proposedOrder({ template_id: "tpl-drop", name: "Service drop", is_gate: true });
const MARK_OUT = proposedOrder({
  template_id: "tpl-markout",
  name: "Site inspection & mark-out",
  service: { id: "svc-w", code: "water", name: "Water" },
  sequence: 2,
});
const PROPOSED: ProposedWorkOrder[] = [DROP, MARK_OUT];

/** Three dwellings on electric and water — the drawing's own build, whose
 *  FIGURES are illustrations (B14 rule 37) and whose SHAPE is not. */
const UNITS: DraftUnit[] = [1, 2, 15].map((n) => ({ label: `${n}`, isCommonArea: false }));

function unitsDraft(over: Partial<NewConnectDraft> = {}): NewConnectDraft {
  return { ...emptyDraft(), premiseServices: ["electric", "water"], ...over };
}

const PLATFORM_SERVICES = [
  "electric",
  "water",
  "gas",
  "sewer",
  "trash",
  "storm_water",
  "solar",
  "broadband",
  "thermal_heat",
  "battery",
  "fire",
] as const;

function tenantServices(enabled: readonly string[]): TenantServiceRow[] {
  return PLATFORM_SERVICES.map((service) => ({
    service: service as string,
    name: service as string,
    enabled: enabled.includes(service),
    primary_uom: null,
    alt_uom: null,
    billed_uom: null,
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: null,
    active_accounts: null,
  }));
}

interface Options {
  draft?: NewConnectDraft;
  units?: readonly DraftUnit[];
  proposed?: readonly ProposedWorkOrder[];
  proposalsUnavailable?: boolean;
  labelsAlreadyHere?: readonly string[];
  breaches?: { unit: string; service: string }[];
  sewerGaps?: string[];
  onPatch?: (next: Partial<NewConnectDraft>) => void;
  /** The tenant's catalogues, when a case needs other than electric/water. */
  enabled?: readonly string[];
  assetTypes?: { code: string; name: string; category: string }[];
  sizes?: { code: string; name: string; service: { code: string } | null }[];
}

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/…` PATTERN** (hard-won law 2): a bare
 * `MemoryRouter` with no matching route leaves `useParams().tenant` undefined
 * and every address the screen builds comes out protocol-relative — a string
 * that reads as perfectly good to `toContain`.
 */
function tree(options: Options = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(
    queryKeys.tenantServices,
    tenantServices(options.enabled ?? ["electric", "water"]),
  );
  const assetTypes = options.assetTypes ?? [
    { code: "meter", name: "Meter", category: "meters" },
    { code: "sub_meter", name: "Sub-meter", category: "sub_meters" },
  ];
  queryClient.setQueryData(["lookups", "asset_types", "new-connect"], {
    count: assetTypes.length,
    results: assetTypes,
  });
  const sizes = options.sizes ?? [{ code: "w1", name: 'Water 1"', service: { code: "water" } }];
  queryClient.setQueryData(["lookups", "service_size_classes", "new-connect"], {
    count: sizes.length,
    results: sizes,
  });
  queryClient.setQueryData(["connection-wizard-templates"], { count: 0, results: [] });
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      new Response(JSON.stringify({ count: 0, results: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=3`]}>
          <Routes>
            <Route
              path="/:tenant/connections/new"
              element={
                <UnitsStep
                  draft={options.draft ?? unitsDraft()}
                  units={options.units ?? UNITS}
                  labelsAlreadyHere={options.labelsAlreadyHere ?? []}
                  breaches={options.breaches ?? []}
                  sewerGaps={options.sewerGaps ?? []}
                  proposed={options.proposed ?? PROPOSED}
                  proposalsUnavailable={options.proposalsUnavailable ?? false}
                  onPatch={options.onPatch ?? (() => undefined)}
                  client={client}
                  t={t}
                  dateFormat="MM/DD/YYYY"
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}

const html = (options: Options = {}) => renderToStaticMarkup(tree(options));

afterEach(() => {
  document.body.innerHTML = "";
});

// ════════════════════════════════════════════════════════════════════════════
// 1 · THE COLUMNS THE PRODUCT OWNER RULED
// ════════════════════════════════════════════════════════════════════════════
describe("the units table's columns", () => {
  it("draws the eight ruled columns and NO Qty", () => {
    // Decision log 2026-09-28 answer 13(c): *Unit · Kind · Service · Asset ·
    // Size · Qty · Work order · Completes · Occupancy*, and *"`Qty` is DRAWN
    // and NOT BUILT"*.
    const markup = html();
    for (const column of ["Unit", "Kind", "Service", "Asset", "Size", "Work order", "Completes", "Occupancy"]) {
      expect(markup).toContain(`>${column}</th>`);
    }
    // ⛔ `OQ-CUS-12770` is OPEN and it multiplies a price on a real invoice.
    // The eight above are asserted in the same case so this cannot pass by the
    // table failing to render at all (law 7).
    expect(markup).not.toContain(">Qty</th>");
  });

  it("puts a CONTROL under every column that takes an answer", () => {
    // A header with nothing under it is the false pass this case exists for.
    const markup = html();
    for (const cell of ["service", "asset", "size", "work-order", "completes", "occupancy"]) {
      expect(markup).toContain(`data-cell="${cell}"`);
    }
  });

  it("shows no database id anywhere a clerk reads", () => {
    // B14 rule 31. The template id is an option's VALUE and the name is the
    // word; the uuid must never be the visible text of anything.
    const markup = html();
    expect(markup).not.toContain(">tpl-drop<");
    expect(markup).not.toContain(">tpl-markout<");
    expect(markup).toContain("Service drop");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 2 · A SERVICE ROW PER UNIT, GROUPED BY UNIT
// ════════════════════════════════════════════════════════════════════════════
describe("a row per unit and service", () => {
  it("names each unit once, at the head of its group", () => {
    // PO, verbatim: *"grouped by units"*.
    const markup = html();
    for (const unit of ["1 · Dwelling", "2 · Dwelling", "15 · Dwelling"]) {
      expect(markup).toContain(unit);
    }
  });

  it("renders one row per unit × service in the open group, and folds the rest", () => {
    // Two services on the open unit; the other two units are FOLDED, which is
    // how `step3-units.png` rests, and each is one press from open.
    // ⚠ **SCOPED TO THE UNITS TABLE ON PURPOSE.** The common selection above
    // it draws `data-cell="service"` too, so an unscoped count reads four and
    // passes for the wrong reason — which is exactly the false pass this file's
    // header promises to name (law 7).
    const UNITS_TABLE = '[data-array="units-and-service-points"] ';
    renderDom(tree());
    expect(document.querySelectorAll(`${UNITS_TABLE}[data-cell="service"]`).length).toBe(2);
    expect(document.querySelectorAll(`${UNITS_TABLE}[data-group-toggle]`).length).toBe(
      UNITS.length,
    );
    // Unfolding unit 2 brings its two rows, so nothing is unreachable.
    fireEvent.click(document.querySelector('[data-group-toggle="unit:2"]') as HTMLElement);
    expect(document.querySelectorAll(`${UNITS_TABLE}[data-cell="service"]`).length).toBe(4);
  });

  it("counts the service points rather than printing a drawn number", () => {
    const markup = html();
    // Six taken points on this build. `12` is the drawing's illustration.
    expect(markup).toContain(">6<");
    expect(markup).not.toContain(">12<");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 3 · WHAT THE ABSORBED *WORK ORDERS* STEP HELD — NOTHING MISSING
// ════════════════════════════════════════════════════════════════════════════
describe("the absorbed Work orders step", () => {
  it("keeps the work-order column, the target date and Completes", () => {
    const markup = html();
    expect(markup).toContain('data-cell="work-order"');
    expect(markup).toContain('id="nc_target"');
    expect(markup).toContain('data-cell="completes"');
  });

  it("ticks Completes from the TEMPLATE and refuses the clerk, with a reason", () => {
    // `BR-WRK-013` — on gas the completing job is the light-up and never the
    // meter set, so this is the template's flag. `BR-SHL-025` — a control that
    // cannot act is disabled AND says why.
    renderDom(tree());
    const tick = document.querySelector('[data-cell="completes"]') as HTMLInputElement;
    expect(tick.disabled).toBe(true);
    expect(tick.getAttribute("title")).toBe("Set by the template.");
    // The template flagged `is_gate`, so the box reads ticked without a clerk.
    expect(tick.checked).toBe(true);
  });

  it("keeps the empty state and its door when no template covers the build", () => {
    const markup = html({ proposed: [] });
    expect(markup).toContain("No template covers these services.");
    expect(markup).toContain("Write a template");
    // Mounted under the real pattern, so the address is a real one.
    expect(markup).toContain(`/${TEST_TENANT}/`);
  });

  it("keeps the proposals-failed refusal", () => {
    expect(html({ proposalsUnavailable: true })).toContain('data-proposals="unavailable"');
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 4 · WHAT THE ABSORBED *MAP SERVICES* STEP HELD
// ════════════════════════════════════════════════════════════════════════════
describe("the absorbed Map services step", () => {
  it("keeps all four counts, computed", () => {
    const markup = html();
    for (const tile of ["Services here", "Service points", "Meters to fit", "Work orders"]) {
      expect(markup).toContain(tile);
    }
  });

  it("keeps the availability refusal, under the unit it is about", () => {
    const markup = html({ breaches: [{ unit: "15", service: "broadband" }] });
    expect(markup).toContain("This address does not.");
  });

  it("keeps the sewer-follows-water refusal", () => {
    expect(html({ sewerGaps: ["2"] })).toContain("Sewer follows water.");
  });

  it("says nothing where neither fires", () => {
    // ⚠ THE CASE THAT STOPS THE TWO ABOVE BEING CHECKS THAT CANNOT FAIL.
    const markup = html();
    expect(markup).not.toContain("This address does not.");
    expect(markup).not.toContain("Sewer follows water.");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 5 · OCCUPANCY IS ON THIS STEP — PO: *"why dont you keep this with units"*
// ════════════════════════════════════════════════════════════════════════════
describe("occupancy", () => {
  it("is a column on the table AND a control in the common selection", () => {
    const markup = html();
    expect(markup).toContain('data-cell="occupancy"');
    expect(markup).toContain('id="nc_common_occupancy"');
    // Its two real choices (`DEF-CUS-9050`, PO 2026-10-02), in the cell's own short words.
    expect(markup).toContain("Vacant");
    expect(markup).toContain("Vacant · base only");
    expect(markup).not.toContain("Landlord-billed");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 6 · THE TWO ADDS, IN PLACE — NEITHER OPENS A DIALOG
// ════════════════════════════════════════════════════════════════════════════
describe("+ Add row and + Add work order", () => {
  it("draws both buttons on the table's footer", () => {
    const markup = html();
    expect(markup).toContain('data-array-action="add-row"');
    expect(markup).toContain('data-array-action="add-work-order"');
  });

  it("adds an EMPTY row in place, and opens nothing on top of the screen", () => {
    // `step3a-add-row.png`, in its own words: *"A row appears at the bottom of
    // the unit you added it to, empty and ready to type. Nothing opens on top
    // of the screen."* Decision log answer 13(e) rules it.
    renderDom(tree());
    const before = document.querySelectorAll('[data-cell="service"]').length;
    fireEvent.click(screen.getByText("+ Add row"));
    const after = document.querySelectorAll('[data-cell="service"]').length;
    expect(after).toBe(before + 1);
    // A DIALOG would be a `role="dialog"`. There is none, before or after.
    expect(document.querySelectorAll('[role="dialog"]').length).toBe(0);
    // The new row is EMPTY and asks for a service first.
    expect(document.body.innerHTML).toContain("Choose a service");
  });

  it("keeps Asset and Size unusable until a service is chosen, with the reason", () => {
    // `step3a-add-row.png`: *"Asset and Size stay empty until a service is
    // chosen, because their lists depend on it."* BR-SHL-025 puts the reason
    // on the control; rule 33 keeps it off the screen as prose.
    renderDom(tree());
    fireEvent.click(screen.getByText("+ Add row"));
    const blocked = [...document.querySelectorAll('[data-cell="asset"]')].filter(
      (node) => (node as HTMLSelectElement).disabled,
    );
    expect(blocked.length).toBe(1);
    expect(blocked[0].getAttribute("title")).toBe("Choose a service first.");
  });

  it("offers ONE Applies to and ONE work-order dropdown (CR-164-BRC10 item 17)", () => {
    // ⊕ AMENDED 2026-10-02: the PO replaced the template search and the
    // per-order *Applies to* list with one pair of dropdowns.
    const markup = html();
    expect(markup).toContain('id="nc_add_order"');
    expect(markup).toContain('id="nc_add_order_applies"');
    expect(markup.match(/id="nc_add_order_applies"/g)?.length).toBe(1);
    expect(markup).not.toContain("Search templates");
  });

  it("puts an added order under Whole build, with Service, Asset and Size as —", () => {
    const added = proposedOrder({ template_id: "tpl-extra", name: "Pole set", scope: "build" });
    const markup = html({ draft: unitsDraft({ addedWorkOrders: [added] }) });
    expect(markup).toContain("Whole build");
    expect(markup).toContain("Pole set");
    // ⊕ `CR-164-BRC10` items 16, 17 — the row itself is editable: its Applies
    // to and its work order are dropdowns in the table, and no second list of
    // *Applies to* boxes stands under it.
    expect(markup).toContain('data-cell="applies-to"');
    expect(markup).toMatch(/<select[^>]*data-cell="work-order"[\s\S]{0,400}Pole set/);
    expect(markup).not.toContain('id="nc_applies_tpl-extra"');
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 7 · THE COMMON SELECTION, AND *APPLY TO ALL*
// ════════════════════════════════════════════════════════════════════════════
describe("the common selection", () => {
  it("draws the four fields and the required act", () => {
    const markup = html();
    expect(markup).toContain('id="nc_from"');
    expect(markup).toContain('id="nc_to"');
    expect(markup).toContain('id="nc_common_occupancy"');
    expect(markup).toContain('id="nc_target"');
    expect(markup).toContain('data-apply-to-all=""');
    // An INSTRUCTION at six words a sentence (B14 rule 33).
    expect(markup).toContain("Required before Continue. Rows stay editable.");
  });

  it("writes the selection onto EVERY unit when pressed", () => {
    // *Apply to all* is the drawn primary act, and the rows stay editable
    // afterwards — PO, of exactly that: *"this is correct"*.
    const patches: Partial<NewConnectDraft>[] = [];
    renderDom(tree({ onPatch: (next) => patches.push(next) }));
    fireEvent.click(screen.getByText("Apply to all"));
    expect(patches.length).toBe(1);
    const grid = patches[0].unitServiceGrid ?? {};
    // Three units × two services, every one written.
    expect(Object.keys(grid).length).toBe(UNITS.length * 2);
    expect(Object.values(grid).every((cell) => cell.taken === true)).toBe(true);
  });

  it("says which act is outstanding until it is pressed", () => {
    expect(html()).toContain('data-apply-required=""');
  });

  it("says it ONLY while the rows are empty (DEF-CUS-9199)", () => {
    // ⊕ `CR-164-BRC10` item 18. A filled table — the state Back and Next bring
    // the clerk back to — carries neither the strip nor the note.
    const filled = unitsDraft({
      unitServiceGrid: Object.fromEntries(
        UNITS.flatMap((unit) => [
          [`${unit.label}\u001Felectric`, { taken: true, assetType: "meter", sizeClass: "E-100" }],
          [`${unit.label}\u001Fwater`, { taken: true, assetType: "meter", sizeClass: "W-1" }],
        ]),
      ),
    });
    const markup = html({ draft: filled });
    expect(markup).not.toContain('data-apply-required=""');
    expect(markup).not.toContain('data-apply-note=""');
    expect(html()).toContain('data-apply-note=""');
  });

  it("offers the unit type in the common selection (CR-164-BRC10 item 15)", () => {
    expect(html()).toContain('id="nc_common_unit_type"');
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 8 · FIRE LINES — PO ruling 2026-10-02 (`OQ-1361`, fire-line half CLOSED)
// ════════════════════════════════════════════════════════════════════════════
//
// *"A · A fire service gets a "fire line" item with a size (2" to 10"), like a
// trash cart. The clerk picks the size on New Connection."* A fire row offers
// the tenant's `fire_line` and fire's own sizes; each further line is one more
// row of the same service, which is how the count is made — a row per piece,
// never a typed `Qty` (`OQ-CUS-12770` holds that column).
//
// WHAT WOULD MAKE THESE PASS WRONGLY (law 7): a size select that lists every
// service's sizes — so the case asserts fire's six AND that water's is absent;
// a piece row that renders but sends nothing — so the case ends on the commit
// payload built from the same draft the screen drew.
describe("fire lines on step 3", () => {
  const FIRE_TYPES = [
    { code: "meter", name: "Meter", category: "meters" },
    { code: "container_cart", name: "Container / Cart", category: "behind_the_meter" },
    { code: "fire_line", name: "Fire service line", category: "behind_the_meter" },
  ];
  const FIRE_SIZES = [
    { code: "w1", name: 'Water 1"', service: { code: "water" } },
    ...[2, 4, 6, 8, 10, 12].map((inch) => ({
      code: `FL-${inch}`,
      name: `Fire line ${inch}"`,
      service: { code: "fire" },
    })),
  ];
  const ONE: DraftUnit[] = [{ label: "1", isCommonArea: false }];
  const FIRE_TABLE = '[data-array="units-and-service-points"] ';

  function fireDraft(more?: string[]): NewConnectDraft {
    return unitsDraft({
      premiseServices: ["fire"],
      // The commit derives its units from the PATTERN, as the wizard does.
      pattern: { prefix: "", from: "1", to: "1", includeCommonArea: false },
      unitServiceGrid: {
        [`1\u001Ffire`]: { taken: true, assetType: "fire_line", sizeClass: "FL-6", more },
      },
    });
  }

  it("offers the fire line and fire's six sizes, and nothing of water's", () => {
    renderDom(
      tree({
        draft: fireDraft(),
        units: ONE,
        enabled: ["fire"],
        assetTypes: FIRE_TYPES,
        sizes: FIRE_SIZES,
      }),
    );
    const asset = document.querySelector(`${FIRE_TABLE}[data-cell="asset"]`) as HTMLSelectElement;
    expect(asset.value).toBe("fire_line");
    expect([...asset.options].map((o) => o.text)).toEqual(["None", "Fire service line"]);
    // `DEF-CUS-9093` — the Asset and Size cells keep their widest name's width
    // (`CellSelect fit`), so "Fire service line" is never cut to "Fire service
    // li". jsdom does no layout: the CLASS is what this proves; the width is
    // measured in a browser by `10-scripts/oq1361_fire_line_step3_walkthrough.mjs`.
    expect(asset.classList.contains("min-w-max")).toBe(true);
    const size = document.querySelector(`${FIRE_TABLE}[data-cell="size"]`) as HTMLSelectElement;
    expect(size.value).toBe("FL-6");
    expect(size.classList.contains("min-w-max")).toBe(true);
    expect([...size.options].slice(1).map((o) => o.value)).toEqual([
      "FL-2",
      "FL-4",
      "FL-6",
      "FL-8",
      "FL-10",
      "FL-12",
    ]);
  });

  it("+ Add row on fire adds one more fire line at the row's size", () => {
    const patches: Partial<NewConnectDraft>[] = [];
    renderDom(
      tree({
        draft: fireDraft(),
        units: ONE,
        enabled: ["fire"],
        assetTypes: FIRE_TYPES,
        sizes: FIRE_SIZES,
        onPatch: (next) => patches.push(next),
      }),
    );
    fireEvent.click(screen.getByText("+ Add row"));
    const pending = [
      ...document.querySelectorAll(`${FIRE_TABLE}select[data-cell="service"]`),
    ].pop() as HTMLSelectElement;
    fireEvent.change(pending, { target: { value: "fire" } });
    const grid = patches.at(-1)?.unitServiceGrid ?? {};
    expect(grid[`1\u001Ffire`]?.more).toEqual(["FL-6"]);
    // Still ONE fire service on the unit — a piece, never a second service row.
    expect(grid[`1\u001Ffire`]?.taken).toBe(true);
  });

  it("draws each further line as its own sized row, and the commit counts them", () => {
    const draft = fireDraft(["FL-2", "FL-2"]);
    renderDom(
      tree({
        draft,
        units: ONE,
        enabled: ["fire"],
        assetTypes: FIRE_TYPES,
        sizes: FIRE_SIZES,
      }),
    );
    const sizes = [
      ...document.querySelectorAll(`${FIRE_TABLE}[data-cell="size"]`),
    ] as HTMLSelectElement[];
    expect(sizes.map((one) => one.value)).toEqual(["FL-6", "FL-2", "FL-2"]);
    // The piece rows name the device rather than offering another.
    expect(document.querySelectorAll(`${FIRE_TABLE}select[data-cell="asset"]`).length).toBe(1);
    expect(
      [...document.querySelectorAll(`${FIRE_TABLE}span[data-cell="asset"]`)].map(
        (one) => one.textContent,
      ),
    ).toEqual(["Fire service line", "Fire service line"]);
    // 1 × 6" + 2 × 2" — the build whose first bill is $60.00 + 2 × $12.00 = $84.00.
    const plan = commitPlanOf(draft, null, []);
    expect(plan.unit_services).toEqual([
      {
        unit_label: "1",
        service: "fire",
        equipment: [
          { type: "fire_line", size_class: "FL-6", count: 1 },
          { type: "fire_line", size_class: "FL-2", count: 2 },
        ],
      },
    ]);
    expect(plan.meters).toEqual([]);
  });
});
