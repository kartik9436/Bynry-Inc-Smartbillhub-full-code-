// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9242 (custom-fields end-to-end walk, 2026-10-03) — New
//          Connection step 2 let Continue past a blank REQUIRED premises field
//          (Roof Material) and landed on Units with nothing naming the box;
//          the same shape DEF-CUS-9235 fixed on New Account.
// ───────────────────────────────────────────────────────
// ⚠ IT ASSERTS THE PRESS, NOT A HELPER (hard-won law 2): the question is
// whether the WIZARD stops on step 2 and names the field when a person
// presses Continue. WHAT WOULD MAKE IT PASS WRONGLY: a step that stopped for
// another reason — so the address is typed, and the case reads the frame's
// blocked line for the field's own label.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { createApiClient } from "@/api/client";
import type { CustomFieldRegistryEntry } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { NewConnectWizard } from "./NewConnectWizard";

const TENANT = "brazosbend";

const ROOF: CustomFieldRegistryEntry = {
  id: "cf-roof",
  key: "roof_material",
  label: "Roof Material",
  help_text: "",
  data_type: "text",
  options: [],
  is_required: true,
  display_order: 1,
  placement: { NEW_CONNECTION_PREMISE: "input" },
};

vi.mock("@/api/endpoints", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/endpoints")>()),
  getCustomFieldRegistry: async (params: { entity: string; screen?: string }) =>
    params.entity === "premises" && params.screen === "NEW_CONNECTION_PREMISE" ? [ROOF] : [],
}));

afterEach(cleanup);

function mountAtStep2() {
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: async () =>
      new Response(JSON.stringify({ count: 0, results: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/connections/new?step=2`]}>
          <Routes>
            <Route path="/:tenant/connections/new" element={<NewConnectWizard client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("DEF-CUS-9242 · a blank required property field holds step 2", () => {
  it("names the field on Continue and stays on step 2", async () => {
    const user = userEvent.setup();
    mountAtStep2();
    await screen.findByLabelText(/Roof Material/);
    await user.type(document.getElementById("nc_address") as HTMLInputElement, "14 Oak St");
    await user.click(screen.getByRole("button", { name: /continue/i }));
    const blocked = await screen.findByText("Fill in: Roof Material.");
    expect(blocked.closest('[data-wizard="blocked"]')).not.toBeNull();
    expect(screen.getByText(/Step 2 of/)).toBeInTheDocument();
  });

  it("an answered field lets the step ask its next question instead", async () => {
    const user = userEvent.setup();
    mountAtStep2();
    const roof = await screen.findByLabelText(/Roof Material/);
    await user.type(document.getElementById("nc_address") as HTMLInputElement, "14 Oak St");
    await user.type(roof, "Tile");
    await user.click(screen.getByRole("button", { name: /continue/i }));
    // The plan is still unchosen — the step's NEXT refusal, not the field's.
    await screen.findByText("Choose a plan for the units.");
    expect(screen.queryByText("Fill in: Roof Material.")).toBeNull();
  });
});
