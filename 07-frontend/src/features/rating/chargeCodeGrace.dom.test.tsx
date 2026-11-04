// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  PO ruling 2026-10-06 11 (a) — *"Put grace on the late-fee code. When
//          Type is Penalty, the form asks Grace days (default 5) and Calendar /
//          Business days, and billing uses the code's grace. The Settings
//          default stays as the starting value for new codes."*
// Red first (law 7): before the build, case 1 found no "Grace days" box on
//          step 1 and case 3 found no grace line under the late fee's When.
// What would pass wrongly: a form that showed the boxes but posted nothing —
//          case 1 asserts the PATCH body; a default hard-coded to 5 — case 2's
//          utility starts at 7 business days.
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
import { normalisePlanSections } from "@/api/planFormEndpoints";
import type { PlanChargeSection } from "@/api/planFormEndpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { howItBills } from "./ChargeCodeDetailPage";
import { ChargeCodeWizard } from "./ChargeCodeWizard";
import { graceLine } from "./planSections/PlanSections";

afterEach(cleanup);

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

function lateRow(extra: Partial<ChargeRow> = {}): ChargeRow {
  return {
    id: "chg-late",
    code: "LATE",
    name: "Late payment fee",
    charge_type: "penalty",
    service: null,
    is_base: false,
    kind: "plan",
    amount_rule: "percent_with_minimum",
    amount: null,
    amount_display: null,
    percent: "0.015000",
    percent_display: "1.50%",
    min_amount: "5.0000",
    min_amount_display: "5.00",
    max_amount: null,
    max_amount_display: null,
    taxable_default: false,
    auto_apply: false,
    waivable: true,
    separate_line: true,
    applies_to_customer_classes: [],
    status: "active",
    gl_account_id: "gl-4200",
    gl_account_code: "4200",
    gl_account_name: "Late-fee revenue",
    used_by_plans: 3,
    used_by_invoice_lines: 0,
    size_amounts: [],
    class_terms: [],
    prices: [],
    price_range: null,
    usage: { bills: 0, lines: 0, revenue: "0.0000", revenue_display: "0.00" },
    versions: [],
    grace_days: 5,
    grace_mode: "calendar",
    grace_default: { days: 5, mode: "calendar" },
    ...extra,
  } as unknown as ChargeRow;
}

function stub(row: ChargeRow) {
  const patches: { path: string; body: Record<string, unknown> }[] = [];
  const ok = <T,>(data: T) => ({ status: 200, data, etag: null, notModified: false });
  const client = {
    get: vi.fn(async (path: string) => {
      if (path.startsWith("/lookups/")) return ok({ count: 0, results: [] });
      if (path === "/charges/chg-late") return ok(row);
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

function mount(element: JSX.Element) {
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
        <MemoryRouter initialEntries={[`/${TENANT}/plans-rates/charge-codes/chg-late/edit`]}>
          <Routes>
            <Route path="/:tenant/plans-rates/charge-codes/:definitionId/edit" element={element} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return user;
}

describe("PO 2026-10-06 11 (a) · the late-fee grace is set on the penalty code", () => {
  it("step 1 asks Grace days and Counted in; a change posts on the code", async () => {
    const s = stub(lateRow());
    const user = mount(<ChargeCodeWizard client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />);
    const days = (await screen.findByLabelText(/^Grace days/)) as HTMLInputElement;
    expect(days.value).toBe("5");
    await user.clear(days);
    await user.type(days, "10");
    await user.selectOptions(screen.getByLabelText(/^Counted in/), "business");
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    expect(screen.getAllByText("10 business days").length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText(/^Effective from/), { target: { value: "2026-11-01" } });
    await user.type(screen.getByLabelText(/^Reason/), "Board moved the late-fee grace");
    await user.click(screen.getByRole("button", { name: t("rating.chargeCode.saveChange") }));
    await waitFor(() => expect(s.patches).toHaveLength(1));
    expect(s.patches[0].body).toMatchObject({ grace_days: "10", grace_mode: "business" });
  });

  it("a penalty with no grace of its own starts at Billing defaults' grace", async () => {
    const s = stub(lateRow({ grace_days: null, grace_mode: null, grace_default: { days: 7, mode: "business" } }));
    mount(<ChargeCodeWizard client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />);
    const days = (await screen.findByLabelText(/^Grace days/)) as HTMLInputElement;
    expect(days.value).toBe("7");
    expect((screen.getByLabelText(/^Counted in/) as HTMLSelectElement).value).toBe("business");
  });

  it("refuses a grace over 30 days before the server is asked", async () => {
    const s = stub(lateRow());
    const user = mount(<ChargeCodeWizard client={s.client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />);
    const days = (await screen.findByLabelText(/^Grace days/)) as HTMLInputElement;
    await user.clear(days);
    await user.type(days, "31");
    expect(await screen.findByText(t("rating.plans.grace_days_range", { max: 30 }))).toBeInTheDocument();
    expect(screen.getByRole("button", { name: t("wizard.continue") })).toBeDisabled();
  });

  it("View details lists the grace under How it bills; a non-penalty does not", () => {
    const facts = howItBills(lateRow({ grace_days: 10, grace_mode: "calendar" }), t);
    expect(facts.find((fact) => fact.id === "grace")?.value).toBe("10 calendar days");
    const recon = howItBills(lateRow({ charge_type: "one_time", grace_days: null, grace_mode: null }), t);
    expect(recon.find((fact) => fact.id === "grace")).toBeUndefined();
  });

  it("the plan shows the late fee's grace, and says when the plan's own override applies", () => {
    const late = { grace: { days: 5, mode: "calendar", from: "charge_code" } } as unknown as PlanChargeSection;
    expect(graceLine(late, t)).toBe("Grace: 5 calendar days");
    const kept = { grace: { days: 3, mode: "calendar", from: "plan" } } as unknown as PlanChargeSection;
    expect(graceLine(kept, t)).toBe("Grace: 3 calendar days (this plan)");
    expect(graceLine({ grace: null } as unknown as PlanChargeSection, t)).toBeNull();
  });

  it("the plan read keeps the served grace (it was dropped by the normaliser at first)", () => {
    const sections = normalisePlanSections({
      charge_codes: [
        {
          ref: { id: "chg-late", kind: "charge_code", code: "LATE", name: "Late payment fee", version: 1 },
          late_fee: true,
          grace: { days: 10, mode: "business", from: "charge_code" },
          priced_by: "one_amount",
          rows: [],
          gl: null,
          type_label: "penalty",
          when_label: "After the due date",
        },
      ],
    });
    expect(sections.charge_codes[0]?.grace).toEqual({ days: 10, mode: "business", from: "charge_code" });
  });
});
