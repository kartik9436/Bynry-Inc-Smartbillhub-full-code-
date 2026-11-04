// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Ruling:  PO 2026-09-28, verbatim: *"the Units "Missing services" block —
//          filter or leave it. - filter"*. Decision log, same date.
// Defect:  DEF-MET-6796 — units holding fewer service points than their
//          address offers; **the shortfall was INVISIBLE**.
// Rules:   BR-MET-119 as amended 2026-09-25 · BR-BIL-300 · NFR-3 (the server
//          pages it) · NFR-5 (no cap) · B14 rule 12 (filters are chips) ·
//          rule 31 (no database id on screen) · rule 33
// Screens: S15 · PRM-01U the units list
// ───────────────────────────────────────────────────────
// **WHAT THIS FILE REPLACES.** `UnitServiceGaps.dom.test.tsx` tested a panel
// that no longer exists. Its cases asserted that the panel COUNTED and that it
// drew nothing at zero; neither question survives, because the panel is gone.
//
// ⚠ **THE FOUR THINGS THE PO WAS SHOWN AS THE REASON FOR THE CHANGE ARE THE
// FOUR THINGS ASSERTED HERE**, because those are what *done* means: the filter
// combines with the SEARCH, it combines with the OTHER filters, it pages with
// the LIST rather than a second pager, and the SELECTION reaches the filtered
// set so a bulk action can act on it.
//
// ⚠ **THE FALSE PASS EACH CASE IS WRITTEN AGAINST, stated rather than implied
// (hard-won law 7 habit 2).**
//   * A chip that rendered from the SCREEN's own state rather than from the
//     server's figure would pass any assertion that only ever looks at it with
//     the filter ON. So the count is asserted with the filter OFF, which is
//     the state `DEF-MET-6796` is about.
//   * A screen that drew the chip and never put `f.missing_services` on the
//     wire would still show a filtered-looking list, because the fixture
//     returns whatever it is given. So the REQUEST is read, not the table.
//   * `waitFor` on the table alone succeeds on its first tick, against the
//     render from BEFORE the request — so every case here waits on the
//     matching REQUEST having been made and then asserts.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { MyPermissions, UnitRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { PREMISES_PERMISSION } from "./meteringShared";
import { UnitsListPage } from "./UnitsListPage";

const TENANT = "brazosbend";

/** A unit at an address offering electric + water. `over` decides whether it
 *  is short: `metered_services` is what it HOLDS and `missing_services` is the
 *  difference the SERVER derived — never subtracted again on the client. */
function unit(over: Partial<UnitRow> = {}): UnitRow {
  return {
    id: "01a0dd9e-0000-7000-8000-000000000001",
    unit_no: "U-01145",
    premises_id: "01a0dd9e-0000-7000-8000-0000000000aa",
    premise_no: "P-00080",
    premise_address: "412 Cypress Row",
    label: "2",
    unit_type: "residential",
    floor_label: null,
    square_feet: null,
    rate_plan_id: null,
    plan_effective_from: null,
    plan_locked: false,
    vacant_standby_auto: false,
    is_common_area: false,
    services: ["electric", "water"],
    lat: null,
    lng: null,
    point: { lat: null, lng: null, source: "none" },
    active: true,
    metered_services: ["water"],
    missing_services: ["electric"],
    meters: [],
    occupancy: "occupied",
    occupant: "Dana Whitfield",
    account_no: "A-90001",
    status: "active",
    sub_metered: false,
    // `DEF-MET-10164` — the row carries its created stamp now; without it the
    // Created and Age cells draw dashes too, and "the dash for nothing
    // missing" stops being the only dash on the row.
    created_at: "2024-01-15T06:00:00+00:00",
    ...over,
  };
}

function fullAccess(): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  };
}

/**
 * ⚠ **THE TOOLBAR TOGGLE, NOT THE APPLIED CHIP'S ✕.** Once the filter is on,
 * `FilterBar` draws a removable chip whose ✕ is named *Remove the Missing
 * services filter* — so `/Missing services/` matches TWO buttons and a bare
 * `getByRole` throws. The toggle is the one carrying the COUNT.
 */
function toggle() {
  return screen.findByRole("button", { name: /Missing services\s*\d+ units/ });
}

/** The `+ Filter ▾` disclosure — `table.filters.open` is *"+ Filter"*, so the
 *  text node is not the bare word. */
function filterPanel() {
  return screen.findByText(/\+ Filter/);
}

/** Every `GET /units` this screen makes, in order — the wire, not the table. */
function unitCalls(urls: string[]): string[] {
  return urls.filter((url) => /\/units(\?|$)/.test(url.split("#")[0]));
}

function mount(opts: { gapCount: number; rows?: UnitRow[]; total?: number }) {
  const urls: string[] = [];
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, fullAccess());
  const fetchImpl = async (input: RequestInfo | URL) => {
    const url = String(input);
    urls.push(url);
    // `/settings/services` answers a bare ARRAY and everything else a page. A
    // mock that returns one shape for both crashes the screen inside React and
    // reads like a component bug.
    const body = url.includes("/settings/services")
      ? []
      : url.includes("/permissions")
        ? fullAccess()
        : /\/units(\?|$)/.test(url)
          ? {
              results: opts.rows ?? [unit()],
              count: opts.total ?? (opts.rows ?? [unit()]).length,
              next: null,
              previous: null,
              // ⚠ THE FIGURE THE TOOLBAR DRAWS, SERVED BY THE LIST ITSELF —
              // on EVERY read, engaged or not. That is the deliverable.
              service_gap_count: opts.gapCount,
            }
          : { results: [], count: 0 };
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  const client = createApiClient({ tenant: TENANT, fetchImpl });
  // ⚠ MOUNTED UNDER THE REAL PATH PATTERN (hard-won law 2). A bare
  // `MemoryRouter` leaves `useParams().tenant` undefined and every address the
  // page builds comes out `//premises/…`.
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/premises/units`]}>
          <Routes>
            <Route
              path="/:tenant/premises/units"
              element={
                <UnitsListPage client={client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { urls };
}

afterEach(cleanup);

describe("the Missing services filter — PO ruling 2026-09-28", () => {
  it("shows the count with the filter OFF, which is the whole point", async () => {
    const { urls } = mount({ gapCount: 60, total: 132 });
    // The chip states the number BEFORE anything is switched on. A clerk who
    // never opens `+ Filter ▾` still sees that 60 units are short — which is
    // the failure `DEF-MET-6796` was filed about.
    const chip = await toggle();
    expect(chip).toHaveAttribute("aria-pressed", "false");
    expect(chip).toHaveTextContent("60 units");
    // …and nothing was asked for the gap separately. One read, one envelope.
    await waitFor(() => expect(unitCalls(urls).length).toBeGreaterThan(0));
    expect(urls.some((url) => url.includes("service-gaps"))).toBe(false);
    expect(unitCalls(urls)[0]).not.toContain("missing_services");
  });

  it("puts f.missing_services on the wire when it is pressed", async () => {
    const user = userEvent.setup();
    const { urls } = mount({ gapCount: 60, total: 132 });
    await user.click(await toggle());
    // ⚠ WAIT ON THE REQUEST, NOT ON THE TABLE. The table is already rendered
    // from the first read, so a `waitFor` over it succeeds on its first tick
    // and would pass with the filter never reaching the server.
    await waitFor(() =>
      expect(unitCalls(urls).some((url) => url.includes("f.missing_services=yes"))).toBe(true),
    );
    expect(await toggle()).toHaveAttribute("aria-pressed", "true");
  });

  it("combines with the search, in ONE request", async () => {
    const user = userEvent.setup();
    const { urls } = mount({ gapCount: 60, total: 132 });
    await user.click(await toggle());
    await user.type(await screen.findByRole("searchbox"), "Willow Bend");
    // The pair a clerk actually wants: *short* AND *on this street*, which the
    // deleted block could not express at all.
    await waitFor(() => {
      const both = unitCalls(urls).find(
        (url) => url.includes("f.missing_services=yes") && url.includes("Willow"),
      );
      expect(both).toBeDefined();
    });
  });

  it("combines with one of the four filters that were already there", async () => {
    const user = userEvent.setup();
    const { urls } = mount({ gapCount: 60, total: 132 });
    await user.click(await toggle());
    // `plan` — BR-MET-100's unplanned chip, one of the four.
    await user.click(await filterPanel());
    await user.click(await screen.findByRole("checkbox", { name: "No plan" }));
    await waitFor(() =>
      expect(
        unitCalls(urls).some(
          (url) => url.includes("f.missing_services=yes") && url.includes("f.plan=unplanned"),
        ),
      ).toBe(true),
    );
  });

  it("pages with the LIST and grows no pager of its own", async () => {
    const user = userEvent.setup();
    const { urls } = mount({ gapCount: 60, total: 132 });
    await user.click(await toggle());
    await waitFor(() =>
      expect(unitCalls(urls).some((url) => url.includes("f.missing_services=yes"))).toBe(true),
    );
    // ONE pagination footer on the screen, and it carries the filter.
    expect(screen.getAllByRole("button", { name: /Next page/i })).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: /Next page/i }));
    await waitFor(() =>
      expect(
        unitCalls(urls).some(
          (url) => url.includes("f.missing_services=yes") && url.includes("page=2"),
        ),
      ).toBe(true),
    );
  });

  it("lets the bulk bar reach the filtered set — the PO's strongest reason", async () => {
    const user = userEvent.setup();
    mount({ gapCount: 60, total: 132 });
    await user.click(await toggle());
    // `Select all {n}` states the SERVER's total for the filtered set, and the
    // gap is a thing to FIX — so the units that are short must be selectable
    // together. In the deleted block they were the one set in the product that
    // could not be.
    // ⚠ `CR-176-BRC10` (PO 2026-10-09): the bar shows only once a unit is
    // ticked, so the first tick is what brings `Select all` on screen.
    await screen.findByText("U-01145");
    const rowBox = document.querySelector("table tbody input[type=checkbox]") as HTMLInputElement;
    await user.click(rowBox);
    const selectAll = await screen.findByRole("button", { name: /Select all 132/ });
    expect(selectAll).toBeEnabled();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Assign plan/i })).toBeEnabled(),
    );
  });

  it("draws Missing on the row, and a dash when nothing is missing", async () => {
    mount({
      gapCount: 1,
      rows: [
        unit(),
        unit({
          id: "01a0dd9e-0000-7000-8000-000000000002",
          unit_no: "U-01146",
          label: "3",
          metered_services: ["electric", "water"],
          missing_services: [],
        }),
      ],
      total: 2,
    });
    await screen.findByText("U-01145");
    // The short unit names what it lacks; the whole one draws a quiet dash and
    // must NOT read "No services" — that is the sentence for an address
    // offering nothing, and it is the opposite of the truth here.
    expect(await screen.findByText("—")).toBeInTheDocument();
    expect(screen.queryByText("No services")).not.toBeInTheDocument();
  });

  it("puts no database id on screen (B14 rule 31)", async () => {
    const { urls } = mount({ gapCount: 60, total: 132 });
    await waitFor(() => expect(unitCalls(urls).length).toBeGreaterThan(0));
    await screen.findByText("U-01145");
    const text = document.body.textContent ?? "";
    expect(text).not.toContain("01a0dd9e-0000-7000-8000-000000000001");
    expect(text).not.toContain("01a0dd9e-0000-7000-8000-0000000000aa");
  });

  it("keeps the chip while the filter is ON even once nothing is short", async () => {
    const user = userEvent.setup();
    // Rows, but NOTHING short — an empty list would replace the whole toolbar
    // with the empty state and there would be no `+ Filter ▾` to press.
    mount({
      gapCount: 0,
      rows: [unit({ metered_services: ["electric", "water"], missing_services: [] })],
      total: 1,
    });
    await screen.findByText("U-01145");
    // Nothing is short, so the chip is absent — a control over nothing is
    // exactly what BR-SHL-010 refuses.
    expect(screen.queryByRole("button", { name: /Missing services/ })).toBeNull();
    // …but a clerk who fixes the LAST short unit with the filter still applied
    // must not be left behind a vanished door (hard-won law 2's mirror). The
    // panel is where that state is reachable, so the chip returns with it.
    await user.click(await filterPanel());
    await user.click(await screen.findByRole("checkbox", { name: "Yes" }));
    // The chip is back, engaged, with `0 units` beside it — a clerk who fixed
    // the last short unit can still untick what they switched on.
    const back = await screen.findByRole("button", { name: /Missing services\s*0 units/ });
    expect(back).toHaveAttribute("aria-pressed", "true");
  });
});
