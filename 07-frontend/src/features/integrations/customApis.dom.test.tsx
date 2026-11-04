// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-115-BRC05 §7 — *"CUSTOM URLs ON A CONNECTOR"*, PO 2026-09-17.
//           R32 (the form) · R36 (the Edit button; standard APIs switch only) ·
//           §7.5 rule 4 (*Working N of M* counts only ENABLED APIs).
// Screens:  S142 the connector view · S147 · INT-07 the set-up form.
// Rules:    B14 rule 31 (no database id is ever the visible value of a field) ·
//           B14 rule 32 (a screen has a description budget; a stated absence is
//           CLOSED by default) · CLAUDE.md hard-won law 1 (a sentence claiming
//           a guarantee is not the guarantee) · law 2's mirror (a control that
//           renders and changes nothing) · law 6 (no gate reads rendered
//           output) · law 7 habit 2 (name what would make this pass wrongly).
// ───────────────────────────────────────────────────────
/**
 * The three things about the per-API table that ONLY rendered output can say.
 *
 * ⚠ **EVERY CASE HERE EXISTS BECAUSE A BROWSER FOUND SOMETHING A GREEN SUITE
 * COULD NOT.** Two defects were caught by clicking this screen after the
 * backend was finished and every test passed:
 *
 *   1. **`custom_api_kinds` was served on the CARD and not on the payload S142
 *      actually fetches**, so `+ API` was never drawn and the whole feature was
 *      unreachable. The field is optional on the wire and `[]` is a legal
 *      answer, so nothing could tell *this connector offers no kinds* from
 *      *nobody plumbed it through*. That one is pinned by a BACKEND case,
 *      `test_the_screens_own_payload_carries_the_closed_list_and_the_rows`,
 *      because the fault was in the payload rather than in the screen.
 *   2. **the set-up screen went on claiming *All use the address above***
 *      after a clerk gave one API its own URL — a footnote asserting a
 *      guarantee the rows directly above it contradict. Case 4 below is that
 *      one, and it is the reason this file exists at all.
 *
 * ── WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2) ────────────────────
 *  * **A FIXTURE THAT CANNOT TELL A RENDERED TABLE FROM AN EMPTY PAGE.** Every
 *    `queryBy…` returning null reads as *correctly absent* over a page that
 *    drew nothing — `DEF-CWP-3925`'s exact shape. So case 0 asserts the table
 *    is really there and really populated before any absence is claimed.
 *  * **A COUNT ASSERTED ON THE NUMERATOR ALONE.** *0 of 4* → *0 of 3* is
 *    satisfied by a build that filters the working rows and forgets the total,
 *    which reads *0 of 4* on a connector with one API off — wrong in the
 *    alarming direction. Case 3 asserts the WHOLE string.
 *  * **AN EDIT CONTROL FOUND BY `data-testid` RATHER THAN BY ITS NAME.** A
 *    `data-testid` passes with no accessible label at all, which is the failure
 *    B14's icon rule exists to prevent. The row actions here are addressed by
 *    `getByRole("button", { name })` — the same string a screen reader speaks.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";

import type { ConnectionRuns, IntegrationsGrid, ProviderCard } from "@/api/integrationsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { ConnectionDetailPage } from "./ConnectionDetailPage";
import { ConnectorSetupPage } from "./ConnectorSetupPage";

afterEach(cleanup);

const TENANT = "brazosbend";
const KEY = "gis_esri";
const OURS = "https://gis.brazosbend.example/addr";
const THEIRS = "https://points.brazosbend.example/addr";

type Row = Record<string, unknown>;

/** One API row as the server serves it — ours unless `custom` says otherwise. */
function op(name: string, extra: Row = {}): Row {
  return {
    name,
    label: name,
    description: "",
    direction: "in",
    initiative: "us",
    state: "working",
    last_run_at: null,
    last_outcome: null,
    trace_id: null,
    test_action: null,
    test_needs_recipient: false,
    executor: "server",
    latency_budget_ms: null,
    result_disposition: null,
    trigger: "inline",
    host_field: "base_url",
    endpoint: OURS,
    endpoint_source: "operation_field",
    endpoint_field: "base_url",
    rate_limit_per_minute: null,
    can_run_now: false,
    // `CR-115-BRC05` §7 — the five fields the per-API work added.
    api_id: null,
    is_standard: true,
    custom_name: null,
    api_kind: "address_lookup",
    enabled: true,
    ...extra,
  };
}

/** Theirs: a name, an address of its own, and the provenance that says so. */
const THEIR_ROW = (extra: Row = {}) =>
  op("address_search", {
    api_id: "11111111-2222-3333-4444-555555555555",
    is_standard: false,
    custom_name: "Address points",
    endpoint: THEIRS,
    endpoint_source: "api_row",
    endpoint_field: null,
    ...extra,
  });

function payload(operations: Row[], kinds: Row[] = [{ kind: "map_tiles", refusal: null }]) {
  return {
    provider: {
      key: KEY,
      display_name: "Esri ArcGIS",
      category: "maps",
      summary: "Find an address and keep parcels in step.",
      auth: { mode: "we_hold_theirs", placement: "query" },
      disposition: { kind: "live", wave: null, phase: 4 },
    },
    describe: null,
    display_state: "untested",
    connection: {
      id: "c1",
      label: null,
      describe: null,
      settings: { base_url: OURS },
      connected_by: null,
      environment: "production",
      status: "untested",
      enabled: true,
      cadence: "nightly",
      next_run_at: null,
      last_test_at: null,
      last_test_ok: null,
      last_test_text: null,
      connected_at: null,
      credential: null,
      expiry: { state: "unknown", expires_at: null, days_left: null, window_days: 14, version: null },
    },
    operations,
    custom_api_kinds: kinds,
    credentials: [],
    issued_keys: [],
    disconnect: null,
    // ⚠ **REQUIRED BY THE PAGE, NOT BY THE TYPE** — the `as unknown as` cast
    // below would have let this be omitted, and the component reads
    // `payload.filters.operations.map(...)` unguarded. A fixture missing it
    // throws before a single assertion runs, and the message names
    // `operations` rather than the fixture, which is where five minutes go.
    filters: {
      operations: operations.map((one) => ({ name: one.name, label: one.label })),
      outcomes: ["succeeded", "partial", "failed"],
      triggers: ["manual", "scheduled", "inline"],
    },
    applied: { q: "", operation: null, outcome: null, trigger: null },
    rows: [],
    page: { page: 1, per: 20, count: 0, pages: 1 },
    elsewhere: 0,
  } as unknown as ConnectionRuns;
}

function mountDetail(operations: Row[], kinds?: Row[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const data = payload(operations, kinds);
  // ⚠ **THE KEY IS THE WHOLE REQUEST, NOT THE PROVIDER** — `runsQuery` builds
  // it from the six `BR-SHL-011` params, so a key of `(KEY, "")` seeds a cache
  // entry the page never reads and the table renders empty. Seeded here AND
  // served by the client below, because a page that re-fetches on mount would
  // otherwise draw nothing while the seed sat unused.
  queryClient.setQueryData(
    queryKeys.integrationRuns(KEY, JSON.stringify(["", {}, 1, 50, "started", "desc"])),
    data,
  );
  queryClient.setQueryData(queryKeys.regionalSettings, {
    timezone: "America/Chicago",
    date_format: "MM/DD/YYYY",
  });
  // ⚠ **THE FULL `ApiResponse` ENVELOPE, NOT `{data, status}`.** `requireData`
  // reads `etag` and `notModified` too; a half-shaped answer refetches over the
  // seed and the page renders with `payload` undefined — which is how five
  // cases failed at once with a message about `operations` rather than about
  // the fixture.
  const client = {
    get: vi.fn(async () => ({ status: 200, data, etag: null, notModified: false })),
  } as unknown as ApiClient;
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* ⚠ **MOUNTED UNDER THE REAL PATH PATTERN**, never bare. A component
            mounted with no `/:tenant/...` route reads `useParams().tenant` as
            undefined and builds every address as `//…`, which is a
            protocol-relative URL to another host and reads as a perfectly good
            string to `toContain` — the fixture failure hard-won law 2 records
            under `DEF-CWP-3925`. */}
        <MemoryRouter initialEntries={[`/${TENANT}/settings/integrations/${KEY}`]}>
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
}

function setupCard(operations: Row[]): ProviderCard {
  return {
    key: KEY,
    category: "maps",
    display_name: "Esri ArcGIS",
    summary: "Find an address and keep parcels in step.",
    fields: [{ name: "base_url", label: "Service address", kind: "url", required: true, options: [] }],
    disposition: { kind: "live", wave: null, phase: 4 },
    kicker: { direction: "in", initiative: "us" },
    auth: { mode: "we_hold_theirs", placement: "query" },
    codecs: [],
    adapter_registered: true,
    issued_keys: [],
    connection: {
      id: "c1",
      label: null,
      describe: null,
      settings: { base_url: OURS },
      environment: "production",
      cadence: "nightly",
      enabled: true,
      status: "untested",
      credential: null,
    },
    connections: [],
    vocabularies: [],
    state: "untested",
    display_state: "untested",
    operations,
  } as unknown as ProviderCard;
}

function mountSetup(operations: Row[]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  queryClient.setQueryData(queryKeys.integrations, {
    providers: [setupCard(operations)],
    counts: { providers: 1, connected: 1 },
  } as unknown as IntegrationsGrid);
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/settings/connectors/${KEY}/configure`]}>
          <Routes>
            <Route
              path="/:tenant/settings/connectors/:providerKey/configure"
              element={<ConnectorSetupPage />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const rows = () => document.querySelectorAll("tbody tr[data-operation]");
const theirs = () => document.querySelector('tbody tr[data-api-standard="no"]');

describe("CR-115-BRC05 §7 — ours and theirs in one list", () => {
  it("case 0 — the fixture can tell a drawn table from a page that rendered nothing", async () => {
    mountDetail([op("address_search"), THEIR_ROW()]);
    // Without this every absence claimed below would pass over an empty page.
    await waitFor(() => expect(rows().length).toBe(2));
    expect(screen.getByText("Address points")).toBeInTheDocument();
  });

  it("case 1 — OURS is marked standard and offers no Edit; THEIRS offers both", async () => {
    mountDetail([op("address_search"), THEIR_ROW()]);
    await waitFor(() => expect(rows().length).toBe(2));

    // R36: *"standard APis … will be availabel for enable diable but those
    // will not be editable"*. Both halves, or this proves only that the cell
    // is empty on every row.
    const ourCell = document.querySelector('tr[data-api-standard="yes"] [data-edit-cell]');
    expect(ourCell?.querySelectorAll("button").length).toBe(0);
    expect(
      document.querySelector('tr[data-api-standard="yes"] [data-api-standard-mark]'),
    ).not.toBeNull();

    const theirCell = theirs()?.querySelector("[data-edit-cell]") as HTMLElement;
    // Addressed by the accessible NAME, not a testid — see the header.
    expect(within(theirCell).getByRole("button", { name: /Edit this API/i })).toBeInTheDocument();
    expect(within(theirCell).getByRole("button", { name: /Delete this API/i })).toBeInTheDocument();
    expect(theirs()?.querySelector("[data-api-standard-mark]")).toBeNull();
  });

  it("case 2 — no database id is the visible value of anything (B14 rule 31)", async () => {
    const id = "11111111-2222-3333-4444-555555555555";
    mountDetail([op("address_search"), THEIR_ROW()]);
    await waitFor(() => expect(rows().length).toBe(2));
    // The id travels as a HANDLE — `data-api-id`, `data-enabled-cell` — and a
    // handle is not a value. What must never happen is a clerk READING it.
    expect(document.body.textContent).not.toContain(id);
  });

  it("case 3 — Working counts only ENABLED APIs, numerator AND denominator", async () => {
    // §7.5 rule 4: *"a switched-off API must not drag the count, and a
    // connector is not Not working because of one you turned off"*.
    mountDetail([
      op("address_search"),
      op("reconcile_parcels", { api_kind: "scheduled_sync" }),
      THEIR_ROW({ enabled: false, state: "not_working" }),
    ]);
    await waitFor(() => expect(rows().length).toBe(3));
    const tile = document.querySelector('[data-kpi="working"]') as HTMLElement;
    // ⚠ THE WHOLE STRING. Asserting only *2* passes on a build that filters the
    // numerator and divides by three, which reads *2 of 3* on a connector with
    // one API deliberately off — wrong in the alarming direction.
    expect(tile.textContent?.trim()).toBe("2 of 2");
  });

  it("case 4 — the set-up screen stops claiming they all share one address", async () => {
    // ⚠ **FOUND BY WALKING, NOT BY A CHECK** (hard-won laws 1 and 6). The
    // footnote *All use the address above* was unconditional; the first custom
    // API made it false while the rows directly above it printed two different
    // addresses. Both states render and both are legal strings, so nothing
    // mechanical could have seen it.
    mountSetup([op("address_search")]);
    await waitFor(() =>
      expect(document.querySelector("[data-endpoint-note]")).not.toBeNull(),
    );
    cleanup();

    mountSetup([op("address_search"), THEIR_ROW()]);
    await waitFor(() => expect(screen.getByText(THEIRS)).toBeInTheDocument());
    // ⚠ The FIRST half of this case is what stops it passing vacuously: a
    // screen that never drew the note at all would satisfy this line alone.
    expect(document.querySelector("[data-endpoint-note]")).toBeNull();
  });

  it("case 5 — the + API control is drawn only where the SERVER offers a kind", async () => {
    // §7.2's kept half: a connector whose every API is bespoke offers nothing,
    // and `BR-SHL-025`'s limit — an action that could never act for anyone is
    // not a blocked action, it is one that does not exist.
    mountDetail([op("address_search")], []);
    await waitFor(() => expect(rows().length).toBe(1));
    expect(document.querySelector("[data-add-api]")).toBeNull();
    cleanup();

    mountDetail([op("address_search")], [{ kind: "map_tiles", refusal: null }]);
    await waitFor(() => expect(rows().length).toBe(1));
    expect(document.querySelector("[data-add-api]")).not.toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-115-BRC05 §7 (the 2026-09-17 rulings verbatim) + B14 31/32/33
// generated: 2026-09-17 by the CR-115-BRC05 per-API lane
// checklist: A=n/a B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest src/features/integrations/customApis.dom.test.tsx (proved RED first, per case)
// exceptions: the `+ API` → form → server round trip is a BROWSER walk, not jsdom — 10-scripts/cr115_custom_apis_walkthrough.mjs
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
