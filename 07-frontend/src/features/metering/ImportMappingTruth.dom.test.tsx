// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  DEF-751 — BR-MET-117 (3) is served by the backend and rendered by
//          NOTHING. `mapping_spec.date_format`, `.column_problems` and
//          `.empty_columns` serialise, are covered by backend tests, are
//          declared in the OpenAPI schema — and `grep` found ZERO frontend
//          consumers of any of them, so for a user the feature did not exist.
//          CR-036 (i) — the utility that mapped `services_available`, saw
//          `Matched`, loaded 9,881 premises and got `No services` on every one
//          of them. MEASURED by exhaustion: no code drops a value; the only
//          input that produces this is an EMPTY CELL, and the run knew.
//          DEF-752 — `ImportTargetColumn` declared no `date_format` though the
//          server has always sent one, so nothing could read it and nothing
//          went red.
// Rules:   BR-MET-117 (3) (the format is shown at stage 2 and any column it
//          could not read is highlighted THERE) · BR-MET-085 (never invent a
//          figure the server has not sent) · B14 rule 21 (Tailwind)
// ───────────────────────────────────────────────────────
// ⚠ EVERY ASSERTION HERE READS RENDERED OUTPUT, and that is the point of the
// defect being fixed: DEF-751 is a value that EXISTS, is CORRECT, is typed and
// tested on the server, and reaches no screen. A test that checked a prop
// would have passed on the broken build.
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

const TEST_TENANT = "ottumwa-water-works";
const RUN_ID = "5f2b7c1e-0000-4000-8000-000000000751";
/** The PO's own two files. */
const LIVE_ROWS = 9_881;

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { status, data, etag: null, notModified: false };
}

function runDict(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    id: RUN_ID,
    run_no: "IMP-2026-000751",
    target: "premises",
    source_kind: "file",
    file_name: "ottumwa.csv",
    file_hash: "2f0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b8552",
    file_bytes: 1_400_000,
    encoding_delimiter: "UTF-8 · comma (detected)",
    mapping_id: null,
    mapping_spec: null,
    batch_label: null,
    write_mode: null,
    counts: { in: LIVE_ROWS, duplicates_dropped: 0, skipped: 0, forward: LIVE_ROWS },
    status: "extracted",
    session_ref: null,
    ip: null,
    started_at: "2026-08-26T09:00:00Z",
    finished_at: null,
    progress: null,
    ...overrides,
  };
}

function validated(overrides: Record<string, unknown>): Record<string, unknown> {
  return runDict({
    status: "validated",
    counts: {
      in: LIVE_ROWS,
      duplicates_dropped: 0,
      skipped: 0,
      forward: LIVE_ROWS,
      checked: LIVE_ROWS,
      clean: LIVE_ROWS,
      errors: 0,
      warnings: 0,
    },
    rules: [],
    rejects: [],
    blocking_rules: { count: 0, platform: 0, structural: 0 },
    ...overrides,
  });
}

/**
 * ONE stub, driven by a scenario. `columns` is what
 * `GET /imports/{id}/columns` serves (BR-MET-088 + `_with_date_format`), and
 * `spec` is what stage 2 stores on the run — the two independent sources the
 * screen reads, exactly as the server has them.
 */
function stubClient(scenario: {
  target: string;
  headers: string[];
  detected: Record<string, string>;
  columns: Record<string, unknown>[];
  spec: Record<string, unknown>;
}): ApiClient {
  const COLUMNS = {
    target: scenario.target,
    columns: [
      ...scenario.columns,
      { target: "__ignore__", label: "— ignore —", kind: "text", required: false, transforms: [] },
    ],
    unavailable_transforms: [],
    row_handling: ["drop_exact_duplicates", "keep_latest_on_key", "skip_rows_missing_required"],
  };
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      if (path === `/imports/${RUN_ID}/columns`) return ok(COLUMNS as T);
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string): Promise<ApiResponse<T>> => {
      if (path === "/imports") {
        return ok(
          runDict({
            target: scenario.target,
            headers: scenario.headers,
            detected_mapping: scenario.detected,
            warnings: [],
          }) as T,
          201,
        );
      }
      if (path === `/imports/${RUN_ID}/transform`) {
        return ok(
          runDict({ target: scenario.target, status: "transformed", mapping_spec: scenario.spec }) as T,
        );
      }
      if (path === `/imports/${RUN_ID}/validate`) {
        return ok(validated({ target: scenario.target, mapping_spec: scenario.spec }) as T);
      }
      throw new Error(`unstubbed POST ${path}`);
    },
  } as unknown as ApiClient;
}

function mount(client: ApiClient, target: "premises" | "units") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const home = target === "premises" ? "premises" : "premises/units";
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/${target}/import`]}>
          <Routes>
            <Route
              path={`/:tenant/${target}/import`}
              element={<ImportWorkflowPage target={target} client={client} />}
            />
            <Route path={`/:tenant/${home}`} element={<div>list</div>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function stageOf(container: HTMLElement): string | null {
  return container.querySelector('[data-workflow="runner"]')?.getAttribute("data-stage") ?? null;
}

function block(container: HTMLElement, id: string): HTMLElement | null {
  return container.querySelector<HTMLElement>(`[data-workflow="${id}"]`);
}

async function toStageTwo(user: ReturnType<typeof userEvent.setup>, container: HTMLElement) {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) throw new Error("stage 1 renders no file input");
  await user.upload(input, new File(["A,B\n1,2\n"], "ottumwa.csv", { type: "text/csv" }));
  const transform = await screen.findByRole("button", { name: "Transform →" });
  await waitFor(() => expect(transform).toBeEnabled());
  await user.click(transform);
  await waitFor(() => expect(stageOf(container)).toBe("2"));
}

async function toStageThree(user: ReturnType<typeof userEvent.setup>, container: HTMLElement) {
  await toStageTwo(user, container);
  await user.click(await screen.findByRole("button", { name: "Validate →" }));
  await waitFor(() => expect(stageOf(container)).toBe("3"), { timeout: 10_000 });
}

/** The PO's UNITS file: `plan_effective_from` carrying `1/1/2026`, US tenant. */
const UNITS = {
  target: "units",
  headers: ["PREMISE_NO", "UNIT_LABEL", "PLAN_START"],
  detected: { PREMISE_NO: "premises", UNIT_LABEL: "label", PLAN_START: "plan_effective_from" },
  columns: [
    { target: "premises", label: "Premise", kind: "premise_ref", required: true, transforms: [] },
    { target: "label", label: "Unit label", kind: "text", required: true, transforms: [] },
    {
      target: "plan_effective_from",
      label: "Plan effective from",
      kind: "date",
      required: false,
      transforms: [],
      date_format: "MM/DD/YYYY",
    },
  ],
  spec: { columns: {}, row_handling: {}, date_format: "MM/DD/YYYY", column_problems: [], empty_columns: [] },
};

/** The PO's PREMISES file: `services_available` mapped, Matched, and empty. */
const PREMISES = {
  target: "premises",
  headers: ["PREMISE_NO", "ADDRESS", "SERVICES_AVAILABLE"],
  detected: {
    PREMISE_NO: "premise_no",
    ADDRESS: "address_line",
    SERVICES_AVAILABLE: "services_available",
  },
  columns: [
    { target: "premise_no", label: "Premise ID", kind: "text", required: true, transforms: [] },
    { target: "address_line", label: "Address", kind: "text", required: true, transforms: [] },
    {
      target: "services_available",
      label: "Services available",
      kind: "list",
      required: false,
      transforms: ["split_on_comma"],
    },
  ],
  spec: {
    columns: {},
    row_handling: {},
    date_format: "MM/DD/YYYY",
    column_problems: [],
    empty_columns: [
      { source_column: "SERVICES_AVAILABLE", target: "services_available", rows: LIVE_ROWS },
    ],
  },
};

afterEach(cleanup);

describe("DEF-751 — BR-MET-117 (3) reaches a screen", () => {
  it("STAGE 2 states the format dates will be read as, and names the columns it will read", async () => {
    const user = userEvent.setup();
    const { container } = mount(stubClient(UNITS), "units");
    await toStageTwo(user, container);

    const declared = block(container, "date-format-declared");
    expect(declared, "stage 2 draws nothing about the date format").not.toBeNull();
    expect(declared).toHaveTextContent("MM/DD/YYYY");
    expect(block(container, "date-format-columns")).toHaveTextContent(
      "PLAN_START → Plan effective from",
    );
  });

  it("STAGE 2 says so when the utility has declared NO format — every dated row is refused", async () => {
    const user = userEvent.setup();
    const unset = {
      ...UNITS,
      columns: UNITS.columns.map((column) =>
        column.target === "plan_effective_from" ? { ...column, date_format: null } : column,
      ),
    };
    const { container } = mount(stubClient(unset), "units");
    await toStageTwo(user, container);

    const notice = block(container, "date-format-unset");
    expect(notice, "a tenant with no date format is told nothing").not.toBeNull();
    expect(notice).toHaveTextContent(/has not set a date format/i);
    expect(block(container, "date-format-declared")).toBeNull();
  });

  it("CR-036 (i) — STAGE 3 NAMES THE MAPPED COLUMN THAT IS EMPTY IN ALL 9,881 ROWS", async () => {
    const user = userEvent.setup();
    const { container } = mount(stubClient(PREMISES), "premises");
    await toStageThree(user, container);

    const notice = block(container, "empty-columns");
    expect(
      notice,
      "the server said services_available is empty in every row and no screen said it",
    ).not.toBeNull();
    expect(notice).toHaveTextContent("Services available");
    expect(notice).toHaveTextContent("SERVICES_AVAILABLE");
    expect(notice).toHaveTextContent("9881");
  });

  it("STAGE 3 names a mapped column it could NOT read, with the first row and a real cell", async () => {
    const user = userEvent.setup();
    const broken = {
      ...UNITS,
      spec: {
        ...UNITS.spec,
        column_problems: [
          {
            source_column: "PLAN_START",
            target: "plan_effective_from",
            rows: LIVE_ROWS,
            first_row: 2,
            example: "13/01/2026",
            problem: "Your date format is MM/DD/YYYY and 13/01/2026 does not match it.",
            fix_hint: "Write it as MM/DD/YYYY — 01/13/2026.",
          },
        ],
      },
    };
    const { container } = mount(stubClient(broken), "units");
    await toStageThree(user, container);

    const notice = block(container, "column-problems");
    expect(notice, "9,881 identical rejects and no word about the COLUMN").not.toBeNull();
    expect(notice).toHaveTextContent("Plan effective from");
    expect(notice).toHaveTextContent("13/01/2026");
    expect(notice).toHaveTextContent("row 2");
    expect(notice).toHaveTextContent("Your date format is MM/DD/YYYY");
  });

  it("STAGE 3 restates the format the run read its dates as", async () => {
    const user = userEvent.setup();
    const { container } = mount(stubClient(UNITS), "units");
    await toStageThree(user, container);
    expect(block(container, "date-format-used")).toHaveTextContent("MM/DD/YYYY");
  });

  it("says NOTHING when there is nothing to say — no empty column, no unreadable column", async () => {
    const user = userEvent.setup();
    const { container } = mount(stubClient(UNITS), "units");
    await toStageThree(user, container);
    expect(block(container, "empty-columns")).toBeNull();
    expect(block(container, "column-problems")).toBeNull();
  });
});
