// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 2 task 5 — Plans & Rates › Taxes & fees LIST,
//           rebuilt from images 01–03 of 05-prototype/taxes-fees-2026-10-03.
// Defect:   DEF-RAT-9274 (P21–P28, reproduced on 2.467.27 before any fix)
// Rules:    B14 rules 21 · 31 · 33 · 37 · 42 · 43 · 44 · NFR-3 (server paging)
// ───────────────────────────────────────────────────────
/**
 * ONE CASE PER PROBLEM THE PO MARKED ON THE LIST (P21–P28), EACH WRITTEN
 * AGAINST THE SCREEN BEFORE IT WAS REBUILT AND WATCHED FAIL THERE.
 *
 * ⚠ **NO DRAWN FIGURE IS ASSERTED AS A FACT (B14 rule 37).** The drawing inks
 * `47 of 84`, `150%`, `V3` and `2200-01`; these fixtures carry their own
 * numbers, chosen to look nothing like the drawing's, so a case cannot pass by
 * a screen that hard-codes the illustration.
 *
 * ⚠ **THE BANNER'S COUNT IS THE SERVER'S, NEVER THE PAGE'S.** The drawing's
 * banner reads the same number in image 01 (All), 02 (Active) and 03 (a search
 * that matches nothing), so it is a fact about the tenant's taxes, not about
 * the rows on screen. A page is at most 50 rows of a list that may hold many
 * more (NFR-3), so counting the page would be a confident wrong number on
 * page two. Case P24(b) is the one that refuses that.
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
import type { TaxRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { TaxesFeesTab } from "./TaxesFeesTab";
import { RATING_TABS } from "./ratingShared";
import type { RatingTabRender } from "./ratingShared";
import { taxRowDefaults } from "./taxRowFixture";
import taxTabSource from "./TaxesFeesTab.tsx?raw";

afterEach(cleanup);

const TENANT = "brazosbend";

/** A percentage tax well over twenty, with every round-2 field served. */
const HIGH: TaxRow & Record<string, unknown> = {
  ...taxRowDefaults(),
  id: "tax-high",
  name: "Harbor Levy",
  jurisdiction: {
    id: "j-1",
    name: "Harbor Levy",
    authority: "Port of Harbor",
    level: "city",
    reference_no: null,
  },
  kind: "percent",
  rate: "0.375000",
  rate_display: "37.50%",
  applies_to_services: ["electric", "water"],
  applies_to_customer_classes: ["residential"],
  effective_from: "2026-03-14",
  effective_to: "2027-05-09",
  gl_account_code: "2399-07",
  gl_account_name: "Levy payable",
  status: "active",
  version: 4,
  premises_reached: 13,
  premises_total: 29,
};

/** A small percentage tax, open-ended, every service, every class. */
const LOW: TaxRow & Record<string, unknown> = {
  ...taxRowDefaults(),
  id: "tax-low",
  name: "Lakeside County",
  jurisdiction: {
    id: "j-2",
    name: "Lakeside County",
    authority: "Lakeside County",
    level: "county",
    reference_no: null,
  },
  kind: "percent",
  rate: "0.031500",
  rate_display: "3.15%",
  effective_from: "2025-11-02",
  effective_to: null,
  gl_account_code: "2399-08",
  gl_account_name: "County payable",
  status: "active",
  version: 1,
  premises_reached: 29,
  premises_total: 29,
};

/** A row from a server that predates round 2 — none of the new fields. */
const OLD_SERVER: TaxRow = {
  ...taxRowDefaults(),
  id: "tax-old",
  name: "Old Fee",
  jurisdiction: null,
  kind: "per_unit",
  rate: null,
  rate_display: null,
  per_unit_amount: "0.250000",
  per_unit_uom: "kgal",
  status: "draft",
};

interface Call {
  url: string;
}

function recordingClient(
  calls: Call[],
  rows: TaxRow[],
  extra: Record<string, unknown> = {},
): ApiClient {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input) => {
      const url = String(input);
      calls.push({ url });
      const body = url.includes("/taxes")
        ? { count: rows.length, next: null, previous: null, results: rows, ...extra }
        : url.includes("/settings/services")
          ? []
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
        <MemoryRouter initialEntries={[`/${TENANT}/plans-rates/taxes-fees${search}`]}>
          <Routes>
            <Route
              path="/:tenant/plans-rates/taxes-fees"
              element={
                <TaxesFeesTab
                  readOnly={false}
                  client={client}
                  timeZone="America/Chicago"
                  dateFormat="MM/DD/YYYY"
                  render={render2}
                />
              }
            />
            <Route
              path="/:tenant/plans-rates/taxes-fees/:taxId"
              element={<p data-testid="opened">opened</p>}
            />
            <Route path="/:tenant/plans-rates/taxes-fees/:taxId/edit" element={<p>edit</p>} />
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

describe("CR-165 task 5 — the Taxes & fees list, built from images 01–03", () => {
  it("columns in the drawn order", async () => {
    mount(recordingClient([], [HIGH, LOW]));
    await screen.findByText("Harbor Levy");
    const headings = screen
      .getAllByRole("columnheader")
      // The kit's sort glyph on the sorted column is not part of the label.
      .map((cell) => (cell.textContent ?? "").replace(/[▲▼]/g, "").trim())
      .filter((text) => text !== "");
    expect(headings).toEqual([
      "Tax or fee",
      "Version",
      "Applies to",
      "Rate",
      "From",
      "To",
      "GL account",
      "Premises",
      "Status",
    ]);
  });

  it("P21: no paragraph above the table", () => {
    const tab = RATING_TABS.find((one) => one.id === "taxes-fees");
    expect(tab?.explainerKey).toBeUndefined();
    expect(i18n.exists("rating.explainer.taxesFees")).toBe(false);
  });

  it("P22: name on one line, the authority's level under it — never repeated", async () => {
    mount(recordingClient([], [HIGH]));
    const link = await screen.findByRole("link", { name: "Harbor Levy" });
    expect(link).toHaveAttribute("href", `/${TENANT}/plans-rates/taxes-fees/tax-high`);
    const row = rowOf("Harbor Levy");
    expect(within(row).getByText("City")).toBeInTheDocument();
    expect(row.textContent).not.toContain("Harbor Levy · ");
  });

  it("P23: the rate is the figure alone — no wrapping sentence", async () => {
    mount(recordingClient([], [HIGH, LOW, OLD_SERVER]));
    await screen.findByText("Harbor Levy");
    expect(within(rowOf("Lakeside County")).getByText("3.15%")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("of the taxable amount");
    expect(within(rowOf("Old Fee")).getByText("0.25 / kgal")).toBeInTheDocument();
  });

  it("P24(a): a percentage over 20 wears the pill; one under does not", async () => {
    mount(recordingClient([], [HIGH, LOW]));
    await screen.findByText("Harbor Levy");
    expect(within(rowOf("Harbor Levy")).getByText("Over 20%")).toBeInTheDocument();
    expect(within(rowOf("Lakeside County")).queryByText("Over 20%")).toBeNull();
  });

  it("P24(b): the banner counts the SERVER's set, and Show them asks the server", async () => {
    const calls: Call[] = [];
    // The page holds ONE over-20 row; the server says the tenant has three.
    mount(recordingClient(calls, [HIGH, LOW], { over_20_count: 3 }));
    const banner = await screen.findByText(/taxes charge over 20%/);
    expect(banner.textContent).toContain("3 taxes charge over 20%.");
    await userEvent.click(screen.getByRole("button", { name: "Show them" }));
    await waitFor(() =>
      expect(calls.some((call) => call.url.includes("f.over_20=1"))).toBe(true),
    );
  });

  it("P24(c): no count served, no banner — the page is never counted", async () => {
    mount(recordingClient([], [HIGH, { ...HIGH, id: "tax-high-2", name: "Second Levy" }]));
    await screen.findByText("Harbor Levy");
    expect(screen.queryByText(/charge over 20%/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Show them" })).toBeNull();
  });

  it("P25: premises reached, as `N of M`; a server without it reads a dash", async () => {
    mount(recordingClient([], [HIGH, OLD_SERVER]));
    await screen.findByText("Harbor Levy");
    expect(within(rowOf("Harbor Levy")).getByText("13 of 29")).toBeInTheDocument();
    const old = rowOf("Old Fee");
    expect(within(old).queryByText(/ of /)).toBeNull();
  });

  it("P26: GL code bold, its name small under it — no long joined string", async () => {
    mount(recordingClient([], [HIGH]));
    await screen.findByText("Harbor Levy");
    const code = within(rowOf("Harbor Levy")).getByText("2399-07");
    expect(code.className).toContain("font-semibold");
    expect(within(rowOf("Harbor Levy")).getByText("Levy payable")).toBeInTheDocument();
    expect(rowOf("Harbor Levy").textContent).not.toContain("2399-07 — Levy payable");
  });

  it("P27: Version, From and To are separate; an open end reads No end", async () => {
    mount(recordingClient([], [HIGH, LOW, OLD_SERVER]));
    await screen.findByText("Harbor Levy");
    const high = rowOf("Harbor Levy");
    expect(within(high).getByText("V4")).toBeInTheDocument();
    expect(within(high).getByText("03/14/2026")).toBeInTheDocument();
    expect(within(high).getByText("05/09/2027")).toBeInTheDocument();
    expect(within(rowOf("Lakeside County")).getByText("No end")).toBeInTheDocument();
    expect(within(rowOf("Old Fee")).queryByText(/^V\d/)).toBeNull();
  });

  it("P28: the row's one action OPENS the details page; no pencil, no edit door", async () => {
    mount(recordingClient([], [HIGH]));
    await screen.findByText("Harbor Levy");
    const row = rowOf("Harbor Levy");
    expect(within(row).queryByRole("button", { name: /edit/i })).toBeNull();
    await userEvent.click(within(row).getByRole("button", { name: "Open" }));
    expect(await screen.findByTestId("opened")).toBeInTheDocument();
    expect(taxTabSource).not.toContain("taxWizardEditPath");
  });

  it("PO 2026-10-03: status is a kit FILTER with a removable chip, not a row of buttons", async () => {
    // *"on list view of Tax - ensure you ahve filter and not button for
    // filters- follow our toolkkit standard"* — supersedes the drawn buttons.
    const calls: Call[] = [];
    mount(recordingClient(calls, [HIGH]), "?f.status=ended");
    await screen.findByText("Harbor Levy");
    expect(screen.queryByRole("tab", { name: "Active" })).toBeNull();
    // The kit's `+ Filter ▾` is a <summary>, and it lists the server's filters.
    const panel = screen.getByText("+ Filter").closest("summary");
    expect(panel?.getAttribute("title")).toContain("Status");
    expect(panel?.getAttribute("title")).toContain("Authority");
    expect(panel?.getAttribute("title")).not.toContain("Over 20%");
    expect(calls.some((call) => call.url.includes("f.status=ended"))).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Remove the Status filter" }));
    await waitFor(() => expect(calls.at(-1)?.url).not.toContain("f.status"));
  });

  it("the list stays server-paged (NFR-3) and keeps its search and CSV", async () => {
    const calls: Call[] = [];
    mount(recordingClient(calls, [HIGH]));
    await screen.findByText("Harbor Levy");
    const list = calls.find((call) => call.url.includes("/taxes"));
    expect(list?.url).toContain("page=1");
    expect(list?.url).toContain("per=50");
    expect(screen.getByPlaceholderText("Find a tax or authority")).toBeInTheDocument();
    expect(document.querySelector('[data-resource="taxes"]')).not.toBeNull();
  });
});
