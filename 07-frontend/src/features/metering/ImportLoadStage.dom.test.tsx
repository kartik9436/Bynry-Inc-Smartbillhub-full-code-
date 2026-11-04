// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:   (none yet — hard-won law 8 is REPORTED in the trailer)
//          Change:  CR-023 W2 — stages 4 and 5, CLICKED THROUGH
//          Screens: WFL-01.premises.3–5
// Rules:   BR-MET-090 (severity and action are TWO columns) · BR-MET-098
//          (approval past 5% OR 10 rows; an Owner or an Admin approves) ·
//          BR-MET-099 (replace DEACTIVATES, skips the occupied, never deletes,
//          and states all three numbers first) · BR-MET-100 (an unplanned unit
//          is COUNTED AND FINDABLE) · BR-SHL-025 (disabled WITH its reason)
// ───────────────────────────────────────────────────────
// ⚠ **THE SUITE THAT COULD NOT HAVE BEEN WRITTEN YESTERDAY.** Every assertion
// below needs a DOM and a click, and until `DEF-523` landed the repo had
// neither. `ImportWorkflowPage.dom.test.tsx` is the first four cases; this file
// is stages 4 and 5, which is where the only endpoint that WRITES lives.
//
// ⚠ **CASE 1 IS `DEF-535`, AND IT IS THE ONE THIS FILE EXISTS FOR.** The kit's
// `RuleResultsTable` renders `rule.action_label` and its `RejectList` renders
// `row_number` / `key` / `suggested_fix`; the server sends `action` +
// `action_value` and `row_no` / `source_key` / `fix_hint`. Both halves agreed
// with each OTHER — `endpoints.ts` typed the kit's spelling — so `tsc` was
// green, the kit's own tests were green, and the ACTION column rendered
// `undefined` on every real run. The fix is an adapter in
// `ImportWorkflowPage.tsx`; the proof is a rendered cell, which is a thing only
// this environment can read.
//
// ⚠ **PROVED RED FIRST (law 7), TWICE.**
//
// **Case 1**, with `ruleRowsOf`/`rejectRowsOf` removed and `checked?.rules`
// passed straight through as it shipped:
//   `TestingLibraryElementError: Unable to find an element with the text:
//    Set a default · Residential`
// — while every other case in this file stayed green, which is exactly the
// shape of the escape: the sentences and the counts spell the same on both
// sides, so only the ACTION cell and the reject's fix text go missing.
//
// **The approval gate**, with `commitBlockedReason` dropped from
// `advanceDisabled` and `approved: true` hard-coded into the load body — the
// two ways a screen can turn `BR-MET-098` off from the client side:
//   `2 failed | 7 passed` — *the commit REFUSES until it is approved* and
//   *changing the write mode CLEARS an approval already given*.
// Both injections were removed and all nine went green.
//
// ⚠ **THE STUB SERVES THE SERVER'S REAL SHAPES, KEY FOR KEY** — copied from
// `import_runs.run_dict` / `rule_results` / `rejects` / `dry_run` / `receipt`,
// never from the TypeScript interfaces. Six field names on this one boundary
// have now shipped wrong (`DEF-522`, `DEF-526`, `DEF-531`, `DEF-535`), and
// every one was invisible to a suite that fed the client its own spelling.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import { WORKFLOW_KINDS } from "@/components/workflow";

import { ImportWorkflowPage } from "./ImportWorkflowPage";

const TEST_TENANT = "silvercreek";
const RUN_ID = "5f2b7c1e-0000-4000-8000-000000000002";
const HASH = "c19a5b7f0d2e4a6b8c1d3e5f7a9b1c3d5e7f9a1b3c5d7e9f1a3b5c7d9e1f4407";

/** A 20-row correction file with 2 rejects — `BR-MET-098`'s small-file case,
 *  and the one where the PERCENTAGE bar is what stops the run. */
const CSV_TEXT = "PREMISE_ID,ADDR1\nP-10001,12 Main St\nP-10002,\n";

/* ── the server's answers ────────────────────────────────────────────────── */

function runDict(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    id: RUN_ID,
    run_no: "RUN-2812",
    target: "premises",
    source_kind: "file",
    file_name: "silvercreek_premises_2026.csv",
    file_hash: HASH,
    file_bytes: CSV_TEXT.length,
    encoding_delimiter: "UTF-8 · comma (detected)",
    mapping_id: null,
    mapping_spec: null,
    batch_label: null,
    write_mode: null,
    counts: { in: 20, duplicates_dropped: 0, skipped: 0, forward: 20 },
    status: "extracted",
    session_ref: "sess_2b41",
    ip: "71.42.108.14",
    started_at: "2026-08-22T09:00:00Z",
    finished_at: null,
    ...overrides,
  };
}

const EXTRACTED = runDict({
  headers: ["PREMISE_ID", "ADDR1"],
  detected_mapping: { PREMISE_ID: "premise_no", ADDR1: "address_line" },
  warnings: [],
});

const COLUMNS = {
  target: "premises",
  columns: [
    { target: "premise_no", label: "Premise ID", kind: "text", required: false, transforms: [] },
    { target: "address_line", label: "Address line", kind: "text", required: true, transforms: [] },
    { target: "__ignore__", label: "— ignore —", kind: "text", required: false, transforms: [] },
  ],
  unavailable_transforms: [],
  row_handling: ["drop_exact_duplicates", "keep_latest_on_key", "skip_rows_missing_required"],
};

const TRANSFORMED = runDict({
  counts: { in: 20, duplicates_dropped: 0, skipped: 0, forward: 20 },
  status: "transformed",
});

/**
 * Stage 3 — `run_dict(run, with_rules=True)`.
 *
 * ⚠ **THE TWO ROWS BELOW ARE `DEF-535`'s WHOLE SURFACE.** The rule carries
 * `action: "default_to"` + `action_value: "Residential"` (never
 * `action_label`), and the reject carries `row_no` / `source_key` / `fix_hint`
 * (never `row_number` / `key` / `suggested_fix`).
 */
const VALIDATED = runDict({
  counts: {
    in: 20,
    duplicates_dropped: 0,
    skipped: 0,
    forward: 20,
    checked: 20,
    clean: 17,
    errors: 2,
    warnings: 1,
  },
  status: "validated",
  rules: [
    {
      code: "PRM.ADDRESS_REQUIRED",
      tier: 1,
      sentence: "Every row has an address",
      severity: "error",
      action: "reject_row",
      action_value: null,
      hits: 2,
      available: true,
      unavailable_reason: null,
    },
    {
      code: "PRM.TYPE_IN_LOOKUP",
      tier: 2,
      sentence: "Premise type exists in the lookup table",
      severity: "warning",
      action: "default_to",
      action_value: "Residential",
      hits: 1,
      available: true,
      unavailable_reason: null,
    },
  ],
  rejects: [
    {
      row_no: 2,
      source_key: "P-10002",
      problem: "An address is required.",
      fix_hint: "Load the premises first",
      outcome: "rejected",
    },
  ],
  blocking_rules: { count: 1, platform: 0, structural: 1 },
});

/** `dry_run(actor, run, "insert")` — no BR-MET-099 numbers on this mode. */
const DRY_INSERT = {
  will_create: 18,
  will_update: 0,
  rejected: 2,
  target: "premises",
  unplanned_units: 0,
  approval: {
    threshold_pct: 5,
    threshold_rows: 10,
    rejected: 2,
    of_rows: 20,
    required: true,
    because: "percent",
  },
};

/**
 * ⛔ **`DRY_REPLACE` IS DELETED — CR-042 WITHDREW THE MODE (2026-08-30,
 * DEF-1693).** It held `not_in_file: 69 · skipped_occupied: 41 ·
 * will_deactivate: 28`, `BR-MET-099`'s three numbers, and the stub served them
 * whenever a test posted `write_mode: "replace"`.
 *
 * **A STUB THAT ANSWERS A CALL THE SERVER REFUSES IS A FIXTURE ASSERTING THE
 * OLD WORLD.** Since CR-042 (PO 2026-08-27: *"in all imports - we need 2 option
 * on step 1 insert, insert & update; replace option is not required"*) the real
 * `import_runs.dry_run` raises on `replace` and names `OQ-580` in the refusal —
 * see `06-backend/tests/test_cr042_write_modes.py`. Keeping figures here would
 * let a UI regression that re-sent `replace` sail through this suite green
 * against a server that would have refused it in production.
 *
 * ⚠ **BR-MET-099's THREE NUMBERS ARE NOT LOST AND ARE NOT THIS FILE'S TO KEEP.**
 * The behaviour still stands in `import_runs.py`, refused at the boundary rather
 * than deleted (`OQ-580` CLOSED 2026-08-27, PO verbatim *"this si correct - a
 * for now, c if it bites"*), and it is asserted where it is now reachable — on
 * the server, by `test_cr023_load_stage.py::
 * test_replace_states_all_three_numbers_before_it_commits`, which re-enables the
 * mode through a fixture precisely because no UI can.
 */
function refuseWithdrawnMode(mode: string | undefined) {
  if (mode === "replace") {
    // The server's shape: a refusal naming OQ-580. Loud on purpose — if the UI
    // ever offers the withdrawn mode again, every case in this file fails.
    throw new Error(`write_mode 'replace' is withdrawn (CR-042); the server refuses it (OQ-580)`);
  }
}

/** `receipt(run)` — `run_dict(with_rules=True)` plus the `receipt` block. */
const LOADED = {
  ...VALIDATED,
  status: "loaded",
  write_mode: "insert",
  finished_at: "2026-08-22T09:04:30Z",
  counts: { ...(VALIDATED.counts as Record<string, number>), created: 18, updated: 0 },
  receipt: {
    run_id: RUN_ID,
    run_no: "RUN-2812",
    loaded: 18,
    rejected: 2,
    flagged: 1,
    unplanned_units: 0,
    deactivated: 0,
    skipped_occupied: 0,
    source_label: "silvercreek_premises_2026.csv",
    file_sha256: HASH,
    file_hash_verified: true,
    run_by: "alex@silvercreek.example",
    session_and_ip: "sess_2b41 · 71.42.108.14",
    mapping_used: null,
    write_mode: "insert",
    finished_at: "2026-08-22T09:04:30Z",
    rollback_point: {
      id: "RB-2813",
      status: "available",
      expires_at: "2026-09-21T09:04:30Z",
    },
  },
};

/** `rollback(run)`'s answer — the same receipt shape, on the run's new state.
 *  18 loaded, 16 reversed, 2 kept: the two an active account moved onto. */
const ROLLED_BACK = {
  ...LOADED,
  status: "rolled_back",
  counts: {
    ...(LOADED.counts as Record<string, number>),
    rolled_back: 16,
    kept_occupied: 2,
  },
  receipt: {
    ...LOADED.receipt,
    rollback_point: { id: "RB-2813", status: "used", expires_at: "2026-09-21T09:04:30Z" },
  },
};

interface RecordedCall {
  method: "GET" | "POST";
  path: string;
  body?: unknown;
}

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { status, data, etag: null, notModified: false };
}

function stubClient(calls: RecordedCall[]): ApiClient {
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "GET", path });
      if (path === `/imports/${RUN_ID}/columns`) return ok(COLUMNS as T);
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string, body?: unknown): Promise<ApiResponse<T>> => {
      calls.push({ method: "POST", path, body });
      if (path === "/imports") return ok(EXTRACTED as T, 201);
      if (path === `/imports/${RUN_ID}/transform`) return ok(TRANSFORMED as T);
      if (path === `/imports/${RUN_ID}/validate`) return ok(VALIDATED as T);
      if (path === `/imports/${RUN_ID}/dry-run`) {
        refuseWithdrawnMode((body as { write_mode?: string } | undefined)?.write_mode);
        return ok(DRY_INSERT as T);
      }
      if (path === `/imports/${RUN_ID}/load`) return ok(LOADED as T);
      if (path === `/imports/${RUN_ID}/rollback`) return ok(ROLLED_BACK as T);
      throw new Error(`unstubbed POST ${path}`);
    },
  } as unknown as ApiClient;
}

function mount(calls: RecordedCall[]) {
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
              element={<ImportWorkflowPage target="premises" client={stubClient(calls)} />}
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

function figure(container: HTMLElement, id: string): string {
  return container.querySelector(`[data-workflow-figure="${id}"]`)?.textContent ?? `<no ${id}>`;
}

type User = ReturnType<typeof userEvent.setup>;

/** Stage 1 → 3, the path `ImportWorkflowPage.dom.test.tsx` already pins. */
async function walkToValidate(user: User, container: HTMLElement) {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) throw new Error("stage 1 renders no file input");
  await user.upload(input, new File([CSV_TEXT], "silvercreek_premises_2026.csv", { type: "text/csv" }));
  const transform = await screen.findByRole("button", { name: "Transform →" });
  await waitFor(() => expect(transform).toBeEnabled());
  await user.click(transform);
  await waitFor(() => expect(stageOf(container)).toBe("2"));
  await user.click(await screen.findByRole("button", { name: "Validate →" }));
  await waitFor(() => expect(stageOf(container)).toBe("3"));
}

/** …and on to stage 4, where the rehearsal runs on ARRIVAL. */
async function walkToLoad(user: User, container: HTMLElement) {
  await walkToValidate(user, container);
  await user.click(await screen.findByRole("button", { name: "Load →" }));
  await waitFor(() => expect(stageOf(container)).toBe("4"));
  await waitFor(() => expect(figure(container, "create")).toContain("18"));
}

/**
 * Change the write mode the way an operator now must — DEF-770.
 *
 * Stage 4 STATES the mode and offers `Change it`, which steps back to stage 1,
 * the step that owns it. This helper is deliberately the WHOLE road rather than
 * a call into component state: a test that reached past the navigation would
 * stop noticing the day the navigation breaks, which is exactly the property
 * the PO's change depends on.
 */
async function changeWriteModeAtStepOne(user: User, container: HTMLElement, label: string) {
  await user.click(screen.getByRole("button", { name: "Change it" }));
  await waitFor(() => expect(stageOf(container)).toBe("1"));
  await user.click(screen.getByRole("radio", { name: label }));
  await walkToLoad(user, container);
}

afterEach(cleanup);

describe("WFL-01 stage 3 — the two columns that rendered nothing (DEF-535)", () => {
  it("the ACTION cell shows the server's action AND its value, and the reject row is whole", async () => {
    const user = userEvent.setup();
    const { container } = mount([]);
    await walkToValidate(user, container);

    // ⚠ `BR-MET-090` splits severity and action into two columns precisely so
    // an operator can see a WARNING THAT WRITES. Before the adapter, the
    // warning showed and the write did not: "Warning · 1 · " with an empty
    // ACTION cell. Both halves, now, and the action's VALUE with it.
    expect(await screen.findByText("Set a default · Residential")).toBeInTheDocument();
    expect(screen.getByText("Reject row")).toBeInTheDocument();

    // The reject row's four cells. `fix_hint` is the fourth column — the one
    // `RejectList`'s own docstring calls "the one that earns the screen".
    const rejectRow = container.querySelector('[data-workflow-reject="2"]');
    expect(rejectRow).not.toBeNull();
    const cells = within(rejectRow as HTMLElement);
    expect(cells.getByText("2")).toBeInTheDocument();
    expect(cells.getByText("P-10002")).toBeInTheDocument();
    expect(cells.getByText("An address is required.")).toBeInTheDocument();
    expect(cells.getByText("Load the premises first")).toBeInTheDocument();
    // …and nothing renders the literal string `undefined`, which is what the
    // shipped build put in those cells.
    expect(container.textContent).not.toContain("undefined");
  });
});

describe("WFL-01 stage 4 — the rehearsal, and the one endpoint that writes", () => {
  it("landing on stage 4 POSTs /dry-run and prints the SERVER's figures, not stage 3's counts", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);
    await walkToLoad(user, container);

    const rehearsal = calls.filter((call) => call.path === `/imports/${RUN_ID}/dry-run`);
    expect(rehearsal).toHaveLength(1);
    expect(rehearsal[0].body).toEqual({ write_mode: "insert" });

    // ⚠ `will_create` is **18** — the loader's own count of what it will write.
    // Stage 3's `clean` is **17**, because a FLAGGED row still loads
    // (BR-MET-100). A screen that re-derived this figure would print 17 and be
    // wrong by exactly the rows the PO was warned about.
    expect(figure(container, "create")).toContain("18");
    expect(figure(container, "create")).not.toContain("17");
    expect(figure(container, "update")).toContain("0");
    expect(figure(container, "reject")).toContain("2");
    // And no row was written by the rehearsal — the only write is `/load`.
    expect(calls.some((call) => call.path === `/imports/${RUN_ID}/load`)).toBe(false);
  });

  /**
   * ⛔ **AMENDED 2026-08-30 — THE MODE THIS CASE CHOSE NO LONGER EXISTS
   * (DEF-1693).**
   *
   * It read *"choosing `Replace` re-runs the rehearsal and states BR-MET-099's
   * THREE numbers in words"* and walked `Change it` → step 1 → **Replace, and
   * retire what is missing** → forward. `CR-042` (PO 2026-08-27, verbatim: *"in
   * all imports - we need 2 option on step 1 insert, insert & update; replace
   * option is not required"*) withdrew that radio from every import, so the case
   * has been RED on the branch since that commit — one of the four DEF-1693
   * names, each of which cost a later lane a cycle proving the failure was not
   * its own.
   *
   * ⚠ **IT IS REWRITTEN RATHER THAN DELETED, BECAUSE ONLY ITS *SUBJECT* WAS
   * WITHDRAWN AND ITS *PROPERTY* WAS NOT.** The property is `DEF-770`'s: the
   * mode is chosen at step 1 and merely STATED at stage 4, so revising it means
   * walking `Change it` → step 1 → choose → forward, and `writeMode` sits in the
   * dry run's query key so that road re-runs the rehearsal. That is the road a
   * clerk actually walks and it is exercised here with a mode that still
   * exists. A case that reached past the navigation would stop noticing the day
   * the navigation breaks, which is exactly what the PO's change depends on.
   *
   * ⚠ **AND BR-MET-099's THREE NUMBERS ARE ASSERTED ABSENT RATHER THAN GONE
   * UNMENTIONED.** `OQ-580` CLOSED 2026-08-27 — PO verbatim *"this si correct -
   * a for now, c if it bites"* — leaving the deactivate-what-is-missing branch
   * standing in `import_runs.py`, refused at the API boundary by name. So the
   * server can still produce those figures and NO screen may reach them. That
   * is a property worth a test, and this is where it fails if a lane re-offers
   * the mode. The figures' own coverage lives on the server, where the fixture
   * can re-enable the mode: `test_cr023_load_stage.py::
   * test_replace_states_all_three_numbers_before_it_commits`.
   */
  it("changing the mode at step 1 re-runs the rehearsal, and no mode on offer reaches BR-MET-099's three numbers", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);
    await walkToLoad(user, container);

    // DEF-770's road: stage 4 STATES the mode; `Change it` walks back to step 1,
    // the step that owns it. `Insert & update` is one of the two CR-042 left.
    await changeWriteModeAtStepOne(user, container, "Insert & update");

    // ⚠ `writeMode` IS IN THE DRY RUN'S QUERY KEY, so the walk re-runs the
    // rehearsal against the new premise rather than reprinting the old figures.
    // Two calls, and the SECOND names the mode the clerk just chose.
    await waitFor(() => {
      const rehearsals = calls.filter((call) => call.path === `/imports/${RUN_ID}/dry-run`);
      expect(rehearsals).toHaveLength(2);
      expect(rehearsals[1].body).toEqual({ write_mode: "upsert" });
    });

    // ⛔ CR-042 / OQ-580 — NEITHER SURVIVING MODE RETIRES ANYTHING, so the
    // sentence and all three figures are absent. An absent figure beats a zero
    // that reads as a promise, and a `0 will be deactivated` under `upsert`
    // would be the screen claiming a behaviour the server refuses.
    expect(screen.queryByText(/premises are on file and not in this file\./)).toBeNull();
    expect(screen.queryByText(/will be deactivated\./)).toBeNull();
    expect(container.querySelector('[data-workflow-figure="not-in-file"]')).toBeNull();
    expect(container.querySelector('[data-workflow-figure="skipped-occupied"]')).toBeNull();
    expect(container.querySelector('[data-workflow-figure="will-deactivate"]')).toBeNull();
  });

  it("`insert` shows NONE of the three — an absent figure beats a zero that reads as a promise", async () => {
    const user = userEvent.setup();
    const { container } = mount([]);
    await walkToLoad(user, container);

    expect(container.querySelector('[data-workflow-figure="will-deactivate"]')).toBeNull();
    expect(screen.queryByText(/will be deactivated\./)).not.toBeInTheDocument();
  });

  it("BR-MET-098: the commit REFUSES until it is approved, and says which bar was crossed", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);
    await walkToLoad(user, container);

    // ⚠ `because: "percent"` — 2 rejected of 20 is 10%, past the 5% bar and
    // nowhere near the 10-row one. A refusal that did not name the bar leaves
    // the operator guessing which number to change.
    expect(
      await screen.findByText(/past the 5% bar, so an Owner or an Admin has to approve it/),
    ).toBeInTheDocument();
    // Both bars are printed beside the run's own numbers (the rule's own ask).
    expect(
      screen.getByText(/more than 5% of the batch, or more than 10 rows/),
    ).toBeInTheDocument();

    const commit = screen.getByRole("button", { name: "Commit load ✓" });
    expect(commit).toBeDisabled();
    expect(screen.getByText(/Approve this load first/)).toBeInTheDocument();
    // ⚠ **AND IT REALLY DOES NOT WRITE.** A disabled button that still fires is
    // the shape a click test exists to catch.
    await user.click(commit);
    expect(calls.some((call) => call.path === `/imports/${RUN_ID}/load`)).toBe(false);

    await user.click(screen.getByLabelText("I approve this load."));
    await waitFor(() => expect(commit).toBeEnabled());
    await user.click(commit);

    const load = calls.find((call) => call.path === `/imports/${RUN_ID}/load`);
    expect(load).toBeDefined();
    // The SERVER's three keys, and only those (`import_runs.load` reads no
    // others; an unknown key is silently read as false — DEF-522's mechanism).
    expect(load?.body).toEqual({
      write_mode: "insert",
      create_rollback_point: true,
      approved: true,
    });
    await waitFor(() => expect(stageOf(container)).toBe("5"));
  });

  it("changing the write mode CLEARS an approval already given", async () => {
    const user = userEvent.setup();
    const { container } = mount([]);
    await walkToLoad(user, container);

    await user.click(screen.getByLabelText("I approve this load."));
    const commit = screen.getByRole("button", { name: "Commit load ✓" });
    await waitFor(() => expect(commit).toBeEnabled());

    // ⚠ A different mode is a different set of consequences to approve —
    // approving an `insert` and committing something else is the shape
    // BR-MET-098 exists to prevent.
    // ⚠ **DEF-770 — THE MODE IS CHOSEN AT STEP 1 AND ONLY STATED HERE.** Stage 4
    // used to carry a duplicate of step 1's control; the PO removed it (*"Write
    // mode from this screen may not required . it is already added on step 1"*).
    // The BEHAVIOUR under test is unchanged and is the reason this case exists,
    // so the case now walks the road a clerk walks: `Change it` → step 1 →
    // choose → forward again.
    // ⛔ **AMENDED 2026-08-30 (DEF-1693): the mode chosen here was `Replace, and
    // retire what is missing`, which `CR-042` withdrew on 2026-08-27** (PO:
    // *"replace option is not required"*), leaving this case red on the branch.
    // `Insert & update` is one of the two the ruling left, and the property
    // under test — a changed premise voids an approval already given — is
    // exactly the same one, because BR-MET-098 is about the mode CHANGING and
    // never about which mode it changed to.
    await changeWriteModeAtStepOne(user, container, "Insert & update");
    await waitFor(() => expect(commit).toBeDisabled());
    expect(screen.getByLabelText("I approve this load.")).not.toBeChecked();
  });
});

describe("WFL-01 stage 5 — the receipt, and a rollback the product cannot honour", () => {
  async function commitAndLand(user: User, container: HTMLElement) {
    await walkToLoad(user, container);
    await user.click(screen.getByLabelText("I approve this load."));
    const commit = screen.getByRole("button", { name: "Commit load ✓" });
    await waitFor(() => expect(commit).toBeEnabled());
    await user.click(commit);
    await waitFor(() => expect(stageOf(container)).toBe("5"));
  }

  it("mounts the Receipt with the run's own six fields (the component nothing rendered)", async () => {
    const user = userEvent.setup();
    const { container } = mount([]);
    await commitAndLand(user, container);

    // ⚠ `Receipt` was one of G40's three unmounted components: built, tested,
    // and drawn by nothing, because stage 5 did not exist. This is the mount.
    const receipt = container.querySelector('[data-workflow="receipt"]');
    expect(receipt).not.toBeNull();
    expect(receipt?.getAttribute("data-run")).toBe(RUN_ID);
    const shown = within(receipt as HTMLElement);
    expect(shown.getByText("silvercreek_premises_2026.csv")).toBeInTheDocument();
    // ⚠ **AMENDED 2026-08-26 (DEF-767).** This asserted `${HASH} · verified` —
    // sixty-four hex characters as the visible value — and it passed while the
    // PO read the deployed receipt and said *"We get database keys on this
    // screen"*. The PROPERTY it exists to pin is unchanged and still asserted:
    // the verdict is a FLAG the server sets, never a word concatenated onto the
    // hash. Only where each half lives has moved — the clerk reads the verdict,
    // and the fingerprint is evidence on the hover.
    expect(shown.getByText("Matched the file you uploaded.")).toBeInTheDocument();
    expect(shown.getByTitle(HASH)).toBeInTheDocument();
    expect(shown.getByText("alex@silvercreek.example")).toBeInTheDocument();
    expect(shown.getByText("sess_2b41 · 71.42.108.14")).toBeInTheDocument();
    // An absent field prints "Not recorded" rather than going quietly blank.
    expect(shown.getByText("Not recorded")).toBeInTheDocument();
    // The rollback point, with an expiry worded from the SERVER's date — the
    // screen never types "30 days".
    // ⚠ **AMENDED 2026-08-26 (DEF-767).** This required the rollback POINT's id
    // to be visible text, and it was passing while the deployed receipt showed
    // `01a03d62-3811-765d-a214-79352d02c075` to a clerk. Nothing was ever
    // actionable through that id — the `Roll back this run` control performs
    // the rollback — so what a clerk needs is the DEADLINE, and the id must NOT
    // be on screen at all. The case now asserts both halves.
    expect(shown.getByText(/available until/)).toBeInTheDocument();
    expect(shown.queryByText(/RB-2813/)).toBeNull();

    // The result KPIs are what the run RECORDED (BR-MET-090 past the commit)
    // — 18 loaded, 2 rejected, 1 flagged, never recounted from the database.
    expect(figure(container, "loaded")).toContain("18");
    expect(figure(container, "rejected")).toContain("2");
    expect(figure(container, "flagged")).toContain("1");
  });

  it("rolls the run back LIVE — arm, confirm, and the receipt says what was kept (DEF-552)", async () => {
    // ⚠ **THIS CASE WAS THE DEF-541-ERA PIN, INVERTED.** It used to assert the
    // button DISABLED with "not switched on yet" — correct on the day W2
    // mounted the screen, and a lie one engine fix later: the endpoint
    // answered while the control still claimed it could not (`DEF-552`, the
    // hard-won-law-1 shape in a title attribute).
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);
    await commitAndLand(user, container);

    // The consequence sentence still comes BEFORE the button (B14 rule 11).
    //
    // ⚠ AMENDED 2026-08-24 (DEF-623). This asserted *"Units with an active
    // account on them are skipped."* — the ONE sentence `RollbackNotice`
    // printed for all six kinds, which is why an ACCOUNTS receipt told the
    // operator that rolling back reverses premises and units. This mount is the
    // PREMISES target, so it now asserts the premises kind's own sentence and
    // that the UNITS half of the old copy is gone from it: a premises run
    // creates premises and nothing else (BR-MET-085).
    const notice = container.querySelector('[data-workflow="rollback-notice"]');
    expect(notice).not.toBeNull();
    expect(notice?.textContent).toContain(WORKFLOW_KINDS.premises.rollbackBody.en);
    expect(notice?.textContent).not.toContain("reverses every premise and unit");

    // Arm: the first click fires NO request — the danger tier's two-step.
    const before = calls.length;
    await user.click(
      within(notice as HTMLElement).getByRole("button", { name: "Roll back this run" }),
    );
    expect(calls.length).toBe(before);

    // Cancel disarms without a request, and the arm button returns.
    await user.click(within(notice as HTMLElement).getByRole("button", { name: "Cancel" }));
    expect(calls.length).toBe(before);
    await user.click(
      within(notice as HTMLElement).getByRole("button", { name: "Roll back this run" }),
    );

    // Confirm: exactly one POST to the rollback door.
    await user.click(
      within(notice as HTMLElement).getByRole("button", { name: "Yes — roll this run back" }),
    );
    expect(
      calls.filter((c) => c.method === "POST" && c.path === `/imports/${RUN_ID}/rollback`),
    ).toHaveLength(1);

    // And the notice redraws from the SERVER's answer: 16 reversed, 2 kept —
    // never a client-side guess, and no second offer of the same rollback.
    expect(notice?.textContent).toContain("16 reversed");
    expect(notice?.textContent).toContain("2 kept");
    expect(
      within(notice as HTMLElement).queryByRole("button", { name: "Roll back this run" }),
    ).toBeNull();
  });

  it("stage 5 has no footer and exits to the list — r10's own shape", async () => {
    const user = userEvent.setup();
    const { container } = mount([]);
    await commitAndLand(user, container);

    expect(container.querySelector('[data-workflow="footer"]')).toBeNull();
    const exit = screen.getByRole("link", { name: "Go to Premises →" });
    expect(exit).toHaveAttribute("href", `/${TEST_TENANT}/premises`);
    await user.click(exit);
    expect(await screen.findByText("premises list")).toBeInTheDocument();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-023 W2 (B15 §4.4–§4.5 · §12 rows 5–9; BR-MET-098/099/100 PO
//         rulings 2026-08-21) + DEF-535 (the fix this lane owns)
// generated: 2026-08-22 by the CR-023 W2 stage-4/5 lane
// checklist: A✔ B✔ C✔ D✔(case 1 proved RED first — the adapter removed, the
//         ACTION cell and the reject's fix text vanish; quoted in the header)
//         E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: vitest✔ (jsdom via the file pragma; the default environment stays
//         `node`) · tsc✔ · g40 (this suite is where `Receipt` and
//         `RollbackNotice` are finally rendered)
// exceptions: E3 **NO STORY OWNS WFL-01** — hard-won law 8, reported rather
//         than invented; B15 §11 lists the runner as new and A1 allocates no
//         id · E3 the rollback ACTION is asserted DISABLED, which is a
//         statement about `DEF-541` and not about the design: when that guard
//         is fixed this case must be rewritten to click it · E3 the dry run's
//         `unplanned_units` is not asserted here because the server's own
//         figure is wrong for a units run (`DEF-544`) and this run is premises
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
