// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-PAY-10779 — Save mapping as template was disabled ("not
//          available yet") though the server could save and re-apply a map.
// Ruling:  decision log 2026-10-30 "Eight open payment questions answered
//          (PO)" — Q7 = A: saved column layout per source; "Save mapping as
//          template" switched on with a name; applied automatically when a
//          file's headers match.
// ───────────────────────────────────────────────────────
// The worked case: this week the clerk maps the Hy-Vee file and saves it as
// "Hy-Vee weekly"; next week the same header row arrives, the server
// recognises it, and the mapping step says which template it used.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { ImportWorkflowPage } from "./ImportWorkflowPage";

const TENANT = "silvercreek";
const RUN_ID = "5f2b7c1e-0000-4000-8000-0000000000aa";
const CSV_TEXT =
  "Store Acct,Paid,Txn Date,Receipt,Network\nAC-1,253.00,2026-10-22,HV-1,Hy-Vee\n";
const HEADERS = ["Store Acct", "Paid", "Txn Date", "Receipt", "Network"];

function runDict(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    id: RUN_ID,
    run_no: "IMP-261030-07",
    target: "payments",
    source_kind: "file",
    file_name: "hyvee.csv",
    file_hash: "ab",
    file_bytes: CSV_TEXT.length,
    encoding_delimiter: "UTF-8 · comma (detected)",
    mapping_id: null,
    mapping_spec: null,
    batch_label: null,
    write_mode: "insert",
    counts: { in: 1, duplicates_dropped: 0, skipped: 0, forward: 0 },
    status: "extracted",
    session_ref: null,
    ip: null,
    started_at: "2026-10-30T09:00:00Z",
    finished_at: null,
    ...overrides,
  };
}

const COLUMNS = {
  target: "payments",
  columns: [
    { target: "account_ref", label: "Account #", kind: "text", required: false, transforms: [] },
    { target: "amount", label: "Amount", kind: "decimal", required: true, transforms: [] },
    { target: "paid_on", label: "Date paid", kind: "date", required: false, transforms: [] },
    { target: "reference", label: "Reference", kind: "text", required: false, transforms: [] },
    { target: "network", label: "Network", kind: "text", required: false, transforms: [] },
    { target: "__ignore__", label: "— ignore —", kind: "text", required: false, transforms: [] },
  ],
  unavailable_transforms: [],
  row_handling: ["drop_exact_duplicates", "keep_latest_on_key", "skip_rows_missing_required"],
};

interface Call {
  method: string;
  path: string;
  body?: unknown;
}

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { status, data, etag: null, notModified: false };
}

function stub(calls: Call[], recognised: { id: string; name: string } | null): ApiClient {
  const extracted = runDict({
    headers: HEADERS,
    detected_mapping: {
      "Store Acct": "account_ref",
      Paid: "amount",
      "Txn Date": "paid_on",
      Receipt: "reference",
      Network: "network",
    },
    recognised_template: recognised === null ? null : { ...recognised, is_system: false },
    warnings: [],
  });
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "GET", path });
      if (path === `/imports/${RUN_ID}/columns`) return ok(COLUMNS as T);
      if (path === "/lookups/import_mappings") {
        return ok({
          count: 2,
          results: [
            { id: "m1", code: "hy_vee_weekly", name: "Hy-Vee weekly", active: true, is_system: false, used_by: 0, target: "payments" },
            { id: "m2", code: "meters_default", name: "Meters default", active: true, is_system: true, used_by: 0, target: "assets_meters" },
          ],
        } as T);
      }
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string, body?: unknown): Promise<ApiResponse<T>> => {
      calls.push({ method: "POST", path, body });
      if (path === "/imports") return ok(extracted as T, 201);
      if (path === `/imports/${RUN_ID}/transform`) {
        return ok(runDict({ status: "transformed", counts: { in: 1, duplicates_dropped: 0, skipped: 0, forward: 1 } }) as T);
      }
      if (path === `/imports/${RUN_ID}/save-mapping`) {
        const name = (body as { name: string }).name;
        return ok({ id: "m9", code: "x", name, target: "payments", is_system: false, column_count: 5 } as T, 201);
      }
      if (path === `/imports/${RUN_ID}/validate`) {
        return ok(runDict({ status: "validated", rules: [], rejects: [], counts: { in: 1, duplicates_dropped: 0, skipped: 0, forward: 1, checked: 1, clean: 1, errors: 0, warnings: 0 } }) as T);
      }
      throw new Error(`unstubbed POST ${path}`);
    },
  } as unknown as ApiClient;
}

function mount(client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/payments/imports/new`]}>
          <Routes>
            <Route
              path="/:tenant/payments/imports/new"
              element={<ImportWorkflowPage target="payments" client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function stageOf(container: HTMLElement): string | null {
  return container.querySelector('[data-workflow="runner"]')?.getAttribute("data-stage") ?? null;
}

async function upload(user: ReturnType<typeof userEvent.setup>, container: HTMLElement) {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) throw new Error("no file input");
  await user.upload(input, new File([CSV_TEXT], "hyvee.csv", { type: "text/csv" }));
  const transform = await screen.findByRole("button", { name: "Transform →" });
  await waitFor(() => expect(transform).toBeEnabled());
  await user.click(transform);
  await waitFor(() => expect(stageOf(container)).toBe("2"));
}

afterEach(cleanup);

describe("DEF-PAY-10779 — Save mapping as template, switched on with a name (Q7)", () => {
  it("step 1 offers this target's saved templates and no 'not available yet'", async () => {
    const calls: Call[] = [];
    const { container } = mount(stub(calls, null));
    await waitFor(() =>
      expect(container.querySelector("#import-mapping")?.textContent ?? "").toContain(
        "Hy-Vee weekly",
      ),
    );
    expect(container.querySelector("#import-mapping")?.textContent ?? "").not.toContain(
      "Meters default",
    );
    expect(container.textContent).not.toContain("not available yet");
  });

  it("this week: tick it, name it 'Hy-Vee weekly', Validate saves the whole map", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    const { container } = mount(stub(calls, null));
    await upload(user, container);

    const box = screen.getByRole("checkbox", { name: "Save mapping as template" });
    expect(box).toBeEnabled();
    await user.click(box);
    // Switched on with no name — Validate waits for one.
    const validate = screen.getByRole("button", { name: "Validate →" });
    expect(validate).toBeDisabled();
    expect(container.textContent).toContain("Name the template.");
    await user.type(screen.getByLabelText(/Template name/), "Hy-Vee weekly");
    await waitFor(() => expect(validate).toBeEnabled());
    await user.click(validate);
    await waitFor(() => expect(stageOf(container)).toBe("3"));

    const save = calls.find((call) => call.path === `/imports/${RUN_ID}/save-mapping`);
    expect(save?.body).toEqual({
      name: "Hy-Vee weekly",
      mapping: {
        "Store Acct": "account_ref",
        Paid: "amount",
        "Txn Date": "paid_on",
        Receipt: "reference",
        Network: "network",
      },
    });
    // Saved AFTER the mapping was accepted, never before.
    const order = calls.map((call) => call.path);
    expect(order.indexOf(`/imports/${RUN_ID}/transform`)).toBeLessThan(
      order.indexOf(`/imports/${RUN_ID}/save-mapping`),
    );
    expect(container.textContent).toContain("Template Hy-Vee weekly saved.");
  });

  it("next week: the same headers are mapped with the template, and the step says so", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    const { container } = mount(stub(calls, { id: "m1", name: "Hy-Vee weekly" }));
    await upload(user, container);
    expect(
      container.querySelector('[data-workflow="template-used"]')?.textContent ?? "",
    ).toContain("Mapped with template Hy-Vee weekly.");
    // Nothing is saved unless the clerk asks.
    await user.click(screen.getByRole("button", { name: "Validate →" }));
    await waitFor(() => expect(stageOf(container)).toBe("3"));
    expect(calls.some((call) => call.path.endsWith("/save-mapping"))).toBe(false);
  });
});
