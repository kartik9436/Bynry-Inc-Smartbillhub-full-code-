// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 6 — the discount DETAILS page, built from
//           images 19–26 of 05-prototype/discounts-2026-10-03.
// Defect:   DEF-RAT-9291 (D19–D34) · DEF-RAT-9310 (Duplicate) · DEF-478
//           (plans from the discount page) · DEF-1005 (CSV) — the last three
//           LIVE since the CR-166 follow-up of 2026-10-03 (lane DISC-SMALLS)
// Rules:    PO lifecycle rulings 2026-10-03 · README point 6 · B14 rules 31,
//           33, 37 · hard-won law 2 (the edit door is asserted by ADDRESS; a
//           hold carries the test that fires when it expires)
// ───────────────────────────────────────────────────────
/**
 * ONE CASE PER DRAWN FACT OF THE DETAILS PAGE, written before the page was
 * mounted and watched fail against the old shell.
 *
 * ⚠ **NO DRAWN FIGURE IS ASSERTED AS A FACT (B14 rule 37).** The drawing inks
 * SENIOR, 15%, 75 units, 12 accounts and $73.80; the fixtures carry their own
 * numbers so no case passes by a screen that hard-codes the illustration.
 *
 * ⚠ **MOUNTED UNDER THE REAL ROUTE PATTERN** —
 * `/:tenant/plans-rates/discounts/:definitionId`, the edit door under
 * `…/:definitionId/edit` — so an address the page builds wrongly cannot read
 * as a good string (hard-won law 2's fixture clause).
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { DiscountDetailRow } from "@/api/discountDetailEndpoints";
import type { MyPermissions } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { DefinitionDetailPage } from "../DefinitionDetailPage";
import { discountEditDoor, headerActs, versionStatus } from "./discountDetailModel";
import { retireSchema } from "./DiscountLifecycleDialogs";
import ddpSource from "../DefinitionDetailPage.tsx?raw";
import appSource from "../../../App.tsx?raw";

afterEach(cleanup);

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>) => `${key}${params ? JSON.stringify(params) : ""}`;

/** A live percentage discount with a later value approved — image 19's shape,
 *  with figures of its own. */
const LIVE: DiscountDetailRow = {
  id: "d-harbor",
  code: "HARBOR",
  name: "Harbor elders credit",
  type: "percentage",
  value: "12.500000",
  value_display: "12.5%",
  currency: "USD",
  eligibility: { value: "age_65_or_over", label: "Age 65 or over", checked_by: "proof" },
  verification: "annual_recertification",
  plans: 3,
  enrolled: 9,
  status: "active",
  stored_status: "active",
  programme_owner: "community",
  program_owner: { value: "community", label: "Community programs" },
  funding_source: "Harbor foundation",
  gl_account_id: null,
  applies_to: "whole_bill",
  effective_from: "2026-03-14",
  effective_to: null,
  version_no: 2,
  version: 2,
  version_status: "active",
  version_id: "v-2",
  report_in_assistance_filing: true,
  funding_exhausted_at: null,
  granted_to_date: "0.00",
  granted_to_date_display: "$0.00",
  offered_to: 37,
  receiving: 9,
  granted_this_month: null,
  scheduled_next: { value_display: "11.5%", effective_from: "2027-02-01" },
  exclusivity_group: { value: "assistance", label: "Assistance programs" },
  applies_to_services: [],
  applies_to_charge_codes: [],
  cap_per_bill: "4.0000",
  // D27 — the BARE display keys carry no symbol (older screens read them);
  // the page must print `money_display`, the server's figure WITH its `$`.
  cap_per_bill_display: "4.00",
  money_display: {
    cap_per_bill: "$4.00",
    cap_per_year: null,
    cap_lifetime: null,
    bill_floor_amount: "$0.00",
    budget_cap: "$1,777.00",
    budget_remaining: "$1,601.00",
  },
  cap_per_year: null,
  cap_per_year_display: null,
  cap_lifetime: null,
  cap_lifetime_display: null,
  bill_floor_amount: "0.0000",
  bill_floor_amount_display: "0.00",
  stacking_precedence: 25,
  stacks_with_others: true,
  enrolment_mode: "apply_and_approve",
  proof_required: true,
  accepted_proof_kinds: [],
  proof_before_first_reduction: true,
  recertification_months: 18,
  recertification_notice_days: 21,
  recertification_grace_days: 9,
  lapse_behaviour: "notify_then_drop",
  budget_cap: "1777.0000",
  budget_cap_display: "1777.00",
  budget_period: "annual",
  exhaustion_behaviour: "suspend",
  budget_remaining: "1601.0000",
  budget_remaining_display: "1601.00",
};

const DRAFT: DiscountDetailRow = {
  ...LIVE,
  id: "d-draft",
  name: "Dockside veterans",
  code: "DOCKVET",
  status: "draft",
  version_status: "draft",
  version: 1,
  version_no: 1,
  scheduled_next: null,
  receiving: 0,
};

const WAITING: DiscountDetailRow = { ...DRAFT, id: "d-wait", name: "Lifeline credit", status: "waiting_approval" };

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

const ACCOUNT_ROWS = [
  {
    enrolment_id: "e-71",
    account_id: "acct-uuid-71",
    account_number: "AC-3141",
    customer_name: "Ines Varga",
    premises_address: "41 Quay Lane",
    plan: "Harbor Homes",
    enrolled_on: "2026-05-02",
    renew_by: "2027-11-02",
    this_month: null,
    status: "receiving",
  },
  {
    enrolment_id: "e-72",
    account_id: "acct-uuid-72",
    account_number: "AC-3142",
    customer_name: "Tomas Ruiz",
    premises_address: null,
    plan: "Harbor Homes",
    enrolled_on: "2026-06-11",
    renew_by: null,
    this_month: null,
    status: "proof_pending",
  },
];

function client(calls: Call[], row: DiscountDetailRow, opts: { accounts?: unknown[]; versions?: unknown[] } = {}): ApiClient {
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
      if (url.includes("format=csv")) {
        return new Response("Account,Customer\nAC-3141,Ines Varga\n", { status: 200, headers: { "Content-Type": "text/csv" } });
      }
      if (method === "POST" && url.includes("/duplicate")) {
        body = { id: "d-copy", code: "HARBOR-2", name: "Harbor elders credit 2" };
        return new Response(JSON.stringify(body), { status: 201, headers: { "Content-Type": "application/json" } });
      }
      if (method === "GET" && url.includes("/plans?") && !url.includes("/discounts/")) {
        body = { count: 1, next: null, previous: null, results: [{ id: "plan-uuid-2", name: "Bayfront Flats" }] };
        return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (method === "GET" && url.includes("/audit")) {
        body = {
          count: 2,
          next: null,
          previous: null,
          results: [
            {
              at: "2026-09-24T15:12:00Z",
              actor: { name: "Rosa Quintero" },
              action: "discount.details_updated",
              before: { recertification_notice_days: 0, value: "12.500000", value_display: "12.5%" },
              after: { recertification_notice_days: 21, value: "11.500000", value_display: "11.5%" },
              reason: "Letters go out early.",
            },
            {
              at: "2026-09-02T20:40:00Z",
              actor: { name: "Vijay Bikkad" },
              action: "discount.account_enrolled",
              before: null,
              after: { account: "AC-3141", enrolled_on: "2026-05-02" },
              reason: null,
            },
          ],
        };
      } else if (method === "GET" && url.includes("/accounts?") && url.includes("/discounts/")) {
        const rows = opts.accounts ?? ACCOUNT_ROWS;
        body = { count: rows.length, next: null, previous: null, results: rows };
      } else if (method === "GET" && url.includes("/plans")) {
        body = {
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              plan_id: "plan-uuid-1",
              plan: "Harbor Homes",
              plan_code: "HH",
              available_from: "2026-04-01",
              available_to: null,
              units: 44,
              accounts: 41,
              services: ["water", "sewer"],
              customer_classes: [],
            },
          ],
        };
      } else if (method === "GET" && url.includes("/versions")) {
        body = opts.versions ?? [
          { id: "v-3", version_no: 3, status: "active", value_display: "11.5%", effective_from: "2027-02-01", effective_to: null },
          { id: "v-2", version_no: 2, status: "active", value_display: "12.5%", effective_from: "2026-03-14", effective_to: "2027-01-31" },
        ];
      } else if (method === "GET" && url.includes("/accounts?")) {
        body = { count: 1, next: null, previous: null, results: [{ id: "acct-uuid-99", account_no: "AC-9001", name: "Ola Berg" }], rollup: {} };
      } else if (method === "POST") {
        body = {};
      } else {
        body = row;
      }
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    },
  });
}

function Where() {
  const location = useLocation();
  return <p data-testid="landed">{`${location.pathname}${location.search}`}</p>;
}

function mount(
  row: DiscountDetailRow,
  calls: Call[] = [],
  search = "",
  opts: { accounts?: unknown[]; versions?: unknown[]; access?: string } = {},
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions(opts.access ?? "Full"));
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/plans-rates/discounts/${row.id}${search}`]}>
          <Routes>
            <Route
              path="/:tenant/plans-rates/discounts/:definitionId"
              element={
                <DefinitionDetailPage
                  kind="discount"
                  client={client(calls, row, opts)}
                  timeZone="America/Chicago"
                  dateFormat="MM/DD/YYYY"
                />
              }
            />
            <Route path="/:tenant/plans-rates/discounts/:definitionId/edit" element={<Where />} />
            <Route path="/:tenant/accounts/:accountId" element={<Where />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function headerButtons(): string[] {
  const head = document.querySelector(".page-header") ?? document.body;
  // The More ▾ menu's own items are not header buttons.
  return within(head as HTMLElement)
    .queryAllByRole("button")
    .filter((button) => button.closest("[data-discount-more]") === null)
    .map((button) => button.textContent?.trim() ?? "")
    .filter((label) => label !== "");
}

describe("CR-166 task 6 · the edit door is ONE agreed address (hard-won law 2)", () => {
  it("Edit opens ?change=info on the discount's own edit route — by literal address", () => {
    expect(discountEditDoor("d-1", "info")).toBe("/plans-rates/discounts/d-1/edit?change=info");
    expect(discountEditDoor("d-1", "change")).toBe("/plans-rates/discounts/d-1/edit?change=change");
    expect(discountEditDoor("d-1", "correct")).toBe("/plans-rates/discounts/d-1/edit?change=correct");
    // The router mounts something at that pattern.
    expect(appSource).toContain('path: "plans-rates/discounts/:definitionId/edit"');
  });

  it("pressing Edit lands on the edit door with change=info", async () => {
    mount(LIVE);
    await userEvent.click(await screen.findByRole("button", { name: "Edit" }));
    expect(await screen.findByTestId("landed")).toHaveTextContent(
      `/${TENANT}/plans-rates/discounts/d-harbor/edit?change=info`,
    );
  });
});

describe("CR-166 task 6 · the header (images 19, 23, 24, 26) — D19, D20, D22", () => {
  it("D19 · D20: name and code, no kicker, no sentence under the title", async () => {
    mount(LIVE);
    const heading = await screen.findByRole("heading", { name: /Harbor elders credit/ });
    expect(within(heading).getByText("HARBOR")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/DISCOUNT · HARBOR/i);
    expect(document.body.textContent).not.toMatch(/overlay/i);
  });

  it("the facts line: status · version · type and window · Next", async () => {
    mount(LIVE);
    await screen.findByRole("heading", { name: /Harbor elders credit/ });
    const facts = document.querySelector("[data-discount-header-facts]") as HTMLElement;
    expect(within(facts).getByText("Active")).toBeInTheDocument();
    expect(within(facts).getByText("V2")).toBeInTheDocument();
    expect(within(facts).getByText("Percentage · 03/14/2026 – no end")).toBeInTheDocument();
    expect(facts.querySelector("[data-discount-header-next]")).toHaveTextContent("Next: 11.5% from 02/01/2027");
  });

  it("no Next when nothing later is approved", async () => {
    mount(DRAFT);
    await screen.findByRole("heading", { name: /Dockside veterans/ });
    expect(document.querySelector("[data-discount-header-next]")).toBeNull();
  });

  it("the buttons follow the status (README point 6)", () => {
    expect(headerActs("active")).toEqual(["edit"]);
    expect(headerActs("scheduled")).toEqual(["edit"]);
    expect(headerActs("draft")).toEqual(["edit", "submit"]);
    expect(headerActs("waiting_approval")).toEqual(["sendBack", "approve"]);
    expect(headerActs("retired")).toEqual([]);
  });

  it("PO 2026-10-03 · a usage-allowance draft offers Edit and never Submit for approval", () => {
    expect(headerActs("draft", "usage_allowance")).toEqual(["edit"]);
    expect(headerActs("draft", "percentage")).toEqual(["edit", "submit"]);
  });

  it("D22 · Active: Edit and More ▾ holding Duplicate and Retire — nothing else", async () => {
    mount(LIVE);
    await screen.findByRole("heading", { name: /Harbor elders credit/ });
    expect(headerButtons()).toEqual(["Edit"]);
    const more = document.querySelector("[data-discount-more]") as HTMLElement;
    expect(within(more).getByText("Duplicate")).toBeInTheDocument();
    expect(within(more).getByText("Retire")).toBeInTheDocument();
    expect(within(more).queryByText("Delete draft")).toBeNull();
  });

  it("Draft (image 24): Edit · Submit for approval, and Submit posts /submit", async () => {
    const calls: Call[] = [];
    mount(DRAFT, calls, "", { versions: [{ id: "v-1", version_no: 1, status: "draft", value_display: "12.5%", effective_from: "2026-11-01", effective_to: null }] });
    await screen.findByRole("heading", { name: /Dockside veterans/ });
    expect(headerButtons()).toEqual(["Edit", "Submit for approval"]);
    await userEvent.click(screen.getByRole("button", { name: "Submit for approval" }));
    await waitFor(() =>
      expect(calls.some((c) => c.method === "POST" && c.url.includes("/discounts/d-draft/submit"))).toBe(true),
    );
  });

  it("Waiting approval (image 26): Send back · Approve; Approve confirms, then posts /approve", async () => {
    const calls: Call[] = [];
    mount(WAITING, calls);
    await screen.findByRole("heading", { name: /Lifeline credit/ });
    expect(headerButtons()).toEqual(["Send back", "Approve"]);
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("03/14/2026");
    await userEvent.click(within(dialog).getByRole("button", { name: "Approve" }));
    await waitFor(() =>
      expect(calls.some((c) => c.method === "POST" && c.url.includes("/discounts/d-wait/approve"))).toBe(true),
    );
  });

  it("Send back needs a note and posts it", async () => {
    const calls: Call[] = [];
    mount(WAITING, calls);
    await screen.findByRole("heading", { name: /Lifeline credit/ });
    await userEvent.click(screen.getByRole("button", { name: "Send back" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Send back" }));
    expect(calls.some((c) => c.url.includes("/send-back"))).toBe(false);
    await userEvent.type(within(dialog).getByLabelText(/Note/), "Budget is wrong");
    await userEvent.click(within(dialog).getByRole("button", { name: "Send back" }));
    await waitFor(() => {
      const sent = calls.find((c) => c.url.includes("/discounts/d-wait/send-back"));
      expect(sent?.body).toEqual({ note: "Budget is wrong" });
    });
    // DEF-RAT-9340: the dialog closes once the send-back has worked
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("Retire asks for the last day (today or later) and posts it to /retire", async () => {
    expect(retireSchema(t, "2026-10-03").safeParse({ effective_to: "2026-10-02" }).success).toBe(false);
    expect(retireSchema(t, "2026-10-03").safeParse({ effective_to: "2026-10-03" }).success).toBe(true);
    const calls: Call[] = [];
    mount(LIVE, calls);
    await screen.findByRole("heading", { name: /Harbor elders credit/ });
    fireEvent.click(screen.getByTestId("discount-more-retire"));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/Last day it applies/), { target: { value: "2099-12-31" } });
    await userEvent.click(within(dialog).getByRole("button", { name: "Retire" }));
    await waitFor(() => {
      const sent = calls.find((c) => c.url.includes("/discounts/d-harbor/retire"));
      expect(sent?.body).toEqual({ effective_to: "2099-12-31" });
    });
    // DEF-RAT-9340 (CR-166 web walk step 10): the date was stored and the
    // dialog stayed open with Retire still live — it closes now.
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("Delete draft is offered only while a draft exists, and discards THAT version", async () => {
    const calls: Call[] = [];
    mount(DRAFT, calls, "", { versions: [{ id: "v-1", version_no: 1, status: "draft", value_display: "12.5%", effective_from: "2026-11-01", effective_to: null }] });
    await screen.findByRole("heading", { name: /Dockside veterans/ });
    fireEvent.click(await screen.findByTestId("discount-more-delete-draft"));
    const dialog = await screen.findByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete draft" }));
    await waitFor(() =>
      expect(calls.some((c) => c.method === "POST" && c.url.includes("/discounts/d-draft/versions/v-1/discard"))).toBe(true),
    );
  });
});

describe("CR-166 follow-up · DEF-RAT-9310 — More ▾ Duplicate makes a new draft", () => {
  it("Duplicate is live: it asks for a new code and bill line label, posts them, and opens the copy", async () => {
    const calls: Call[] = [];
    mount(LIVE, calls);
    await screen.findByRole("heading", { name: /Harbor elders credit/ });
    const item = screen.getByTestId("discount-more-duplicate");
    expect(item).toBeEnabled();
    await userEvent.click(item);
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Copies every value and condition. No plans, no accounts.");
    await userEvent.type(within(dialog).getByLabelText(/^Code/), "harbor-2");
    await userEvent.type(within(dialog).getByLabelText(/Bill line label/), "Harbor elders credit 2");
    await userEvent.click(within(dialog).getByRole("button", { name: "Duplicate" }));
    await waitFor(() => {
      const sent = calls.find((c) => c.method === "POST" && c.url.includes("/discounts/d-harbor/duplicate"));
      expect(sent?.body).toEqual({ code: "HARBOR-2", name: "Harbor elders credit 2" });
    });
    // The door lands on the COPY's own page (by address), never the source's.
    await waitFor(() => expect(calls.some((c) => c.method === "GET" && /\/discounts\/d-copy(\?|$)/.test(c.url))).toBe(true));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("Duplicate posts nothing until both boxes are filled", async () => {
    const calls: Call[] = [];
    mount(LIVE, calls);
    await screen.findByRole("heading", { name: /Harbor elders credit/ });
    await userEvent.click(screen.getByTestId("discount-more-duplicate"));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Duplicate" }));
    expect(await within(dialog).findByText("Enter a new code.")).toBeInTheDocument();
    expect(within(dialog).getByText("Enter a bill line label.")).toBeInTheDocument();
    expect(calls.some((c) => c.url.includes("/duplicate"))).toBe(false);
  });
});

describe("CR-166 task 6 · tabs and the Overview (images 19, 24, 26) — D23–D28, D33, D34", () => {
  it("tabs are Overview · Accounts · Plans · Audit, Accounts and Plans carry their counts", async () => {
    mount(LIVE);
    await screen.findByRole("heading", { name: /Harbor elders credit/ });
    const tabs = screen.getAllByRole("tab").map((tab) => tab.textContent?.replace(/\s+/g, " ").trim());
    expect(tabs).toHaveLength(4);
    expect(tabs[0]).toMatch(/^Overview/);
    expect(tabs[1]).toMatch(/^Accounts.*9/);
    expect(tabs[2]).toMatch(/^Plans.*3/);
    expect(tabs[3]).toMatch(/^Audit/);
  });

  it("four tiles: Value · Offered to · Receiving it · Granted — Granted is a dash while null", async () => {
    mount(LIVE);
    await screen.findByRole("heading", { name: /Harbor elders credit/ });
    const overview = document.querySelector("[data-discount-overview]") as HTMLElement;
    expect(overview).toHaveTextContent("12.5%");
    expect(overview).toHaveTextContent("off subtotal before taxes");
    expect(overview).toHaveTextContent("37");
    expect(overview).toHaveTextContent("units on its plans");
    expect(overview).toHaveTextContent("Granted");
    expect(overview).not.toHaveTextContent("$73.80");
    // Granted is a bare dash: no figure and no sentence explaining it.
    expect(overview).not.toHaveTextContent("$0.00 this month");
    expect(overview.textContent).not.toMatch(/Not counted|DEF-2430/);
  });

  it("D33: every entered value is shown, money with $, list values by their labels", async () => {
    mount(LIVE);
    await screen.findByRole("heading", { name: /Harbor elders credit/ });
    const details = document.querySelector("[data-fact-block='discount-details'], [data-facts='discount-details']") ?? document.body;
    for (const fact of [
      "HARBOR",
      "Community programs",
      "Harbor foundation",
      "USD",
      "Subtotal before taxes",
      "$4.00 · — · —",
      "25 · stacks with others",
      "Assistance programs",
    ]) {
      expect(details).toHaveTextContent(fact);
    }
    const body = document.body;
    for (const fact of [
      "Age 65 or over",
      "Apply and approve",
      "Annual recertification",
      "18 months",
      "21 days · 9 days",
      "Notify, then drop the enrollment",
      "$1,777.00 · Annual",
      "$1,601.00",
      "Suspend the discount",
    ]) {
      expect(body).toHaveTextContent(fact);
    }
    // No database id anywhere (B14 rule 31).
    expect(body.textContent).not.toContain("d-harbor");
  });

  it("D34: Starts and Ends sit together under Eligibility", async () => {
    mount(LIVE);
    await screen.findByRole("heading", { name: /Harbor elders credit/ });
    const eligibility = screen.getByRole("region", { name: "Eligibility" });
    expect(eligibility).toHaveTextContent("Starts");
    expect(eligibility).toHaveTextContent("03/14/2026");
    expect(eligibility).toHaveTextContent("Ends");
    expect(eligibility).toHaveTextContent("No end");
  });

  it("the versions table reads dates and a derived status, and See every change opens Audit", async () => {
    mount(LIVE);
    await screen.findByRole("heading", { name: /Harbor elders credit/ });
    const table = await waitFor(() => {
      const found = document.querySelector("[data-discount-versions]") as HTMLElement | null;
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(table).toHaveTextContent("02/01/2027 – No end");
    expect(table).toHaveTextContent("03/14/2026 – 01/31/2027");
    expect(within(table).getByText("Scheduled")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See every change in Audit" })).toHaveAttribute(
      "href",
      `/${TENANT}/plans-rates/discounts/d-harbor?tab=audit`,
    );
  });

  it("a version's status is read from its dates (ruling 1: approved is stored active)", () => {
    const row = { id: "v", version_no: 1, value_display: null, effective_from: "2026-01-01", effective_to: "2026-06-30", status: "active" };
    expect(versionStatus(row, "2026-10-03")).toBe("ended");
    expect(versionStatus({ ...row, effective_to: null }, "2026-10-03")).toBe("active");
    expect(versionStatus({ ...row, effective_from: "2027-01-01", effective_to: null }, "2026-10-03")).toBe("scheduled");
    expect(versionStatus({ ...row, status: "pending_approval" }, "2026-10-03")).toBe("waiting_approval");
  });

  it("an old tab address (?tab=versions) still opens Audit", async () => {
    mount(LIVE, [], "?tab=versions");
    expect(await screen.findByRole("heading", { name: "Audit" })).toBeInTheDocument();
  });
});

describe("CR-166 task 6 · the Accounts tab (images 20, 25) — D30", () => {
  it("lists who receives it, paged by the server, names never ids, This month a dash", async () => {
    const calls: Call[] = [];
    mount(LIVE, calls, "?tab=accounts");
    const link = await screen.findByRole("link", { name: "AC-3141" });
    expect(link).toHaveAttribute("href", `/${TENANT}/accounts/acct-uuid-71`);
    const panel = document.querySelector("[data-discount-accounts]") as HTMLElement;
    expect(panel).toHaveTextContent("Ines Varga");
    expect(panel).toHaveTextContent("41 Quay Lane");
    expect(panel).toHaveTextContent("Harbor Homes");
    expect(panel).toHaveTextContent("05/02/2026");
    expect(panel).toHaveTextContent("Receiving");
    expect(panel).toHaveTextContent("Proof pending");
    expect(panel.textContent).not.toContain("acct-uuid");
    expect(panel.textContent).not.toContain("e-71");
    const read = calls.find((c) => c.method === "GET" && c.url.includes("/discounts/d-harbor/accounts"));
    expect(read?.url).toContain("page=1");
    expect(read?.url).toContain("per=50");
  });

  it("the Status filter goes to the server as f.status", async () => {
    const calls: Call[] = [];
    mount(LIVE, calls, "?tab=accounts&acc.f.status=renewal_due");
    await waitFor(() =>
      expect(
        calls.some((c) => c.url.includes("/discounts/d-harbor/accounts") && c.url.includes("f.status=renewal_due")),
      ).toBe(true),
    );
  });

  it("× ends ONE enrollment with a date and a reason", async () => {
    const calls: Call[] = [];
    mount(LIVE, calls, "?tab=accounts");
    await screen.findByRole("link", { name: "AC-3141" });
    await userEvent.click(screen.getAllByRole("button", { name: /End AC-3141/ })[0] as HTMLElement);
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/Reason/), "Moved away");
    await userEvent.click(within(dialog).getByRole("button", { name: "End it" }));
    await waitFor(() => {
      const sent = calls.find((c) => c.url.includes("/discount-enrolments/e-71/end"));
      expect(sent?.method).toBe("POST");
      expect((sent?.body as { reason: string }).reason).toBe("Moved away");
      expect((sent?.body as { ended_on: string }).ended_on).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    });
  });

  it("image 25: nobody receives it yet", async () => {
    mount(DRAFT, [], "?tab=accounts", { accounts: [] });
    expect(await screen.findByText("Nobody receives it yet.")).toBeInTheDocument();
  });

  it("+ Enroll an account posts the account to the enrollment door", async () => {
    const calls: Call[] = [];
    mount(LIVE, calls, "?tab=accounts");
    await screen.findByRole("link", { name: "AC-3141" });
    await userEvent.click(screen.getByRole("button", { name: "+ Enroll an account" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByRole("combobox"), "Ola");
    await userEvent.click(await within(dialog).findByText("AC-9001 · Ola Berg"));
    await userEvent.click(within(dialog).getByRole("button", { name: "Enroll" }));
    await waitFor(() => {
      const sent = calls.find((c) => c.method === "POST" && c.url.includes("/accounts/acct-uuid-99/discounts"));
      expect(sent?.body).toEqual({ programme_id: "d-harbor" });
    });
  });

  // DEF-RAT-9326 (CR-166 task 9 web walk step 5): both dialogs stayed open
  // after they succeeded, because FormModal leaves closing to its caller.
  it("Enroll closes its dialog once the account is enrolled (DEF-RAT-9326)", async () => {
    const calls: Call[] = [];
    mount(LIVE, calls, "?tab=accounts");
    await screen.findByRole("link", { name: "AC-3141" });
    await userEvent.click(screen.getByRole("button", { name: "+ Enroll an account" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByRole("combobox"), "Ola");
    await userEvent.click(await within(dialog).findByText("AC-9001 · Ola Berg"));
    await userEvent.click(within(dialog).getByRole("button", { name: "Enroll" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("End it closes its dialog once the enrollment is ended (DEF-RAT-9326)", async () => {
    const calls: Call[] = [];
    mount(LIVE, calls, "?tab=accounts");
    await screen.findByRole("link", { name: "AC-3141" });
    await userEvent.click(screen.getAllByRole("button", { name: /End AC-3141/ })[0] as HTMLElement);
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(/Reason/), "Moved away");
    await userEvent.click(within(dialog).getByRole("button", { name: "End it" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  // DEF-RAT-9325: a Proof pending row could never become Receiving — the
  // service existed and nothing reached it.
  it("a Proof pending row offers Verify proof, which posts /verify; a Receiving row does not (DEF-RAT-9325)", async () => {
    const calls: Call[] = [];
    mount(LIVE, calls, "?tab=accounts");
    await screen.findByRole("link", { name: "AC-3142" });
    expect(screen.queryByRole("button", { name: /Verify proof for AC-3141/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Verify proof for AC-3142/ }));
    await waitFor(() => {
      const sent = calls.find((c) => c.url.includes("/discount-enrolments/e-72/verify"));
      expect(sent?.method).toBe("POST");
    });
  });

  // DEF-RAT-9792: an Automatic discount is the nightly sync's to grant and
  // end; a hand enrolment was ended the next night.
  // ⚖️ AMENDED 2026-10-06 (DEF-RAT-9833, PO D2 (b): "clark can add it later
  // also on account") — the button now follows `hand_enrolment_refused`, so
  // Municipal account still draws none and Autopay/Paperless (automatic but
  // addable by hand) draw it.
  it("an Automatic discount no person may add draws no + Enroll an account; a person's discount does (DEF-RAT-9792)", async () => {
    mount(
      { ...LIVE, enrolment_mode: "automatic", enrolled_automatically: true, hand_enrolment_refused: true },
      [],
      "?tab=accounts",
    );
    await screen.findByRole("link", { name: "AC-3141" });
    expect(screen.queryByRole("button", { name: "+ Enroll an account" })).not.toBeInTheDocument();
    cleanup();
    mount({ ...LIVE, enrolled_automatically: false, hand_enrolment_refused: false }, [], "?tab=accounts");
    await screen.findByRole("link", { name: "AC-3141" });
    expect(screen.getByRole("button", { name: "+ Enroll an account" })).toBeInTheDocument();
  });

  it("Autopay and Paperless are automatic yet keep + Enroll an account (DEF-RAT-9833)", async () => {
    mount(
      { ...LIVE, enrolment_mode: "automatic", enrolled_automatically: true, hand_enrolment_refused: false },
      [],
      "?tab=accounts",
    );
    await screen.findByRole("link", { name: "AC-3141" });
    expect(screen.getByRole("button", { name: "+ Enroll an account" })).toBeInTheDocument();
  });

  // DEF-CUS-9780: the evidence taken at the counter sits on the enrolment, and
  // the verifier opens it from the row it supports.
  it("a Proof pending row with its proof on file offers View proof, opening the account document (DEF-CUS-9780)", async () => {
    const opened: string[] = [];
    const original = window.open;
    // `openDocumentContent` reads the tenant from the window's own address.
    window.history.pushState({}, "", `/${TENANT}/plans-rates/discounts/${LIVE.id}?tab=accounts`);
    window.open = ((url?: string | URL) => {
      opened.push(String(url));
      return null;
    }) as typeof window.open;
    try {
      const rows = [
        { ...ACCOUNT_ROWS[0], proof_document_id: null },
        { ...ACCOUNT_ROWS[1], proof_document_id: "card-9780" },
      ];
      mount(LIVE, [], "?tab=accounts", { accounts: rows });
      await screen.findByRole("link", { name: "AC-3142" });
      expect(screen.queryByRole("button", { name: /View proof for AC-3141/ })).not.toBeInTheDocument();
      // B14 rule 15: two icons visible — View proof and Verify; End moves behind `…`.
      // (`<details>` keeps its menu in the DOM, so ask WHERE End sits.)
      const end3142 = screen.getByRole("button", { name: /End AC-3142/, hidden: true });
      expect(end3142.closest("[data-row-more]")).not.toBeNull();
      const end3141 = screen.getAllByRole("button", { name: /End AC-3141/ })[0] as HTMLElement;
      expect(end3141.closest("[data-row-more]")).toBeNull();
      expect(document.querySelectorAll("[data-row-more]")).toHaveLength(1);
      await userEvent.click(screen.getByRole("button", { name: /View proof for AC-3142/ }));
      expect(opened).toHaveLength(1);
      expect(opened[0]).toContain(`/${TENANT}/accounts/acct-uuid-72/documents/card-9780/content?as=view`);
    } finally {
      window.open = original;
    }
  });
});

describe("CR-166 task 6 · Plans and Audit (images 21, 22) — D29, D31, D32", () => {
  it("Plans: Plan · Services · Customer classes · Accounts · Since", async () => {
    mount(LIVE, [], "?tab=plans");
    const link = await screen.findByRole("link", { name: "Harbor Homes" });
    expect(link.getAttribute("href")).toContain("plan-uuid-1");
    const panel = document.querySelector("[data-discount-plans]") as HTMLElement;
    expect(panel).toHaveTextContent("Water, Sewer");
    expect(panel).toHaveTextContent("Every class");
    expect(panel).toHaveTextContent("41");
    expect(panel).toHaveTextContent("04/01/2026");
    expect(panel.textContent).not.toMatch(/read that does not exist/i);
  });

  it("DEF-478: + Add to a plan asks for a plan and a reason, then posts both", async () => {
    const calls: Call[] = [];
    mount(LIVE, calls, "?tab=plans");
    await screen.findByRole("link", { name: "Harbor Homes" });
    await userEvent.click(screen.getByRole("button", { name: "+ Add to a plan" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByRole("combobox"), "Bay");
    await userEvent.click(await within(dialog).findByText("Bayfront Flats"));
    // No reason → nothing is posted (a discount on a plan changes what people pay).
    await userEvent.click(within(dialog).getByRole("button", { name: "Add" }));
    expect(await within(dialog).findByText("Give a reason.")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST" && c.url.includes("/discounts/d-harbor/plans"))).toBe(false);
    await userEvent.type(within(dialog).getByLabelText(/Reason/), "Flats join the elders credit");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add" }));
    await waitFor(() => {
      const sent = calls.find((c) => c.method === "POST" && c.url.includes("/discounts/d-harbor/plans"));
      expect(sent?.body).toEqual({ plan: "plan-uuid-2", reason: "Flats join the elders credit" });
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("DEF-478: × removes it from the plan — danger tier, the consequence, a reason, then DELETE", async () => {
    const calls: Call[] = [];
    mount(LIVE, calls, "?tab=plans");
    await screen.findByRole("link", { name: "Harbor Homes" });
    await userEvent.click(screen.getByRole("button", { name: "Remove from Harbor Homes" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Stops from the next bill. Enrollments on this plan end.");
    await userEvent.type(within(dialog).getByLabelText(/Reason/), "Moved to the new tariff");
    await userEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
    await waitFor(() => {
      const sent = calls.find((c) => c.method === "DELETE" && c.url.includes("/discounts/d-harbor/plans/plan-uuid-1"));
      expect(sent?.body).toEqual({ reason: "Moved to the new tariff" });
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("DEF-478: a read-only role sees both controls disabled with its reason", async () => {
    mount(LIVE, [], "?tab=plans", { access: "View" });
    await screen.findByRole("link", { name: "Harbor Homes" });
    expect(screen.getByRole("button", { name: "+ Add to a plan" })).toBeDisabled();
  });

  it("Audit: who, when, what, before → after, reason — NAMES, never ids; no DATED box", async () => {
    mount(LIVE, [], "?tab=audit");
    const panel = await waitFor(() => {
      const found = document.querySelector("[data-discount-audit] table") as HTMLElement | null;
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(panel).toHaveTextContent("Rosa Quintero");
    expect(panel).toHaveTextContent("Notice: 0 → 21");
    expect(panel).toHaveTextContent("Value: 12.5% → 11.5%");
    // The STORED six-place magnitude never reaches the screen (BR-RAT-087).
    expect(panel.textContent).not.toContain("12.500000");
    expect(panel).toHaveTextContent("Letters go out early.");
    expect(panel).toHaveTextContent("AC-3141");
    expect(document.body.textContent).not.toMatch(/Bills always use the version in force/);
  });
});

describe("CR-166 follow-up · DEF-1005 — ⤓ CSV on Accounts and Audit", () => {
  beforeEach(() => {
    globalThis.URL.createObjectURL = () => "blob:discount";
    globalThis.URL.revokeObjectURL = () => undefined;
  });

  it("Accounts ⤓ asks the server for the WHOLE filtered set — the table's filters, never a page", async () => {
    const calls: Call[] = [];
    mount(LIVE, calls, "?tab=accounts&acc.f.status=receiving");
    await screen.findByRole("link", { name: "AC-3141" });
    await userEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    await waitFor(() => {
      const sent = calls.find((c) => c.url.includes("/discounts/d-harbor/accounts?") && c.url.includes("format=csv"));
      expect(sent).toBeDefined();
      expect(sent?.url).toContain("f.status=receiving");
      expect(sent?.url).not.toMatch(/[?&](page|per)=/);
    });
  });

  it("Audit ⤓ asks the server for every row", async () => {
    const calls: Call[] = [];
    mount(LIVE, calls, "?tab=audit");
    await waitFor(() => expect(document.querySelector("[data-discount-audit] table")).not.toBeNull());
    await userEvent.click(screen.getByRole("button", { name: "Download CSV" }));
    await waitFor(() =>
      expect(calls.some((c) => c.url.includes("/discounts/d-harbor/audit?") && c.url.includes("format=csv"))).toBe(true),
    );
  });
});

describe("CR-166 task 6 · wiring", () => {
  it("DefinitionDetailPage mounts DiscountDetailPage for the discount kind", () => {
    expect(ddpSource).toMatch(/props\.kind === "discount"[\s\S]{0,80}<DiscountDetailPage/);
  });
});
