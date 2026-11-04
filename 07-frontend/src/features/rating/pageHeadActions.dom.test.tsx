// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-RAT-9101 — PO 2026-10-02 on the live list (2.439.7), verbatim:
//           "on list screen you need add rate schdule button on top right - it
//           was there before now it is not - it should open new rate schedule
//           form"
// Ruling:   decision log 2026-10-02, "PAGE ACTIONS ON A DETAILS VIEW OR A LIST
//           GO TOP-RIGHT IN THE PAGE HEAD … THE ADD/EDIT WIZARD KEEPS ITS
//           FOOTER AT THE BOTTOM"
// Rules:    B14 rule 2 (shared page-head, right-aligned actions)
// ───────────────────────────────────────────────────────
/**
 * Every Plans & Rates list tab puts its own "New …" in the page head, beside
 * History, and the Rate schedules one OPENS the three-step Add wizard.
 *
 * ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 clause 2):
 *   · finding the label anywhere on the page — the empty state's CTA carries the
 *     same words, so the list is given one row and the button is looked for
 *     INSIDE `.page-header-actions` only;
 *   · asserting the URL alone — the click is followed to the mounted wizard and
 *     its rendered step rail is counted, so a route that resolves to nothing
 *     fails.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { MyPermissions, TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { PlansRatesPage } from "./PlansRatesPage";
import { RateScheduleWizard } from "./RateScheduleWizard";

const TENANT = "brazosbend";
const t = (key: string) => i18n.t(key);

const PERMISSIONS = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "plans_rates", label: "Plans & Rates", access: "Full" }],
} as unknown as MyPermissions;

const SERVICES = [
  { service: "water", name: "Water", enabled: true, primary_uom: "kgal", alt_uom: null, billed_uom: null },
] as unknown as TenantServiceRow[];

const ROW = {
  id: "t-1",
  name: "Residential Water",
  service: "water",
  service_name: "Water",
  customer_class_name: null,
  base_code: null,
  sizes_priced: 0,
  sizes_total: 0,
  account_type_id: null,
  structure: "flat",
  status: "active",
  scheduled_change: null,
  current_version: null,
  draft_version: null,
  used_by_plans: 0,
  applied_to_accounts: 0,
  size_count: 0,
  season_labels: [],
  block_count: 0,
  window_count: 0,
  effective_from: "2026-01-01",
};

const CHARGE = {
  id: "chg-1",
  code: "BASE-W",
  name: "Water base",
  service: "water",
  kind: "base",
  is_base: true,
  charge_type: "recurring",
  amount_rule: "flat",
  amount: "8.0000",
  amount_display: "8.00",
  currency: "USD",
  status: "active",
  size_amounts: [],
  prices: [],
  price_range: null,
  applies_to_customer_classes: [],
  gl_account_id: null,
  gl_account_code: null,
  gl_account_name: null,
  taxable_default: false,
  auto_apply: true,
  waivable: false,
  separate_line: true,
  used_by_plans: 0,
  used_by_invoice_lines: 0,
};

function client(): ApiClient {
  const ok = <T,>(data: T) => ({ status: 200, data, etag: null, notModified: false });
  const page = (results: unknown[]) => ({ count: results.length, next: null, previous: null, results });
  return {
    get: vi.fn(async (path: string) => {
      if (path === "/plans") {
        return ok({ ...page([]), rollup: { plans: 0, rate_schedules: 1, charge_codes: 0, effective_from: null } });
      }
      if (path === "/rate-schedules") return ok(page([ROW]));
      if (path === "/charges") return ok({ ...page([CHARGE]), kind_counts: { all: 1, base: 1, plan: 0, other: 0 } });
      if (path === "/tenant/services") return ok(SERVICES);
      if (path.startsWith("/rate-schedules/percent-basis-options")) return ok({ results: [] });
      // Every other list (lookups, charges, discounts, taxes) answers empty.
      return ok(page([]));
    }),
    post: vi.fn(),
    request: vi.fn(),
  } as unknown as ApiClient;
}

function mount(url: string) {
  const c = client();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  qc.setQueryData(queryKeys.tenantServices, SERVICES);
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[url]}>
          <Routes>
            <Route path="/:tenant/plans-rates/rates/new" element={<RateScheduleWizard client={c} />} />
            <Route
              path="/:tenant/plans-rates/:tab"
              element={<PlansRatesPage client={c} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function pageHead(): HTMLElement {
  const head = document.querySelector<HTMLElement>(".page-header-actions");
  if (head === null) throw new Error("no page head actions");
  return head;
}

afterEach(cleanup);

describe("DEF-RAT-9101 — a list's New … is top-right in the page head, beside History", () => {
  it("Rate schedules: New rate schedule is in the page head and opens the three-step Add wizard", async () => {
    const user = userEvent.setup();
    mount(`/${TENANT}/plans-rates/rates`);
    await screen.findByText("Residential Water");
    const head = pageHead();
    expect(within(head).getByRole("button", { name: t("rating.tab.history") })).toBeInTheDocument();
    const add = within(head).getByRole("button", { name: t("rating.rates.new") });
    // Nothing below the table holds a page button any more.
    expect(document.querySelector("[data-rs-actions]")).toBeNull();
    await user.click(add);
    await waitFor(() => expect(document.querySelectorAll("[data-wizard-step]").length).toBe(3));
  });

  it("DEF-RAT-9103 — a service filter from the URL shows as the usual removable tag; removing it shows all services", async () => {
    const user = userEvent.setup();
    mount(`/${TENANT}/plans-rates/rates?f.service=water`);
    await screen.findByText("Residential Water");
    expect(document.querySelector("[data-quick-filter]")).toBeNull();
    const remove = await screen.findByRole("button", {
      name: i18n.t("table.filters.remove", { label: t("rating.filter.service") }),
    });
    await user.click(remove);
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: i18n.t("table.filters.remove", { label: t("rating.filter.service") }) }),
      ).toBeNull(),
    );
  });

  for (const [tab, key] of [
    ["plans", "rating.plans.new"],
    ["charge-codes", "rating.charges.new"],
    ["discounts", "rating.discounts.new"],
    ["taxes-fees", "rating.taxes.new"],
  ] as const) {
    it(`${tab}: its own New … sits in the page head beside History`, async () => {
      mount(`/${TENANT}/plans-rates/${tab}`);
      await waitFor(() => expect(within(pageHead()).getByRole("button", { name: t(key) })).toBeInTheDocument());
      expect(within(pageHead()).getByRole("button", { name: t("rating.tab.history") })).toBeInTheDocument();
    });
  }
});

/**
 * DEF-RAT-9112 — below 1440 (the 1280 laptop) both lists fit their 960px frame:
 * the lowest-value columns start behind the Columns picker, and the full set
 * stays one click away. At 1440 nothing changes.
 *
 * ⚠ WHAT WOULD MAKE THIS PASS WRONGLY: jsdom has no layout, so these read the
 * rendered HEADERS (what the clerk sees first), not widths; the widths were
 * measured in Chromium by `e2e/DEF-RAT-9101-rs-cc-sweep.spec.ts`.
 */
function stubWidth(narrow: boolean): void {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: narrow && query.includes("max-width"),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    onchange: null,
    dispatchEvent: () => false,
  }));
}
const headers = () =>
  [...document.querySelectorAll("table thead th")].map((th) => (th.textContent ?? "").replace("▲", "").trim());

describe("DEF-RAT-9112 — the lists fit 1280 without sideways scroll", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("rate schedules below 1440: Sizes and Plans start hidden; Schedule, Service, Status, Actions stay", async () => {
    stubWidth(true);
    mount(`/${TENANT}/plans-rates/rates`);
    await screen.findByText("Residential Water");
    const shown = headers();
    expect(shown).not.toContain(t("rating.rates.col.sizes"));
    expect(shown).not.toContain(t("rating.rates.col.plans"));
    for (const key of ["rating.rates.col.schedule", "rating.rs.col.service", "rating.col.status", "rating.col.actions"]) {
      expect(shown).toContain(t(key));
    }
  });

  it("rate schedules at 1440: all eleven columns, unchanged", async () => {
    stubWidth(false);
    mount(`/${TENANT}/plans-rates/rates`);
    await screen.findByText("Residential Water");
    expect(headers()).toContain(t("rating.rates.col.sizes"));
    expect(headers()).toContain(t("rating.rates.col.plans"));
  });

  it("charge codes below 1440: Priced by and GL account start hidden", async () => {
    stubWidth(true);
    mount(`/${TENANT}/plans-rates/charge-codes`);
    await waitFor(() => expect(headers()).toContain(t("rating.charges.col.code")));
    expect(headers()).not.toContain(t("rating.chargeCode.col.pricedBy"));
    expect(headers()).not.toContain(t("rating.charges.col.gl"));
    expect(headers()).toContain(t("rating.filter.service"));
  });
});
