// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9235 — New Account let the clerk past a blank REQUIRED
//          custom field. Continue never asked, the create was refused 422 at
//          the end and the review said "Check the highlighted fields" about a
//          box two steps back. Found by the custom-fields end-to-end walk
//          (`10-scripts/cf_e2e_walk.mjs` phase 8).
// Rules:   CR-161-BRC10 Rules table — "Required means required only where
//          it's typed in" · hard-won law 2 (mounted under the REAL path)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import type { CustomFieldRegistryEntry, MyPermissions } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { NewAccountWizard } from "./NewAccountWizard";
import { ACCOUNTS_PERMISSION } from "./customersShared";

afterEach(() => cleanup());

const CONTRACT_REF = {
  id: "cf-1",
  key: "contract_ref",
  label: "Contract ref",
  help_text: "",
  data_type: "text",
  options: [],
  is_required: true,
  display_order: 0,
  placement: { S18: "input" },
} as unknown as CustomFieldRegistryEntry;

/** The registry answers `fields` for `entity` on New account; everything else is empty. */
function client(entity: string, fields: CustomFieldRegistryEntry[]): ApiClient {
  const answer = <T,>(data: unknown) => ({ data: data as T, status: 200, headers: new Headers() });
  return {
    request: <T,>() => Promise.resolve(answer<T>({})),
    get: <T,>(path: string, options?: { query?: Record<string, unknown> }) => {
      if (path === "/custom-fields") {
        return Promise.resolve(answer<T>({ entity: options?.query?.entity, fields: options?.query?.entity === entity ? fields : [] }));
      }
      return Promise.resolve(answer<T>({ results: [], count: 0, next: null, previous: null }));
    },
    post: <T,>() => Promise.resolve(answer<T>({})),
  } as unknown as ApiClient;
}

function mountAt(step: number, api: ApiClient, accountFields: CustomFieldRegistryEntry[] = []) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  // The registry the step's own box reads (it uses the shared transport), in
  // the cache, so the box and the step check read the SAME answer.
  queryClient.setQueryData(queryKeys.customFieldRegistry("accounts", "S18", "input"), accountFields);
  const permissions: MyPermissions = {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access: "write" }],
  };
  queryClient.setQueryData(queryKeys.myPermissions, permissions);
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/brazosbend/accounts/new?step=${step}`]}>
          <Routes>
            <Route path="/:tenant/accounts/new" element={<NewAccountWizard client={api} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("DEF-CUS-9235 · a required own field holds the New Account step that draws it", () => {
  it("Account preferences: a blank required Contract ref holds Continue and names the field", async () => {
    const user = userEvent.setup();
    mountAt(3, client("accounts", [CONTRACT_REF]), [CONTRACT_REF]);
    const box = await screen.findByLabelText(/Contract ref/);
    await user.click(screen.getAllByRole("button", { name: /^Continue/ })[0]);
    expect(await screen.findByText("Fill in: Contract ref.")).toBeInTheDocument();
    // still on the step: the box is still there to type into
    expect(screen.getByLabelText(/Contract ref/)).toBe(box);
  });

  it("Account preferences: once typed, Continue moves on (the check is not a wall)", async () => {
    const user = userEvent.setup();
    mountAt(3, client("accounts", [CONTRACT_REF]), [CONTRACT_REF]);
    const box = await screen.findByLabelText(/Contract ref/);
    await user.type(box, "CR-7788");
    await user.click(screen.getAllByRole("button", { name: /^Continue/ })[0]);
    expect(screen.queryByText("Fill in: Contract ref.")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Contract ref/)).not.toBeInTheDocument();
  });

  it("a NOT-required own field never holds the step (required only where it is typed in)", async () => {
    const user = userEvent.setup();
    mountAt(3, client("accounts", []), [{ ...CONTRACT_REF, is_required: false } as CustomFieldRegistryEntry]);
    await screen.findByLabelText(/Contract ref/);
    await user.click(screen.getAllByRole("button", { name: /^Continue/ })[0]);
    expect(screen.queryByText("Fill in: Contract ref.")).not.toBeInTheDocument();
  });
});
