// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-054 — *"the reads upload: hand the clerk the file instead of
//           asking them to build it"* (PO 2026-08-30). Tasks 6, 11, 12, 13,
//           18, 19, 20 and 21.   Screens: RDS-03 (S28) stages 1–3
// Rules:    BR-MET-013 (mapping auto-detected on every upload) · BR-MET-032
//           (ONE published template, NO mapping memory) · BR-MET-049
//           (plan-driven read-set completeness) · BR-MET-015 (an error must be
//           resolved; a warning is accepted with a reason) · BR-MET-059 (the
//           channel model) · BR-MET-091 (a rule that could not run is DECLARED
//           with its reason, never omitted) · BR-SHL-025 (a control this
//           release cannot offer renders disabled WITH its reason) ·
//           BR-SHL-034 (ONE date formatter) · B14 rules 20 and 21
// Defect:   DEF-2443 — the flagged-rows READ DATE rendered the raw ISO instant.
// ───────────────────────────────────────────────────────
// WHAT THIS FILE DEFENDS, and why each one is invisible to every other check:
//
//   1. **The reading-sheet button names its own number, or says why it cannot.**
//      `tsc` is happy with a button whose label is a key name and whose click
//      does nothing; only rendering it and reading the text can tell.
//   2. **The register-completeness table groups by PLAN MODEL and dedupes by
//      (meter, date).** The completeness verdict is a GROUP rule attached to
//      every row of a meter's group, so a naive tally over rows reports a
//      four-register time-of-use meter four times — arithmetic that is entirely
//      plausible and entirely wrong.
//   3. **The read date goes through the shared formatter.** A `toContain`
//      assertion on a meter number passes just as happily over
//      `2026-08-03T00:00:00+00:00` as over `08/03/2026`.
//
// ⚠ THE BROWSER HALF IS NOT HERE AND CANNOT BE. jsdom does no layout, so the
// binding proof for these screens is `10-scripts/render-checks/cr054-reads-
// upload.mjs`, per the PO's rule of 2026-08-30: *"All UI screen should be
// confirm using real broswer testing and not just based on test cases"*.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import type { MyPermissions, ReadImportBatchRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import {
  READS_SOURCE_CHOICES,
  RULE_PLAN_REGISTERS,
  UploadReadsWizard,
  fileComposition,
  fileMappingRows,
  registerGroups,
  ruleResults,
  unmappedTargets,
  uploadReadMethodsKey,
  validationTiles,
} from "./UploadReadsWizard";
import { PREMISES_PERMISSION } from "./meteringShared";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const BATCH_ID = "b-054";
const CYCLE_ID = "c-002";

/** The clerk's own file — a time-of-use meter with its four rows, and one
 *  column (`site`) the published template has never heard of. */
const CSV_TEXT = [
  "meter_id,read_date,channel,reading,site",
  "M-7450,2026-08-03,tou_on,120,Silver Creek",
  "M-7450,2026-08-03,tou_mid,140,Silver Creek",
  "M-7450,2026-08-03,tou_off,164,Silver Creek",
  "M-7450,2026-08-03,total,424,Silver Creek",
  "M-7301,2026-08-03,total,318,Silver Creek",
].join("\n");

/** `POST /read-batches` — the batch, its counts and the detected mapping. */
const STAGED = {
  id: BATCH_ID,
  batch_no: "B-2608-09",
  status: "staged",
  source_kind: "csv",
  source_detail: null,
  read_method: null,
  period_month: "2026-08-01",
  cycle_id: CYCLE_ID,
  route_id: null,
  service: null,
  compliance: {
    file_name: "silvercreek_reads_08.csv",
    // BR-MET-018 — the SERVER's digest. `DropZone` states it the moment the
    // file is accepted, so "verified" on the receipt means something later.
    file_hash: "9f2c41ab7d0e5c88",
    uploaded_by: "01a01d99-d617-7aa9-9f07-e2c08cc4fdc9",
    uploaded_by_name: "Marcus Johnson",
    uploaded_at: "2026-08-06T14:14:22Z",
    session_ref: "sess_9f27",
    ip: "98.200.114.7",
    certified: false,
    cosigned_by: null,
    cosigned_by_name: null,
  },
  counts: {
    rows: 5,
    passed: 4,
    warnings: 1,
    errors: 0,
    rows_with_unevaluated: 0,
    accepted: 0,
    rejected: 0,
    field_visit: 0,
    skipped: 0,
    estimate_requested: 0,
    undispositioned: 5,
    posted: 0,
    severity_total: 5,
    reconciles: true,
  },
  posted_at: null,
  mapping: {
    meter_id: "meter_id",
    read_date: "read_date",
    channel: "channel",
    reading: "reading",
    notes: null,
  },
};

/** BR-MET-049's verdict, exactly as `plan_register_completeness` stores it —
 *  attached to EVERY row of the (meter, date) group, which is the shape the
 *  grouping has to survive. */
function completenessOutcome(over: Record<string, unknown>) {
  return {
    rule: RULE_PLAN_REGISTERS,
    severity: "warning",
    detail: {
      expected: ["total", "tou_on", "tou_mid", "tou_off"],
      received: ["total"],
      missing: ["tou_on", "tou_mid", "tou_off"],
      unexpected: [],
      plan_model: "time_of_use",
      plan_id: "p-res-std",
      summary: "expects total/tou_on/tou_mid/tou_off, file has total only",
      ...over,
    },
  };
}

function row(over: Partial<ReadImportBatchRow> = {}): ReadImportBatchRow {
  return {
    row_no: 1,
    meter_no: "M-7450",
    asset_id: "a-7450",
    read_at: "2026-08-03",
    read_at_raw: "2026-08-03",
    channel: "tou_on",
    value: "120.000000",
    raw_value: "120.000000",
    unit: "kWh",
    service: "electric",
    read_method: null,
    note: null,
    severity: "ok",
    rule_outcomes: [
      {
        rule: RULE_PLAN_REGISTERS,
        severity: "ok",
        detail: {
          expected: ["total", "tou_on", "tou_mid", "tou_off"],
          received: ["total", "tou_on", "tou_mid", "tou_off"],
          missing: [],
          plan_model: "time_of_use",
        },
      },
    ],
    disposition: null,
    disposition_reason: null,
    demand_reset_noted: false,
    is_peak: false,
    meter_read_id: null,
    ...over,
  };
}

/** M-7450 complete on four registers; M-7301 short of three. */
const ROWS: ReadImportBatchRow[] = [
  row(),
  row({ row_no: 2, channel: "tou_mid", value: "140.000000" }),
  row({ row_no: 3, channel: "tou_off", value: "164.000000" }),
  row({ row_no: 4, channel: "total", value: "424.000000" }),
  row({
    row_no: 5,
    meter_no: "M-7301",
    asset_id: "a-7301",
    channel: "total",
    value: "318.000000",
    severity: "warning",
    rule_outcomes: [completenessOutcome({})],
  }),
];

const VALIDATION = {
  ...STAGED,
  status: "validated",
  unevaluated_rules: [{ rule: "factor_flag", reason: "no_threshold_configured" }],
  validation_config_present: true,
  // ⛔ DEF-2440 — the SERVER's own field names, read off a live batch. The
  // three this fixture used to declare are sent by nothing, and a fixture that
  // invents a shape asserts the lane's own mistake back at it.
  cycle_coverage: {
    cycle_code: "CY-002",
    expected_meters: 18,
    received_in_batch: 5,
    committed_before_batch: 0,
    missing_after_batch: 13,
  },
};

const SHEET_SUMMARY = {
  cycle_id: CYCLE_ID,
  cycle_code: "CY-002",
  period_start: "2026-08-01",
  period_end: "2026-08-03",
  window_absent_reason: null,
  rows: 18,
  meters: 5,
  registers: { total: 5, tou_on: 4, tou_mid: 4, tou_off: 4, export: 1 },
  unresolved_meters: 0,
  unresolved: [],
  filename: "reading_sheet_CY-002_2026-08.csv",
};

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { status, data, etag: null, notModified: false };
}

interface Call {
  method: string;
  path: string;
  body?: unknown;
}

function stubClient(calls: Call[], overrides: { sheet?: unknown } = {}): ApiClient {
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "GET", path });
      if (path === "/cycles") {
        return ok({ count: 1, results: [{ id: CYCLE_ID, code: "CY-002", name: "Residential" }] } as T);
      }
      if (path === "/routes") return ok({ count: 0, results: [] } as T);
      if (path === "/reads/read-methods") return ok({ results: [{ code: "walk_by", name: "Walk-by" }] } as T);
      // CR-054 task 9's control reads this. Stubbed here so these cases render
      // the control's ORDINARY state; without it the query throws, the control
      // correctly draws its "could not be read" sentence, and every assertion
      // below still passes — over a stage 1 nobody meant to test.
      // `CR054ServiceTag.dom.test.tsx` is where the control itself is pinned.
      if (path === "/settings/services") {
        return ok([
          { service: "electric", name: "Electric", enabled: true },
          { service: "water", name: "Water", enabled: true },
        ] as T);
      }
      if (path === `/cycles/${CYCLE_ID}/reading-sheet/summary`) {
        return ok((overrides.sheet ?? SHEET_SUMMARY) as T);
      }
      if (path === `/read-batches/${BATCH_ID}`) {
        return ok({ ...VALIDATION, rows: ROWS } as T);
      }
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string, body?: unknown): Promise<ApiResponse<T>> => {
      calls.push({ method: "POST", path, body });
      if (path === "/read-batches") return ok(STAGED as T, 201);
      if (path === `/read-batches/${BATCH_ID}/validate`) return ok(VALIDATION as T);
      throw new Error(`unstubbed POST ${path}`);
    },
    request: async <T,>(path: string, options?: { method?: string; body?: unknown }) => {
      calls.push({ method: options?.method ?? "PATCH", path, body: options?.body });
      return ok({} as T);
    },
  } as unknown as ApiClient;
}

function permissions(): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  };
}

function mount(calls: Call[], overrides: { sheet?: unknown } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  queryClient.setQueryData(queryKeys.myPermissions, permissions());
  queryClient.setQueryData(uploadReadMethodsKey, [{ code: "walk_by", name: "Walk-by" }]);
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/reads/upload`]}>
          <Routes>
            <Route
              path="/:tenant/reads/upload"
              element={<UploadReadsWizard client={stubClient(calls, overrides)} />}
            />
            <Route path="/:tenant/reads" element={<div>reads list</div>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

type User = ReturnType<typeof userEvent.setup>;

/** Stage 1 → 2: a reading month and a cycle, then forward. */
async function walkToUpload(user: User, container: HTMLElement): Promise<void> {
  const month = container.querySelector<HTMLInputElement>("#period_month");
  if (month === null) throw new Error("stage 1 draws no reading-month field");
  await user.type(month, "2026-08-03");
  const cycle = container.querySelector<HTMLSelectElement>("#cycle_id");
  if (cycle !== null) {
    await waitFor(() => expect(cycle.options.length).toBeGreaterThan(1));
    await user.selectOptions(cycle, CYCLE_ID);
  }
  await user.click(await screen.findByRole("button", { name: t("workflow.advance.transform") }));
}

describe("CR-054 · the pure pieces, provable without a browser", () => {
  it("DEF-2441: the grouped rule's code is the SERVER's, not its function name", () => {
    // ⚠ THE FIXTURES BELOW CANNOT CATCH THIS AND DID NOT. They are written from
    // the same source as the code, so a wrong rule code asserts itself back.
    // What decides it is the value `apps/metering/validation.py` actually
    // stores — `RULE_PLAN_REGISTERS = "plan_registers"` — which is also the
    // only `metering.reads.status.*` key the catalogue defines for it. A code
    // no catalogue can name is a code no row carries.
    expect(RULE_PLAN_REGISTERS).toBe("plan_registers");
    expect(i18n.exists(`metering.reads.status.${RULE_PLAN_REGISTERS}`)).toBe(true);
  });

  it("task 18: the two transports are the KIT's cards, and there is no third", () => {
    // BR-MET-123 clause 3 — *"a transport card with nothing behind it is not
    // offered"*. The kit CAN draw an unavailable card; reads has none to draw.
    expect(READS_SOURCE_CHOICES.map((choice) => choice.id)).toEqual(["csv", "manual"]);
    expect(READS_SOURCE_CHOICES.every((choice) => choice.available)).toBe(true);
  });

  it("task 18: the mapping carries a SAMPLE VALUE out of the clerk's own file", () => {
    // ⚠ The sibling importer leaves this column empty and files DEF-521,
    // because its file lives on the server. Reads has the bytes in the browser.
    const rows = fileMappingRows(CSV_TEXT, STAGED.mapping);
    expect(rows.map((entry) => entry.source_column)).toEqual([
      "meter_id",
      "read_date",
      "channel",
      "reading",
      "site",
    ]);
    expect(rows[0].sample_value).toBe("M-7450");
    expect(rows[3].sample_value).toBe("120");
    // A column the template has never heard of is UNMAPPED, not ignored: nobody
    // decided to drop `site`, and the two are different answers.
    expect(rows[4].target_column).toBeNull();
    expect(rows[4].status).toBe("unmapped");
    // …and a template field the file did not carry is named separately, never
    // smuggled in as a row whose source column is blank.
    expect(unmappedTargets(STAGED.mapping)).toEqual(["notes"]);
  });

  it("task 11: 'what is in this file' counts rows, meters, services, dates and each register", () => {
    const figures = fileComposition(ROWS, t);
    const at = (id: string): unknown => figures.find((figure) => figure.id === id)?.value;
    expect(at("rows")).toBe(5);
    expect(at("meters")).toBe(2);
    expect(at("services")).toBe("electric");
    expect(at("dates")).toBe("2026-08-03");
    // THE LINE THAT EARNS THE PANEL: two of the five rows are `total` and the
    // other three are time-of-use windows. A clerk who uploaded one row per
    // meter against a time-of-use cycle sees it here, not at the bill run.
    expect(at("register-total")).toBe(2);
    expect(at("register-tou_on")).toBe(1);
    expect(at("register-tou_mid")).toBe(1);
    expect(at("register-tou_off")).toBe(1);
  });

  it("task 18: a rule that could not run is a ROW of the table, with its reason (BR-MET-091)", () => {
    const results = ruleResults(ROWS, VALIDATION.unevaluated_rules, t);
    const unavailable = results.find((result) => result.code === "unevaluated|factor_flag");
    expect(unavailable).toBeDefined();
    expect(unavailable?.available).toBe(false);
    expect(unavailable?.unavailable_reason).not.toBe("");
    // A shortfall is a WARNING and its action is BR-MET-015's, not an invention.
    const warning = results.find((result) => result.code.startsWith(RULE_PLAN_REGISTERS));
    expect(warning?.severity).toBe("warning");
    expect(warning?.action_label).toBe(t("metering.upload.validate.actionWarning"));
  });

  it("task 12: the completeness table dedupes by (meter, date) before it groups", () => {
    // ⚠ THE ARITHMETIC THIS PINS. The verdict is a GROUP rule and lands on every
    // row of the meter's group, so a tally over ROWS would count M-7450's four
    // registers four times and report 20 expected against a plan that expects 8.
    const groups = registerGroups(ROWS);
    expect(groups).toHaveLength(1);
    const [tou] = groups;
    expect(tou.planModel).toBe("time_of_use");
    expect(tou.meters).toBe(2);
    expect(tou.short).toBe(1);
    expect(tou.expects).toBe(8);
    expect(tou.arrived).toBe(5);
    expect(tou.missing).toBe(3);
    expect(tou.missingChannels).toEqual(["tou_on", "tou_mid", "tou_off"]);
    // Task 13 acts on the SHORT meter's rows only — a complete meter has
    // nothing to estimate and nobody to send out.
    expect(tou.rowNos).toEqual([5]);
  });

  it("task 20: the Missing tile is the SERVER's figure now, and an em-dash only when there is none", () => {
    // ⚠ The 33-word note that stood here — *"that calculation is not built"* —
    // stopped being true when CR-038 W1 built BR-MET-049's resolver. Hard-won
    // law 1: a screen claiming an absence is not the absence.
    const withCoverage = validationTiles(VALIDATION as never, t);
    expect(withCoverage.find((tile) => tile.id === "missing")?.value).toBe(13);
    const noCycle = validationTiles({ ...VALIDATION, cycle_coverage: null } as never, t);
    expect(noCycle.find((tile) => tile.id === "missing")?.value).toBe("—");
  });
});

describe("CR-054 · RDS-03 in a DOM", () => {
  it("task 6: the reading-sheet button names its cycle and its row count", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    const { container } = mount(calls);
    await walkToUpload(user, container);
    const button = await screen.findByRole("button", {
      name: t("metering.upload.file.sheetDownload", { cycle: "CY-002", rows: 18 }),
    });
    expect(button).toBeEnabled();
    // The count came from the SUMMARY route, never from downloading the file
    // to measure it (hard-won law 5).
    expect(calls.some((call) => call.path.endsWith("/reading-sheet/summary"))).toBe(true);
    expect(calls.some((call) => call.path.endsWith("/reading-sheet"))).toBe(false);
    // …and the STARTER FILES are still offered BESIDE it, never instead.
    // ⚠ `CR-077`: this was ONE button naming `reads_template.csv`, and it is
    // four now — one per read SHAPE. The assertion counts all four rather than
    // naming one, because the thing this case is protecting is that the sheet
    // did not REPLACE the starters, and a check that names one button would go
    // on passing with the other three gone.
    for (const shape of ["flat", "tou", "demand", "net"]) {
      expect(screen.getByTestId(`reads-starter-${shape}`)).toBeEnabled();
    }
  });

  it("task 6 / BR-SHL-025: a cycle with no read window disables the button WITH the reason", async () => {
    const user = userEvent.setup();
    const { container } = mount([], {
      sheet: { ...SHEET_SUMMARY, rows: 0, window_absent_reason: "cycle_window_not_set" },
    });
    await walkToUpload(user, container);
    expect(await screen.findByText(t("metering.read.reason.cycle_window_not_set"))).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: t("metering.upload.file.sheetDownloadPlain") }),
    ).toBeDisabled();
  });

  it("tasks 11 and 18: staging draws the file's composition and the mapping with samples", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    const { container } = mount(calls);
    await walkToUpload(user, container);
    const paste = container.querySelector<HTMLTextAreaElement>("#reads-text");
    if (paste === null) throw new Error("stage 2 draws no paste field");
    await user.click(paste);
    await user.paste(CSV_TEXT);
    await user.click(screen.getByRole("button", { name: t("metering.upload.file.stage") }));

    // The kit's drop target states what the SERVER received, hash included.
    await waitFor(() =>
      expect(container.querySelector('[data-workflow="dropzone-hash"]')).toBeInTheDocument(),
    );
    expect(container.querySelector('[data-workflow="dropzone-hash"]')?.textContent).toContain(
      "9f2c41ab7d0e5c88",
    );
    // Task 11's panel, from the rows the server staged.
    await waitFor(() =>
      expect(container.querySelector('[data-workflow-figure="register-tou_on"]')).toBeInTheDocument(),
    );
    expect(
      container.querySelector('[data-workflow-figure="register-tou_on"]')?.textContent,
    ).toContain("1");
    // The mapping is a STATEMENT: BR-MET-032 keeps no mapping and no route
    // remaps a read batch, so the kit's picker is not drawn.
    const mapping = container.querySelector('[data-workflow="mapping"]');
    expect(mapping).toBeInTheDocument();
    expect(mapping?.querySelectorAll("select")).toHaveLength(0);
    expect(mapping?.textContent).toContain("M-7450");
  });

  it("tasks 12, 13 and 21: stage 3 groups the shortfall, offers both bulk actions, and formats the date", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    const { container } = mount(calls);
    await walkToUpload(user, container);
    const paste = container.querySelector<HTMLTextAreaElement>("#reads-text");
    if (paste === null) throw new Error("stage 2 draws no paste field");
    await user.click(paste);
    await user.paste(CSV_TEXT);
    await user.click(screen.getByRole("button", { name: t("metering.upload.file.stage") }));
    await screen.findByText(t("metering.upload.file.inFile.caption"));
    await user.click(screen.getByRole("button", { name: t("workflow.advance.validate") }));
    await user.click(await screen.findByRole("button", { name: t("metering.upload.validate.run") }));

    // ── task 12 ──
    const table = await waitFor(() => {
      const found = container.querySelector('[data-reads="register-completeness"]');
      if (found === null) throw new Error("no completeness table");
      return found;
    });
    const group = table.querySelector('[data-reads-plan="time_of_use"]');
    expect(group).toBeInTheDocument();
    expect(group?.getAttribute("data-reads-short")).toBe("1");
    expect(group?.textContent).toContain(t("rating.model.time_of_use"));

    // ── task 13 — both actions, on the shortfall group ──
    const estimate = screen.getByRole("button", { name: t("metering.upload.registers.estimateAll") });
    await user.click(estimate);
    await waitFor(() =>
      expect(
        calls.some(
          (call) =>
            call.path === `/read-batches/${BATCH_ID}/rows/5` &&
            (call.body as { disposition?: string } | undefined)?.disposition === "estimate",
        ),
      ).toBe(true),
    );
    // BR-MET-015 — a bulk action records a reason on every row it touches.
    const written = calls.find((call) => call.path === `/read-batches/${BATCH_ID}/rows/5`);
    expect((written?.body as { reason?: string } | undefined)?.reason).toBe(
      t("metering.upload.registers.bulkReason"),
    );

    // ── task 21 / DEF-2443 — the flagged row's READ DATE ──
    const review = container.querySelector('[data-reads="review-rows"]');
    expect(review).toBeInTheDocument();
    expect(review?.textContent).not.toContain("2026-08-03T00:00:00");
    expect(review?.textContent).toContain("08/03/2026");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-054 tasks 6/11/12/13/18/19/20/21 (12-governance/11-change-requests.md, PO 2026-08-30) + BR-MET-013/015/032/049/059/091 + BR-SHL-025/034
// generated: 2026-08-30 by the CR-054 W5 frontend lane
// checklist: A✔ B=deferred(no-backend-half — screen tests) C✔ D=deferred(no-API-half) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report
// exceptions: E3 the LAYOUT half — that the reading-sheet button sits beside the template rather than under it, that the completeness table does not scroll the page sideways, that the mapping's five columns fit — is NOT assertable in jsdom, which does no layout and returns 0 for every measurement; it is `10-scripts/render-checks/cr054-reads-upload.mjs`, which opens the screen in Chromium (PO 2026-08-30) · E3 stage 4 and stage 5 are not driven here: posting is a real transaction against a real batch and a mocked commit would assert this file's own fixture
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
