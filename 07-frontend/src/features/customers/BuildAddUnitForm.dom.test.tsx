// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-9219 — the request's Add unit form (found by the New
//           Connection end-to-end walk, CON-26-0129, 2026-10-02): Unit type was
//           a free-text box while step 3 offers the utility's own list, and
//           pressing Add unit with no service ticked did nothing and said
//           nothing.
// ───────────────────────────────────────────────────────
//
// WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2)
// * Asserting a <select> exists without its OPTIONS — the case reads the
//   utility's own names, served by the stubbed lookup.
// * Asserting "nothing was posted" for the empty press — a form that silently
//   does nothing passes that; the case reads the sentence the clerk gets.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { createApiClient } from "@/api/client";

import { BuildAddUnitForm, servicesOfThisBuild } from "./BuildLifecycleForms";

const t = (key: string, params?: Record<string, unknown>) => String(params?.defaultValue ?? key);

function client() {
  return createApiClient({
    tenant: "lakeside",
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("/lookups/unit_types")
        ? {
            results: [
              { code: "residential", name: "Residential", active: true },
              { code: "commercial", name: "Commercial", active: true },
              { code: "common_area", name: "Common area", active: true },
            ],
            count: 3,
          }
        : {};
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
}

function mount(saved: unknown[]) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <BuildAddUnitForm
        t={t}
        services={[
          { code: "electric", name: "Electric" },
          { code: "water", name: "Water" },
        ] as never}
        client={client()}
        onClose={() => undefined}
        onSave={async (body) => {
          saved.push(body);
        }}
      />
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("Add unit (DEF-CUS-9219)", () => {
  it("offers the utility's own unit types, without Common area", async () => {
    mount([]);
    const select = (await screen.findByLabelText("Unit type")) as HTMLSelectElement;
    expect(select.tagName).toBe("SELECT");
    await waitFor(() =>
      expect([...select.options].map((o) => o.textContent)).toEqual([
        "Choose a unit type",
        "Residential",
        "Commercial",
      ]),
    );
  });

  it("says why when Add unit is pressed with no service ticked", async () => {
    const saved: unknown[] = [];
    mount(saved);
    fireEvent.change(document.getElementById("label") as HTMLElement, { target: { value: "9" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add unit" }).at(-1) as HTMLElement);
    expect(await screen.findByText("Choose at least one service.")).toBeInTheDocument();
    expect(saved).toEqual([]);
  });

  it("sends the unit type's CODE with the ticked services", async () => {
    const saved: unknown[] = [];
    mount(saved);
    fireEvent.change(document.getElementById("label") as HTMLElement, { target: { value: "9" } });
    const select = (await screen.findByLabelText("Unit type")) as HTMLSelectElement;
    await waitFor(() => expect(select.options.length).toBe(3));
    fireEvent.change(select, { target: { value: "residential" } });
    fireEvent.click(screen.getByLabelText("Electric"));
    fireEvent.click(screen.getAllByRole("button", { name: "Add unit" }).at(-1) as HTMLElement);
    await waitFor(() =>
      expect(saved).toEqual([{ label: "9", unit_type: "residential", services: ["electric"] }]),
    );
  });
});

// ⊕ DEF-MET-9262 — Add unit offers the BUILD's services; a new one is Add service's.
describe("DEF-MET-9262 — Add unit offers only the services this build carries", () => {
  it("keeps the build's services, in the utility's order and names", () => {
    const all = [
      { code: "electric", name: "Electric" },
      { code: "water", name: "Water" },
      { code: "solar", name: "Solar" },
      { code: "battery", name: "Battery" },
    ];
    expect(servicesOfThisBuild(all, ["battery", "solar"])).toEqual([
      { code: "solar", name: "Solar" },
      { code: "battery", name: "Battery" },
    ]);
  });
});
