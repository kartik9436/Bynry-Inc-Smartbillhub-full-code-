// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-8834 — a penalty priced as a FLAT amount (the seeded NSF
//          $30.00, TAMPER $250.00) opened on View details and on Edit as a blank
//          Percent and Minimum, and saving the Edit turned the $30.00 into a
//          0.25 % percent rule (found by 10-scripts/charge_codes_walk33.mjs,
//          2026-10-01, PostgreSQL 16 + Chromium 1440).
// Red first (law 7): on the tip before the fix, case 1 found no "Amount 1"
//          box (the step drew Percent / Minimum) and case 2 found no $30.00 on
//          the Prices tab.
// What would pass wrongly: a fix that showed the amount but still posted
//          amount_rule percent_with_minimum — case 1 asserts the PATCH body.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { ChargeRow, MyPermissions, TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { ChargeCodeDetailPage } from "./ChargeCodeDetailPage";
import { ChargeCodeWizard } from "./ChargeCodeWizard";

afterEach(cleanup);

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

const NSF = {
  id: "chg-nsf",
  code: "NSF",
  name: "Returned payment (NSF) fee",
  charge_type: "penalty",
  service: null,
  is_base: false,
  kind: "plan",
  amount_rule: "flat",
  amount: "30.0000",
  amount_display: "30.00",
  percent: null,
  percent_display: null,
  min_amount: null,
  min_amount_display: null,
  max_amount: null,
  max_amount_display: null,
  taxable_default: false,
  auto_apply: false,
  waivable: false,
  separate_line: true,
  applies_to_customer_classes: [],
  status: "active",
  gl_account_id: "gl-4210",
  gl_account_code: "4210",
  gl_account_name: "NSF & other fee revenue",
  used_by_plans: 3,
  used_by_invoice_lines: 0,
  size_amounts: [],
  class_terms: [],
  prices: [
    {
      id: "p-nsf",
      size_class: "All sizes",
      customer_class: null,
      amount: "30.0000",
      amount_display: "30.00",
      currency: "USD",
      effective_from: "2000-01-01",
      effective_to: null,
      killed: false,
      version: 1,
    },
  ],
  price_range: { low: "30.0000", high: "30.0000", low_display: "30.00", high_display: "30.00", priced_by: "flat", rows: 1 },
  usage: { bills: 0, lines: 0, revenue: "0.0000", revenue_display: "0.00" },
  versions: [],
} as unknown as ChargeRow;

function stub() {
  const patches: { path: string; body: Record<string, unknown> }[] = [];
  const ok = <T,>(data: T) => ({ status: 200, data, etag: null, notModified: false });
  const client = {
    get: vi.fn(async (path: string) => {
      if (path.startsWith("/lookups/")) return ok({ count: 0, results: [] });
      if (path.endsWith("/plans")) return ok({ count: 0, next: null, previous: null, results: [] });
      if (path === "/charges/chg-nsf") return ok(NSF);
      throw new Error(`no stub for ${path}`);
    }),
    request: vi.fn(async (path: string, options: { method: string; body: Record<string, unknown> }) => {
      patches.push({ path, body: options.body });
      return ok({ ...NSF });
    }),
    post: vi.fn(),
  } as unknown as ApiClient;
  return { client, patches };
}

function mount(element: JSX.Element, url: string, pattern: string) {
  const user = userEvent.setup();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(queryKeys.myPermissions, {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: "plans_rates", label: "Plans & Rates", access: "Full" }],
  } as unknown as MyPermissions);
  qc.setQueryData(queryKeys.tenantServices, [
    { service: "water", name: "Water", enabled: true, primary_uom: null, alt_uom: null } as unknown as TenantServiceRow,
  ]);
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

describe("DEF-RAT-8834 · a FLAT penalty (NSF $30.00) stays a flat amount", () => {
  it("Edit shows its $30.00 as one amount and an amount change posts a flat price, never a percent", async () => {
    const s = stub();
    const user = mount(
      <ChargeCodeWizard client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-nsf/edit`,
      "/:tenant/plans-rates/charge-codes/:definitionId/edit",
    );
    await user.click(await screen.findByRole("button", { name: t("wizard.continue") }));
    const box = (await screen.findByLabelText(/^Amount 1/)) as HTMLInputElement;
    expect(box.value).toBe("30.00");
    expect(document.querySelector('[data-cell="percent-0"]')).toBeNull();
    await user.clear(box);
    await user.type(box, "35.00");
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    fireEvent.change(screen.getByLabelText(/^Effective from/), { target: { value: "2026-11-01" } });
    await user.type(screen.getByLabelText(/^Reason/), "Board approved NSF review");
    await user.click(screen.getByRole("button", { name: t("rating.chargeCode.saveChange") }));
    await waitFor(() => expect(s.patches).toHaveLength(1));
    expect(s.patches[0].body).toMatchObject({ amount_rule: "flat", amount: "35.00", percent: null, effective_from: "2026-11-01" });
  });

  it("View details › Prices shows $30.00, not a blank percent and minimum", async () => {
    const s = stub();
    mount(
      <ChargeCodeDetailPage client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-nsf?tab=prices`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => expect(document.querySelector('[data-array="charge-prices"]')).not.toBeNull());
    const table = document.querySelector('[data-array="charge-prices"]') as HTMLElement;
    expect(table.textContent).toContain("$30.00");
  });
});
