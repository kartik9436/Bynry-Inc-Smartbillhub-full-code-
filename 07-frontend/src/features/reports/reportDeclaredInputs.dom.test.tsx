// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-179-BRC10 — the reporting framework's SERVER-DECLARED INPUTS,
//          proved on the first report that declares them (Rate Impact) and on
//          one that declares none (the billing register, unchanged).
// Rules:   hard-won law 2's fixture clause (mount under the REAL path pattern)
//          · law 7 (red first; what would make this pass wrongly) · hard
//          rule 2 (money boxes at 2, unit prices up to 4, never a float).
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 clause 2):
//   · **A screen that never asked the server.** Every case below first waits
//     for the fake server to have been called — a table drawn from nothing is
//     not a table drawn from `controls.inputs`.
//   · **A Run that sends the rows as many params.** The assertion parses the
//     ONE `rows` value as JSON and compares the whole array, so a second
//     encoding cannot satisfy it.
//   · **"now" figures read by value alone.** Two versions of one schedule both
//     carry a `5/8"` size; the v2 case asserts *Billed*, which a lookup that
//     ignored the version would answer as v3's `$8.50`.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

import { scaleByPercent } from "@/components/moneyMath";

import { ReportViewerPage } from "./ReportViewerPage";
import { REPORTS_ROUTE } from "./reportsShared";

afterEach(cleanup);

const TENANT = "brazosbend";

const USER: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@sample.test",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "reports", label: "Reports", access: "Full" }],
};

const PERIOD = { fy_label: "FY2026", period: 9, start: "2026-09-01", end: "2026-09-30", status: "open" };

const MONTHS = [1, 2, 3, 6, 9, 12].map((count) => ({
  value: String(count),
  label_key: count === 1 ? "reports.input.months_one" : "reports.input.months_other",
  params: { count },
}));

/** The contract's `controls.inputs`, verbatim in shape. */
const INPUTS = [
  {
    param: "services",
    kind: "multi",
    label_key: "reports.rateImpact.input.services",
    options: [
      { value: "water", label: "Water" },
      { value: "electric", label: "Electric" },
      { value: "trash", label: "Trash" },
    ],
  },
  {
    param: "classes",
    kind: "multi",
    label_key: "reports.rateImpact.input.classes",
    options: [
      { value: "residential", label: "Residential" },
      { value: "commercial", label: "Commercial" },
    ],
    all_label_key: "reports.input.allClasses",
  },
  { param: "months", kind: "select", label_key: "reports.rateImpact.input.months", default: "12", options: MONTHS },
  {
    param: "rows",
    kind: "table",
    label_key: "reports.rateImpact.input.rows",
    add_label_key: "reports.rateImpact.input.addRow",
    columns: [
      {
        name: "type",
        kind: "select",
        options: [
          { value: "rate", label_key: "reports.rateImpact.input.type.rate" },
          { value: "charge", label_key: "reports.rateImpact.input.type.charge" },
        ],
      },
      { name: "item", kind: "select", choices: "items", depends_on: "type" },
      { name: "version", kind: "select", choices: "versions", depends_on: "item" },
      { name: "effective_from", kind: "display", from: "versions" },
      { name: "service", kind: "display", from: "items" },
      { name: "capacity", kind: "select", choices: "capacities", depends_on: "version" },
      { name: "base", kind: "money", now_from: "capacities" },
      { name: "price", kind: "unit_price", now_from: "capacities", hidden_for_item_kinds: ["capacity", "charge"] },
      { name: "min", kind: "money", now_from: "capacities", hidden_for_item_kinds: ["capacity", "charge"] },
    ],
    choices: {
      items: [
        { value: "t-wrf", label: "Water · Residential Flat", type: "rate", service: "water", service_label: "Water", item_kind: "metered", unit: "kgal", item_noun: "" },
        { value: "t-trc", label: "Trash · Residential Carts", type: "rate", service: "trash", service_label: "Trash", item_kind: "capacity", unit: "", item_noun: "cart" },
        { value: "c-inf", label: "Infrastructure fee", type: "charge", service: "water", service_label: "Water", item_kind: "charge", unit: "", item_noun: "" },
      ],
      // The server's labels, as `rating.rate_impact_reads.versions` serves
      // them: `v<n>` and an `in_force` flag. The *· in force* is the SCREEN's
      // word, in eleven languages (walk of 2026-10-12).
      versions: [
        { value: "v-wrf-3", label: "v3", item: "t-wrf", effective_from: "2026-01-01", in_force: true },
        { value: "v-wrf-2", label: "v2", item: "t-wrf", effective_from: "2025-07-01", in_force: false },
        { value: "v-trc-2", label: "v2", item: "t-trc", effective_from: "2026-01-01", in_force: true },
        { value: "v-inf-2", label: "v2", item: "c-inf", effective_from: "2025-10-01", in_force: true },
      ],
      capacities: [
        { value: "58", label: '5/8" meter', version: "v-wrf-3", now: { base: "8.5000", price: "4.2500", min: "10.0000" } },
        { value: "1", label: '1" meter', version: "v-wrf-3", now: { base: "14.0000", price: "4.2500", min: "16.0000" } },
        { value: "58", label: '5/8" meter', version: "v-wrf-2", now: { base: null, price: null, min: null } },
        { value: "64", label: "64-gal cart", version: "v-trc-2", now: { base: "14.0000", price: null, min: null } },
        { value: "", label: "All sizes", version: "v-inf-2", now: { base: "3.0000", price: null, min: null } },
      ],
    },
    shortcuts: [
      { kind: "percent", label_key: "reports.rateImpact.input.changeAll", options: ["-10", "-5", "2", "3", "5", "8", "10", "15", "20"] },
    ],
  },
];

const MONEY = { type: "money", unit: null, unit_from: null, money_basis: "posting", scale: 4 };

function group(value: string, rows: number, now: string, proposed: string, change: string) {
  return {
    __kind__: "group",
    level: 0,
    dimension: "item",
    value,
    path: [{ dimension: "item", column: "item", value }],
    filters: null,
    drill_unavailable: "rate_impact_no_drill",
    rows,
    subtotals: { revenue_now: now, revenue_proposed: proposed, change, change_pct: "7.6", accounts: 1100 },
  };
}

const RATE_IMPACT = {
  key: "rate_impact",
  name: "Rate Impact",
  basis: "posting",
  window: { start: "2025-10-01", end: "2026-09-30" },
  currency: "USD",
  columns: ["capacity", "class", "accounts", "usage", "items", "revenue_now", "revenue_proposed", "change", "change_pct"],
  column_meta: {
    accounts: { type: "count", unit: null, unit_from: null, money_basis: null, scale: null },
    usage: { type: "quantity", unit: null, unit_from: "unit", money_basis: null, scale: 6 },
    items: { type: "count", unit: null, unit_from: "item_noun", money_basis: null, scale: null },
    revenue_now: MONEY,
    revenue_proposed: MONEY,
    change: MONEY,
    change_pct: { type: "percent", unit: null, unit_from: null, money_basis: null, scale: 6 },
  },
  rows: [
    group("Water · Residential Flat · v3, from 01-Jan-2026", 1, "392700.0000", "422400.0000", "29700.0000"),
    {
      capacity: '5/8" meter',
      class: "Residential",
      accounts: 1100,
      usage: "66000.000000",
      unit: "kgal",
      items: null,
      item_noun: null,
      revenue_now: "392700.0000",
      revenue_proposed: "422400.0000",
      change: "29700.0000",
      change_pct: "7.6",
    },
    group("Trash · Residential Carts · v2, from 01-Jan-2026", 1, "137760.0000", "147600.0000", "9840.0000"),
    {
      capacity: "64-gal cart",
      class: "Residential",
      accounts: 820,
      usage: null,
      unit: null,
      items: 820,
      item_noun: "carts",
      revenue_now: "137760.0000",
      revenue_proposed: "147600.0000",
      change: "9840.0000",
      change_pct: "7.1",
    },
  ],
  kpis: [
    { key: "revenue_now", value: "530460.0000", kind: "money", detail: null, reason_code: null },
    { key: "revenue_proposed", value: "570000.0000", kind: "money", detail: null, reason_code: null },
    { key: "change", value: "39540.0000", kind: "money", detail: null, reason_code: null },
    { key: "change_pct", value: "7.5", kind: "percent", detail: null, reason_code: null },
  ],
  totals: { revenue_now: "530460.0000", revenue_proposed: "570000.0000", change: "39540.0000" },
  unavailable: [
    { code: "no_bills_in_period", br_ref: "", detail: "", count: 3, message_key: "reports.gap.no_bills_in_period" },
    { code: "no_plan_on_unit", br_ref: "", detail: "", count: 1, message_key: "reports.gap.no_plan_on_unit" },
    { code: "size_today_used", br_ref: "", detail: "" },
  ],
  exportable: false,
  controls: { sorts: [], sort: "", dir: "asc", searchable: false, inputs: INPUTS },
};

const REGISTER = {
  key: "billing_register",
  basis: "posting",
  window: { start: "2026-09-01", end: "2026-09-30" },
  currency: "USD",
  columns: ["invoice_no", "account_no", "amount"],
  rows: [{ invoice_id: "i1", invoice_no: "BL-2609-000001", account_no: "100244", amount: "247.87" }],
  kpis: [],
  totals: { amount: "247.87" },
  unavailable: [],
  grain: "bill",
  page: { page: 1, per: 50, total: 1, pages: 1 },
  controls: { sorts: ["invoice_no"], sort: "invoice_no", dir: "asc", searchable: true },
};

function fakeServer(): { client: ApiClient; calls: URLSearchParams[] } {
  const calls: URLSearchParams[] = [];
  const get = async (path: string) => {
    if (path.startsWith("/reports/")) {
      const [bare, search = ""] = path.split("?");
      calls.push(new URLSearchParams(search));
      return { data: bare === "/reports/rate_impact" ? RATE_IMPACT : REGISTER, status: 200 };
    }
    if (path === "/reports") {
      return {
        data: { cards: [], vocabularies: { services: [], bill_types: ["regular"], purposes: [] } },
        status: 200,
      };
    }
    if (path.startsWith("/lookups/")) return { data: { results: [], count: 0 }, status: 200 };
    return { data: {}, status: 200 };
  };
  const write = async () => ({ data: {}, status: 200 });
  return {
    calls,
    client: { request: get, get, post: write, put: write, patch: write, delete: write } as unknown as ApiClient,
  };
}

function mount(client: ApiClient, segment: string, search: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  // ⚠ THE REAL PATH PATTERN — `/:tenant/reports/:reportKey`.
  const router = createMemoryRouter(
    [
      {
        path: `/:tenant${REPORTS_ROUTE}/:reportKey`,
        element: <ReportViewerPage client={client} timeZone="America/Chicago" today="2026-10-12" />,
      },
    ],
    { initialEntries: [`/${TENANT}${REPORTS_ROUTE}/${segment}${search}`] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return router;
}

const OPEN = "?in.services=water,trash&in.classes=residential&in.months=12";

function table(): HTMLElement {
  const found = document.querySelector<HTMLElement>('[data-array="input-rows"]');
  if (found === null) throw new Error("the table input was not drawn");
  return found;
}

function cells(name: string): HTMLElement[] {
  return Array.from(table().querySelectorAll<HTMLElement>(`[data-cell="rows.${name}"]`));
}

function pick(name: string, index: number, label: string): void {
  const select = cells(name)[index] as HTMLSelectElement;
  const option = Array.from(select.options).find((one) => one.textContent === label);
  if (option === undefined) {
    throw new Error(`${name}[${index}] offers no "${label}" — it offers ${Array.from(select.options).map((one) => one.textContent).join(" | ")}`);
  }
  fireEvent.change(select, { target: { value: option.value } });
}

function optionLabels(name: string, index: number): string[] {
  return Array.from((cells(name)[index] as HTMLSelectElement).options).map((one) => one.textContent ?? "");
}

async function opened(segment = "rate-impact", search = OPEN) {
  const server = fakeServer();
  const router = mount(server.client, segment, search);
  await waitFor(() => expect(server.calls.length).toBeGreaterThan(0));
  return { ...server, router };
}

async function waterRow(index = 0, version = "v3 · in force") {
  pick("type", index, "Rate schedule");
  pick("item", index, "Water · Residential Flat");
  pick("version", index, version);
  pick("capacity", index, '5/8" meter');
}

describe("CR-179 · the standard viewer draws a report's declared inputs", () => {
  it("draws the multi and select inputs, each summarising what is picked", async () => {
    await opened();
    await waitFor(() => expect(screen.getByText("Services")).toBeTruthy());
    expect(screen.getByText("Customer classes")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Services" }).textContent).toContain("Water, Trash");
    expect(screen.getByRole("button", { name: "Customer classes" }).textContent).toContain("Residential");
    const months = screen.getByLabelText("Usage period") as HTMLSelectElement;
    expect(months.value).toBe("12");
    expect(Array.from(months.options).map((one) => one.textContent)).toEqual([
      "1 month",
      "2 months",
      "3 months",
      "6 months",
      "9 months",
      "12 months",
    ]);
  });

  it("reads the all-label when every class is picked", async () => {
    await opened("rate-impact", "?in.services=water");
    await waitFor(() => expect(screen.getByRole("button", { name: "Customer classes" })).toBeTruthy());
    expect(screen.getByRole("button", { name: "Customer classes" }).textContent).toContain("All classes");
  });

  it("adds and removes rows of the table, and draws its columns", async () => {
    await opened();
    await waitFor(() => expect(table()).toBeTruthy());
    expect(within(table()).getByText("No rows yet. Add a row.")).toBeTruthy();
    fireEvent.click(within(table()).getByText("+ Add a row"));
    const headers = Array.from(table().querySelectorAll("th")).map((one) => one.textContent);
    expect(headers).toEqual(
      expect.arrayContaining(["Type", "Item", "Version", "Effective from", "Service", "Capacity", "Base / month", "Price per unit", "Minimum"]),
    );
    fireEvent.click(within(table()).getByText("+ Add a row"));
    expect(cells("type")).toHaveLength(2);
    fireEvent.click(within(table()).getAllByRole("button", { name: /^Remove row/ })[0]);
    expect(cells("type")).toHaveLength(1);
  });

  it("filters each dependent choice by the one before it", async () => {
    await opened();
    await waitFor(() => expect(table()).toBeTruthy());
    fireEvent.click(within(table()).getByText("+ Add a row"));
    expect((cells("item")[0] as HTMLSelectElement).disabled).toBe(true);
    pick("type", 0, "Rate schedule");
    expect(optionLabels("item", 0)).toEqual(["Choose", "Water · Residential Flat", "Trash · Residential Carts"]);
    pick("type", 0, "Charge code");
    expect(optionLabels("item", 0)).toEqual(["Choose", "Infrastructure fee"]);
    // One version and one size — each picked for the clerk.
    pick("item", 0, "Infrastructure fee");
    expect((cells("version")[0] as HTMLSelectElement).selectedOptions[0].textContent).toBe("v2 · in force");
    expect((cells("capacity")[0] as HTMLSelectElement).selectedOptions[0].textContent).toBe("All sizes");
    pick("type", 0, "Rate schedule");
    pick("item", 0, "Water · Residential Flat");
    expect(optionLabels("version", 0)).toEqual(["Choose", "v3 · in force", "v2"]);
    pick("version", 0, "v3 · in force");
    expect(optionLabels("capacity", 0)).toEqual(["Choose", '5/8" meter', '1" meter']);
    expect(within(table()).getByText("01/01/2026")).toBeTruthy();
    expect(within(table()).getAllByText("Water").length).toBeGreaterThan(0);
  });

  it("starts each box at its now figure and shows it — Billed where not flat", async () => {
    await opened();
    await waitFor(() => expect(table()).toBeTruthy());
    fireEvent.click(within(table()).getByText("+ Add a row"));
    await waterRow();
    expect((cells("base")[0] as HTMLInputElement).value).toBe("8.50");
    expect((cells("price")[0] as HTMLInputElement).value).toBe("4.25");
    expect((cells("min")[0] as HTMLInputElement).value).toBe("10.00");
    const nows = Array.from(table().querySelectorAll("[data-now]")).map((one) => one.textContent);
    expect(nows).toEqual(["now $8.50", "now $4.25", "now $10.00"]);
    // The SAME size on an older version is not flat: Billed, and empty boxes.
    pick("version", 0, "v2");
    pick("capacity", 0, '5/8" meter');
    expect(Array.from(table().querySelectorAll("[data-now]")).map((one) => one.textContent)).toEqual([
      "now Billed",
      "now Billed",
      "now Billed",
    ]);
    expect((cells("base")[0] as HTMLInputElement).value).toBe("");
  });

  it("hides price and minimum for capacity-billed and charge items", async () => {
    await opened();
    await waitFor(() => expect(table()).toBeTruthy());
    fireEvent.click(within(table()).getByText("+ Add a row"));
    fireEvent.click(within(table()).getByText("+ Add a row"));
    pick("type", 0, "Rate schedule");
    pick("item", 0, "Trash · Residential Carts");
    pick("capacity", 0, "64-gal cart");
    pick("type", 1, "Charge code");
    pick("item", 1, "Infrastructure fee");
    expect(cells("base")).toHaveLength(2);
    expect(cells("price")).toHaveLength(0);
    expect(cells("min")).toHaveLength(0);
    expect(table().querySelector('[data-now="rows.base"]')?.textContent).toBe("now $14.00per cart");
  });

  it("the percent shortcut fills every box from its now figure", async () => {
    await opened();
    await waitFor(() => expect(table()).toBeTruthy());
    fireEvent.click(within(table()).getByText("+ Add a row"));
    await waterRow();
    const fill = screen.getByRole("button", { name: "Fill" }) as HTMLButtonElement;
    expect(fill.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Change all prices"), { target: { value: "5" } });
    fireEvent.click(fill);
    // 8.50 × 1.05 = 8.925 → money box at 2; 4.25 × 1.05 = 4.4625 → a price keeps 4.
    expect((cells("base")[0] as HTMLInputElement).value).toBe("8.93");
    expect((cells("price")[0] as HTMLInputElement).value).toBe("4.4625");
    expect((cells("min")[0] as HTMLInputElement).value).toBe("10.50");
  });

  it("Run sends the rows as ONE JSON string with services, classes and months — and typing sends nothing", async () => {
    const { calls, router } = await opened();
    await waitFor(() => expect(table()).toBeTruthy());
    fireEvent.click(within(table()).getByText("+ Add a row"));
    const run = screen.getByRole("button", { name: "Run report" }) as HTMLButtonElement;
    expect(run.disabled).toBe(true);
    await waterRow();
    fireEvent.change(cells("base")[0], { target: { value: "9" } });
    fireEvent.change(cells("price")[0], { target: { value: "4.6" } });
    const before = calls.length;
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(calls.length).toBe(before);
    expect(run.disabled).toBe(false);
    fireEvent.click(run);
    await waitFor(() => expect(calls.length).toBe(before + 1));
    const sent = calls[calls.length - 1];
    expect(sent.get("services")).toBe("water,trash");
    expect(sent.get("classes")).toBe("residential");
    expect(sent.get("months")).toBe("12");
    expect(JSON.parse(sent.get("rows") ?? "null")).toEqual([
      { type: "rate", item: "t-wrf", version: "v-wrf-3", capacity: "58", base: "9", price: "4.6", min: "10.00" },
    ]);
    // …and the link reopens with them.
    expect(new URLSearchParams(router.state.location.search).get("in.rows")).toBe(sent.get("rows"));
  });

  it("renders the grouped result with Capacity, units beside figures, subtotals, totals and KPIs", async () => {
    await opened();
    await waitFor(() => expect(screen.getByText(/Water · Residential Flat · v3, from/)).toBeTruthy());
    const head = Array.from(document.querySelectorAll("th")).map((one) => one.textContent);
    expect(head).toEqual(expect.arrayContaining(["Capacity", "Usage", "Items", "Revenue now (billed)", "Revenue proposed", "Change"]));
    // A group with no drill is a plain label that still opens.
    const groupLabel = screen.getByText(/Water · Residential Flat · v3, from/);
    expect(groupLabel.closest("a")).toBeNull();
    const groupRow = groupLabel.closest("tr") as HTMLElement;
    expect(within(groupRow).getByText("$392,700.00")).toBeTruthy();
    expect(screen.queryByText('5/8" meter')).toBeNull();
    fireEvent.click(within(groupRow).getByRole("button"));
    await waitFor(() => expect(screen.getByText('5/8" meter')).toBeTruthy());
    expect(screen.getByText("66,000 kgal")).toBeTruthy();
    fireEvent.click(within(screen.getByText(/Trash · Residential Carts/).closest("tr") as HTMLElement).getByRole("button"));
    await waitFor(() => expect(screen.getByText("820 carts")).toBeTruthy());
    expect(screen.getAllByText("$530,460.00").length).toBeGreaterThan(0);
    expect(screen.getByText("Now (billed)")).toBeTruthy();
  });

  it("lists Not worked out by reason, and Proposed figures used from the committed rows", async () => {
    const rows = JSON.stringify([
      { type: "rate", item: "t-wrf", version: "v-wrf-3", capacity: "58", base: "9.00", price: "4.60", min: "10.00" },
    ]);
    await opened("rate-impact", `${OPEN}&in.rows=${encodeURIComponent(rows)}`);
    await waitFor(() => expect(screen.getByText("Not worked out")).toBeTruthy());
    expect(screen.getByText("3 accounts · No bills in the period")).toBeTruthy();
    expect(screen.getByText("1 account · No plan on the unit")).toBeTruthy();
    expect(screen.getByText("Today's size used for every month.")).toBeTruthy();
    const used = document.querySelector('[data-input-used]') as HTMLElement;
    expect(within(used).getByText("Proposed figures used")).toBeTruthy();
    expect(used.textContent).toContain('Water · Residential Flat · v3 · in force · 5/8" meter (01/01/2026)');
    expect(used.textContent).toContain("Base / month $8.50 → $9.00");
    expect(used.textContent).toContain("Price per unit $4.25 → $4.60");
    // The committed row reopened into the table, too.
    expect((cells("base")[0] as HTMLInputElement).value).toBe("9.00");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// The browser walk of 2026-10-12 (`05-prototype/rate-impact-2026-10-12/walk/`)
// ═══════════════════════════════════════════════════════════════════════════
describe("CR-179 · the walk of 2026-10-12", () => {
  it("a version reads v3 · in force, and picking an item starts the row on the version in force", async () => {
    // RED before: the version box stayed on "Choose", and a server label `v3`
    // read bare (the walk saw `2026-09-20`, the server's fallback then).
    await opened();
    await waitFor(() => expect(table()).toBeTruthy());
    fireEvent.click(within(table()).getByText("+ Add a row"));
    pick("type", 0, "Rate schedule");
    pick("item", 0, "Water · Residential Flat");
    expect(optionLabels("version", 0)).toEqual(["Choose", "v3 · in force", "v2"]);
    expect((cells("version")[0] as HTMLSelectElement).selectedOptions[0].textContent).toBe("v3 · in force");
    // …so its effective date and its capacities are there without another pick.
    expect(within(table()).getByText("01/01/2026")).toBeTruthy();
    expect(optionLabels("capacity", 0)).toEqual(["Choose", '5/8" meter', '1" meter']);
  });

  it("every dropdown of a row is as wide as its longest choice, never a bare chevron", async () => {
    // RED before: the selects were `input` alone — 100% of a column the table
    // squeezed, so at 1280 Type and Item showed no text at all.
    await opened();
    await waitFor(() => expect(table()).toBeTruthy());
    fireEvent.click(within(table()).getByText("+ Add a row"));
    for (const name of ["type", "item", "version", "capacity"]) {
      expect(cells(name)[0].className.split(" ")).toContain("min-w-max");
    }
    // The table scrolls inside its own box rather than cutting a word off.
    expect(table().querySelector(".overflow-x-auto")).not.toBeNull();
  });

  it("a group's ACCOUNTS is a count, grouped, never money; usage is grouped and stays on one line", async () => {
    // RED before: the walk read `$47.00` in ACCOUNTS (the server declared no
    // kind — fixed server-side, `test_tc_walk_the_accounts_column_is_a_count`),
    // `1100` here, and `114500 kWh` with the unit wrapped.
    await opened();
    const label = await waitFor(() => screen.getByText(/Water · Residential Flat · v3, from/));
    const groupRow = label.closest("tr") as HTMLElement;
    const texts = Array.from(groupRow.querySelectorAll("td")).map((cell) => cell.textContent);
    expect(texts).toContain("1,100");
    expect(texts.some((text) => text === "$1,100.00")).toBe(false);
    fireEvent.click(within(groupRow).getByRole("button"));
    const usage = await waitFor(() => screen.getByText("66,000 kgal"));
    expect(usage.className.split(" ")).toContain("whitespace-nowrap");
    const factRow = usage.closest("tr") as HTMLElement;
    expect(Array.from(factRow.querySelectorAll("td")).map((cell) => cell.textContent)).toContain("1,100");
  });
});

describe("CR-179 · a report that declares no inputs is drawn exactly as before", () => {
  it("billing_register keeps its window, bill type and service, and gains no Run, no table and no in. params", async () => {
    const { calls } = await opened("billing-register", "?f.from=2026-09-01&f.to=2026-09-30");
    await waitFor(() => expect(screen.getByText("BL-2609-000001")).toBeTruthy());
    expect(screen.getByLabelText("From")).toBeTruthy();
    expect(screen.getByLabelText("To")).toBeTruthy();
    expect(screen.getByLabelText("Bill type")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Run report" })).toBeNull();
    expect(document.querySelector('[data-array="input-rows"]')).toBeNull();
    expect(document.querySelector("[data-counted-gaps]")).toBeNull();
    expect(calls[0].toString()).toBe("from=2026-09-01&to=2026-09-30");
  });
});

describe("CR-179 · scaleByPercent moves a figure exactly, at four places", () => {
  it("rounds half away from zero and never touches a float", () => {
    expect(scaleByPercent("8.50", "5")).toBe("8.9250");
    expect(scaleByPercent("0.105", "-10")).toBe("0.0945");
    expect(scaleByPercent("14.00", "2.5")).toBe("14.3500");
    expect(scaleByPercent("0.123456", "10")).toBe("0.1358");
    expect(scaleByPercent("-1.00005", "0")).toBe("-1.0001");
  });
});
