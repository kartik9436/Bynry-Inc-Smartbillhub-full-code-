// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-046 wave E (E1 · E2 · E3 · E4) — "the identifier is ours to
//          issue, and the write mode decides what a known record does"
//          (PO, 2026-08-27). The wizard's three screens told an operator the
//          OLD story: step 1 said a known record is *reported*, stage 2 never
//          rendered the identifier column's new header or its help, and the
//          rehearsal printed "Will create 20" over numbers the operator had
//          no way to learn.
// Rules:   CR-046 step 5 shape (1)-(5) · BR-AST-026 (the series allocates,
//          per-type prefix, shared sequence) · BR-AST-045 / OQ-840 CLOSED
//          (no unit -> Inventory / Spare; unit named -> Installed / Active) ·
//          DEF-1079 (the split is a SUBSET of will_create) · DEF-962 (a
//          sample cell is proved by READING THE FILE, never by reading the
//          column definition) · B14 rule 21 (Tailwind; this file's subject,
//          `ImportWorkflowPage.tsx`, is on `route-b-migrated.txt` line 1830)
// ───────────────────────────────────────────────────────
// ⚠ **EVERY ASSERTION HERE READS RENDERED OUTPUT OR DOWNLOADED BYTES.**
// Hard-won law 2: a served field nobody draws is dead UI that passes every
// type check — `will_issue` has been served by `_dry_run_assets` since
// 2026-08-27 and was declared in NO TypeScript interface and drawn on NO
// screen, which is `DEF-752`'s exact shape for the fourth time.
//
// ⚠ **THE `SAMPLE_METERS_CSV` FIXTURE BELOW IS NOT WRITTEN BY HAND.** It is
// the verbatim body `import_runs.sample_csv("assets_meters")` produced on the
// Brazos Bend fixture, captured 2026-08-27. `DEF-962` shipped an invented
// number into this very cell because only the column DEFINITION was checked,
// so the backend half (`tests/test_cr046_e4_sample_identifier_blank.py`)
// asserts the bytes and this half asserts the CLICK delivers them unaltered.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { ImportWorkflowPage } from "./ImportWorkflowPage";

const TEST_TENANT = "ottumwa-water-works";
const RUN_ID = "5f2b7c1e-0000-4000-8000-000000000046";

/** The server's own words for the reshaped column (`_asset_number_column`). */
const ASSET_NO_LABEL = "Meter number (existing only)";
const ASSET_NO_HELP =
  "LEAVE THIS BLANK for a new meter — SMART360 Next issues the number from " +
  "Settings → Numbering, so it can never collide with one already in use or " +
  "arrive in a shape your settings would not produce. Fill it in ONLY to " +
  "update a meter already on file, quoting the number this system shows on " +
  "its own screen. Your old system's number goes in External reference, and " +
  "the manufacturer's number goes in Serial number.";

/**
 * ⚠ VERBATIM BACKEND OUTPUT — `import_runs.sample_csv("assets_meters")`,
 * Brazos Bend, 2026-08-27. Do not tidy it: the blank first cell IS the
 * assertion, and a hand-written fixture would prove nothing about the file a
 * person actually receives.
 */
const SAMPLE_METERS_CSV =
  "asset_no,serial_no,meter_type,service,read_method,multiplier,unit_ref," +
  "manufacturer,model,install_date,certification_due,warranty_end,supplier," +
  "purchase_cost,external_ref\n" +
  ",Sample serial number,ami,electric,ami,1,,Sample Meter Co,MX-100," +
  "01/01/2026,01/01/2027,01/01/2031,Sample Meter Co,164.0000,\n";

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { status, data, etag: null, notModified: false };
}

const COLUMNS = {
  target: "assets_meters",
  columns: [
    {
      target: "asset_no",
      label: ASSET_NO_LABEL,
      kind: "text",
      required: false,
      transforms: [],
      sample: "",
      blank_means: "a new number is issued from your numbering settings",
      help: ASSET_NO_HELP,
    },
    { target: "serial_no", label: "Serial number", kind: "text", required: true, transforms: [] },
    { target: "service", label: "Service", kind: "lookup", required: true, transforms: [] },
    { target: "__ignore__", label: "— ignore —", kind: "text", required: false, transforms: [] },
  ],
  unavailable_transforms: [],
  row_handling: ["drop_exact_duplicates", "keep_latest_on_key", "skip_rows_missing_required"],
};

/** Twenty meters — the PO's own rehearsal in DEF-1079, and CR-046's worked case. */
const ROWS = 20;

const COUNTS = {
  in: ROWS,
  duplicates_dropped: 0,
  skipped: 0,
  forward: ROWS,
  checked: ROWS,
  clean: ROWS,
  errors: 0,
  warnings: 0,
};

function runDict(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    id: RUN_ID,
    run_no: "IMP-2026-000046",
    target: "assets_meters",
    source_kind: "file",
    file_name: "meter_fleet_2026.csv",
    file_hash: "46108f2c3d4e5a6b7c8d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d",
    file_bytes: 4_200,
    encoding_delimiter: "UTF-8 · comma (detected)",
    mapping_id: null,
    mapping_spec: null,
    batch_label: null,
    write_mode: null,
    counts: COUNTS,
    status: "extracted",
    session_ref: null,
    ip: null,
    started_at: "2026-08-27T09:00:00Z",
    finished_at: null,
    progress: null,
    headers: ["SERIAL", "SVC"],
    detected_mapping: { SERIAL: "serial_no", SVC: "service" },
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
  rules: [],
  rejects: [],
  blocking_rules: { count: 0, platform: 0, structural: 0 },
});

const APPROVAL = {
  threshold_pct: 5,
  threshold_rows: 10,
  rejected: 0,
  of_rows: ROWS,
  required: false,
  because: "percent",
};

/**
 * `_dry_run_assets`' answer, field for field — including `will_issue`, which
 * `assets.selectors.asset_no_preview_run` returns and which no screen drew.
 * Twelve of the twenty name no unit (r10's own 1,243 / 12 split, scaled), so
 * the two outcome figures are 8 and 12 and they SUM to `will_create`.
 */
const DRY_INSERT = {
  will_create: ROWS,
  will_create_in_service: 8,
  will_create_to_inventory: 12,
  will_update: 0,
  skipped_existing: 0,
  rejected: 0,
  target: "assets_meters",
  unplanned_units: 0,
  unplanned_plans: [],
  unit_tagged: 8,
  to_inventory: 12,
  will_issue: {
    series_format: "M-{00000}",
    next_number: 42,
    count: ROWS,
    numbers: ["M-00042", "M-00043", "M-00044", "M-00045", "M-00046"],
    last: "M-00061",
  },
  approval: APPROVAL,
};

/** The same run on a tenant with no `asset` series row: `_issued_numbers_block`
 *  returns `{}` and the key is ABSENT. The screen owes a sentence, not a gap. */
const DRY_NO_SERIES = { ...DRY_INSERT, will_issue: undefined };

function stubClient(dry: unknown = DRY_INSERT, sample = SAMPLE_METERS_CSV): ApiClient {
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      if (path === `/imports/${RUN_ID}/columns`) return ok(COLUMNS as T);
      if (path === "/imports/sample?target=assets_meters") return ok(sample as T);
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string): Promise<ApiResponse<T>> => {
      if (path === "/imports") return ok(runDict({}) as T, 201);
      if (path === `/imports/${RUN_ID}/transform`)
        return ok(runDict({ status: "transformed", mapping_spec: SPEC }) as T);
      if (path === `/imports/${RUN_ID}/validate`) return ok(VALIDATED as T);
      if (path === `/imports/${RUN_ID}/dry-run`) return ok(dry as T);
      throw new Error(`unstubbed POST ${path}`);
    },
  } as unknown as ApiClient;
}

function mount(dry: unknown = DRY_INSERT, sample = SAMPLE_METERS_CSV) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/assets/import/meters`]}>
          <Routes>
            <Route
              path="/:tenant/assets/import/meters"
              element={
                <ImportWorkflowPage target="assets_meters" client={stubClient(dry, sample)} />
              }
            />
            <Route path="/:tenant/assets" element={<div>assets list</div>} />
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

/**
 * jsdom's `Blob` carries no `.text()`, so the bytes come back through
 * `FileReader` — the same API a browser hands a page. Reading the BLOB rather
 * than the fetched string is the point: it is the last object between the
 * server's answer and the operator's disk, and `DEF-962` lived in exactly that
 * gap.
 */
function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

async function pickFile(user: User, container: HTMLElement) {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) throw new Error("stage 1 renders no file input");
  await user.upload(
    input,
    new File([SAMPLE_METERS_CSV], "meter_fleet_2026.csv", { type: "text/csv" }),
  );
}

async function toStageTwo(user: User, container: HTMLElement) {
  await pickFile(user, container);
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

// ═══════════════════════════════════════════════════════════════════════════
// E1 — step 1 says REJECT and UPDATE, never "reported"
// ═══════════════════════════════════════════════════════════════════════════
describe("CR-046 E1 — the write mode says what actually happens to a known row", () => {
  it("INSERT NEW ONLY states that a row naming a record on file is REJECTED", async () => {
    // ⚠ No click: `insert` is the DEFAULT (hard-won law 3, the safe option is
    // the one you get without typing), so this reads what a clerk who touches
    // nothing is told.
    const { container } = mount();

    const consequence = block(container, "write-mode-consequence");
    expect(consequence, "step 1 draws no consequence for the default mode").not.toBeNull();
    // The mode CR-046 clause (iii) changed: `AST.NUMBER_ON_FILE` warned by
    // design (DEF-543) and now ERRORS, so the row does not load at all.
    expect(consequence).toHaveTextContent(/reject/i);
    // ⛔ The OLD sentence, which is now false. It said the record is "left
    // exactly as it is" and the rows are "counted and shown to you" — which
    // is REPORTING, the very word CR-046 E1 strikes.
    expect(consequence).not.toHaveTextContent(/counted and shown to you/i);
    expect(consequence).not.toHaveTextContent(/left exactly as it is/i);
  });

  it("INSERT & UPDATE states that the record's DETAILS are updated", async () => {
    const user = userEvent.setup();
    const { container } = mount();

    await user.click(screen.getByRole("radio", { name: /Insert & update/i }));
    const consequence = block(container, "write-mode-consequence");
    expect(consequence).toHaveTextContent(/updat/i);
    // CR-046 shape (1): the number is issued, on BOTH modes, for a new row.
    expect(consequence).toHaveTextContent(/Numbering/i);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// E2 — the identifier column's new header AND its help reach the screen
// ═══════════════════════════════════════════════════════════════════════════
describe("CR-046 E2 — stage 2 shows the identifier column's header and help", () => {
  it("renders BOTH the new header and the server's help sentence, whole", async () => {
    const user = userEvent.setup();
    const { container } = mount();
    await toStageTwo(user, container);

    const note = block(container, "column-help-asset_no");
    expect(
      note,
      "stage 2 says nothing about the column whose meaning just changed",
    ).not.toBeNull();
    // The HEADER — the operator has to recognise it in their own file.
    expect(note).toHaveTextContent(ASSET_NO_LABEL);
    // …and the whole help sentence, not a truncated head of it.
    expect(note).toHaveTextContent("LEAVE THIS BLANK for a new meter");
    expect(note).toHaveTextContent("Your old system's number goes in External reference");
    // ⚠ NOT TRUNCATED OR SWALLOWED — no line-clamp, no ellipsis, no overflow
    // hidden anywhere on the element that carries the sentence.
    expect(note?.className ?? "").not.toMatch(/truncate|line-clamp|overflow-hidden|text-ellipsis/);
  });

  it("draws nothing for a column the server gave no help for", async () => {
    const user = userEvent.setup();
    const { container } = mount();
    await toStageTwo(user, container);
    expect(block(container, "column-help-serial_no")).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// E3 — the rehearsal states the projected numbers and the outcome per row
// ═══════════════════════════════════════════════════════════════════════════
describe("CR-046 E3 — the dry run projects the identifiers it will issue", () => {
  it("prints the numbers the commit will issue, and says the rehearsal issued none", async () => {
    const user = userEvent.setup();
    const { container } = mount();
    await toStageFour(user, container);

    const panel = block(container, "will-issue");
    expect(
      panel,
      "`will_issue` is served and no screen draws it — DEF-752's shape again",
    ).not.toBeNull();
    // The first numbers, verbatim off `asset_no_preview_run`.
    expect(panel).toHaveTextContent("M-00042");
    expect(panel).toHaveTextContent("M-00046");
    // …and the LAST, so twenty rows do not read as five.
    expect(panel).toHaveTextContent("M-00061");
    // A PEEK, never an allocation — the rehearsal may be run twice.
    expect(panel).toHaveTextContent(/issued|nothing/i);
  });

  it("names the OUTCOME each created row lands in, per OQ-840's closing", async () => {
    const user = userEvent.setup();
    const { container } = mount();
    await toStageFour(user, container);

    const inService = container.querySelector('[data-workflow-figure="create-in-service"]');
    const toInventory = container.querySelector('[data-workflow-figure="create-to-inventory"]');
    expect(inService).not.toBeNull();
    expect(toInventory).not.toBeNull();
    // ⚠ THE STATUS BY NAME, not a paraphrase: an operator reads these two
    // words on the Assets screen afterwards, and "in service" is neither of
    // them. `assets/services.py:91` — ("inventory", "Inventory/Spare", …).
    expect(inService).toHaveTextContent(/Installed\/Active/);
    expect(inService).toHaveTextContent("8");
    expect(toInventory).toHaveTextContent(/Inventory\/Spare/);
    expect(toInventory).toHaveTextContent("12");
  });

  it("says the numbering is UNSET rather than printing a range nobody gets", async () => {
    const user = userEvent.setup();
    const { container } = mount(DRY_NO_SERIES);
    await toStageFour(user, container);

    expect(block(container, "will-issue")).toBeNull();
    const unset = block(container, "will-issue-unset");
    expect(
      unset,
      "`_issued_numbers_block` returns {} with no series row and its docstring " +
        "claims 'the screen then says the numbering is unset' — hard-won law 1",
    ).not.toBeNull();
    expect(unset).toHaveTextContent(/Numbering/i);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// E4 — the DOWNLOADED BYTES, not the column definition (DEF-962)
// ═══════════════════════════════════════════════════════════════════════════
describe("CR-046 E4 — clicking the sample download produces a blank identifier cell", () => {
  it("hands the operator the server's bytes, unaltered, with asset_no empty", async () => {
    const user = userEvent.setup();
    const saved: { name: string; body: string }[] = [];
    // The real `saveTextFile` builds a Blob and clicks an anchor. Spying on
    // both is what turns "the endpoint returns a good file" into "the person
    // who clicked received one" — `DEF-962` was invisible because only the
    // first half was ever checked.
    // ⚠ jsdom implements NEITHER `URL.createObjectURL` NOR `revokeObjectURL`,
    // so they are DEFINED here rather than spied on. That is not a workaround
    // for the test — it is the reason `DEF-962` could ship: the one line that
    // turns a fetched body into a file on disk runs in no unit test by
    // default, so "the endpoint returns a good file" was the only half anyone
    // ever checked.
    const blobs: Blob[] = [];
    (URL as unknown as { createObjectURL: (b: Blob) => string }).createObjectURL = (b: Blob) => {
      blobs.push(b);
      return "blob:cr046";
    };
    (URL as unknown as { revokeObjectURL: (u: string) => void }).revokeObjectURL = () => undefined;
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        saved.push({ name: this.download, body: "" });
      });

    mount();
    await user.click(await screen.findByRole("button", { name: /sample CSV/i }));
    await waitFor(() => expect(saved.length).toBe(1));

    // The file the operator receives, by name…
    expect(saved[0].name).toBe("assets_meters_sample.csv");
    // …and by CONTENT: the Blob handed to `createObjectURL`.
    expect(blobs.length).toBe(1);
    const body = await readBlob(blobs[0]);
    const [header, row] = body.split("\n");
    const cells = header.split(",");
    const values = row.split(",");
    const at = cells.indexOf("asset_no");
    expect(at, "the identifier column is not in the downloaded header").toBeGreaterThanOrEqual(0);
    // ⛔ **THE ASSERTION `DEF-962` NEEDED.** Not `sample === ""` on the column
    // definition — the CELL, in the bytes that left the browser.
    expect(values[at]).toBe("");
    // …and the two columns the ruling moved the old number INTO are present,
    // so a migrating utility has somewhere to put what it holds.
    expect(cells).toContain("external_ref");
    expect(cells).toContain("serial_no");

    click.mockRestore();
  });
});
