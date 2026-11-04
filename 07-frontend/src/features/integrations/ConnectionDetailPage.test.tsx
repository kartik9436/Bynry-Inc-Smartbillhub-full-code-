// @vitest-environment jsdom
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-INT-020 (EP-INT-06) — S142, the run record. US-INT-021 — the
//           unconfirmed outcome. Frames 25.2 · 44.1 · 51.1 · 51.2 · 52.2.
// Rules:    BR-INT-018 (never green when the counts cannot be reconciled) ·
//           BR-INT-040 (the items are NAMED) · B14 rule 15 (an icon with an
//           accessible name) · rule 31 (the trace id is the only identifier;
//           no database id is a visible value) · rule 32 (one sentence per
//           section)
// Cases:    US-INT-020 TC-1 (the rows and the 1 Aug line; opening it names the
//           seven) · TC-2 (the search) · TC-4 (no id and no rule number on
//           screen) · US-INT-021 TC-1 (the amber word and the DASHES) ·
//           TC-7 (`changed` only where something can be revised) · the route
//           ranks below the mappings route
// ─────────────────────────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { RouteObject } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import type { ConnectionRuns, RunDetail, RunRow } from "@/api/integrationsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { APP_ROUTES } from "@/App";

import { ConnectionDetailPage } from "./ConnectionDetailPage";
import { ValueMappingPage } from "./ValueMappingPage";

const SMTP = "email_smtp";

function runRow(over: Partial<RunRow> = {}): RunRow {
  return {
    id: "01a06aad-0000-7000-8000-000000000001",
    trace_id: "A7F3C9E1",
    provider_key: SMTP,
    provider_name: "Custom SMTP",
    connection_label: "billing@brazosbend.example",
    environment: "production",
    operation: "send_message",
    operation_label: "Send messages",
    direction: "outbound",
    trigger: "scheduled",
    outcome: "succeeded",
    attempted: 93,
    succeeded: 93,
    failed: 0,
    skipped: 0,
    changed: 0,
    show_changed: false,
    summary: "Every message was accepted by the mail server.",
    started_at: "2026-09-01T06:02:00Z",
    finished_at: "2026-09-01T06:06:00Z",
    has_artifact: false,
    named_items: 0,
    unnamed_items: 0,
    ...over,
  };
}

const SEPTEMBER = runRow({ id: "run-sep", trace_id: "9F1B2C3D" });
const AUGUST = runRow({
  id: "run-aug",
  trace_id: "4C71A0E5",
  outcome: "partial",
  succeeded: 86,
  failed: 7,
  named_items: 7,
  started_at: "2026-08-01T06:02:00Z",
  summary: "Seven addresses were refused by the mail server.",
});
const JULY = runRow({
  id: "run-jul",
  trace_id: "B2E4F6A8",
  outcome: "unconfirmed",
  succeeded: 0,
  failed: 0,
  started_at: "2026-07-01T06:03:00Z",
  summary: "We handed over 93 messages and the provider did not say how many it accepted.",
});

const SEVEN = [
  "j.ortiz@example.invalid",
  "d.whitfield@example.invalid",
  "p.nakamura@example.invalid",
  "s.abbott@example.invalid",
  "r.delgado@example.invalid",
  "m.fitzgerald@example.invalid",
  "c.brennan@example.invalid",
];

function detailOf(row: RunRow, over: Partial<RunDetail> = {}): RunDetail {
  return {
    ...row,
    provider_error: null,
    artifact_link: null,
    content_hash: null,
    items: [],
    // CR-069 wave K — a finished run of an operation with no unsafe defaults.
    // Both are REQUIRED on the type rather than optional, and that is the whole
    // reason `tsc` caught this factory: an optional field would have let every
    // caller keep compiling while the screen silently drew nothing.
    asked_for: [],
    collecting: null,
    ...over,
  };
}

function payload(rows: RunRow[], over: Partial<ConnectionRuns> = {}): ConnectionRuns {
  return {
    provider: {
      key: SMTP,
      display_name: "Custom SMTP",
      category: "email",
      // ⚠ `native`, NOT `redirect`. SMTP AUTH carries the credential inside the
      // protocol's own handshake, so this connection genuinely HAS a password
      // and the panel keeps offering to replace it. A fixture that said
      // `redirect` here would quietly test the other branch and prove nothing
      // about the screen wave E built.
      auth: { mode: "we_hold_theirs", placement: "native" },
      // `CR-110-BRC04` wave B — whether the connector can be connected at
      // all. The grid has carried it since wave A; S142 now does too, so a
      // placeholder's own page stops reading as ready.
      disposition: { kind: "live" as const, wave: null },
    },
    describe: "billing@brazosbend.example · Custom SMTP",
    display_state: "working",
    connection: {
      id: "01a06aad-0000-7000-8000-00000000000c",
      label: "billing@brazosbend.example",
      describe: "billing@brazosbend.example · Custom SMTP",
      settings: {},
      connected_by: "Alex Reed",
      environment: "production",
      status: "working",
      enabled: true,
      cadence: "manual",
      next_run_at: null,
      last_test_at: null,
      last_test_ok: null,
      last_test_text: null,
      connected_at: "2026-08-12T09:00:00Z",
      credential: null,
      expiry: { state: "unknown", expires_at: null, days_left: null, window_days: 14, version: null },
    },
    // Wave E (US-INT-024 · US-INT-025): the two versions of frame 54.2 and the
    // figures the disconnect confirm states. `messages_waiting` is a REAL
    // number here; the `null` case has its own test.
    credentials: [
      {
        version: 2,
        is_active: true,
        hint: "••••iday",
        expires_at: null,
        rotated_at: null,
        created_at: "2026-08-28T17:04:00Z",
      },
      {
        version: 1,
        is_active: false,
        hint: "••••kbox",
        expires_at: null,
        rotated_at: "2026-08-28T17:04:00Z",
        created_at: "2026-08-12T09:00:00Z",
      },
    ],
    disconnect: {
      category: "email",
      label: "billing@brazosbend.example",
      versions: 2,
      runs_kept: 20,
      channel: "email",
      messages_waiting: 12,
    },
    operations: [
      {
        name: "send_message",
        label: "Send messages",
        description: "We send bills and notices through this server.",
        direction: "out",
        initiative: "us",
        state: "working",
        last_run_at: "2026-09-01T06:06:00Z",
        last_outcome: "succeeded",
        trace_id: "9F1B2C3D",
        test_action: "Send one real message to an address you type.",
        test_needs_recipient: true,
      // CR-069 wave M — `BR-INT-048`'s three declared facts.
      executor: "server",
      latency_budget_ms: null,
      result_disposition: null,
      },
    ],
    filters: {
      operations: [{ name: "send_message", label: "Send messages" }],
      outcomes: ["succeeded", "partial", "failed", "unconfirmed", "indeterminate"],
      triggers: ["manual", "scheduled", "dispatcher", "webhook", "partner"],
    },
    applied: { q: "", operation: null, outcome: null, trigger: null },
    rows,
    page: { page: 1, per: 20, count: rows.length, pages: 1 },
    elsewhere: 0,
    ...over,
  };
}

function ok<T>(data: T): ApiResponse<T> {
  return { status: 200, data, etag: null, notModified: false };
}

function mount(data: ConnectionRuns, details: Record<string, RunDetail> = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(
    queryKeys.integrationRuns(
      SMTP,
      JSON.stringify(["", {}, 1, 50, "started", "desc"]),
    ),
    data,
  );
  queryClient.setQueryData(queryKeys.regionalSettings, {
    timezone: "America/Chicago",
    date_format: "MM/DD/YYYY",
  });
  for (const [id, one] of Object.entries(details)) {
    queryClient.setQueryData(queryKeys.integrationRun(SMTP, id), one);
  }
  const get = vi.fn(async (path: string) => {
    const match = /\/runs\/([^?]+)$/.exec(path);
    if (match !== null) return ok(details[match[1]] ?? detailOf(data.rows[0]));
    return ok(data);
  });
  const client = { get } as unknown as ApiClient;
  // Wave E: the Manage panel fires a toast after a committed action (IS-6), so
  // the page now needs the provider the real shell mounts above the router.
  const view = render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
      <MemoryRouter initialEntries={[`/brazosbend/settings/integrations/${SMTP}`]}>
        <Routes>
          <Route
            path="/:tenant/settings/integrations/:key/mappings"
            element={<ValueMappingPage client={client} />}
          />
          <Route
            path="/:tenant/settings/integrations/:key"
            element={<ConnectionDetailPage client={client} />}
          />
        </Routes>
      </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { ...view, client, queryClient };
}

describe("S142 · why the connection is in that state (US-INT-022, wave F · DEF-INT-4025)", () => {
  afterEach(cleanup);

  // The breaker writes `last_test_text` on the connection — *The mail server
  // is not answering.* — and until wave F nothing drew it.
  //
  // ⚠ **THE FIXTURE NOW SETS `display_state` AS WELL AS THE CONNECTION'S
  // `status`, BECAUSE THE SCREEN'S GUARD MOVED THERE ON 2026-09-17.** The
  // sentence used to be drawn whenever there was one, working or not, and that
  // is a stale reason under a green word: a connector that failed on Monday and
  // was fixed on Tuesday carried Monday's excuse all week. The PO's KPI ruling
  // gave it a place — a red line under the strip — and a red line is only
  // honest while the thing really is red. `display_state` is the word actually
  // on the screen beside it, so they cannot disagree.
  const withReason = (text: string | null, over: Record<string, unknown> = {}) =>
    payload([SEPTEMBER], {
      display_state: "not_working",
      connection: {
        ...payload([SEPTEMBER]).connection!,
        status: "not_working",
        last_test_ok: false,
        last_test_text: text,
        ...over,
      },
    } as never);

  it("the breaker's sentence is on the screen, under the state word", () => {
    const { container } = mount(withReason("The mail server is not answering."));
    const reason = container.querySelector("[data-state-reason]");
    expect(reason).not.toBeNull();
    expect(reason?.textContent).toBe("The mail server is not answering.");
  });

  it("and nothing is drawn when there is nothing to say", () => {
    const { container } = mount(withReason(null));
    expect(container.querySelector("[data-state-reason]")).toBeNull();
  });

  // ⚠ **THE GUARD IS THE STATE AND NOT MERELY THE FIELD'S PRESENCE**, and this
  // case is what makes that a claim rather than a comment. A connector that
  // failed and has since been fixed still HOLDS the old sentence — the server
  // never clears it — so a screen keyed off the text alone prints yesterday's
  // reason in red under today's green word.
  it("a connector that has been FIXED stops showing the old reason", () => {
    const { container } = mount(
      payload([SEPTEMBER], {
        display_state: "working",
        connection: {
          ...payload([SEPTEMBER]).connection!,
          status: "working",
          last_test_ok: true,
          last_test_text: "The mail server is not answering.",
        },
      } as never),
    );
    expect(container.querySelector("[data-state-reason]")).toBeNull();
  });

  it("the sentence carries no rule id and no database id (B14 rule 31)", () => {
    const { container } = mount(withReason("The mail server is not answering."));
    const html = container.innerHTML;
    expect(html).not.toMatch(/BR-[A-Z]{3}-\d+/);
    expect(container.querySelector("[data-state-reason]")?.textContent).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}/,
    );
  });
});

describe("S142 · the run record (US-INT-020 · US-INT-021)", () => {
  // vitest runs without globals, so Testing Library's auto-cleanup never registers.
  afterEach(cleanup);

  it("TC-1: the runs read newest first, and the 1 August row says 86 of 93 · 7 bad addresses", () => {
    const { container } = mount(payload([SEPTEMBER, AUGUST, JULY]));
    const rows = container.querySelectorAll("[data-run-row]");
    expect(rows).toHaveLength(3);
    expect([...rows].map((one) => one.getAttribute("data-run-row"))).toEqual([
      "9F1B2C3D",
      "4C71A0E5",
      "B2E4F6A8",
    ]);
    expect(
      container.querySelector('[data-run-counts="4C71A0E5"]')?.textContent,
    ).toBe("86 of 93 · 7 bad addresses");
    expect(
      container.querySelector('[data-run-counts="9F1B2C3D"]')?.textContent,
    ).toBe("93 of 93");
  });

  it("US-INT-021 TC-1: the 1 July row reads Unconfirmed, in amber, and never green", () => {
    const { container } = mount(payload([SEPTEMBER, AUGUST, JULY]));
    const cell = container.querySelector('[data-run-counts="B2E4F6A8"]');
    expect(cell?.textContent).toBe("Unconfirmed · 93 sent, provider did not say");
    // The colour is a TOKEN this theme declares — amber, and not the green a
    // succeeded run gets. The computed colour itself is read in the browser
    // walkthrough; here the token is asserted so a swap shows up in the suite.
    expect(cell?.className).toContain("text-warning-700");
    expect(cell?.className).not.toContain("text-success-700");
    expect(
      container.querySelector('[data-run-counts="9F1B2C3D"]')?.className,
    ).toContain("text-success-700");
  });

  it("US-INT-021: an unconfirmed run's tiles are DASHES, and a zero is never shown", async () => {
    const user = userEvent.setup();
    const detail = detailOf(JULY);
    const { container } = mount(payload([JULY]), { "run-jul": detail });
    await user.click(screen.getByRole("button", { name: "Open the run" }));
    const tiles = container.querySelectorAll("[data-count-tile]");
    expect(tiles).toHaveLength(4);
    // *93 handed over · — sent · — refused · — skipped* (frame 51.2)
    expect([...tiles].map((one) => one.querySelector("span")?.textContent)).toEqual([
      "93",
      "—",
      "—",
      "—",
    ]);
    expect(screen.getByText(/Dashes, not zeroes/)).toBeTruthy();
  });

  it("TC-1: opening the 1 August run names the seven, each with the mailbox's own sentence", async () => {
    const user = userEvent.setup();
    const detail = detailOf(AUGUST, {
      items: SEVEN.map((address, index) => ({
        ref: `A-104${index}`,
        detail: address,
        outcome: "failed",
        provider_text: "No such mailbox",
      })),
    });
    const { container } = mount(payload([AUGUST]), { "run-aug": detail });
    await user.click(screen.getByRole("button", { name: "Open the run" }));
    const items = container.querySelectorAll("[data-run-item]");
    expect(items).toHaveLength(7);
    expect([...items].map((one) => one.getAttribute("data-run-item"))).toEqual(SEVEN);
    expect(within(items[0] as HTMLElement).getByText("No such mailbox")).toBeTruthy();
    // …and the tiles are NUMBERS here, because the far end did confirm.
    const tiles = container.querySelectorAll("[data-count-tile]");
    expect([...tiles].map((one) => one.getAttribute("data-dashed"))).toEqual([
      "false",
      "false",
      "false",
      "false",
    ]);
  });

  // ═════════════════════════════════════════════════════════════════════════
  // CR-069 wave K — the collecting band, the four parameters, and the file
  // ═════════════════════════════════════════════════════════════════════════

  it("US-INT-031 frame 53.2: a run still going says what it is waiting for and when it asks next", async () => {
    const user = userEvent.setup();
    const building = runRow({
      id: "run-export",
      trace_id: "C4D5E6F7",
      provider_key: "meters_neptune360",
      operation: "request_billing_export",
      operation_label: "Request billing export",
      outcome: "running",
      attempted: 1,
      succeeded: 0,
      failed: 0,
      summary: null,
    });
    const detail = detailOf(building, {
      collecting: { done: 4, total: 40, asked: 4, next_in_s: 30 },
    });
    const { container } = mount(payload([building]), { "run-export": detail });
    await user.click(screen.getByRole("button", { name: "Open the run" }));
    const band = container.querySelector("[data-collecting]");
    expect(band?.getAttribute("data-collecting")).toBe("poll");
    // The demo's own sentence, and the two figures beside it.
    expect(
      screen.getByText(/They are building the file\. We will collect it when it is ready/),
    ).toBeTruthy();
    expect(screen.getByText("asked them 4 times")).toBeTruthy();
    expect(screen.getByText("checking again in 30 seconds")).toBeTruthy();
    expect(band?.getAttribute("data-collecting-asked")).toBeNull();
    expect(
      container.querySelector("[data-collecting-asked]")?.getAttribute("data-collecting-asked"),
    ).toBe("4");
  });

  it("US-INT-028: a walk in progress reads window 61 of 105, not a percentage", async () => {
    const user = userEvent.setup();
    const walking = runRow({
      id: "run-walk",
      trace_id: "D5E6F7A8",
      provider_key: "meters_neptune360",
      operation: "collect_readings",
      operation_label: "Meter readings",
      outcome: "running",
      summary: null,
    });
    const detail = detailOf(walking, {
      collecting: { done: 61, total: 105, window: 61, of: 105 },
    });
    const { container } = mount(payload([walking]), { "run-walk": detail });
    await user.click(screen.getByRole("button", { name: "Open the run" }));
    expect(container.querySelector("[data-collecting]")?.getAttribute("data-collecting")).toBe(
      "walk",
    );
    expect(screen.getByText("window 61 of 105")).toBeTruthy();
  });

  it("a FINISHED run draws no collecting band — a stale one would claim work still running", async () => {
    const user = userEvent.setup();
    const detail = detailOf(AUGUST);
    const { container } = mount(payload([AUGUST]), { "run-aug": detail });
    await user.click(screen.getByRole("button", { name: "Open the run" }));
    expect(container.querySelector("[data-collecting]")).toBeNull();
  });

  it("US-INT-035 frame 83.1: the four parameters we state are shown, and the panel is absent when there are none", async () => {
    const user = userEvent.setup();
    const collection = runRow({
      id: "run-reads",
      trace_id: "E6F7A8B9",
      provider_key: "meters_neptune360",
      operation: "collect_readings",
      operation_label: "Meter readings",
    });
    const four = [
      "actual_consumption",
      "include_estimates",
      "unit_of_measure",
      "read_time_zone",
    ];
    const detail = detailOf(collection, { asked_for: four });
    const { container } = mount(payload([collection]), { "run-reads": detail });
    await user.click(screen.getByRole("button", { name: "Open the run" }));
    expect(container.querySelector("[data-asked-for]")?.getAttribute("data-asked-for")).toBe("4");
    expect(screen.getByText("What we ask them for")).toBeTruthy();
    for (const name of four) expect(screen.getByText(name)).toBeTruthy();
    expect(screen.getByText(/Their own defaults are never used/)).toBeTruthy();
  });

  it("an operation with no unsafe defaults draws no panel at all (B14 rule 32)", async () => {
    const user = userEvent.setup();
    const detail = detailOf(AUGUST, { asked_for: [] });
    const { container } = mount(payload([AUGUST]), { "run-aug": detail });
    await user.click(screen.getByRole("button", { name: "Open the run" }));
    expect(container.querySelector("[data-asked-for]")).toBeNull();
    expect(screen.queryByText("What we ask them for")).toBeNull();
  });

  it("BR-INT-046: the collected file is linked on the run, and only once it is in hand", async () => {
    const user = userEvent.setup();
    const detail = detailOf(AUGUST, {
      artifact_link: "https://api.neptune360.example/exports/RECORDED-EXPORT-0042.csv",
    });
    const { container } = mount(payload([AUGUST]), { "run-aug": detail });
    await user.click(screen.getByRole("button", { name: "Open the run" }));
    const link = container.querySelector("[data-run-artifact]");
    expect(link?.getAttribute("href")).toBe(
      "https://api.neptune360.example/exports/RECORDED-EXPORT-0042.csv",
    );
    expect(link?.textContent).toBe("The file they built");
  });

  it("frame 52.2: our sentence first, the server's words underneath — and only here", async () => {
    const user = userEvent.setup();
    const failed = runRow({
      id: "run-test",
      trace_id: "A7F3C9E1",
      outcome: "failed",
      attempted: 1,
      succeeded: 0,
      failed: 1,
      summary: "The mail server rejected the password.",
    });
    const detail = detailOf(failed, { provider_error: "535 5.7.8 AUTHENTICATION FAILED" });
    const { container } = mount(payload([failed]), { "run-test": detail });
    // The list row does NOT carry the provider's words.
    expect(container.querySelector("[data-provider-said]")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Open the run" }));
    expect(container.querySelector("[data-provider-said]")?.textContent).toBe(
      "535 5.7.8 AUTHENTICATION FAILED",
    );
    expect(screen.getByText("The mail server rejected the password.")).toBeTruthy();
    expect(container.querySelector('[data-run-counts="A7F3C9E1"]')?.textContent).toBe("Failed");
  });

  it("TC-2: the search box is the trace id, and a hit on another connection says so", async () => {
    const user = userEvent.setup();
    const elsewhere = runRow({
      id: "run-neptune",
      trace_id: "B1C2D3E4",
      provider_key: "meters_neptune360",
      provider_name: "Neptune 360",
      connection_label: "Water meter cloud",
      operation: "collect_readings",
      operation_label: "Collect readings",
    });
    const { container } = mount(payload([elsewhere], { elsewhere: 1 }));
    expect(screen.getAllByLabelText("Support reference").length).toBeGreaterThan(0);
    expect(container.querySelector('[data-run-elsewhere="meters_neptune360"]')?.textContent).toBe(
      "on Water meter cloud",
    );
    expect(screen.getByText(/ran on another connection/)).toBeTruthy();
    await user.type(screen.getAllByLabelText("Support reference")[0], "a7f3c9e1");
    expect(container.querySelector('[data-screen="S142"]')).toBeTruthy();
  });

  it("TC-4: the trace id is the only identifier on the screen, and it is not a database id", () => {
    const { container } = mount(payload([SEPTEMBER, AUGUST, JULY]));
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
    expect(text).not.toMatch(/\bBR-[A-Z]{3}-\d{3,5}\b/);
    expect(text).not.toMatch(/\brun-(sep|aug|jul)\b/); // the ids the row action uses
    expect(text).toContain("Support reference");
    expect(text).toContain("4C71A0E5");
  });

  it("TC-7: `changed` is a tile only where something can be revised", async () => {
    const user = userEvent.setup();
    const collection = runRow({
      id: "run-collect",
      trace_id: "C1D2E3F4",
      operation: "collect_readings",
      operation_label: "Collect readings",
      attempted: 1240,
      succeeded: 1240,
      changed: 6,
      show_changed: true,
    });
    const detail = detailOf(collection);
    const { container } = mount(payload([collection]), { "run-collect": detail });
    expect(container.querySelector('[data-run-counts="C1D2E3F4"]')?.textContent).toBe(
      "1240 of 1240 · 6 revised",
    );
    await user.click(screen.getByRole("button", { name: "Open the run" }));
    expect(container.querySelector('[data-count-tile="Revised"]')).toBeTruthy();
    expect(container.querySelector('[data-count-tile="Skipped"]')).toBeNull();
  });

  it("rule 15: the row action is an icon with an accessible name, not a text link", () => {
    mount(payload([SEPTEMBER]));
    const action = screen.getByRole("button", { name: "Open the run" });
    expect(action.querySelector("svg")).toBeTruthy();
    expect(action.textContent).toBe("");
  });

  it("the route ranks BELOW the mappings route — S143 is not swallowed by /:key", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(queryKeys.regionalSettings, {
      timezone: "America/Chicago",
      date_format: "MM/DD/YYYY",
    });
    const client = { get: vi.fn(async () => ok(payload([]))) } as unknown as ApiClient;
    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
        <MemoryRouter initialEntries={[`/brazosbend/settings/integrations/${SMTP}/mappings`]}>
          <Routes>
            <Route
              path="/:tenant/settings/integrations/:key/mappings"
              element={<div data-screen="S143" />}
            />
            <Route
              path="/:tenant/settings/integrations/:key"
              element={<ConnectionDetailPage client={client} />}
            />
          </Routes>
        </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(container.querySelector('[data-screen="S143"]')).toBeTruthy();
    expect(container.querySelector('[data-screen="S142"]')).toBeNull();
  });
});

/**
 * ── CR-110-BRC04 wave B · THE DOOR, ASSERTED AGAINST THE REAL ROUTE TABLE ──
 *
 * **The test that would have caught *this screen has no route*.** Its sibling
 * above ("the route ranks BELOW the mappings route") builds its OWN `<Routes>`
 * and therefore proves only that React Router ranks two patterns the way we
 * think it does — it would pass unchanged if `App.tsx` mounted S142 at a
 * different address, or nowhere at all. That is hard-won law 7's *looking at
 * the wrong thing*, named in `CLAUDE.md` with this exact shape: *"a
 * hold-expiry test asserted a screen was REGISTERED at an address while the
 * router was mounting it somewhere else; both screens opened onto 'not built
 * yet' and every check passed."*
 *
 * So these read `APP_ROUTES` — the array `createBrowserRouter` is actually
 * handed — and assert the door **by ADDRESS and by the connector it opens**,
 * which is what a later lane cannot satisfy by mounting the screen elsewhere.
 *
 * ⚠ **THE ADDRESS IS `settings/integrations/:key` AND IT MUST NOT MOVE.** The
 * Integration Blueprint draws `/:tenant/settings/connectors/<key>`, and the
 * ruling of 2026-09-16 keeps the route as it is — *"changing it breaks every
 * bookmark to buy a word in a place nobody reads for meaning"*. The visible
 * word becomes *Connector*; the address does not. A lane that "finishes the
 * rename" by moving this path turns every existing link into a 404, and this
 * case is what tells them so.
 */
describe("S142 · the door (CR-110-BRC04 wave B)", () => {
  afterEach(cleanup);

  function flatten(routes: RouteObject[], prefix = ""): { path: string; route: RouteObject }[] {
    const out: { path: string; route: RouteObject }[] = [];
    for (const route of routes) {
      const here = route.path === undefined ? prefix : `${prefix}/${route.path}`.replace(/\/+/g, "/");
      if (route.path !== undefined) out.push({ path: here, route });
      if (route.children !== undefined) out.push(...flatten(route.children, here));
    }
    return out;
  }

  it("the address exists in the route table the browser router is built from", () => {
    const paths = flatten(APP_ROUTES).map((one) => one.path);
    expect(paths).toContain("/:tenant/settings/integrations/:key");
  });

  it("and that address opens S142, for the connector named in it", async () => {
    // Mounted under the REAL path pattern, so `useParams().key` is a real
    // value rather than `undefined` — the fixture trap `CLAUDE.md` records for
    // the portal front page, where a bare MemoryRouter left every address the
    // page built as `//portal/…` and `toContain` read it as a good string.
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(queryKeys.regionalSettings, {
      timezone: "America/Chicago",
      date_format: "MM/DD/YYYY",
    });
    const asked: string[] = [];
    const client = {
      get: vi.fn(async (url: string) => {
        asked.push(url);
        return ok(payload([SEPTEMBER]));
      }),
    } as unknown as ApiClient;
    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/brazosbend/settings/integrations/${SMTP}`]}>
            <Routes>
              <Route
                path="/:tenant/settings/integrations/:key"
                element={<ConnectionDetailPage client={client} />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    // ⚠ AWAIT THE SCREEN BEFORE ASSERTING ON IT. The page fetches its payload,
    // so a synchronous `querySelector` here reads the LOADING frame and finds
    // nothing — which looks exactly like "the route is wrong" and would have
    // been a test that fails for a reason it does not name.
    await screen.findByText("Custom SMTP");
    expect(container.querySelector('[data-screen="S142"]')).toBeTruthy();
    // BY THE CONNECTOR, not merely by the screen: the key in the address is
    // the key the screen fetches and the key it stamps on itself. A screen
    // that opened but showed another connector would pass the first assertion
    // and fail these two.
    expect(container.querySelector(`[data-provider="${SMTP}"]`)).toBeTruthy();
    expect(asked.some((one) => one.includes(SMTP))).toBe(true);
  });
});

// ── S142 rebuilt to its drawing — VIEW-17, p066–p067 (DEF-INT-5560) ────────
//
// The PO put this screen beside the Integration Blueprint and asked why it
// does not match. Six differences were mine; these are the four that a test in
// this harness can hold, plus the two that only a browser can see are noted in
// the walkthrough rather than faked here.
//
// ⚠ **WHAT WOULD MAKE EACH OF THESE PASS WRONGLY, ANSWERED ONE BY ONE — this
// block is the answer to law 7's second habit and not decoration.**
//
//  · *"Recent activity" is on the screen.* It ALREADY IS, and always was: the
//    catalogue value is sentence case and it is CSS — `uppercase` — that puts
//    it on screen as *RECENT ACTIVITY*. jsdom computes no styles, so a text
//    assertion passes today, before and after, and proves nothing. These cases
//    assert the ELEMENT (`h3`, the Panel's own heading) and the ABSENCE of the
//    `uppercase` utility in its class list, which is the mechanism.
//
//  · *"the toolbar exists".* It already exists whenever a run has happened —
//    `DataTable` has drawn it since wave C. What the drawing asks is that it
//    sit INSIDE the Recent activity panel, so the case queries it through
//    `[data-runs-panel]` rather than through the document.
//
//  · *"the footer buttons exist".* They already exist; they are simply in the
//    wrong place. So the case asserts DOCUMENT ORDER against a run row, which
//    is the only form of this assertion that can fail on today's code.
//
//  · *"no `Test it now` button".* A payload that never reaches the empty
//    branch would satisfy that vacuously, so the empty case FIRST asserts the
//    empty block's own title is on screen — proving we are in the branch — and
//    only then that it carries no control and no reason line.
describe("S142 · rebuilt to VIEW-17 (p066–p067)", () => {
  afterEach(cleanup);

  it("p067: the footer row sits BELOW the activity table, not above it", () => {
    const { container } = mount(payload([SEPTEMBER, AUGUST]));
    const footer = container.querySelector("[data-connection-footer]");
    const row = container.querySelector("[data-run-row]");
    expect(row).toBeTruthy();
    expect(footer).toBeTruthy();
    expect(
      (row as Element).compareDocumentPosition(footer as Element) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // ⚠ **THE FOOTER'S CONTROLS MOVED TO THE PAGE HEAD ON 2026-09-17 AND ITS
    // NOTE DID NOT**, so this case asserts the half the PO left alone and the
    // half they moved, in one place. Verbatim: *"actions on this screens -
    // should be on top - like we follow as per our ui guideline"*. p067 still
    // draws the append-only footnote on this row and B14 rule 41 keeps it here;
    // B14 rule 38 is what took the buttons up.
    expect(within(footer as HTMLElement).getByText(/Runs are kept/)).toBeTruthy();
    expect(within(footer as HTMLElement).queryByText("Disconnect")).toBeNull();
  });

  it("2026-09-17: every action is in the page head, above the run table", () => {
    const { container } = mount(payload([SEPTEMBER, AUGUST]));
    const head = container.querySelector(".page-header-actions");
    expect(head).toBeTruthy();
    // `Disconnect` is the one every connected connector has, whatever its auth
    // mode, so it is the one that proves the ROW rather than a single arm of it.
    expect(within(head as HTMLElement).getByText("Disconnect")).toBeTruthy();
    const row = container.querySelector("[data-run-row]");
    expect(
      (head as Element).compareDocumentPosition(row as Element) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("2026-09-17: the KPI line is under the head and above the first panel", () => {
    const { container } = mount(payload([SEPTEMBER]));
    const strip = container.querySelector(".kpi-grid");
    expect(strip).toBeTruthy();
    // Four tiles, and the one that used to be a chip on the identity line.
    expect((strip as Element).querySelectorAll(".kpi")).toHaveLength(4);
    expect(container.querySelector("[data-kpi='apis']")?.textContent).toBe("1");
    // ⚠ **THE CHIP LEFT IN THE SAME COMMIT.** One fact in two places is what
    // drifts, which is the whole reason the PO's tile replaced it rather than
    // joining it.
    const head = container.querySelector(".page-header");
    expect(head?.textContent).not.toMatch(/\d+ APIs?\b/);
  });

  it("2026-09-17: *Cannot be tested* is said ONCE under the table, not per row", () => {
    // TWO operations, one testable and one not — which is the mix that makes
    // the assertion mean something. A fixture where every row is untestable
    // cannot tell *the sentence moved* from *the column was emptied*.
    const base = payload([SEPTEMBER]);
    const untestable = {
      ...base.operations[0],
      name: "collect_bounce",
      label: "Collect bounces",
      test_action: null,
    };
    const { container } = mount({
      ...base,
      operations: [base.operations[0], untestable],
    } as never);
    const cells = [...container.querySelectorAll("[data-test-action]")];
    expect(cells).toHaveLength(2);
    // The row that CAN be tested keeps the manifest's own sentence.
    expect(cells[0].textContent).toContain("Send one real message");
    // The row that cannot says nothing at all, rather than a fourth copy of
    // one fact (B14 rules 32 and 33).
    expect(cells[1].textContent).toBe("");
    const note = container.querySelectorAll("[data-test-note]");
    expect(note).toHaveLength(1);
    expect(note[0].textContent).toBe("Cannot be tested until first use.");
  });

  it("p067: *Recent activity* is the panel's heading, not small grey capitals", () => {
    mount(payload([SEPTEMBER]));
    const heading = screen.getByRole("heading", { name: "Recent activity" });
    // `Panel` writes an `<h3>` at `text-h5`, which is what p066/p067 draw for
    // *Keys we issue* and *N APIs on this connector* — one heading level for
    // the three sections a reader sees as equals.
    expect(heading.tagName).toBe("H3");
    expect(heading.className).not.toContain("uppercase");
  });

  it("p067: the toolbar and the table are INSIDE the activity panel", () => {
    const { container } = mount(payload([SEPTEMBER, AUGUST]));
    const panel = container.querySelector("[data-runs-panel]");
    expect(panel).toBeTruthy();
    expect((panel as Element).querySelector(".table-toolbar")).toBeTruthy();
    expect((panel as Element).querySelector("table")).toBeTruthy();
  });

  it("B14 rule 32: the section carries no description line", () => {
    mount(payload([SEPTEMBER]));
    expect(screen.queryByText("Every attempt, newest first.")).toBeNull();
  });

  it("with nothing run, the empty block offers no control and no reason line", () => {
    const { container } = mount(
      payload([], { page: { page: 1, per: 50, count: 0, pages: 0 } }),
    );
    // First prove we are really in the empty branch — otherwise the two
    // assertions below are true of a screen that simply drew a table.
    expect(screen.getByText("Nothing has run yet")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Test it now" })).toBeNull();
    expect(container.querySelector("[data-cta-reason]")).toBeNull();
  });

  it("p067: the append-only note rides in the footer row, beside the buttons", () => {
    const { container } = mount(payload([SEPTEMBER]));
    const footer = container.querySelector("[data-connection-footer]");
    expect(footer).toBeTruthy();
    expect((footer as HTMLElement).textContent).toContain(
      "Runs are kept exactly as they happened",
    );
  });
});
