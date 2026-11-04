// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 task 6 — Plans & Rates › Plans LIST, rebuilt
//           from images 01–03 of 05-prototype/plans-2026-10-03.
// Defect:   DEF-RAT-9333 (reproduced on 2.481.6, CR-167 §6 P12, before any fix)
// Rules:    B14 rules 21 · 31 · 33 · 37 · 42 · 43 · 44 · NFR-3 (server paging,
//           server search, server sort) · NFR-5 (no cap) · BR-RAT-1040 (base
//           charges is not a sort)
// ───────────────────────────────────────────────────────
/**
 * ONE CASE PER THING `DEF-RAT-9333` NAMES, EACH WRITTEN AGAINST THE OLD SCREEN
 * BEFORE IT WAS REBUILT AND WATCHED FAIL THERE.
 *
 * ⚠ **NO DRAWN FIGURE IS ASSERTED AS A FACT (B14 rule 37).** Image 01 inks
 * *Residential* at V3 with 75 units; these fixtures carry their own numbers.
 *
 * ⚠ **THE ROUND-2 LIST FIELDS ARE THE CONTRACT'S (CR-167 §7.3, `GET /plans`):**
 * `schedules`, `units`, `version`, `effective_from`, `effective_to`. A row from
 * a server that predates them still renders — counts fall back to what today's
 * row carries, never to an invented zero.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";
import { createApiClient } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { PlanRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { PlansTab } from "./PlansTab";
import { RATING_TABS } from "./ratingShared";
import type { RatingTabRender } from "./ratingShared";
import plansTabSource from "./PlansTab.tsx?raw";

afterEach(cleanup);

const TENANT = "brazosbend";
const RESIDENTIAL_ID = "0193f0aa-1111-7000-8000-00000000c1a5";
const COMMERCIAL_ID = "0193f0aa-2222-7000-8000-00000000c1a5";

/** A published plan as today's server serves it. */
const TODAY: PlanRow = {
  id: "p-harbor",
  code: "HBR",
  name: "Harbor Residential",
  description: null,
  status: "published",
  version: 4,
  account_type_id: RESIDENTIAL_ID,
  account_type_ids: [RESIDENTIAL_ID],
  account_subtype_id: null,
  budget_billing: false,
  eligibility: {},
  minimum_bill_amount: null,
  outside_city_factor: null,
  effective_from: "2026-03-14",
  effective_to: "2027-05-09",
  services: ["water", "sewer"],
  base_charges: "23.000000",
  base_charges_display: "23.00",
  rate_schedules: [
    { service: "water", tariff_id: "t-w", tariff_name: "Harbor water tiers" },
    { service: "sewer", tariff_id: "t-s", tariff_name: "Harbor sewer flat" },
  ],
  accounts: 3,
};

/** The same plan, every round-2 field served. */
const HARBOR = {
  ...TODAY,
  schedules: 2,
  units: 41,
  upcoming_version: null,
  customer_classes: [{ value: RESIDENTIAL_ID, label: "Residential" }],
} as PlanRow;

/** A draft for every class, open-ended, no base figure. */
const LAKE = {
  ...HARBOR,
  id: "p-lake",
  code: "LKD",
  name: "Lake Draft",
  status: "draft",
  version: 1,
  account_type_id: null,
  account_type_ids: [],
  effective_from: "2026-12-01",
  effective_to: null,
  services: ["water"],
  base_charges: null,
  base_charges_display: null,
  rate_schedules: [{ service: "water", tariff_id: "t-w", tariff_name: "Harbor water tiers" }],
  accounts: 0,
  schedules: 1,
  units: 0,
  customer_classes: [],
} as PlanRow;

/** A row from a server that predates round 2 — no `schedules`, no `units`. */
const OLD_SERVER: PlanRow = {
  ...TODAY,
  id: "p-old",
  code: "OLD",
  name: "Old Row",
  account_type_ids: [COMMERCIAL_ID],
  accounts: 9,
  rate_schedules: [{ service: "water", tariff_id: "t-w", tariff_name: "Harbor water tiers" }],
};

const CLASSES = [
  { id: RESIDENTIAL_ID, code: "residential", name: "Residential", active: true, is_system: true, used_by: 0 },
  { id: COMMERCIAL_ID, code: "commercial", name: "Commercial", active: true, is_system: true, used_by: 0 },
];

interface Call {
  url: string;
}

function recordingClient(calls: Call[], rows: PlanRow[]): ApiClient {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input) => {
      const url = String(input);
      calls.push({ url });
      let body: unknown = { count: 0, next: null, previous: null, results: [] };
      if (url.includes("/lookups/account_types")) {
        body = { count: CLASSES.length, next: null, previous: null, results: CLASSES };
      } else if (url.includes("/plans")) {
        const narrowed = url.includes("q=zzz") ? [] : rows;
        body = {
          count: narrowed.length,
          next: null,
          previous: null,
          results: narrowed,
          rollup: {
            plans: narrowed.length,
            rate_schedules: 0,
            charge_codes: 0,
            discounts: 0,
            taxes: 0,
            contracts: null,
            effective_from: null,
          },
        };
      } else if (url.includes("/settings/services")) {
        body = [];
      }
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
}

const render2: RatingTabRender = ({ action, body }) => (
  <>
    <div data-testid="action">{action}</div>
    {body}
  </>
);

function mount(client: ApiClient, search = "") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/plans-rates${search}`]}>
          <Routes>
            <Route
              path="/:tenant/plans-rates"
              element={
                <PlansTab
                  readOnly={false}
                  client={client}
                  timeZone="America/Chicago"
                  dateFormat="MM/DD/YYYY"
                  render={render2}
                />
              }
            />
            <Route
              path="/:tenant/plans-rates/plans/:planId"
              element={<p data-testid="opened">opened</p>}
            />
            <Route
              path="/:tenant/plans-rates/plans/:planId/edit"
              element={<p data-testid="edit">edit</p>}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function rowOf(name: string): HTMLElement {
  const row = screen.getByText(name).closest("tr");
  if (row === null) throw new Error(`no row for ${name}`);
  return row;
}

function headings(): string[] {
  return screen
    .getAllByRole("columnheader")
    .map((cell) => (cell.textContent ?? "").replace(/[▲▼↕]/g, "").trim())
    .filter((text) => text !== "");
}

describe("CR-167 task 6 — the Plans list, built from images 01–03 (DEF-RAT-9333)", () => {
  it("columns in the drawn order: Plan · Version · Services · Schedules · Base charges · Units · From · To · Status", async () => {
    mount(recordingClient([], [HARBOR, LAKE]));
    await screen.findByText("Harbor Residential");
    expect(headings()).toEqual([
      "Plan",
      "Version",
      "Services",
      "Schedules",
      "Base charges",
      "Units",
      "From",
      "To",
      "Status",
    ]);
  });

  it("a plan attaches to UNITS: no Accounts column; Units reads the served count", async () => {
    mount(recordingClient([], [HARBOR]));
    await screen.findByText("Harbor Residential");
    expect(screen.queryByRole("columnheader", { name: /Accounts/ })).toBeNull();
    const cells = within(rowOf("Harbor Residential"))
      .getAllByRole("cell")
      .map((cell) => cell.textContent);
    expect(cells).toContain("41");
    expect(cells).not.toContain("3");
  });

  it("Schedules is a COUNT, never the schedule names; an older server's row counts its own list", async () => {
    mount(recordingClient([], [HARBOR, OLD_SERVER]));
    await screen.findByText("Harbor Residential");
    const harbor = rowOf("Harbor Residential");
    expect(within(harbor).queryByText("Harbor water tiers")).toBeNull();
    expect(within(harbor).getAllByRole("cell").map((c) => c.textContent)).toContain("2");
    expect(within(rowOf("Old Row")).getAllByRole("cell").map((c) => c.textContent)).toContain("1");
  });

  it("Plan: the name opens the plan, with the code and the customer class under it — never an id", async () => {
    mount(recordingClient([], [HARBOR, LAKE]));
    await screen.findByText("Harbor Residential");
    const harbor = rowOf("Harbor Residential");
    expect(await within(harbor).findByText("HBR · Residential")).toBeInTheDocument();
    expect(within(rowOf("Lake Draft")).getByText("LKD · Every customer class")).toBeInTheDocument();
    expect(harbor.textContent).not.toContain(RESIDENTIAL_ID);
    await userEvent.click(within(harbor).getByRole("link", { name: "Harbor Residential" }));
    expect(await screen.findByTestId("opened")).toBeInTheDocument();
  });

  it("DEF-RAT-9354: classes are the row's served words — the list never reads the class list a second time", async () => {
    const calls: Call[] = [];
    mount(recordingClient(calls, [HARBOR, LAKE, OLD_SERVER]));
    await screen.findByText("Harbor Residential");
    expect(await within(rowOf("Harbor Residential")).findByText("HBR · Residential")).toBeInTheDocument();
    // a row with no served words shows its code alone, never an id
    expect(within(rowOf("Old Row")).getByText("OLD")).toBeInTheDocument();
    expect(rowOf("Old Row").textContent).not.toContain(COMMERCIAL_ID);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(calls.filter((call) => call.url.includes("/lookups/account_types"))).toEqual([]);
  });

  it("Version is a V-tag; From and To are dates; an open end reads No end", async () => {
    mount(recordingClient([], [HARBOR, LAKE]));
    await screen.findByText("Harbor Residential");
    const harbor = rowOf("Harbor Residential");
    expect(within(harbor).getByText("V4")).toBeInTheDocument();
    expect(within(harbor).getByText("03/14/2026")).toBeInTheDocument();
    expect(within(harbor).getByText("05/09/2027")).toBeInTheDocument();
    const lake = rowOf("Lake Draft");
    expect(within(lake).getByText("V1")).toBeInTheDocument();
    expect(within(lake).getByText("No end")).toBeInTheDocument();
  });

  it("Base charges: the server's figure with its $; none is a dash, never $0.00", async () => {
    mount(recordingClient([], [HARBOR, LAKE]));
    await screen.findByText("Harbor Residential");
    expect(within(rowOf("Harbor Residential")).getByText("$23.00")).toBeInTheDocument();
    expect(within(rowOf("Lake Draft")).queryByText(/0\.00/)).toBeNull();
  });

  it("the row's one action OPENS the plan: no pencil, no publish, no archive, no delete on the row", async () => {
    mount(recordingClient([], [HARBOR, LAKE]));
    await screen.findByText("Harbor Residential");
    for (const name of ["Harbor Residential", "Lake Draft"]) {
      const row = rowOf(name);
      expect(
        within(row).queryByRole("button", { name: /new version|edit|publish|archive|delete/i }),
      ).toBeNull();
    }
    await userEvent.click(within(rowOf("Lake Draft")).getByRole("button", { name: "Open" }));
    expect(await screen.findByTestId("opened")).toBeInTheDocument();
    expect(plansTabSource).not.toContain("PencilIcon");
    expect(plansTabSource).not.toContain("ConfirmDialog");
  });

  it("no paragraph above the table — the plans explainer is retired", () => {
    const tab = RATING_TABS.find((one) => one.id === "plans");
    expect(tab?.explainerKey).toBeUndefined();
    expect(i18n.exists("rating.explainer.plans")).toBe(false);
  });

  it("every sortable head is a sort the SERVER runs (NFR-3); base charges is not one (BR-RAT-1040)", async () => {
    const calls: Call[] = [];
    mount(recordingClient(calls, [HARBOR]));
    await screen.findByText("Harbor Residential");
    const sortable = screen
      .getAllByRole("columnheader")
      .filter((cell) => cell.querySelector("button.table-sort") !== null)
      .map((cell) => (cell.textContent ?? "").replace(/[▲▼↕]/g, "").trim());
    expect(sortable).toEqual(["Plan", "Version", "Units", "From", "To", "Status"]);
    await userEvent.click(within(screen.getByRole("columnheader", { name: /Units/ })).getByRole("button"));
    await waitFor(() => expect(calls.some((call) => /\/plans\?.*sort=units/.test(call.url))).toBe(true));
  });

  it("search, filters and paging go to the SERVER, never over the page (NFR-3)", async () => {
    const calls: Call[] = [];
    mount(recordingClient(calls, [HARBOR]), "?q=harbor&f.status=published");
    await screen.findByText("Harbor Residential");
    const list = calls.find((call) => /\/plans\?/.test(call.url) && call.url.includes("q=harbor"));
    expect(list?.url).toContain("f.status=published");
    expect(list?.url).toContain("page=1");
    expect(list?.url).toContain("per=50");
  });

  it("images 02–03: the search box reads Search plan name or code, and no match is the kit's empty", async () => {
    mount(recordingClient([], [HARBOR]), "?q=zzz");
    expect(await screen.findByPlaceholderText("Search plan name or code")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Harbor Residential")).toBeNull());
  });

  it("DEF-RAT-9341's lesson, applied: no header breaks inside a word in ja-JP or ko-KR", async () => {
    mount(recordingClient([], [HARBOR]));
    await screen.findByText("Harbor Residential");
    const wrapper = screen.getByRole("table").closest("[data-plan-list]");
    expect(wrapper).not.toBeNull();
    expect(wrapper?.className).toContain("[&_thead_th]:break-keep");
  });
});
