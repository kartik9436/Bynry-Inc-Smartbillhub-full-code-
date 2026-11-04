// ── Trace ──────────────────────────────────────────────
// Change:  CR-176-BRC10 — the Add units redesign (DEF-MET-10035), over CR-089
//          U2/U3. REWRITTEN 2026-10-09: the old cases asserted the drawn shape
//          the redesign replaces (three kickers, ten review rows, the CHECK
//          box, `Or add a common area instead`); the cases that protect a
//          ruling still in force are kept below unchanged in substance.
// Drawn:   05-prototype/add-units-redesign-2026-10-09/images/01–11
// Rules:   CR-176 rules (1)–(6) · BR-MET-101 · BR-MET-119 as amended ·
//          BR-MET-007 · DEF-MET-5868 (Floor area on the add form)
// ───────────────────────────────────────────────────────
//
// ⚠ **NO DRAWN NUMBER IS ASSERTED (B14 rule 37).** The mock-up's `U-00013` and
// `101 Silver Creek Rd` are an illustration; what is pinned is the SHAPE.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { PremisesDetail, PremisesLends } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  PremiseFactsGrid,
  ReviewStep,
  TheseUnitsCard,
  UnitsFields,
  addUnitsRequest,
  addUnitsTotal,
  buildingLine,
  emptyAddUnitsForm,
  rangeText,
  renderTokens,
  resolvedUnitServices,
  runValues,
} from "./AddUnitsWizard";
import type { AddUnitsForm, ReviewRow } from "./AddUnitsWizard";
import { COMMON_AREA_KINDS } from "./meteringShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function premises(over: Partial<PremisesDetail> = {}): PremisesDetail {
  return {
    id: "p-1",
    premise_no: "P-00074",
    name: null,
    address_line: "123 Main Street",
    city: "Ottumwa",
    state: "IA",
    postal_code: "52501",
    inside_city_limits: null,
    area_code: null,
    area_name: null,
    area_parent_code: null,
    area_path: null,
    premises_type: "apartment",
    premises_type_name: "Apartments",
    services_available: ["water", "sewer", "trash"],
    owner_manager: null,
    owner: null,
    owner_unmatched: false,
    external_ref: null,
    gis_unchecked: false,
    lat: null,
    lng: null,
    gis_checked_at: null,
    gis_checked_by: null,
    status: "active",
    units: 4,
    unit_rows: [],
    units_common: 0,
    ...over,
  } as PremisesDetail;
}

function lends(over: Partial<PremisesLends> = {}, premisesOver: Partial<PremisesDetail> = {}): PremisesLends {
  return {
    premises: premises(premisesOver),
    units_today: 4,
    unit_labels: ["Unit 1", "Unit 2", "Unit 3", "Unit 5"],
    unit_labels_truncated: false,
    routes: [
      { code: "RT-004", name: null, service: null, cycle_code: "CY-002", cycle_name: null, cycle_start_day: null },
    ],
    ...over,
  };
}

function form(over: Partial<AddUnitsForm> = {}): AddUnitsForm {
  return { ...emptyAddUnitsForm("p-1"), ...over };
}

function rows(labels: string[]): ReviewRow[] {
  return labels.map((label, index) => ({ label, unitNo: `U-${String(13 + index).padStart(5, "0")}`, errors: [] }));
}

function render(node: JSX.Element): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/premises/units/new"]}>
          <Routes>
            <Route path="/:tenant/premises/units/new" element={node} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function spec(f: AddUnitsForm, commonArea?: string): Record<string, unknown> {
  return addUnitsRequest(f, commonArea).pattern as Record<string, unknown>;
}

// ── rule (2) · ONE COUNT ─────────────────────────────────────────────────────
describe("CR-176 rule (2) — the count on screen is the count created", () => {
  it("a fresh form counts ONE, because How many starts at 1 (it read 0: DEF-MET-10035)", () => {
    expect(emptyAddUnitsForm("p-1").units_per_floor).toBe("1");
    expect(addUnitsTotal(form())).toBe(1);
  });

  it("floors × how many, and an empty or broken box counts nothing", () => {
    expect(addUnitsTotal(form({ units_per_floor: "3" }))).toBe(3);
    expect(addUnitsTotal(form({ units_per_floor: "3", floors: "2" }))).toBe(6);
    expect(addUnitsTotal(form({ units_per_floor: "" }))).toBe(0);
    expect(addUnitsTotal(form({ units_per_floor: "2.5" }))).toBe(0);
  });

  it("the count the card prints is the count the request asks for", () => {
    const f = form({ units_per_floor: "3", seq_start: "6", label_pattern: "Unit {seq}" });
    const card = render(
      <TheseUnitsCard
        kind="units"
        total={addUnitsTotal(f)}
        building={lends()}
        labels={runValues("Unit {seq}", 1, 3, 6)}
        unitNumbers={[]}
        typeText="—"
        services={["water"]}
        planText="When someone moves in"
        t={t}
      />,
    );
    expect(card).toContain(">3 units<");
    expect(spec(f).units_per_floor).toBe(3);
    expect(spec(f).seq_start).toBe(6);
  });
});

// ── rule (1) · numbering from the next free start ───────────────────────────
describe("CR-176 rule (1) — the labels a start makes, and the taken refusal", () => {
  it("renders the pattern the server renders, padding included", () => {
    expect(runValues("Unit {seq}", 1, 3, 6)).toEqual(["Unit 6", "Unit 7", "Unit 8"]);
    expect(renderTokens("A-{seq:00}", 1, 4)).toBe("A-04");
    expect(runValues("{floor}{seq:00}", 2, 2, 1)).toEqual(["101", "102", "201", "202"]);
  });

  it("a range reads first to last, one value alone, nothing as a dash", () => {
    expect(rangeText(["Unit 6", "Unit 7", "Unit 8"], t)).toBe("Unit 6 to Unit 8");
    expect(rangeText(["Laundry"], t)).toBe("Laundry");
    expect(rangeText([], t)).toBe("—");
  });

  it("Next free is the help; a taken start names the labels and offers Use N", () => {
    const html = render(
      <UnitsFields
        form={form({ units_per_floor: "3", seq_start: "1", seq_start_touched: true })}
        onChange={() => undefined}
        start={1}
        nextFree={6}
        taken={["Unit 1", "Unit 2", "Unit 3"]}
        labels={runValues("Unit {seq}", 1, 3, 1)}
        unitNumbers={[]}
        t={t}
      />,
    );
    expect(html).toContain("Next free: 6");
    expect(html).toContain("Unit 1, Unit 2, Unit 3 are taken.");
    expect(html).toContain(">Use 6<");
  });

  it("How many is NOT red on a valid value (DEF-MET-10035)", () => {
    const html = render(
      <UnitsFields
        form={form()}
        onChange={() => undefined}
        start={6}
        nextFree={6}
        taken={[]}
        labels={["Unit 6"]}
        unitNumbers={[]}
        t={t}
      />,
    );
    expect(html).not.toContain('aria-invalid="true"');
    expect(html).not.toContain(t("metering.addUnits.error.howMany"));
  });

  it("the untyped start shows the server's next free number", () => {
    const html = render(
      <UnitsFields form={form()} onChange={() => undefined} start={6} nextFree={6} taken={[]} labels={["Unit 6"]} unitNumbers={[]} t={t} />,
    );
    expect(html).toMatch(/id="seq_start"[^>]*value="6"|value="6"[^>]*id="seq_start"/);
  });

  it("the two rows of three: How many · Start · Unit type, then Floor · Floor area · Creates", () => {
    const html = render(
      <UnitsFields form={form()} onChange={() => undefined} start={1} nextFree={1} taken={[]} labels={["Unit 1"]} unitNumbers={["U-00013"]} t={t} />,
    );
    const order = ["units_per_floor", "seq_start", "unit_type", "floor_label", "square_feet", "data-add-units-creates"].map(
      (needle) => html.indexOf(needle),
    );
    expect(order.every((at) => at >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    expect(html).toContain("grid-cols-3");
  });
});

// ── the building card (rule 4, DEF-MET-10035's unlabelled Not recorded) ─────
describe("the building card — every value labelled, the owner is the master account", () => {
  it("draws the six labels and never a bare Not recorded", () => {
    const html = render(<PremiseFactsGrid lends={lends()} t={t} />);
    for (const label of ["Type", "Status", "Units today", "Route and cycle", "Owner", "Services"]) {
      expect(html).toContain(`>${label}<`);
    }
    expect(html).not.toContain("Not recorded");
    expect(html).toContain("4 · Unit 1, Unit 2, Unit 3, Unit 5");
    expect(html).toContain("RT-004 · CY-002");
  });

  it("no master account reads a dash; a named one reads its name", () => {
    const none = render(<PremiseFactsGrid lends={lends()} t={t} />);
    expect(none).toMatch(/data-building-fact="owner"[\s\S]*?<dd[^>]*>—<\/dd>/);
    const named = render(
      <PremiseFactsGrid
        lends={lends({}, {
          master_account_id: "acc-1",
          master_account_no: "AC-2026-00051",
          master_account_name: "Bramble Property Group",
        } as unknown as Partial<PremisesDetail>)}
        t={t}
      />,
    );
    expect(named).toContain("Bramble Property Group");
    expect(named).not.toContain("acc-1");
  });

  it("the building line leads with the address", () => {
    expect(buildingLine(lends())).toBe("123 Main Street · P-00074 · Ottumwa, IA 52501");
  });
});

// ── rule (5) · a common area ─────────────────────────────────────────────────
describe("CR-176 rule (5) — a common area is one unit of the chosen kind, billed to the owner", () => {
  it("is ONE unit, flagged, labelled with its kind, whatever the count box held", () => {
    const f = form({ kind: "common", common_area: "laundry", units_per_floor: "9", floor_label: "2", square_feet: "850" });
    expect(addUnitsTotal(f)).toBe(1);
    const s = spec(f, "Laundry");
    expect(s).toMatchObject({ is_common_area: true, unit_type: "common_area", label_pattern: "Laundry", floors: 1, units_per_floor: 1 });
    expect(s.floor_label).toBeUndefined();
    expect(s.square_feet).toBeUndefined();
  });

  it("the kinds are the ONE declared list", () => {
    expect(COMMON_AREA_KINDS).toHaveLength(6);
  });

  it("the card says 1 common area", () => {
    const html = render(
      <TheseUnitsCard kind="common" total={1} building={lends()} labels={["Laundry"]} unitNumbers={["U-00013"]} typeText="Common area" services={["water"]} planText="When someone moves in" t={t} />,
    );
    expect(html).toContain(">1 common area<");
    expect(html).toContain("123 Main Street · P-00074");
  });
});

// ── rule (3) · services from the building, all ticked ───────────────────────
describe("CR-176 rule (3) · BR-MET-119 — services come from the building, all ticked to start", () => {
  it("an untouched control takes the WHOLE offer once the building has loaded", () => {
    expect(resolvedUnitServices(null, ["water", "sewer"], true)).toEqual(["water", "sewer"]);
  });
  it("before the building loads it resolves to nothing, and the SERVER inherits", () => {
    expect(resolvedUnitServices(null, null, false)).toBeNull();
  });
  it("a deliberate untick is honoured, empty included; a stale tick is dropped", () => {
    expect(resolvedUnitServices([], ["water"], true)).toEqual([]);
    expect(resolvedUnitServices(["electric", "water"], ["water"], true)).toEqual(["water"]);
  });
  it("the run posts services only when there is an answer", () => {
    expect(spec(form()).services).toBeUndefined();
    expect(spec(form({ services: [] })).services).toEqual([]);
  });
});

// ── what the kept controls SEND (CR-089 U2, DEF-MET-5868) ───────────────────
describe("what the controls send — the rulings the redesign keeps", () => {
  it("Floor and Floor area are sent when answered and ABSENT when not", () => {
    expect(spec(form({ floor_label: "3", square_feet: "850" }))).toMatchObject({ floor_label: "3", square_feet: 850 });
    expect(spec(form()).floor_label).toBeUndefined();
    expect(spec(form()).square_feet).toBeUndefined();
  });

  it("rule (6): a number pattern is sent only for My own pattern", () => {
    expect(spec(form({ unit_no_pattern: "A-{seq:00}", unit_no_source: "series" })).unit_no_pattern).toBeUndefined();
    expect(spec(form({ unit_no_pattern: "A-{seq:00}", unit_no_source: "pattern" })).unit_no_pattern).toBe("A-{seq:00}");
  });

  it("a plan is sent only for Pick a plan now; Starts sends a chosen date or nothing", () => {
    expect(spec(form({ plan_id: "rp-1" })).plan).toBeUndefined();
    expect(spec(form({ plan_mode: "now", plan_id: "rp-1" })).plan).toEqual({ plan_id: "rp-1", effective_from: undefined });
    expect(
      spec(form({ plan_mode: "now", plan_id: "rp-1", plan_starts_mode: "chosen", plan_starts: "2026-11-01" })).plan,
    ).toEqual({ plan_id: "rp-1", effective_from: "2026-11-01" });
  });

  it("all or none: never the bulk importer's skip-errors default", () => {
    expect(addUnitsRequest(form()).options).toEqual({ skip_errors: false, merge_duplicates: false });
  });
});

// ── Review ──────────────────────────────────────────────────────────────────
function review(over: Partial<AddUnitsForm> = {}, labels = ["Unit 6", "Unit 7", "Unit 8"]): string {
  const f = form({ units_per_floor: "3", ...over });
  return render(
    <ReviewStep
      form={f}
      lends={lends()}
      rows={rows(labels)}
      total={addUnitsTotal(f)}
      start={6}
      services={["water", "sewer", "trash"]}
      unitNumbers={[]}
      typeText="—"
      planText="When someone moves in"
      startsText="The day it is created"
      commonAreaLabel={f.kind === "common" ? "Laundry" : null}
      seriesMissing={false}
      onEdit={() => undefined}
      t={t}
    />,
  );
}

describe("Review — grouped, Edit on every row, and no CHECK box", () => {
  it("four groups in the drawn order", () => {
    const html = review();
    const at = ["Building", "Units", "Names &amp; numbers", "Plan &amp; start"].map((g) => html.indexOf(`data-review-group="${g}"`));
    expect(at.every((i) => i >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
  });

  it("every answer row carries an Edit, and an empty answer reads as a dash", () => {
    const html = review();
    const answerRows = html.split('data-review-row=""').length - 1;
    const edits = html.split(">Edit<").length - 1;
    expect(answerRows).toBe(12);
    expect(edits).toBe(answerRows);
    expect(html).toContain("3, numbered from 6");
  });

  it("This will create: one row per unit, five columns, Vacant, no meter", () => {
    const html = review();
    expect(html.split("Vacant, no meter").length - 1).toBe(3);
    for (const head of ["Label", "Unit number", "Type", "Plan", "Starts"]) expect(html).toContain(`>${head}<`);
  });

  it("the CHECK box and its two sentences are gone", () => {
    const html = review();
    expect(html).not.toContain(">CHECK<");
    expect(html).not.toContain("taken when you press Create");
    expect(html).not.toContain("Each unit starts vacant");
  });

  it("a common area reviews as Common area, Billed to the owner", () => {
    const html = review({ kind: "common", common_area: "laundry" }, ["Laundry"]);
    expect(html).toContain('data-review-group="Common area"');
    expect(html).toContain(">Billed to<");
    expect(html).toContain("The owner");
    expect(html).not.toContain('data-review-group="Units"');
  });
});

// ── rule 33 · the explanation text is gone ──────────────────────────────────
describe("B14 rules 32/33 — the sentences the redesign removed are not in the catalogue", () => {
  it("none of the retired explanation keys survive", async () => {
    const en = (await import("@/i18n/locales/en.json")).default as Record<string, string>;
    for (const key of [
      "metering.addUnits.sub",
      "metering.addUnits.building.carries",
      "metering.addUnits.floorHelp",
      "metering.addUnits.planChoiceHelp",
      "metering.addUnits.review.noteBody",
      "metering.addUnits.review.noteTitle",
      "metering.addUnits.total",
    ]) {
      expect(en[key], key).toBeUndefined();
    }
  });
});
