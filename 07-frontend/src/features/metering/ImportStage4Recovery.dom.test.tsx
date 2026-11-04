// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-019 (accounts cutover through the ONE runner)
//           Screens: WFL-01.accounts.4 (Load — the rehearsal and the commit)
// Defect:   DEF-2487 (critical) — a 1,048-account commit was killed by the
//           60-second web-worker timeout after a clean dry run. Two of the
//           three complaints were about this screen: there was no way to see
//           WHICH rows would not load, and a stage handed to a worker that
//           nothing claims looks identical to one that is about to finish.
// Rules:    PO ruling 2026-08-29 (*"at the end we need 2 CsV file 1 for
//           success record and other for failed records"*) · PO ruling
//           2026-08-30 (*"can we run anything above 100 recors directly using
//           worker batch job"*) · BR-MET-096 (a kind is COPY AND A ROUTE) ·
//           B14 rule 11 (a consequence preview before a commit) ·
//           CLAUDE.md law 2 (built is not wired)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **THE TWO FILES EXISTED, WORKED, AND WERE UNREACHABLE WHEN THEY MATTERED.**
 *
 * `import_results_csv`, `_failures_csv` and `downloadResults` were all complete.
 * The buttons that call them lived on the stage-5 Result screen, and **a commit
 * that fails never reaches stage 5** — so the one moment a person most needs the
 * list of what failed was the one moment the product would not give it to them.
 * Hard-won law 2 in a new costume: built is not the same as reachable.
 *
 * ⚠ **AND A QUEUED STAGE THAT NOTHING CLAIMS DREW A PROGRESS BAR.** Lowering
 * the accounts bar to 100 rows moves almost every real migration onto the worker
 * path. `apps/tenancy/tasks.send` swallows a broker failure by design — the
 * record is the truth and a later worker can still claim it — so a deployment
 * whose worker has died leaves the gauge resting `queued`, for ever, under a
 * panel that says the work is in progress.
 *
 * ⚠ **PROVED RED FIRST (hard-won law 7).** Both cases were run against the tip's
 * `ImportWorkflowPage.tsx`, before the fix existed:
 *
 *     × stage 4 offers the failures file, and clicking it asks the server for it
 *       → expected null not to be null
 *     × the stalled notice names the wait, says nothing was written, and names the fix
 *       → no stalled notice
 *
 * The three cases that assert an ABSENCE passed on the tip, as they must — a
 * guard that is green before the fix is a guard that is not looking at it.
 *
 * ⚠ **THE STUB SERVES THE SERVER'S OWN SHAPES, KEY FOR KEY** — copied from
 * `import_runs.run_dict` / `dry_run` / `import_progress.read`, never from the
 * TypeScript interfaces, for the reason `ImportResults.dom.test.tsx` gives: six
 * field names on this boundary have shipped wrong and every one was invisible to
 * a suite that fed the client its own spelling.
 */
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

const TEST_TENANT = "silvercreek";
const RUN_ID = "5f2b7c1e-0000-4000-8000-000000002487";
const JOB_ID = "7c1e5f2b-0000-4000-8000-000000002487";
const HASH = "9f2b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b81";

const CSV_TEXT =
  "UNIT,NAME,TYPE,CURRENT\n" +
  "U-00101-A,Harmon Luis,residential,84.20\n" +
  "U-00101-B,Alvarez Rosa,residential,0.00\n";

interface RecordedCall {
  method: string;
  path: string;
}

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { status, data, etag: null, notModified: false };
}

function runDict(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    id: RUN_ID,
    run_no: "IMP-2026-002487",
    target: "accounts",
    source_kind: "file",
    file_name: "accounts.csv",
    file_hash: HASH,
    file_bytes: CSV_TEXT.length,
    encoding_delimiter: "UTF-8 · comma (detected)",
    mapping_id: null,
    mapping_spec: null,
    batch_label: null,
    write_mode: null,
    counts: { in: 6, duplicates_dropped: 0, skipped: 0, forward: 0 },
    status: "extracted",
    session_ref: "sess_2487",
    ip: "71.42.108.14",
    started_at: "2026-08-30T09:00:00Z",
    finished_at: null,
    progress: null,
    ...overrides,
  };
}

const EXTRACTED = runDict({
  headers: ["UNIT", "NAME", "TYPE", "CURRENT"],
  detected_mapping: {
    UNIT: "unit_ref",
    NAME: "customer_name",
    TYPE: "account_type",
    CURRENT: "ob_current",
  },
  warnings: [],
});

const COLUMNS = {
  target: "accounts",
  columns: [
    { target: "unit_ref", label: "Unit", kind: "unit_ref", required: true, transforms: [] },
    {
      target: "customer_name",
      label: "Customer name",
      kind: "text",
      required: true,
      transforms: ["trim_whitespace"],
    },
    {
      target: "account_type",
      label: "Account type",
      kind: "lookup",
      required: true,
      transforms: ["trim_whitespace"],
    },
    {
      target: "ob_current",
      label: "Opening balance · current",
      kind: "decimal",
      required: false,
      transforms: [],
    },
  ],
  unavailable_transforms: [],
  row_handling: ["drop_exact_duplicates", "keep_latest_on_key", "skip_rows_missing_required"],
};

const TRANSFORMED = runDict({
  status: "transformed",
  counts: { in: 6, duplicates_dropped: 0, skipped: 0, forward: 6 },
});

const VALIDATED = runDict({
  status: "validated",
  counts: {
    in: 6,
    duplicates_dropped: 0,
    skipped: 0,
    forward: 6,
    checked: 6,
    clean: 5,
    errors: 1,
    warnings: 0,
  },
  rules: [],
  rejects: [
    {
      row_no: 3,
      source_key: "U-00404-C",
      problem: "There is no unit called U-00404-C in this utility.",
      fix_hint: "Load the unit first, then upload this row again.",
      outcome: "rejected",
    },
  ],
  rejects_window: { total: 1, offset: 0, limit: 50 },
  blocking_rules: { count: 0, platform: 0, structural: 0 },
});

/** `dry_run(...)` — one row will not load. */
const DRY_RUN_WITH_REJECTS = {
  will_create: 5,
  will_update: 0,
  rejected: 1,
  target: "accounts",
  unplanned_units: 0,
  approval: {
    threshold_pct: 5,
    threshold_rows: 10,
    rejected: 1,
    of_rows: 6,
    required: false,
    because: "percent",
  },
};

/** The same rehearsal over a file with nothing wrong in it. */
const DRY_RUN_CLEAN = { ...DRY_RUN_WITH_REJECTS, will_create: 6, rejected: 0 };

/** `import_progress.read(...)` for a load handed to a worker. */
function gauge(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    stage: "load",
    done: 0,
    total: 1048,
    state: "queued",
    message: null,
    job_id: JOB_ID,
    pct: 0,
    updated_at: "2026-08-30T09:00:00Z",
    stalled: false,
    stalled_after_seconds: 30,
    ...overrides,
  };
}

interface StubOptions {
  dryRun?: Record<string, unknown>;
  /** When set, `/load` answers 202 with this gauge and the poll repeats it. */
  deferredGauge?: Record<string, unknown>;
}

function stubClient(calls: RecordedCall[], options: StubOptions = {}): ApiClient {
  const dry = options.dryRun ?? DRY_RUN_WITH_REJECTS;
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "GET", path });
      if (path === `/imports/${RUN_ID}/columns`) return ok(COLUMNS as T);
      if (path.startsWith(`/imports/${RUN_ID}/results.csv`)) {
        return ok("UNIT,NAME,why_it_failed,how_to_fix_it\n" as T);
      }
      if (path === `/imports/${RUN_ID}`) {
        return ok(runDict({ status: "validated", progress: options.deferredGauge }) as T);
      }
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "POST", path });
      if (path === "/imports") return ok(EXTRACTED as T, 201);
      if (path === `/imports/${RUN_ID}/transform`) return ok(TRANSFORMED as T);
      if (path === `/imports/${RUN_ID}/validate`) return ok(VALIDATED as T);
      if (path === `/imports/${RUN_ID}/dry-run`) return ok(dry as T);
      if (path === `/imports/${RUN_ID}/load`) {
        if (options.deferredGauge === undefined) throw new Error("load not scripted");
        return ok(
          runDict({
            status: "validated",
            deferred: true,
            stage: "load",
            job_id: JOB_ID,
            status_url: `/api/jobs/${JOB_ID}`,
            progress: options.deferredGauge,
          }) as T,
          202,
        );
      }
      throw new Error(`unstubbed POST ${path}`);
    },
  } as unknown as ApiClient;
}

function mount(calls: RecordedCall[], options: StubOptions = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts/import`]}>
          <Routes>
            <Route
              path="/:tenant/accounts/import"
              element={
                <ImportWorkflowPage target="accounts" client={stubClient(calls, options)} />
              }
            />
            <Route path="/:tenant/accounts" element={<div>accounts list</div>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function stageOf(container: HTMLElement): string | null {
  return container.querySelector('[data-workflow="runner"]')?.getAttribute("data-stage") ?? null;
}

type User = ReturnType<typeof userEvent.setup>;

async function walkToStageFour(user: User, container: HTMLElement) {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  await user.upload(input, new File([CSV_TEXT], "accounts.csv", { type: "text/csv" }));
  const transform = await screen.findByRole("button", { name: "Transform →" });
  await waitFor(() => expect(transform).toBeEnabled());
  await user.click(transform);
  await waitFor(() => expect(stageOf(container)).toBe("2"));
  const validate = await screen.findByRole("button", { name: "Validate →" });
  await waitFor(() => expect(validate).toBeEnabled());
  await user.click(validate);
  await waitFor(() => expect(stageOf(container)).toBe("3"));
  await user.click(await screen.findByRole("button", { name: "Load →" }));
  await waitFor(() => expect(stageOf(container)).toBe("4"));
}

afterEach(cleanup);

describe("DEF-2487 — the rows that will not load are downloadable BEFORE the commit", () => {
  it("stage 4 offers the failures file, and clicking it asks the server for it", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);
    await walkToStageFour(user, container);

    // The sentence first — B14 rule 11's posture: say what the button is for
    // before offering it.
    const block = container.querySelector('[data-workflow="stage4-failures"]');
    expect(block).not.toBeNull();
    expect(block?.textContent).toContain("correct them in your own file");

    const download = await screen.findByRole("button", { name: "Download the 1 row that failed" });
    await user.click(download);

    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.method === "GET" &&
            call.path === `/imports/${RUN_ID}/results.csv?kind=failures`,
        ),
      ).toBe(true),
    );
  });

  it("a clean rehearsal offers no such button, because the file would be empty", async () => {
    // ⚠ The same argument stage 5 already makes: a *"download the rows that
    // failed"* button over a run with nothing wrong offers an empty file and
    // reads as an accusation. It is also the Product Owner's own 1,048-account
    // run — rejected 0 — so this is the case that says the fix for THAT run is
    // the async bar and not this block.
    const user = userEvent.setup();
    const { container } = mount([], { dryRun: DRY_RUN_CLEAN });
    await walkToStageFour(user, container);

    expect(container.querySelector('[data-workflow="stage4-failures"]')).toBeNull();
    expect(screen.queryByRole("button", { name: /rows that failed/ })).toBeNull();
  });

  it("the successes file is NOT offered before anything has loaded", async () => {
    // Nothing has been written yet, so *"download the rows that loaded"* would
    // hand back a header and no rows — which reads as an answer. The server
    // refuses that half for the same reason.
    const user = userEvent.setup();
    const { container } = mount([]);
    await walkToStageFour(user, container);
    expect(screen.queryByRole("button", { name: /that loaded/ })).toBeNull();
  });
});

describe("DEF-2487 — a queued stage nothing has claimed says so", () => {
  it("the stalled notice names the wait, says nothing was written, and names the fix", async () => {
    const user = userEvent.setup();
    const { container } = mount([], {
      deferredGauge: gauge({ stalled: true, stalled_after_seconds: 30 }),
    });
    await walkToStageFour(user, container);
    await user.click(await screen.findByRole("button", { name: "Commit load ✓" }));

    const notice = await waitFor(() => {
      const found = container.querySelector('[data-workflow="progress-stalled"]');
      if (found === null) throw new Error("no stalled notice");
      return found;
    });
    expect(notice.textContent).toContain("30 seconds");
    expect(notice.textContent).toContain("Nothing has been written");
    expect(notice.textContent).toContain("background worker");
    // It stays on stage 4: a job nobody claimed is not a stage that passed.
    expect(stageOf(container)).toBe("4");
  });

  it("a healthy queued stage draws no such notice", async () => {
    // The half that keeps the notice meaningful. A warning shown on every
    // deferral is a warning nobody reads.
    const user = userEvent.setup();
    const { container } = mount([], { deferredGauge: gauge({ stalled: false }) });
    await walkToStageFour(user, container);
    await user.click(await screen.findByRole("button", { name: "Commit load ✓" }));

    await waitFor(() =>
      expect(container.querySelector('[data-workflow="runner"]')).not.toBeNull(),
    );
    expect(container.querySelector('[data-workflow="progress-stalled"]')).toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-2487 (critical) — the accounts import commit 500, reported by the
//   Product Owner on a screen share, utility ottumwa-water-works, build v2.81.1
// generated: 2026-08-30 by the DEF-2487 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest (this file)✔ · npx vitest run src/i18n/locales.test.ts✔
// exceptions: the stalled cases script the poll to answer the SAME gauge every
//   time, because the interval is real and a test that waited for a second poll
//   would be timing-dependent; what is asserted is what the screen draws for a
//   given server answer, which is the whole of the client's half
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
