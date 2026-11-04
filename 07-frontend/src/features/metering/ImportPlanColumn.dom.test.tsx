// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  DEF-771 — the units import matched a plan by CODE while the column
//          is labelled `Plan` and its aliases (`plan`, `rate plan`, `tariff`)
//          are the words for a plan's NAME. A utility's 9,881-row file said
//          `city customer plan` in every cell, mapped clean, showed `Matched`,
//          and loaded: LOADED 9,881 · FLAGGED 9,881 · UNITS WITH NO PLAN 9,881.
//          Nothing on any screen stated which of the two the column took, and
//          the receipt could not tell "no such plan" from "that plan is a
//          draft" — which need different acts from the operator.
// Rules:   BR-MET-100 (an unresolved plan LOADS, unplanned and flagged — the
//          PO's option B, unchanged) · BR-RAT-030 (only a PUBLISHED plan is
//          assignable) · BR-MET-117 posture (say it at stage 2, where the file
//          can still be changed) · B14 rule 21 (Tailwind utilities only)
// ───────────────────────────────────────────────────────
// ⚠ EVERY ASSERTION HERE READS RENDERED OUTPUT. The server sentence exists,
// is typed and is covered by `tests/test_def_771_plan_by_name.py`; a test that
// checked a prop would pass on a build where no operator ever sees it — which
// is precisely how `blank_means` has sat in `ImportTargetColumn` unrendered.
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
const RUN_ID = "5f2b7c1e-0000-4000-8000-000000000771";
/** The PO's own file. */
const LIVE_ROWS = 9_881;
/** …and the cell it carried on every one of those rows. */
const THE_CELL = "city customer plan";

/** The server's own sentence for the column (`UNITS_FIELD_OVERRIDES`). */
const PLAN_HELP =
  "The plan's CODE or its NAME — either one, and upper or lower case makes no " +
  "difference. Only a PUBLISHED plan can be assigned: a draft or an archived " +
  "plan is named back to you rather than used. A cell naming no plan leaves " +
  "the unit unplanned, which is allowed.";

/** `rating.assignable_plan_index` found the plan and it is a DRAFT — the case
 *  the operator could not distinguish from "no such plan" before. */
const UNPLANNED_PLANS = [
  {
    asked_for: THE_CELL,
    rows: LIVE_ROWS,
    reason: "draft" as const,
    detail:
      "Plan city customer plan is a DRAFT — City Customer Plan (PLN-A17). A draft has " +
      "no prices a bill could be produced from, so it cannot be assigned.",
    fix_hint:
      "Publish it under Plans & Rates and run this file again. This unit will be created " +
      "WITHOUT a plan and flagged. It cannot be billed until a plan is set.",
  },
];

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { status, data, etag: null, notModified: false };
}

const COLUMNS = {
  target: "units",
  columns: [
    { target: "premises", label: "Parent premise", kind: "premise_ref", required: true, transforms: [] },
    { target: "label", label: "Unit label", kind: "text", required: true, transforms: [] },
    {
      target: "rate_plan",
      label: "Plan",
      kind: "plan_ref",
      required: false,
      transforms: [],
      help: PLAN_HELP,
    },
    { target: "__ignore__", label: "— ignore —", kind: "text", required: false, transforms: [] },
  ],
  unavailable_transforms: [],
  row_handling: ["drop_exact_duplicates", "keep_latest_on_key", "skip_rows_missing_required"],
};

const COUNTS = {
  in: LIVE_ROWS,
  duplicates_dropped: 0,
  skipped: 0,
  forward: LIVE_ROWS,
  checked: LIVE_ROWS,
  clean: 0,
  errors: 0,
  warnings: LIVE_ROWS,
};

function runDict(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    id: RUN_ID,
    run_no: "IMP-2026-000771",
    target: "units",
    source_kind: "file",
    file_name: "ottumwa_units.csv",
    file_hash: "77108f2c3d4e5a6b7c8d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d",
    file_bytes: 1_400_000,
    encoding_delimiter: "UTF-8 · comma (detected)",
    mapping_id: null,
    mapping_spec: null,
    batch_label: null,
    write_mode: null,
    counts: COUNTS,
    status: "extracted",
    session_ref: null,
    ip: null,
    started_at: "2026-08-26T09:00:00Z",
    finished_at: null,
    progress: null,
    headers: ["UNIT_REF", "PREMISE_ID", "PLAN"],
    detected_mapping: { UNIT_REF: "label", PREMISE_ID: "premises", PLAN: "rate_plan" },
    warnings: [],
    ...overrides,
  };
}

const SPEC = {
  columns: {},
  row_handling: {},
  date_format: "MM/DD/YYYY",
  column_problems: [],
  empty_columns: [],
};

const VALIDATED = runDict({
  status: "validated",
  mapping_spec: SPEC,
  rules: [
    {
      code: "UNT.PLAN_ON_FILE",
      tier: 2,
      sentence: "The plan named in the file is on file",
      severity: "warning",
      action: "flag_only",
      action_value: null,
      hits: LIVE_ROWS,
      available: true,
      unavailable_reason: null,
    },
  ],
  rejects: [],
  blocking_rules: { count: 0, platform: 0, structural: 0 },
});

const DRY_INSERT = {
  will_create: LIVE_ROWS,
  will_update: 0,
  rejected: 0,
  target: "units",
  unplanned_units: LIVE_ROWS,
  unplanned_plans: UNPLANNED_PLANS,
  approval: {
    threshold_pct: 5,
    threshold_rows: 10,
    rejected: 0,
    of_rows: LIVE_ROWS,
    required: false,
    because: "percent",
  },
};

const LOADED = {
  ...VALIDATED,
  status: "loaded",
  write_mode: "insert",
  finished_at: "2026-08-26T09:04:30Z",
  receipt: {
    run_id: RUN_ID,
    run_no: "RUN-2871",
    loaded: LIVE_ROWS,
    rejected: 0,
    flagged: LIVE_ROWS,
    unplanned_units: LIVE_ROWS,
    unplanned_plans: UNPLANNED_PLANS,
    deactivated: 0,
    skipped_occupied: 0,
    source_label: "ottumwa_units.csv",
    file_sha256: "77108f2c3d4e5a6b7c8d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d",
    file_hash_verified: true,
    run_by: "alex@ottumwa.example",
    session_and_ip: "sess_2b41 · 71.42.108.14",
    mapping_used: null,
    write_mode: "insert",
    finished_at: "2026-08-26T09:04:30Z",
    rollback_point: null,
  },
};

function stubClient(): ApiClient {
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      if (path === `/imports/${RUN_ID}/columns`) return ok(COLUMNS as T);
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string): Promise<ApiResponse<T>> => {
      if (path === "/imports") return ok(runDict({}) as T, 201);
      if (path === `/imports/${RUN_ID}/transform`)
        return ok(runDict({ status: "transformed", mapping_spec: SPEC }) as T);
      if (path === `/imports/${RUN_ID}/validate`) return ok(VALIDATED as T);
      if (path === `/imports/${RUN_ID}/dry-run`) return ok(DRY_INSERT as T);
      if (path === `/imports/${RUN_ID}/load`) return ok(LOADED as T);
      throw new Error(`unstubbed POST ${path}`);
    },
  } as unknown as ApiClient;
}

function mount() {
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
              element={<ImportWorkflowPage target="units" client={stubClient()} />}
            />
            <Route path="/:tenant/premises/units" element={<div>units list</div>} />
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

type User = ReturnType<typeof userEvent.setup>;

async function toStageTwo(user: User, container: HTMLElement) {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) throw new Error("stage 1 renders no file input");
  await user.upload(
    input,
    new File([`UNIT_REF,PREMISE_ID,PLAN\nU-1,P-1,${THE_CELL}\n`], "ottumwa_units.csv", {
      type: "text/csv",
    }),
  );
  const transform = await screen.findByRole("button", { name: "Transform →" });
  await waitFor(() => expect(transform).toBeEnabled());
  await user.click(transform);
  await waitFor(() => expect(stageOf(container)).toBe("2"));
}

async function toStageFour(user: User, container: HTMLElement) {
  await toStageTwo(user, container);
  await user.click(await screen.findByRole("button", { name: "Validate →" }));
  await waitFor(() => expect(stageOf(container)).toBe("3"), { timeout: 10_000 });
  await user.click(await screen.findByRole("button", { name: "Load →" }));
  await waitFor(() => expect(stageOf(container)).toBe("4"));
}

afterEach(cleanup);

describe("DEF-771 — the screen says which the Plan column takes", () => {
  it("STAGE 2 states that the Plan column takes a CODE OR a NAME", async () => {
    const user = userEvent.setup();
    const { container } = mount();
    await toStageTwo(user, container);

    const note = block(container, "plan-column-help");
    expect(note, "stage 2 says nothing about what the Plan column takes").not.toBeNull();
    expect(note).toHaveTextContent(/CODE or its NAME/i);
    // …and it names the operator's OWN column, so the sentence is about the
    // file in front of them rather than about the product in general.
    expect(note).toHaveTextContent("PLAN → Plan");
  });
});

describe("DEF-771 — 9,881 flagged rows is not a review anybody can perform", () => {
  it("STAGE 4 names the plan every unplanned row asked for, BEFORE the commit", async () => {
    const user = userEvent.setup();
    const { container } = mount();
    await toStageFour(user, container);

    const panel = block(container, "unplanned-plans");
    expect(panel, "the rehearsal prints a count of 9,881 and never which plan").not.toBeNull();
    expect(panel).toHaveTextContent(THE_CELL);
    expect(panel).toHaveTextContent("9881");
    expect(panel).toHaveTextContent(/DRAFT/);
    expect(panel).toHaveTextContent(/Publish it under Plans & Rates/);
  });

  it("STAGE 5 says the same thing on the receipt, and says WHY rather than 'unknown plan'", async () => {
    const user = userEvent.setup();
    const { container } = mount();
    await toStageFour(user, container);
    await user.click(await screen.findByRole("button", { name: /Commit/i }));
    await waitFor(() => expect(stageOf(container)).toBe("5"));

    const panel = block(container, "unplanned-plans");
    expect(panel).not.toBeNull();
    expect(panel).toHaveTextContent(THE_CELL);
    expect(panel).toHaveTextContent("9881");
    // ⚠ the half of the fix DEF-771 calls "half the value": the plan EXISTS
    // and is a draft, which is one click to fix — not a spelling mistake.
    expect(panel).toHaveTextContent(/DRAFT/);
    expect(panel?.textContent ?? "").not.toContain("is not on file");
  });
});
