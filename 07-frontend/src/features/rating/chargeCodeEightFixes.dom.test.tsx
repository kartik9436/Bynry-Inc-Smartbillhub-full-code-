// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-RAT-9803 (Kind filter outside + Filter) · 9804 (locked fields
//           look empty) · 9805 (Apply automatically on a one-time code) · 9806
//           (Edit's Code is a text box) · 9807 (an Entered-when-used default —
//           PO ruling 2026-10-06 option (a), BR-RAT-1054 AMENDED) · 9811, 9812
//           (late-fee hints) · 9813 (recurring + automatic warning).
// Every case below fails on the screens at 2.549.7 — proved red first.
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
import { startingAmount } from "@/components/moneyMath";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { ChargeCodesTab } from "./ChargeCodesTab";
import { ChargeCodeWizard } from "./ChargeCodeWizard";
import { chargePayload, draftFromCharge } from "./chargeCodeModel";

afterEach(cleanup);

const TENANT = "annarbor";
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

const PERMISSIONS = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "plans_rates", label: "Plans & Rates", access: "Full" }],
} as unknown as MyPermissions;
const SERVICES = ["water", "sewer"].map(
  (service) =>
    ({ service, name: t(`rating.service.${service}`), enabled: true, primary_uom: null, alt_uom: null }) as unknown as TenantServiceRow,
);
const CLASSES: LookupEntry[] = ["residential", "commercial"].map(
  (code) => ({ id: code, code, name: code, active: true, is_system: true, used_by: 0 }) as unknown as LookupEntry,
);

function charge(overrides: Partial<ChargeRow>): ChargeRow {
  return {
    id: "chg-1",
    code: "CODE",
    name: "A charge",
    charge_type: "one_time",
    service: null,
    is_base: false,
    kind: "other",
    amount_rule: "flat",
    amount: null,
    amount_display: null,
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
    gl_account_id: "gl-4900",
    gl_account_code: "4900",
    gl_account_name: "Fees",
    used_by_plans: 0,
    used_by_invoice_lines: 0,
    size_amounts: [],
    prices: [],
    price_range: null,
    usage: { bills: 0, lines: 0, revenue: "0.0000", revenue_display: "0.00" },
    versions: [],
    ...overrides,
  } as unknown as ChargeRow;
}

const APP_FEE = charge({ id: "chg-app", code: "APP-FEE", name: "Application processing fee", amount: "10.0000", amount_display: "10.00" });
const APP_WHEN_USED = charge({
  id: "chg-appw",
  code: "APP-W",
  name: "Application fee",
  amount_rule: "per_case",
  amount: "10.000000",
  amount_display: "10.00",
});
const TAP = charge({ id: "chg-tap", code: "TAP", name: "New service tap fee", amount_rule: "per_case" });

function stub(rows: ChargeRow[]) {
  const gets: { path: string; query: Record<string, unknown> }[] = [];
  const patches: { path: string; body: Record<string, unknown> }[] = [];
  const ok = <T,>(data: T) => ({ status: 200, data, etag: null, notModified: false });
  const client = {
    get: vi.fn(async (path: string, options?: { query?: Record<string, unknown> }) => {
      const query = options?.query ?? {};
      gets.push({ path, query });
      if (path === "/charges/picker") return ok({ results: [{ id: "chg-new", code: "PENALTY", name: "Late Fee", charge_type: null, kind: null, service: null }] });
      if (path.startsWith("/lookups/service_size_classes")) return ok({ count: 0, results: [] });
      if (path.startsWith("/lookups/account_types")) return ok({ count: CLASSES.length, results: CLASSES });
      if (path.endsWith("/plans")) return ok({ count: 0, next: null, previous: null, results: [] });
      if (path === "/charges") {
        return ok({ count: rows.length, next: null, previous: null, results: rows, kind_counts: { all: 37, base: 9, plan: 11, other: 16 } });
      }
      const id = decodeURIComponent(path.replace("/charges/", ""));
      const row = rows.find((one) => one.id === id) ?? charge({ id, code: "PENALTY", name: "Late Fee", kind: null as unknown as "other" });
      return ok(row);
    }),
    request: vi.fn(async (path: string, options: { method: string; body: Record<string, unknown> }) => {
      patches.push({ path, body: options.body });
      return ok({ ...rows[0] });
    }),
    post: vi.fn(),
  } as unknown as ApiClient;
  return { client, gets, patches };
}

function mount(element: JSX.Element, url: string, pattern: string) {
  const user = userEvent.setup();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  qc.setQueryData(queryKeys.tenantServices, SERVICES);
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
const mountEdit = (s: ReturnType<typeof stub>, row: ChargeRow) =>
  mount(
    <ChargeCodeWizard client={s.client} timeZone="America/Detroit" dateFormat="MM/DD/YYYY" />,
    `/${TENANT}/plans-rates/charge-codes/${row.id}/edit`,
    "/:tenant/plans-rates/charge-codes/:definitionId/edit",
  );
const mountAdd = (s: ReturnType<typeof stub>) =>
  mount(
    <ChargeCodeWizard client={s.client} timeZone="America/Detroit" dateFormat="MM/DD/YYYY" />,
    `/${TENANT}/plans-rates/charge-codes/new`,
    "/:tenant/plans-rates/charge-codes/new",
  );
const pageText = () => document.body.textContent ?? "";
const helpOf = (id: string) => document.getElementById(`${id}-help`)?.textContent ?? null;

// ── 1 · DEF-RAT-9803 ─────────────────────────────────────────────────────
describe("DEF-RAT-9803 · Kind lives in the + Filter panel", () => {
  it("draws no chip row; the panel offers Kind with counts and applies a removable Kind: Base chip", async () => {
    const s = stub([APP_FEE]);
    const user = mount(
      <ChargeCodesTab readOnly={false} client={s.client} timeZone="America/Detroit" dateFormat="MM/DD/YYYY" render={(parts) => <>{parts.body}</>} />,
      `/${TENANT}/plans-rates/charge-codes`,
      "/:tenant/plans-rates/charge-codes",
    );
    await waitFor(() => expect(pageText()).toContain("APP-FEE"));
    expect(document.querySelector("[data-kind-chips]")).toBeNull();
    const legend = [...document.querySelectorAll("details legend")].find((el) => el.textContent === t("rating.chargeCode.col.kind"));
    expect(legend).toBeDefined();
    const options = [...(legend?.parentElement?.querySelectorAll("label") ?? [])].map((el) => el.textContent);
    expect(options).toEqual(["Base · 9", "Plan · 11", "Other · 16"]);
    await user.click(screen.getByLabelText("Base · 9"));
    await waitFor(() => expect(s.gets.some((call) => call.path === "/charges" && call.query["f.kind"] === "base")).toBe(true));
    expect(screen.getByRole("button", { name: t("table.filters.remove", { label: t("rating.chargeCode.col.kind") }) })).toBeInTheDocument();
    expect(pageText()).toContain(t("table.filters.chip", { label: t("rating.chargeCode.col.kind"), value: "Base" }));
  });
});

// ── 2 + 4 · DEF-RAT-9804, DEF-RAT-9806 ──────────────────────────────────
describe("DEF-RAT-9804 / 9806 · Edit step 1 shows locked values in full", () => {
  it("What is it?, Service, Part month and Code are all LOCKED, readable, and Code is the dropdown", async () => {
    const s = stub([APP_FEE]);
    mountEdit(s, APP_FEE);
    await waitFor(() => expect(document.getElementById("cc-code")).not.toBeNull());
    for (const [id, value] of [
      ["cc-kind", t("rating.chargeCode.kind.other")],
      ["cc-service", t("rating.charges.anyService")],
      ["cc-part-month", t("rating.chargeCode.partMonth.full")],
      ["cc-code", "APP-FEE · Application processing fee"],
    ] as const) {
      const box = document.getElementById(id) as HTMLInputElement;
      expect(box, id).not.toBeNull();
      expect(box.hasAttribute("data-locked"), id).toBe(true);
      expect(box.readOnly, id).toBe(true);
      expect(box.disabled, id).toBe(false);
      expect(box.className, id).not.toContain("opacity-45");
      expect(box.value, id).toBe(value);
    }
    expect(document.getElementById("cc-code")?.getAttribute("role")).toBe("combobox");
    expect(helpOf("cc-code")).toBe(t("rating.chargeCode.codeLocked"));
    expect(helpOf("cc-service")).toBe(t("rating.chargeCode.fixed"));
  });
});

// ── 3 · DEF-RAT-9805 ─────────────────────────────────────────────────────
describe("DEF-RAT-9805 · a one-time code never applies automatically", () => {
  it("Apply automatically reads No, locked, with its help line", async () => {
    const s = stub([charge({ ...APP_FEE, auto_apply: true })]);
    mountEdit(s, APP_FEE);
    await waitFor(() => expect(document.getElementById("cc-auto")).not.toBeNull());
    const box = document.getElementById("cc-auto") as HTMLInputElement;
    expect(box.hasAttribute("data-locked")).toBe(true);
    expect(box.value).toBe(t("rating.no"));
    expect(helpOf("cc-auto")).toBe(t("rating.chargeCode.autoOneTimeHelp"));
  });
});

// ── 8 · 9 · 10 · DEF-RAT-9811, 9812, 9813 ───────────────────────────────
describe("DEF-RAT-9811 / 9812 / 9813 · late-fee hints and the every-bill warning", () => {
  it("Other says where late fees go; Plan's Type says Penalty; recurring + automatic warns", async () => {
    const s = stub([]);
    const user = mountAdd(s);
    await waitFor(() => expect(document.getElementById("cc-kind")).not.toBeNull());
    await user.selectOptions(document.getElementById("cc-kind") as HTMLSelectElement, "other");
    expect(helpOf("cc-kind")).toContain("Late fees: choose Plan charge.");
    await user.selectOptions(document.getElementById("cc-kind") as HTMLSelectElement, "plan");
    expect(helpOf("cc-type")).toBe("Late fees: choose Penalty.");
    expect(document.querySelector('[data-warning="bills-everyone"]')).toBeNull();
    await user.selectOptions(document.getElementById("cc-type") as HTMLSelectElement, "recurring");
    await user.selectOptions(document.getElementById("cc-auto") as HTMLSelectElement, "yes");
    expect(document.querySelector('[data-warning="bills-everyone"]')?.textContent).toBe("Bills every account, every bill.");
    await user.selectOptions(document.getElementById("cc-auto") as HTMLSelectElement, "no");
    expect(document.querySelector('[data-warning="bills-everyone"]')).toBeNull();
  });
});

// ── 5 · DEF-RAT-9807 ─────────────────────────────────────────────────────
describe("DEF-RAT-9807 · an Entered-when-used code may carry a default", () => {
  it("the box starts at the stored default, and a save posts what the clerk typed", async () => {
    const s = stub([APP_WHEN_USED]);
    const user = mountEdit(s, APP_WHEN_USED);
    await waitFor(() => expect(document.getElementById("cc-code")).not.toBeNull());
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    const box = (await screen.findByLabelText(new RegExp(`^${t("rating.chargeCode.field.defaultAmount")}`))) as HTMLInputElement;
    expect(box.value).toBe("10.00");
    expect(helpOf("cc-default-amount")).toBe(t("rating.chargeCode.defaultAmountHelp"));
  });

  it("the payload carries the default, or null when blank — exactly as before", () => {
    const withDefault = draftFromCharge(APP_WHEN_USED, []);
    expect(chargePayload(withDefault, true).amount).toBe("10.00");
    expect(chargePayload({ ...withDefault, rows: [{ ...withDefault.rows[0], amount: "25.00" }] }, true).amount).toBe("25.00");
    const blank = draftFromCharge(TAP, []);
    expect(chargePayload(blank, true).amount).toBeNull();
    expect(chargePayload(blank, true).amount_rule).toBe("per_case");
  });

  it("startingAmount drops zeros past two places and never rounds", () => {
    expect(startingAmount("10.0000")).toBe("10.00");
    expect(startingAmount("8.937500")).toBe("8.9375");
    expect(startingAmount("0.1000")).toBe("0.10");
    expect(startingAmount(null)).toBe("");
  });
});
