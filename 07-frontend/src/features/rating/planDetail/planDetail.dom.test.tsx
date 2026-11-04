// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 7 — the plan DETAILS page, built from
//           images 24–37 of 05-prototype/plans-2026-10-03.
// Defects:  DEF-RAT-9334 · DEF-RAT-9331 · DEF-RAT-9288 · DEF-RAT-9286 ·
//           DEF-RAT-9285 (details half) · DEF-RAT-9352 (Duplicate held) ·
//           DEF-RAT-9353 (Units links) · CR-167 §5.5 L13 (Delete draft)
// Rules:    README rulings 2, 8, 11, 13, 15 · B14 rules 31, 33, 37 · hard-won
//           law 2 (the edit door is asserted by ADDRESS; a hold carries the
//           test that fires when it expires)
// ───────────────────────────────────────────────────────
/**
 * ONE CASE PER DRAWN FACT OF THE PLAN DETAILS PAGE, written before the page
 * was mounted and watched fail against the old `PlanDetail.tsx` (CR-167 §13
 * quotes each failure).
 *
 * ⚠ **NO DRAWN FIGURE IS ASSERTED AS A FACT (B14 rule 37).** The fixtures carry
 * their own names and numbers, so no case passes on a screen that hard-codes
 * the illustration.
 *
 * ⚠ **MOUNTED UNDER THE REAL ROUTE PATTERN** — `/:tenant/plans-rates/plans/
 * :planId`, with the edit door and the unit, premises and account pages
 * routed — so an address built wrongly cannot read as a good string.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { MyPermissions } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { PlanDetailPage } from "./PlanDetailPage";
import { normalisePlanSections } from "@/api/planFormEndpoints";

import { planDetailTabFrom, planEditDoor, planSectionEditDoor, rateRange, upcomingService } from "./planDetailModel";
import appSource from "../../../App.tsx?raw";

afterEach(cleanup);

const TENANT = "brazosbend";
const CLASS_ID = "01a1023a-e194-7b10-9c3d-000000000001";

function ref(id: string, kind: string, code: string, name: string, version: number, from: string, next: unknown = null) {
  return { id, kind, code, name, version, version_label: null, effective_from: from, effective_to: null, next };
}

/** Image 24's SHAPE with figures of its own: two services, a class, a note
 *  stored as the class's ID (the pre-§11 form), a later water schedule. */
function body(overrides: Record<string, unknown> = {}, rates = ["$3.10 per kgal", "$5.20 per kgal"]) {
  return {
    id: "plan-1",
    name: "Lakeside Homes",
    code: "LKH",
    status: "published",
    version: 1,
    accounts: 7,
    as_of: "2026-10-03",
    plan_version: { version: 1, status: "in_force", effective_from: "2026-08-01", effective_to: "2026-12-31", reason: null },
    versions: [
      { id: "pv-1", version_no: 1, version: 1, status: "in_force", effective_from: "2026-08-01", effective_to: "2026-12-31", reason: null },
    ],
    upcoming: [{ kind: "schedule", code: "LW", name: "Lakeside water", version: 6, effective_from: "2027-01-01" }],
    details: {
      name: "Lakeside Homes",
      code: "LKH",
      customer_classes: [{ value: CLASS_ID, label: "Residential" }],
      description: "Water and sewer for the lake homes.",
      intended_for: { cap_proof: false, min_demand_25kw: false, owner_occupied: true },
      notes: [{ attribute: "customer_class", operator: "is", value: CLASS_ID, value_label: "Residential" }],
      minimum_bill_display: "11.00",
      budget_billing: false,
    },
    services: [
      {
        service: "water",
        name: "Water",
        gl: { code: "4111", name: "Water revenue" },
        schedule: { ...ref("sch-lw", "schedule", "LW", "Lakeside water", 5, "2026-09-30", { version: 6, effective_from: "2027-01-01" }), model: "tiered", model_label: "Tiered" },
        base: {
          code: ref("bc-lw", "base_code", "BASE-LW", "Lake water base", 2, "2026-09-01"),
          sized_by_label: "meter size",
          by_size: [
            { size_class: "5_8", size_label: '5/8"', amount_display: "11.00" },
            { size_class: "2", size_label: '2"', amount_display: "41.00" },
          ],
          flat_display: null,
          state: "ok",
          codes: ["BASE-LW"],
          monthly_amount: "11.0000",
        },
        minimum: { by_size: [], flat_display: "6.00" },
        usage: { kind: "blocks", kind_label: "Block (per month)", rows: rates.map((rate, i) => ({ label: `Block ${i + 1}`, rate_display: rate })) },
        outside_city: { surcharged: true, percent_display: "20%" },
      },
      {
        service: "sewer",
        name: "Sewer",
        gl: { code: "4121", name: "Sewer revenue" },
        schedule: { ...ref("sch-ls", "schedule", "LS", "Lake sewer", 2, "2026-09-28"), model: "flat", model_label: "Flat" },
        base: { code: ref("bc-ls", "base_code", "BASE-LS", "Sewer base", 1, "2026-08-01"), sized_by_label: null, by_size: [], flat_display: "8.00", state: "ok", codes: ["BASE-LS"], monthly_amount: "8.0000" },
        minimum: { by_size: [], flat_display: null },
        usage: { kind: "flat", kind_label: null, rows: [{ label: "Each month", rate_display: "$13.00 flat" }] },
        outside_city: { surcharged: false, percent_display: null },
      },
    ],
    base_total: { amount_display: "19.00", unavailable: null },
    outside_city_surcharge: { percent_display: "20%", service_names: ["Water"] },
    charge_codes: [
      { ref: ref("cc-late", "charge_code", "LATEX", "Late fee", 1, "2026-08-01"), priced_by: "class", rows: [{ class_or_size_label: "Residential", amount_display: null, percent_display: "1.75%", min_display: "4.00" }], gl: { code: "2611", name: "Late fees" }, type_label: "Penalty", when_label: "After the due date" },
    ],
    taxes: [
      { ref: ref("tx-1", "tax", "STATE", "Lake State Tax", 1, "2026-01-01"), rate_display: "5.5%", rate_percent: "5.500000", what_is_taxed_label: "Usage and base charges", gl: { code: "2201", name: "Tax payable" }, authority: "Lake Revenue Office", brought_by: "jurisdiction" },
    ],
    combined_tax_rate_display: "5.5%",
    deposits: [
      { ref: ref("dp-1", "deposit_code", "DEP", "Security deposit", 2, "2026-09-01"), priced_by: "class", rows: [{ class_or_size_label: "Residential", amount_display: "125.00", percent_display: null, min_display: null }], gl: { code: "2301", name: "Deposits held" } },
    ],
    discounts: [
      { ref: ref("ds-1", "discount", "ELDER", "Elder discount", 1, "2026-08-01"), value_display: "12%", gl: { code: "4761", name: "Discounts" }, enrolled: 3, offered_from: "2026-08-01", offered_until: null },
    ],
    currency: "USD",
    ...overrides,
  };
}

const UNIT_ROWS = [
  { unit_id: "unit-a", unit_label: "Cabin 4", unit_no: null, premises_id: "prem-a", premises_address: "9 Shore Rd", premises_city: "Lakeside", services: [], account_id: null, account_no: null, account_closed: false, customer_name: null, vacant: true, assigned_from: "2026-08-01" },
  { unit_id: "unit-b", unit_label: "Cabin 5", unit_no: null, premises_id: "prem-a", premises_address: "9 Shore Rd", premises_city: "Lakeside", services: ["water", "sewer"], account_id: "acct-b", account_no: "AC-7001", account_closed: false, customer_name: "Ada Lake", vacant: false, assigned_from: "2026-09-15" },
];

const AUDIT_ROWS = [
  { id: "au-1", at: "2026-09-18T19:10:00Z", actor: { name: "Rosa Quintero" }, what: { kind: "plan", name: "Lakeside Homes" }, change: "correction", reason: "Wrong sewer schedule", before_display: "Services: Water, Sewer", after_display: "Services: Water", version: { kind: "plan", version: 1, effective_from: "2026-08-01" } },
  { id: "au-2", at: "2026-09-30T14:00:00Z", actor: { name: "Rosa Quintero" }, what: { kind: "schedule", name: "Lakeside water" }, change: "new_version", reason: "+5% across blocks", before_display: "Rate: $3.00", after_display: "Rate: $3.10", version: { kind: "schedule", version: null, effective_from: "2026-09-30" } },
  // DEF-RAT-10033 — a tax the plan uses, worded by the server.
  { id: "au-3", at: "2026-10-09T15:00:00Z", actor: { name: "Rosa Quintero" }, what: { kind: "tax", name: "City Utility Franchise Fee 2%" }, change: "edited", reason: "Council resolution 22", before_display: "Rate: 0.020000", after_display: "Rate: 0.060000", version: null, changes: [{ field: "Rate", before: "2.00%", after: "6.00%" }, { field: "Starts", before: "—", after: "11/01/2026" }] },
];

function permissions(access = "Full"): MyPermissions {
  return { role: "system_admin", role_name: "System Admin", permissions: [{ code: "plans_rates", label: "Plans & Rates", access }] };
}

interface Call {
  method: string;
  url: string;
  body?: unknown;
}

function client(calls: Call[], plan: Record<string, unknown>): ApiClient {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input, init) => {
      const url = String(input);
      const method = String(init?.method ?? "GET");
      calls.push({ method, url, body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined });
      let payload: unknown = plan;
      let type = "application/json";
      if (url.includes("format=csv")) {
        payload = "Unit,Premises\nCabin 4,9 Shore Rd\n";
        type = "text/csv";
      } else if (url.includes("/units")) {
        const rows = url.includes("f.occupancy=vacant") ? UNIT_ROWS.filter((row) => row.vacant) : UNIT_ROWS;
        payload = { count: rows.length, next: null, previous: null, results: rows };
      } else if (url.includes("/audit")) {
        const rows = url.includes("f.kind=underneath") ? AUDIT_ROWS.filter((row) => row.what.kind !== "plan") : AUDIT_ROWS;
        payload = { count: rows.length, next: null, previous: null, results: rows };
      } else if (url.includes("as_of=2027")) {
        payload = body({ upcoming: [] }, ["$3.40 per kgal", "$5.70 per kgal"]);
      } else if (url.endsWith("/duplicate")) {
        payload = { ...plan, id: "plan-copy", status: "draft", ...(typeof init?.body === "string" ? JSON.parse(init.body) : {}) };
      } else if (url.includes("/versions/") && url.endsWith("/publish")) {
        payload = { ...plan, version: 2 };
      } else if (method !== "GET") {
        payload = { ...plan, status: "archived" };
      }
      const text = typeof payload === "string" ? payload : JSON.stringify(payload);
      return new Response(method === "DELETE" ? null : text, {
        status: method === "DELETE" ? 204 : 200,
        headers: { "Content-Type": type },
      });
    },
  });
}

function Where() {
  const location = useLocation();
  return <p data-testid="landed">{`${location.pathname}${location.search}`}</p>;
}

function mount(plan: Record<string, unknown> = body(), search = "", calls: Call[] = [], access = "Full") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions(access));
  const id = String(plan.id);
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/plans-rates/plans/${id}${search}`]}>
          <Routes>
            <Route
              path="/:tenant/plans-rates/plans/:planId"
              element={<PlanDetailPage client={client(calls, plan)} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />}
            />
            <Route path="/:tenant/plans-rates/plans/:planId/edit" element={<Where />} />
            <Route path="/:tenant/plans-rates" element={<Where />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function tabNames(): string[] {
  return screen.getAllByRole("tab").map((tab) => tab.textContent?.trim() ?? "");
}

describe("CR-167 task 7 · the edit door is ONE agreed address (hard-won law 2)", () => {
  it("header Edit → ?change=info; a section's Edit → that step (image 37), by literal address", () => {
    expect(planEditDoor("p-1", "info")).toBe("/plans-rates/plans/p-1/edit?change=info");
    expect(planSectionEditDoor("p-1", "published", "services")).toBe("/plans-rates/plans/p-1/edit?change=change&step=1");
    expect(planSectionEditDoor("p-1", "published", "taxes")).toBe("/plans-rates/plans/p-1/edit?change=change&step=2");
    expect(planSectionEditDoor("p-1", "published", "billingTerms")).toBe("/plans-rates/plans/p-1/edit?change=change&step=3");
    expect(planSectionEditDoor("p-1", "draft", "charges")).toBe("/plans-rates/plans/p-1/edit?step=3");
    expect(appSource).toContain('path: "plans-rates/plans/:planId/edit"');
    expect(appSource).toContain("<PlanDetailPage />");
  });

  it("pressing Edit lands on the edit door with change=info", async () => {
    mount();
    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    expect(await screen.findByTestId("landed")).toHaveTextContent(`/${TENANT}/plans-rates/plans/plan-1/edit?change=info`);
  });
});

describe("CR-167 task 7 · header and tabs (images 24, 25) — DEF-RAT-9334", () => {
  it("six tabs, Units not Accounts, with the counts drawn (ruling 2)", async () => {
    mount();
    await screen.findByRole("heading", { name: /Lakeside Homes/ });
    expect(tabNames()).toEqual(["Overview", "Services2", "Charges", "Billing", "Units7", "Audit"]);
  });

  it("name and CODE, then status · v1 · class · window; no kicker", async () => {
    mount();
    const heading = await screen.findByRole("heading", { name: /Lakeside Homes/ });
    expect(within(heading).getByText("LKH")).toBeInTheDocument();
    const facts = document.querySelector("[data-plan-header-facts]") as HTMLElement;
    expect(facts).toHaveTextContent("Published");
    expect(facts).toHaveTextContent("V1");
    expect(facts).toHaveTextContent("Residential · 08/01/2026 – 12/31/2026");
    expect(document.body.textContent).not.toMatch(/Plan · LKH/);
  });

  it("the header is sticky", async () => {
    mount();
    await screen.findByRole("heading", { name: /Lakeside Homes/ });
    expect(document.querySelector("[data-plan-detail-header]")).toHaveClass("sticky", "top-0");
  });

  it("the tab is kept in the address, and old tab names land where their content is", () => {
    expect(planDetailTabFrom("versions")).toBe("audit");
    expect(planDetailTabFrom("accounts")).toBe("units");
    expect(planDetailTabFrom("taxes")).toBe("charges");
    expect(planDetailTabFrom("discounts")).toBe("billing");
    expect(planDetailTabFrom("nonsense")).toBe("overview");
  });

  it("arrow keys move between tabs (ruling 13)", async () => {
    mount();
    const overview = await screen.findByRole("tab", { name: "Overview" });
    overview.focus();
    fireEvent.keyDown(overview, { key: "ArrowRight" });
    await waitFor(() => expect(screen.getByRole("tab", { name: /Services/ })).toHaveAttribute("aria-selected", "true"));
    fireEvent.keyDown(screen.getByRole("tab", { name: /Services/ }), { key: "ArrowLeft" });
    await waitFor(() => expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true"));
  });

  it("More ▾ on a published plan: Duplicate and Retire live; no Delete draft (image 25)", async () => {
    mount();
    await screen.findByRole("heading", { name: /Lakeside Homes/ });
    expect(screen.getByTestId("plan-more-duplicate")).toBeEnabled();
    expect(screen.getByTestId("plan-more-retire")).toBeEnabled();
    expect(screen.queryByTestId("plan-more-delete-draft")).toBeNull();
  });

  it("CR-167 §5.5 L13: a DRAFT offers Delete draft in More ▾, confirmed as *removed for good*", async () => {
    const calls: Call[] = [];
    mount(body({ status: "draft" }), "", calls);
    await screen.findByRole("heading", { name: /Lakeside Homes/ });
    expect(screen.queryByTestId("plan-more-retire")).toBeNull();
    await userEvent.click(screen.getByTestId("plan-more-delete-draft"));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("The draft is removed for good.");
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete draft" }));
    await waitFor(() => expect(calls.some((call) => call.method === "DELETE" && call.url.endsWith("/plans/plan-1"))).toBe(true));
  });

  it("DEF-RAT-9352 (hold released): Duplicate asks a new name and code, copies, and opens the copy", async () => {
    const calls: Call[] = [];
    mount(body(), "", calls);
    await screen.findByRole("heading", { name: /Lakeside Homes/ });
    await userEvent.click(screen.getByTestId("plan-more-duplicate"));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Duplicate Lakeside Homes");
    expect(dialog).toHaveTextContent("Copies today's version. No units.");
    await userEvent.click(within(dialog).getByRole("button", { name: "Duplicate" }));
    expect(calls.some((call) => call.url.endsWith("/duplicate"))).toBe(false);
    await userEvent.type(within(dialog).getByLabelText(/^Plan name/), "Lakeside Homes 2027");
    await userEvent.type(within(dialog).getByLabelText(/^Code/), "LKH-27");
    await userEvent.click(within(dialog).getByRole("button", { name: "Duplicate" }));
    await waitFor(() =>
      expect(calls.find((call) => call.method === "POST" && call.url.endsWith("/plans/plan-1/duplicate"))?.body).toEqual({
        name: "Lakeside Homes 2027",
        code: "LKH-27",
      }),
    );
    // The copy opens: the page reads the NEW plan.
    await waitFor(() => expect(calls.some((call) => call.method === "GET" && /\/plans\/plan-copy(\?|$)/.test(call.url))).toBe(true));
  });

});

describe("DEF-RAT-9364 · a saved new version is published from the details page", () => {
  const withDraft = () =>
    body({
      versions: [
        { id: "pv-2", version_no: 2, version: 2, status: "draft", effective_from: "2027-01-01", effective_to: null, reason: "New council rates" },
        { id: "pv-1", version_no: 1, version: 1, status: "in_force", effective_from: "2026-08-01", effective_to: "2026-12-31", reason: null },
      ],
    });

  it("no draft version, no publish banner", async () => {
    mount();
    await screen.findByRole("heading", { name: /Lakeside Homes/ });
    expect(screen.queryByTestId("plan-draft-version")).toBeNull();
  });

  it("a draft v2 says so with Publish v2; the confirm states what ends; the server's call is made", async () => {
    const calls: Call[] = [];
    mount(withDraft(), "", calls);
    const banner = await screen.findByTestId("plan-draft-version");
    expect(banner).toHaveTextContent("v2 not published yet.");
    expect(banner).toHaveTextContent("Starts 01/01/2027.");
    await userEvent.click(within(banner).getByRole("button", { name: "Publish v2" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("Publish v2 of Lakeside Homes?");
    expect(dialog).toHaveTextContent("v1 ends 12/31/2026.");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish v2" }));
    await waitFor(() =>
      expect(calls.some((call) => call.method === "POST" && call.url.endsWith("/plans/plan-1/versions/2/publish"))).toBe(true),
    );
  });

  it("DEF-RAT-9506: a DRAFT plan's own v1 is not a saved new version — no banner (Edit publishes a draft)", async () => {
    mount(
      body({
        status: "draft",
        versions: [{ id: "pv-1", version_no: 1, version: 1, status: "draft", effective_from: null, effective_to: null, reason: null }],
      }),
    );
    await screen.findByRole("heading", { name: /Lakeside Homes/ });
    expect(screen.queryByTestId("plan-draft-version")).toBeNull();
  });

  it("read-only staff see the banner but cannot publish", async () => {
    mount(withDraft(), "", [], "View");
    const banner = await screen.findByTestId("plan-draft-version");
    expect(within(banner).getByRole("button", { name: "Publish v2" })).toBeDisabled();
  });
});

describe("CR-167 task 7 · Overview (image 24) — DEF-RAT-9331, DEF-RAT-9285", () => {
  it("customer classes and the note by NAME — never the id, never 'cannot be named'", async () => {
    mount();
    const details = await screen.findByRole("region", { name: "Details" }).catch(() => document.body);
    await screen.findByText("Customer classes");
    expect(document.querySelector('[data-fact="classes"]') ?? details).toHaveTextContent("Residential");
    expect(document.body.textContent).toContain("Customer class is Residential");
    expect(document.body.textContent).not.toContain(CLASS_ID);
    expect(document.body.textContent).not.toMatch(/cannot be named/);
  });

  it("nine facts, money with $, and the README's removed text is gone", async () => {
    mount();
    await screen.findByText("Customer classes");
    for (const label of ["Plan name", "Code", "Description", "Intended for", "Notes", "Starts", "Ends", "Minimum bill"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(document.body.textContent).toContain("$11.00");
    expect(document.body.textContent).toContain("$19.00");
    for (const gone of ["Revenue", "Exceptions", "How a plan works", "Sample bill", "Not recorded on a plan yet"]) {
      expect(document.body.textContent).not.toContain(gone);
    }
  });

  it("tiles open their tab (ruling 13)", async () => {
    mount();
    await screen.findByText("Customer classes");
    const href = (tab: string) => document.querySelector(`[data-plan-tile-link="${tab}"]`)?.getAttribute("href");
    expect(href("units")).toBe(`/${TENANT}/plans-rates/plans/plan-1?tab=units`);
    expect(href("services")).toBe(`/${TENANT}/plans-rates/plans/plan-1?tab=services`);
    expect(href("charges")).toBe(`/${TENANT}/plans-rates/plans/plan-1?tab=charges`);
  });

  it("the banner names the upcoming schedule with its own later prices, and See it opens that date", async () => {
    mount();
    const banner = await waitFor(() => {
      const found = document.querySelector("[data-plan-upcoming]");
      if (found === null) throw new Error("no banner yet");
      return found as HTMLElement;
    });
    expect(banner).toHaveTextContent("Water rate schedule v6 starts 01/01/2027.");
    await waitFor(() => expect(banner).toHaveTextContent("Usage charges $3.40 · $5.70 per kgal."));
    expect(within(banner).getByRole("link", { name: "See it" })).toHaveAttribute(
      "href",
      `/${TENANT}/plans-rates/plans/plan-1?tab=services&as_of=2027-01-01`,
    );
  });

  it("DEF-RAT-9515: a plan that starts later still names its upcoming schedule — one line per upcoming item", async () => {
    mount(
      body({
        upcoming: [
          { kind: "plan", code: "LKH", name: "Lakeside Homes", version: 1, effective_from: "2026-11-01" },
          { kind: "schedule", code: "LW", name: "Lakeside water", version: 6, effective_from: "2027-01-01" },
        ],
      }),
    );
    await waitFor(() => expect(document.querySelectorAll("[data-plan-upcoming]")).toHaveLength(2));
    const lines = [...document.querySelectorAll("[data-plan-upcoming]")].map((el) => el.textContent ?? "");
    expect(lines[0]).toContain("11/01/2026");
    expect(lines[1]).toContain("Water rate schedule v6 starts 01/01/2027.");
  });
});

describe("CR-167 task 7 · Services, Charges, Billing mount the shared sections (images 26–30, 37)", () => {
  it("services fold to one line; Show sizes opens one; Expand all opens every one", async () => {
    mount(body(), "?tab=services");
    const line = await screen.findByText((_, el) => el?.getAttribute("data-service-line") === "water");
    expect(line).toHaveTextContent("Base charges $11.00 – $41.00 · Usage charges $3.10 – $5.20 per kgal");
    expect(document.querySelector('[data-service-tables="water"]')).toBeNull();
    await userEvent.click(document.querySelector('[data-service-toggle="water"]') as HTMLElement);
    expect(document.querySelector('[data-service-tables="water"]')).not.toBeNull();
    expect(document.querySelector('[data-service-tables="sewer"]')).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Expand all/ }));
    expect(document.querySelector('[data-service-tables="sewer"]')).not.toBeNull();
    expect(screen.getByRole("button", { name: /Collapse all/ })).toBeInTheDocument();
  });

  it("every name is a link, with its version and from-date (rulings 8, 13)", async () => {
    mount(body(), "?tab=services");
    const schedule = await screen.findByRole("link", { name: "Lakeside water" });
    expect(schedule.getAttribute("href")).toContain("/plans-rates/rates/sch-lw");
    expect(screen.getByRole("link", { name: "BASE-LW" }).getAttribute("href")).toContain("/charge-codes/bc-lw");
    expect(document.body.textContent).toContain("from 09/30/2026");
  });

  it("a section's Edit opens that step of Edit (image 37)", async () => {
    mount(body(), "?tab=charges");
    await userEvent.click(await screen.findByRole("button", { name: "Edit Taxes" }));
    expect(await screen.findByTestId("landed")).toHaveTextContent(
      `/${TENANT}/plans-rates/plans/plan-1/edit?change=change&step=2`,
    );
  });

  it("Billing: deposits, discounts, billing terms with $ (image 30)", async () => {
    mount(body(), "?tab=billing");
    expect(await screen.findByRole("link", { name: "DEP" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "ELDER" })).toBeInTheDocument();
    expect(document.body.textContent).toContain("$125.00");
    expect(document.body.textContent).toContain("Not offered");
  });

  it("Priced as of a date reads the plan on that date (image 28)", async () => {
    const calls: Call[] = [];
    mount(body(), "?tab=services&as_of=2027-01-15", calls);
    await screen.findByText((_, el) => el?.getAttribute("data-service-line") === "water");
    expect(calls.some((call) => call.url.includes("as_of=2027-01-15"))).toBe(true);
    expect(document.querySelector('[data-service-line="water"]')).toHaveTextContent("$3.40 – $5.70 per kgal");
    expect(document.querySelector("[data-plan-upcoming]")).toBeNull();
  });

  it("a read-only role sees no section Edit", async () => {
    mount(body(), "?tab=charges", [], "View");
    await screen.findByText("Charge codes");
    expect(screen.queryByRole("button", { name: /^Edit Taxes$/ })).toBeNull();
  });
});

describe("CR-167 task 7 · Units (images 31–33) — DEF-RAT-9353", () => {
  it("unit, premises and account are links; a vacant unit says so; no Move, no selection (ruling 15)", async () => {
    mount(body(), "?tab=units");
    const unit = await screen.findByRole("link", { name: "Cabin 4" });
    expect(unit).toHaveAttribute("href", `/${TENANT}/premises/units/unit-a`);
    expect(screen.getAllByRole("link", { name: "9 Shore Rd" })[0]).toHaveAttribute("href", `/${TENANT}/premises/prem-a`);
    expect(screen.getByRole("link", { name: "AC-7001" })).toHaveAttribute("href", `/${TENANT}/accounts/acct-b`);
    expect(screen.getByText("No service point")).toBeInTheDocument();
    expect(screen.getAllByText("Vacant").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /Move units|another plan/i })).toBeNull();
    expect(document.querySelector('[data-plan-units] tbody input[type="checkbox"]')).toBeNull();
  });

  it("Vacant only asks the server (image 33)", async () => {
    const calls: Call[] = [];
    mount(body(), "?tab=units", calls);
    await screen.findByRole("link", { name: "Cabin 5" });
    await userEvent.click(document.querySelector('[data-occupancy="vacant"]') as HTMLElement);
    await waitFor(() => expect(calls.some((call) => call.url.includes("/units?") && call.url.includes("f.occupancy=vacant"))).toBe(true));
    await waitFor(() => expect(screen.queryByRole("link", { name: "Cabin 5" })).toBeNull());
  });

  it("CSV asks the server for the whole filtered set", async () => {
    const calls: Call[] = [];
    globalThis.URL.createObjectURL = () => "blob:units";
    globalThis.URL.revokeObjectURL = () => undefined;
    mount(body(), "?tab=units", calls);
    await screen.findByRole("link", { name: "Cabin 5" });
    await userEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    await waitFor(() => expect(calls.some((call) => call.url.includes("/units?") && call.url.includes("format=csv"))).toBe(true));
  });
});

describe("CR-167 task 7 · Audit (images 34–36) — DEF-RAT-9288", () => {
  it("rows in words; Changes underneath filters on the server; a row opens to Before → After · Version", async () => {
    const calls: Call[] = [];
    mount(body(), "?tab=audit", calls);
    expect(await screen.findByText("Fixed a mistake · v1")).toBeInTheDocument();
    expect(screen.getByText("Services: Water, Sewer → Services: Water")).toBeInTheDocument();
    expect(screen.getByText("Rate schedule · Lakeside water")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
    await userEvent.click(document.querySelector('[data-audit-kind="underneath"]') as HTMLElement);
    await waitFor(() => expect(calls.some((call) => call.url.includes("/audit?") && call.url.includes("f.kind=underneath"))).toBe(true));
    await waitFor(() => expect(screen.queryByText("Fixed a mistake · v1")).toBeNull());
    const expander = screen.getAllByRole("button", { expanded: false }).find((button) => button.closest("tr") !== null);
    await userEvent.click(expander as HTMLElement);
    const open = await screen.findByText("Before");
    const strip = open.closest("[data-plan-audit-open]") as HTMLElement;
    expect(strip).toHaveTextContent("Rate: $3.00");
    expect(strip).toHaveTextContent("Rate: $3.10");
    expect(strip).toHaveTextContent("Rate schedule from 09/30/2026");
  });

  it("DEF-RAT-10033 — a tax the plan uses says what changed, in words, never 'Edited'", async () => {
    mount(body(), "?tab=audit");
    expect(await screen.findByText("Tax · City Utility Franchise Fee 2%")).toBeInTheDocument();
    expect(screen.getByText("Rate: 2.00% → 6.00% · +1 more")).toBeInTheDocument();
    expect(screen.queryByText("Edited")).toBeNull();
    expect(document.body.textContent).not.toMatch(/0\.060000/);
  });
});

describe("DEF-RAT-10031 · the Versions table says what each version changed", () => {
  it("v2 reads Minimum bill: $10.00 → $12.00; a copy from before the fix is marked, not 'no change'", async () => {
    mount(
      body({
        versions: [
          { id: "pv-3", version_no: 3, version: 3, status: "scheduled", effective_from: "2027-06-01", effective_to: null, reason: null, change_words: [], terms_recorded: false },
          { id: "pv-2", version_no: 2, version: 2, status: "scheduled", effective_from: "2027-01-01", effective_to: "2027-05-31", reason: null, change_words: [{ field: "Minimum bill", before: "$10.00", after: "$12.00" }], terms_recorded: true },
          { id: "pv-1", version_no: 1, version: 1, status: "in_force", effective_from: "2026-08-01", effective_to: "2026-12-31", reason: null, change_words: [], terms_recorded: true },
        ],
      }),
    );
    expect(await screen.findByText("Minimum bill: $10.00 → $12.00")).toBeInTheDocument();
    const marked = document.querySelectorAll('[data-version-change="not-recorded"]');
    expect(marked).toHaveLength(1);
    expect(marked[0]).toHaveTextContent("Terms not recorded");
  });
});

describe("CR-167 task 7 · the model", () => {
  it("a range says shared words once; a list joins heads", () => {
    expect(rateRange(["$4.24 per kgal", "$6.89 per kgal", "$8.48 per kgal"])).toBe("$4.24 – $8.48 per kgal");
    expect(rateRange(["$4.45 per kgal", "$7.23 per kgal", "$8.90 per kgal"], " · ")).toBe("$4.45 · $7.23 · $8.90 per kgal");
    expect(rateRange(["$14.00 flat"])).toBe("$14.00 flat");
  });

  it("an upcoming schedule with no code finds its service by name, never the first blank code", () => {
    const sections = normalisePlanSections(
      body({}, ["$1.00 per kgal"]),
    );
    sections.services = sections.services.map((line) => ({
      ...line,
      schedule: line.schedule === null ? null : { ...line.schedule, code: "" },
    }));
    const found = upcomingService({ kind: "schedule", code: "", name: "Lake sewer", version: 3, effective_from: "2027-03-01" }, sections);
    expect(found?.service).toBe("sewer");
  });
});
