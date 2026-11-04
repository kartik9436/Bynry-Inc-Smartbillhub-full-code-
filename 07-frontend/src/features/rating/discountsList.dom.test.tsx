// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 2 task 5 — Plans & Rates › Discounts LIST,
//           rebuilt from images 01–04 of 05-prototype/discounts-2026-10-03.
// Defect:   DEF-RAT-9290 (D14–D17, reproduced on 2.469.0 before any fix)
// Rules:    B14 rules 21 · 31 · 33 · 37 · 42 · 43 · 44 · NFR-3 (server paging
//           and server filters) · BR-RAT-087 (the server's display string)
// ───────────────────────────────────────────────────────
/**
 * ONE CASE PER PROBLEM THE PO MARKED ON THE LIST (D14–D18), EACH WRITTEN
 * AGAINST THE SCREEN BEFORE IT WAS REBUILT AND WATCHED FAIL THERE.
 *
 * ⚠ **NO DRAWN FIGURE IS ASSERTED AS A FACT (B14 rule 37).** The drawing inks
 * SENIOR at 15% with 12 enrolled; these fixtures carry their own numbers, so a
 * case cannot pass by a screen that hard-codes the illustration.
 *
 * ⚠ **THE `$` IS THE SERVER'S (BR-RAT-087, the round-2 contract's
 * `value_display` "with `$` or `%`").** The fixture serves `$31.00`; the screen
 * prints what it is given and never adds a symbol of its own, so a server that
 * has not landed the contract shows its own string rather than a guess.
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
import type { DiscountRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { DiscountsTab } from "./DiscountsTab";
import type { DiscountListRow } from "./discountListParts";
import { RATING_TABS } from "./ratingShared";
import type { RatingTabRender } from "./ratingShared";
import discountTabSource from "./DiscountsTab.tsx?raw";

afterEach(cleanup);

const TENANT = "brazosbend";

const BASE: DiscountRow = {
  id: "d-base",
  code: "BASE",
  name: "Base",
  type: "percentage",
  value: "7.000000",
  value_display: "7%",
  currency: "USD",
  eligibility: null,
  verification: null,
  plans: 0,
  enrolled: 0,
  status: "active",
  programme_owner: null,
  funding_source: null,
  gl_account_id: null,
  applies_to: "whole_bill",
  effective_from: null,
  version_no: 1,
  version_status: "active",
  version_id: "v-base",
};

/** A fixed amount, every round-2 field served, an end date set. */
const HARBOR: DiscountListRow = {
  ...BASE,
  id: "d-harbor",
  code: "HARBOR",
  name: "Harbor credit",
  type: "fixed_amount",
  value: "31.000000",
  value_display: "$31.00",
  eligibility: [{ value: "income", label: "Household income under a limit", checked_by: "proof" }],
  verification: { value: "annual", label: "Annual recertification" },
  effective_from: "2026-03-14",
  effective_to: "2027-05-09",
  plans: 4,
  enrolled: 2,
  receiving: 19,
  status: "waiting_approval",
};

/** A percentage, open-ended. */
const LAKE: DiscountListRow = {
  ...BASE,
  id: "d-lake",
  code: "LAKE",
  name: "Lake discount",
  value: "3.500000",
  value_display: "3.5%",
  eligibility: [{ value: "autopay", label: "Autopay is on", checked_by: "system" }],
  verification: "automatic",
  effective_from: "2025-11-02",
  effective_to: null,
  plans: 2,
  enrolled: 6,
  receiving: 6,
  status: "ended",
};

/** A row from a server that predates round 2 — none of the new fields. */
const OLD_SERVER: DiscountRow = {
  ...BASE,
  id: "d-old",
  code: "OLDROW",
  name: "Old row",
  status: "draft",
};

interface Call {
  url: string;
}

function recordingClient(calls: Call[], rows: DiscountListRow[]): ApiClient {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input) => {
      const url = String(input);
      calls.push({ url });
      const narrowed = url.includes("q=zzz") ? [] : rows;
      const body = url.includes("/discounts")
        ? { count: narrowed.length, next: null, previous: null, results: narrowed }
        : { count: 0, next: null, previous: null, results: [] };
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
        <MemoryRouter initialEntries={[`/${TENANT}/plans-rates/discounts${search}`]}>
          <Routes>
            <Route
              path="/:tenant/plans-rates/discounts"
              element={
                <DiscountsTab
                  readOnly={false}
                  client={client}
                  timeZone="America/Chicago"
                  dateFormat="MM/DD/YYYY"
                  render={render2}
                />
              }
            />
            <Route
              path="/:tenant/plans-rates/discounts/:discountId"
              element={<p data-testid="opened">opened</p>}
            />
            <Route
              path="/:tenant/plans-rates/discounts/:discountId/edit"
              element={<p data-testid="edit">edit</p>}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function rowOf(code: string): HTMLElement {
  const row = screen.getByText(code).closest("tr");
  if (row === null) throw new Error(`no row for ${code}`);
  return row;
}

/** Tick Verification on in ▦ Columns (DEF-RAT-9319: off by default). */
async function showVerification(): Promise<void> {
  await userEvent.click(screen.getByLabelText("Show or hide columns"));
  await userEvent.click(screen.getByRole("checkbox", { name: /Verification/ }));
}

describe("CR-166 task 5 — the Discounts list, built from images 01–04", () => {
  it("columns in the drawn order, From and To among them (D17)", async () => {
    mount(recordingClient([], [HARBOR, LAKE]));
    await screen.findByText("HARBOR");
    const headings = screen
      .getAllByRole("columnheader")
      .map((cell) => (cell.textContent ?? "").replace(/[▲▼]/g, "").trim())
      .filter((text) => text !== "");
    expect(headings).toEqual([
      "Code",
      "Discount",
      "Type",
      "Value",
      "Eligibility",
      // DEF-RAT-9319: Verification is in ▦ Columns, off by default — twelve
      // columns cannot fit 1,120px at 1440 under the kit's header tier.
      "From",
      "To",
      "Plans",
      "Enrolled",
      "Status",
    ]);
  });

  it("DEF-RAT-9319: Verification is offered in ▦ Columns and shows when ticked", async () => {
    mount(recordingClient([], [HARBOR, LAKE]));
    await screen.findByText("HARBOR");
    expect(screen.queryByRole("columnheader", { name: /Verification/ })).toBeNull();
    await showVerification();
    expect(await screen.findByRole("columnheader", { name: /Verification/ })).toBeInTheDocument();
  });

  it("DEF-RAT-9341: no column header breaks inside a word (ja-JP プラ/ン, ステータ/ス; ko-KR 요금/제)", async () => {
    mount(recordingClient([], [HARBOR]));
    await screen.findByText("HARBOR");
    const table = screen.getByRole("table");
    // jsdom performs no layout, so the rule is asserted as the class that
    // carries it: every header cell sits under a list-level `break-keep`.
    const wrapper = table.closest("[data-discount-list]");
    expect(wrapper).not.toBeNull();
    expect(wrapper?.className).toContain("[&_thead_th]:break-keep");
  });

  it("DEF-RAT-9319: Type and Status never break inside a word (ja-JP 定率 read one character per line)", async () => {
    mount(recordingClient([], [HARBOR]));
    await screen.findByText("HARBOR");
    const row = rowOf("HARBOR");
    expect(row.querySelectorAll(".break-keep").length).toBe(2);
  });

  it("DEF-RAT-9319: an allowance's unit may wrap under its figure (2.00 / kgal); a figure itself has no space to break at", async () => {
    mount(recordingClient([], [{ ...HARBOR, id: "g", code: "GARDEN", value_display: "2.00 kgal" }]));
    await screen.findByText("GARDEN");
    const value = within(rowOf("GARDEN")).getByText("2.00 kgal");
    expect(value.className).not.toContain("whitespace-nowrap");
  });

  it("D14: no paragraph above the table", () => {
    const tab = RATING_TABS.find((one) => one.id === "discounts");
    expect(tab?.explainerKey).toBeUndefined();
    expect(i18n.exists("rating.explainer.discounts")).toBe(false);
  });

  it("D15: the value is the server's string — $ on a fixed amount, % on a percentage", async () => {
    mount(recordingClient([], [HARBOR, LAKE, { ...BASE, id: "w", code: "WAIVE", value_display: null }]));
    await screen.findByText("HARBOR");
    expect(within(rowOf("HARBOR")).getByText("$31.00")).toBeInTheDocument();
    expect(within(rowOf("LAKE")).getByText("3.5%")).toBeInTheDocument();
    // Null is a dash, never a zero.
    expect(within(rowOf("WAIVE")).queryByText(/0\.00/)).toBeNull();
  });

  it("D16: the row's one action OPENS the details page; no pencil, no edit door", async () => {
    mount(recordingClient([], [HARBOR]));
    await screen.findByText("HARBOR");
    const row = rowOf("HARBOR");
    expect(within(row).queryByRole("button", { name: /new version|edit/i })).toBeNull();
    await userEvent.click(within(row).getByRole("button", { name: "Open" }));
    expect(await screen.findByTestId("opened")).toBeInTheDocument();
    expect(discountTabSource).not.toContain("PencilIcon");
  });

  it("D17: From and To are dates; an open end reads No end; a server without them reads a dash", async () => {
    mount(recordingClient([], [HARBOR, LAKE, OLD_SERVER]));
    await screen.findByText("HARBOR");
    const harbor = rowOf("HARBOR");
    expect(within(harbor).getByText("03/14/2026")).toBeInTheDocument();
    expect(within(harbor).getByText("05/09/2027")).toBeInTheDocument();
    expect(within(rowOf("LAKE")).getByText("No end")).toBeInTheDocument();
    expect(within(rowOf("OLDROW")).getAllByText("—").length).toBeGreaterThan(0);
  });

  it("eligibility and verification read the contract's labels, never a code", async () => {
    mount(recordingClient([], [HARBOR, LAKE]));
    await screen.findByText("HARBOR");
    await showVerification(); // DEF-RAT-9319: off by default, in ▦ Columns
    const harbor = rowOf("HARBOR");
    expect(within(harbor).getByText("Household income under a limit")).toBeInTheDocument();
    expect(within(harbor).getByText("Annual recertification")).toBeInTheDocument();
    expect(harbor.textContent).not.toContain("income,");
    expect(within(rowOf("LAKE")).getByText("Automatic")).toBeInTheDocument();
  });

  it("Enrolled reads the accounts RECEIVING it when served; Plans stays its own number", async () => {
    mount(recordingClient([], [HARBOR]));
    await screen.findByText("HARBOR");
    const cells = within(rowOf("HARBOR")).getAllByRole("cell").map((c) => c.textContent);
    expect(cells).toContain("19");
    expect(cells).toContain("4");
    expect(cells).not.toContain("2");
  });

  it("the five statuses carry words, never codes", async () => {
    mount(recordingClient([], [HARBOR, LAKE, OLD_SERVER]));
    await screen.findByText("HARBOR");
    expect(within(rowOf("HARBOR")).getByText("Waiting approval")).toBeInTheDocument();
    expect(within(rowOf("LAKE")).getByText("Ended")).toBeInTheDocument();
    expect(within(rowOf("OLDROW")).getByText("Draft")).toBeInTheDocument();
    for (const status of ["draft", "waiting_approval", "active", "ended", "retired"]) {
      expect(i18n.exists(`rating.discounts.status.${status}`)).toBe(true);
    }
  });

  it("D18: + Filter offers Status and Type; the chip is removable; both go to the SERVER", async () => {
    const calls: Call[] = [];
    mount(recordingClient(calls, [HARBOR]), "?f.status=active");
    await screen.findByText("HARBOR");
    const panel = screen.getByText("+ Filter").closest("summary");
    expect(panel?.getAttribute("title")).toContain("Status");
    expect(panel?.getAttribute("title")).toContain("Type");
    expect(panel?.getAttribute("title")).not.toContain("Verification");
    expect(calls.some((call) => call.url.includes("f.status=active"))).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Remove the Status filter" }));
    await waitFor(() => expect(calls.at(-1)?.url).not.toContain("f.status"));
  });

  it("a type filter is a server param, never a filter over the page (NFR-3)", async () => {
    const calls: Call[] = [];
    mount(recordingClient(calls, [HARBOR]), "?f.type=fixed_amount");
    await screen.findByText("HARBOR");
    const list = calls.find((call) => call.url.includes("/discounts"));
    expect(list?.url).toContain("f.type=fixed_amount");
    expect(list?.url).toContain("page=1");
    expect(list?.url).toContain("per=50");
  });

  it("image 04: search placeholder and the no-match state", async () => {
    mount(recordingClient([], [HARBOR]), "?q=zzz");
    expect(await screen.findByPlaceholderText("Search code or name")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("HARBOR")).toBeNull());
    expect(screen.queryByRole("table")).toBeNull();
  });
});
