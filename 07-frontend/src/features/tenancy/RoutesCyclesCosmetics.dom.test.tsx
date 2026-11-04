// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-029 RC-W3-T7 (PO 2026-08-23) — the open cosmetic batch on the
//           Routes & Cycles surface, closed and asserted.
// Defects:  DEF-223 (four B14 rules broken, measured in Chromium: no footer on
//           the SET-06 meter list or the SET-07 route picker, and no toolbar on
//           the SET-07 picker) · DEF-582 (the wizard empty-state cell has never
//           been centred and its 24px padding has never applied) ·
//           DEF-224 (no count on this surface has a plural form)
// Rules:    B14 rule 12 (table toolbar) · 16 (pagination footer on EVERY list
//           table; wizard SUMMARY tables exempt) · 17 (empty state)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **THESE THREE DEFECTS ARE ALL ON WIZARD STEPS 2 AND 3, WHICH A FIRST-PAINT
 * TEST CANNOT REACH.** `renderToStaticMarkup` renders step 1 and stops — a
 * stepper is state, and state needs an event. That is exactly why DEF-223 and
 * DEF-582 were both found by a human in Chromium and by no suite in this repo:
 * the markup they are about had never been rendered by a test at all.
 *
 * So this file clicks through, in jsdom, the way DEF-523 established.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";
import type { CycleRow, RouteRow } from "@/api/endpoints";
import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { CycleWizard } from "./RoutesCyclesWizards";
import { pluralKey } from "./routesCyclesShared";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function route(id: string, code: string): RouteRow {
  return {
    id,
    code,
    name: `${code} name`,
    route_type: "walk",
    feeder_ref: null,
    assigned_to: null,
    cycle_id: null,
    cycle_code: null,
    status: "active",
    members: 1,
    meters: 1,
    collected: null,
    last_completion: null,
    progress: null,
    service_id: null,
    service_code: null,
    services: [],
    service_ids: [],
    area_id: null,
    area_code: null,
    area_name: null,
    notes: null,
    premises: 1,
    units: 1,
    meters_available: 1,
    meters_excluded: 0,
    excluded_asset_ids: [],
    exclusions: [],
  };
}


/**
 * ⚠ **THE WIZARD FETCHES ITS OWN PAGE OF ROUTES SINCE `DEF-MET-5743`**, so the
 * fixture hands it a CLIENT rather than an array. That is not ceremony: the
 * whole point of the change is that step 2 makes a request, and a fixture that
 * went on passing rows in memory could not tell the fixed screen from the
 * broken one.
 */
function routesClient(routes: RouteRow[]): ApiClient {
  return {
    get: async (path: string, options?: { query?: Record<string, unknown> }) => {
      if (path === "/routes") {
        const per = Number(options?.query?.per ?? 50);
        const page = Number(options?.query?.page ?? 1);
        const q = String(options?.query?.q ?? "");
        const onCycle = options?.query?.["f.on_cycle"];
        // The stub does the SERVER's job, because the screen no longer does it:
        // match, then window. A stub that returned everything would hide a
        // screen that had gone back to slicing in the browser.
        const matched = routes.filter((row) => {
          if (onCycle === "1" && row.cycle_code === null) {
            return false;
          }
          return (
            q.length < 2 ||
            row.code.toLowerCase().includes(q.toLowerCase()) ||
            (row.name ?? "").toLowerCase().includes(q.toLowerCase())
          );
        });
        return {
          data: {
            count: matched.length,
            next: null,
            previous: null,
            results: matched.slice((page - 1) * per, page * per),
          },
          status: 200,
          headers: new Headers(),
        };
      }
      return { data: { count: 0, next: null, previous: null, results: [] }, status: 200, headers: new Headers() };
    },
  } as unknown as ApiClient;
}

function renderCycleWizard(routes: RouteRow[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(["cycles", "next-code"], { code: "CY-009", warnings: [] });
  queryClient.setQueryData(["cycles", "coverage", ""], { uncovered_accounts: 0 });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <CycleWizard
            cycle={null as CycleRow | null}
            client={routesClient(routes)}
            readOnly={false}
            onDone={() => undefined}
            onCancel={() => undefined}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Step 1 → step 2. The rail is clickable only once a step is complete, so the
 *  footer's Next is the honest way through. */
async function toStepTwo(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.type(screen.getByLabelText(/Name/), "Quarterly — irrigation");
  await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
}

describe("DEF-223 — the SET-07 route picker gains B14's toolbar and footer", () => {
  it("rule 12: the picker has a search box, which it has never had", async () => {
    const user = userEvent.setup();
    renderCycleWizard([route("r1", "RT-001"), route("r2", "RT-002")]);
    await toStepTwo(user);
    // The SET-06 picker two steps away has had one since CR-006; this one had
    // "no search, chips or + Filter" at all (DEF-223, measured).
    //
    // ⚠ **THE BOX IS `DataTable`'s NOW, NOT THIS SCREEN'S (DEF-TEN-5706).** It
    // is found by the SAME accessible name, because the config hands the kit
    // this list's own placeholder key — so the assertion below is unchanged.
    // What DID change is that the kit DEBOUNCES (`SEARCH_DEBOUNCE_MS`, 300ms)
    // where the hand-rolled box filtered on every keystroke, so the narrowing
    // is awaited rather than asserted synchronously. Without the `waitFor`
    // this test fails on timing and says nothing about searching.
    const search = screen.getByLabelText(t("settings.routes.searchPlaceholder"));
    expect(search).toBeInTheDocument();
    await user.type(search, "RT-002");
    await waitFor(() => {
      expect(screen.queryByText("RT-001")).not.toBeInTheDocument();
    });
    expect(screen.getByText("RT-002")).toBeInTheDocument();
  });

  it("rule 16: the picker carries a pagination footer with its five page sizes", async () => {
    const user = userEvent.setup();
    renderCycleWizard([route("r1", "RT-001")]);
    await toStepTwo(user);
    expect(screen.getByText(t("table.pager.pageSize"))).toBeInTheDocument();
    expect(screen.getByLabelText(t("table.pager.next"))).toBeInTheDocument();
  });
});

describe("DEF-582 — the wizard's empty state still says what is missing", () => {
  /**
   * ⚠ **DEF-582's ORIGINAL ASSERTION IS GONE ON PURPOSE, AND THIS IS THE
   * WEAKENING NAMED RATHER THAN SLIPPED THROUGH.** It read the empty `<td>`'s
   * own class list for `text-center` and `py-6`, because the empty state used
   * to be a `colSpan` cell this screen drew itself. `DEF-TEN-5706` moved the
   * picker onto `DataTable`, and the kit renders `StateFrame`'s `EmptyList`
   * instead — there is no `<td>` to read, and there should not be: B14 rule 36
   * puts one visual decision in one component, and centring an empty state is
   * exactly such a decision. `src/components/StateFrame*` owns it now and is
   * where a regression in it would go red.
   *
   * What this file can still prove, and what DEF-582 was actually FOR, is that
   * the empty state SPEAKS — B14 rule 17: what is missing, and the action that
   * fills it. A silent empty table is the defect the centring was cosmetic to.
   */
  it("an empty picker names what is missing and what to do", async () => {
    const user = userEvent.setup();
    renderCycleWizard([]);
    await toStepTwo(user);
    expect(screen.getByText(t("settings.cycles.wizard.noRoutesTitle"))).toBeInTheDocument();
    expect(screen.getByText(t("settings.cycles.wizard.noRoutesBody"))).toBeInTheDocument();
  });
});

describe("DEF-224 — the counts on this surface have plural forms", () => {
  it("one route reads 'route', two read 'routes' — in the picker's own counter", async () => {
    const user = userEvent.setup();
    renderCycleWizard([route("r1", "RT-001"), route("r2", "RT-002")]);
    await toStepTwo(user);
    await user.click(screen.getByLabelText(t("settings.cycles.wizard.selectRoute", { route: "RT-001" })));
    expect(
      screen.getByText(t(pluralKey("settings.cycles.wizard.routesSelected", 1), { count: 1 })),
    ).toBeInTheDocument();
    await user.click(screen.getByLabelText(t("settings.cycles.wizard.selectRoute", { route: "RT-002" })));
    expect(
      screen.getByText(t(pluralKey("settings.cycles.wizard.routesSelected", 2), { count: 2 })),
    ).toBeInTheDocument();
  });

  it("and the singular is a DIFFERENT sentence — the bug was '1 routes selected'", () => {
    expect(t(pluralKey("settings.cycles.wizard.routesSelected", 1), { count: 1 })).toBe(
      "1 route selected",
    );
    expect(t(pluralKey("settings.cycles.wizard.routesSelected", 2), { count: 2 })).toBe(
      "2 routes selected",
    );
    expect(t(pluralKey("settings.routes.wizard.selectedCount", 1), { count: 1 })).not.toContain(
      "selecteds",
    );
    expect(t(pluralKey("settings.routes.detail.unitsOnStop", 1), { count: 1 })).toBe("1 unit");
    expect(t(pluralKey("settings.routes.detail.unitsOnStop", 4), { count: 4 })).toBe("4 units");
  });
});
