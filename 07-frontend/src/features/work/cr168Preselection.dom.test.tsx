// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 P3.42 — six screens read the pre-selection (lane FIN-T).
//           The three Field visit TABLES (move-in, move-out, transfer) mount
//           FieldVisitOrders; the new connection's step 6 reads
//           `preselected_by` on its proposals.
// Rules:    BR-WRK-055 (nothing is raised until the save; the clerk may remove
//           the rule's row) · BR-WRK-024 (the job names its rule) · B14 rule
//           31 (no id is a visible value) · rule 33 (a fact, ≤ 6 words)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { Translator } from "@/features/tenancy/settingsShared";
import i18n from "@/i18n";

import {
  FIELD_VISIT_HOLDERS_KEY,
  FIELD_VISIT_OPTIONS_KEY,
  FieldVisitOrders,
  emptyFieldVisit,
  fieldVisitPayload,
  hydrateFieldVisit,
} from "./FieldVisitOrders";
import type { FieldVisitValue } from "./FieldVisitOrders";
import type { CrewList, ProposedWorkOrder, RaiseOptions } from "./workEndpoints";
import { orderForService, workOrderOptions } from "@/features/customers/NewConnectUnitsStep";

afterEach(cleanup);

const t: Translator = (key, params) => i18n.t(key, params);

const OPTIONS: RaiseOptions = {
  types: [
    { id: "ty-fr", code: "FINAL_READ", name: "Final read", parent_name: null, default_priority_id: null },
    { id: "ty-rr", code: "RE_READ", name: "Re-read", parent_name: null, default_priority_id: null },
  ],
  priorities: [
    { id: "pr-high", code: "high", name: "High", sla_hours: 8 },
    { id: "pr-normal", code: "normal", name: "Normal", sla_hours: 72 },
  ],
  preselected: {
    move_out: [
      {
        rule: { id: "ru-1", name: "Final read on move-out" },
        type_id: "ty-fr",
        priority_id: "pr-high",
        holder: "crew:cr-b",
      },
    ],
  },
};

const CREWS: CrewList = {
  count: 1,
  next: null,
  previous: null,
  results: [
    { id: "cr-b", kind: "crew", name: "Crew B (3)", slug: "crew-b", role_label: null, skills: [], certifications: [], shift: null, status: "crew", unavailable_reason: null },
  ],
  counts: { rows: 1, people: 0, crews: 1, contractors: 0 },
};

function Harness(props: { flowKind: string; onValue?: (value: FieldVisitValue) => void }) {
  const [value, setValue] = useState<FieldVisitValue>(emptyFieldVisit());
  props.onValue?.(value);
  return (
    <FieldVisitOrders
      flowKind={props.flowKind}
      value={value}
      onChange={setValue}
      dateFormat="DD-MMM-YY"
      timeZone="America/Chicago"
      t={t}
    />
  );
}

function mount(flowKind: string, onValue?: (value: FieldVisitValue) => void) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(FIELD_VISIT_OPTIONS_KEY, OPTIONS);
  client.setQueryData(FIELD_VISIT_HOLDERS_KEY, CREWS);
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/brazosbend/move-outs/new"]}>
        <Routes>
          <Route path="/:tenant/move-outs/new" element={<Harness flowKind={flowKind} onValue={onValue} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("P3.42 — a Field visit table arrives with its rule's job", () => {
  it("the move-out table opens with the rule's row, its priority and holder, and says which rule", async () => {
    let latest: FieldVisitValue = emptyFieldVisit();
    mount("move_out", (value) => (latest = value));
    const row = (await screen.findAllByRole("row")).find((tr) => tr.closest("tbody")) as HTMLElement;
    expect(within(row).getByLabelText(/Job type/)).toHaveValue("ty-fr");
    expect(within(row).getByLabelText("Priority")).toHaveValue("pr-high");
    expect(within(row).getByLabelText("Assigned to")).toHaveValue("crew:cr-b");
    expect(row.textContent).toContain("By rule: Final read on move-out");
    // B14 rule 31 — the rule's id is never drawn.
    expect(document.body.textContent).not.toContain("ru-1");
    // Nothing is raised: the save carries the row, naming its rule.
    expect(fieldVisitPayload(latest)).toEqual({
      orders: [{ type_id: "ty-fr", priority_id: "pr-high", crew_id: "cr-b", rule_id: "ru-1" }],
    });
  });

  it("a moment no rule names opens empty, as before", () => {
    mount("move_in");
    expect(screen.getByRole("button", { name: "+ Add work order" })).toBeInTheDocument();
    expect(document.body.querySelector("tbody tr")).toBeNull();
  });

  it("the clerk may remove it, and is not handed it back", async () => {
    const user = userEvent.setup();
    let latest: FieldVisitValue = emptyFieldVisit();
    mount("move_out", (value) => (latest = value));
    await screen.findByText("By rule: Final read on move-out");
    await user.click(screen.getByRole("button", { name: /Remove/ }));
    expect(document.body.querySelector("tbody tr")).toBeNull();
    expect(latest.rows).toEqual([]);
    expect(latest.ruled).toBe(true);
    expect(screen.queryByText("By rule: Final read on move-out")).toBeNull();
  });

  it("No visit needed clears the rule's row too — a recorded choice (BR-WRK-055)", async () => {
    const user = userEvent.setup();
    let latest: FieldVisitValue = emptyFieldVisit();
    mount("move_out", (value) => (latest = value));
    await screen.findByText("By rule: Final read on move-out");
    await user.click(screen.getByLabelText("No visit needed"));
    expect(fieldVisitPayload(latest)).toEqual({ none: true });
  });

  it("a parked draft keeps the row's rule and the once-only mark", () => {
    const back = hydrateFieldVisit({
      none: false,
      ruled: true,
      rows: [{ key: "k", type_id: "ty-fr", priority_id: "", due_on: "", holder: "", note: "", rule: { id: "ru-1", name: "R" } }],
    });
    expect(back.ruled).toBe(true);
    expect(back.rows[0].rule).toEqual({ id: "ru-1", name: "R" });
  });
});

describe("P3.42 — the new connection's step 3 arrives on the rule's job", () => {
  const proposed = [
    { template_id: "t-meter", name: "Meter set", service: { id: "s", code: "electric", name: "Electric" } },
    {
      template_id: "t-survey",
      name: "Site survey",
      service: { id: "s", code: "electric", name: "Electric" },
      preselected_by: { id: "ru-9", name: "Survey every build" },
    },
  ] as unknown as ProposedWorkOrder[];

  it("a service's row arrives on the job a Work rule proposes", () => {
    expect(orderForService(proposed, "electric")?.template_id).toBe("t-survey");
    expect(orderForService(proposed.slice(0, 1), "electric")?.template_id).toBe("t-meter");
  });

  it("the option says which rule proposed it", () => {
    const labels = workOrderOptions(proposed, (name) => t("work.fieldVisitOrders.byRule", { name })).map(
      (option) => option.label,
    );
    expect(labels).toEqual(["Meter set", "Site survey · By rule: Survey every build"]);
  });
});
