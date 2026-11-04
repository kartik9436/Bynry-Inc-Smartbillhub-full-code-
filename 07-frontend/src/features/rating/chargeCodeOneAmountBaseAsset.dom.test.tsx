// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-8836 — PO, on Edit BASE-BAT ($5.00 → $6.00 from 11/01/2026),
//          Review step: "why asset - is blank on this screen?". A base code
//          priced as ONE amount on a service that HAS sizes drew Asset "—" on
//          step 2, on Review and on View details › Prices. The row is the
//          code's *All sizes* row (PO 2026-10-01, "Flat amount as an All sizes
//          row") and the asset is the service's (battery: Behind-the-meter
//          battery). Sewer, ruled to have no sizes, keeps "—" (case 3).
// Red first (law 7): on the tip before the fix, cases 1 and 2 found "—" where
//          the asset word belongs, and no "All sizes".
// What would pass wrongly: a fix that named an asset for EVERY base — case 3
//          keeps sewer at "—".
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { ChargeRow, LookupEntry, MyPermissions, TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { ChargeCodeDetailPage } from "./ChargeCodeDetailPage";
import { ChargeCodeWizard } from "./ChargeCodeWizard";

afterEach(cleanup);

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);
const ASSET = t("rating.chargeCode.asset.battery");
const ALL_SIZES = t("rating.rs.allSizes");

const SIZES: LookupEntry[] = ["BAT-5", "BAT-10", "BAT-15"].map(
  (code) =>
    ({ id: code, code, name: code, active: true, is_system: true, used_by: 0, service: { id: "battery", code: "battery" } }) as unknown as LookupEntry,
);

function base(id: string, code: string, service: string, amount: string): ChargeRow {
  return {
    id,
    code,
    name: `${code} base`,
    charge_type: "recurring",
    service,
    is_base: true,
    kind: "base",
    amount_rule: "flat",
    amount: `${amount}00`,
    amount_display: amount,
    percent: null,
    percent_display: null,
    min_amount: null,
    min_amount_display: null,
    max_amount: null,
    max_amount_display: null,
    taxable_default: false,
    auto_apply: true,
    waivable: false,
    separate_line: true,
    applies_to_customer_classes: [],
    status: "active",
    gl_account_id: null,
    gl_account_code: null,
    gl_account_name: null,
    used_by_plans: 3,
    used_by_invoice_lines: 0,
    size_amounts: [],
    class_terms: [],
    prices: [
      {
        id: `p-${id}`,
        size_class: "All sizes",
        customer_class: null,
        amount: `${amount}00`,
        amount_display: amount,
        currency: "USD",
        effective_from: "2000-01-01",
        effective_to: null,
        killed: false,
        version: 1,
      },
    ],
    price_range: null,
    usage: { bills: 0, lines: 0, revenue: "0.0000", revenue_display: "0.00" },
    versions: [],
  } as unknown as ChargeRow;
}

const BAT = base("chg-bat", "BASE-BAT", "battery", "5.00");
const SEWER = base("chg-sewer", "BASE-S", "sewer", "9.00");

function stub(rows: ChargeRow[]) {
  const ok = <T,>(data: T) => ({ status: 200, data, etag: null, notModified: false });
  const client = {
    get: vi.fn(async (path: string) => {
      if (path.startsWith("/lookups/service_size_classes")) return ok({ count: SIZES.length, results: SIZES });
      if (path.startsWith("/lookups/")) return ok({ count: 0, results: [] });
      if (path.endsWith("/plans")) return ok({ count: 0, next: null, previous: null, results: [] });
      const row = rows.find((one) => path === `/charges/${one.id}`);
      if (row === undefined) throw new Error(`no stub for ${path}`);
      return ok(row);
    }),
    request: vi.fn(async () => ok(rows[0])),
    post: vi.fn(),
  } as unknown as ApiClient;
  return { client };
}

function mount(element: JSX.Element, url: string, pattern: string) {
  const user = userEvent.setup();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(queryKeys.myPermissions, {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: "plans_rates", label: "Plans & Rates", access: "Full" }],
  } as unknown as MyPermissions);
  qc.setQueryData(
    queryKeys.tenantServices,
    ["battery", "sewer"].map(
      (service) => ({ service, name: service, enabled: true, primary_uom: null, alt_uom: null }) as unknown as TenantServiceRow,
    ),
  );
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[url]}>
          <Routes>
            <Route path={pattern} element={element} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return user;
}

const cellText = (name: string) =>
  [...document.querySelectorAll(`[data-cell="${name}"], [data-static="${name}"]`)].map((el) => el.textContent ?? "");

describe("DEF-RAT-8836 · a one-amount base on a service with sizes names its asset and reads All sizes", () => {
  it("Edit BASE-BAT: step 2 and Review show Behind-the-meter battery and All sizes, never a blank asset", async () => {
    const s = stub([BAT]);
    const user = mount(
      <ChargeCodeWizard client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-bat/edit`,
      "/:tenant/plans-rates/charge-codes/:definitionId/edit",
    );
    await user.click(await screen.findByRole("button", { name: t("wizard.continue") }));
    await waitFor(() => expect(document.querySelector('[data-array="charge-price-rows"]')).not.toBeNull());
    const step2 = (document.querySelector('[data-array="charge-price-rows"]') as HTMLElement).textContent ?? "";
    expect(step2).toContain(ASSET);
    expect(step2).toContain(ALL_SIZES);
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).not.toBeNull());
    const review = (document.querySelector('[data-step="review"]') as HTMLElement).textContent ?? "";
    expect(review).toContain(ASSET);
    expect(review).toContain(ALL_SIZES);
    expect(cellText("asset")).not.toContain("—");
  });

  it("View details › Prices of BASE-BAT names the asset and All sizes", async () => {
    const s = stub([BAT]);
    mount(
      <ChargeCodeDetailPage client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-bat?tab=prices`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => expect(document.querySelector('[data-array="charge-prices"]')).not.toBeNull());
    await waitFor(() => {
      const table = (document.querySelector('[data-array="charge-prices"]') as HTMLElement).textContent ?? "";
      expect(table).toContain(ASSET);
      expect(table).toContain(ALL_SIZES);
      expect(table).toContain("$5.00");
    });
  });

  it("sewer, ruled to have no sizes, keeps '—' and no size", async () => {
    const s = stub([SEWER]);
    mount(
      <ChargeCodeDetailPage client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-sewer?tab=prices`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => expect(document.querySelector('[data-array="charge-prices"]')).not.toBeNull());
    const table = (document.querySelector('[data-array="charge-prices"]') as HTMLElement).textContent ?? "";
    expect(table).toContain("—");
    expect(table).not.toContain(ALL_SIZES);
    expect(table).toContain("$9.00");
  });
});
