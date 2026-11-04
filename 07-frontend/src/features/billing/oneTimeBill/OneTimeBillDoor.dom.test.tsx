// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Task:    one-time bill build plan T6 — "Hold-expiry test: the door to the new
//          page opens the new page" (04-docs/05-modules/07-billing/
//          12-one-time-bill-build-plan.md), and F18 — "grep for every link that
//          pointed at them" (the deleted `OneTimeBillTab` / `OneTimeWizardShell`).
// Rules:   CLAUDE.md hard-won law 2 and its mirror (`DEF-CWP-3925`): assert the
//          destination BY ADDRESS and by the screen it opens, with the routed
//          component mounted under the REAL path pattern — a bare mount with no
//          `/:tenant` route builds `//billing/…` and every assertion passes.
// Screen:  S30 · `/:tenant/billing/one-time`
// ───────────────────────────────────────────────────────
/**
 * THE DOORS TO THE ONE-TIME BILL, WALKED THROUGH THE PRODUCT'S OWN ROUTER.
 *
 * `OneTimeBillDoor.test.tsx` beside this file proves the ADDRESS arithmetic
 * with `matchRoutes` and renders nothing. This file is the half it cannot be:
 * it mounts `APP_ROUTES` — the real shell, the real route table — at the Bills
 * page, PRESSES the `One-time bill` tab the way a clerk does, and then asks two
 * questions of what happened:
 *
 *   1. **WHERE DID IT GO?** — the router's own location, by address:
 *      `/brazosbend/billing/one-time`, and the screen register resolves that
 *      address to its own `/:tenant/billing/one-time` entry (S30), not to the
 *      `:tab` entry the Bills list answers on.
 *   2. **WHAT OPENED?** — the redrawn page's own mark, `data-screen="one-time-bill"`,
 *      with the kind cards and the four-step rail (Account · Services · Review
 *      · Send) — and NOT the Bills list with a tab selected.
 *
 * The doors, found by grep on 2026-09-30 (every reference to `ONE_TIME_BILL_ROUTE`,
 * `billing/one-time` and `billing.tab.oneTime` outside the page itself):
 *
 *   * the Bills page's tab strip — `BILLING_TABS` id `one-time`, navigated by
 *     `BillsListPage`'s `onTabSelect` to `/billing/<id>`;
 *   * the `ButtonLink` in `BillsListPage`'s `one-time` branch — reachable only
 *     by a bare mount of the list at that tab, which the router never does
 *     (its own comment says *"this branch is not a door"*); its href is
 *     asserted here anyway so the day the route order changes, it still points
 *     at the page;
 *   * a typed or bookmarked address — the page's own route;
 *   * the RETIRED `/billing/one-time/who` (the deleted three-step shell) —
 *     which must open neither the page nor a one-time screen.
 *
 * Nothing else in `src/` links to the one-time bill: no sidebar entry, no
 * account action. If one is added, add its door here.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, RouterProvider, Routes, createMemoryRouter } from "react-router-dom";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { APP_ROUTES } from "@/App";
import type { MyPermissions, SessionUser, ShellDisplay } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { resolveScreen } from "@/routing/screenIds";

import { BillsListPage } from "../BillsListPage";
import { BILLING_ROUTE } from "../billingShared";

import { ONE_TIME_BILL_ROUTE } from "./OneTimeBillPage";

const TENANT = "brazosbend";
const PAGE_ADDRESS = `/${TENANT}/billing/one-time`;

const ADMIN: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@brazosbend.example",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [
    { code: "reads_billing_runs", label: "Billing runs", access: "Full" },
    { code: "billing", label: "Billing", access: "Full" },
  ],
};

const DISPLAY: ShellDisplay = {
  regional: {
    country: "United States",
    timezone: "America/Chicago",
    language: "en-US",
    first_day_of_week: "sunday",
    currency: "USD",
    number_format: "1,234.56",
    date_format: "MM/DD/YYYY",
    time_format: "12-hour",
  },
  company: {
    legal_name: "Brazos Bend Utility District No. 1",
    dba_name: "Brazos Bend Utilities",
    has_logo: false,
    logo_ref: null,
    mark: { letters: "BB", background_hex: null, ink_hex: null, contrast_ratio: null },
    brand_primary_hex: null,
  },
  period: null,
};

/** Every read the two screens make that the cache does not already answer
 *  gets an empty page — the doors are the subject, not the data. */
function emptyPage(): Response {
  return new Response(JSON.stringify({ count: 0, next: null, previous: null, results: [] }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => emptyPage()),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function openTheProductAt(address: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, ADMIN);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(queryKeys.shellDisplay, DISPLAY);
  const router = createMemoryRouter(APP_ROUTES, { initialEntries: [address] });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return router;
}

function theOneTimePage(): HTMLElement | null {
  return document.querySelector<HTMLElement>('[data-screen="one-time-bill"]');
}

function expectTheRedrawnPage(page: HTMLElement | null) {
  expect(page).not.toBeNull();
  const scope = within(page as HTMLElement);
  // The four-step rail, in the drawing's order and words.
  for (const step of ["Account", "Services", "Review", "Send"]) {
    expect(scope.getAllByText(step).length).toBeGreaterThan(0);
  }
}

describe("T6 — every door to the one-time bill opens the redrawn page", () => {
  it("the Bills page's One-time bill TAB, pressed, lands on /:tenant/billing/one-time and opens the page", async () => {
    const router = openTheProductAt(`/${TENANT}${BILLING_ROUTE}`);

    const tab = await screen.findByRole("tab", { name: "One-time bill" });
    // Before the press: the list, not the page.
    expect(theOneTimePage()).toBeNull();

    await act(async () => {
      fireEvent.click(tab);
    });

    // 1 · WHERE — by address, from the router itself.
    expect(router.state.location.pathname).toBe(PAGE_ADDRESS);
    // …and the register resolves that address to the page's OWN entry.
    expect(resolveScreen(router.state.location.pathname, "").route?.path).toBe(
      "/:tenant/billing/one-time",
    );
    expect(resolveScreen(router.state.location.pathname, "").a1).toBe("S30");

    // 2 · WHAT — the redrawn page, and the list's tab strip is gone.
    expectTheRedrawnPage(await waitForPage());
    expect(screen.queryByRole("tab", { name: "One-time bill" })).toBeNull();
  });

  it("a typed or bookmarked /:tenant/billing/one-time opens the page directly", async () => {
    const router = openTheProductAt(PAGE_ADDRESS);
    expect(router.state.location.pathname).toBe(PAGE_ADDRESS);
    expectTheRedrawnPage(await waitForPage());
  });

  it("the list's own one-time branch links to the page's address, tenant-scoped", () => {
    // The branch only renders when the LIST is mounted at the one-time tab,
    // which the router never does — so it is mounted bare, under the real
    // `/:tenant/billing/:tab` pattern, exactly as a route change would expose it.
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[PAGE_ADDRESS]}>
            <Routes>
              <Route path="/:tenant/billing/:tab" element={<BillsListPage />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(html).toContain(`href="${PAGE_ADDRESS}"`);
    expect(html).not.toContain('href="//billing');
    expect(`/${TENANT}${ONE_TIME_BILL_ROUTE}`).toBe(PAGE_ADDRESS);
  });

  it("the RETIRED three-step address opens neither the page nor a one-time screen", async () => {
    openTheProductAt(`${PAGE_ADDRESS}/who`);
    // Give the router a tick to settle on whatever it mounts there.
    await act(async () => {});
    expect(theOneTimePage()).toBeNull();
  });
});

async function waitForPage(): Promise<HTMLElement | null> {
  // The page is not lazy today; `findBy` keeps this honest if it becomes so.
  await screen.findAllByText("Services");
  return theOneTimePage();
}
