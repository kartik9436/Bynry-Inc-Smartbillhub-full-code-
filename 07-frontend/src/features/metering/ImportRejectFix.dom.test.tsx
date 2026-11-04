// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-036 amendment 1 (b) — PO on a live deployment, verbatim:
//          *"am not able to press the fix button"*. 9,881 units rejected, the
//          stage-3 table drew `Fix here…` on every row under the caption
//          *"Fix the rejects here — no need to re-upload"*, and the control
//          did nothing an operator could see.
// Rules:   CR-016 (plain English) · B14 rule 21 (Tailwind)
// ───────────────────────────────────────────────────────
// ⚠ THIS SUITE DRIVES THE WHOLE PAGE, NOT THE COMPONENT. RejectListFix.dom
// already proves the editor opens when RejectList is rendered on its own with
// ONE reject; it passed all along and told us nothing about the live screen.
// The live screen is a BACKGROUND run (9,881 > ASYNC_ROW_BAR) whose rejects
// arrive from the POLL, and the reject count is four figures.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { ImportWorkflowPage } from "./ImportWorkflowPage";

const TEST_TENANT = "silvercreek";
const RUN_ID = "5f2b7c1e-0000-4000-8000-000000000042";
const JOB_ID = "9a1c0000-0000-4000-8000-0000000000aa";

/** The PO's own file: 9,881 unit rows, every one rejected. */
const LIVE_ROWS = 9_881;
const CSV_TEXT = "PREMISE_NO,LABEL,MOVE_IN\nP-1,Apt 1,1/1/2026\n";

function runDict(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    id: RUN_ID,
    run_no: "IMP-2026-000042",
    target: "units",
    source_kind: "file",
    file_name: "units.csv",
    file_hash: "1f0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b8551",
    file_bytes: 1_200_000,
    encoding_delimiter: "UTF-8 · comma (detected)",
    mapping_id: null,
    mapping_spec: null,
    batch_label: null,
    write_mode: null,
    counts: { in: LIVE_ROWS, duplicates_dropped: 0, skipped: 0, forward: 0 },
    status: "extracted",
    session_ref: null,
    ip: null,
    started_at: "2026-08-26T09:00:00Z",
    finished_at: null,
    progress: null,
    ...overrides,
  };
}

function gauge(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    stage: "transform",
    done: 0,
    total: LIVE_ROWS,
    state: "queued",
    message: null,
    job_id: JOB_ID,
    pct: 0,
    updated_at: "2026-08-26T09:00:02Z",
    ...overrides,
  };
}

const EXTRACTED = runDict({
  headers: ["PREMISE_NO", "LABEL", "MOVE_IN"],
  detected_mapping: { PREMISE_NO: "premise_no", LABEL: "label" },
  warnings: [],
});

const COLUMNS = {
  target: "units",
  columns: [
    {
      target: "premise_no",
      label: "Premise ID",
      kind: "text",
      required: true,
      transforms: ["trim_whitespace"],
    },
    { target: "label", label: "Unit label", kind: "text", required: true, transforms: [] },
    { target: "__ignore__", label: "— ignore —", kind: "text", required: false, transforms: [] },
  ],
  unavailable_transforms: [],
  row_handling: ["drop_exact_duplicates", "keep_latest_on_key", "skip_rows_missing_required"],
};

/** `import_runs.rejects()`, key for key — including `raw`. */
function rejectRows(count: number): Record<string, unknown>[] {
  return Array.from({ length: count }, (_unused, index) => ({
    row_no: index + 1,
    source_key: `P-${11_000 + index}`,
    problem: "1/1/2026 is not a date this import can read.",
    fix_hint: "Use YYYY-MM-DD — 2026-04-01.",
    outcome: "rejected",
    raw: {
      PREMISE_NO: `P-${11_000 + index}`,
      LABEL: `Apt ${index + 1}`,
      MOVE_IN: "1/1/2026",
    },
  }));
}

function deferred(stage: string, progress: Record<string, unknown>): Record<string, unknown> {
  return runDict({
    progress,
    deferred: true,
    stage,
    job_id: JOB_ID,
    status_url: `/api/jobs/${JOB_ID}`,
  });
}

/** The PO's screen: every row rejected by one tier-2 rule. */
function validatedRun(
  progress: Record<string, unknown>,
  rejectCount: number,
): Record<string, unknown> {
  return runDict({
    counts: {
      in: LIVE_ROWS,
      duplicates_dropped: 0,
      forward: LIVE_ROWS,
      checked: LIVE_ROWS,
      clean: 0,
      errors: rejectCount,
      warnings: 0,
    },
    status: "validated",
    progress,
    rules: [
      {
        code: "kinds.value_kind",
        tier: 2,
        sentence: "Every value has to be the kind of value its column holds",
        severity: "error",
        action: "reject_row",
        action_value: null,
        hits: rejectCount,
        available: true,
        unavailable_reason: null,
      },
    ],
    rejects: rejectRows(rejectCount),
    blocking_rules: { count: 1, platform: 0, structural: 0 },
  });
}

interface RecordedCall {
  method: "GET" | "POST" | "PATCH";
  path: string;
}

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { status, data, etag: null, notModified: false };
}

function stubClient(rejectCount: number, calls: RecordedCall[]): ApiClient {
  let stage = "transform";
  const poll: Record<string, Record<string, unknown>> = {
    transform: runDict({
      counts: { in: LIVE_ROWS, duplicates_dropped: 0, forward: LIVE_ROWS },
      status: "transformed",
      progress: gauge({ state: "done", done: LIVE_ROWS, pct: 100 }),
    }),
    validate: validatedRun(
      gauge({ stage: "validate", state: "done", done: LIVE_ROWS, pct: 100 }),
      rejectCount,
    ),
  };
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "GET", path });
      if (path === `/imports/${RUN_ID}/columns`) return ok(COLUMNS as T);
      if (path === `/imports/${RUN_ID}`) return ok(poll[stage] as T);
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "POST", path });
      if (path === "/imports") return ok(EXTRACTED as T, 201);
      if (path === `/imports/${RUN_ID}/transform`) {
        stage = "transform";
        return ok(deferred("transform", gauge({ state: "queued" })) as T, 202);
      }
      if (path === `/imports/${RUN_ID}/validate`) {
        stage = "validate";
        return ok(
          deferred("validate", gauge({ stage: "validate", state: "queued" })) as T,
          202,
        );
      }
      throw new Error(`unstubbed POST ${path}`);
    },
    patch: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "PATCH", path });
      return ok(runDict({ status: "extracted" }) as T);
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
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/units/import`]}>
          <Routes>
            <Route
              path="/:tenant/units/import"
              element={<ImportWorkflowPage target="units" client={client} />}
            />
            <Route path="/:tenant/premises" element={<div>premises list</div>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function stageOf(container: HTMLElement): string | null {
  return container.querySelector('[data-workflow="runner"]')?.getAttribute("data-stage") ?? null;
}

async function runToRejects(
  user: ReturnType<typeof userEvent.setup>,
  container: HTMLElement,
) {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) throw new Error("stage 1 renders no file input");
  await user.upload(input, new File([CSV_TEXT], "units.csv", { type: "text/csv" }));
  const transform = await screen.findByRole("button", { name: "Transform →" });
  await waitFor(() => expect(transform).toBeEnabled());
  await user.click(transform);
  await waitFor(() => expect(stageOf(container)).toBe("2"));
  await user.click(await screen.findByRole("button", { name: "Validate →" }));
  await waitFor(() => expect(stageOf(container)).toBe("3"), { timeout: 10_000 });
  await waitFor(
    () => expect(container.querySelectorAll("[data-workflow-reject]").length).toBeGreaterThan(0),
    { timeout: 10_000 },
  );
}

afterEach(cleanup);

describe("CR-036 (b) — the fix button on a BACKGROUND run's rejects", () => {
  it("three rejects: the editor opens and the operator's own cells render", async () => {
    const calls: RecordedCall[] = [];
    const user = userEvent.setup();
    const { container } = mount(stubClient(3, calls));
    await runToRejects(user, container);

    const buttons = screen.getAllByRole("button", { name: "Fix here…" });
    expect(buttons).toHaveLength(3);
    await user.click(buttons[0]);
    // RENDERED OUTPUT, not a prop: the row's own cells, labelled by the
    // operator's file headers, with the value the file actually holds.
    await waitFor(() =>
      expect(container.querySelector("[data-workflow-fix-editor]")).not.toBeNull(),
    );
    expect(screen.getByLabelText("MOVE_IN")).toHaveValue("1/1/2026");

    // ⚠ **AND THE SAVE IS LIVE ON A BACKGROUND RUN.** The other candidate for
    // *"am not able to press the fix button"* was
    // `fixing={fixRow.isPending || transform.isPending || validate.isPending}`
    // holding the save down for a run that is in a worker. It does not: a
    // deferred stage answers 202 immediately, so both mutations settle long
    // before stage 3 draws, and this asserts it on the rendered control rather
    // than by reading the expression.
    fireEvent.change(screen.getByLabelText("MOVE_IN"), { target: { value: "2026-01-01" } });
    const save = screen.getByRole("button", { name: "Save & re-check" });
    expect(save).toBeEnabled();
    fireEvent.click(save);
    await waitFor(() =>
      expect(
        calls.filter(
          (call) => call.method === "PATCH" && call.path === `/imports/${RUN_ID}/rows/1`,
        ),
      ).toHaveLength(1),
    );
  }, 30_000);

  it("THE LIVE RUN — 9,881 rejects: ONE page renders, and the fix button acts", async () => {
    const calls: RecordedCall[] = [];
    const user = userEvent.setup();
    const { container } = mount(stubClient(LIVE_ROWS, calls));
    await runToRejects(user, container);

    // ⚠ THE MEASURED DEFECT. Before CR-036 (b) this was 9,881 rows and 9,881
    // buttons — ~60,000 nodes in one auto-layout table — and every one of them
    // re-rendered on the click that opens the editor.
    const rows = container.querySelectorAll("[data-workflow-reject]");
    expect(rows).toHaveLength(50);
    const buttons = container.querySelectorAll<HTMLButtonElement>(
      "[data-workflow-reject] button",
    );
    expect(buttons).toHaveLength(50);
    // The operator can still SEE that nine thousand rows were rejected.
    expect(screen.getByText("1–50 of 9881")).toBeInTheDocument();

    const t0 = Date.now();
    fireEvent.click(buttons[0]);
    // eslint-disable-next-line no-console
    console.log(`[measure] click + re-render at 50 rows = ${Date.now() - t0}ms`);
    expect(container.querySelector("[data-workflow-fix-editor]")).not.toBeNull();
    expect(screen.getByLabelText("MOVE_IN")).toHaveValue("1/1/2026");

    // ⚠ **AND THE IMPATIENT SECOND CLICK.** This is the assertion that was
    // RED on the shipped screen and stayed RED after pagination alone: at
    // 9,881 rows the first click took 1,114 ms to re-render, the operator
    // clicked again, and the old toggle CLOSED the editor. Measured, both
    // ways, in `RejectList`'s docstring.
    fireEvent.click(buttons[0]);
    // Asserted after EACH click: an even number of toggles lands back on
    // "open", so a test that only looked at the end would pass over it.
    expect(container.querySelector("[data-workflow-fix-editor]")).not.toBeNull();
    fireEvent.click(buttons[0]);
    expect(container.querySelector("[data-workflow-fix-editor]")).not.toBeNull();
    expect(screen.getByLabelText("MOVE_IN")).toHaveValue("1/1/2026");
  }, 300_000);
});

// ═══════════════════════════════════════════════════════════════════════════
// DEF-766 — THE PAYLOAD, NOT THE TABLE
// ═══════════════════════════════════════════════════════════════════════════
/**
 * The suite above proved the TABLE draws fifty rows. It could not see what the
 * SERVER sent, and the server was sending all 9,881 — with each row's full
 * `raw` cells — **every two seconds**, because `GET /imports/{id}` is the poll
 * surface and `rejects()` was unbounded: 4.28 MB per poll, measured on the PO's
 * own run, to draw a fifty-row table.
 *
 * So this stub answers what a bounded server answers: fifty rejects and a
 * `rejects_window` stating the true total. Under the old screen that payload
 * would draw *"1–50 of 50"* — the operator loses the only figure that tells
 * them how bad the file is — and page two would be unreachable.
 */
const ALL_REJECTS = rejectRows(LIVE_ROWS);

function windowedValidatedRun(
  progress: Record<string, unknown>,
  offset: number,
  limit: number,
): Record<string, unknown> {
  const run = validatedRun(progress, LIVE_ROWS);
  return {
    ...run,
    rejects: ALL_REJECTS.slice(offset, offset + limit),
    rejects_window: { total: LIVE_ROWS, offset, limit },
  };
}

/** `stubClient`, plus the reject window the poll surface now takes. */
function windowedClient(calls: RecordedCall[]): ApiClient {
  let stage = "transform";
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "GET", path });
      if (path === `/imports/${RUN_ID}/columns`) return ok(COLUMNS as T);
      const [route, query] = path.split("?");
      if (route === `/imports/${RUN_ID}`) {
        if (stage === "transform") {
          return ok(
            runDict({
              counts: { in: LIVE_ROWS, duplicates_dropped: 0, forward: LIVE_ROWS },
              status: "transformed",
              progress: gauge({ state: "done", done: LIVE_ROWS, pct: 100 }),
            }) as T,
          );
        }
        const params = new URLSearchParams(query ?? "");
        const offset = Number(params.get("reject_offset") ?? 0);
        const limit = Number(params.get("reject_limit") ?? 50);
        return ok(
          windowedValidatedRun(
            gauge({ stage: "validate", state: "done", done: LIVE_ROWS, pct: 100 }),
            offset,
            limit,
          ) as T,
        );
      }
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "POST", path });
      if (path === "/imports") return ok(EXTRACTED as T, 201);
      if (path === `/imports/${RUN_ID}/transform`) {
        stage = "transform";
        return ok(deferred("transform", gauge({ state: "queued" })) as T, 202);
      }
      if (path === `/imports/${RUN_ID}/validate`) {
        stage = "validate";
        return ok(deferred("validate", gauge({ stage: "validate", state: "queued" })) as T, 202);
      }
      throw new Error(`unstubbed POST ${path}`);
    },
    patch: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "PATCH", path });
      return ok(runDict({ status: "extracted" }) as T);
    },
  } as unknown as ApiClient;
}

describe("DEF-766 — fifty rejects on the wire, nine thousand on the footer", () => {
  it("draws the SERVER's window and still counts the whole run", async () => {
    const calls: RecordedCall[] = [];
    const user = userEvent.setup();
    const { container } = mount(windowedClient(calls));
    await runToRejects(user, container);

    // The payload carried fifty. The screen draws fifty.
    expect(container.querySelectorAll("[data-workflow-reject]")).toHaveLength(50);
    // ⚠ AND THE TOTAL IS THE SERVER'S. `rejects.length` is 50 here, so a screen
    // that counted its own array would print "1–50 of 50" and tell an operator
    // whose file failed entirely that fifty rows had a problem.
    expect(screen.getByText("1–50 of 9881")).toBeInTheDocument();

    // The fix control still opens on a served row — the window carries `raw`.
    fireEvent.click(
      container.querySelectorAll<HTMLButtonElement>("[data-workflow-reject] button")[0],
    );
    expect(screen.getByLabelText("MOVE_IN")).toHaveValue("1/1/2026");
  }, 300_000);

  it("page two is a REQUEST — the rows beyond the window are still reachable", async () => {
    const calls: RecordedCall[] = [];
    const user = userEvent.setup();
    const { container } = mount(windowedClient(calls));
    await runToRejects(user, container);

    await user.click(screen.getByRole("button", { name: "Next page" }));
    // ⚠ **BUILT IS NOT WIRED (law 2).** The window exists server-side and the
    // component takes a `serverPage` prop; this is the assertion that the page
    // actually ASKS. Without it a pager click would slice a fifty-row array and
    // draw nothing.
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === "GET" &&
            call.path === `/imports/${RUN_ID}?reject_offset=50&reject_limit=50`,
        ),
      ).toBe(true),
    );
    await waitFor(() =>
      expect(
        container.querySelectorAll("[data-workflow-reject]")[0]?.getAttribute(
          "data-workflow-reject",
        ),
      ).toBe("51"),
    );
    expect(screen.getByText("51–100 of 9881")).toBeInTheDocument();
  }, 300_000);
});
