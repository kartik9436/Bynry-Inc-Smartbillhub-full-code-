// ── Trace ──────────────────────────────────────────────
// Screen:  Meter Reads blueprint **entry 15 — "Read cycles — the list"**,
//          `/:tenant/reads?tab=cycles`. Drawings read AS IMAGES (B14 rule 42):
//          p040 (the frame and the table), p041 (the five callouts, the
//          `DEF-MET-5206` hold and the as-built disposition table), p042 (the
//          spec row: primary action, table controls, write surfaces, states).
// Rules:   BR-MET-010 · BR-MET-011 CONFIRMED-AS-NARROWED · BR-SHL-010 ·
//          BR-SHL-011 · BR-SHL-020 · NFR-3 · B14 12 · 13 · 16 · 17 · 19 · 31
// ───────────────────────────────────────────────────────
/**
 * **THE LOAD-BEARING CASE IN THIS FILE IS AN ABSENCE, AND IT IS FIRST.**
 *
 * Entry 15 draws NINE columns and this screen builds SEVEN. ④ *Registers
 * collected* and ⑤ *Window* are held by `DEF-MET-5206` — two derivations of a
 * cycle's current window disagree (August against September, measured on one
 * day) — and the PO ruled *"Settle first."* on 2026-09-14. An absence is
 * invisible to every other check this repo has, so it is asserted here by name:
 * a lane that "finishes the drawing" without settling the fork turns this red
 * and reads why.
 *
 * The rest of the file is what the entry exists FOR: four table controls where
 * there were none, and a pager that pages on the SERVER over a read that used
 * to fetch everything and slice it in the browser (`NFR-3`).
 *
 * ⚠ **EVERY CASE WAS PROVED RED FIRST (hard-won law 7), in this harness** —
 * `npx vitest run src/features/metering/ReadCyclesTab.test.tsx` — against the
 * pre-entry-15 screen (`CyclesOpsPage`, the component this tab mounted until
 * today), which has no toolbar, no server pager, no row target, ten columns
 * including both held ones, and an empty state with no way out. The failures
 * are quoted in the lane report.
 *
 * ⚠ **IT MOUNTS UNDER THE REAL PATH PATTERN.** A bare `MemoryRouter` with no
 * `/:tenant/...` route leaves `useParams().tenant` undefined, so every URL the
 * page builds comes out `//reads/...` — a protocol-relative URL to another host
 * that reads as a perfectly good string to `toContain`. That is how the customer
 * portal's front page shipped with two working doors out of eight.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { CycleRow, ListPage, MyPermissions } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import type { TableRequestState } from "@/components/tableTypes";
import { SEEDED_REGIONAL } from "@/components/tenantRegionalFixture";

import {
  READ_CYCLES_TAB_PATH,
  ReadCyclesTab,
  SETTINGS_ROUTES_CYCLES,
  cycleFrequencyLine,
  cycleStatusTone,
  readCyclesQueryKey,
  readCyclesTableConfig,
} from "./ReadCyclesTab";
import { PREMISES_PERMISSION } from "./meteringShared";

// ⚠ **A BARE `import … from "node:fs"` PASSES VITEST AND FAILS `tsc --noEmit`**
// — `@types/node` is not in the app's tsconfig, so the module has no
// declarations. `api/apiPathLiteral.guard.test.ts`, `components/buttonKit.test.ts`
// and `styles/routeBUtilities.test.ts` all reach Node through this string-split
// shim for exactly that reason, and it is COPIED rather than reinvented: the
// split keeps Vite from pre-bundling and keeps `tsc` out of it. Written the
// obvious way first here too, and `tsc` said `TS2307: Cannot find module
// 'node:fs'` — which is why three other files already carry this note.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string | URL, enc: string): string;
};
const { readFileSync } = nodeFs;

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/**
 * ⚠ **THE FIGURES ARE NOT THE DRAWING'S (B14 rule 37).** The drawing inks
 * `CY-001`, `RT-001`, `5` meters and `11/05/2026`; every one of those is an
 * illustration of a SHAPE and asserting one would be a test about the
 * illustrator's choice of example. What is asserted below is the shape: which
 * columns, in which order, with which controls, pointing where.
 */
const CYCLES: CycleRow[] = [
  {
    id: "c1",
    code: "CY-101",
    routes: ["RT-201", "RT-203"],
    window_start: "2026-09-01",
    window_end: "2026-09-03",
    bill_date: "2026-11-05",
    due_days: 20,
    due_date: "2026-11-25",
    expected: 5,
    collected: null,
    progress: null,
    status: "in_progress",
    lifecycle_status: "active",
    name: "North monthly",
    frequency: "Monthly",
    start_day: 1,
    days_to_complete: 3,
    effective_start_day: 1,
    start_day_differs: false,
    read_window_source: "derived",
    first_run_date: "2026-09-01",
    bill_day: 5,
    accounts: 42,
    route_ids: ["r1", "r2"],
    proposed_windows: [],
    next_period: null,
    next_cycle_date: null,
    schedule_gap: null,
    schedule_warning: null,
  } as unknown as CycleRow,
  {
    id: "c2",
    code: "CY-103",
    routes: ["RT-204"],
    window_start: null,
    window_end: null,
    bill_date: null,
    due_days: null,
    due_date: null,
    expected: 2,
    collected: null,
    progress: null,
    // The DOMAIN STATE entry 15 names — *before the window opens*. Two of the
    // three places the drawing says it are ④ and ⑤, which are held; this is
    // the half the screen may honestly show, and it is served from the
    // committed-read count alone.
    status: "scheduled",
    lifecycle_status: "draft",
    name: "South quarterly",
    frequency: "Quarterly",
    start_day: 15,
    days_to_complete: 1,
    effective_start_day: 15,
    start_day_differs: false,
    read_window_source: null,
    first_run_date: null,
    bill_day: null,
    accounts: 8,
    route_ids: ["r3"],
    proposed_windows: [],
    next_period: null,
    next_cycle_date: null,
    schedule_gap: null,
    schedule_warning: null,
  } as unknown as CycleRow,
];

/** BR-SHL-011's default request state — what the tab asks for on first paint. */
const FIRST_STATE: TableRequestState = {
  q: "",
  sort: "code",
  dir: "asc",
  page: 1,
  per: 50,
  filters: {},
};

function permissions(access: string): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access }],
  };
}

function renderTab(seed: { page?: ListPage<CycleRow>; access?: string } = {}): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.regionalSettings, SEEDED_REGIONAL);
  if (seed.page !== undefined) {
    queryClient.setQueryData([...readCyclesQueryKey, JSON.stringify(FIRST_STATE)], seed.page);
  }
  queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access ?? "Full"));
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* The REAL path pattern — see this file's opening note. */}
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/reads?tab=cycles`]}>
          <Routes>
            <Route
              path="/:tenant/reads"
              element={<ReadCyclesTab timeZone="America/Chicago" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const FULL_PAGE: ListPage<CycleRow> = { rows: CYCLES, total: 99, pagedBy: "server" };

// ════════════════════════════════════════════════════════════════════════════
// ⛔ THE HOLD — `DEF-MET-5206`
// ════════════════════════════════════════════════════════════════════════════
describe("entry 15 · DEF-MET-5206 — the two columns that are NOT built", () => {
  it("neither Registers collected nor Window is declared on the capability row", () => {
    const config = readCyclesTableConfig(t, {
      dash: "—",
      tenantPath: (segment) => `/${TEST_TENANT}${segment}`,
      timeZone: "America/Chicago",
      dateFormat: "MM/DD/YYYY",
    });
    const keys = config.columns.map((column) => column.key);
    // BR-SHL-010 — a capability absent from the config is absent from the
    // screen, which is why the ▦ chooser cannot offer either of these.
    expect(keys).not.toContain("registers_collected");
    expect(keys).not.toContain("completeness");
    expect(keys).not.toContain("window");
    expect(keys).not.toContain("window_state");
  });

  it("the rendered table shows neither heading, and no completeness figure", () => {
    const html = renderTab({ page: FULL_PAGE });
    expect(html).not.toContain("Registers collected");
    expect(html).not.toContain("Completeness");
    // The old cell's own vocabulary — the chase call that fed it is gone too.
    expect(html).not.toContain("Nothing expected");
    expect(html).not.toContain("Chase");
    expect(html).not.toContain("days left");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// THE SEVEN COLUMNS THAT ARE BUILT, IN THE DRAWN ORDER
// ════════════════════════════════════════════════════════════════════════════
describe("entry 15 · the table", () => {
  const config = () =>
    readCyclesTableConfig(t, {
      dash: "—",
      tenantPath: (segment) => `/${TEST_TENANT}${segment}`,
      timeZone: "America/Chicago",
      dateFormat: "MM/DD/YYYY",
    });

  it("the columns are the drawn seven, in the drawn order", () => {
    expect(config().columns.map((column) => column.key)).toEqual([
      "code",
      "routes",
      "frequency",
      "read_window",
      "bill_date",
      "expected",
      "status",
    ]);
  });

  it("the drawn headings are the rendered headings", () => {
    const html = renderTab({ page: FULL_PAGE });
    for (const heading of ["Cycle", "Routes", "Frequency", "Read window", "Bill date", "Meters", "Status"]) {
      expect(html).toContain(heading);
    }
  });

  it("Frequency folds Start day and Days to complete into one cell", () => {
    // The drawing's own example of the SHAPE: *"Monthly · day 1 · 3 days"*.
    expect(cycleFrequencyLine(CYCLES[0], t, "—")).toBe("Monthly · day 1 · 3 days");
    // …and the plural is a plural, not an "s" glued on a number.
    expect(cycleFrequencyLine(CYCLES[1], t, "—")).toBe("Quarterly · day 15 · 1 day");
    const html = renderTab({ page: FULL_PAGE });
    expect(html).toContain("Monthly · day 1 · 3 days");
    // The two folded columns are GONE as columns and PRESENT as facts.
    expect(html).not.toContain(">Start day<");
    expect(html).not.toContain(">Days to complete<");
  });

  it("Meters is the only meter count on the row (callout ③)", () => {
    const html = renderTab({ page: FULL_PAGE });
    expect(html).toContain("Meters");
    // The column that counted READINGS beside it is what made the old quotient
    // meaningless (DEF-2730). It is not here.
    expect(html).not.toContain("Collected");
  });

  it("Status renders the served operational word, including the before-open one", () => {
    const html = renderTab({ page: FULL_PAGE });
    expect(html).toContain("In progress");
    expect(html).toContain("Scheduled");
    expect(cycleStatusTone("in_progress")).toBe("warning");
    expect(cycleStatusTone("scheduled")).toBe("neutral");
    expect(cycleStatusTone("billed")).toBe("success");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// THE FOUR TABLE CONTROLS — the point of the entry
// ════════════════════════════════════════════════════════════════════════════
describe("entry 15 · search · filter · columns · sort · the server pager", () => {
  const config = () =>
    readCyclesTableConfig(t, {
      dash: "—",
      tenantPath: (segment) => `/${TEST_TENANT}${segment}`,
      timeZone: "America/Chicago",
      dateFormat: "MM/DD/YYYY",
    });

  it("callout ② — search covers the cycle code AND the route code, and says so", () => {
    expect(config().searchFields).toEqual(["code", "name", "route"]);
    // B14 rule 19 — this list's OWN prompt, naming what the server matches.
    expect(config().searchPlaceholder).toBe("metering.cycles.searchPlaceholder");
    const html = renderTab({ page: FULL_PAGE });
    expect(html).toContain("Search cycle or route…");
  });

  it("two filters are declared, and the lifecycle one is NOT called Status", () => {
    const filters = config().filters ?? [];
    expect(filters.map((filter) => filter.name)).toEqual(["frequency", "status"]);
    // ⚠ The STATUS COLUMN shows the operational word (Scheduled / In progress)
    // and `f.status` filters the stored lifecycle (Draft / Active / Inactive).
    // One label over two facts is the quietest way to make a control wrong.
    expect(filters[1].label).toBe("Lifecycle");
    expect(filters[1].options.map((option) => option.value)).toEqual([
      "draft",
      "active",
      "inactive",
    ]);
    const html = renderTab({ page: FULL_PAGE });
    expect(html).toContain("+ Filter");
    expect(html).toContain("All");
  });

  it("the sortable headers are the drawn three, and every key is one the server answers", () => {
    const sortable = config()
      .columns.filter((column) => column.sortable === true)
      .map((column) => column.key);
    expect(sortable).toEqual(["code", "read_window", "bill_date"]);
    // `selectors.CYCLE_SORTS` — the vocabulary these three travel as. A key the
    // server drops comes back in the default order with nothing saying so.
    expect(config().defaultSort).toEqual({ sort: "code", dir: "asc" });
  });

  it("the ▦ column chooser is drawn", () => {
    expect(renderTab({ page: FULL_PAGE })).toContain("Show or hide columns");
  });

  it("NFR-3 — the pager counts the SERVER's total, not the rows in hand", () => {
    // Two rows in hand and ninety-nine in the set. A pager that ran in the
    // browser over a fetch-everything read — which is exactly what this screen
    // used to be — could only ever say "of 2".
    const html = renderTab({ page: FULL_PAGE });
    expect(html).toContain("of 99");
    expect(html).toContain("Rows per page");
    // …and the NEXT control is live, because the page count is derived from the
    // server's total against the page size — on a browser-side pager over two
    // rows it would be disabled.
    expect(html).toContain('aria-label="Next page"');
    expect(html).not.toContain('disabled="" aria-label="Next page"');
  });

  /**
   * ⚠ **B14 RULE 16 IS NOT FULLY BUILT AND IT IS THE SHARED FOOTER'S GAP, NOT
   * THIS SCREEN'S — ALREADY FILED, TWICE.**
   *
   * The rule spells the footer out: *"Showing 1–50 of N · Rows per page
   * 50/100/200/500/1000 · ⇤ ← Page x of y → ⇥"*, and entry 15's drawing draws
   * all of it. `DataTable`'s footer renders the range, the page-size select and
   * prev/next — **no first, no last and no `Page x of y`** — which is
   * `DEF-2449` (OPEN) and `DEF-SHL-4754` (OPEN). `table.pager.pageOf` exists in
   * all eleven catalogues and only `ListPager` renders it.
   *
   * It is asserted HERE as an absence so the next lane meets it as a fact
   * rather than re-discovering it: **nothing on this screen can close it.**
   * `DataTable` is mounted by 27 lists, and rule 38's own reasoning is that a
   * kit change is never local.
   */
  it("the missing half of rule 16 is the shared footer's, and is recorded not silently accepted", () => {
    const html = renderTab({ page: FULL_PAGE });
    expect(html).not.toContain("Page 1 of 2");
    // The key is translated in all eleven catalogues and rendered by the OTHER
    // footer, which is the whole of DEF-SHL-4754: one rule, two implementations.
    expect(t("table.pager.pageOf", { page: 1, pages: 2 })).toBe("Page 1 of 2");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// THE ROW IS THE TARGET, AND IT OPENS ENTRY 20
// ════════════════════════════════════════════════════════════════════════════
describe("entry 15 · where a row goes", () => {
  it("the identity cell links to entry 20 under the tenant", () => {
    const html = renderTab({ page: FULL_PAGE });
    expect(html).toContain(`href="/${TEST_TENANT}/reads/cycles/c1"`);
    // ⚠ Not `//reads/...` — the protocol-relative URL a router-less fixture
    // builds, which every `toContain` in this repo would have accepted.
    expect(html).not.toContain('href="//reads');
  });

  it("the whole row is declared as the target (B14 rule 12's row-click)", () => {
    const config = readCyclesTableConfig(t, {
      dash: "—",
      tenantPath: (segment) => `/${TEST_TENANT}${segment}`,
      timeZone: "America/Chicago",
      dateFormat: "MM/DD/YYYY",
    });
    expect(config.rowHref?.(CYCLES[0])).toBe(`/${TEST_TENANT}/reads/cycles/c1`);
  });

  it("the tab's own address is the one the retired URLs redirect to", () => {
    expect(READ_CYCLES_TAB_PATH).toBe("/reads?tab=cycles");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// THE STATES THE DRAWING SPECIFIES
// ════════════════════════════════════════════════════════════════════════════
describe("entry 15 · states", () => {
  it("empty — the drawn sentence AND the way out it lacked", () => {
    const html = renderTab({ page: { rows: [], total: 0, pagedBy: "server" } });
    expect(html).toContain("No cycles are configured yet.");
    expect(html).toContain("Add a cycle in Settings →");
    // B14 rule 4 — the page header above already owns this screen's primary,
    // so the empty state's way out is the secondary tier.
    expect(html).toContain('data-variant="secondary"');
    // ⚠ **THE KIT'S CTA IS A `<button>` WITH AN `onCta`, NOT AN `<a>`**, so
    // there is no href to assert and a test looking for one passes on a screen
    // with no destination at all. What CAN be pinned is the destination itself,
    // which is the constant the handler navigates to — and it is the address
    // BR-MET-011 puts every cycle write behind.
    expect(SETTINGS_ROUTES_CYCLES).toBe("/settings/reference-data/routes-cycles");
  });

  it("loading — the table skeleton, and no empty sentence under it", () => {
    // Nothing seeded, so the query is pending on first paint.
    const html = renderTab();
    expect(html).not.toContain("No cycles are configured yet.");
    expect(html).toContain("skeleton");
  });

  it("failed — the reason and a Retry, never a silent empty list", () => {
    // A18 §4's own copy, asserted from the catalogue rather than typed here.
    expect(t("table.failed.title")).toBe("This list couldn't load.");
    expect(t("table.failed.reason")).toContain("Retry runs the same request again.");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// BR-MET-011 — THE WRITE SURFACES, WHICH ARE NONE
// ════════════════════════════════════════════════════════════════════════════
describe("entry 15 · BR-MET-011 CONFIRMED-AS-NARROWED", () => {
  it("carries no create, edit or delete — not disabled, ABSENT", () => {
    const html = renderTab({ page: FULL_PAGE });
    for (const affordance of ["+ Cycle", "Add cycle", "Edit", "Delete", "Deactivate", "Save"]) {
      expect(html).not.toContain(affordance);
    }
  });

  it("and `Manage in Settings →` has moved off this screen into entry 20", () => {
    const html = renderTab({ page: FULL_PAGE });
    // The drawing's as-built table: MOVED — *"Into entry 20's header, beside
    // the cycle it configures."* It survives here only as the EMPTY state's
    // way out, which is a different control with a different sentence.
    expect(html).not.toContain("Manage in Settings");
  });

  it("B14 rule 31 — no database id reaches a cell", () => {
    const html = renderTab({ page: FULL_PAGE });
    // The ids ride in the href, which is a URL and not a field's value.
    expect(html).not.toContain(">c1<");
    expect(html).not.toContain(">r1<");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// ⛔ ENTRY 14's HOLD, AND THE TEST THAT FIRES WHEN IT EXPIRES
// ════════════════════════════════════════════════════════════════════════════
/**
 * **Hard-won law 2's amendment: *"when you write a hold, write the test that
 * fires when the hold expires, in the same commit."***
 *
 * Entry 14 retires Routes *"as a screen"* and says where its contents go in the
 * same breath — *"Every column survives, inside the cycle it belongs to — see
 * entry 20."* So the redirect is built (`RedirectToReadCycles`) and is NOT
 * mounted: forwarding `/:tenant/reads/routes` before entry 20's Routes section
 * exists would lose the nine columns rather than move them, and would take the
 * only door to entry 21 with it.
 *
 * **The condition is mechanical and this is it.** Entry 20 is
 * `reads/cycles/:cycleId`; the day `App.tsx` mounts it, this case goes RED and
 * names what to do. The alternative — a comment saying "mount it later" — is
 * the shape that left the customer portal with two working doors out of eight.
 */
describe("entry 14 · the redirect is held until entry 20 lands", () => {
  /**
   * **THE PAIRING, NOT A ONE-SIDED PROMISE.** `RedirectToReadCycles` is built
   * and NOT mounted, because entry 14 retires Routes *"as a screen"* and says
   * in the same breath where its contents go — *"Every column survives, inside
   * the cycle it belongs to — see entry 20."* Forwarding the address before
   * entry 20 exists would lose the nine columns rather than move them.
   *
   * So the two are asserted as ONE state: **entry 20's route and entry 14's
   * redirect are both absent, or both present.** Neither (today, on the branch)
   * is green; both (once entry 14 lands) is green; **entry 20 mounted with the
   * redirect still held is RED and names the three steps.** That is the shape
   * law 2's amendment asks for — a hold that fires when it expires — and it is
   * not a check that cannot fail: flipping either side alone turns it red.
   */
  it("entry 20's route and entry 14's redirect land together, or neither does", () => {
    const app = readFileSync(new URL("../../App.tsx", import.meta.url), "utf-8");
    const entry20Mounted = app.includes('path: "reads/cycles/:cycleId"');
    const redirectMounted = app.includes("RedirectToReadCycles");
    expect(
      redirectMounted,
      entry20Mounted
        ? [
            "Entry 20 (`reads/cycles/:cycleId`) is mounted, so entry 14's hold has",
            "expired. Three steps, and they go together:",
            "  1. mount `RedirectToReadCycles` at `reads/routes` AND `reads/cycles`",
            "     — blueprint entry 14: 'Kept and redirected… there are tickets with",
            "     these URLs in them';",
            "  2. drop both from the sidebar (`AppShell.tsx` SHELL_NAV and",
            "     `routing/sidebarDestinations.ts`), because a nav word pointing at a",
            "     redirect is a door to a door;",
            "  3. delete `RoutesOpsPage` from RoutesCyclesPage.tsx and its cases from",
            "     RoutesCyclesPage.test.tsx. The all-routes view is a RECORDED COST of",
            "     the ruling, not a screen to keep alive — and check entry 21's door",
            "     (`reads/routes/:routeId`) while you are there, because it was",
            "     reached from the retired screen's row link.",
          ].join("\n")
        : "entry 14's redirect is mounted while entry 20's route is not — the nine columns have nowhere to go",
    ).toBe(entry20Mounted);
  });
});
