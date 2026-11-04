// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    (none yet — hard-won law 8 is REPORTED in the trailer)
//           Change:  CR-047 tasks 14–17 — the RESULT stage of the import
//           runner: the rows that failed, the two CSV files, what the accounts
//           inherited from their units, and the door that releases the money
//           Screens: WFL-01.accounts.2 and WFL-01.accounts.5
// Rules:    PO ruling 2026-08-29 (*"if it is fail - you display on screen
//           shich record failed and why (dont write to dB) and continue to
//           uplaod next record; at the end we need 2 CsV file 1 for success
//           record and other for failed records"*) · PO ruling 2026-08-29
//           (*"if account is created then we need to inherit details form
//           units"*) · PO ruling 2026-08-27 (the accounts LOAD and only the
//           money waits — BR-CUS-049) · BR-TEN-043 (the caller names the
//           business event's date; no clock is read on their behalf) ·
//           BR-MET-096 (a kind is COPY AND A ROUTE, NEVER BEHAVIOUR) ·
//           B14 rule 11 (a consequence preview before a commit)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **THE RESULT STAGE WAS A DEAD END, AND THAT IS WHAT THIS FILE PINS.**
 *
 * Before CR-047 the receipt drew `opening_held` as a flagged figure — *"412
 * opening balances waiting for your changeover date"* — and offered **nothing
 * to do about it**. `POST /imports/{id}/confirm-changeover` had been complete
 * on the server since 2026-08-27 with **no client wrapper and no call site
 * anywhere in `07-frontend/src`**, and stage 2 still refused to advance
 * without a cutover date, so the hold the ruling created could not be entered
 * and could not be left.
 *
 * ⚠ **PROVED RED FIRST (hard-won law 7).** Every case below was run against
 * the tip before a line of the fix existed. The failures are quoted in the
 * lifecycle trailer at the bottom of this file, verbatim, one per case.
 *
 * ⚠ **THE STUB SERVES THE SERVER'S OWN SHAPES, KEY FOR KEY** — copied from
 * `import_runs.run_dict` / `rejects` / `receipt` / `confirm_changeover_date`,
 * never from the TypeScript interfaces. Six field names on this one boundary
 * have shipped wrong (`DEF-522`, `DEF-526`, `DEF-531`, `DEF-535`) and every
 * one was invisible to a suite that fed the client its own spelling.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { ImportWorkflowPage } from "./ImportWorkflowPage";

const TEST_TENANT = "silvercreek";
const RUN_ID = "5f2b7c1e-0000-4000-8000-000000000047";
const HASH = "9f2b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b81";

/** Six accounts, one opening-balance column. Headers are the customer's own. */
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
  return { status, data, etag: null, notModified: false };
}

function runDict(overrides: Record<string, unknown>): Record<string, unknown> {
  return {
    id: RUN_ID,
    run_no: "IMP-2026-000047",
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
    session_ref: "sess_9c31",
    ip: "71.42.108.14",
    started_at: "2026-08-29T09:00:00Z",
    finished_at: null,
    ...overrides,
  };
}

const EXTRACTED = runDict({
  headers: ["UNIT", "NAME", "TYPE", "CURRENT"],
  detected_mapping: {
    UNIT: "unit_ref",
    NAME: "customer_name",
    TYPE: "account_type",
    // ⚠ THE OPENING-BALANCE COLUMN IS MAPPED, which is exactly the state that
    // used to weld stage 2 shut when no cutover date was typed.
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
    clean: 4,
    errors: 1,
    warnings: 1,
  },
  rules: [
    {
      code: "ACC.UNIT_ON_FILE",
      tier: 1,
      sentence: "Every row names a unit already on file",
      severity: "error",
      action: "reject_row",
      action_value: null,
      hits: 1,
      available: true,
      unavailable_reason: null,
    },
  ],
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
  blocking_rules: { count: 1, platform: 0, structural: 1 },
});

const DRY_RUN = {
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

/**
 * `receipt(run)` after a load that ran WITHOUT a changeover date.
 *
 * ⚠ **THE FAILURES ARE ON THE SAME ROW RECORDS.** PO ruling 2026-08-29: a row
 * that fails at the WRITE is reported and skipped and the next row is read —
 * so `rejects` carries the stage-3 reject (row 3) AND the stage-4 failure
 * (row 5), each with `outcome`, `problem` and `fix_hint` populated, and
 * `created` counts only what actually landed.
 */
const LOADED = {
  ...VALIDATED,
  status: "loaded",
  write_mode: "insert",
  finished_at: "2026-08-29T09:04:30Z",
  counts: {
    ...(VALIDATED.counts as Record<string, number>),
    errors: 2,
    created: 4,
    updated: 0,
    opening_held: 4,
  },
  rejects: [
    ...(VALIDATED.rejects as Record<string, unknown>[]),
    {
      row_no: 5,
      source_key: "U-00108-B",
      problem: "The account number 4471-02 is already in use by another account.",
      fix_hint: "Give this row a different account number and upload it again.",
      outcome: "rejected",
    },
  ],
  rejects_window: { total: 2, offset: 0, limit: 50 },
  receipt: {
    run_id: RUN_ID,
    run_no: "IMP-2026-000047",
    loaded: 4,
    rejected: 2,
    flagged: 1,
    unplanned_units: 0,
    unplanned_plans: [],
    deactivated: 0,
    skipped_occupied: 0,
    numbers_issued_from_series: 0,
    // PO ruling 2026-08-29 — how many of the four took their services from the
    // unit they sit under. One did not, and that one is unbillable.
    with_services: 3,
    opening_held: 4,
    changeover_provisional: "2026-05-31",
    changeover_on: null,
    source_label: "accounts.csv",
    file_sha256: HASH,
    file_hash_verified: true,
    run_by: "alex@silvercreek.example",
    session_and_ip: "sess_9c31 · 71.42.108.14",
    mapping_used: null,
    write_mode: "insert",
    finished_at: "2026-08-29T09:04:30Z",
    rollback_point: { id: "RB-4471", status: "available", expires_at: "2026-09-28T09:04:30Z" },
  },
};

/** `confirm_changeover_date(...)`'s answer — the SAME receipt shape, on a run
 *  that is holding nothing any more. */
const CONFIRMED = {
  ...LOADED,
  counts: { ...(LOADED.counts as Record<string, number>), opening_held: 0 },
  receipt: {
    ...LOADED.receipt,
    opening_held: 0,
    changeover_provisional: null,
    changeover_on: "2026-07-31",
  },
};

interface StubOptions {
  /** What the `/load` call answers with. */
  loaded?: Record<string, unknown>;
  /** Thrown by `POST .../confirm-changeover` instead of answering. */
  changeoverRefusal?: unknown;
  /** The two CSV bodies, by `kind`. */
  csv?: Record<string, string>;
}

function stubClient(calls: RecordedCall[], options: StubOptions = {}): ApiClient {
  const loaded = options.loaded ?? LOADED;
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "GET", path });
      if (path === `/imports/${RUN_ID}/columns`) return ok(COLUMNS as T);
      if (path.startsWith(`/imports/${RUN_ID}/results.csv`)) {
        const kind = new URLSearchParams(path.split("?")[1] ?? "").get("kind") ?? "";
        return ok((options.csv?.[kind] ?? `${kind}\n`) as T);
      }
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string, body?: unknown): Promise<ApiResponse<T>> => {
      calls.push({ method: "POST", path, body });
      if (path === "/imports") return ok(EXTRACTED as T, 201);
      if (path === `/imports/${RUN_ID}/transform`) return ok(TRANSFORMED as T);
      if (path === `/imports/${RUN_ID}/validate`) return ok(VALIDATED as T);
      if (path === `/imports/${RUN_ID}/dry-run`) return ok(DRY_RUN as T);
      if (path === `/imports/${RUN_ID}/load`) return ok(loaded as T);
      if (path === `/imports/${RUN_ID}/confirm-changeover`) {
        if (options.changeoverRefusal !== undefined) throw options.changeoverRefusal;
        return ok(CONFIRMED as T);
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

function figure(container: HTMLElement, id: string): HTMLElement | null {
  return container.querySelector<HTMLElement>(`[data-workflow-figure="${id}"]`);
}

type User = ReturnType<typeof userEvent.setup>;

async function reachStageTwo(user: User, container: HTMLElement) {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  await user.upload(input, new File([CSV_TEXT], "accounts.csv", { type: "text/csv" }));
  const transform = await screen.findByRole("button", { name: "Transform →" });
  await waitFor(() => expect(transform).toBeEnabled());
  await user.click(transform);
  await waitFor(() => expect(stageOf(container)).toBe("2"));
}

/**
 * Stage 1 → 5, WITHOUT ever typing a changeover date.
 *
 * ⚠ That is deliberate and it is the whole point: the ruling says the accounts
 * load and only the money waits, so this is the ordinary path an operator who
 * does not yet know their cutover date must be able to walk.
 */
async function walkToResult(user: User, container: HTMLElement) {
  await reachStageTwo(user, container);
  const validate = await screen.findByRole("button", { name: "Validate →" });
  await waitFor(() => expect(validate).toBeEnabled());
  await user.click(validate);
  await waitFor(() => expect(stageOf(container)).toBe("3"));
  await user.click(await screen.findByRole("button", { name: "Load →" }));
  await waitFor(() => expect(stageOf(container)).toBe("4"));
  const commit = await screen.findByRole("button", { name: "Commit load ✓" });
  await waitFor(() => expect(commit).toBeEnabled());
  await user.click(commit);
  await waitFor(() => expect(stageOf(container)).toBe("5"));
}

afterEach(cleanup);

describe("CR-047 task 17 (b) — the changeover date is OPTIONAL at stage 2", () => {
  it("the stage advances with the date empty, and says what leaving it empty means", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);
    await reachStageTwo(user, container);

    const field = container.querySelector("#import-option-cutover_on") as HTMLInputElement;
    expect(field).not.toBeNull();
    expect(field.value).toBe("");
    // ⚠ NOT required any more: the PO ruled the accounts LOAD and only the
    // money waits, so a date nobody knows yet cannot be a wall in front of the
    // whole migration.
    expect(field.getAttribute("aria-required")).not.toBe("true");

    // BR-SHL-025's posture, inverted: a control that no longer blocks must say
    // what happens if you leave it alone.
    expect(container.textContent).toContain("Leave this empty if you do not know the date yet");
    expect(container.textContent).toContain("nothing is written to your books");

    const validate = await screen.findByRole("button", { name: "Validate →" });
    await waitFor(() => expect(validate).toBeEnabled());
    await user.click(validate);
    await waitFor(() => expect(stageOf(container)).toBe("3"));

    // ⚠ And an EMPTY option does not travel — `{cutover_on: ""}` would put an
    // empty string where the server expects a date, and its refusal would then
    // be about the FORMAT rather than the absence (DEF-626's own note).
    const transform = calls.find((call) => call.path.endsWith("/transform"));
    expect((transform?.body as { options?: unknown }).options).toBeUndefined();
  });

  it("a date that IS given still reaches the server under `options`", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);
    await reachStageTwo(user, container);

    const field = container.querySelector("#import-option-cutover_on") as HTMLInputElement;
    await user.type(field, "2026-07-31");
    await user.click(await screen.findByRole("button", { name: "Validate →" }));

    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/transform"))).toBe(true));
    const transform = calls.find((call) => call.path.endsWith("/transform"));
    expect((transform?.body as { options?: unknown }).options).toEqual({
      cutover_on: "2026-07-31",
    });
  });
});

describe("CR-047 task 14 — the rows that failed are ON THE RECEIPT", () => {
  it("lists every failed row with its number, its own key, the reason and the fix", async () => {
    const user = userEvent.setup();
    const { container } = mount([]);
    await walkToResult(user, container);

    // The stage-3 reject AND the stage-4 write failure — one list, because a
    // person reading a receipt is asking one question: what did not load?
    const list = container.querySelector('[data-workflow="rejects"]');
    expect(list).not.toBeNull();
    expect(list?.querySelector('[data-workflow-reject="3"]')).not.toBeNull();
    expect(list?.querySelector('[data-workflow-reject="5"]')).not.toBeNull();
    expect(list?.textContent).toContain("U-00404-C");
    expect(list?.textContent).toContain("U-00108-B");
    expect(list?.textContent).toContain(
      "The account number 4471-02 is already in use by another account.",
    );
    expect(list?.textContent).toContain(
      "Give this row a different account number and upload it again.",
    );

    // ⚠ **THE RECEIPT'S LIST IS READ-ONLY.** `Fix here…` re-runs stages 2–3
    // over a run that has ALREADY WRITTEN — it must not be offered after the
    // commit, and its absence is the assertion.
    expect(list?.querySelectorAll('button[aria-expanded]').length).toBe(0);

    // The sentence the ruling asks for: nothing was written for these rows and
    // the rest of the file loaded anyway.
    expect(container.textContent).toContain("Nothing was written for these rows");
  });
});

describe("CR-047 task 15 — the two CSV files", () => {
  it("offers both downloads, says how many failed, and asks for the right file", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const clicked: { name: string; body: string }[] = [];
    const createObjectURL = vi.fn(() => "blob:results");
    Object.defineProperty(URL, "createObjectURL", { value: createObjectURL, writable: true });
    Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), writable: true });
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        clicked.push({ name: this.download, body: "" });
      });

    const { container } = mount(calls, {
      csv: { successes: "account_no\n4471-01\n", failures: "row_no,problem\n3,no unit\n" },
    });
    await walkToResult(user, container);

    const successes = await screen.findByRole("button", {
      name: "Download the accounts that loaded",
    });
    const failures = await screen.findByRole("button", {
      name: "Download the 2 rows that failed",
    });

    await user.click(successes);
    await waitFor(() =>
      expect(
        calls.some((c) => c.path === `/imports/${RUN_ID}/results.csv?kind=successes`),
      ).toBe(true),
    );
    await user.click(failures);
    await waitFor(() =>
      expect(
        calls.some((c) => c.path === `/imports/${RUN_ID}/results.csv?kind=failures`),
      ).toBe(true),
    );
    await waitFor(() => expect(clicked.length).toBe(2));
    click.mockRestore();
  });

  it("a run with nothing to fix offers the successes file and NOT the failures one", async () => {
    const user = userEvent.setup();
    const clean = {
      ...LOADED,
      counts: { ...(LOADED.counts as Record<string, number>), errors: 0, created: 6 },
      rejects: [],
      rejects_window: { total: 0, offset: 0, limit: 50 },
      receipt: { ...LOADED.receipt, loaded: 6, rejected: 0, with_services: 6 },
    };
    const { container } = mount([], { loaded: clean });
    await walkToResult(user, container);

    expect(
      screen.queryByRole("button", { name: /Download the .* rows that failed/ }),
    ).toBeNull();
    expect(
      await screen.findByRole("button", { name: "Download the accounts that loaded" }),
    ).toBeInTheDocument();
  });
});

describe("CR-047 task 16 — what the accounts inherited from their units", () => {
  it("draws `with_services` as its own figure and FLAGS the difference", async () => {
    const user = userEvent.setup();
    const { container } = mount([]);
    await walkToResult(user, container);

    expect(figure(container, "loaded")?.textContent).toContain("4");
    expect(figure(container, "with-services")?.textContent).toContain("3");

    // ⚠ **THE DIFFERENCE IS ITS OWN FIGURE AND IT IS FLAGGED.** A count that
    // adds a wired account to an unwired one is exactly what made this
    // invisible: "4 loaded" reads as four billable accounts and one of them
    // has nothing to bill.
    const gap = figure(container, "without-services");
    expect(gap).not.toBeNull();
    expect(gap?.textContent).toContain("1");
    expect(gap?.getAttribute("data-flagged")).toBe("true");
    expect(container.textContent).toContain("nothing to bill them for yet");
  });

  it("a receipt that never counted it prints NO figure — absent is not zero", async () => {
    const user = userEvent.setup();
    const older = {
      ...LOADED,
      receipt: { ...LOADED.receipt },
    };
    delete (older.receipt as Record<string, unknown>).with_services;
    const { container } = mount([], { loaded: older });
    await walkToResult(user, container);

    // DEF-127 / the AbsentFigure discipline: a `0` is a measurement and this
    // is the absence of one. Neither tile is drawn.
    expect(figure(container, "with-services")).toBeNull();
    expect(figure(container, "without-services")).toBeNull();
  });
});

describe("CR-047 task 17 (a) — the door that releases the money", () => {
  it("is offered while balances are held, asks for the date in the RULE's own words, and posts it", async () => {
    const user = userEvent.setup();
    const calls: RecordedCall[] = [];
    const { container } = mount(calls);
    await walkToResult(user, container);

    expect(figure(container, "opening-held")?.textContent).toContain("4");
    // The label is the sentence the rule itself uses. The PO met the word
    // *cutover* on a screen that blocks people and could not tell what it was
    // for; nobody at a two-person utility will do better.
    expect(container.textContent).toContain(
      "The last day your old system was in charge of the money",
    );
    // B14 rule 11 — the consequence BEFORE the commit, with the provisional
    // date the balances are sitting under right now.
    expect(container.textContent).toContain("2026-05-31");

    const field = container.querySelector("#import-changeover-on") as HTMLInputElement;
    expect(field).not.toBeNull();
    await user.type(field, "2026-07-31");
    await user.click(await screen.findByRole("button", { name: "Post the opening balances" }));

    await waitFor(() =>
      expect(
        calls.some((c) => c.path === `/imports/${RUN_ID}/confirm-changeover`),
      ).toBe(true),
    );
    const posted = calls.find((c) => c.path.endsWith("/confirm-changeover"));
    // ⚠ `changeover_on` — `api.import_confirm_changeover` reads this name and
    // no other (DEF-531's lesson, on a fourth field).
    expect(posted?.body).toEqual({ changeover_on: "2026-07-31" });

    // The receipt redraws from the confirmation's OWN answer, exactly as the
    // rollback does — nothing is held any more and the control is gone.
    await waitFor(() => expect(figure(container, "opening-held")).toBeNull());
    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: "Post the opening balances" }),
      ).toBeNull(),
    );
  });

  it("surfaces the SERVER's refusal of a future date rather than pre-empting it", async () => {
    const user = userEvent.setup();
    const refusal = new ApiError(422, {
      code: "BIZ-STATE",
      message_key: "metering.import.changeover_in_future",
      params: { given: "2027-01-31", today: "2026-08-29" },
      br_ref: "BR-CUS-049",
    } as never);
    const { container } = mount([], { changeoverRefusal: refusal });
    await walkToResult(user, container);

    const field = container.querySelector("#import-changeover-on") as HTMLInputElement;
    await user.type(field, "2027-01-31");
    await user.click(await screen.findByRole("button", { name: "Post the opening balances" }));

    // The server refuses a future date BY NAME. The screen must not have its
    // own opinion about it: a second validator drifts from the first, and the
    // one that matters is the one that guards the write.
    await waitFor(() =>
      expect(container.querySelector('[role="alert"]')?.textContent ?? "").toContain(
        "is in the future",
      ),
    );
    // ⛔ **AND THE SERVER'S OWN PARAMETERS REACH THE SENTENCE.** This catalogue
    // entry was written with SINGLE braces — `({given})`, `({today})` — and
    // i18next interpolates `{{…}}`, so until CR-047 it printed the placeholder
    // NAMES to a clerk: *"Your changeover date ({given}) is in the future …
    // later than today ({today})"*. Nothing could see it: G18 asks whether a
    // key RESOLVES, never whether its parameters do, and no test had ever
    // rendered this refusal because nothing in the product could reach it.
    // Measured, before the fix, by prefixing the value with `PROBE:{given}`:
    // the alert read `PROBE:{given} Your changeover date ({given}) …`.
    // Asserted on the two DATES rather than on the brace style, because the
    // dates are what the operator has to read.
    const alert = container.querySelector('[role="alert"]')?.textContent ?? "";
    expect(alert).toContain("2027-01-31");
    expect(alert).toContain("2026-08-29");
    expect(alert).not.toContain("{given}");
    expect(alert).not.toContain("{today}");
    expect(container.querySelector('[role="alert"]')?.getAttribute("data-br-ref")).toBe(
      "BR-CUS-049",
    );
    // Still on offer — a refusal is not a dead end.
    expect(
      await screen.findByRole("button", { name: "Post the opening balances" }),
    ).toBeInTheDocument();
  });

  it("is NOT offered on a run that is holding nothing", async () => {
    const user = userEvent.setup();
    const dated = {
      ...LOADED,
      counts: { ...(LOADED.counts as Record<string, number>), opening_held: 0 },
      receipt: {
        ...LOADED.receipt,
        opening_held: 0,
        changeover_provisional: null,
        changeover_on: "2026-07-31",
      },
    };
    const { container } = mount([], { loaded: dated });
    await walkToResult(user, container);

    expect(container.querySelector("#import-changeover-on")).toBeNull();
    expect(
      screen.queryByRole("button", { name: "Post the opening balances" }),
    ).toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-047 tasks 14–17 (PO rulings 2026-08-29 + the 2026-08-27 hold)
// generated: 2026-08-29 by the CR-047 frontend lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
