// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-026 second half — the screen that draws a background import's
//          progress (PO 2026-08-22) · BR-MET-102 (PO 2026-08-22, "No")
// Screens: WFL-01.premises.2-4 (the stage rail)
// Rules:   BR-MET-085 (the counts on screen are the SERVER's — nothing is
//          invented) · BR-MET-090 (the gauge is not the run's record) ·
//          BR-MET-102 (a running import CANNOT be cancelled and NO cancel
//          control is drawn — not even a disabled one)
// ───────────────────────────────────────────────────────
// ⚠ **THE FIRST CASE BELOW IS THE ONE THAT MATTERS MOST, AND IT ASSERTS AN
// ABSENCE.** CR-026 made every import answer carry a `progress` field. The
// failure mode that costs a customer something is not a missing progress bar on
// a 50,000-row file — they would report that. It is a progress bar appearing on
// a THREE-ROW file, where `progress` is `null`, nothing is running, and the
// screen suddenly grows a component that says a background worker is involved.
// Nobody reports that as a bug; they just trust the screen slightly less. So the
// small-file case is pinned first and by name.
//
// ⚠ **AND THE LAST CASE ASSERTS AN ABSENCE THE PRODUCT OWNER RULED
// (`BR-MET-102`, verbatim: *"No"*).** There is no cancel control on a running
// import and there must not be a DISABLED one either. That is precisely the
// kind of rule a later well-meaning lane violates by adding a helpful greyed-out
// button, so something has to check it. This is that something.
//
// ⚠ **THE STUB SERVES THE SERVER'S REAL SHAPES.** `_defer()`'s answer is
// `run_dict(run)` + `deferred` + `stage` + `job_id` + `status_url` — and NO
// stage output at all; `import_progress.read()`'s answer is the eight-key gauge
// including the SERVER-computed `pct`. Both are copied from the Python, not
// from the TypeScript interfaces, for the reason DEF-526/531/522/535 record.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { ImportWorkflowPage } from "./ImportWorkflowPage";
import { PremisesImportsTab } from "./PremisesImportsTab";

const TEST_TENANT = "silvercreek";
const RUN_ID = "5f2b7c1e-0000-4000-8000-000000000042";
const JOB_ID = "9a1c0000-0000-4000-8000-0000000000aa";

/** A file over `import_runs.ASYNC_ROW_BAR` (5,000). 20,000 rows. */
const BIG_ROWS = 20_000;
const CSV_TEXT = "Address,City\n12 Main St,Katy\n";

function runDict(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    id: RUN_ID,
    run_no: "IMP-2026-000042",
    target: "premises",
    source_kind: "file",
    file_name: "premises-50k.csv",
    file_hash: "1f0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b8551",
    file_bytes: 2_400_000,
    encoding_delimiter: "UTF-8 · comma (detected)",
    mapping_id: null,
    mapping_spec: null,
    batch_label: null,
    write_mode: null,
    counts: { in: BIG_ROWS, duplicates_dropped: 0, skipped: 0, forward: 0 },
    status: "extracted",
    session_ref: null,
    ip: null,
    started_at: "2026-08-22T09:00:00Z",
    finished_at: null,
    // CR-026 — served on EVERY import answer, `null` until a stage defers.
    progress: null,
    ...overrides,
  };
}

/** `import_progress.read()`, key for key. `pct` is the SERVER's division. */
function gauge(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    stage: "transform",
    done: 0,
    total: BIG_ROWS,
    state: "queued",
    message: null,
    job_id: JOB_ID,
    pct: 0,
    updated_at: "2026-08-22T09:00:02Z",
    ...overrides,
  };
}

const EXTRACTED = runDict({
  headers: ["Address", "City"],
  detected_mapping: { Address: "address_line", City: "city" },
  warnings: [],
});

const COLUMNS = {
  target: "premises",
  columns: [
    {
      target: "address_line",
      label: "Address line",
      kind: "text",
      required: true,
      transforms: ["trim_whitespace"],
    },
    { target: "city", label: "City", kind: "text", required: false, transforms: [] },
    { target: "__ignore__", label: "— ignore —", kind: "text", required: false, transforms: [] },
  ],
  unavailable_transforms: [],
  row_handling: ["drop_exact_duplicates", "keep_latest_on_key", "skip_rows_missing_required"],
};

/**
 * `_defer()`'s answer — **the run and the job, and NONE of the stage's output**.
 * No `rules`, no `rejects`, and `counts` still holds stage 1's figures.
 */
function deferred(stage: string, progress: Record<string, unknown>): Record<string, unknown> {
  return runDict({
    progress,
    deferred: true,
    stage,
    job_id: JOB_ID,
    status_url: `/api/jobs/${JOB_ID}`,
  });
}

/** `read_run()` once validate has finished in the worker. */
function validatedRun(progress: Record<string, unknown>): Record<string, unknown> {
  return runDict({
    counts: {
      in: BIG_ROWS,
      duplicates_dropped: 12,
      forward: BIG_ROWS - 12,
      checked: BIG_ROWS - 12,
      clean: 19_900,
      errors: 0,
      warnings: 88,
    },
    status: "validated",
    progress,
    rules: [
      {
        code: "structural.address_required",
        tier: 1,
        sentence: "Every row has an address",
        severity: "error",
        action: "reject_row",
        action_value: null,
        hits: 0,
        available: true,
        unavailable_reason: null,
      },
    ],
    rejects: [],
    blocking_rules: { count: 1, platform: 0, structural: 1 },
  });
}

interface RecordedCall {
  method: "GET" | "POST";
  path: string;
}

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { status, data, etag: null, notModified: false };
}

/**
 * `answers` decides what each stage POST returns and what the poll returns
 * WHILE that stage is outstanding — which is how a test can put a run in a
 * worker without a worker.
 */
interface Script {
  transform: Record<string, unknown>;
  validate?: Record<string, unknown>;
  poll: Record<string, Record<string, unknown>>;
}

function stubClient(script: Script, calls: RecordedCall[]): ApiClient {
  let stage = "transform";
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "GET", path });
      if (path === `/imports/${RUN_ID}/columns`) return ok(COLUMNS as T);
      if (path === `/imports/${RUN_ID}`) {
        const answer = script.poll[stage];
        if (answer === undefined) throw new Error(`no poll answer for ${stage}`);
        return ok(answer as T);
      }
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "POST", path });
      if (path === "/imports") return ok(EXTRACTED as T, 201);
      if (path === `/imports/${RUN_ID}/transform`) {
        stage = "transform";
        // 202 — the engine deferred. The status code follows the engine, and
        // `deferred: true` in the body is what the client actually reads.
        return ok(script.transform as T, 202);
      }
      if (path === `/imports/${RUN_ID}/validate`) {
        stage = "validate";
        if (script.validate === undefined) throw new Error("validate not scripted");
        return ok(script.validate as T, 202);
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
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/import`]}>
          <Routes>
            <Route
              path="/:tenant/premises/import"
              element={<ImportWorkflowPage target="premises" client={client} />}
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

async function uploadAndTransform(
  user: ReturnType<typeof userEvent.setup>,
  container: HTMLElement,
) {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) throw new Error("stage 1 renders no file input");
  await user.upload(input, new File([CSV_TEXT], "premises-50k.csv", { type: "text/csv" }));
  const transform = await screen.findByRole("button", { name: "Transform →" });
  await waitFor(() => expect(transform).toBeEnabled());
  await user.click(transform);
  await waitFor(() => expect(stageOf(container)).toBe("2"));
  await user.click(await screen.findByRole("button", { name: "Validate →" }));
}

afterEach(cleanup);

describe("CR-026 — a background import says how far it has got", () => {
  it("a SMALL synchronous run adds nothing at all: no panel, no bar, no poll", async () => {
    // ⚠ THE REGRESSION THIS SUITE EXISTS FOR. `progress` is `null` on every
    // answer of a run under the 5,000-row bar, `deferred` is absent, and the
    // screen must be byte-for-byte what it was before CR-026.
    const calls: RecordedCall[] = [];
    const small = runDict({ counts: { in: 3, duplicates_dropped: 1, forward: 2 }, status: "transformed" });
    const client = stubClient(
      { transform: small, poll: {} },
      calls,
    ) as ApiClient;
    // The stage POST answers 200 with the stage's real output — no deferral.
    const user = userEvent.setup();
    const { container } = mount(client);
    await uploadAndTransform(user, container);

    // It moved on, exactly as a small file always did.
    await waitFor(() => expect(stageOf(container)).toBe("3"));
    expect(container.querySelector('[data-workflow="progress"]')).toBeNull();
    expect(container.querySelector('[data-workflow="progress-bar"]')).toBeNull();
    expect(container.querySelector('[data-workflow="progress-starting"]')).toBeNull();
    // And NOT ONE poll was issued: `GET /imports/{id}` never happens.
    expect(calls.filter((call) => call.path === `/imports/${RUN_ID}`)).toHaveLength(0);
  });

  it("a deferred stage draws the SERVER's figures — 'Mapping… 8,000 of 20,000' and 40%", async () => {
    const calls: RecordedCall[] = [];
    const client = stubClient(
      {
        transform: deferred("transform", gauge({ state: "queued" })),
        poll: {
          transform: runDict({
            progress: gauge({ state: "running", done: 8_000, pct: 40 }),
          }),
        },
      },
      calls,
    );
    const user = userEvent.setup();
    const { container } = mount(client);
    await uploadAndTransform(user, container);

    // The line is the server's two counts, grouped — r10's own sentence shape.
    await waitFor(() =>
      expect(screen.getByText("Mapping… 8,000 of 20,000")).toBeInTheDocument(),
    );
    // ⚠ THE PERCENTAGE IS THE SERVER'S. `import_progress.read` computes `pct`
    // so that two clients cannot each divide by zero their own way; the bar's
    // `aria-valuenow` is that same number and is never `done / total` here.
    expect(screen.getByText("40% complete")).toBeInTheDocument();
    const bar = container.querySelector('[data-workflow="progress-bar"]');
    expect(bar).not.toBeNull();
    expect(bar?.getAttribute("aria-valuenow")).toBe("40");

    // The run has not moved on, and the stage's own output was NOT drawn from
    // the 202: no reconcile strip of zeros over a file still being mapped.
    expect(stageOf(container)).toBe("2");
    expect(await screen.findByRole("button", { name: "Validate →" })).toBeDisabled();

    // The poll surface was asked, and the job endpoint was not: one payload.
    expect(calls.some((call) => call.path === `/imports/${RUN_ID}`)).toBe(true);
    expect(calls.some((call) => call.path.startsWith("/jobs"))).toBe(false);
  });

  it("BR-MET-102 — NO cancel control renders on a deferred run, not even a disabled one", async () => {
    const calls: RecordedCall[] = [];
    const client = stubClient(
      {
        transform: deferred("transform", gauge({ state: "running", done: 8_000, pct: 40 })),
        poll: {
          transform: runDict({ progress: gauge({ state: "running", done: 8_000, pct: 40 }) }),
        },
      },
      calls,
    );
    const user = userEvent.setup();
    const { container } = mount(client);
    await uploadAndTransform(user, container);
    await waitFor(() =>
      expect(container.querySelector('[data-workflow="progress"]')).not.toBeNull(),
    );

    // ⚠ PO ruling 2026-08-22, verbatim "No". Not a disabled control with a
    // reason (BR-SHL-025 is for a control that cannot act YET) — nothing.
    // ⚠ Stage 1's footer secondary IS called "Cancel" and is r10's own exit
    // from the wizard; the run is on stage 2 here, where that button reads
    // "← Back", so a match on this name could only be a job cancel.
    expect(stageOf(container)).toBe("2");
    for (const word of [/cancel/i, /abort/i, /stop this/i]) {
      expect(screen.queryByRole("button", { name: word })).toBeNull();
      expect(screen.queryByRole("link", { name: word })).toBeNull();
    }
    // What the operator is offered instead, on the screen, while they watch:
    // the ruled rollback, named without its window (ROLLBACK_DAYS is the
    // server's number).
    expect(container.querySelector('[data-workflow="no-cancel"]')?.textContent).toContain(
      "cannot be stopped",
    );
    expect(container.querySelector('[data-workflow="no-cancel"]')?.textContent).toContain(
      "rollback",
    );
  });

  it("when the gauge reaches `done` the run moves on, and the SERVER's stage output is what is drawn", async () => {
    const calls: RecordedCall[] = [];
    const client = stubClient(
      {
        transform: deferred("transform", gauge({ state: "queued" })),
        validate: deferred("validate", gauge({ stage: "validate", state: "queued" })),
        poll: {
          // Transform finished in the worker — its counts are real now.
          transform: runDict({
            counts: { in: BIG_ROWS, duplicates_dropped: 12, forward: BIG_ROWS - 12 },
            status: "transformed",
            progress: gauge({ state: "done", done: BIG_ROWS, pct: 100 }),
          }),
          // …and so did validate, which is the payload stage 3 draws.
          validate: validatedRun(
            gauge({ stage: "validate", state: "done", done: BIG_ROWS - 12, pct: 100 }),
          ),
        },
      },
      calls,
    );
    const user = userEvent.setup();
    const { container } = mount(client);
    await uploadAndTransform(user, container);

    // The poll — not the 202 — is what advanced the run.
    await waitFor(() => expect(stageOf(container)).toBe("3"));
    // And stage 3 shows the WORKER's numbers, from `GET /imports/{id}`.
    await waitFor(() =>
      expect(screen.getByText("Every row has an address")).toBeInTheDocument(),
    );
    expect(screen.queryByText("No rules ran on this file.")).not.toBeInTheDocument();
    // The panel is gone once nothing is running.
    await waitFor(() =>
      expect(container.querySelector('[data-workflow="progress"]')).toBeNull(),
    );
    // Both stages were polled, each on its own key.
    expect(calls.filter((call) => call.path === `/imports/${RUN_ID}`).length).toBeGreaterThanOrEqual(2);
  });

  it("a stage that DIES in the worker says so, in the worker's own words, and does not advance", async () => {
    const calls: RecordedCall[] = [];
    const client = stubClient(
      {
        transform: deferred("transform", gauge({ state: "queued" })),
        poll: {
          transform: runDict({
            progress: gauge({
              state: "failed",
              done: 6_400,
              pct: 32,
              message: "worker lost the database connection",
            }),
          }),
        },
      },
      calls,
    );
    const user = userEvent.setup();
    const { container } = mount(client);
    await uploadAndTransform(user, container);

    await waitFor(() =>
      expect(
        screen.getByText(
          "This stage stopped before it finished: worker lost the database connection",
        ),
      ).toBeInTheDocument(),
    );
    // ⚠ The message OUTLIVES its own poll. Clearing the deferral changes the
    // query key, so the payload is gone on the next render; a screen that lost
    // the only sentence explaining why nothing happened is worse than one that
    // never had it.
    expect(stageOf(container)).toBe("2");
    expect(container.querySelector('[data-workflow="progress-bar"]')).toBeNull();
    // The operator can act again: the run did not advance and is not locked.
    expect(await screen.findByRole("button", { name: "Validate →" })).toBeEnabled();
  });
});

describe("CR-026 — the run table, the come-back-later surface", () => {
  /** `run_list`'s nine columns, as `import_runs.run_list` serves them. */
  function listRow(overrides: Record<string, unknown>) {
    return {
      id: RUN_ID,
      run_no: "IMP-2026-000042",
      target: "premises",
      file_name: "premises-50k.csv",
      rows_in: BIG_ROWS,
      loaded: 0,
      rejected: 0,
      status: "validated",
      run_by: "dana@brazosbendutilities.com",
      started_at: "2026-08-22T09:00:00Z",
      finished_at: null,
      ...overrides,
    };
  }

  function tabClient(detail: Record<string, unknown>, row: Record<string, unknown>): ApiClient {
    return {
      get: async <T,>(path: string): Promise<ApiResponse<T>> => {
        if (path === "/imports") return ok({ rows: [row] } as T);
        if (path === `/imports/${RUN_ID}`) return ok(detail as T);
        throw new Error(`unstubbed GET ${path}`);
      },
      post: async () => {
        throw new Error("the run table writes nothing");
      },
    } as unknown as ApiClient;
  }

  function mountTab(client: ApiClient) {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    return render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/imports`]}>
            <PremisesImportsTab
              writeBlockedReason={null}
              onImportPremises={() => undefined}
              onImportUnits={() => undefined}
              client={client}
            />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  it("draws the gauge under r10's STATUS pill while a run is still in a worker", async () => {
    // ⚠ The status pill says "Checked" for the whole of a two-minute load —
    // `import_runs` writes the new status when a stage COMMITS, and the stage
    // holds that row locked until then. The gauge is the only thing on this
    // screen that can say otherwise, which is the whole reason it is here.
    const { container } = mountTab(
      tabClient(
        runDict({
          status: "validated",
          progress: gauge({ stage: "load", state: "running", done: 8_600, pct: 43 }),
        }),
        listRow({}),
      ),
    );
    await waitFor(() => expect(screen.getByText("Checked")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Loading · 43%")).toBeInTheDocument());
    expect(
      container.querySelector('[data-progress-state="running"]'),
    ).not.toBeNull();
  });

  it("a run that never deferred draws NO gauge — the row is what it always was", async () => {
    const { container } = mountTab(
      tabClient(runDict({ status: "validated", progress: null }), listRow({ rows_in: 3 })),
    );
    await waitFor(() => expect(screen.getByText("Checked")).toBeInTheDocument());
    // Long enough for the one detail read to land and be rendered.
    await waitFor(() =>
      expect(screen.getByText("dana@brazosbendutilities.com")).toBeInTheDocument(),
    );
    expect(container.querySelector("[data-progress-state]")).toBeNull();
  });

  it("a FINISHED run is not polled at all — nothing to ask", async () => {
    const calls: string[] = [];
    const client = {
      get: async <T,>(path: string): Promise<ApiResponse<T>> => {
        calls.push(path);
        if (path === "/imports") {
          return ok({ rows: [listRow({ status: "loaded", loaded: BIG_ROWS })] } as T);
        }
        throw new Error(`unstubbed GET ${path}`);
      },
      post: async () => {
        throw new Error("the run table writes nothing");
      },
    } as unknown as ApiClient;
    mountTab(client);
    // ⚠ **THIS ASSERTION WAS PASSING ON THE COLUMN HEADER, NOT THE ROW, AND
    //    CR-045 wave D (D.15) IS WHAT EXPOSED IT.** It read
    //    `getByText("Loaded")`, and PRM-04 draws that word in three places
    //    once the Status filter exists: the `Loaded` COLUMN heading, the
    //    status PILL on the row, and now the filter's `Loaded` option.
    //
    //    Measured at the pre-change commit: exactly one node matched, and it
    //    was `SPAN.truncate` — the column heading, which renders on the very
    //    first frame. So `waitFor` returned immediately, before any row had
    //    arrived, and the case never waited for the thing it is named after.
    //    It would have passed with the list empty.
    //
    //    So this is not re-scoped to dodge an ambiguity — it is pointed at
    //    the STATUS PILL, which is what "a FINISHED run" means here, and it
    //    now genuinely waits for the row. `getAllByText` was the other
    //    available fix and is the wrong one: it would keep passing on the
    //    heading alone.
    await waitFor(() =>
      expect(
        within(screen.getByRole("table")).getByText("Loaded", { selector: "span.pill" }),
      ).toBeInTheDocument(),
    );
    // ⚠ The row rendering is NOT proof on its own — a detail read fired one
    // tick later would still be a poll of a finished run, and an assertion
    // taken at this instant would miss it. Give the queries a turn first.
    await new Promise((resolve) => setTimeout(resolve, 250));
    expect(calls.filter((path) => path === `/imports/${RUN_ID}`)).toHaveLength(0);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-026 second half — the frontend (12-governance/11-change-requests.md
//         §CR-026) + BR-MET-102 (PO ruling 2026-08-22, "No")
// generated: 2026-08-22 by the CR-026 closure lane
// checklist: A✔ B✔ C✔ D✔(each case proved RED against the pre-change page: the
//         202 was read as a result, so "a deferred stage draws the SERVER's
//         figures" found no panel at all and "the gauge reaches done" landed on
//         stage 3 with zero counts) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: vitest (jsdom via the file pragma)✔ · tsc✔
// exceptions: E3 the stub answers the poll from a `stage` variable the POST
//         handlers set, because a test cannot run a Celery worker; the SHAPES
//         are the server's, copied from import_runs._defer and
//         import_progress.read rather than from the TypeScript interfaces
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
