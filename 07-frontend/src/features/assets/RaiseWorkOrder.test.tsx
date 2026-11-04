// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-038 (EP-WRK-07) — the Assets door: one address, four ways in.
// Change:   CR-168-BRC10 round 3, lane RAISE — ruling 35 RETIRES figure 42's
//           one-page form (*Template · Raise work order ✓*); the address now
//           opens the dispatcher's three-step raise ARRIVING FILLED from the
//           asset (image 20). `BR-WRK-056` holds: same address, Work's own
//           write, templates filtered by the asset's type and service.
// Rules:    BR-AST-534 / BR-SHL-025 (a control that cannot act is disabled
//           WITH ITS REASON) · B14 rule 31.
// ───────────────────────────────────────────────────────
//
// ⚠ **THE NINE CASES THIS FILE HELD FOR THE ONE-PAGE FORM ARE GONE WITH THE
// FORM, NOT SKIPPED.** What they protected and still applies moved here: the
// empty-picker refusal and its next step (now on the raise's Template), the
// asset NUMBER and never its uuid (now in the *From the asset* panel and the
// kicker), and the write going to Work's own door with `source: assets`
// (asserted in `features/work/raise/cr168Raise.dom.test.tsx`, which walks the
// whole three-step flow).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import type { AssetTemplatesPayload } from "@/features/work/workEndpoints";

import { RaiseWorkOrderPage, raiseWorkOrderPath, RAISE_WORK_ORDER_ROUTE } from "./RaiseWorkOrderPage";

const TEST_TENANT = "brazosbend";
const ASSET_ID = "01a08ef6-1111-7000-8000-000000000001";
const ASSET_NO = "M-7001";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(() => cleanup());

const ok = (data: unknown) => ({ status: 200, data, etag: null, notModified: false }) as ApiResponse<unknown>;

function client(rows: AssetTemplatesPayload["results"]): ApiClient {
  const reads: Record<string, unknown> = {
    [`/assets/${ASSET_ID}`]: {
      id: ASSET_ID, asset_no: ASSET_NO, type: "meter", type_name: "Meter", read_method_name: "Walk-by",
      service: "water", assigned_unit_id: "u-1", assigned_address: "101 Silver Creek Rd", assigned: true,
      actions: [], warnings: [],
    },
    "/units/u-1": { id: "u-1", label: "Unit 1", premises_id: "p-1", premise_address: "101 Silver Creek Rd" },
    "/units/u-1/account": { account: null },
    // SRV-2's envelope (`results`); the one-round `rows` twin is retired (SRV-3).
    [`/assets/${ASSET_ID}/work-order-templates`]: {
      count: rows.length, next: null, previous: null, results: rows,
      asset: { id: ASSET_ID, asset_no: ASSET_NO, asset_type_id: "at-meter" },
    },
    "/work/raise-options": { types: [], priorities: [] },
  };
  return {
    get: async (path: string) => {
      if (path in reads) return ok(reads[path]);
      if (path.startsWith("/custom-fields")) return ok({ results: [] });
      throw new Error(`unexpected read: ${path}`);
    },
  } as unknown as ApiClient;
}

function mount(rows: AssetTemplatesPayload["results"]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${raiseWorkOrderPath(ASSET_ID)}`]}>
          <Routes>
            <Route
              path={`/:tenant${RAISE_WORK_ORDER_ROUTE}`}
              element={<RaiseWorkOrderPage client={client(rows)} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("the Assets door (BR-WRK-056 holds; ruling 35 retires the one-page form)", () => {
  it("keeps its address — a sibling of …/maintenance/new", () => {
    expect(raiseWorkOrderPath(ASSET_ID)).toBe(`/assets/${ASSET_ID}/work-orders/new`);
    expect(RAISE_WORK_ORDER_ROUTE).toBe("/assets/:assetId/work-orders/new");
  });

  it("does not define a screen badge of its own (DEF-MET-4978)", async () => {
    const mod = (await import("./RaiseWorkOrderPage")) as Record<string, unknown>;
    expect(mod.RAISE_WORK_ORDER_SCREEN).toBeUndefined();
  });

  it("names the asset by its NUMBER, never its uuid (B14 rule 31)", async () => {
    mount([{ id: "tpl-backflow", name: "Annual backflow test", scope: "asset", restricted: true }]);
    expect(await screen.findByText(t("work.raise.kicker.asset", { asset: ASSET_NO }))).toBeTruthy();
    await waitFor(() => expect(screen.getByRole("option", { name: "Annual backflow test" })).toBeTruthy());
    expect(document.body.textContent ?? "").not.toContain(ASSET_ID);
  });

  it("no template fits: the picker cannot act and says why, with the next step", async () => {
    mount([]);
    const help = `${t("assets.raiseWork.noneApply")} ${t("assets.raiseWork.noneApplyNext")}`;
    expect(await screen.findByText(help)).toBeTruthy();
    const select = screen.getByLabelText(new RegExp(t("work.raise.template"), "u")) as HTMLSelectElement;
    expect(select.disabled).toBe(true);
  });
});
