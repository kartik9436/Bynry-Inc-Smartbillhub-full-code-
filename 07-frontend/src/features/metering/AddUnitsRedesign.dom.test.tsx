// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-176-BRC10 — the Add units redesign (DEF-MET-10035), round C.
// Rules:   CR-176 rules (1) next free start · (2) one count · (3) services all
//          ticked · (4) search and Use this building · the Units list's
//          selection bar only once a unit is ticked.
// ───────────────────────────────────────────────────────
// The wizard MOUNTED UNDER ITS REAL ROUTE with a fetch fake, so these cases see
// what a clerk sees: the start the server offers lands in the box, the count is
// one number everywhere, and the list's bar appears only on a tick.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { MyPermissions, PremisesLends, UnitRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { AddUnitsWizard } from "./AddUnitsWizard";
import { PREMISES_PERMISSION } from "./meteringShared";
import { UnitsListPage } from "./UnitsListPage";

const TENANT = "brazosbend";

function lends(): PremisesLends {
  return {
    premises: {
      id: "p-74",
      premise_no: "P-00074",
      name: null,
      address_line: "123 Main Street",
      city: "Ottumwa",
      state: "IA",
      postal_code: "52501",
      premises_type: "apartment",
      premises_type_name: "Apartments",
      services_available: ["water", "sewer", "trash"],
      owner_manager: null,
      owner: null,
      status: "active",
      master_account_id: "acc-9",
      master_account_no: "AC-2026-00051",
      master_account_name: "Bramble Property Group",
    } as unknown as PremisesLends["premises"],
    units_today: 4,
    unit_labels: ["Unit 1", "Unit 2", "Unit 3", "Unit 5"],
    unit_labels_truncated: false,
    routes: [{ code: "RT-004", name: null, service: null, cycle_code: "CY-002", cycle_name: null, cycle_start_day: null }],
  };
}

interface Call {
  url: string;
  method: string;
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
}

/** The server's next-free answer for the worked figure: 1, 2, 3, 5 on file. */
function nextFree(url: URL): { next_free: number; taken: string[] } {
  const count = Number(url.searchParams.get("count") ?? "1");
  const start = url.searchParams.get("start");
  const onFile = new Set([1, 2, 3, 5]);
  let n = 1;
  while (Array.from({ length: count }, (_u, i) => n + i).some((s) => onFile.has(s))) n += 1;
  const taken =
    start === null
      ? []
      : Array.from({ length: count }, (_u, i) => Number(start) + i)
          .filter((s) => onFile.has(s))
          .map((s) => `Unit ${s}`);
  return { next_free: n, taken };
}

function mountWizard(calls: Call[], path = `/${TENANT}/premises/units/new?premises=p-74`) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const fetchImpl = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://local");
    calls.push({ url: url.pathname + url.search, method: String(init?.method ?? "GET").toUpperCase() });
    if (url.pathname.endsWith("/lends")) return json(lends());
    if (url.pathname.endsWith("/units/next-free")) return json(nextFree(url));
    if (url.pathname.endsWith("/units/number-preview")) {
      const count = Number(url.searchParams.get("count") ?? "1");
      const numbers = Array.from({ length: Math.min(count, 5) }, (_u, i) => `U-${String(13 + i).padStart(5, "0")}`);
      return json({ series_missing: false, count, numbers, last: `U-${String(12 + count).padStart(5, "0")}` });
    }
    if (url.pathname.endsWith("/premises")) {
      return json({ count: 1, results: [{ ...lends().premises, units: 4 }] });
    }
    return json({ count: 0, results: [] });
  };
  const client = createApiClient({ tenant: TENANT, fetchImpl });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route
              path="/:tenant/premises/units/new"
              element={<AddUnitsWizard client={client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("CR-176 rule (1) — Start numbering at starts at the first number the WHOLE run is free", () => {
  it("1, 2, 3 and 5 on file: one unit starts at 4, three units start at 6", async () => {
    const user = userEvent.setup();
    mountWizard([]);
    const start = (await screen.findByLabelText("Start numbering at")) as HTMLInputElement;
    await waitFor(() => expect(start.value).toBe("4"));
    expect(screen.getByText("Next free: 4")).toBeInTheDocument();
    const howMany = screen.getByLabelText(/How many/) as HTMLInputElement;
    await user.clear(howMany);
    await user.type(howMany, "3");
    await waitFor(() => expect(start.value).toBe("6"));
    expect(screen.getByText("Next free: 6")).toBeInTheDocument();
  });

  it("a typed start that hits taken labels names them, and Use 6 sets the start", async () => {
    const user = userEvent.setup();
    mountWizard([]);
    const howMany = (await screen.findByLabelText(/How many/)) as HTMLInputElement;
    await user.clear(howMany);
    await user.type(howMany, "3");
    const start = screen.getByLabelText("Start numbering at") as HTMLInputElement;
    await waitFor(() => expect(start.value).toBe("6"));
    await user.clear(start);
    await user.type(start, "1");
    expect(await screen.findByText("Unit 1, Unit 2, Unit 3 are taken.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Use 6" }));
    await waitFor(() => expect(start.value).toBe("6"));
    expect(screen.queryByText("Unit 1, Unit 2, Unit 3 are taken.")).not.toBeInTheDocument();
  });
});

describe("CR-176 rule (2) — one count drives Creates, the card and the button", () => {
  it("How many 3 reads 3 units on the card and Unit 6 to Unit 8 under Creates", async () => {
    const user = userEvent.setup();
    mountWizard([]);
    const howMany = (await screen.findByLabelText(/How many/)) as HTMLInputElement;
    expect(howMany.value).toBe("1");
    await waitFor(() => expect(screen.getByText("1 unit")).toBeInTheDocument());
    await user.clear(howMany);
    await user.type(howMany, "3");
    await waitFor(() => expect(screen.getByText("3 units")).toBeInTheDocument());
    const creates = document.querySelector("[data-add-units-creates]") as HTMLElement;
    await waitFor(() => expect(within(creates).getByText("Unit 6 to Unit 8")).toBeInTheDocument());
    expect(within(creates).getByText("U-00013 to U-00015")).toBeInTheDocument();
  });
});

describe("the building card and services (rules 3 and 4)", () => {
  it("a building carried in is shown chosen, owner named, every service ticked", async () => {
    const user = userEvent.setup();
    mountWizard([]);
    expect(await screen.findByText("✓ Selected")).toBeInTheDocument();
    expect(screen.getByText("Change building")).toBeInTheDocument();
    expect(await screen.findByText("Bramble Property Group")).toBeInTheDocument();
    expect(screen.queryByText("Not recorded")).not.toBeInTheDocument();
    const services = screen.getByRole("button", { name: /Services/ });
    expect(services).toHaveTextContent("All the building's services");
    await user.click(services);
    const boxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    expect(boxes.length).toBe(4);
    expect(boxes.every((box) => box.checked)).toBe(true);
  });

  it("no building: Continue says pick the building first, and How many is not red", async () => {
    const user = userEvent.setup();
    mountWizard([], `/${TENANT}/premises/units/new`);
    await user.click(await screen.findByRole("button", { name: "Continue" }));
    expect(await screen.findByText("Pick the building first.")).toBeInTheDocument();
    expect(screen.queryByText("Enter how many units.")).not.toBeInTheDocument();
  });

  it("search, then Use this building, then ✓ Selected", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    mountWizard(calls, `/${TENANT}/premises/units/new`);
    await user.type(await screen.findByLabelText(/Premise/), "Main");
    await user.click(screen.getByRole("button", { name: "Find" }));
    const use = await screen.findByRole("button", { name: "Use this building" });
    expect(calls.some((c) => c.url.includes("/premises?") && c.url.includes("q=Main"))).toBe(true);
    await user.click(use);
    expect(await screen.findByText("✓ Selected")).toBeInTheDocument();
  });
});

// ── the Units list ───────────────────────────────────────────────────────────
function unit(): UnitRow {
  return {
    id: "u-501",
    unit_no: "U-00501",
    premises_id: "p-101",
    premise_no: "P-00101",
    premise_address: "1408 Bluestem Ln",
    label: "2",
    unit_type: "residential",
    floor_label: null,
    square_feet: null,
    rate_plan_id: null,
    plan_effective_from: null,
    plan_locked: false,
    vacant_standby_auto: false,
    is_common_area: false,
    services: ["water"],
    lat: null,
    lng: null,
    active: true,
    metered_services: [],
    meters: [],
    occupancy: "vacant",
    occupant: null,
    account_no: null,
    status: "active",
    sub_metered: false,
  } as unknown as UnitRow;
}

function mountList() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const perms: MyPermissions = {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  };
  queryClient.setQueryData(queryKeys.myPermissions, perms);
  const fetchImpl = async (input: RequestInfo | URL) => {
    const url = String(input);
    const body = url.includes("/settings/services")
      ? []
      : url.includes("/permissions")
        ? perms
        : url.includes("/units")
          ? { results: [unit()], count: 3412 }
          : { results: [], count: 0 };
    return json(body);
  };
  const client = createApiClient({ tenant: TENANT, fetchImpl });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/premises/units`]}>
          <Routes>
            <Route
              path="/:tenant/premises/units"
              element={<UnitsListPage client={client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("DEF-MET-10035 — the Units list's selection bar shows only once a unit is ticked", () => {
  it("nothing ticked: no bar and no '0 unit(s) selected'", async () => {
    mountList();
    await screen.findByText("1408 Bluestem Ln");
    expect(screen.queryByText(/unit\(s\) selected/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Select all/ })).not.toBeInTheDocument();
  });

  it("one tick: the bar, with Select all stating the SERVER's total (DEF-TEN-5840 kept)", async () => {
    const user = userEvent.setup();
    mountList();
    await screen.findByText("1408 Bluestem Ln");
    const row = document.querySelector("table tbody input[type=checkbox]") as HTMLInputElement;
    await user.click(row);
    expect(await screen.findByText("1 unit(s) selected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Select all 3412" })).toBeInTheDocument();
  });
});
