// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  DEF-523 — the frontend learns to CLICK. First interactive suite.
// Screens: WFL-01
// Rules:   BR-MET-096 (ONE workflow, premises and units) · BR-MET-085 (stage 1
//          stages rows, writes nothing) · BR-MET-088 (the MAPS TO list is the
//          server's) · BR-TEN-003 (the tenant is the first URL path segment —
//          every internal link must keep it)
// ───────────────────────────────────────────────────────
// ⚠ **THIS FILE IS THE REPO'S FIRST TEST THAT CLICKS ANYTHING (`DEF-523`).**
// Every other frontend test is `renderToStaticMarkup` — the first paint, no
// DOM, no events. Five defects in one day escaped through that gap: DEF-526
// and DEF-531 (wrong payload keys — only a real POST shows what leaves the
// client), DEF-529 (a 500 only a real request path could produce), DEF-530
// (validate's results unseeable — only ARRIVING at stage 3 shows what it
// renders), DEF-532 (a back link that broke the whole app — a link must be
// FOLLOWED to see where it goes). Each of the four regression cases below is
// one of those, pinned.
//
// ⚠ **PROVED RED FIRST (law 7).** Before jsdom/@testing-library landed in
// package.json, running exactly this file produced (2026-08-22):
//   `Error: Cannot find package 'jsdom' imported from
//    node_modules/vitest/dist/chunks/index.K90BXFOx.js` · `Test Files  no tests`
// — the suite could not even START, which is DEF-523's whole finding: a test
// that clicks a button was IMPOSSIBLE in this repo, not merely missing.
//
// ⚠ **THE STUB SERVES THE SERVER'S REAL SHAPES, KEY FOR KEY.** Every response
// below is copied from `06-backend/apps/metering/import_runs.py` (`run_dict`,
// `extract`, `_validate_locked`, `rule_results`, `rejects`) and
// `apps/metering/api.import_columns` — NOT from the TypeScript interfaces,
// because hand-copied interfaces are exactly what DEF-526/531/522 proved
// unreliable (three of four field names wrong in one file, one day). A field
// the server does not send is not stubbed.
//
// ⚠ **KNOWN DRIFT, FILED NOT FIXED (DEF-535):** the server's `rules` rows
// carry `action`/`action_value` and its `rejects` rows carry
// `row_no`/`source_key`/`fix_hint` — the kit reads `action_label`,
// `row_number`/`key`/`suggested_fix`. So stage 3's ACTION column and the
// reject list's ROW/KEY/FIX cells render EMPTY on a real run. This suite
// asserts only the fields both sides agree on (`sentence`, `problem`, the
// counts); the drift belongs to the page/kit lane and is in the register.
import "@/i18n";
// Registers `toBeInTheDocument` / `toBeEnabled` on vitest's `expect` — scoped
// to this file rather than a global setup so the 200+ static-markup suites run
// exactly as before.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { ImportWorkflowPage } from "./ImportWorkflowPage";

const TEST_TENANT = "silvercreek";
const RUN_ID = "5f2b7c1e-0000-4000-8000-000000000001";

/** The 3-row file the operator uploads — small on purpose (BR-MET-098's
 *  second bar exists because small corrective files are the common case). */
const CSV_TEXT =
  "Address,City,Premise Type\n" +
  "12 Main St,Katy,Residential\n" +
  "12 Main St,Katy,Residential\n" +
  "88 Oak Ave,Katy,Commercial\n";

/* ── The server's answers, shaped by `run_dict` and friends ─────────────── */

/** `run_dict(run)` — every stage answers with this envelope. */
function runDict(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    id: RUN_ID,
    run_no: "IMP-2026-000041",
    target: "premises",
    source_kind: "file",
    file_name: "premises.csv",
    file_hash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    file_bytes: CSV_TEXT.length,
    encoding_delimiter: "UTF-8 · comma (detected)",
    mapping_id: null,
    mapping_spec: null,
    batch_label: null,
    write_mode: null,
    counts: { in: 3, duplicates_dropped: 0, skipped: 0, forward: 0 },
    status: "extracted",
    session_ref: null,
    ip: null,
    started_at: "2026-08-22T09:00:00Z",
    finished_at: null,
    ...overrides,
  };
}

/** Stage 1's answer — `extract()`: run + headers + detected_mapping + warnings. */
const EXTRACTED = runDict({
  headers: ["Address", "City", "Premise Type"],
  detected_mapping: { Address: "address_line", City: "city" },
  warnings: [],
});

/** `GET /imports/:id/columns` — `api.import_columns`, verbatim keys. */
const COLUMNS = {
  target: "premises",
  columns: [
    {
      target: "address_line",
      label: "Address line",
      kind: "text",
      required: true,
      transforms: ["trim_whitespace", "title_case", "uppercase"],
    },
    {
      target: "city",
      label: "City",
      kind: "text",
      required: false,
      transforms: ["trim_whitespace", "title_case", "uppercase"],
    },
    {
      target: "premises_type",
      label: "Premises type",
      kind: "lookup",
      required: false,
      transforms: ["trim_whitespace"],
    },
    { target: "__ignore__", label: "— ignore —", kind: "text", required: false, transforms: [] },
  ],
  unavailable_transforms: [],
  // ⚠ The SERVER's spelling — `keep_latest_on_key`, not the kit's
  // `keep_latest_on_duplicate_key` (DEF-522).
  row_handling: ["drop_exact_duplicates", "keep_latest_on_key", "skip_rows_missing_required"],
};

/** Stage 2's answer — `transform()` returns a bare `run_dict`. */
const TRANSFORMED = runDict({
  counts: { in: 3, duplicates_dropped: 1, skipped: 0, forward: 2 },
  status: "transformed",
});

/** Stage 3's answer — `run_dict(run, with_rules=True)`. Rule rows are the
 *  server's `rule_results()` shape; reject rows are its `rejects()` shape. */
const VALIDATED = runDict({
  counts: {
    in: 3,
    duplicates_dropped: 1,
    skipped: 0,
    forward: 2,
    checked: 2,
    clean: 1,
    errors: 0,
    warnings: 1,
  },
  status: "validated",
  rules: [
    {
      code: "structural.address_required",
      tier: "structural",
      sentence: "Every row has an address",
      severity: "error",
      action: "reject_row",
      action_value: null,
      hits: 0,
      available: true,
      unavailable_reason: null,
    },
    {
      code: "platform.premise_type_lookup",
      tier: "platform",
      sentence: "Premise type exists in the lookup table",
      severity: "warning",
      action: "default_to",
      action_value: "Residential",
      hits: 1,
      available: true,
      unavailable_reason: null,
    },
  ],
  rejects: [],
  blocking_rules: { count: 1, platform: 0, structural: 1 },
});

/* ── The stub client — records every call so the tests can read the wire ── */

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
      throw new Error(`unstubbed POST ${path}`);
    },
  } as unknown as ApiClient;
}

/** Where did the router end up? Rendered OUTSIDE `<Routes>` so it reports the
 *  location even when no route matches it — which is DEF-532's failure mode. */
function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location-pathname">{location.pathname}</div>;
}

function mount(calls: RecordedCall[]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/import`]}>
          <LocationProbe />
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

function tile(container: HTMLElement, id: string): string {
  return (
    container.querySelector(`[data-workflow-figure="${id}"]`)?.textContent ?? `<no tile ${id}>`
  );
}

/** Drives stage 1: pick the CSV, click `Transform →`, land on stage 2. */
async function uploadAndTransform(user: ReturnType<typeof userEvent.setup>, container: HTMLElement) {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  if (input === null) throw new Error("stage 1 renders no file input");
  await user.upload(input, new File([CSV_TEXT], "premises.csv", { type: "text/csv" }));
  const transform = await screen.findByRole("button", { name: "Transform →" });
  await waitFor(() => expect(transform).toBeEnabled());
  await user.click(transform);
  await waitFor(() => expect(stageOf(container)).toBe("2"));
}

/** Drives stage 2: click `Validate →` (which POSTs transform, then the page
 *  runs validate ON ARRIVAL at stage 3 — DEF-530's fixed order). */
async function advanceToValidate(
  user: ReturnType<typeof userEvent.setup>,
  container: HTMLElement,
) {
  const validate = await screen.findByRole("button", { name: "Validate →" });
  await waitFor(() => expect(validate).toBeEnabled());
  await user.click(validate);
  await waitFor(() => expect(stageOf(container)).toBe("3"));
}

afterEach(cleanup);

describe("WFL-01 — the five-stage import, CLICKED THROUGH (DEF-523)", () => {
  it("⛔ CR-042 — STEP 1 OFFERS TWO WRITE MODES AND THE CLERK CAN PICK EITHER", async () => {
    // **THE PO's ASK, CLICKED.** Verbatim: *"in all imports - we need 2 option
    // on step 1 insert, insert & update; replace option is not required;
    // currently many places this option is at step 4 of import"*.
    //
    // ⚠ **THIS IS THE ONLY KIND OF CHECK THAT CAN ANSWER IT.** Hard-won law 6:
    // no gate in this repo reads rendered output, so nothing else in the build
    // can say WHICH STEP a control is on or HOW MANY choices it offers. A unit
    // test on `writeModeOptions` proves the list; only arriving on step 1 in a
    // browser-shaped DOM proves the list is THERE, on THAT step, and pressable.
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);

    // Step 1, before anything is uploaded — the mode is a PREMISE, so it is
    // asked before the file is read (CR-036 (g)), not after.
    expect(stageOf(container)).toBe("1");
    const group = container.querySelector('[data-workflow="write-mode"]');
    expect(group).not.toBeNull();
    const radios = group?.querySelectorAll('input[type="radio"]') ?? [];
    expect(radios).toHaveLength(2);
    expect(Array.from(radios).map((radio) => (radio as HTMLInputElement).value)).toEqual([
      "insert",
      "upsert",
    ]);
    // hard-won law 3 — the safe mode is the one you get without typing.
    expect((radios[0] as HTMLInputElement).checked).toBe(true);
    expect(container.textContent).not.toContain("Replace");

    // …and the second one is genuinely selectable, with its consequence
    // sentence following the choice rather than sitting beside both.
    await user.click(radios[1] as HTMLInputElement);
    expect((radios[1] as HTMLInputElement).checked).toBe(true);
    const consequence = container.querySelector('[data-workflow="write-mode-consequence"]');
    // ⛔ **CR-046 E1 — THE SENTENCE CHANGED WITH THE BEHAVIOUR IT DESCRIBES.**
    // It used to read *"…is updated from your file"* and its sibling said a
    // known row is *counted and shown to you*, which is REPORTING. Under
    // CR-046 clause (iii) `insert` REJECTS such a row and `upsert` UPDATES it,
    // so this asserts the verb rather than the old phrasing.
    expect(consequence?.textContent ?? "").toContain("UPDATES that record's details");
  });

  it("upload → Transform → stage 2 shows the mapping rows the server extracted", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);

    await uploadAndTransform(user, container);

    // One row per header the FILE had (BR-MET-088), with the server's own
    // guess pre-selected: Address and City matched, Premise Type unmapped.
    const rows = container.querySelectorAll("[data-workflow-map-status]");
    expect(rows).toHaveLength(3);
    const statuses = Array.from(rows).map((row) => row.getAttribute("data-workflow-map-status"));
    expect(statuses).toEqual(["matched", "matched", "unmapped"]);
    expect(screen.getByText("Premise Type")).toBeInTheDocument();
  });

  it("Validate → stage 3 SHOWS the tiles with the stub's numbers (DEF-530)", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);

    await uploadAndTransform(user, container);
    await advanceToValidate(user, container);

    // ⚠ THE DEF-530 CASE. The broken build jumped to stage 4 in
    // validate.onSuccess, so these four tiles rendered 0/0/0/0 and "No rules
    // ran on this file" over a run the database had already checked. Here the
    // operator ARRIVES at stage 3 and the server's numbers are ON the screen.
    await waitFor(() => expect(tile(container, "checked")).toContain("2"));
    expect(tile(container, "clean")).toContain("1");
    expect(tile(container, "errors")).toContain("0");
    expect(tile(container, "warnings")).toContain("1");

    // The rules AS THEY RAN (BR-MET-090) — the server's sentences, visible.
    expect(screen.getByText("Every row has an address")).toBeInTheDocument();
    expect(screen.getByText("Premise type exists in the lookup table")).toBeInTheDocument();
    expect(screen.queryByText("No rules ran on this file.")).not.toBeInTheDocument();

    // And the page did NOT jump on: the operator is still reading stage 3.
    expect(stageOf(container)).toBe("3");
  });

  it("the wire carries the SERVER's keys: content_b64 · mapping · keep_latest_on_key (DEF-526/531/522)", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);

    await uploadAndTransform(user, container);
    await advanceToValidate(user, container);

    // ⚠ THE DEF-526 CASE — stage 1's body. `_file_bytes` reads `content_b64`
    // then `content`; the broken build sent `file_base64` and every upload was
    // refused with "a file is required".
    const extract = calls.find((call) => call.method === "POST" && call.path === "/imports");
    expect(extract).toBeDefined();
    const extractBody = extract?.body as Record<string, unknown>;
    expect(Object.keys(extractBody)).toContain("content_b64");
    expect(Object.keys(extractBody)).not.toContain("file_base64");
    expect(extractBody.target).toBe("premises");
    expect(extractBody.file_name).toBe("premises.csv");
    // The payload is the FILE, base64 — decode it and get the CSV back.
    expect(atob(String(extractBody.content_b64))).toBe(CSV_TEXT);

    // ⚠ THE DEF-531 CASE — stage 2's body. `transform` reads `mapping`; the
    // broken build sent `columns`, and the server blamed the OPERATOR for an
    // unmapped address column whose mapping it had silently discarded.
    const transform = calls.find(
      (call) => call.method === "POST" && call.path === `/imports/${RUN_ID}/transform`,
    );
    expect(transform).toBeDefined();
    const transformBody = transform?.body as Record<string, unknown>;
    expect(Object.keys(transformBody)).toContain("mapping");
    expect(Object.keys(transformBody)).not.toContain("columns");
    const mapping = transformBody.mapping as Record<string, { target: string }>;
    expect(mapping.Address).toEqual({ target: "address_line" });
    expect(mapping.City).toEqual({ target: "city" });

    // ⚠ THE DEF-522 CASE — the row-handling spelling. The server USED to read
    // its three keys with `bool(payload.get(key))`, so the kit's spelling
    // (`keep_latest_on_duplicate_key`) was not refused — it was read as FALSE
    // and the operator's tick silently kept the FIRST row. Both halves are
    // closed now: `contract.ts` spells all three the way the wire does (so
    // there is no boundary mapping left to get wrong), and `_transform_locked`
    // REFUSES an unrecognised key by name instead of coercing it. This
    // assertion is what keeps the client half honest — the exact keys leaving
    // the client are the SERVER's three, and only those.
    const rowHandling = transformBody.row_handling as Record<string, boolean>;
    expect(Object.keys(rowHandling).sort()).toEqual([
      "drop_exact_duplicates",
      "keep_latest_on_key",
      "skip_rows_missing_required",
    ]);
    expect(Object.keys(rowHandling)).not.toContain("keep_latest_on_duplicate_key");
  });

  it("the header back link keeps the TENANT in the path (DEF-532)", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    mount(calls);

    // ⚠ THE DEF-532 CASE. The broken build linked to bare `/premises`; the
    // shell read "premises" AS the tenant slug and every screen in the product
    // failed from then on. A static render shows the link's markup; only
    // FOLLOWING it shows where the router actually lands.
    await user.click(screen.getByRole("link", { name: "← Premises" }));

    const landed = screen.getByTestId("location-pathname").textContent;
    expect(landed).toBe(`/${TEST_TENANT}/premises`);
    // The first URL segment is still the tenant (BR-TEN-003, path tenancy).
    expect(landed?.split("/")[1]).toBe(TEST_TENANT);
    expect(screen.getByText("premises list")).toBeInTheDocument();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-523 (W5b — jsdom + testing-library; regression pins for
//         DEF-526 · DEF-529-class · DEF-530 · DEF-531 · DEF-532 · DEF-522)
// generated: 2026-08-22 by the W5b lane
// checklist: A✔ B✔ C✔ D✔(proved RED first: without jsdom in package.json this
//         file cannot start — "Cannot find dependency 'jsdom'") E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// gates: vitest✔ (default environment stays `node`; this file opts in via the
//         `@vitest-environment jsdom` pragma) · tsc✔
// exceptions: E3 the stub serves the server's REAL response shapes; the kit
//         reads `action_label`/`row_number`/`key`/`suggested_fix` which the
//         server does not send — filed as DEF-535, owned by the page/kit lane,
//         deliberately NOT asserted here so this suite is green on truth
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
