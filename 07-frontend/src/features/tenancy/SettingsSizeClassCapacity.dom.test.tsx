// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-10220 (PO 2026-10-17) — a size class added in Settings
//          carries its CAPACITY for a service that sums. Screen: S8 →
//          Reference data → Utility service size classes.
// Rulings: *"enters its kW (e.g. 47.84), stored to 4 decimals"*; *"do not hard
//          code anything … it should able to handle dyanmic capacities"* — so
//          the field is drawn from each service's `capacity_uom`, never from a
//          list of service names, and this file proves it with ton (thermal)
//          as well as kW.
// Note:    Driven with a mouse and read off the JSON body the server received
//          (hard-won law 2 — a field whose value reaches no payload is not the
//          feature). Shown RED before the fix: no "Capacity" column, no field.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import { sameUnit } from "@/lib/units";

import { ReferenceDataTab } from "./SettingsReferenceData";
import { capacityText, trimCapacity } from "./SizeClassCapacity";

interface Sent {
  method: string;
  body: Record<string, unknown> | null;
}

const ROWS = [
  {
    id: "r-sol-own",
    code: "SOL-P47.84",
    name: "Solar Panal 47.84",
    active: true,
    is_system: false,
    used_by: 1,
    service: { id: "svc-solar", code: "solar" },
    capacity: "47.8400",
    capacity_uom: "kW",
  },
  {
    id: "r-cart",
    code: "CART-96",
    name: "Cart 96 gal",
    active: true,
    is_system: true,
    used_by: 0,
    service: { id: "svc-trash", code: "trash" },
    capacity: null,
    capacity_uom: null,
  },
];

/** `capacity_uom` is the server's configuration — nothing in the screen names
 *  a service. Thermal sums in ton; trash counts and carries none. */
const SERVICES = [
  { service: "solar", name: "Solar", enabled: true, capacity_uom: "kW" },
  { service: "thermal_heat", name: "Thermal/Heat", enabled: true, capacity_uom: "ton" },
  { service: "trash", name: "Trash", enabled: true, capacity_uom: null },
];

function json(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
}

function recordingClient(sent: Sent[]) {
  return createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (method !== "GET") {
        sent.push({ method, body: init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null });
        return json(ROWS[0]);
      }
      if (url.includes("/settings/services")) return json(SERVICES);
      if (url.includes("/fixture-gap")) return json({ missing: [] });
      return json({ count: ROWS.length, next: null, previous: null, results: ROWS });
    },
  });
}

function renderList(sent: Sent[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/settings/reference?list=service_size_classes"]}>
        <ToastProvider>
          <ReferenceDataTab readOnly={false} client={recordingClient(sent)} />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("DEF-RAT-10220 — a size class carries its capacity", () => {
  it("the list shows each size's capacity with its unit, and a dash where none", async () => {
    renderList([]);
    expect(await screen.findByRole("columnheader", { name: "Capacity" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("47.84 kW")).toBeInTheDocument());
  });

  it("Add asks Capacity (kW) for solar, sends it as typed, and never for trash", async () => {
    const sent: Sent[] = [];
    renderList(sent);
    await userEvent.click(await screen.findByRole("button", { name: /Add entry/i }));
    const form = await screen.findByRole("dialog");
    expect(within(form).queryByLabelText(/^Capacity/)).toBeNull();

    await userEvent.selectOptions(within(form).getByLabelText("Utility service"), "trash");
    expect(within(form).queryByLabelText(/^Capacity/)).toBeNull();

    await userEvent.selectOptions(within(form).getByLabelText("Utility service"), "solar");
    const field = within(form).getByLabelText(/^Capacity \(kW\)/);
    await userEvent.type(within(form).getByLabelText(/^Code/), "SOL-P3.5");
    await userEvent.type(within(form).getByLabelText(/^Name/), "Solar 3.5");
    await userEvent.type(field, "3.5");
    await userEvent.click(within(form).getByRole("button", { name: "Add entry" }));

    await waitFor(() => expect(sent.length).toBeGreaterThan(0));
    expect(sent[0].body).toMatchObject({ code: "SOL-P3.5", service: "solar", capacity: "3.5" });
  });

  it("the unit comes from the service's configuration — thermal asks in ton", async () => {
    renderList([]);
    await userEvent.click(await screen.findByRole("button", { name: /Add entry/i }));
    const form = await screen.findByRole("dialog");
    await userEvent.selectOptions(within(form).getByLabelText("Utility service"), "thermal_heat");
    expect(within(form).getByLabelText(/^Capacity \(ton\)/)).toBeInTheDocument();
  });

  it("formats and compares units by one generic rule", () => {
    expect(trimCapacity("47.8400")).toBe("47.84");
    expect(trimCapacity("120.0000")).toBe("120");
    expect(capacityText({ capacity: "3.5000", capacity_uom: "kW" })).toBe("3.5 kW");
    expect(capacityText({ capacity: null, capacity_uom: null })).toBe("—");
    expect(sameUnit("KW", "kW")).toBe(true);
    expect(sameUnit(" kw ", "kW")).toBe(true);
    expect(sameUnit("kWh", "MWh")).toBe(false);
    expect(sameUnit("", "")).toBe(false);
  });
});
