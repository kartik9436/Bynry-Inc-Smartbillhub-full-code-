// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-9321 — PO, 2026-10-03, on the live site at 2.455.0,
//          Ottumwa Water Works, Edit BASE-W-FIRE › step 2 Pricing (Every class
//          · by Meter size): the Size dropdown listed "W-58, W-34, W-1, W-112,
//          W-2 …" and the chosen value read "W-1". Verbatim: "sizes should be
//          user friendly language - youa re showing internal codes".
// Red first (law 7): on the tip before the fix every option's text was the
//          code (`W-58`) and the Review and View details tables printed `W-1`.
// What would pass wrongly: a fixture whose size NAME equals its code — the
//          fixtures this file replaces did exactly that, so here every name
//          differs from its code and each case also asserts the code is ABSENT.
//          The STORED value is untouched: each select's `value` stays the code.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
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
import { chargePayload, draftFromCharge, emptyRow, sizeListedTwice } from "./chargeCodeModel";

afterEach(cleanup);

const TENANT = "ottumwa";
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

/** Ottumwa's water list, served in CODE order. Every name differs from its code. */
const WATER: [string, string][] = [
  ["W-1", 'Water 1"'],
  ["W-112", 'Water 1 1/2"'],
  ["W-2", 'Water 2"'],
  ["W-34", 'Water 3/4"'],
  ["W-58", 'Water 5/8"'],
];
const SIZES: LookupEntry[] = WATER.map(
  ([code, name]) =>
    ({ id: code, code, name, active: true, is_system: true, used_by: 0, service: { id: "water", code: "water" } }) as unknown as LookupEntry,
);
const CODES = WATER.map(([code]) => code);

function price(size_class: string, amount: string) {
  return {
    id: `p-${size_class}`,
    size_class,
    customer_class: null,
    amount: `${amount}00`,
    amount_display: amount,
    currency: "USD",
    effective_from: "2000-01-01",
    effective_to: null,
    killed: false,
    version: 1,
  };
}

const BASE_W_FIRE = {
  id: "chg-wfire",
  code: "BASE-W-FIRE",
  name: "Water base, fire",
  charge_type: "recurring",
  service: "water",
  is_base: true,
  kind: "base",
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
  auto_apply: true,
  waivable: false,
  separate_line: true,
  applies_to_customer_classes: [],
  status: "active",
  gl_account_id: null,
  gl_account_code: null,
  gl_account_name: null,
  used_by_plans: 1,
  used_by_invoice_lines: 0,
  size_amounts: [price("W-58", "8.00"), price("W-1", "12.00"), price("W-112", "20.00")],
  class_terms: [],
  prices: [],
  price_range: null,
  usage: { bills: 0, lines: 0, revenue: "0.0000", revenue_display: "0.00" },
  versions: [
    {
      effective_from: "2026-11-01",
      effective_to: null,
      state: "scheduled",
      created: false,
      changes: [{ size_class: "W-1", customer_class: null, before_display: "12.00", after_display: "13.00", new: false }],
      who: "Clerk",
      why: "Board approved",
    },
  ],
} as unknown as ChargeRow;

function stub(row: ChargeRow) {
  const ok = <T,>(data: T) => ({ status: 200, data, etag: null, notModified: false });
  const client = {
    get: vi.fn(async (path: string) => {
      if (path.startsWith("/lookups/service_size_classes")) return ok({ count: SIZES.length, results: SIZES });
      if (path.startsWith("/lookups/")) return ok({ count: 0, results: [] });
      if (path.endsWith("/plans")) return ok({ count: 0, next: null, previous: null, results: [] });
      if (path === `/charges/${row.id}`) return ok(row);
      throw new Error(`no stub for ${path}`);
    }),
    request: vi.fn(async () => ok(row)),
    post: vi.fn(),
  } as unknown as ApiClient;
  return client;
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

const noCode = (text: string) => CODES.filter((code) => new RegExp(`(^|[^A-Za-z-])${code}([^0-9]|$)`).test(text));

describe("DEF-RAT-9321 · a charge code's sizes read as the utility's names, never as codes", () => {
  it("Edit BASE-W-FIRE › Pricing: every Size option and the chosen value read Water 5/8\" etc.; the value posted stays the code", async () => {
    const client = stub(BASE_W_FIRE);
    const user = mount(
      <ChargeCodeWizard client={client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-wfire/edit`,
      "/:tenant/plans-rates/charge-codes/:definitionId/edit",
    );
    await user.click(await screen.findByRole("button", { name: t("wizard.continue") }));
    await waitFor(() => expect(screen.getAllByLabelText(t("rating.chargeCode.col.size")).length).toBe(3));
    const selects = screen.getAllByLabelText(t("rating.chargeCode.col.size")) as HTMLSelectElement[];
    // The STORED key is unchanged — size order, codes.
    expect(selects.map((select) => select.value)).toEqual(["W-58", "W-1", "W-112"]);
    // What a clerk SEES in the closed select: the chosen option's words.
    expect(selects.map((select) => select.selectedOptions[0]?.textContent)).toEqual(['Water 5/8"', 'Water 1"', 'Water 1 1/2"']);
    // The open list of row 1: its own size plus the two nobody priced, by name.
    const offered = within(selects[0]).getAllByRole("option").map((option) => option.textContent ?? "").slice(1);
    expect(offered).toEqual(['Water 5/8"', 'Water 3/4"', 'Water 2"']);
    for (const select of selects) {
      const words = within(select).getAllByRole("option").map((option) => option.textContent ?? "");
      expect(words.flatMap(noCode)).toEqual([]);
    }
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).not.toBeNull());
    const review = (document.querySelector('[data-step="review"]') as HTMLElement).textContent ?? "";
    expect(review).toContain('Water 5/8"');
    expect(review).toContain('Water 1 1/2"');
    expect(noCode(review)).toEqual([]);
  });

  it("View details › Prices and the version history name each size", async () => {
    const client = stub(BASE_W_FIRE);
    mount(
      <ChargeCodeDetailPage client={client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-wfire?tab=prices`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => {
      const sizes = [...document.querySelectorAll('[data-array="charge-prices"] tbody strong')].map((cell) => cell.textContent);
      expect(sizes).toEqual(['Water 5/8"', 'Water 1"', 'Water 1 1/2"']);
    });
    expect(noCode((document.querySelector('[data-array="charge-prices"]') as HTMLElement).textContent ?? "")).toEqual([]);
    cleanup();
    mount(
      <ChargeCodeDetailPage client={stub(BASE_W_FIRE)} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-wfire?tab=audit`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => expect(document.body.textContent ?? "").toContain('Water 1": $12.00 → $13.00'));
  });
});

// ── DEF-RAT-9322 · one size held twice: every class AND Commercial ─────────
// Red first (law 7): on the tip before the fix step 2 drew two identical
// "W-1" rows with no class, and Save posted BOTH as `customer_class: null` —
// the pair the server refuses ("W-1 appears twice"), or a Commercial-only
// price silently widened to every class.
function priceFor(size_class: string, amount: string, customer_class: string | null) {
  return { ...price(size_class, amount), id: `p-${size_class}-${customer_class ?? ""}`, customer_class };
}
const BASE_W_DUP = {
  ...BASE_W_FIRE,
  id: "chg-wdup",
  code: "BASE-W-DUP",
  versions: [],
  size_amounts: [priceFor("W-58", "8.00", null), priceFor("W-1", "12.00", null), priceFor("W-1", "18.00", "commercial")],
} as unknown as ChargeRow;

describe("DEF-RAT-9322 · a size priced for every class and for one class reads as two classes, not one size twice", () => {
  it("Edit › Pricing shows the class beside each size; Review names it; the payload keeps Commercial on its row", async () => {
    const client = stub(BASE_W_DUP);
    const user = mount(
      <ChargeCodeWizard client={client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-wdup/edit`,
      "/:tenant/plans-rates/charge-codes/:definitionId/edit",
    );
    await user.click(await screen.findByRole("button", { name: t("wizard.continue") }));
    await waitFor(() => expect(screen.getAllByLabelText(t("rating.chargeCode.col.size")).length).toBe(3));
    const table = document.querySelector('[data-array="charge-price-rows"]') as HTMLElement;
    const rows = [...table.querySelectorAll("tbody tr")].map((row) => [
      (row.querySelector("select") as HTMLSelectElement).selectedOptions[0]?.textContent,
      row.querySelector('[data-static="class"], [data-cell="class"]')?.textContent ?? null,
    ]);
    expect(rows).toEqual([
      ['Water 5/8"', t("rating.chargeCode.everyClass")],
      ['Water 1"', t("rating.chargeCode.everyClass")],
      ['Water 1"', "Commercial"],
    ]);
    expect(table.textContent ?? "").toContain(t("rating.chargeCode.col.customerClass"));
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    await waitFor(() => expect(document.querySelector('[data-step="review"]')).not.toBeNull());
    const review = (document.querySelector('[data-step="review"]') as HTMLElement).textContent ?? "";
    expect(review).toContain("Commercial");
    const posted = chargePayload(draftFromCharge(BASE_W_DUP, SIZES), true).size_amounts;
    expect(posted).toEqual([
      { size_class: "W-58", customer_class: null, amount: "8.00" },
      { size_class: "W-1", customer_class: null, amount: "12.00" },
      { size_class: "W-1", customer_class: "commercial", amount: "18.00" },
    ]);
  });

  it("View details › Prices names the class on each row", async () => {
    mount(
      <ChargeCodeDetailPage client={stub(BASE_W_DUP)} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />,
      `/${TENANT}/plans-rates/charge-codes/chg-wdup?tab=prices`,
      "/:tenant/plans-rates/charge-codes/:definitionId",
    );
    await waitFor(() => {
      const cells = [...document.querySelectorAll('[data-array="charge-prices"] tbody tr')].map((row) =>
        [...row.querySelectorAll("strong")].map((cell) => cell.textContent),
      );
      expect(cells).toEqual([
        ['Water 5/8"', t("rating.chargeCode.everyClass")],
        ['Water 1"', t("rating.chargeCode.everyClass")],
        ['Water 1"', "Commercial"],
      ]);
    });
  });

  it("the same size twice for the SAME class is refused, naming the size; two classes are not", () => {
    expect(sizeListedTwice([emptyRow("W-1"), emptyRow("W-1", "commercial")])).toBeNull();
    expect(sizeListedTwice([emptyRow("W-1"), emptyRow(""), emptyRow("W-1")])?.size).toBe("W-1");
    expect(t("rating.chargeCode.sizeTwice", { size: 'Water 1"' })).toBe('Water 1" is listed twice.');
  });
});
