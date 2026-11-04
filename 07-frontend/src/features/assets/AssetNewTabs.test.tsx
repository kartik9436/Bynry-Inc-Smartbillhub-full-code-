// ── Trace ──────────────────────────────────────────────
// Change:   CR-028 AST-W5 (B16 §4.4–§4.6 · §10 rulings D1/D3/D5/D6/D7,
//           PO 2026-08-22): T1 Inventory tab · T2 Lifecycle tab · T3 Map tab ·
//           T4 the ONE "Work R5" sweep over every work-order touchpoint.
// Rules:    §10-D5 (counts & costs ONLY — the r10 reorder/van/stock-import
//           affordances are asserted ABSENT) · §10-D3 (no GL sentence —
//           "5300"/"5400"/"Cost & Margin"/depreciation asserted ABSENT) ·
//           §10-D6 (Esri tiles + geocoded premises; the canvas never loads
//           Leaflet under jsdom) · §10-D7 ("Work R5", exactly two words,
//           disabled-with-reason — BR-SHL-025) · BR-AST-026 · BR-AST-031
// ───────────────────────────────────────────────────────
// RED-FIRST (r11 2d) — both guards were BROKEN ON PURPOSE and their failures
// quoted in the lane report before being trusted green:
//   · the D5-absence case went RED on an injected "Import stock count"
//     button (`D5 forbids "Import stock count": expected … not to contain`);
//   · the Work-R5 sweep's FIRST DRAFT stayed GREEN when the lifecycle wrench
//     was mutated to an ENABLED tooltip (`hint` instead of `reason`) — the
//     whole-page substring check could not see it (the DEF-182 class). The
//     per-control walk below replaced it and goes RED on exactly that
//     mutation (`expected false to be true` on the wrench's parsed tag).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  AssetGeoRow,
  AssetGeoView,
  AssetLifecycleView,
  AssetStockView,
} from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  AssetInventoryTab,
  assetStockQueryKey,
  stockDrillPath,
} from "./AssetInventoryTab";
import {
  AssetLifecycleTab,
  assetLifecycleQueryKey,
  requirementLabel,
  yearsLabel,
} from "./AssetLifecycleTab";
import {
  AssetMapTab,
  EMPTY_GEO_FILTERS,
  assetGeoQueryKey,
  filterGeoAssets,
  geoNeedsAttention,
  mapVocab,
  markerStyle,
} from "./AssetMapTab";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

// ── Fixtures (the served shapes, r10's own figures where it has them) ──────

const STOCK: AssetStockView = {
  kpis: {
    uninstalled: 115,
    value_at_cost: "18420.0000",
    aged_over_12_months: 9,
    currency: "USD",
  },
  rows: [
    {
      type: "meter",
      type_name: "Meter",
      tab: "meters",
      count: 62,
      unit_cost: "171.0000",
      unit_cost_min: "118.0000",
      unit_cost_max: "171.0000",
      value: "10416.0000",
      suppliers: ["Badger Meter", "Neptune"],
      services: ["water"],
    },
    {
      type: "container_cart",
      type_name: "Trash cart",
      tab: "behind_the_meter",
      count: 1,
      unit_cost: null,
      unit_cost_min: null,
      unit_cost_max: null,
      value: null,
      suppliers: [],
      services: [],
    },
  ],
};

const LIFECYCLE: AssetLifecycleView = {
  certifications: [
    {
      id: "a-3301",
      asset_no: "BF-3301",
      type: "backflow",
      type_name: "Backflow preventer",
      premises: "500 Main Plaza · 200",
      requirement: { kind: "annual_test", interval_months: 12 },
      due: "2026-01-18",
      days_until: -210,
      status: "overdue",
    },
    {
      id: "a-3318",
      asset_no: "BF-3318",
      type: "backflow",
      type_name: "Backflow preventer",
      premises: "1200 Business Park",
      requirement: { kind: "annual_test", interval_months: 12 },
      due: "2026-09-02",
      days_until: 17,
      status: "due_soon",
    },
    {
      id: "a-4310",
      asset_no: "M-4310",
      type: "meter",
      type_name: "Meter",
      premises: "77 Industrial Way",
      requirement: { kind: "accuracy_recertification", interval_months: 96 },
      due: "2026-11-12",
      days_until: 88,
      status: "in_date",
    },
    {
      id: "a-1204",
      asset_no: "PV-1204",
      type: "pv",
      type_name: "Solar inverter",
      premises: "1200 Business Park",
      requirement: { kind: "certification", interval_months: null },
      due: "2027-03-04",
      days_until: 200,
      status: "scheduled",
    },
  ],
  warranty_groups: [
    {
      type: "meter",
      type_name: "Meter",
      tab: "meters",
      supplier: "Neptune",
      units: 113,
      cover_ends: "2032-06-30",
      under_warranty: 113,
      status: "covered",
    },
    {
      type: "meter",
      type_name: "Meter",
      tab: "meters",
      supplier: "Itron Inc",
      units: 42,
      cover_ends: "2023-08-01",
      under_warranty: 0,
      status: "expired",
    },
  ],
  age_forecast: {
    rows: [
      {
        type: "meter",
        type_name: "Meter",
        tab: "meters",
        avg_age_months: 170,
        expected_life_years: 15,
        past_life: 26,
        due_within_12mo: 87,
        replacement_cost: "10266.0000",
      },
      {
        type: "comms",
        type_name: "Comms endpoint",
        tab: "meters",
        avg_age_months: null,
        expected_life_years: null,
        past_life: 0,
        due_within_12mo: 0,
        replacement_cost: null,
      },
    ],
    programme: { units: 121, cost: "15842.0000" },
  },
  asset_value: {
    buy_value: "34224.0000",
    present_value: "22150.5500",
    currency: "USD",
  },
};

function geoRow(over: Partial<AssetGeoRow> = {}): AssetGeoRow {
  return {
    id: "a-4021",
    asset_no: "M-4021",
    tab: "meters",
    type: "meter",
    type_name: "Meter",
    role: { kind: "standard" },
    service: "electric",
    status: "active",
    status_name: "Installed/Active",
    behavior_class: "in_service",
    test_due: false,
    lat: "30.245200",
    lng: "-97.765100",
    // CR-089 wave A · BR-MET-1162 — the ordinary case: this pin is the
    // building's, which is what all 1,109 units read today.
    point_source: "premises",
    premises: "1408 Elm Street",
    unit: "Unit A",
    area: "North",
    last_read: { consumption: "42864", unit: "kWh", read_at: "2026-08-03" },
    ...over,
  };
}

const GEO: AssetGeoView = {
  assets: [
    geoRow(),
    geoRow({
      id: "a-master",
      asset_no: "M-MASTER-12",
      role: { kind: "master", count: 24 },
      service: "water",
      area: "East",
    }),
    geoRow({
      id: "a-sub",
      asset_no: "SM-8801",
      tab: "sub_meters",
      type: "sub_meter",
      type_name: "Sub-meter",
      role: { kind: "sub", parent: "M-MASTER-12" },
    }),
    geoRow({
      id: "a-4204",
      asset_no: "M-4204",
      status: "needs_repair",
      status_name: "Needs repair",
      behavior_class: "out_of_service",
      area: "South",
    }),
    geoRow({
      id: "a-dev",
      asset_no: "BF-3301",
      tab: "behind_the_meter",
      type: "backflow",
      type_name: "Backflow preventer",
      service: "water",
      test_due: true,
      last_read: null,
    }),
  ],
};

// ── Render helper ──────────────────────────────────────────────────────────

function render(node: ReactNode, section?: string, lifecycleView = LIFECYCLE): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(assetStockQueryKey, STOCK);
  queryClient.setQueryData(assetLifecycleQueryKey, lifecycleView);
  queryClient.setQueryData(assetGeoQueryKey, GEO);
  // The Lifecycle sub-tab is URL state (BR-SHL-011), so the entry carries it.
  const entry = `/${TEST_TENANT}/assets${section === undefined ? "" : `?section=${section}`}`;
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[entry]}>{node}</MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const inventory = () =>
  render(
    <AssetInventoryTab writeBlockedReason={null} onDrill={() => undefined} />,
  );
/** ⚠ **THE LIFECYCLE TAB IS THREE SECTIONS FROM 2026-09-12 (`DEF-MET-4955`),
 *  SO A TEST MUST SAY WHICH ONE.** It used to stack all three tables on one
 *  page, which is what these assertions were written against; screens 05a/05b/
 *  05c split them into sub-tabs carried in the URL (BR-SHL-011). The
 *  assertions below moved to the section that now holds their subject — none
 *  was dropped or weakened, because a dropped assertion is how a rebuilt
 *  screen quietly loses a column. */
const lifecycle = (section?: "certifications" | "warranty" | "forecast") =>
  render(<AssetLifecycleTab writeBlockedReason={null} />, section);
const blockedLifecycle = (section?: "certifications" | "warranty" | "forecast") =>
  render(<AssetLifecycleTab writeBlockedReason="Your role can view this but not change it." />, section);
const map = () => render(<AssetMapTab />);

// ══════════════════════════════════════════════════════════════════════════
// T1 — Inventory (AST-01.inventory · §10-D5)
// ══════════════════════════════════════════════════════════════════════════

describe("CR-028 W5 T1 — the Inventory tab", () => {
  it("draws the D5 KPI pair and the aggregate table from the SERVED view", () => {
    const html = inventory();
    expect(html).toContain(t("assets.stock.kpi.uninstalled"));
    expect(html).toContain("115");
    // $ at cost, displayed 2 dp from the 4-dp store (rule 2).
    expect(html).toContain("$18,420.00");
    expect(html).toContain(t("assets.stock.kpi.aged"));
    expect(html).toContain(">9<");
    // The meter line: count · latest unit cost · range · value · suppliers.
    expect(html).toContain(">62<");
    expect(html).toContain("$171.00");
    expect(html).toContain("$118.00");
    expect(html).toContain("$10,416.00");
    expect(html).toContain("Badger Meter · Neptune");
  });

  it("renders NULL costs as the dash — never a fabricated $0.00", () => {
    const html = inventory();
    expect(html).not.toContain("$0.00");
    // The costless cart line still counts.
    expect(html).toContain("Trash cart");
  });

  it("§10-D5: NO reorder columns/statuses/buttons and NO stock import", () => {
    const html = inventory();
    for (const banned of [
      "Reorder",
      "reorder",
      "On vans",
      "Yard",
      "Import stock count",
      "Below reorder",
      "At reorder",
    ]) {
      expect(html, `D5 forbids ${JSON.stringify(banned)}`).not.toContain(banned);
    }
  });

  it('"Parts in Work →" is LIVE and goes to the parts register', () => {
    // ⚠ INVERTED BY CR-070 WAVE M. It read *renders DISABLED with exactly
    // "Work R5"*, which was true until `Work-025` existed — and then went on
    // being asserted for two more waves while the parts register was live
    // behind it. That is the mirror of dead UI, and only a test pointed this
    // way can see it.
    const html = inventory();
    expect(html).toContain(t("assets.stock.partsInWork"));
    expect(html).toContain("data-parts-in-work");
    expect(html).not.toContain("data-work-r5");
    expect(html).not.toContain('title="Work R5"');
  });

  it("drills to the registry filtered by type + the uninstalled CLASS", () => {
    expect(stockDrillPath(STOCK.rows[0])).toBe(
      "/assets?tab=meters&f.type=meter&f.status=uninstalled",
    );
    // BR-AST-031: the class value, never a tenant stage label.
    expect(stockDrillPath(STOCK.rows[1])).toContain("f.status=uninstalled");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// T2 — Lifecycle (AST-01.lifecycle · §10-D3)
// ══════════════════════════════════════════════════════════════════════════

describe("CR-028 W5 T2 — the Lifecycle tab", () => {
  it("draws the three lists with the served statuses and derived wording", () => {
    // 05a · certifications — all four states, r10's own copy. The DEFAULT
    // section, so the bare address still lands here (05a's own "How you get
    // here": `?tab=lifecycle` lands on Certifications & tests due).
    const certs = lifecycle();
    expect(certs).toContain("BF-3301");
    expect(certs).toContain(t("assets.lifecycle.status.overdue"));
    expect(certs).toContain(t("assets.lifecycle.status.due_soon", { days: 17 }));
    expect(certs).toContain(t("assets.lifecycle.status.scheduled"));
    expect(certs).toContain(t("assets.lifecycle.status.in_date"));
    // Requirement wording DERIVES from the served cadence — never per-asset.
    expect(certs).toContain(t("assets.lifecycle.req.annual_test"));
    expect(certs).toContain(t("assets.lifecycle.req.accuracy_recertification"));
    // 05b · warranty groups.
    const warranty = lifecycle("warranty");
    expect(warranty).toContain(t("assets.lifecycle.warranty.covered"));
    expect(warranty).toContain(t("assets.lifecycle.warranty.expired"));
    expect(warranty).toContain(">113<");
    // 05c · forecast — months → "N.n yrs", and the programme total, which
    // survives the rebuild BESIDE the table rather than inside it (a
    // DataTable renders rows and a total is not one — see the component).
    const forecast = lifecycle("forecast");
    expect(forecast).toContain("14.2");
    expect(forecast).toContain(t("assets.lifecycle.programme"));
    // The programme pair reads as ONE line now ("121 · $10,266.00") rather than
    // two cells of a total row, so the assertion is the line and not a cell.
    // Both figures are still on the screen, which is the thing that matters.
    expect(forecast).toContain("121 · ");
    expect(forecast).toContain("$10,266.00");
    expect(forecast).toContain("$15,842.00");
  });

  it("05a/05b/05c: three sub-tabs, URL state, and the section decides the table", () => {
    // `DEF-MET-4955`. The three section titles become tab labels — same words,
    // same order — and only one table is mounted at a time, which is what
    // makes each of them a list the kit can give a toolbar and a pager to.
    const certs = lifecycle();
    for (const key of [
      "assets.lifecycle.certsTitle",
      "assets.lifecycle.warrantyTitle",
      "assets.lifecycle.forecastTitle",
    ]) {
      // `&` is `&amp;` in markup, and two of the three titles carry one — so
      // the raw catalogue value is compared against the ESCAPED form rather
      // than the assertion being dropped for the two that would fail.
      expect(certs, key).toContain(t(key).replace(/&/g, "&amp;"));
    }
    expect(certs).toContain('data-section="certifications"');
    expect(certs).toContain('aria-selected="true"');
    // The as-built breach, asserted as its repair: a toolbar, this list's own
    // search prompt (B14 rule 19), a column chooser and a pager — none of
    // which the three stacked tables had.
    expect(certs).toContain(t("assets.lifecycle.certs.search"));
    expect(certs).toContain("table-toolbar");
    expect(certs).toContain("Show or hide columns");
    expect(certs).toContain("table-pager");
    // Each section asks for ITS OWN search, so a screen cannot silently share
    // one prompt across three different questions.
    expect(lifecycle("warranty")).toContain(t("assets.lifecycle.warranty.search"));
    expect(lifecycle("forecast")).toContain(t("assets.lifecycle.forecast.search"));
    // An unknown section is the default rather than a blank screen — a stale
    // link is not a failure.
    expect(lifecycle("nonsense" as "forecast")).toContain(
      t("assets.lifecycle.certs.explainer"),
    );
  });

  it("B14 rule 17: the forecast table has an empty state — the branch that did not exist", () => {
    // `DEF-MET-4955`. `certifications` and `warranty_groups` each rendered a
    // colSpan empty row; `age_forecast.rows.map(...)` had NO empty branch at
    // all, so a tenant with nothing recorded got a header, no rows and a bare
    // Programme total. It cannot be reached from any seeded tenant — every one
    // of them has forecast rows — which is exactly why it is asserted here.
    const bare = render(
      <AssetLifecycleTab writeBlockedReason={null} />,
      "forecast",
      { ...LIFECYCLE, age_forecast: { rows: [], programme: { units: 0, cost: null } } },
    );
    expect(bare).toContain(t("assets.lifecycle.forecastEmpty"));
    expect(bare).toContain(t("assets.lifecycle.forecastEmptyHelper"));
  });

  it("BR-SHL-025: a role without write meets the two Work controls DISABLED, with the reason", () => {
    // `DEF-MET-4950`. `writeBlockedReason` was declared on this component,
    // passed by the page and read NOWHERE in the file — the word appeared
    // exactly once, in the type declaration. G13 could not see it: it asks
    // whether an optional prop has a CALLER, and it did.
    const blocked = blockedLifecycle();
    expect(blocked).toContain("Your role can view this but not change it.");
    const wrench = (blocked.match(/<button[^>]*aria-label="Raise work order"[^>]*>/) ??
      [])[0];
    expect(wrench, "the wrench must render").toBeTruthy();
    expect(/\bdisabled(?:=|>|\s|\/)/.test(`${wrench}>`)).toBe(true);

    const rule = blockedLifecycle("forecast");
    const programme = (rule.match(/<button[^>]*>[^<]*Set up an exchange rule[^<]*<\/button>/) ??
      [])[0];
    expect(programme, "the exchange-rule button must render").toBeTruthy();
    expect(/\bdisabled(?:=|>|\s|\/)/.test(programme ?? "")).toBe(true);
  });

  it("requirementLabel and yearsLabel derive words from data alone", () => {
    expect(requirementLabel({ kind: "annual_test", interval_months: 12 }, t)).toBe(
      "Annual test",
    );
    expect(
      requirementLabel({ kind: "accuracy_recertification", interval_months: 96 }, t),
    ).toBe("Accuracy recertification");
    expect(requirementLabel({ kind: "periodic_test", interval_months: 6 }, t)).toBe(
      "Test every 6 months",
    );
    expect(requirementLabel({ kind: "certification", interval_months: null }, t)).toBe(
      "Certification",
    );
    expect(yearsLabel(170, t)).toBe("14.2 yrs");
    expect(yearsLabel(29, t)).toBe("2.4 yrs");
  });

  it("the Asset value panel is GONE \u2014 PO instruction 2026-09-11, and its cost is stated", () => {
    // ⚠ **THIS CASE IS THE INVERSE OF WHAT IT WAS**, and the inversion is the
    // ruling rather than a convenience. It asserted the panel's presence and
    // its two figures at 2 dp. The PO removed it on 2026-09-11, quoting the
    // panel in full: *"remove this - Asset value"*. It is the ONE field-bearing
    // removal in the whole CR-092 blueprint, and the cost is real and stated:
    // `buy_value` and `present_value` are computed NOWHERE ELSE in the
    // product, so a person who used them loses them entirely.
    for (const section of [undefined, "warranty", "forecast"] as const) {
      const html = lifecycle(section);
      expect(html, `Asset value on ${section ?? "certifications"}`).not.toContain(
        t("assets.value.title"),
      );
      expect(html).not.toContain("$34,224.00");
      expect(html).not.toContain("$22,150.55");
    }
    // The server still SERVES it — the removal is a screen decision, and a
    // silently dropped field on the wire would be a different change.
    expect(LIFECYCLE.asset_value.buy_value).toBe("34224.0000");
  });

  it("§10-D3: NO GL sentence anywhere — the banned strings are absent", () => {
    const html = lifecycle();
    for (const banned of [
      "5300",
      "5400",
      "Cost &amp; Margin",
      "Cost & Margin",
      "Depreciation",
      "O&amp;M",
    ]) {
      expect(html, `D3 forbids ${JSON.stringify(banned)}`).not.toContain(banned);
    }
  });

  it("a NULL figure renders the dash — an unpriceable group fakes nothing", () => {
    const html = lifecycle("forecast");
    // The comms group has no ages, no life, no cost: three dashes on its row.
    expect(html).toContain("Comms endpoint");
    expect(html).toContain("—");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// T3 — Map (AST-03 · §10-D6)
// ══════════════════════════════════════════════════════════════════════════

describe("CR-028 W5 T3 — the Map tab", () => {
  it("renders the r10 filter bar, the count line and the three-state legend", () => {
    const html = map();
    expect(html).toContain(t("assets.map.searchPlaceholder"));
    expect(html).toContain(t("assets.map.type.all"));
    expect(html).toContain(t("assets.map.type.masters"));
    expect(html).toContain(t("assets.map.status.attention"));
    expect(html).toContain(t("assets.map.area.all"));
    // Area options come from the DATA (the premises' BR-MET-071 areas).
    expect(html).toContain(">North<");
    expect(html).toContain(">East<");
    expect(html).toContain(">South<");
    expect(html).toContain(t("assets.map.showing", { shown: 5, total: 5 }));
    expect(html).toContain(t("assets.map.legend.healthy"));
    expect(html).toContain(t("assets.map.legend.attention"));
    expect(html).toContain(t("assets.map.legend.master"));
    // The canvas div exists; Leaflet itself never loads in this render
    // (dynamic import inside an effect — static markup runs no effects).
    expect(html).toContain("data-map-canvas");
  });

  it("filterGeoAssets applies the r10 semantics, AND-combined", () => {
    const rows = GEO.assets;
    const f = (over: Partial<typeof EMPTY_GEO_FILTERS>) =>
      filterGeoAssets(rows, { ...EMPTY_GEO_FILTERS, ...over }).map((r) => r.asset_no);
    expect(f({})).toHaveLength(5);
    expect(f({ type: "master" })).toEqual(["M-MASTER-12"]);
    expect(f({ type: "sub" })).toEqual(["SM-8801"]);
    expect(f({ type: "device" })).toEqual(["BF-3301"]);
    // Meters = the meters tab (masters included — they ARE meters, r10's own
    // reading), never sub-meters or devices.
    expect(f({ type: "meter" })).toEqual(["M-4021", "M-MASTER-12", "M-4204"]);
    // Status: attention = out_of_service OR test due; active excludes both.
    expect(f({ status: "attention" })).toEqual(["M-4204", "BF-3301"]);
    expect(f({ status: "active" })).toEqual(["M-4021", "M-MASTER-12", "SM-8801"]);
    expect(f({ service: "water" })).toEqual(["M-MASTER-12", "BF-3301"]);
    expect(f({ area: "South" })).toEqual(["M-4204"]);
    expect(f({ q: "master-12" })).toContain("M-MASTER-12");
    // The sub is findable by its MASTER's number (the popup's own fact).
    expect(f({ q: "master-12" })).toContain("SM-8801");
    expect(f({ q: "elm street", area: "South" })).toEqual(["M-4204"]);
  });

  it("markerStyle draws the master's hollow ring and colors attention", () => {
    expect(geoNeedsAttention(geoRow())).toBe(false);
    expect(geoNeedsAttention(geoRow({ behavior_class: "out_of_service" }))).toBe(true);
    expect(geoNeedsAttention(geoRow({ test_due: true }))).toBe(true);
    const healthy = markerStyle(geoRow());
    expect(healthy).toMatchObject({ radius: 7, weight: 2, fillOpacity: 0.9 });
    const master = markerStyle(geoRow({ role: { kind: "master", count: 3 } }));
    expect(master).toMatchObject({ radius: 10, weight: 3, fillOpacity: 0.15 });
    const warn = markerStyle(geoRow({ behavior_class: "out_of_service" }));
    expect(warn.color).not.toBe(healthy.color);
    expect(mapVocab(GEO.assets)).toEqual({
      services: ["electric", "water"],
      areas: ["East", "North", "South"],
    });
  });

  it("§10-D7: the map surface carries NO work-order affordance or WO string", () => {
    const html = map();
    expect(html).not.toContain("WO-");
    expect(html.toLowerCase()).not.toContain("work order");
  });

  it("with nothing geocoded the tab says so instead of drawing an empty world", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    queryClient.setQueryData(assetGeoQueryKey, { assets: [] });
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TEST_TENANT}/assets`]}>
            <AssetMapTab />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(html).toContain(t("assets.map.empty.title"));
    expect(html).not.toContain("data-map-canvas");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// T4 — THE "Work R5" SWEEP (§10-D7): one test, every WO touchpoint
// ══════════════════════════════════════════════════════════════════════════
//
// The flows' own touchpoints (reassign · log-repair · retire step 2 · the add
// wizard's step-3 checkbox) are pinned by AssetLifecycle.test.tsx's D7 case
// through the ROUTER; this sweep adds the two NEW tabs and re-pins the shared
// pattern so ONE consistent posture covers the whole feature: a DISABLED
// control inside a data-work-r5 landmark whose reason is EXACTLY "Work R5".
// (The registry KPI sub-labels carry no WO clause at all — W1 dropped it.)

/** EVERY control carrying the "Work R5" title, with whether it is actually
 *  DISABLED. The per-control walk exists because the first draft of this
 *  sweep only checked the whole page for `title="Work R5"` + `disabled`
 *  ANYWHERE — and it stayed GREEN when the wrench was switched to an ENABLED
 *  tooltip (`hint`), because the Turn-into-work button still satisfied both
 *  substrings. A sweep whose output cannot distinguish pass from fail is the
 *  DEF-182 class; this one reads each control. */
export function workR5Controls(html: string): { tag: string; disabled: boolean }[] {
  const controls = html.match(/<(?:button|input)[^>]*>/g) ?? [];
  return controls
    .filter((tag) => tag.includes('title="Work R5"') || tag.includes("aria-disabled"))
    .map((tag) => ({ tag, disabled: /\bdisabled(?:=|>|\s|\/)/.test(tag + ">") }));
}

describe("CR-070 wave M — the \"Work R5\" sweep, INVERTED", () => {
  /* ⚠ **THIS SUITE USED TO ASSERT THE OPPOSITE, AND ITS FIRING IS THE POINT.**
     It read *every WO touchpoint on the new tabs is disabled with exactly
     "Work R5"* and it was correct for as long as the Work module did not
     exist. `BR-WRK-056` gives the Assets door an address and CR-070 wave M
     builds it, so the refusal expired — and this is the test that goes RED on
     the day it does, which is hard-won law 2's mirror clause working as
     written. `DEF-CWP-3925` is what it costs when nobody writes one: the
     customer portal's front page had two working doors out of eight, five of
     them refusing over screens that had shipped days earlier, with `tsc`, 391
     cases and every gate green over the top.

     REWRITTEN rather than deleted, and pointed the other way: nothing may go
     back to refusing over an address that now exists. */

  it("no control on the new tabs refuses over Work any more", () => {
    // The key itself is GONE from all eleven catalogues, so `t()` can only
    // echo the key back. A catalogue that still answered "Work R5" would mean
    // the deletion was reverted.
    expect(t("assets.flow.workR5")).not.toBe("Work R5");
    for (const [name, html] of [
      ["inventory · Parts in Work", inventory()],
      ["lifecycle · the wrench and Turn into work", lifecycle()],
      ["map", map()],
    ] as [string, string][]) {
      expect(html, name).not.toContain("data-work-r5");
      expect(html, name).not.toContain('title="Work R5"');
      expect(workR5Controls(html), name).toHaveLength(0);
    }
  });

  it("FIRES IF A DOOR IS RE-CLOSED: the live controls are present and enabled", () => {
    // An absence proves nothing on its own — a screen that rendered NO control
    // at all would pass the case above. These are the controls themselves.
    expect(inventory()).toContain("data-parts-in-work");
    // ⚠ The wrench is on 05a and the Turn-into-work panel is on 05c, so this
    // asks TWO sections rather than one page (`DEF-MET-4955`). Asking only the
    // default would have let the panel's door close unseen — which is the
    // exact failure this inverted sweep exists to catch.
    const certsHtml = lifecycle();
    const forecastHtml = lifecycle("forecast");
    const lifecycleHtml = certsHtml + forecastHtml;
    expect(certsHtml).toContain('aria-label="Raise work order"');
    expect(forecastHtml).toContain("data-turn-into-work");
    expect(forecastHtml).toContain(t("assets.lifecycle.raiseProgramme"));
    // None of them is disabled: a live-looking control that refuses is the
    // exact shape this suite was rewritten to refuse.
    for (const tag of lifecycleHtml.match(/<button[^>]*>/g) ?? []) {
      if (tag.includes("data-programme-rule")) {
        expect(/\bdisabled(?:=|>|\s|\/)/.test(tag + ">")).toBe(false);
      }
    }
  });
});
