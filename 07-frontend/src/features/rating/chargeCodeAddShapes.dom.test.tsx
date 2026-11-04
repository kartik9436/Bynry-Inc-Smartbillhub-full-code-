// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-RAT-8843 — Add could not create a penalty priced as ONE FLAT
//          amount (NSF $30.00, TAMPER $250.00); it drew a penalty only as a
//          percent and a minimum. DEF-RAT-8844 — Add could not create a base
//          priced as ONE amount for every size on a service that has sizes
//          (BASE-W $8.00 All sizes). Found by 10-scripts/charge_codes_walk33.mjs
//          (2026-10-01), decided for fixing by the coordinator (law 13).
// Red first (law 7): on the tip before the fix, case 1 found no "One amount"
//          choice for a penalty and case 2 found no Priced by on a water base.
// What would pass wrongly: a flat penalty that still posted a percent rule —
//          case 1 asserts amount_rule "flat", percent null and the amount;
//          a one-amount base that posted per-size rows — case 2 asserts
//          size_amounts [] and the one amount.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { LookupEntry, MyPermissions, TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { ChargeCodeWizard } from "./ChargeCodeWizard";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

const SIZES: LookupEntry[] = ["W-58", "W-34", "W-1"].map(
  (code) =>
    ({ id: code, code, name: code, active: true, is_system: true, used_by: 0, service: { id: "water", code: "water" } }) as unknown as LookupEntry,
);

function stub(picked: { id: string; code: string; name: string }) {
  const patches: { path: string; body: Record<string, unknown> }[] = [];
  const ok = <T,>(data: T) => ({ status: 200, data, etag: null, notModified: false });
  const client = {
    get: vi.fn(async (path: string) => {
      if (path === "/charges/picker") return ok({ results: [{ ...picked, charge_type: null, kind: null, service: null }] });
      if (path.startsWith("/lookups/service_size_classes")) return ok({ count: SIZES.length, results: SIZES });
      if (path.startsWith("/lookups/")) return ok({ count: 0, results: [] });
      throw new Error(`no stub for ${path}`);
    }),
    request: vi.fn(async (path: string, options: { method: string; body: Record<string, unknown> }) => {
      patches.push({ path, body: options.body });
      return ok({ id: picked.id, code: picked.code, name: picked.name });
    }),
    post: vi.fn(),
  } as unknown as ApiClient;
  return { client, patches };
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
    { service: "water", name: "Water", enabled: true, primary_uom: null, alt_uom: null } as unknown as TenantServiceRow,
  ]);
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/plans-rates/charge-codes/new"]}>
          <Routes>
            <Route
              path="/:tenant/plans-rates/charge-codes/new"
              element={<ChargeCodeWizard client={client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return user;
}

async function pick(user: ReturnType<typeof userEvent.setup>, code: string) {
  await user.click(screen.getByLabelText(new RegExp(`^${t("rating.chargeCode.field.code")}`)));
  await user.click(await screen.findByRole("option", { name: new RegExp(`^${code} ·`) }));
}

async function finish(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
  fireEvent.change(screen.getByLabelText(/^Effective from/), { target: { value: "2026-10-01" } });
  await user.click(screen.getByRole("button", { name: t("rating.chargeCode.create") }));
}

describe("DEF-RAT-8843 · Add a penalty priced as one flat amount", () => {
  it("offers One amount for a penalty and posts a flat $30.00, never a percent", async () => {
    const s = stub({ id: "chg-nsf2", code: "NSF2", name: "Returned payment fee" });
    const user = mountAdd(s.client);
    await waitFor(() => expect(document.querySelector("#cc-kind")).not.toBeNull());
    fireEvent.change(document.querySelector("#cc-kind") as HTMLSelectElement, { target: { value: "plan" } });
    fireEvent.change(document.querySelector("#cc-type") as HTMLSelectElement, { target: { value: "penalty" } });
    fireEvent.change(document.querySelector("#cc-priced-by") as HTMLSelectElement, { target: { value: "amount" } });
    await pick(user, "NSF2");
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    const box = (await screen.findByLabelText(/^Amount 1/)) as HTMLInputElement;
    expect(document.querySelector('[data-cell="percent-0"]')).toBeNull();
    await user.type(box, "30.00");
    await finish(user);
    await waitFor(() => expect(s.patches).toHaveLength(1));
    expect(s.patches[0].body).toMatchObject({ charge_type: "penalty", amount_rule: "flat", amount: "30.00", percent: null, size_amounts: [] });
  });
});

describe("DEF-RAT-8844 · Add a base priced as one amount for every size", () => {
  it("a water base chosen as All sizes posts ONE amount and no per-size rows", async () => {
    const s = stub({ id: "chg-bw", code: "BASE-W2", name: "Water base" });
    const user = mountAdd(s.client);
    await waitFor(() => expect(document.querySelector("#cc-kind")).not.toBeNull());
    fireEvent.change(document.querySelector("#cc-kind") as HTMLSelectElement, { target: { value: "base" } });
    fireEvent.change(document.querySelector("#cc-service") as HTMLSelectElement, { target: { value: "water" } });
    await waitFor(() => expect(document.querySelector("#cc-priced-by")).not.toBeNull());
    fireEvent.change(document.querySelector("#cc-priced-by") as HTMLSelectElement, { target: { value: "one" } });
    await pick(user, "BASE-W2");
    await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
    await waitFor(() => expect(document.querySelectorAll('[data-cell^="amount-"]')).toHaveLength(1));
    expect(document.querySelector('[data-cell^="size-"]')).toBeNull();
    await user.type(document.querySelector('[data-cell="amount-0"]') as HTMLInputElement, "8.00");
    await finish(user);
    await waitFor(() => expect(s.patches).toHaveLength(1));
    expect(s.patches[0].body).toMatchObject({ kind: "base", amount: "8.00", size_amounts: [] });
  });
});
