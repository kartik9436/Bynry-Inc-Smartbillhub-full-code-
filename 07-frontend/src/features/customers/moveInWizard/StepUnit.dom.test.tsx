// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.18–P2.21 · P2.35 (lane MVI-WIZ-UNIT) — images 30, 31, 32
// Tests:    StepUnit.tsx (the step), FieldVisitOrders.tsx (`layout="panel"`),
//           moveShared.MoveInUnitPick (the card inside the picker's box)
// ───────────────────────────────────────────────────────
// **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
//   * a table that draws the sub-meter as a meter — the nested row is found
//     by its `data-editable-nested` mark AND its *Sub-meter* pill;
//   * a size printed as its code — `W-58` must be ABSENT, not merely
//     `Water 5/8"` present;
//   * *Below the last read.* drawn from the client's own comparison — the
//     warning appears only after the stub SERVER answered `below_last_read`,
//     and the stub is asked with exactly the typed value;
//   * a Field visit payload that carries the template because the type's
//     default happened to match — the template is picked by its label.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import i18n from "@/i18n";
import {
  FIELD_VISIT_HOLDERS_KEY,
  FIELD_VISIT_OPTIONS_KEY,
  emptyFieldVisit,
  fieldVisitPayload,
} from "@/features/work/FieldVisitOrders";
import type { FieldVisitValue } from "@/features/work/FieldVisitOrders";
import type { CrewList, ProposedWorkOrders, RaiseOptions } from "@/features/work/workEndpoints";

import { MoveInUnitPick } from "../moveShared";
import { datedReadsDraft, readsPayloadPart } from "../moveReadsCapture";
import type { ReadsDraft } from "../moveReadsCapture";
import type { MoveInWizardContext } from "./moveInWizardContext";
import {
  StepUnit,
  meterLines,
  missingOpeningReads,
  stepUnitVerdict,
  testDue,
  useStepUnitOwn,
} from "./StepUnit";
import type { StepUnitFacts, StepUnitMeters } from "./StepUnit";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const UNIT = "u-308";

function facts(over: Partial<StepUnitFacts["history"]> = {}): StepUnitFacts {
  return {
    unit: {
      id: UNIT,
      unit_no: "SCW-U-308",
      label: "Unit 3B",
      unit_type: "residential",
      floor_label: "2nd floor",
      square_feet: 850,
      is_common_area: false,
      occupancy: "vacant",
      address: { line1: "8 Quarry Lane", city: "Ottumwa", state: "IA", postal_code: "52501" },
    },
    building: {
      premise_no: "P-00063",
      name: "Kestrel Park ph. 2",
      premises_type: "residential",
      premises_type_name: "Residential",
      inside_city_limits: true,
      area_code: "SE",
      area_name: "SE",
      parcel: "12-345",
      parcel_verified: true,
      routes: [{ code: "R4", name: "Route 4", service: "water", cycle_code: "C2", cycle_name: "Cycle 2" }],
    },
    owner: { name: "Kestrel Holdings", account_no: "AC-2026-00050", status_name: "Active", billed_while_vacant: true },
    history: { first_occupant: true, previous: null, plan_changes: 2, ...over },
  };
}

function meters(): StepUnitMeters {
  return {
    unit_id: UNIT,
    services: [
      {
        service: "water",
        start: true,
        metered: true,
        meters: [
          {
            asset_no: "W-5000",
            kind: "meter",
            type_name: "Water meter",
            location_note: "Basement, left of stairs",
            size_class: "W-58",
            size_name: 'Water 5/8"',
            reads_as: { multiplier: "1.000000", digits: 6 },
            unit: "kgal",
            last_read: { value: "1024.000000", unit: "kgal", read_at: "2026-10-04" },
            needs_opening_read: true,
            last_test_date: null,
            test_interval_months: null,
            facts: {
              serial_no: "77123",
              meter_type_name: "Positive displacement",
              read_method_name: "Manual read",
              installed_on: "2026-01-12",
              manufacturer: "Badger",
              model: "M25",
              seal_no: "S-0912",
              certified_to: "2027-03-03",
            },
            children: [
              // The SERVER sends them by number (BF before W); the table draws the
              // read sub-meter first, as image 30 does.
              {
                asset_no: "BF-0217",
                kind: "behind_the_meter",
                type_name: "Backflow preventer",
                location_note: null,
                size_class: null,
                size_name: null,
                reads_as: null,
                unit: null,
                last_read: null,
                needs_opening_read: false,
                last_test_date: "2026-03-15",
                test_interval_months: 12,
                children: [],
              },
              {
                asset_no: "W-5000-S1",
                kind: "sub_meter",
                type_name: "Sub-meter",
                location_note: "Irrigation · side yard",
                size_class: "W-58",
                size_name: 'Water 5/8"',
                reads_as: { multiplier: "1.000000", digits: 5 },
                unit: "kgal",
                last_read: { value: "212.000000", unit: "kgal", read_at: "2026-10-04" },
                needs_opening_read: true,
                last_test_date: null,
                test_interval_months: null,
                children: [],
              },
            ],
          },
        ],
      },
      { service: "sewer", start: true, metered: false, meters: [] },
    ],
    unplaced: [],
    counts: { services: 2, meters: 2, devices: 1, opening_reads_needed: 2 },
    assets_readable: true,
  };
}

const OPTIONS: RaiseOptions = {
  types: [
    { id: "ty-read", code: "MOVE_IN_READ", name: "Reading", parent_name: null, default_priority_id: null },
    { id: "ty-turn", code: "TURN_ON", name: "Turn-on", parent_name: null, default_priority_id: null },
  ],
  priorities: [{ id: "pr-normal", code: "normal", name: "Normal", sla_hours: 72 }],
};

const CREWS: CrewList = {
  count: 1,
  next: null,
  previous: null,
  results: [
    { id: "te-p", kind: "person", name: "R. Patel", slug: "r-patel", role_label: null, skills: [], certifications: [], shift: null, status: "on_shift", unavailable_reason: null },
  ],
  counts: { rows: 1, people: 1, crews: 0, contractors: 0 },
};

const OFFER: ProposedWorkOrders = {
  services: ["water", "sewer"],
  count: 1,
  proposed: [
    {
      template_id: "tpl-mi",
      template_no: "T-0007",
      name: "Move-in read",
      service: { id: "s-w", code: "water", name: "Water" },
      scope: "per_asset",
      sequence: 0,
      job_type: { id: "ty-read", name: "Reading" },
      is_gate: false,
      version: 1,
      est_duration_minutes: 15,
    },
  ],
};

interface Probe {
  chosen: string[] | null;
  reads: ReadsDraft;
  visit: FieldVisitValue;
  posts: { path: string; body: unknown }[];
  /** DEF-CUS-10050 — what `POST /integrations/meter-reading/fetch` answers. */
  fetchAnswer?: unknown;
}

function stubClient(probe: Probe): ApiClient {
  return {
    get: vi.fn(async (path: string) => ({
      status: 200,
      etag: null,
      notModified: false,
      data: path.includes("/work/candidates")
        ? {
            results: [
              {
                kind: "person",
                id: "te-p",
                name: "R. Patel",
                best_fit: true,
                advice: { skill: null, has_skill: true, area_match: false, off_that_day: false, jobs_that_day: 2, certifications_lapsed: [] },
              },
            ],
            count: 1,
            next: null,
            previous: null,
          }
        : {},
    })),
    post: vi.fn(async (path: string, body: unknown) => {
      probe.posts.push({ path, body });
      if (path === "/integrations/meter-reading/fetch") {
        return { status: 200, etag: null, notModified: false, data: probe.fetchAnswer };
      }
      const reads = (body as { reads: { meter_no: string; value: string }[] }).reads;
      return {
        status: 200,
        etag: null,
        notModified: false,
        data: {
          rows: reads.map((row) => ({
            meter_no: row.meter_no,
            value: row.value,
            last_value: row.meter_no === "W-5000" ? "1024" : "212",
            unit: "kgal",
            below_last_read: row.meter_no === "W-5000" ? Number(row.value) < 1024 : Number(row.value) < 212,
          })),
        },
      };
    }),
  } as unknown as ApiClient;
}

function Harness(props: {
  probe: Probe;
  withPicker?: boolean;
  initialVisit?: FieldVisitValue;
  onCtx?: (ctx: MoveInWizardContext) => void;
}) {
  const [chosen, setChosen] = useState<string[] | null>(null);
  const [reads, setReads] = useState<ReadsDraft>({});
  const [visit, setVisit] = useState<FieldVisitValue>(props.initialVisit ?? emptyFieldVisit());
  const [openedAt, setOpenedAt] = useState("2026-10-10");
  const unitOwn = useStepUnitOwn();
  props.probe.chosen = chosen;
  props.probe.reads = reads;
  props.probe.visit = visit;
  const offer = ["water", "sewer"];
  const ctx = {
    t,
    client: stubClient(props.probe),
    dateFormat: "MM/DD/YYYY",
    timeZone: "America/Chicago",
    standalone: props.withPicker === true,
    picker:
      props.withPicker === true ? (
        <MoveInUnitPick
          unitId={UNIT}
          onUnitChange={() => undefined}
          options={[{ value: UNIT, label: "Kestrel Park ph. 2 · SCW-U-308" }]}
          unitsLoading={false}
          unitsFailed={false}
          predecessor={null}
          resolved
          accountsFailedReason={null}
          t={t}
        />
      ) : null,
    unitId: UNIT,
    outgoing: null,
    pickedUnit: null,
    unitLabel: "SCW-U-308",
    unitFree: true,
    firstOccupant: true,
    outgoingUnitId: UNIT,
    serviceOffer: offer,
    ticked: chosen ?? offer,
    setChosenServices: (next: string[] | null) => setChosen(next),
    offerLoading: false,
    offerFailed: false,
    openedAt,
    setOpenedAt,
    earliest: null,
    dateProblem: null,
    readsDraft: reads,
    setReadsDraft: setReads,
    fieldVisit: visit,
    setFieldVisit: setVisit,
    tried: { unit: false, customer: false, billing: false, review: false },
    markTried: () => undefined,
    goToStep: () => undefined,
    own: { unit: unitOwn },
  } as unknown as MoveInWizardContext;
  props.onCtx?.(ctx);
  return <StepUnit ctx={ctx} />;
}

function mount(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(["move-in-step-unit-facts", UNIT], facts());
  client.setQueryData(["move-in-step-unit-meters", UNIT], meters());
  client.setQueryData(FIELD_VISIT_OPTIONS_KEY, OPTIONS);
  client.setQueryData(FIELD_VISIT_HOLDERS_KEY, CREWS);
  client.setQueryData(["work", "flow-offer", "move_in", "sewer,water"], OFFER);
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/brazosbend/move-ins/new"]}>
        <Routes>
          <Route path="/:tenant/move-ins/new" element={node} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const newProbe = (): Probe => ({ chosen: null, reads: {}, visit: emptyFieldVisit(), posts: [] });

describe("P2.18 · image 30 — the Unit box: picker, card, four groups", () => {
  it("draws the card INSIDE the picker's box, headed Unit, with no second Unit panel", () => {
    mount(<Harness probe={newProbe()} withPicker />);
    const boxes = document.querySelectorAll('[data-move-pick="unit"]');
    expect(boxes).toHaveLength(1);
    const box = boxes[0] as HTMLElement;
    expect(within(box).getByRole("heading", { name: "Unit" })).toBeInTheDocument();
    expect(within(box).getByLabelText(/Vacant unit/)).toBeInTheDocument();
    expect(within(box).getByText("Occupied units aren't listed.")).toBeInTheDocument();
    expect(box.querySelector('[data-unit-card="ready"]')).not.toBeNull();
    // The two old sentences under the picker are not drawn twice: the card's
    // History group carries the fact.
    expect(within(box).queryByText("First occupant of this unit.")).toBeNull();
    // The panels the old step drew are gone.
    expect(screen.queryByText("Which unit are they moving into?")).toBeNull();
    expect(screen.queryByText("Start date & initial meter read.")).toBeNull();
  });

  it("the header line, its three chips, and the four groups in the drawn order", () => {
    mount(<Harness probe={newProbe()} />);
    const card = document.querySelector('[data-unit-card="ready"]') as HTMLElement;
    expect(within(card).getByText("SCW-U-308 · Unit 3B")).toBeInTheDocument();
    expect(within(card).getByText("8 Quarry Lane, Ottumwa, IA 52501 · Kestrel Park ph. 2")).toBeInTheDocument();
    const chips = card.querySelector("[data-unit-card-chips]") as HTMLElement;
    expect(chips.textContent).toContain("Vacant");
    expect(chips.textContent).toContain("Residential");
    expect(chips.textContent).toContain("First occupant");
    const groups = [...card.querySelectorAll("[data-unit-group]")].map((node) => node.getAttribute("data-unit-group"));
    expect(groups).toEqual(["building", "unit", "owner", "history"]);
    const text = (name: string) => (card.querySelector(`[data-unit-group="${name}"]`) as HTMLElement).textContent ?? "";
    expect(text("building")).toContain("P-00063 · Kestrel Park ph. 2");
    expect(text("building")).toContain("Residential · inside city limits");
    expect(text("building")).toContain("Area SE · Parcel 12-345 · Verified");
    expect(text("building")).toContain("Route Route 4 · Cycle Cycle 2");
    expect(text("unit")).toContain("Residential · 2nd floor");
    expect(text("unit")).toContain("850 sq ft");
    expect(text("unit")).toContain("Not a common area");
    expect(text("owner")).toContain("Kestrel Holdings");
    expect(text("owner")).toContain("AC-2026-00050");
    expect(text("owner")).toContain("Billed while vacant");
    expect(text("history")).toContain("First occupant");
    expect(text("history")).toContain("Plan changed 2 times");
    // *see* opens the unit's plan history, under the tenant.
    const see = within(card).getByRole("link", { name: "see" });
    expect(see).toHaveAttribute("href", `/brazosbend/premises/units/${UNIT}?tab=plan`);
  });
});

describe("P2.19 · the Move-in date box", () => {
  it("is its own box with a required date and the drawn help line", () => {
    mount(<Harness probe={newProbe()} />);
    const box = document.querySelector("[data-move-in-date]") as HTMLElement;
    expect(within(box).getByRole("heading", { name: "Move-in date" })).toBeInTheDocument();
    expect(box.querySelector("#opened_at")).not.toBeNull();
    expect(within(box).getByText("Rates and reads use this date.")).toBeInTheDocument();
  });
});

describe("P2.20 · images 30–32 — Services and meters", () => {
  it("the drawn columns, the meter tree, and the fact and the footer", () => {
    mount(<Harness probe={newProbe()} />);
    const table = document.querySelector('[data-array="move-in-meters"]') as HTMLElement;
    const heads = [...table.querySelectorAll("thead th")].map((th) => th.textContent?.trim());
    expect(heads.slice(0, 7)).toEqual(["Start", "Service", "Meter", "Size", "Reads as", "Last read", "Opening read* · Read date*"]);
    expect(within(table).getByText("2 services · 2 meters · 1 device")).toBeInTheDocument();
    expect(within(table).getByText("2 of 2 services start · 2 opening reads needed")).toBeInTheDocument();
    // The size as the tenant names it, never its code (B14 rule 31).
    expect(table.textContent).toContain('Water 5/8"');
    expect(table.textContent).not.toContain("W-58");
    expect(table.textContent).toContain("×1 · 6 digits");
    expect(table.textContent).toContain("1,024 kgal");
    // The sub-meter and the device hang off their meter.
    const nested = [...table.querySelectorAll("tr[data-editable-nested]")];
    expect(nested).toHaveLength(2);
    expect(nested[0].textContent).toContain("Sub-meter");
    expect(nested[0].textContent).toContain("W-5000-S1");
    expect(nested[1].textContent).toContain("Behind the meter");
    expect(nested[1].textContent).toContain("Not read · test due 03/15/2027");
    // Sewer has no meter: one line, a Start tick, *Not metered*, no read box.
    expect(table.textContent).toContain("Not metered");
    expect(table.querySelectorAll('input[id^="moveIn-open-read-"][id$="-value"]')).toHaveLength(2);
  });

  it("▸ opens the meter's facts on one line under it (image 31) and ▾ closes it", async () => {
    const user = userEvent.setup();
    mount(<Harness probe={newProbe()} />);
    expect(document.querySelector('[data-meter-facts="W-5000"]')).toBeNull();
    await user.click(screen.getByRole("button", { name: "Show W-5000 details" }));
    const line = document.querySelector('[data-meter-facts="W-5000"]') as HTMLElement;
    expect(line.textContent).toBe(
      "W-5000 · SN 77123 · Positive displacement · Manual read · Installed 01/12/2026 · Badger M25 · Seal S-0912 · Certified to 03/03/2027",
    );
    await user.click(screen.getByRole("button", { name: "Hide W-5000 details" }));
    expect(document.querySelector('[data-meter-facts="W-5000"]')).toBeNull();
  });

  it("Below the last read. appears once the SERVER says so, for the value typed (image 32)", async () => {
    const user = userEvent.setup();
    const probe = newProbe();
    mount(<Harness probe={probe} />);
    await user.type(screen.getByLabelText(/^Opening read for W-5000\*?$/), "1000");
    await waitFor(() => expect(screen.getByText("Below the last read.")).toBeInTheDocument(), { timeout: 2000 });
    const asked = probe.posts.at(-1);
    expect(asked?.path).toBe(`/units/${UNIT}/move-in-meters/check`);
    expect(asked?.body).toEqual({ reads: [{ meter_no: "W-5000", value: "1000" }] });
    // The reading rides the payload keyed by its NUMBER.
    expect(probe.reads["W-5000"]?.meterNo).toBe("W-5000");
    await user.clear(screen.getByLabelText(/^Opening read for W-5000\*?$/));
    await user.type(screen.getByLabelText(/^Opening read for W-5000\*?$/), "1031");
    await waitFor(() => expect(screen.queryByText("Below the last read.")).toBeNull(), { timeout: 2000 });
  });

  it("unticking Start takes the service off the move-in and drops its typed reads", async () => {
    const user = userEvent.setup();
    const probe = newProbe();
    mount(<Harness probe={probe} />);
    await user.type(screen.getByLabelText(/^Opening read for W-5000\*?$/), "1031");
    await user.click(screen.getByRole("checkbox", { name: "Start Water" }));
    expect(probe.chosen).toEqual(["sewer"]);
    expect(Object.keys(probe.reads)).toEqual([]);
    expect(document.querySelectorAll('input[id^="moveIn-open-read-"][id$="-value"]')).toHaveLength(0);
    await user.click(screen.getByRole("checkbox", { name: "Start Water" }));
    expect(probe.chosen).toEqual(["water", "sewer"]);
  });

  it("opening reads are REQUIRED as drawn — unless a field visit is booked", () => {
    const lines = meterLines(meters());
    const started = ["water", "sewer"];
    expect(missingOpeningReads(lines, started, {}, emptyFieldVisit())).toEqual(["W-5000", "W-5000-S1"]);
    const typed: ReadsDraft = {
      "W-5000": { meterNo: "W-5000", value: "1031", estimate: false, readAt: "" },
      // A draft parked under the old table is keyed by asset id.
      "ast-1": { meterNo: "W-5000-S1", value: "214", estimate: false, readAt: "" },
    };
    expect(missingOpeningReads(lines, started, typed, emptyFieldVisit())).toEqual([]);
    const booked: FieldVisitValue = {
      none: false,
      rows: [{ key: "r", type_id: "ty-read", priority_id: "", due_on: "", holder: "", note: "" }],
    };
    expect(missingOpeningReads(lines, started, {}, booked)).toEqual([]);
    // A service that does not start needs nothing.
    expect(missingOpeningReads(lines, ["sewer"], {}, emptyFieldVisit())).toEqual([]);
    expect(testDue("2026-03-15", 12)).toBe("2027-03-15");
    expect(testDue(null, 12)).toBeNull();
  });

  it("the verdict holds Continue on a missing read and lets it pass once typed", async () => {
    const user = userEvent.setup();
    const probe = newProbe();
    let latest: MoveInWizardContext | null = null;
    mount(<Harness probe={probe} onCtx={(ctx) => (latest = ctx)} />);
    expect(stepUnitVerdict(latest as unknown as MoveInWizardContext)).toBe(false);
    await user.type(screen.getByLabelText(/^Opening read for W-5000\*?$/), "1031");
    await user.type(screen.getByLabelText(/^Opening read for W-5000-S1\*?$/), "214");
    expect(stepUnitVerdict(latest as unknown as MoveInWizardContext)).toBe(true);
  });
});

describe("P2.21 · image 30 — Field visit", () => {
  it("Visit needed at the right; + Add work order opens a row due on the move-in date", async () => {
    const user = userEvent.setup();
    const probe = newProbe();
    mount(<Harness probe={probe} />);
    const panel = document.querySelector('[data-field-visit-layout="panel"]') as HTMLElement;
    expect(within(panel).getByRole("checkbox", { name: "Visit needed" })).toBeChecked();
    expect(within(panel).getByText("Raised when you complete")).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "+ Add work order" }));
    const heads = [...panel.querySelectorAll("thead th")].map((th) => th.textContent?.trim());
    expect(heads.slice(0, 8)).toEqual(["#", "Work order*", "For", "Priority", "Due", "Window", "Assign to", "Note"]);
    expect(probe.visit.rows).toHaveLength(1);
    expect(probe.visit.rows[0]?.due_on).toBe("2026-10-10");
  });

  it("one Work order field names a TEMPLATE; For, Window and Assign to reach the payload", async () => {
    const user = userEvent.setup();
    const probe = newProbe();
    mount(<Harness probe={probe} />);
    const panel = document.querySelector('[data-field-visit-layout="panel"]') as HTMLElement;
    await user.click(within(panel).getByRole("button", { name: "+ Add work order" }));
    await user.click(within(panel).getByLabelText(/^Work order/));
    await user.click(await screen.findByRole("option", { name: "Move-in read · 15 min — Reading" }));
    await user.selectOptions(within(panel).getByLabelText("For"), "W-5000");
    await user.selectOptions(within(panel).getByLabelText("Window"), "morning");
    await user.selectOptions(within(panel).getByLabelText("Assign to"), "technician:te-p");
    await waitFor(() => expect(within(panel).getByText("Best fit · 2 jobs that day")).toBeInTheDocument(), {
      timeout: 2000,
    });
    expect(fieldVisitPayload(probe.visit)).toEqual({
      orders: [
        {
          type_id: "ty-read",
          priority_id: "pr-normal",
          due_on: "2026-10-10",
          technician_id: "te-p",
          template_id: "tpl-mi",
          asset_no: "W-5000",
          window_start: "2026-10-10T08:00:00",
          window_end: "2026-10-10T12:00:00",
        },
      ],
    });
  });

  it("unticking Visit needed is the answer `none`, and the table goes", async () => {
    const user = userEvent.setup();
    const probe = newProbe();
    mount(<Harness probe={probe} />);
    const panel = document.querySelector('[data-field-visit-layout="panel"]') as HTMLElement;
    await user.click(within(panel).getByRole("checkbox", { name: "Visit needed" }));
    expect(probe.visit.none).toBe(true);
    expect(fieldVisitPayload(probe.visit)).toEqual({ none: true });
    expect(within(panel).queryByRole("button", { name: "+ Add work order" })).toBeNull();
  });
});

describe("DEF-CUS-9734 — the no-opening-read warning is the fact alone", () => {
  it("says no read was recorded, and nothing about a batch upload (B14 rule 33)", () => {
    // The server sends this ONLY when the move-in captured no reading
    // (`services.move_in` filters it otherwise), so the fact is true; the
    // old second sentence was rationale and false since CR-038 W9.
    const sentence = i18n.t("customers.account.warning.initial_reads_not_committed");
    expect(sentence).toBe("No opening read was recorded.");
    expect(sentence.split(/\s+/).length).toBeLessThanOrEqual(6);
  });
});

// ── DEF-CUS-10050 — *Fetch reading* on each metered row (PO 2026-10-11) ─────
// WHAT WOULD MAKE THESE PASS WRONGLY: a button on every row (sewer and the
// device are counted ABSENT, not the meters merely present); a reading drawn
// from the stub without the request (the request body is asserted); a fetched
// value that locks the box (it is typed over and the draft read back).
describe("DEF-CUS-10050 — Fetch reading on a metered row", () => {
  const fetchButton = (meter: string) => screen.getByRole("button", { name: `Fetch reading for ${meter}` });

  it("draws the icon on the two metered rows only — not sewer, not the device", () => {
    mount(<Harness probe={newProbe()} />);
    const table = document.querySelector('[data-array="move-in-meters"]') as HTMLElement;
    const marks = [...table.querySelectorAll("[data-fetch-reading]")].map((node) =>
      node.getAttribute("data-fetch-reading"),
    );
    expect(marks).toEqual(["W-5000", "W-5000-S1"]);
    expect(fetchButton("W-5000")).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Fetch reading for BF-0217" })).toBeNull();
    const sewer = within(table).getByText("Not metered").closest("tr") as HTMLElement;
    expect(sewer.querySelector("[data-fetch-reading]")).toBeNull();
  });

  it("not connected: says so beside the row and leaves the box empty", async () => {
    const user = userEvent.setup();
    const probe = newProbe();
    probe.fetchAnswer = {
      result: "not_connected",
      reading: null,
      message_key: "integrations.meterReading.not_connected",
    };
    mount(<Harness probe={probe} />);
    await user.click(fetchButton("W-5000"));
    const cell = document.querySelector('[data-fetch-reading="W-5000"]') as HTMLElement;
    await waitFor(() => expect(within(cell).getByText("Provider is not connected.")).toBeInTheDocument());
    expect(probe.posts.at(-1)).toEqual({
      path: "/integrations/meter-reading/fetch",
      body: { meter_no: "W-5000" },
    });
    expect(screen.getByLabelText(/^Opening read for W-5000\*?$/)).toHaveValue("");
    expect(probe.reads["W-5000"]).toBeUndefined();
  });

  it("fetched: fills Opening read with the value and shows its read date", async () => {
    const user = userEvent.setup();
    const probe = newProbe();
    probe.fetchAnswer = {
      result: "fetched",
      reading: { meter_no: "W-5000", value: "3004", unit: "kgal", read_on: "2026-10-11" },
      message_key: null,
    };
    mount(<Harness probe={probe} />);
    await user.click(fetchButton("W-5000"));
    await waitFor(() => expect(screen.getByLabelText(/^Opening read for W-5000\*?$/)).toHaveValue("3004"));
    expect(screen.getByText("Read on 10/11/2026")).toBeInTheDocument();
    // The head-end's date rides the draft with the value.
    expect(probe.reads["W-5000"]).toMatchObject({ meterNo: "W-5000", value: "3004", readAt: "2026-10-11" });
  });

  it("manual typing still works, and overwrites a fetched value", async () => {
    const user = userEvent.setup();
    const probe = newProbe();
    probe.fetchAnswer = {
      result: "fetched",
      reading: { meter_no: "W-5000", value: "3004", unit: "kgal", read_on: "2026-10-11" },
      message_key: null,
    };
    mount(<Harness probe={probe} />);
    // A row never fetched types exactly as before.
    await user.type(screen.getByLabelText(/^Opening read for W-5000-S1\*?$/), "215");
    expect(probe.reads["W-5000-S1"]).toMatchObject({ value: "215", readAt: "" });
    await user.click(fetchButton("W-5000"));
    const box = screen.getByLabelText(/^Opening read for W-5000\*?$/);
    await waitFor(() => expect(box).toHaveValue("3004"));
    await user.clear(box);
    await user.type(box, "3010");
    expect(box).toHaveValue("3010");
    expect(probe.reads["W-5000"]).toMatchObject({ value: "3010", readAt: "" });
    expect(screen.queryByText("Read on 10/11/2026")).toBeNull();
  });

  it("no reading, or a provider error: one short line saying so", async () => {
    const user = userEvent.setup();
    const probe = newProbe();
    probe.fetchAnswer = { result: "no_reading", reading: null, message_key: "integrations.meterReading.no_reading" };
    mount(<Harness probe={probe} />);
    await user.click(fetchButton("W-5000"));
    await waitFor(() => expect(screen.getByText("No reading for this meter.")).toBeInTheDocument());
    probe.fetchAnswer = { result: "unavailable", reading: null, message_key: "integrations.meterReading.unavailable" };
    await user.click(fetchButton("W-5000-S1"));
    await waitFor(() => expect(screen.getByText("Provider could not give a reading.")).toBeInTheDocument());
    expect(screen.getByLabelText(/^Opening read for W-5000-S1\*?$/)).toHaveValue("");
  });
});

// ── DEF-CUS-10165 — the opening read's READ DATE (PO 2026-10-17) ───────────
// *"Move-in, step 1 (opening) - read date is required"*. WHAT WOULD MAKE
// THESE PASS WRONGLY: a date box that shows the move-in day while the payload
// sends none (the payload builder is asserted); a refusal drawn without the
// verdict holding Continue (both are asserted); a check against a clock other
// than the tenant's (the harness zone is America/Chicago and today is passed
// through `todayInZone`).
describe("DEF-CUS-10165 — Read date per opening read", () => {
  const dateBox = (meter: string) => screen.getByLabelText(new RegExp(`^Read date for ${meter}\\*?$`));
  const problem = (meter: string) =>
    document.querySelector(`[data-meter-reading-date="${meter}"]`)?.getAttribute("data-read-date-problem");

  it("opens on the move-in date for every read meter, with today as its bound", () => {
    mount(<Harness probe={newProbe()} />);
    expect(dateBox("W-5000")).toHaveValue("10/10/2026");
    expect(dateBox("W-5000-S1")).toHaveValue("10/10/2026");
    expect(screen.queryByLabelText(/^Read date for BF-0217/)).toBeNull();
    // No Estimate on move-in (PO: "estimate will not be reuired in move in").
    expect(screen.queryByLabelText(/Estimate/)).toBeNull();
  });

  it("a date before the meter's last reading is named and holds Continue", async () => {
    const user = userEvent.setup();
    let latest: MoveInWizardContext | null = null;
    const probe = newProbe();
    mount(<Harness probe={probe} onCtx={(ctx) => (latest = ctx)} />);
    await user.type(screen.getByLabelText(/^Opening read for W-5000\*?$/), "1031");
    await user.type(screen.getByLabelText(/^Opening read for W-5000-S1\*?$/), "214");
    expect(stepUnitVerdict(latest as unknown as MoveInWizardContext)).toBe(true);
    await user.clear(dateBox("W-5000"));
    await user.type(dateBox("W-5000"), "10/01/2026");
    expect(probe.reads["W-5000"]?.readAt).toBe("2026-10-01");
    expect(problem("W-5000")).toBe("before_last");
    expect(screen.getByText("Earlier than the last reading.")).toBeInTheDocument();
    expect(stepUnitVerdict(latest as unknown as MoveInWizardContext)).toBe(false);
  });

  it("a date after today is named", async () => {
    const user = userEvent.setup();
    const probe = newProbe();
    mount(<Harness probe={probe} />);
    await user.type(screen.getByLabelText(/^Opening read for W-5000\*?$/), "1031");
    await user.clear(dateBox("W-5000"));
    await user.type(dateBox("W-5000"), "12/31/2099");
    expect(problem("W-5000")).toBe("future");
    expect(screen.getByText("Read date is after today.")).toBeInTheDocument();
  });

  it("an earlier lawful date rides the payload; an untouched row sends the move-in date", async () => {
    const user = userEvent.setup();
    const probe = newProbe();
    mount(<Harness probe={probe} />);
    await user.type(screen.getByLabelText(/^Opening read for W-5000\*?$/), "1031");
    await user.type(screen.getByLabelText(/^Opening read for W-5000-S1\*?$/), "214");
    await user.clear(dateBox("W-5000"));
    await user.type(dateBox("W-5000"), "10/08/2026");
    expect(problem("W-5000")).toBe("");
    const rows = readsPayloadPart("initial_reads", datedReadsDraft(probe.reads, "2026-10-10")).initial_reads;
    expect(rows).toEqual([
      { meter_no: "W-5000", value: "1031", read_at: "2026-10-08" },
      { meter_no: "W-5000-S1", value: "214", read_at: "2026-10-10" },
    ]);
  });

  it("a fetched reading keeps the meter's own date and locks the date box", async () => {
    const user = userEvent.setup();
    const probe = newProbe();
    probe.fetchAnswer = {
      result: "fetched",
      reading: { meter_no: "W-5000", value: "3004", unit: "kgal", read_on: "2026-10-11" },
      message_key: null,
    };
    mount(<Harness probe={probe} />);
    await user.click(screen.getByRole("button", { name: "Fetch reading for W-5000" }));
    await waitFor(() => expect(dateBox("W-5000")).toHaveValue("10/11/2026"));
    expect(dateBox("W-5000")).toBeDisabled();
    expect(screen.getByText("Date from the meter.")).toBeInTheDocument();
  });
});
