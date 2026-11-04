// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-10739 — a utility could not mark its own NSF fee code: the
//          flag `charges.is_nsf_fee` (rating/0068) was served and accepted, and
//          the charge-code form drew no control for it, so a utility that named
//          its code RETCHK charged no NSF fee on a bounce.
// Ruling:  PO 2026-10-31 P7 = A — Plans & Rates › Charges gets an "NSF fee"
//          tick on the charge form, backed by `is_nsf_fee`.
// Red first (law 7): on the tip, case 1 found no "NSF fee" field on step 1
//          and case 3 found no NSF fee row on View details.
// What would pass wrongly: a field drawn but never posted — case 1 asserts the
//          PATCH body carries `is_nsf_fee: true`; case 2 that a one-time code
//          is never asked (the server refuses the mark on anything else).
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
import { chargePayload, emptyDraft } from "./chargeCodeModel";

afterEach(cleanup);

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

const RETCHK = {
  id: "chg-retchk",
  code: "RETCHK",
  name: "Returned cheque fee",
  charge_type: "penalty",
  service: null,
  is_base: false,
  kind: "plan",
  amount_rule: "flat",
  amount: "35.0000",
  amount_display: "35.00",
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
  is_nsf_fee: false,
  applies_to_customer_classes: [],
  status: "active",
  gl_account_id: "gl-4210",
  gl_account_code: "4210",
  gl_account_name: "NSF & other fee revenue",
  used_by_plans: 1,
  used_by_invoice_lines: 0,
  size_amounts: [],
  class_terms: [],
  prices: [
    {
      id: "p-retchk",
      size_class: "All sizes",
      customer_class: null,
      amount: "35.0000",
      amount_display: "35.00",
      currency: "USD",
      effective_from: "2000-01-01",
      effective_to: null,
      killed: false,
      version: 1,
    },
  ],
  price_range: { low: "35.0000", high: "35.0000", low_display: "35.00", high_display: "35.00", priced_by: "flat", rows: 1 },
  usage: { bills: 0, lines: 0, revenue: "0.0000", revenue_display: "0.00" },
  versions: [],
} as unknown as ChargeRow;

function stub(row: ChargeRow) {
  const patches: { path: string; body: Record<string, unknown> }[] = [];
  const ok = <T,>(data: T) => ({ status: 200, data, etag: null, notModified: false });
  const client = {
    get: vi.fn(async (path: string) => {
      if (path.startsWith("/lookups/")) return ok({ count: 0, results: [] });
      if (path.endsWith("/plans")) return ok({ count: 0, next: null, previous: null, results: [] });
      if (path === `/charges/${row.id}`) return ok(row);
      throw new Error(`no stub for ${path}`);
    }),
    request: vi.fn(async (path: string, options: { method: string; body: Record<string, unknown> }) => {
      patches.push({ path, body: options.body });
      return ok({ ...row });
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

describe("DEF-RAT-10739 · the NSF fee tick on a charge code (PO P7 = A)", () => {
  it("RETCHK, a penalty: Edit offers NSF fee, and Yes is posted", async () => {
    const s = stub(RETCHK);
    const user = mount(
      <ChargeCodeWizard client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-retchk/edit`,
      "/:tenant/plans-rates/charge-codes/:definitionId/edit",
    );
    const field = (await screen.findByLabelText(new RegExp(`^${t("rating.chargeCode.field.nsfFee")}`))) as HTMLSelectElement;
    expect(field.value).toBe("no");
    fireEvent.change(field, { target: { value: "yes" } });
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    await user.click(await screen.findByRole("button", { name: t("wizard.continue") }));
    fireEvent.change(screen.getByLabelText(/^Effective from/), { target: { value: "2026-11-01" } });
    await user.type(screen.getByLabelText(/^Reason/), "RETCHK is our NSF fee");
    await user.click(screen.getByRole("button", { name: t("rating.chargeCode.saveChange") }));
    await waitFor(() => expect(s.patches).toHaveLength(1));
    expect(s.patches[0].body).toMatchObject({ is_nsf_fee: true });
  });

  it("a one-time code is never asked, and never posts the mark", () => {
    const draft = { ...emptyDraft(), kind: "other" as const, chargeType: "one_time", nsfFee: true };
    expect(chargePayload(draft, false).is_nsf_fee).toBe(false);
    expect(chargePayload({ ...draft, chargeType: "penalty" }, false).is_nsf_fee).toBe(true);
  });

  it("View details shows NSF fee: Yes on a marked code", async () => {
    const s = stub({ ...RETCHK, is_nsf_fee: true } as ChargeRow);
    mount(
      <ChargeCodeDetailPage client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-retchk`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    const label = await screen.findByText(t("rating.chargeCode.field.nsfFee"));
    expect(label.parentElement?.textContent).toContain(t("rating.yes"));
  });
});
