// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-REP-6345 — the dashboard's AR-aging link opened the trial
//          balance, and its finance to-do would have too: both were built from
//          the bare FINANCE_ROUTE, which CR-060 T10 moved onto the trial
//          balance. The aging detail lives on Revenue & AR (S36); a close is
//          done on Close & export (S42/S43).
// ───────────────────────────────────────────────────────
//
// Asserted by DESTINATION, the way writeOffsHeadDoor.dom.test.tsx does: the
// href is read off the RENDERED anchor and handed to the app's own route table,
// and the case asserts the component that address mounts. A string compare
// would pass on a typo'd path that happens to equal the constant.
//
// ⚠ WHAT WOULD MAKE THIS PASS WRONGLY: mounting the page without the
// `/:tenant/...` pattern, so every tenantPath is `//finance/...` — a
// protocol-relative URL that still contains the segment (hard-won law 2's
// fixture note). The page is mounted under the real pattern, and the href is
// asserted to START with the tenant.
import "@testing-library/jest-dom/vitest";

import type { ReactElement } from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, matchRoutes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { APP_ROUTES } from "@/App";
import { CloseExportPage } from "@/features/ledger/CloseExportPage";
import { GeneralLedgerPage } from "@/features/ledger/GeneralLedgerPage";
import { RevenueArPage } from "@/features/ledger/RevenueArPage";

import { AgingDoor, DASHBOARD_ROUTE, todoHref } from "./DashboardPage";

afterEach(cleanup);

const TENANT = "brazosbend";

/** Which component `App.tsx` mounts at an address. */
function mountedAt(address: string): unknown {
  const matches = matchRoutes(APP_ROUTES, address);
  const route = matches?.at(-1)?.route as { element?: ReactElement } | undefined;
  return route?.element?.type;
}

function renderAgingDoor(): void {
  render(
    <MemoryRouter initialEntries={[`/${TENANT}${DASHBOARD_ROUTE}`]}>
      <Routes>
        <Route
          path={`/:tenant${DASHBOARD_ROUTE}`}
          element={<AgingDoor t={(key) => i18n.t(key)} />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("DEF-REP-6345 · the dashboard's finance doors open the screen they promise", () => {
  it("the AR-aging panel's link opens Revenue & AR, where the aging detail lives", async () => {
    renderAgingDoor();
    const link = await screen.findByRole("link", { name: "Open Finance" });
    const href = link.getAttribute("href") ?? "";
    expect(href.startsWith(`/${TENANT}/`)).toBe(true);
    expect(mountedAt(href)).toBe(RevenueArPage);
    expect(mountedAt(href)).not.toBe(GeneralLedgerPage);
  });

  it("the finance to-do opens Close & export, not the trial balance", () => {
    const href = `/${TENANT}${todoHref("finance")}`;
    expect(mountedAt(href)).toBe(CloseExportPage);
  });
});
