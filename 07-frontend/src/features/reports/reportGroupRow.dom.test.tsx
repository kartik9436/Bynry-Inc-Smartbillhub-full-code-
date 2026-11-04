// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 2 · `P2.18` (*"Drill through to the facts"*).
//          Screens: 2·1 group rows.
// Defect:  DEF-REP-6869 (a group row's `path` is not a filter set) ·
//          DEF-REP-6871 (44 of 71 dimensions cannot be drilled)
// Rules:   B14 rule 33 · CLAUDE.md hard-won law 2 and its mirror · law 7
//          clause 2 (*"ask what would make this check pass wrongly"*)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  A SUBTOTAL OPENS THE ROWS THAT MAKE IT — BY ADDRESS, NOT BY APPEARANCE  ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// ⚠ **THE RED THIS WAS PROVED ON.** Before `ReportGroupRow` existed the viewer
// handed every server row to `ReportCell`, which looked up `row["invoice_no"]`
// on an object holding `__kind__`, `value`, `rows` and `subtotals`. A grouped
// report drew **a line of em-dashes where its subtotal belongs**, and no check
// in the module saw it because nothing rendered a grouped payload at all.
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7 clause 2):
//
//   · **A bare `MemoryRouter`.** `useParams().tenant` is then undefined and
//     every address the screen builds comes out `//reports/…` — a
//     protocol-relative URL to another host, which reads as a perfectly good
//     string to `toContain`. Mounted under the real `/:tenant/reports/:reportKey`.
//   · **Asserting the link EXISTS.** A drill-through pointing at the wrong
//     rows is the whole defect; the address is asserted in full, including
//     that `group_by` has GONE and the clerk's window has SURVIVED.
//   · **Asserting only the presence of a control.** The `filters: null` case
//     asserts the link is ABSENT, so a component that always draws one cannot
//     pass both cases.
//   · **A subtotal that never renders.** The refused case would satisfy *"no
//     digits"* perfectly on a crashed row, so the lawful case asserts the real
//     figure IS on screen in the same markup.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ReportGroupRow } from "@/api/reportsEndpoints";
import { GroupLabelCell, GroupSubtotalCell } from "./ReportGroupRow";

afterEach(cleanup);

const t = i18n.getFixedT("en");
const TENANT = "brazosbend";

/** A group row exactly as the server serves it — measured on real PostgreSQL
 *  16 against the seeded demo tenant, 2026-09-27, via
 *  `10-scripts/rep_p2_18_drill_readback.py`. */
const COMMERCIAL: ReportGroupRow = {
  __kind__: "group",
  level: 0,
  dimension: "consumer_class",
  value: "Commercial",
  path: [{ dimension: "consumer_class", column: "account_class", value: "Commercial" }],
  filters: { class: "commercial" },
  drill_unavailable: null,
  rows: 11,
  subtotals: { total: "48221.140000" },
};

/** The common case: 44 of the registry's 71 dataset/dimension pairs declare no
 *  filter that can select them (`DEF-REP-6871`), so the server sends none. */
const UNDRILLABLE: ReportGroupRow = {
  ...COMMERCIAL,
  dimension: "area",
  value: "North",
  filters: null,
  drill_unavailable: "drill_through_filter_is_not_declared",
  rows: 7,
};

function mountCell(row: ReportGroupRow, search: string) {
  const router = createMemoryRouter(
    [
      {
        // ⚠ THE REAL PATH PATTERN — see the header.
        path: "/:tenant/reports/:reportKey",
        element: (
          // ⚠ `expandable={false}` — these cases mount ONE cell with no rows
          // around it, so there is by definition nothing beneath this group.
          // `P2.24`'s own states are asserted in
          // `reportDrillDownInPlace.dom.test.tsx`, against the real payload.
          <GroupLabelCell
            row={row}
            reportHref={`/${TENANT}/reports/ar-aging`}
            search={new URLSearchParams(search)}
            expandable={false}
            open={false}
            onToggle={() => undefined}
            t={t}
          />
        ),
      },
    ],
    { initialEntries: [`/${TENANT}/reports/ar-aging?${search}`] },
  );
  render(<RouterProvider router={router} />);
}

describe("P2.18 · a subtotal opens the rows behind it", () => {
  it("the drill-through carries the group's FILTERS, drops the grouping, keeps the window", () => {
    mountCell(COMMERCIAL, "group_by=consumer_class&f.from=2026-09-01&f.to=2026-09-30&page=4");
    const link = screen.getByRole("link", { name: "Commercial" });
    const href = link.getAttribute("href") ?? "";

    // The address, in full. Not `toContain` — a partial match is how
    // `//portal/…` passed for a working link on the customer portal.
    expect(href.startsWith(`/${TENANT}/reports/ar-aging?`)).toBe(true);
    const query = new URLSearchParams(href.split("?")[1] ?? "");
    expect(query.get("f.class")).toBe("commercial");
    // The grouping is GONE: drilling means show me the facts, and carrying it
    // through would open the same subtotal again.
    expect(query.get("group_by")).toBeNull();
    // The page is RESET: page 4 of a shorter report is a blank screen under a
    // chip naming a group with eleven rows in it.
    expect(query.get("page")).toBeNull();
    // …and the clerk's own question SURVIVES. A drill that widened the window
    // would open rows the subtotal never counted.
    expect(query.get("f.from")).toBe("2026-09-01");
    expect(query.get("f.to")).toBe("2026-09-30");
  });

  it("the DISPLAY label never becomes the filter value — DEF-REP-6869", () => {
    mountCell(COMMERCIAL, "group_by=consumer_class");
    const href = screen.getByRole("link", { name: "Commercial" }).getAttribute("href") ?? "";
    const query = new URLSearchParams(href.split("?")[1] ?? "");
    // Measured: `f.class=Commercial` returns 0 rows and `f.class=commercial`
    // returns 11. Both directions, because asserting only the first would pass
    // for a link carrying no class at all.
    expect(query.get("f.class")).toBe("commercial");
    expect(query.get("f.class")).not.toBe("Commercial");
    // And the path's own dimension name is never used as a parameter — the
    // dataset declares no `consumer_class` filter, so `bind` would drop it and
    // open the WHOLE report under a chip naming one group.
    expect(query.get("f.consumer_class")).toBeNull();
    expect(query.get("consumer_class")).toBeNull();
  });

  it("a group the server cannot express as filters offers NO control at all", () => {
    mountCell(UNDRILLABLE, "group_by=area");
    // The group still reads — the label and its count are the subtotal's own
    // facts and do not depend on being openable.
    expect(screen.getByText("North")).toBeTruthy();
    expect(screen.getByText("7 rows")).toBeTruthy();
    // ⚠ ABSENT, never disabled and never a link to nowhere. A control that
    // runs and answers a different question is worse than one that is not
    // there, because the clerk cannot tell.
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("the count is a FACT in rule 33's budget, and reads as a sentence would", () => {
    mountCell(COMMERCIAL, "");
    const count = screen.getByText("11 rows");
    expect(count.textContent!.trim().split(/\s+/).length).toBeLessThanOrEqual(6);
    // RATIONALE is zero words on screen: nothing explains what a subtotal is,
    // why it can be opened, or what a dimension means.
    expect(screen.queryByText(/because/i)).toBeNull();
    expect(screen.queryByText(/dimension/i)).toBeNull();
  });
});

describe("P2.18 · the subtotal cell feeds the refusal rather than bypassing it", () => {
  const money = (amount: string) => <span data-money="">{amount}</span>;

  it("a lawful subtotal renders its figure", () => {
    render(
      <GroupSubtotalCell
        total={COMMERCIAL.subtotals.total}
        currency="USD"
        t={t}
        renderMoney={money}
      />,
    );
    expect(screen.getByText("48221.140000")).toBeTruthy();
  });

  it("an unlawful one renders the em-dash and its reason, and no digit", () => {
    const { container } = render(
      <GroupSubtotalCell
        total={{
          value: null,
          display: "—",
          refused: true,
          measure: "total",
          reason_code: "balance_does_not_sum_across_time",
          reason: "Balances do not sum across time",
          across: ["time"],
        }}
        currency="USD"
        t={t}
        renderMoney={money}
      />,
    );
    expect(container.textContent).toContain("—");
    expect(container.textContent).toMatch(/sum across time/i);
    // ⚠ The worked case from the brief: $41,220.00 + $44,118.50 + $48,221.14 =
    // $133,559.64, a figure nobody owes. No digit of it reaches the screen.
    expect(container.textContent!.replace(/[^0-9]/g, "")).toBe("");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// THE WIRING — hard-won law 2. A component nothing mounts is dead UI.
// ═══════════════════════════════════════════════════════════════════════════
describe("P2.18 · the VIEWER renders a group row, not a line of em-dashes", () => {
  it("a grouped payload draws its label, its count and its subtotal", async () => {
    const { QueryClient, QueryClientProvider } = await import("@tanstack/react-query");
    const { queryKeys } = await import("@/api/queryClient");
    const { shellBootSeed } = await import("@/components/shellBootSeed");
    const { ToastProvider } = await import("@/components/Toast");
    const { ReportViewerPage } = await import("./ReportViewerPage");

    const GROUPED = {
      key: "ar_aging",
      basis: "posting",
      window: { as_of: "2026-09-30" },
      currency: "USD",
      columns: ["account_no", "customer_name", "total"],
      group_by: ["consumer_class"],
      rows: [
        COMMERCIAL,
        { account_id: "a1", account_no: "AC-2026-00004", customer_name: "Dev Duval", total: "1202.400000" },
      ],
      kpis: [],
      totals: { total: "48221.140000" },
      unavailable: [],
      grain: "account",
      controls: { sorts: [], sort: "", dir: "asc", searchable: false },
    };
    const get = async (path: string) => {
      if (path.startsWith("/reports/")) return { data: GROUPED, status: 200 };
      if (path === "/reports")
        return {
          data: { cards: [], vocabularies: { services: [], bill_types: [], purposes: [] } },
          status: 200,
        };
      return { data: { results: [], count: 0 }, status: 200 };
    };
    const write = async () => ({ data: {}, status: 200 });
    const client = { request: get, get, post: write, put: write, patch: write, delete: write };

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity } },
    });
    queryClient.setQueryData(queryKeys.me, {
      id: "u1",
      full_name: "Dana Whitfield",
      email: "dana@sample.test",
      phone: null,
      role: "system_admin",
      role_name: "System Admin",
      must_change_password: false,
    });
    queryClient.setQueryData(queryKeys.myPermissions, {
      role: "system_admin",
      role_name: "System Admin",
      permissions: [{ code: "reports", label: "Reports", access: "Full" }],
    });
    queryClient.setQueryData(
      queryKeys.shellDisplay,
      shellBootSeed(
        { timezone: "America/Chicago", date_format: "MM/DD/YYYY" },
        { fy_label: "FY2026", period: 9, start: "2026-09-01", end: "2026-09-30", status: "open" },
      ),
    );

    const router = createMemoryRouter(
      [
        {
          path: "/:tenant/reports/:reportKey",
          element: (
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            <ReportViewerPage client={client as any} timeZone="America/Chicago" today="2026-09-30" />
          ),
        },
      ],
      { initialEntries: [`/${TENANT}/reports/ar-aging?group_by=consumer_class`] },
    );
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </QueryClientProvider>,
    );

    // The group's own facts reach the screen…
    expect(await screen.findByText("Commercial")).toBeTruthy();
    expect(screen.getByText("11 rows")).toBeTruthy();
    // …the fact row below it still renders, so this is not a screen that has
    // simply replaced its table…
    //
    // ⚠ **AMENDED 2026-09-27 (lane REP-P2-REST) — `P2.24` GAVE A GROUP ROW A
    // RESTING STATE, AND IT IS CLOSED.** p028's 2·1E note ② draws *"▾ open · ▸
    // closed"*, so a grouped report now opens showing its outermost level and
    // the fact rows arrive on a click. THIS CASE'S SUBJECT IS UNCHANGED: it
    // asserts the same fact row, in the same markup, for the same reason —
    // that the viewer draws a grouped payload rather than replacing its table
    // — and the one added line is the click the drawing says is required.
    // Asserting it BEFORE the click would have been this case silently
    // becoming a test of the disclosure's default instead.
    fireEvent.click(screen.getByRole("button", { name: t("table.expand.row", { row: "Commercial" }) }));
    expect(await screen.findByText("AC-2026-00004")).toBeTruthy();
    // …and the drill-through points at the filtered report by ADDRESS.
    const link = screen.getByRole("link", { name: "Commercial" });
    const query = new URLSearchParams((link.getAttribute("href") ?? "").split("?")[1] ?? "");
    expect(query.get("f.class")).toBe("commercial");
    expect(query.get("group_by")).toBeNull();
  });
});
