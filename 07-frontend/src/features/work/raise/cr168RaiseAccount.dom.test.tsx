// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 3, lane RAISE — image 19 (1·4e), *Raise from an
//           account*: ruling 35 (the form arrives filled), P2.4,
//           DEF-WRK-4752 (the account's *Raise work here* opened it blank).
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import RECORDED_ASSETS from "../__fixtures__/work-raise-assets.recorded.json";
import RECORDED_TEMPLATES from "../__fixtures__/work-templates-for-the-raise.recorded.json";

import { ACCOUNT_RAISE_ROUTE, AccountRaisePage, accountRaisePath } from "./AccountRaisePage";

// REAL answers recorded on PostgreSQL by lane SRV-2 — the demo's Unit 1 of
// 101 Silver Creek Rd, AC-2026-00001's unit, carries E-5000 and W-5000.
const U1 = RECORDED_ASSETS.results[0].unit.id;
const METER_TYPE = RECORDED_ASSETS.results[0].type.id;
const T_MX = RECORDED_TEMPLATES.results.find((r) => r.name === "Meter exchange — residential")!.id;

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
afterEach(() => cleanup());

type Call = { method: string; path: string; query: Record<string, unknown>; body: unknown };
const ok = (data: unknown) => ({ status: 200, data, etag: null, notModified: false }) as ApiResponse<unknown>;
const page = <R,>(results: R[]) => ({ count: results.length, next: null, previous: null, results });

const ACCOUNT = {
  id: "acc-1", account_no: "AC-2026-00001", name: "Ana Alvarez", unit_id: U1, unit_label: "Unit 1",
  premises_id: "p-101", premise: "101 Silver Creek Rd", premise_address: "101 Silver Creek Rd",
  services: ["electric", "water"], status: "active", status_name: "Active",
  account_type: "residential", account_subtype_name: "Single-family",
};

function fakeClient(calls: Call[]): ApiClient {
  const reads: Record<string, unknown> = {
    "/accounts/acc-1": ACCOUNT,
    "/work/raise-options": {
      types: [{ id: "jt-change", code: "MC", name: "Meter Change", parent_name: null, default_priority_id: "pr-n" }],
      priorities: [{ id: "pr-n", code: "NORMAL", name: "Normal", sla_hours: 72 }],
    },
    "/work/templates": RECORDED_TEMPLATES,
    [`/work/templates/${T_MX}`]: { ...RECORDED_TEMPLATES.results.find((r) => r.id === T_MX), bundle: { asset_types: [{ asset_type_id: METER_TYPE }] } },
    "/lookups/asset_types": page([{ id: METER_TYPE, code: "meter", name: "Meter" }]),
    "/work/raise/assets": RECORDED_ASSETS,
  };
  return {
    get: async (path: string, opts?: { query?: Record<string, unknown> }) => {
      calls.push({ method: "GET", path, query: opts?.query ?? {}, body: null });
      if (path in reads) return ok(reads[path]);
      if (path.startsWith("/custom-fields")) return ok({ results: [] });
      throw new Error(`unexpected read: ${path}`);
    },
  } as unknown as ApiClient;
}

describe("CR-168 image 19 · raised from an account (ruling 35, DEF-WRK-4752)", () => {
  it("has its own address beside the account, and its constant has no tenant", () => {
    expect(accountRaisePath("acc-1")).toBe("/accounts/acc-1/work-orders/new");
    expect(ACCOUNT_RAISE_ROUTE).toBe("/accounts/:accountId/work-orders/new");
  });

  it("arrives filled: From the account, no premises to type, the account's meters listed", async () => {
    const calls: Call[] = [];
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}${accountRaisePath("acc-1")}`]}>
            <Routes>
              <Route path={`/:tenant${ACCOUNT_RAISE_ROUTE}`} element={<AccountRaisePage client={fakeClient(calls)} />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(await screen.findByText(t("work.raise.fromAccount"))).toBeTruthy();
    expect(await screen.findByText(t("work.raise.kicker.account", { account: "AC-2026-00001" }))).toBeTruthy();
    expect(screen.getByText("Residential · Single-family")).toBeTruthy();
    expect(screen.queryByRole("combobox", { name: t("work.raise.premises") })).toBeNull();
    expect(screen.queryByTestId("raise-units")).toBeNull();

    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText(new RegExp(t("work.raise.type"), "u")), "jt-change");
    const templateSelect = screen.getByLabelText(new RegExp(t("work.raise.template"), "u"));
    await waitFor(() => expect(templateSelect.querySelectorAll(`option[value='${T_MX}']`).length).toBe(1));
    await user.selectOptions(templateSelect, T_MX);
    expect(await screen.findByText("W-5000")).toBeTruthy();
    const read = calls.filter((c) => c.path === "/work/raise/assets").pop();
    expect(read?.query).toMatchObject({ unit_ids: U1, asset_type: METER_TYPE, service: "water" });
    await user.click(screen.getByRole("checkbox", { name: t("work.raise.tick", { unit: "W-5000" }) }));
    expect(screen.getByText(t("work.raise.summaryOne", { subject: "W-5000" }))).toBeTruthy();
  });
});
