// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-WRK-9784 — a move-in's Field visit offered visit templates of
//           ANOTHER service, and Complete then raised no work order at all
//           (M6: water's *Opening read* picked for electric meter E-M6).
//           DEF-CUS-9785 — Move-in completed printed the raw code
//           `work_orders_not_raised` instead of its own sentence.
// Tests:    FieldVisitOrders.tsx (`layout="panel"`), customersShared.warningText
// ───────────────────────────────────────────────────────
// **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
//   * an electric list that is right because the offer held no water entry —
//     the offer here carries BOTH services' *Opening read*, and the water one
//     must be ABSENT from the electric row, not merely the electric one present;
//   * a whole-unit row narrowed by accident — the row with no meter must still
//     list both, each naming its service;
//   * a warning sentence that is right because the code happened to have a
//     `customers.account.warning.*` key — the three Work codes have none, and
//     the test asserts that before asserting the sentence.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import { warningText } from "@/features/customers/customersShared";
import i18n from "@/i18n";

import {
  FIELD_VISIT_HOLDERS_KEY,
  FIELD_VISIT_OPTIONS_KEY,
  FieldVisitOrders,
  emptyFieldVisit,
  fieldVisitProblem,
} from "./FieldVisitOrders";
import type { FieldVisitValue } from "./FieldVisitOrders";
import type { CrewList, ProposedWorkOrder, ProposedWorkOrders, RaiseOptions } from "./workEndpoints";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const OPTIONS: RaiseOptions = {
  types: [
    { id: "ty-rr", code: "RE_READ", name: "Re-read", parent_name: null, default_priority_id: null },
    { id: "ty-dr", code: "DISCONNECT_RECONNECT", name: "Disconnect/Reconnect", parent_name: null, default_priority_id: null },
  ],
  priorities: [{ id: "pr-normal", code: "normal", name: "Normal", sla_hours: 72 }],
};

const CREWS: CrewList = {
  count: 0,
  next: null,
  previous: null,
  results: [],
  counts: { rows: 0, people: 0, crews: 0, contractors: 0 },
};

function template(id: string, no: string, service: "water" | "electric", name: string, type: string): ProposedWorkOrder {
  return {
    template_id: id,
    template_no: no,
    name,
    service: { id: `s-${service}`, code: service, name: service === "water" ? "Water" : "Electric" },
    scope: "per_asset",
    sequence: 0,
    job_type: { id: type, name: type === "ty-rr" ? "Re-read" : "Disconnect/Reconnect" },
    is_gate: false,
    version: 1,
    est_duration_minutes: null,
  };
}

// M6's shape: water's visit set and electric's one, side by side in one offer.
const OFFER: ProposedWorkOrders = {
  services: ["electric", "water"],
  count: 3,
  proposed: [
    template("tpl-e-open", "ST-0031", "electric", "Opening read", "ty-rr"),
    template("tpl-w-open", "ST-0019", "water", "Opening read", "ty-rr"),
    template("tpl-w-recon", "ST-0022", "water", "Reconnect visit", "ty-dr"),
  ],
};

const METERS = [
  { value: "E-M6", label: "E-M6 · Electric", service: "electric" },
  { value: "W-M6", label: "W-M6 · Water", service: "water" },
];

function stubClient(): ApiClient {
  return {
    get: vi.fn(async () => ({ status: 200, etag: null, notModified: false, data: { results: [], count: 0 } })),
    post: vi.fn(),
  } as unknown as ApiClient;
}

function Harness(props: { initial: FieldVisitValue; onValue: (value: FieldVisitValue) => void }) {
  const [value, setValue] = useState<FieldVisitValue>(props.initial);
  props.onValue(value);
  return (
    <FieldVisitOrders
      flowKind="move_in"
      layout="panel"
      value={value}
      onChange={setValue}
      services={["electric", "water"]}
      meters={METERS}
      dateFormat="MM/DD/YYYY"
      timeZone="America/Chicago"
      t={t}
      client={stubClient()}
    />
  );
}

function mount(initial: FieldVisitValue, onValue: (value: FieldVisitValue) => void) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(FIELD_VISIT_OPTIONS_KEY, OPTIONS);
  client.setQueryData(FIELD_VISIT_HOLDERS_KEY, CREWS);
  client.setQueryData(["work", "flow-offer", "move_in", "electric,water"], OFFER);
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/brazosbend/move-ins/new"]}>
        <Routes>
          <Route path="/:tenant/move-ins/new" element={<Harness initial={initial} onValue={onValue} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function row(over: Partial<FieldVisitValue["rows"][number]> = {}): FieldVisitValue["rows"][number] {
  return { key: "r1", type_id: "", priority_id: "", due_on: "", holder: "", note: "", ...over };
}

async function optionsOf(user: ReturnType<typeof userEvent.setup>): Promise<string[]> {
  const panel = document.querySelector('[data-field-visit-layout="panel"]') as HTMLElement;
  await user.click(within(panel).getByLabelText(/^Work order/));
  return (await screen.findAllByRole("option")).map((option) => option.textContent?.trim() ?? "");
}

describe("DEF-WRK-9784 — a row's Work order list is its meter's service", () => {
  it("an electric meter is offered electric's Opening read and never water's", async () => {
    const user = userEvent.setup();
    mount({ none: false, rows: [row({ asset_no: "E-M6" })] }, () => undefined);
    const offered = await optionsOf(user);
    expect(offered).toContain("Opening read — Re-read");
    // Exactly one *Opening read*: water's is gone, not merely joined by electric's.
    expect(offered.filter((label) => label.startsWith("Opening read"))).toHaveLength(1);
    expect(offered.some((label) => label.startsWith("Reconnect visit"))).toBe(false);
    // No electric reconnect template: the TYPE is offered, which raises by type.
    expect(offered).toContain("Disconnect/Reconnect");
  });

  it("a whole-unit row keeps the whole offer, each entry naming its service", async () => {
    const user = userEvent.setup();
    mount({ none: false, rows: [row()] }, () => undefined);
    const offered = await optionsOf(user);
    expect(offered).toContain("Opening read — Re-read · Electric");
    expect(offered).toContain("Opening read — Re-read · Water");
  });

  it("picking a template keeps its service; moving For to another service is refused at the step", async () => {
    const user = userEvent.setup();
    let latest: FieldVisitValue = emptyFieldVisit();
    mount({ none: false, rows: [row({ asset_no: "W-M6" })] }, (value) => (latest = value));
    await user.click(screen.getByLabelText(/^Work order/));
    await user.click(await screen.findByRole("option", { name: "Opening read — Re-read" }));
    expect(latest.rows[0]?.template_id).toBe("tpl-w-open");
    expect(latest.rows[0]?.template_service).toBe("water");
    const serviceOf = (assetNo: string) => METERS.find((meter) => meter.value === assetNo)?.service;
    expect(fieldVisitProblem(latest, serviceOf)).toBeNull();

    // For moved to the electric meter: the SAME visit of electric replaces it.
    await user.selectOptions(screen.getByLabelText("For"), "E-M6");
    expect(latest.rows[0]?.template_id).toBe("tpl-e-open");
    expect(latest.rows[0]?.template_service).toBe("electric");
    expect(fieldVisitProblem(latest, serviceOf)).toBeNull();
  });

  it("a visit the meter's service does not have is refused at the step, not dropped at Complete", async () => {
    const user = userEvent.setup();
    let latest: FieldVisitValue = emptyFieldVisit();
    mount({ none: false, rows: [row({ asset_no: "W-M6" })] }, (value) => (latest = value));
    await user.click(screen.getByLabelText(/^Work order/));
    await user.click(await screen.findByRole("option", { name: "Reconnect visit — Disconnect/Reconnect" }));
    await user.selectOptions(screen.getByLabelText("For"), "E-M6");
    const serviceOf = (assetNo: string) => METERS.find((meter) => meter.value === assetNo)?.service;
    expect(latest.rows[0]?.template_id).toBe("tpl-w-recon");
    expect(fieldVisitProblem(latest, serviceOf)).toBe("work.order.template_wrong_service");
    expect(screen.getByText(i18n.t("work.order.template_wrong_service"))).toBeInTheDocument();
  });
});

describe("DEF-CUS-9785 — Move-in completed reads a warning's own sentence", () => {
  const WORK_WARNINGS = [
    { code: "work_orders_not_raised", message_key: "work.fromFlows.notRaised", br_ref: "BR-WRK-055" },
    { code: "work_order_not_assigned", message_key: "work.fromFlows.notAssigned", params: { order: "WO-0101" } },
    { code: "work_order_not_scheduled", message_key: "work.fromFlows.notScheduled", params: { order: "WO-0102" } },
  ];

  it.each(WORK_WARNINGS)("$code renders its sentence, never the code", (warning) => {
    // The precondition that made it a defect: no code-keyed sentence exists.
    expect(i18n.exists(`customers.account.warning.${warning.code}`)).toBe(false);
    const text = warningText(warning, t);
    expect(text).not.toMatch(/[a-z]+_[a-z_]+/);
    expect(text).toBe(i18n.t(warning.message_key, warning.params ?? {}));
  });

  it("every language says it in its own words", async () => {
    for (const language of ["de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"]) {
      const translate = i18n.getFixedT(language);
      const own = (key: string, params?: Record<string, unknown>) => translate(key, params);
      expect(warningText(WORK_WARNINGS[0]!, own)).not.toBe("work_orders_not_raised");
      expect(warningText(WORK_WARNINGS[0]!, own)).not.toBe(i18n.t("work.fromFlows.notRaised"));
    }
  });

  it("a code-keyed sentence still wins, and an unknown code still renders", () => {
    expect(warningText({ code: "initial_reads_not_committed" }, t)).toBe("No opening read was recorded.");
    expect(warningText({ code: "something_new" }, t)).toBe("something_new");
  });
});
