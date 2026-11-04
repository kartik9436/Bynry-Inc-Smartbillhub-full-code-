// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 4, lane PARTS — images 35, 36, 37.
// Defects:  DEF-WRK-9574 (Issue log held over a live endpoint) · DEF-WRK-9578
//           (no edit) · DEF-WRK-9579 (no retire) · DEF-WRK-9580 (no filters) ·
//           DEF-WRK-9585 (library English on Add part; Description not Name)
// Rules:    B14 rules 2 · 6 (danger tier on Retire) · 13 (row actions are
//           icons) · 31 · 33 · hard-won law 2 (a hold's expiry test, mounted
//           under the real path pattern)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient, ApiResponse } from "@/api/client";

import { AddPartModal, editableCost } from "./AddPartModal";
import { PartsPage } from "./PartsPage";
import type { PartRow } from "./workEndpoints";

afterEach(() => cleanup());

type Call = { method: string; path: string; query: Record<string, unknown>; body: unknown };
const ok = (data: unknown) =>
  ({ status: 200, data, etag: null, notModified: false }) as ApiResponse<unknown>;

const SEAL: PartRow = {
  id: "p-seal",
  part_no: "SEAL-WIRE",
  name: "Meter seal, wire and tag",
  category: { id: "c-cons", name: "Consumables" },
  unit_of_measure: "each",
  unit_cost: "0.7500",
  active: true,
};
const PIPE: PartRow = {
  id: "p-pipe",
  part_no: "PIPE-CU34",
  name: 'Copper service pipe 3/4"',
  category: { id: "c-fit", name: "Fittings" },
  unit_of_measure: "ft",
  unit_cost: "3.1500",
  active: false,
};
const CATEGORIES = {
  count: 2,
  next: null,
  previous: null,
  results: [
    { id: "c-cons", code: "consumables", name: "Consumables", active: true, is_system: true, used_by: 1 },
    { id: "c-fit", code: "fittings", name: "Fittings", active: true, is_system: true, used_by: 1 },
  ],
};
const ISSUES = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: "i-1",
      part_id: "p-seal",
      part_no: "SEAL-WIRE",
      part_name: "Meter seal, wire and tag",
      qty: "-2.0000",
      unit_of_measure: "each",
      issued_to: "D. Ortiz",
      purpose: "Meter exchange",
      order_ref: "WO-0041",
      at: "2026-10-03T15:20:00Z",
      direction: "issue",
    },
  ],
};

function fakeClient(calls: Call[]): ApiClient {
  const write = (method: string) => async (path: string, body?: unknown) => {
    calls.push({ method, path, query: {}, body: body ?? null });
    return ok({ ...SEAL, ...(body as object) });
  };
  return {
    get: async (path: string, opts?: { query?: Record<string, unknown> }) => {
      calls.push({ method: "GET", path, query: opts?.query ?? {}, body: null });
      if (path === "/work/parts") {
        return ok({ count: 2, next: null, previous: null, results: [SEAL, PIPE], units: ["each", "ft"] });
      }
      if (path === "/work/parts/issues") return ok(ISSUES);
      if (path.startsWith("/lookups/")) return ok(CATEGORIES);
      throw new Error(`unexpected read: ${path}`);
    },
    post: write("POST"),
    patch: write("PATCH"),
    put: write("PUT"),
    del: write("DELETE"),
    request: write("REQUEST"),
  } as unknown as ApiClient;
}

function mount(calls: Call[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/brazosbend/work/parts"]}>
        <Routes>
          <Route path="/:tenant/work/parts" element={<PartsPage client={fakeClient(calls)} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CR-168 Parts — the register (image 35)", () => {
  it("ruling 32: the second column is Name, never Description", async () => {
    mount([]);
    await screen.findByText("SEAL-WIRE");
    const headers = screen.getAllByRole("columnheader").map((th) => th.textContent ?? "");
    expect(headers.some((h) => /^Name/.test(h))).toBe(true);
    expect(headers.some((h) => /Description/.test(h))).toBe(false);
    expect(screen.getByPlaceholderText("Search part #, name…")).toBeInTheDocument();
  });

  it("DEF-WRK-9574 (hold expiry): Issue log is a live segment and opens the log", async () => {
    const calls: Call[] = [];
    mount(calls);
    await screen.findByText("SEAL-WIRE");
    expect(screen.queryByText("Arrives with parts on jobs.")).not.toBeInTheDocument();
    const segment = document.querySelector('[data-segment="issues"]') as HTMLElement;
    expect(segment).not.toHaveAttribute("data-segment-disabled", "true");
    await userEvent.click(segment);
    await screen.findByText("WO-0041");
    expect(screen.getByText("D. Ortiz")).toBeInTheDocument();
    // P1.18 — a quantity without four trailing zeros.
    expect(screen.getByText("-2 each")).toBeInTheDocument();
    expect(calls.some((c) => c.path === "/work/parts/issues")).toBe(true);
  });

  it("DEF-WRK-9578: the pencil opens the part's own values and saves them with PATCH", async () => {
    const calls: Call[] = [];
    mount(calls);
    await screen.findByText("SEAL-WIRE");
    await userEvent.click(screen.getByTestId("edit-part-SEAL-WIRE"));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Edit a part")).toBeInTheDocument();
    const name = within(dialog).getByLabelText(/^Name/);
    expect(name).toHaveValue("Meter seal, wire and tag");
    expect(within(dialog).getByLabelText(/^Unit cost/)).toHaveValue("0.75");
    await userEvent.clear(name);
    await userEvent.type(name, "Meter seal, wire");
    await userEvent.click(within(dialog).getByRole("button", { name: /Save part/ }));
    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch?.path).toBe("/work/parts/p-seal");
    expect(patch?.body).toMatchObject({ name: "Meter seal, wire", unit_cost: "0.75", category: "Consumables" });
  });

  it("DEF-WRK-9579: Retire asks first on the danger tier, then switches the part off", async () => {
    const calls: Call[] = [];
    mount(calls);
    await screen.findByText("SEAL-WIRE");
    await userEvent.click(screen.getByTestId("retire-part-SEAL-WIRE"));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText("Retire SEAL-WIRE?")).toBeInTheDocument();
    expect(within(dialog).getByText("Crews can no longer pick it. Past jobs keep it.")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "PATCH")).toBe(false);
    await userEvent.click(within(dialog).getByRole("button", { name: /Retire part/ }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === "PATCH")).toMatchObject({
        path: "/work/parts/p-seal",
        body: { active: false },
      }),
    );
  });

  it("DEF-WRK-9579: an inactive part is reactivated in one press", async () => {
    const calls: Call[] = [];
    mount(calls);
    await screen.findByText("PIPE-CU34");
    await userEvent.click(screen.getByTestId("reactivate-part-PIPE-CU34"));
    await waitFor(() =>
      expect(calls.find((c) => c.method === "PATCH")).toMatchObject({
        path: "/work/parts/p-pipe",
        body: { active: true },
      }),
    );
  });

  it("DEF-WRK-9580: Category, Unit and Status filter the register on the server", async () => {
    const calls: Call[] = [];
    mount(calls);
    await screen.findByText("SEAL-WIRE");
    await userEvent.click(screen.getByText("+ Filter"));
    const legends = Array.from(document.querySelectorAll("legend")).map((l) => l.textContent);
    expect(legends).toEqual(["Category", "Unit", "Status"]);
    // The register's own units and the tenant's own categories — names, never ids.
    expect(screen.getByLabelText("ft")).toBeInTheDocument();
    expect(screen.getByLabelText("Consumables")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Inactive"));
    await waitFor(() =>
      expect(
        calls.some((c) => c.path === "/work/parts" && c.query["f.status"] === "inactive"),
      ).toBe(true),
    );
    await userEvent.click(screen.getByLabelText("Fittings"));
    await waitFor(() =>
      expect(
        calls.some((c) => c.path === "/work/parts" && c.query["f.category"] === "fittings"),
      ).toBe(true),
    );
  });
});

describe("CR-168 Add a part (images 36, 37) — DEF-WRK-9585", () => {
  function mountForm() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={queryClient}>
        <AddPartModal client={fakeClient([])} onClose={() => undefined} onAdded={() => undefined} />
      </QueryClientProvider>,
    );
  }

  it("draws Name, the drawn help lines and Add part ✓", () => {
    mountForm();
    expect(screen.getByLabelText(/^Name/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/^Description/)).not.toBeInTheDocument();
    expect(screen.getByText("How you count it — each, meter, box.")).toBeInTheDocument();
    expect(screen.getByText("In dollars, like 92.40.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add part ✓" })).toBeInTheDocument();
  });

  it("an empty form is refused in the clerk's words, never the library's", async () => {
    mountForm();
    await userEvent.click(screen.getByRole("button", { name: "Add part ✓" }));
    expect(await screen.findAllByText("This is required.")).toHaveLength(3);
    expect(screen.getByText("Unit cost must be a number.")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/String must contain|Invalid/);
  });

  it("a fifth decimal is refused by its own sentence", async () => {
    mountForm();
    await userEvent.type(screen.getByLabelText(/^Unit cost/), "92.40004");
    await userEvent.click(screen.getByRole("button", { name: "Add part ✓" }));
    expect(await screen.findByText("Keep unit cost to 4 decimals.")).toBeInTheDocument();
  });

  it("the stored four places come back as a person types them", () => {
    expect(editableCost("92.4000")).toBe("92.40");
    expect(editableCost("8.9375")).toBe("8.9375");
    expect(editableCost("0.4500")).toBe("0.45");
    expect(editableCost("12.0000")).toBe("12.00");
  });
});
