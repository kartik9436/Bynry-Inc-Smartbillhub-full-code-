// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-021/022 (EP-CUS-07) · Screens: S68
// Change:   CR-030 W1 — DEF-626, the stage-2 option the runner could not send
// Rules:    BR-CUS-049 (opening entries are dated at CUTOVER) · BR-TEN-043
//           (never read a clock for the caller) · BR-MET-096 (one runner, and
//           a kind is COPY AND A ROUTE, NEVER BEHAVIOUR)
// ───────────────────────────────────────────────────────
/**
 * ⛔ **DEF-626 — THE ACCOUNT IMPORT COULD NOT BE COMPLETED AT ALL, AND EVERY
 * AUTOMATED CHECK IN THIS REPO PASSED OVER IT.**
 *
 * `import_runs.transform` has always stored `mapping_spec["options"]` from
 * `data.get("options")`, and `_accounts_cutover` reads `options.cutover_on`.
 * The client's `ImportTransformRequest` declared `mapping` and `row_handling`
 * and nothing else, so the wizard built exactly those two keys. An accounts
 * file carrying any `ob_*` column therefore reached stage 4 — the ONE stage
 * that writes — and was refused there, correctly, by BR-CUS-049:
 *
 *     code=BIZ-COMPLETENESS  key=customers.import.cutover_required
 *     br_ref=BR-CUS-049      POST /api/{tenant}/imports/{id}/load  → 422
 *
 * There was no control anywhere in the five stages that could satisfy it. A
 * full-page DOM scan of stage 2 found exactly four inputs — the header search
 * box and three checkboxes — and the string `cutover` appeared nowhere on the
 * page. The feature W1 exists to deliver was unreachable.
 *
 * ⚠ **WHAT FOUND IT, AND WHAT DID NOT.** tsc, eslint, 2217 unit tests and
 * every gate were green. It was found by a browser walking the screen
 * (`10-scripts/12-smoke-walkthrough.mjs`), which is hard-won law 6 word for
 * word: *"Diff the running app against 05-prototype/ — no gate looks at
 * rendered output."* This file is the cheap regression pin that law 6's
 * finding earns; it is not a substitute for the walkthrough.
 *
 * ⚠ **WHY THE FIX IS DATA AND NOT AN `if`.** The obvious repair —
 * `if (target === "accounts") renderCutover()` — is precisely what BR-MET-096
 * forbids and what `kinds.ts` means by *"a kind is COPY AND A ROUTE, NEVER
 * BEHAVIOUR"*. So the accounts kind DECLARES an option field, and the runner
 * renders, validates and sends it without ever learning what a cutover date
 * is. The premises kind declares none and its stage 2 is unchanged — which is
 * the assertion at the bottom of this file.
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
const RUN_ID = "5f2b7c1e-0000-4000-8000-000000000042";

/** Three of the thirty accounts columns, and the one bucket that makes a
 *  cutover date mandatory. Headers are the customer's own, because the point
 *  of stage 2 is that they need not be ours. */
const CSV_TEXT =
  "UNIT,NAME,TYPE,CURRENT\n" +
  "U-00101-A,Harmon Luis,residential,84.20\n" +
  "U-00101-B,Alvarez Rosa,residential,0.00\n";

interface RecordedCall {
  method: string;
  path: string;
  body?: unknown;
}

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { ok: true, status, data } as unknown as ApiResponse<T>;
}

function runDict(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    id: RUN_ID,
    run_no: "IMP-2026-000042",
    target: "accounts",
    source_kind: "file",
    file_name: "accounts.csv",
    file_hash: "9f2b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b81",
    file_bytes: CSV_TEXT.length,
    encoding_delimiter: "UTF-8 · comma (detected)",
    mapping_id: null,
    mapping_spec: null,
    batch_label: null,
    write_mode: null,
    counts: { in: 2, duplicates_dropped: 0, skipped: 0, forward: 0 },
    status: "extracted",
    session_ref: null,
    ip: null,
    started_at: "2026-08-24T09:00:00Z",
    finished_at: null,
    ...overrides,
  };
}

/** ⚠ `ob_current` IS in the detected mapping. That is what arms the option —
 *  and the last test in this file removes it to prove the arming is real. */
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
};

const TRANSFORMED = runDict({
  status: "transformed",
  counts: { in: 2, duplicates_dropped: 0, skipped: 0, forward: 2 },
});

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
      throw new Error(`unstubbed POST ${path}`);
    },
  } as unknown as ApiClient;
}

function mount(calls: RecordedCall[], target: "accounts" | "premises" = "accounts") {
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
              element={<ImportWorkflowPage target={target} client={stubClient(calls)} />}
            />
            <Route path="/:tenant/accounts" element={<div>accounts list</div>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Upload the file and land on stage 2, the way an operator does. */
async function reachStageTwo(user: ReturnType<typeof userEvent.setup>, container: HTMLElement) {
  const file = new File([CSV_TEXT], "accounts.csv", { type: "text/csv" });
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  await user.upload(input, file);
  const transform = await screen.findByRole("button", { name: "Transform →" });
  await waitFor(() => expect(transform).toBeEnabled());
  await user.click(transform);
  await waitFor(() => expect(stageOf(container)).toBe("2"));
}

function stageOf(container: HTMLElement): string | null {
  return container.querySelector('[data-workflow="runner"]')?.getAttribute("data-stage") ?? null;
}

afterEach(cleanup);

describe("DEF-626 — the accounts import can be given its cutover date", () => {
  it("stage 2 draws the control once an opening-balance column is mapped", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);
    await reachStageTwo(user, container);

    const field = container.querySelector("#import-option-cutover_on") as HTMLInputElement;
    // Before DEF-626 this query returned null: stage 2 held exactly four
    // inputs and none of them was a date.
    expect(field).not.toBeNull();
    // BR-SHL-033 — the native picker, which is also typeable.
    expect(field.getAttribute("type")).toBe("date");
    // ⛔ **AMENDED BY CR-047 (b), 2026-08-29 — THIS LINE ASSERTED
    // `aria-required === "true"` AND THE ASSERTION IS NOW THE OPPOSITE.**
    // The reasoning did not become wrong, it MOVED: the PO ruled on
    // 2026-08-27 that the accounts LOAD and only the money waits, so a date
    // the operator does not yet know is a thing to be asked for LATER — on the
    // receipt, through `confirm-changeover` — and not a wall in front of the
    // whole migration. The server had already stopped refusing
    // (`opening_held = cutover is None`); only this screen still did.
    expect(field.getAttribute("aria-required")).not.toBe("true");
    // ⚠ EMPTY, never prefilled. BR-TEN-043 forbids reading a clock for the
    // caller, and a silently-defaulted cutover dates a utility's migrated
    // books on whatever day somebody ran the import — every ageing band wrong
    // by the gap, and uncorrectable once the entries post (hard rule 4).
    // **Unchanged by CR-047, and more important now than before**: the field
    // being optional is not permission to fill it in for somebody.
    expect(field.value).toBe("");
  });

  it("CR-047 (b) — the stage ADVANCES while it is empty, and says what that means", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);
    await reachStageTwo(user, container);

    // ⛔ **THIS CASE WAS `..._cannot_be_advanced_while_it_is_empty` AND IT IS
    // INVERTED, NOT DELETED.** Its old body asserted a DISABLED `Validate →`
    // and the server's refusal sentence *"Choose the cutover date"* on screen,
    // and both were right for the rule as it stood: BR-CUS-049 dated every
    // opening entry at cutover and stage 4 refused a file without one, so
    // refusing HERE said the same sentence at the step that could act on it.
    //
    // The PO ruled otherwise on 2026-08-27 — the accounts LOAD and only the
    // money waits — and the old shape then cost exactly the operator the hold
    // was built for: the one who has the file and does not know the date.
    // What replaces the refusal is a STATEMENT, because a choice with no
    // stated consequence is a coin toss.
    expect(await screen.findByRole("button", { name: "Validate →" })).toBeEnabled();
    expect(container.textContent).toContain("Leave this empty if you do not know the date yet");
    expect(container.textContent).not.toContain("Choose the cutover date");
  });

  it("filling it releases the stage and the date reaches the server under `options`", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);
    await reachStageTwo(user, container);

    const field = container.querySelector("#import-option-cutover_on") as HTMLInputElement;
    await user.type(field, "2026-08-31");

    const advance = await screen.findByRole("button", { name: "Validate →" });
    await waitFor(() => expect(advance).toBeEnabled());
    await user.click(advance);

    await waitFor(() =>
      expect(calls.some((call) => call.path.endsWith("/transform"))).toBe(true),
    );
    const transform = calls.find((call) => call.path.endsWith("/transform"));
    const body = transform?.body as { options?: Record<string, string> };
    // ⚠ `options.cutover_on` — the key `_accounts_cutover` reads, and the one
    // this request type did not declare. DEF-531's lesson: the server reads
    // this name and no other.
    expect(body.options).toEqual({ cutover_on: "2026-08-31" });
  });

  it("BR-MET-096 — a kind that declares no option gets no control, and its stage 2 is untouched", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    // Same runner, same file, same stubs — only the kind differs. If this
    // renders a cutover field, the fix leaked behaviour into the runner and
    // the whole point of declaring it as data is lost.
    const { container } = mount(calls, "premises");
    await reachStageTwo(user, container);

    expect(container.querySelector("#import-option-cutover_on")).toBeNull();
    expect(container.textContent).not.toContain("Cutover date");
    expect(await screen.findByRole("button", { name: "Validate →" })).toBeEnabled();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-626 (CR-030 W1 — found by the browser walkthrough, task 1.25)
// generated: 2026-08-24 by the CR-030 W1 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
//         D, measured rather than asserted: this file was copied into a
//         DETACHED WORKTREE at 627b83a6 (the commit before the fix, with
//         node_modules symlinked) and run there. Result: 3 FAILED, 1 passed.
//           · "stage 2 draws the control"    — the querySelector returns null
//           · "cannot be advanced"           — findByRole finds no disabled
//                                              Validate button, because
//                                              nothing was blocking it
//           · "the date reaches the server"  — TypeError: Cannot read
//                                              properties of null (reading
//                                              'disabled') — there is no
//                                              field to type into
//         ⚠ THE FOURTH PASSED, AND IT IS SUPPOSED TO. It is the BR-MET-096
//         control: the premises kind declares no option, so it must render no
//         control BEFORE the fix and AFTER it. A control case that changes
//         with the fix is not a control.
// gates: vitest✔ · tsc✔ · G31 n/a (no markup of its own)
// exceptions: E3 the stub serves the server's real response shapes for the
//         accounts target; it does NOT stub `/validate`, `/dry-run` or
//         `/load`, because every case here ends at the transform call — the
//         later stages are the walkthrough's job, against a real server
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
