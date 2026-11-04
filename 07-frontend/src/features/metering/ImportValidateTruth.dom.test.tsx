// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-036 amendment 1 (f) — the stage-3 panel contradicted itself
//          mid-run: `ROWS CHECKED 0 · PASSED CLEAN 0 · ERRORS 0 · WARNINGS 0`
//          under *"Rules that ran"* and *"No rules ran on this file."*, beside
//          a bar reading `Validating… 1,646 of 9,881 · 16% complete`. And on
//          the FINISHED premises run it read `ROWS CHECKED 9881 · PASSED CLEAN
//          0 · ERRORS 0 · WARNINGS 9881`, which the PO read as total failure —
//          *"it rejected and shown all error"* — over a run in which not one
//          row was blocked.
//          CR-036 amendment 2 (g) — PO, verbatim: *"you need at step 1 or 2
//          itself - this is important decision how you will process the data
//          and upload it"*. The write mode is a PREMISE, not a confirmation.
// Rules:   BR-MET-085 (never invent a figure the server has not sent) ·
//          CR-016 (plain English) · B14 rule 21 (Tailwind)
// ───────────────────────────────────────────────────────
// ⚠ EVERY ASSERTION HERE READS RENDERED OUTPUT (hard-won law 2). A prop is not
// a screen: the four zero tiles were passed correctly to a component that drew
// them correctly, and the screen was still wrong.
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

const TEST_TENANT = "ottumwa-water-works";
const RUN_ID = "5f2b7c1e-0000-4000-8000-000000000099";
const JOB_ID = "9a1c0000-0000-4000-8000-0000000000bb";

/** The PO's own premises file. */
const LIVE_ROWS = 9_881;
const CSV_TEXT = "PREMISE_NO,ADDRESS\nP-10000,1 Main St\n";

function runDict(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    id: RUN_ID,
    run_no: "IMP-2026-000099",
    target: "premises",
    source_kind: "file",
    file_name: "premises.csv",
    file_hash: "2f0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b8552",
    file_bytes: 1_400_000,
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
  headers: ["PREMISE_NO", "ADDRESS"],
  detected_mapping: { PREMISE_NO: "premise_no", ADDRESS: "address_line1" },
  warnings: [],
});

const COLUMNS = {
  target: "premises",
  columns: [
    {
      target: "premise_no",
      label: "Premise ID",
      kind: "text",
      required: true,
      transforms: ["trim_whitespace"],
    },
    {
      target: "address_line1",
      label: "Address",
      kind: "text",
      required: true,
      transforms: [],
    },
    { target: "__ignore__", label: "— ignore —", kind: "text", required: false, transforms: [] },
  ],
  unavailable_transforms: [],
  row_handling: ["drop_exact_duplicates", "keep_latest_on_key", "skip_rows_missing_required"],
};

function deferred(stage: string, progress: Record<string, unknown>): Record<string, unknown> {
  return runDict({
    progress,
    deferred: true,
    stage,
    job_id: JOB_ID,
    status_url: `/api/jobs/${JOB_ID}`,
  });
}

/**
 * ⚠ **THE PO'S FINISHED PREMISES RUN, NUMBER FOR NUMBER.** `PRM.ADDRESS_ON_FILE`
 * hit every row at severity WARNING, so: 9,881 checked, 0 clean, **0 errors**,
 * 9,881 warnings. Zero rows blocked, and the screen read as total failure.
 */
const VALIDATED = runDict({
  counts: {
    in: LIVE_ROWS,
    duplicates_dropped: 0,
    forward: LIVE_ROWS,
    checked: LIVE_ROWS,
    clean: 0,
    errors: 0,
    warnings: LIVE_ROWS,
  },
  status: "validated",
  progress: gauge({ stage: "validate", state: "done", done: LIVE_ROWS, pct: 100 }),
  rules: [
    {
      code: "PRM.ADDRESS_ON_FILE",
      tier: 3,
      sentence: "No premises is already on file at this address",
      severity: "warning",
      action: "skip_on_load",
      action_value: null,
      hits: LIVE_ROWS,
      available: true,
      unavailable_reason: null,
    },
  ],
  rejects: [],
  blocking_rules: { count: 0, platform: 0, structural: 0 },
});

/** Mid-run: the worker is 1,646 rows into 9,881 and has decided NOTHING. */
const VALIDATING = runDict({
  status: "transformed",
  progress: gauge({ stage: "validate", state: "running", done: 1_646, pct: 16 }),
});

interface RecordedCall {
  method: string;
  path: string;
  body?: unknown;
}

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { status, data, etag: null, notModified: false };
}

/** `finish` false leaves validate RUNNING for ever — the mid-run screen. */
function stubClient(finish: boolean, calls: RecordedCall[]): ApiClient {
  let phase = "transform";
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "GET", path });
      if (path === `/imports/${RUN_ID}/columns`) return ok(COLUMNS as T);
      if (path === `/imports/${RUN_ID}`) {
        if (phase === "transform") {
          return ok(
            runDict({
              counts: { in: LIVE_ROWS, duplicates_dropped: 0, forward: LIVE_ROWS },
              status: "transformed",
              progress: gauge({ state: "done", done: LIVE_ROWS, pct: 100 }),
            }) as T,
          );
        }
        return ok((finish ? VALIDATED : VALIDATING) as T);
      }
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string, body?: unknown): Promise<ApiResponse<T>> => {
      calls.push({ method: "POST", path, body });
      if (path === "/imports") return ok(EXTRACTED as T, 201);
      if (path === `/imports/${RUN_ID}/transform`) {
        phase = "transform";
        return ok(deferred("transform", gauge({ state: "queued" })) as T, 202);
      }
      if (path === `/imports/${RUN_ID}/validate`) {
        phase = "validate";
        return ok(deferred("validate", gauge({ stage: "validate", state: "queued" })) as T, 202);
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

function tile(container: HTMLElement, id: string): HTMLElement {
  const node = container.querySelector<HTMLElement>(`[data-workflow-figure="${id}"]`);
  if (node === null) throw new Error(`no tile ${id} on screen`);
  return node;
}

async function walkToStageThree(
  user: ReturnType<typeof userEvent.setup>,
  container: HTMLElement,
) {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) throw new Error("stage 1 renders no file input");
  await user.upload(input, new File([CSV_TEXT], "premises.csv", { type: "text/csv" }));
  const transform = await screen.findByRole("button", { name: "Transform →" });
  await waitFor(() => expect(transform).toBeEnabled());
  await user.click(transform);
  await waitFor(() => expect(stageOf(container)).toBe("2"));
  await user.click(await screen.findByRole("button", { name: "Validate →" }));
  await waitFor(() => expect(stageOf(container)).toBe("3"), { timeout: 10_000 });
}

afterEach(cleanup);

describe("CR-036 (f) — a count that has not been computed is not a zero", () => {
  it("MID-RUN the tiles say NOTHING YET, and no half of the screen calls the other a liar", async () => {
    const user = userEvent.setup();
    const { container } = mount(stubClient(false, []));
    await walkToStageThree(user, container);

    // The bar and the tiles are on screen TOGETHER — that is the defect's
    // whole shape, so the test holds both in one assertion block.
    await waitFor(() =>
      expect(container.querySelector('[data-workflow="progress-line"]')?.textContent).toContain(
        "Validating… 1,646 of 9,881",
      ),
    );
    expect(container.querySelector('[data-workflow="progress-pct"]')?.textContent).toContain(
      "16% complete",
    );

    // ⚠ NOT "0". Five tiles, five em-dashes: the server has not answered.
    for (const id of ["checked", "will-load", "errors", "warnings", "clean"]) {
      expect(tile(container, id).textContent).toContain("—");
      expect(tile(container, id).textContent).not.toMatch(/\d/);
    }
    // ⚠ AND THE SENTENCE THE PO ACTUALLY READ IS GONE while work is in flight.
    // "No rules ran on this file." is reserved for a FINISHED run that ran none.
    expect(screen.queryByText("No rules ran on this file.")).not.toBeInTheDocument();
    expect(
      screen.getByText(/The checks are still running on this file\./),
    ).toBeInTheDocument();
    expect(screen.getByText(/the checks are still running on this file\./)).toBeInTheDocument();
    // Nothing has been decided, so nothing claims an outcome either.
    expect(container.querySelector('[data-workflow="validate-outcome"]')).toBeNull();
  }, 30_000);

  it("THE FINISHED PREMISES RUN — 9,881 warnings, 0 blocked, and the screen says so", async () => {
    const user = userEvent.setup();
    const { container } = mount(stubClient(true, []));
    await walkToStageThree(user, container);
    await waitFor(() => expect(tile(container, "checked").textContent).toContain("9881"), {
      timeout: 10_000,
    });

    // ⚠ **THE FIGURE THAT DID NOT EXIST.** The PO read four true numbers and
    // concluded *"it rejected and shown all error"*. This is the answer to the
    // question they were asking.
    expect(tile(container, "will-load").textContent).toContain("Will load");
    expect(tile(container, "will-load").textContent).toContain("9881");

    // Blocked is ZERO and is drawn as an ordinary tile, not an exception one.
    expect(tile(container, "errors").textContent).toContain("Blocked — will not load");
    expect(tile(container, "errors").getAttribute("data-flagged")).toBe("false");

    // "Passed clean" is gone: it read as *succeeded*, so `0` beside it read as
    // *nothing succeeded*, which is exactly what happened.
    expect(screen.queryByText("Passed clean")).not.toBeInTheDocument();
    expect(tile(container, "clean").textContent).toContain("No remarks at all");
    // A warning does not stop a row, and the label now says which it is.
    expect(tile(container, "warnings").textContent).toContain("Loads, with a warning");

    const outcome = container.querySelector('[data-workflow="validate-outcome"]');
    expect(outcome?.textContent).toContain("9881 of these premises will load and 0 are blocked");
    expect(outcome?.textContent).toContain("a warning does not stop a row");
  }, 30_000);
});

describe("CR-036 (g) — the write mode is chosen at stage 1, before anything is read", () => {
  /**
   * ⛔ **AMENDED 2026-08-30 — CR-042 WITHDREW THE THIRD MODE AND THIS CASE WAS
   * STILL ASSERTING IT (DEF-1693).**
   *
   * The ruling, verbatim (PO 2026-08-27, `12-governance/02-decision-log.md`
   * *"CR-042: two write modes, on step 1, on EVERY import"*): *"in all imports -
   * we need 2 option on step 1 insert, insert & update; replace option is not
   * required"*. `writeModeOptions` has served exactly `["insert", "upsert"]`
   * ever since, so the third radio this case looked for has not existed on any
   * screen since that commit.
   *
   * **THREE FACTS MOVED AND ONLY ONE OF THEM WAS THE MODE**, which is why the
   * whole case is rewritten rather than trimmed by one line:
   *   1. the third radio is gone (CR-042);
   *   2. the radiogroup's accessible name is now `workflow.writeMode.label` —
   *      *"What does this file mean?"* — because the local `SegmentedField`
   *      captioned "Write mode" was replaced by the ONE shared control
   *      `components/workflow/WriteModeChoice`, which is what stopped this
   *      screen and the reads upload printing two different translations of the
   *      same options in eight of eleven languages;
   *   3. the help sentence is now `workflow.writeMode.help`, written from the
   *      shared control rather than this rail.
   * Only (1) is a rule change; (2) and (3) are the consolidation that carried
   * it. A lane that fixed the mode alone would have gone red twice more.
   *
   * ⚠ **THE ABSENCE IS NOW ASSERTED, NOT MERELY UNTESTED.** `OQ-580` closed the
   * same day — PO verbatim *"this si correct - a for now, c if it bites"* —
   * ruling that `Replace` stays withdrawn from every import and that retiring a
   * premises stays a per-record act. So a third radio reappearing here is a
   * regression against a closed question, and this case is where it fails.
   */
  it("stage 1 offers the TWO modes CR-042 left, and `insert` is what it opens on", async () => {
    mount(stubClient(true, []));
    const group = await screen.findByRole("radiogroup", { name: "What does this file mean?" });
    expect(within(group).getByRole("radio", { name: "Insert new only" })).toBeChecked();
    expect(within(group).getByRole("radio", { name: "Insert & update" })).toBeInTheDocument();
    // ⛔ CR-042: exactly two, and the withdrawn third is not merely unchecked —
    // it is not rendered. `getAllByRole` rather than a name query, so a mode
    // added under ANY label fails here.
    expect(within(group).getAllByRole("radio")).toHaveLength(2);
    expect(
      within(group).queryByRole("radio", { name: /Replace/i }),
    ).not.toBeInTheDocument();
    // The reason it is asked at stage 1 at all, on the stage.
    expect(
      screen.getByText(/because it decides what the checks at the next two steps are checking FOR/),
    ).toBeInTheDocument();
  });

  /**
   * ⛔ **AMENDED 2026-08-30 — THIS CASE'S SUBJECT WAS WITHDRAWN (DEF-1693).**
   *
   * It asserted that the DESTRUCTIVE mode carries a caution at stage 1. CR-042
   * removed that mode, so `data-workflow="write-mode-caution-stage1"` is
   * rendered by nothing and the case could only ever fail. Asserting the
   * caution's ABSENCE would be a check that cannot fail — the shape CLAUDE.md
   * calls worse than no check, because it is trusted.
   *
   * **WHAT SURVIVES THE WITHDRAWAL IS THE PROPERTY THE CAUTION EXISTED TO
   * SERVE:** a mode states its consequence AT STAGE 1, where the choice is
   * made, rather than leaving the operator to discover it at stage 3. That is
   * now `WriteModeField`'s `write-mode-consequence`, and it travels with the
   * CHOSEN mode — a sentence about the mode the operator did not pick is noise.
   *
   * ⚠ **AND IT IS ASSERTED THROUGH THIS RAIL'S OWN WORDS ON PURPOSE.** The
   * shared control's own suite proves the two-option list and that a sentence
   * renders; what it CANNOT prove is that the premises importer supplies its
   * own consequences rather than the reads rail's, which are deliberately
   * different (`WriteModeChoice.dom.test.tsx` asserts they differ). The string
   * below is `metering.import.writeMode.upsertConsequence` and belongs to this
   * rail alone.
   */
  it("the chosen mode states its consequence AT STAGE 1, in this rail's own words", async () => {
    const user = userEvent.setup();
    const { container } = mount(stubClient(true, []));
    await user.click(await screen.findByRole("radio", { name: "Insert & update" }));
    expect(
      container.querySelector('[data-workflow="write-mode-consequence"]')?.textContent,
    ).toContain("UPDATES that record's details from your file");
  });

  it("STAGE 3 NAMES THE PREMISE IT CHECKED UNDER — the mode the screenshot refused to show", async () => {
    const user = userEvent.setup();
    const { container } = mount(stubClient(true, []));
    await user.click(await screen.findByRole("radio", { name: "Insert & update" }));
    await walkToStageThree(user, container);
    const said = container.querySelector('[data-workflow="checked-under-mode"]');
    expect(said?.textContent).toContain("Checked as “Insert & update”");
    // And it is still revisable — a premise you cannot change before
    // committing is a trap, not a decision.
    expect(said?.textContent).toContain("You can change it at the dry run");
  }, 30_000);
});
