// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Plan:    15-bulk-bill-run-build-plan.md T5 — "Door test: Bills → Run opens the
//          new screen, the old wizard is unreachable" (F2, changes row 9)
// Story:   US-BIL-036 TC-1
// Rules:   hard-won law 2 and its mirror (`DEF-CWP-3925`): the destination is
//          asserted BY ADDRESS and by the screen it opens, through the product's
//          own route table (`APP_ROUTES`), mounted under the real paths.
// Proof:   red first — with `App.tsx`'s `billing/run` route pointed back at a
//          different element this file failed on `theBulkRunPage()` being null
//          (recorded in the commit that added it).
// ───────────────────────────────────────────────────────
/**
 * THE DOORS TO THE BILL RUN, WALKED THROUGH THE REAL ROUTER.
 *
 * Found by grep on 2026-09-30 (every reference to `BILL_RUN_ROUTE` / `billRunPath`
 * outside the page): the Bills page's `Run` tab (`BILLING_TABS` id `run`), the
 * Bills page's `Run bills` action and empty-state CTA (`openRunWizard`), the
 * Dashboard's `ButtonLink`, `PastBillingRunsPanel`'s run links (`billRunPath`),
 * and a typed address. All build `/billing/run[?run=…]`, so asserting that
 * ADDRESS opens the redrawn page covers every one of them; the tab is pressed
 * here as a clerk would.
 *
 * The retired four-step shell answered at `/billing/run/:step`; that address
 * must open neither the page nor any bill-run screen now.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { APP_ROUTES } from "@/App";
import type { MyPermissions, SessionUser, ShellDisplay } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { resolveScreen } from "@/routing/screenIds";

import { BILLING_ROUTE } from "../billingShared";
import { billRunPath } from "../billRunShared";

const TENANT = "brazosbend";
const PAGE = `/${TENANT}/billing/run`;

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

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify({ count: 0, next: null, previous: null, results: [] }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
    ),
  );
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function open(address: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
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

function theBulkRunPage(): HTMLElement | null {
  return document.querySelector<HTMLElement>('[data-screen="bulk-bill-run"]');
}

// BULK-CHG-9 (one bill-run screen; the replaced wizard unreachable) · BULK-CHG-27 (plan T5)
describe("T5 — every door to the bill run opens the redrawn page", () => {
  it("Bills › Run bills, pressed, lands on /:tenant/billing/run and opens the four-step page", async () => {
    const router = open(`/${TENANT}${BILLING_ROUTE}`);
    const tab = await screen.findByRole("tab", { name: "Run bills" });
    expect(theBulkRunPage()).toBeNull();
    await act(async () => {
      fireEvent.click(tab);
    });
    expect(router.state.location.pathname).toBe(PAGE);
    expect(resolveScreen(router.state.location.pathname, "").route?.path).toBe("/:tenant/billing/run");
    expect(resolveScreen(router.state.location.pathname, "").a1).toBe("S31");
    await screen.findAllByText("Start checking");
    const page = theBulkRunPage();
    expect(page).not.toBeNull();
    expect(document.querySelectorAll("[data-wizard-step]")).toHaveLength(4);
    // The old six-step wizard's own marks are gone.
    expect(document.querySelector("[data-brun-s3]")).toBeNull();
  });

  it("a run link (`billRunPath`) re-opens the SAME page with the run", async () => {
    const router = open(`/${TENANT}${billRunPath("run-1")}`);
    expect(router.state.location.pathname).toBe(PAGE);
    expect(router.state.location.search).toBe("?run=run-1");
    await act(async () => {});
    expect(theBulkRunPage()).not.toBeNull();
  });

  it("the retired four-step address opens no bill-run screen", async () => {
    open(`${PAGE}/scope`);
    await act(async () => {});
    expect(theBulkRunPage()).toBeNull();
    expect(resolveScreen(`${PAGE}/scope`, "").route?.path).not.toBe("/:tenant/billing/run/:step");
  });
});
