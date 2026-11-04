// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 3 task 6 — the tax DETAILS page, built from
//           images 18–23 of 05-prototype/taxes-fees-2026-10-03.
// Defect:   DEF-RAT-9272 (P29–P43, reproduced on 2.467.27 before any fix)
// Rules:    PO rounds 6 and 7 · README points 3, 5, 7, 8 · B14 rules 31, 33,
//           37 · hard-won law 2 (the edit door is asserted by ADDRESS)
// ───────────────────────────────────────────────────────
/**
 * ONE CASE PER DRAWN FACT OF THE DETAILS PAGE, written against today's page
 * first and watched fail there.
 *
 * ⚠ **NO DRAWN FIGURE IS ASSERTED AS A FACT (B14 rule 37).** The drawing inks
 * `150%`, `47 of 84`, `$90.00` and `AA-CITY`; the fixtures below carry their
 * own numbers, chosen to look nothing like it, so no case passes by a screen
 * that hard-codes the illustration.
 *
 * ⚠ **THE PAGE IS MOUNTED UNDER THE REAL ROUTE PATTERN** (hard-won law 2's
 * fixture clause): `/:tenant/plans-rates/taxes-fees/:definitionId`, the edit
 * door under `…/:taxId/edit`, so an address the page builds wrongly cannot
 * read as a good string.
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
import type { TaxDetailRow } from "@/api/taxDetailEndpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { DefinitionDetailPage } from "../DefinitionDetailPage";
import { TAX_WIZARD_EDIT_PATTERN } from "../definitionDetail";
import { taxRowDefaults } from "../taxRowFixture";
import { auditChange, overTwentyEffect, taxEditDoor } from "./taxDetailModel";
import { taxDuplicatePath, taxFinishDraftPath } from "../taxForm/taxEditModel";
import taxDetailPageSource from "./TaxDetailPage.tsx?raw";
import appSource from "../../../App.tsx?raw";
import newTaxFormSource from "../taxForm/NewTaxWizard.tsx?raw";
import ddpSource from "../DefinitionDetailPage.tsx?raw";

afterEach(cleanup);

const TENANT = "brazosbend";
const REGIONAL = { timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" as const };
const t = (key: string, params?: Record<string, unknown>) => `${key}${params ? JSON.stringify(params) : ""}`;

/** A live percentage tax well over twenty, every round-2 field served. */
const HIGH: TaxDetailRow = {
  ...taxRowDefaults(),
  id: "tax-harbor",
  name: "Harbor Levy",
  jurisdiction: { id: "j-1", name: "Port of Harbor", authority: null, level: "city", reference_no: null },
  kind: "percent",
  rate: "0.375000",
  rate_display: "37.50%",
  applies_to_services: ["electric", "water"],
  applies_to_customer_classes: ["residential", "commercial"],
  premises_scope_kind: "city_limits",
  effective_from: "2026-03-14",
  effective_to: "2027-05-09",
  code: "HB-LEVY",
  bill_label: "Harbor levy",
  gl_account_code: "2399-07",
  gl_account_name: "Levy payable",
  filing_frequency: "monthly",
  due_date_rule: "25th_next_month",
  collection_allowance_percent_display: "0.75%",
  interest_penalty_percent_display: "1.25%",
  interest_penalty_basis: "monthly",
  filing_reminder_recipient: "levy@harbor.example",
  rounding_rule: "half_even",
  status: "active",
  used_by_plans: 4,
  version: 3,
  authority_account: { id: "aa-1", label: "Port Treasurer · PT-7731" },
  next_filing_due: "2026-10-25",
  scheduled_next: null,
  premises_reached: 13,
  premises_total: 29,
};

/** Low, scheduled to change — the drawing's image 22 shape. */
const STEADY: TaxDetailRow = {
  ...HIGH,
  id: "tax-steady",
  name: "Lakeside Utility Tax",
  code: null,
  kind: "percent",
  rate: "0.041000",
  rate_display: "4.10%",
  version: 1,
  scheduled_next: { rate_display: "4.35%", effective_from: "2027-02-01" },
};

function permissions(access = "Full"): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: "plans_rates", label: "Plans & Rates", access }],
  };
}

interface Call {
  method: string;
  url: string;
  body: unknown;
}

function client(calls: Call[], row: TaxDetailRow): ApiClient {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input, init) => {
      const url = String(input);
      const method = String(init?.method ?? "GET");
      calls.push({
        method,
        url,
        body: init?.body === undefined || init?.body === null ? null : JSON.parse(String(init.body)),
      });
      let body: unknown = {};
      if (url.includes("/audit")) {
        body = {
          count: 41,
          next: null,
          previous: null,
          results: [
            {
              at: "2026-09-28T16:05:00Z",
              actor: { id: "u-91f3", name: "Rosa Quintero" },
              action: "tax.updated",
              before: { effective_to: null },
              after: { effective_to: "2027-05-09" },
              reason: "Council extended it.",
            },
            {
              at: "2026-03-01T14:00:00Z",
              actor: null,
              action: "tax.created",
              before: null,
              after: { status: "draft", rate_display: "37.50%", applies_to_services: ["electric"] },
              reason: null,
            },
          ],
        };
      } else if (url.includes("/plans") && url.includes("/taxes/")) {
        body = [
          { id: "p-1", name: "Harbor Homes", reached_by: "jurisdiction", units: 19, accounts: 17 },
          { id: "p-2", name: "Dockside Shops", reached_by: "attached", units: 6, accounts: 6 },
        ];
      } else if (url.includes("/versions")) {
        body = [
          { id: "v-3", version: 3, amount_display: "37.50%", rate_display: "37.50%", effective_from: "2026-03-14", effective_to: "2027-05-09", status: "active", is_current: true, correction_reason: null, corrected_by: null },
          { id: "v-2", version: 2, amount_display: "2.90%", rate_display: "2.90%", effective_from: "2025-01-01", effective_to: "2026-03-13", status: "ended", is_current: false, correction_reason: null, corrected_by: null },
        ];
      } else if (url.includes("/retire")) {
        body = { ...row, effective_to: "2026-12-31" };
      } else {
        body = row;
      }
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    },
  });
}

function Where() {
  const location = useLocation();
  return <p data-testid="edit-door">{`${location.pathname}${location.search}`}</p>;
}

function mount(row: TaxDetailRow, calls: Call[] = [], search = "", access = "Full") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions(access));
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/plans-rates/taxes-fees/${row.id}${search}`]}>
          <Routes>
            <Route
              path="/:tenant/plans-rates/taxes-fees/:definitionId"
              element={
                <DefinitionDetailPage kind="tax" client={client(calls, row)} timeZone={REGIONAL.timeZone} dateFormat={REGIONAL.dateFormat} />
              }
            />
            <Route path={`/:tenant${TAX_WIZARD_EDIT_PATTERN}`} element={<Where />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-165 task 6 · the edit door is ONE agreed address (hard-won law 2)", () => {
  it("Edit opens ?change=info, Fix the rate opens ?change=correct — by literal address", () => {
    expect(taxEditDoor("t-1", "info")).toBe("/plans-rates/taxes-fees/t-1/edit?change=info");
    expect(taxEditDoor("t-1", "change")).toBe("/plans-rates/taxes-fees/t-1/edit?change=change");
    expect(taxEditDoor("t-1", "correct")).toBe("/plans-rates/taxes-fees/t-1/edit?change=correct");
    // The router still mounts something at that pattern.
    expect(TAX_WIZARD_EDIT_PATTERN).toBe("/plans-rates/taxes-fees/:taxId/edit");
    expect(appSource).toContain("TAX_WIZARD_EDIT_PATTERN.slice(1)");
  });

  it("pressing Edit lands on the edit door with change=info", async () => {
    mount(HIGH);
    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    expect(await screen.findByTestId("edit-door")).toHaveTextContent(
      `/${TENANT}/plans-rates/taxes-fees/tax-harbor/edit?change=info`,
    );
  });

  it("Fix the rate on the over-20% band lands on change=correct", async () => {
    mount(HIGH);
    await userEvent.click(await screen.findByRole("link", { name: "Fix the rate" }));
    expect(await screen.findByTestId("edit-door")).toHaveTextContent(
      `/${TENANT}/plans-rates/taxes-fees/tax-harbor/edit?change=correct`,
    );
  });
});

describe("CR-165 task 6 · the header (PO round 7) — P29, P30, P31, P35", () => {
  it("P29: no kicker repeating the kind and authority", async () => {
    mount(HIGH);
    await screen.findByRole("heading", { name: /Harbor Levy/ });
    expect(document.body.textContent).not.toMatch(/TAX · CITY/i);
    expect(document.querySelector(".page-header [data-kicker], .page-header .kicker")).toBeNull();
  });

  it("P30: name + code · Active · version · Over 20% · authority · dates · Filing due", async () => {
    mount(HIGH);
    const heading = await screen.findByRole("heading", { name: /Harbor Levy/ });
    expect(within(heading).getByText("HB-LEVY")).toBeInTheDocument();
    const facts = document.querySelector("[data-tax-header-facts]") as HTMLElement;
    expect(within(facts).getByText("Active")).toBeInTheDocument();
    expect(within(facts).getByText("V3")).toBeInTheDocument();
    expect(within(facts).getByText("Over 20%")).toBeInTheDocument();
    expect(within(facts).getByText("Port of Harbor · 03/14/2026 – 05/09/2027")).toBeInTheDocument();
    expect(facts.querySelector("[data-tax-header-due]")).toHaveTextContent("Filing due 10/25/2026");
    // Nothing is scheduled, so there is no Next.
    expect(facts.querySelector("[data-tax-header-next]")).toBeNull();
  });

  it("Next: shows only when a later version is saved; no Over 20% under twenty", async () => {
    mount(STEADY);
    await screen.findByRole("heading", { name: /Lakeside Utility Tax/ });
    const facts = document.querySelector("[data-tax-header-facts]") as HTMLElement;
    expect(facts.querySelector("[data-tax-header-next]")).toHaveTextContent("Next: 4.35% from 02/01/2027");
    expect(within(facts).queryByText("Over 20%")).toBeNull();
  });

  it("Filing due is for an ACTIVE tax only", async () => {
    mount({ ...STEADY, status: "scheduled" });
    await screen.findByRole("heading", { name: /Lakeside Utility Tax/ });
    expect(document.querySelector("[data-tax-header-due]")).toBeNull();
  });

  it("P31: no sentence under the title", async () => {
    mount(HIGH);
    await screen.findByRole("heading", { name: /Harbor Levy/ });
    expect(document.body.textContent).not.toContain("Live taxes are corrected, never edited");
    expect(document.body.textContent).not.toContain("Effective from:");
  });

  it("P35: ONE Edit plus More ▾ holding Duplicate and Retire — no other header button", async () => {
    mount(HIGH);
    await screen.findByRole("heading", { name: /Harbor Levy/ });
    const header = document.querySelector(".page-header") as HTMLElement;
    const buttons = within(header)
      .getAllByRole("button")
      .map((b) => b.textContent?.trim());
    expect(buttons.filter((name) => name === "Edit")).toHaveLength(1);
    expect(buttons).toContain("Duplicate");
    expect(buttons).toContain("Retire");
    expect(buttons).not.toContain("Save filing details");
    const more = header.querySelector("[data-tax-more]") as HTMLElement;
    expect(within(more).getByText("Duplicate")).toBeInTheDocument();
    expect(within(more).getByText("Retire")).toBeInTheDocument();
  });

  it("Retire asks for the last day and posts it to /retire", async () => {
    const calls: Call[] = [];
    mount(HIGH, calls);
    await screen.findByRole("heading", { name: /Harbor Levy/ });
    await userEvent.click(screen.getByText("More"));
    await userEvent.click(screen.getByTestId("tax-more-retire"));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/Last day it charges/), { target: { value: "2026-12-31" } });
    await userEvent.click(within(dialog).getByRole("button", { name: "Retire" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url.includes("/taxes/tax-harbor/retire"))).toBe(true));
    const post = calls.find((c) => c.url.includes("/retire"));
    expect(post?.body).toEqual({ effective_to: "2026-12-31" });
  });

  it("Duplicate opens the New form filled from this tax (DEF-RAT-9299 — the hold is released)", async () => {
    mount(HIGH);
    await screen.findByRole("heading", { name: /Harbor Levy/ });
    const duplicate = screen.getByTestId("tax-more-duplicate");
    expect(duplicate).not.toBeDisabled();
    expect(taxDuplicatePath("tax-harbor")).toBe("/plans-rates/taxes-fees/new?duplicate=tax-harbor");
    // DEF-RAT-9305 — a draft's Edit is the New form filled from the draft.
    expect(taxFinishDraftPath("tax-harbor")).toBe("/plans-rates/taxes-fees/new?draft=tax-harbor");
    expect(taxDetailPageSource).toMatch(/row\.status === "draft" \? taxFinishDraftPath/);
    expect(newTaxFormSource).toMatch(/DUPLICATE_PARAM/);
  });
});

describe("CR-165 task 6 · Overview — P32, P33, P34, P37, P39–P43", () => {
  it("tabs are Overview · Plans · Audit, Plans carries its count, no Rate history", async () => {
    mount(HIGH);
    const tabs = await screen.findAllByRole("tab");
    expect(tabs.map((tab) => tab.textContent?.replace(/\s+/g, "").trim())).toEqual(["Overview", "Plans4", "Audit"]);
    expect(document.body.textContent).not.toContain("Rate history");
  });

  it("P34: four tiles — Rate, Premises of total, Plans, Collected — and no invented figure", async () => {
    mount(HIGH);
    await screen.findByRole("heading", { name: /Harbor Levy/ });
    const tiles = Array.from(document.querySelectorAll(".kpi")).map((tile) => tile.textContent);
    expect(tiles).toEqual([
      "Rate37.50%of the taxed amount",
      "Premises13of 29",
      "Plans4using it",
      "Collected—Not counted yet",
    ]);
  });

  it("P34: over twenty warns with the example bill's figure and Fix the rate", async () => {
    mount(HIGH);
    await screen.findByRole("heading", { name: /Harbor Levy/ });
    const band = document.querySelector("[data-tax-over-20]") as HTMLElement;
    // 37.5% of the $60.00 example bill, worked by the New form's own arithmetic.
    expect(overTwentyEffect(HIGH)).toBe("22.50");
    expect(band).toHaveTextContent("37.50% is high. On a $60.00 bill this adds $22.50. Fix the rate");
  });

  it("no band at or under twenty", async () => {
    mount(STEADY);
    await screen.findByRole("heading", { name: /Lakeside Utility Tax/ });
    expect(document.querySelector("[data-tax-over-20]")).toBeNull();
  });

  it("P32 · P33: no Not worked out yet band, and no explaining sentence under a section", async () => {
    mount(HIGH);
    await screen.findByRole("heading", { name: "Rate and scope" });
    expect(document.body.textContent).not.toMatch(/not worked out yet/i);
    expect(document.body.textContent).not.toContain("These can be changed at any time");
    expect(document.body.textContent).not.toContain("The rate, and exactly what it is charged on.");
  });

  it("Rate and scope shows what the New form's steps 1–2 collected", async () => {
    mount(HIGH);
    await screen.findByRole("heading", { name: "Rate and scope" });
    const grid = document.querySelector('[data-facts="rate-scope"]') as HTMLElement;
    const read = (id: string) => grid.querySelector(`[data-fact="${id}"] dd`)?.textContent;
    expect(read("basis")).toBe("A percentage of the bill");
    expect(read("rate")).toBe("37.50%");
    expect(read("taxed")).toBe("Usage charges, Base charges");
    expect(read("services")).toBe("Electric, Water");
    expect(read("classes")).toBe("Residential, Commercial");
    expect(read("boundary")).toBe("Inside city limits");
    expect(read("from")).toBe("03/14/2026");
    expect(read("to")).toBe("05/09/2027");
    expect(read("discounts")).toBe("Tax the full amount · Half to even");
  });

  it("P37 · P41 · P42 · P43: filing is READ — every step-3 value, account as its label, percents as percents", async () => {
    mount(HIGH);
    await screen.findByRole("heading", { name: "On the bill and filing" });
    const grid = document.querySelector('[data-facts="bill-filing"]') as HTMLElement;
    const read = (id: string) => grid.querySelector(`[data-fact="${id}"] dd`)?.textContent;
    expect(read("code")).toBe("HB-LEVY");
    expect(read("billLabel")).toBe("Harbor levy");
    expect(read("liability")).toBe("2399-07 · Levy payable");
    expect(read("filed")).toBe("Monthly");
    expect(read("due")).toBe("25th of the next month");
    expect(read("authorityAccount")).toBe("Port Treasurer · PT-7731");
    expect(read("allowance")).toBe("0.75%");
    expect(read("interest")).toBe("1.25% / month");
    expect(read("reminder")).toBe("levy@harbor.example");
    // Nothing on Overview is typed into (P37): no box, no save.
    const overview = document.querySelector("[data-tax-overview]") as HTMLElement;
    expect(overview.querySelectorAll("input, select, textarea")).toHaveLength(0);
    expect(document.body.textContent).not.toMatch(/as a fraction/);
    // B14 rule 31 — the account's id never reaches the screen.
    expect(document.body.textContent).not.toContain("aa-1");
  });

  it("P39 · P40: a versions table on Overview, and See every change opens Audit", async () => {
    mount(HIGH);
    const table = await waitFor(() => {
      const found = document.querySelector("[data-tax-versions] tbody");
      if (found === null || found.children.length === 0) throw new Error("not yet");
      return found as HTMLElement;
    });
    const lines = Array.from(table.querySelectorAll("tr")).map((tr) => tr.textContent);
    expect(lines).toEqual(["V337.50%03/14/2026 – 05/09/2027Active", "V22.90%01/01/2025 – 03/13/2026Ended"]);
    const link = screen.getByRole("link", { name: "See every change in Audit" });
    expect(link).toHaveAttribute("href", `/${TENANT}/plans-rates/taxes-fees/tax-harbor?tab=audit`);
  });
});

describe("CR-165 task 6 · Plans and Audit tabs — P38", () => {
  it("Plans: an Accounts column, the totals, + Add to a plan, × only on an attachment", async () => {
    mount(HIGH, [], "?tab=plans");
    const table = await screen.findByRole("table");
    const heads = within(table).getAllByRole("columnheader").map((th) => th.textContent?.trim());
    expect(heads).toContain("Accounts");
    expect(within(table).getByRole("link", { name: "Harbor Homes" })).toHaveAttribute(
      "href",
      `/${TENANT}/plans-rates/plans/p-1`,
    );
    const totals = table.querySelector("[data-plan-totals]") as HTMLElement;
    expect(totals).toHaveTextContent("2 plans2325");
    const bound = table.querySelector('[data-plan-reach="jurisdiction"]') as HTMLElement;
    const attached = table.querySelector('[data-plan-reach="attached"]') as HTMLElement;
    expect(within(bound).queryByRole("button")).toBeNull();
    expect(within(attached).getByRole("button", { name: "Remove from Dockside Shops" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Add to a plan" })).toBeEnabled();
  });

  it("Audit: who, when, what, before → after, reason — NAMES, never ids, paged by the server", async () => {
    const calls: Call[] = [];
    mount(HIGH, calls, "?tab=audit");
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("Rosa Quintero");
    expect(rows[0]).toHaveTextContent("Changed");
    expect(rows[0]).toHaveTextContent("Ends: No end → 05/09/2027");
    expect(rows[0]).toHaveTextContent("Council extended it.");
    expect(rows[1]).toHaveTextContent("System");
    expect(rows[1]).toHaveTextContent("Created");
    expect(document.body.textContent).not.toContain("u-91f3");
    const read = calls.find((c) => c.url.includes("/audit"));
    expect(read?.url).toMatch(/page=1/);
    expect(read?.url).toMatch(/per=\d+/);
    // The pager reads the server's count (41), never the page's two rows.
    expect(document.body.textContent).toMatch(/41/);
  });

  it("an old tab address (?tab=versions) still opens Audit", async () => {
    mount(HIGH, [], "?tab=versions");
    expect(await screen.findByRole("heading", { name: "Audit" })).toBeInTheDocument();
  });

  it("auditChange names a plan link by the plan's NAME", () => {
    expect(
      auditChange(
        { at: null, actor: null, action: "tax.attached_to_plan", before: null, after: { plan: "Dockside Shops", version: 3 }, reason: null },
        t,
        REGIONAL,
      ),
    ).toBe("Dockside Shops");
  });
});

describe("CR-165 task 6 · the tax kind no longer renders the shared shell's tax branches", () => {
  it("DefinitionDetailPage mounts TaxDetailPage and imports nothing from the old tax wizard", () => {
    expect(ddpSource).toContain("<TaxDetailPage");
    expect(ddpSource).not.toContain('from "./TaxWizard"');
    expect(ddpSource).not.toContain("taxDetailTabs");
  });
});
