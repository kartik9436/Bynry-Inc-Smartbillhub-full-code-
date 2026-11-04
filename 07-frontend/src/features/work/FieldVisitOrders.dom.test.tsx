// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-6363 — the shared field-visit table (FieldVisitOrders.tsx)
// Rules:    PO 2026-09-23 (the move-in's work-order table, as shown and
//           approved) · BR-WRK-055 (raised at save) · B14 rule 38 (inline rows)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE WORKED ROWS ARE THE ONES THE PO APPROVED**: *Disconnection/Reconnection
// · High · 01-Aug-26 · <a crew> · Not raised yet · "Turn water on at curb"* and
// *Re-read · Normal · — · Unassigned · Not raised yet · "Check W-5041 opening
// read"*. They are shapes (B14 rule 37), so the fixture below holds the SAME
// shapes with the tenant's own-looking names — the assertions are about which
// column says what, never about a figure drawn in a frame.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { formatDate, parseRegionalDate, REGIONAL_DATE_FORMATS } from "@/components/DateCell";
import type { Translator } from "@/features/tenancy/settingsShared";
import i18n from "@/i18n";

import {
  FIELD_VISIT_HOLDERS_KEY,
  FIELD_VISIT_OPTIONS_KEY,
  FieldVisitOrders,
  newFieldVisitRow,
  emptyFieldVisit,
  fieldVisitPayload,
  fieldVisitProblem,
} from "./FieldVisitOrders";
import type { FieldVisitValue, RaisedWorkOrderRef } from "./FieldVisitOrders";
import type { CrewList, RaiseOptions } from "./workEndpoints";

afterEach(cleanup);

const t: Translator = (key, params) => i18n.t(key, params);

const OPTIONS: RaiseOptions = {
  types: [
    { id: "ty-dr", code: "DISCON_RECON", name: "Disconnection/Reconnection", parent_name: null, default_priority_id: "pr-high" },
    { id: "ty-rr", code: "RE_READ", name: "Re-read", parent_name: null, default_priority_id: null },
  ],
  priorities: [
    { id: "pr-high", code: "high", name: "High", sla_hours: 8 },
    { id: "pr-normal", code: "normal", name: "Normal", sla_hours: 72 },
  ],
};

const CREWS: CrewList = {
  count: 2,
  next: null,
  previous: null,
  results: [
    { id: "cr-b", kind: "crew", name: "Crew B (3)", slug: "crew-b", role_label: null, skills: [], certifications: [], shift: null, status: "crew", unavailable_reason: null },
    { id: "te-o", kind: "person", name: "D. Ortiz", slug: "d-ortiz", role_label: null, skills: [], certifications: [], shift: null, status: "on_shift", unavailable_reason: null },
  ],
  counts: { rows: 2, people: 1, crews: 1, contractors: 0 },
};

function Harness(props: { initial?: FieldVisitValue; onValue?: (value: FieldVisitValue) => void; showErrors?: boolean }) {
  const [value, setValue] = useState<FieldVisitValue>(props.initial ?? emptyFieldVisit());
  props.onValue?.(value);
  return (
    <FieldVisitOrders
      flowKind="move_in"
      value={value}
      onChange={setValue}
      showErrors={props.showErrors}
      dateFormat="DD-MMM-YY"
      timeZone="America/Chicago"
      t={t}
    />
  );
}

function mount(node: React.ReactNode, seed: (client: QueryClient) => void = () => undefined) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(FIELD_VISIT_OPTIONS_KEY, OPTIONS);
  client.setQueryData(FIELD_VISIT_HOLDERS_KEY, CREWS);
  seed(client);
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

describe("FieldVisitOrders — edit: rows are added inline, and nothing is raised", () => {
  it("with no rows it draws the button and no empty table", () => {
    mount(<Harness />);
    expect(screen.getByRole("button", { name: "+ Add work order" })).toBeInTheDocument();
    expect(document.body.querySelector("table")).toBeNull();
  });

  it("builds the two approved rows, and the payload carries exactly what the raise reads", async () => {
    const user = userEvent.setup();
    let latest: FieldVisitValue = emptyFieldVisit();
    mount(<Harness onValue={(value) => (latest = value)} />);

    await user.click(screen.getByRole("button", { name: "+ Add work order" }));
    await user.click(screen.getByRole("button", { name: "+ Add work order" }));
    const rows = document.body.querySelectorAll("tbody tr");
    expect(rows).toHaveLength(2);
    // A new row opens on the utility's own Normal.
    expect(within(rows[0] as HTMLElement).getByLabelText("Priority")).toHaveValue("pr-normal");

    // Row 1 — the type's own default priority (High) replaces the opening Normal.
    await user.selectOptions(within(rows[0] as HTMLElement).getByLabelText(/Job type/), "ty-dr");
    expect(within(rows[0] as HTMLElement).getByLabelText("Priority")).toHaveValue("pr-high");
    await user.type(within(rows[0] as HTMLElement).getByLabelText("Due"), "01-Aug-26");
    await user.selectOptions(within(rows[0] as HTMLElement).getByLabelText("Assigned to"), "crew:cr-b");
    await user.type(within(rows[0] as HTMLElement).getByLabelText("Note"), "Turn water on at curb");
    // Row 2 — no default on the type, so Normal stays; no due date; unassigned.
    await user.selectOptions(within(rows[1] as HTMLElement).getByLabelText(/Job type/), "ty-rr");
    await user.type(within(rows[1] as HTMLElement).getByLabelText("Note"), "Check W-5041 opening read");

    for (const row of rows) {
      expect(within(row as HTMLElement).getByText("Not raised yet")).toBeInTheDocument();
    }
    expect(fieldVisitProblem(latest)).toBeNull();
    expect(fieldVisitPayload(latest)).toEqual({
      orders: [
        { type_id: "ty-dr", priority_id: "pr-high", due_on: "2026-08-01", crew_id: "cr-b", note: "Turn water on at curb" },
        { type_id: "ty-rr", priority_id: "pr-normal", note: "Check W-5041 opening read" },
      ],
    });
  });

  it("a row with no job type holds the step, and says so only after Continue", async () => {
    const user = userEvent.setup();
    let latest: FieldVisitValue = emptyFieldVisit();
    mount(<Harness onValue={(value) => (latest = value)} />);
    await user.click(screen.getByRole("button", { name: "+ Add work order" }));
    expect(fieldVisitProblem(latest)).toBe("work.fieldVisitOrders.jobTypeRequired");
    expect(screen.queryByText("Choose a job type.")).toBeNull();
    cleanup();
    mount(<Harness initial={latest} showErrors />);
    expect(screen.getAllByText("Choose a job type.").length).toBeGreaterThan(0);
  });

  it("No visit needed clears the rows, hides the table and is sent as an answer", async () => {
    const user = userEvent.setup();
    let latest: FieldVisitValue = emptyFieldVisit();
    mount(<Harness onValue={(value) => (latest = value)} />);
    await user.click(screen.getByRole("button", { name: "+ Add work order" }));
    await user.click(screen.getByText("No visit needed"));
    expect(latest).toEqual({ none: true, rows: [] });
    expect(screen.queryByRole("button", { name: "+ Add work order" })).toBeNull();
    expect(fieldVisitPayload(latest)).toEqual({ none: true });
    expect(fieldVisitPayload(emptyFieldVisit())).toBeUndefined();
  });
});

describe("FieldVisitOrders — review and live", () => {
  const value: FieldVisitValue = {
    none: false,
    rows: [
      { key: "a", type_id: "ty-dr", priority_id: "pr-high", due_on: "2026-08-01", holder: "crew:cr-b", note: "Turn water on at curb" },
      { key: "b", type_id: "ty-rr", priority_id: "pr-normal", due_on: "", holder: "", note: "Check W-5041 opening read" },
    ],
  };

  it("review: the same rows read-only, Order # reading On save", () => {
    mount(<FieldVisitOrders flowKind="move_in" mode="review" value={value} dateFormat="DD-MMM-YY" timeZone="America/Chicago" t={t} />);
    const rows = [...document.body.querySelectorAll("tbody tr")].map((row) =>
      [...row.querySelectorAll("td")].map((cell) => cell.textContent),
    );
    expect(rows).toEqual([
      ["On save", "Disconnection/Reconnection", "High", "01-Aug-26", "Crew B (3)", "Not raised yet", "Turn water on at curb"],
      ["On save", "Re-read", "Normal", "—", "Unassigned", "Not raised yet", "Check W-5041 opening read"],
    ]);
    expect(document.body.querySelector("select, input")).toBeNull();
  });

  it("live: the real number links to the order, and status and assignee are Work's", () => {
    const raised: RaisedWorkOrderRef[] = [
      { id: "wo-1", order_no: "WO-4823" },
      { id: "wo-2", order_no: "WO-4824" },
    ];
    mount(
      <FieldVisitOrders flowKind="move_in" mode="live" value={value} raised={raised} dateFormat="DD-MMM-YY" timeZone="America/Chicago" t={t} />,
      (client) => {
        client.setQueryData(["work", "order", "wo-1"], {
          id: "wo-1", order_no: "WO-4823", type: "Disconnection/Reconnection", state: "planned",
          priority: { id: "pr-high", code: "high", name: "High", colour: "danger", rank: 1 },
          technician: { kind: "crew", name: "Crew B (3)", slug: "crew-b" }, due_at: "2026-08-01T05:00:00Z",
        });
        client.setQueryData(["work", "order", "wo-2"], {
          id: "wo-2", order_no: "WO-4824", type: "Re-read", state: "planned",
          priority: { id: "pr-normal", code: "normal", name: "Normal", colour: "neutral", rank: 3 },
          technician: null, due_at: null,
        });
      },
    );
    expect(screen.getByRole("link", { name: "WO-4823" })).toHaveAttribute("href", "/brazosbend/work/orders/wo-1");
    const statuses = [...document.body.querySelectorAll("[data-field-visit-status]")].map((cell) => cell.textContent);
    expect(statuses).toEqual(["Planned", "Planned"]);
    expect(screen.getByText("Unassigned")).toBeInTheDocument();
  });
});

describe("parseRegionalDate — the mirror of formatDate, in every format", () => {
  it("reads back what formatDate writes, for all seven", () => {
    for (const format of REGIONAL_DATE_FORMATS) {
      const shown = formatDate("2026-08-01", "UTC", format, false, "en");
      expect({ format, back: parseRegionalDate(shown, format, { locale: "en" }) }).toEqual({
        format,
        back: "2026-08-01",
      });
    }
  });

  it("refuses a day the month does not have, and resolves a 2-digit year of birth", () => {
    expect(parseRegionalDate("31-Feb-26", "DD-MMM-YY", { locale: "en" })).toBeNull();
    expect(parseRegionalDate("12-Aug-87", "DD-MMM-YY", { locale: "en", max: "2026-09-23" })).toBe("1987-08-12");
    expect(parseRegionalDate("2026-08-01", "MM/DD/YYYY")).toBe("2026-08-01");
  });
});

// ── CR-168-BRC10 lane FLOW-FIX · DEF-WRK-9626 ─────────────────────────────
describe("DEF-WRK-9626 — a flow's new row opens on the job type that fits it", () => {
  const options = {
    types: [
      { id: "t-reread", code: "RE_READ", name: "Re-read", parent_name: "Reading", default_priority_id: null },
      { id: "t-recon", code: "DISCONNECT_RECONNECT", name: "Disconnection/Reconnection", parent_name: "Consumer Services", default_priority_id: "p-high" },
    ],
    priorities: [
      { id: "p-normal", code: "NORMAL", name: "Normal", sla_hours: 72 },
      { id: "p-high", code: "HIGH", name: "High", sla_hours: 8 },
    ],
    flow_types: { move_out: "t-reread", reconnect: "t-recon" },
  } as never;
  it("a move-out row opens on Re-read; a reconnect row on its own type and that type's priority", () => {
    expect(newFieldVisitRow(options, "move_out").type_id).toBe("t-reread");
    expect(newFieldVisitRow(options, "move_out").priority_id).toBe("p-normal");
    expect(newFieldVisitRow(options, "reconnect").type_id).toBe("t-recon");
    expect(newFieldVisitRow(options, "reconnect").priority_id).toBe("p-high");
  });
  it("a flow the server names no type for opens empty, as before", () => {
    expect(newFieldVisitRow(options, "service_request").type_id).toBe("");
  });
});
