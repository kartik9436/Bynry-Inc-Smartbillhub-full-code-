// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-10026 — a second base code for a class another base code
//          already holds was warned on step 1 ("BASE-E already covers
//          Residential.") and Continue was blocked. PO 2026-10-09, *"yes please
//          do it"*: a service may hold two or more base codes for one class; the
//          rate schedule names which one bills. Supersedes DEF-RAT-9799's warning,
//          which this file used to assert (renamed from chargeCodeBaseClash).
// Red first (law 7): on the tip before the fix the wizard asked
//          /charges/base-clash, rendered the warning and disabled Continue.
// What would pass wrongly: a wizard that still asks the probe but whose stub
//          answered null — so the stub answers a clash, and the case asserts no
//          request was made at all as well as no warning and Continue enabled.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { MyPermissions, TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { ChargeCodeWizard } from "./ChargeCodeWizard";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

function stub(clashWith: string | null) {
  const ok = <T,>(data: T) => ({ status: 200, data, etag: null, notModified: false });
  const asked: Record<string, string>[] = [];
  const client = {
    get: vi.fn(async (path: string, options?: { query?: Record<string, string> }) => {
      if (path === "/charges/picker")
        return ok({ results: [{ id: "chg-res", code: "BASE-SOL-RES", name: "Solar base", charge_type: null, kind: null, service: null }] });
      if (path === "/charges/base-clash") {
        asked.push(options?.query ?? {});
        return ok({ clash_with: clashWith });
      }
      if (path.startsWith("/lookups/")) return ok({ count: 0, results: [] });
      throw new Error(`no stub for ${path}`);
    }),
    request: vi.fn(),
    post: vi.fn(),
  } as unknown as ApiClient;
  return { client, asked };
}

function mountAdd(client: ApiClient) {
  const user = userEvent.setup();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  qc.setQueryData(queryKeys.myPermissions, {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: "plans_rates", label: "Plans & Rates", access: "Full" }],
  } as unknown as MyPermissions);
  qc.setQueryData(queryKeys.tenantServices, [
    { service: "solar", name: "Solar", enabled: true, primary_uom: null, alt_uom: null } as unknown as TenantServiceRow,
  ]);
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/annarbor/plans-rates/charge-codes/new"]}>
          <Routes>
            <Route
              path="/:tenant/plans-rates/charge-codes/new"
              element={<ChargeCodeWizard client={client} timeZone="America/Detroit" dateFormat="MM/DD/YYYY" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return user;
}

async function fillStepOne(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() => expect(document.querySelector("#cc-kind")).not.toBeNull());
  fireEvent.change(document.querySelector("#cc-kind") as HTMLSelectElement, { target: { value: "base" } });
  fireEvent.change(document.querySelector("#cc-service") as HTMLSelectElement, { target: { value: "solar" } });
  await user.click(screen.getByLabelText(new RegExp(`^${t("rating.chargeCode.field.code")}`)));
  await user.click(await screen.findByRole("option", { name: /^BASE-SOL-RES ·/ }));
}

describe("DEF-RAT-10026 · a second base code for the same class is not warned", () => {
  it("asks no clash probe, shows no warning and lets Continue on", async () => {
    // The stub WOULD answer a clash if asked — so a wizard still asking fails.
    const s = stub("BASE-SOL");
    const user = mountAdd(s.client);
    await fillStepOne(user);
    await waitFor(() => expect(screen.getByRole("button", { name: t("wizard.continue") })).toBeEnabled());
    expect(screen.queryByText(/already covers/)).toBeNull();
    expect(s.asked).toEqual([]);
  });
});
