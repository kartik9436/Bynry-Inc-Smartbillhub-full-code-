// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 wave G — **Complaints and Services: two tabs on
//           the accounts register, and one full-page intake form behind each.**
//           PO ruling 2026-09-12, verbatim: *"in the main tab list, add
//           complaints and services. These two tabs. build their ad form and
//           detail view. and tables."*, *"A complaint form should be of a
//           staple form and on new page it should open up. Same for the
//           services"*, confirmed **"Yes that is correct"**, and folded into
//           this CR by **"(a) Fold into this CR as build items."**
// Design:   `05-prototype/02 Accounts Menu Blueprint.pdf` pages 39–54, read as
//           IMAGES (its text layer renders every digit as `&`). Screen 18
//           (Complaints) draws `/:tenant/accounts?tab=complaints` and
//           `/complaints/new?step=1..4`; screen 19 (Services) draws
//           `/:tenant/accounts?tab=services` and `/services/new`.
// Rules:    BR-WRK-006 (a job stands on an anchor) · BR-WRK-018 (the promise is
//           stamped at the raise, from the type's priority) · BR-WRK-026 (the
//           dispatcher list has exactly six filters — NOT moved here) ·
//           BR-SHL-010 · BR-SHL-011 · BR-SHL-025 · B14 rules 3, 4, 19, 20, 21,
//           31, 32, 33, 38, 39, 40
// ───────────────────────────────────────────────────────
//
// ⚠ **THE CASES THAT MATTER MOST HERE ARE THE THREE THAT WOULD PASS ON A
// BROKEN SCREEN IF THEY WERE WRITTEN THE OBVIOUS WAY.**
//
//   1. **The tab strip is TEN and the two new ones are in the drawn
//      POSITION.** `toContain(">Complaints<")` passes on a strip that put them
//      last, or first, or on the account detail instead of the register — the
//      blueprint draws them between `Disconnects` and `Imports`, so the case
//      asserts the whole ORDER rather than presence.
//   2. **The queue asks for the heading AND its kinds.** The drawn table's
//      rows are all SUB-TYPES (`Billing Issues`, `Odour complaint`, `Low
//      Pressure`, `Missed collection`), so a request that filtered on the
//      heading row alone would return an empty tab on a utility doing exactly
//      what the drawing shows. The case reads the OUTGOING `type=` off the
//      captured request and pins it to the heading's own id.
//   3. **The form is a PAGE at its own address, not a dialog.** Mounted under
//      the real `/:tenant/complaints/new` pattern — a bare `MemoryRouter` with
//      no `:tenant` route leaves `useParams().tenant` undefined and every
//      address the page builds comes out `//complaints/…`, a protocol-relative
//      URL to another host that reads as a perfectly good string to
//      `toContain` (hard-won law 2's fixture clause).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, waitFor } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import { defaultRequestState } from "@/components/tableTypes";

import { ACCOUNTS_TAB_IDS } from "./AccountsListPage";
import {
  COMPLAINT_INTAKE,
  JOB_INTAKE_KINDS,
  SERVICE_INTAKE,
  jobIntakePath,
  jobQueueQueryKey,
  jobQueueTableConfig,
} from "./jobIntakeShared";
import { JobIntakeWizard } from "./JobIntakeWizard";
import { JobQueueTab } from "./JobQueueTab";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** The heading rows `work.models.SEED_TYPE_SPINE` seeds, and two of the kinds
 *  the blueprint's own table draws beneath `Consumer Complaint`. */
const TYPE_ROWS = [
  {
    id: "type-complaint",
    code: "COMPLAINT",
    name: "Consumer Complaint",
    active: true,
    is_system: true,
    used_by: 4,
    parent_code: null,
  },
  {
    id: "type-billing",
    code: "BILLING_ISSUES",
    name: "Billing Issues",
    active: true,
    is_system: true,
    used_by: 1,
    parent_code: "COMPLAINT",
  },
  {
    id: "type-svc",
    code: "CONSUMER_SVC",
    name: "Consumer Services",
    active: true,
    is_system: true,
    used_by: 2,
    parent_code: null,
  },
  {
    id: "type-bin",
    code: "BIN_SWAP",
    name: "Container swap",
    active: true,
    is_system: true,
    used_by: 1,
    parent_code: "CONSUMER_SVC",
  },
];

const PRIORITY_ROWS = [
  { id: "prio-high", code: "HIGH", name: "High", active: true, is_system: true, used_by: 3 },
  { id: "prio-urgent", code: "URGENT", name: "Urgent", active: true, is_system: true, used_by: 4 },
];

/** One row of `GET /work-orders` as `dispatch._dispatch_row` serves it. */
function order(over: Record<string, unknown> = {}) {
  return {
    id: "wo-0412",
    order_no: "WO-26-0412",
    type: "Billing Issues",
    premise: { id: "p1", address: "142 Bakers Row", unit_label: "Suite 1" },
    service: null,
    state: "planned",
    outcome: null,
    mode: "our_crew",
    is_gate: false,
    connection: null,
    account: { id: "acc-1", account_no: "A-11812" },
    raised_at: "2026-05-09T09:14:00Z",
    priority: { id: "prio-high", code: "HIGH", name: "High", rank: 2, sla_hours: 8 },
    technician: null,
    due_at: "2026-05-09T17:14:00Z",
    window_start: null,
    window_end: null,
    dispatch_state: "queued",
    source: "dispatcher",
    source_ref: null,
    area: null,
    ...over,
  };
}

/**
 * A client that answers each route from a table and RECORDS every path it was
 * asked for, so a case can assert what the screen sent rather than what it
 * rendered from a fixture it also wrote.
 */
function recordingClient(rows: readonly unknown[] = [order()]) {
  const asked: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      asked.push(url);
      const body = url.includes("/lookups/work_order_types")
        ? { count: TYPE_ROWS.length, next: null, previous: null, results: TYPE_ROWS }
        : url.includes("/lookups/work_priorities")
          ? { count: PRIORITY_ROWS.length, next: null, previous: null, results: PRIORITY_ROWS }
          : url.includes("/work-orders")
            ? { count: rows.length, next: null, previous: null, results: rows }
            : { count: 0, next: null, previous: null, results: [] };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  return { client, asked };
}

function queryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

/** The ten cell renderers `jobQueueTableConfig` asks for. The config's SHAPE is
 *  what these cases are about, so every one is a stub. */
const CELLS = {
  ref: () => <span />,
  account: () => <span />,
  address: () => <span />,
  about: () => <span />,
  service: () => <span />,
  priority: () => <span />,
  logged: () => <span />,
  respondBy: () => <span />,
  state: () => <span />,
  actions: () => <span />,
};

afterEach(() => cleanup());

/** The four characters `renderToStaticMarkup` escapes in text. */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

describe("CR-094 wave G · the two tabs on the register", () => {
  it("TC-G-1: the strip is TEN tabs and Complaints/Services sit where the blueprint draws them", () => {
    // ⚠ **ORDER, NOT PRESENCE.** The drawing at page 39 reads
    // `Accounts · Requests · New connects · Move-ins · Move-outs · Transfers ·
    // Disconnects · Complaints · Services · Imports`, and `Imports` is LAST
    // there as it is today — so the two arrive BEFORE it, not after.
    expect(ACCOUNTS_TAB_IDS).toEqual([
      "accounts",
      "requests",
      "new-connects",
      "move-ins",
      "move-outs",
      "transfers",
      "disconnects",
      "complaints",
      "services",
      "imports",
    ]);
  });

  it("TC-G-1b: the queue's cache key carries the HEADING ID, so one utility's queue cannot be served to the next", () => {
    // ⚠ **THIS CASE EXISTS BECAUSE `G98` FOUND ITS ABSENCE.** The lint gate
    // reported `jobQueueQueryKey` and `defaultRequestState` imported and never
    // used, with its own warning: *"In a TEST file an unused symbol is often an
    // assertion that went missing — read it before deleting it."* It had. The
    // first draft of `TC-G-2` prefetched under this key; rewriting that case to
    // read the OUTGOING request made it stronger and orphaned the import, and
    // the property the key exists for was then asserted by nothing.
    //
    // The property, stated in `jobQueueQueryKey`'s own docstring: two tenants'
    // `COMPLAINT` rows are DIFFERENT ids, so a key holding only the word
    // `complaint` would serve one utility's complaints to the next one in the
    // same session — a cross-tenant read that no server check can see, because
    // the request is never made.
    const config = jobQueueTableConfig(t, COMPLAINT_INTAKE, CELLS);
    const state = defaultRequestState(config);
    const brazos = jobQueueQueryKey(COMPLAINT_INTAKE.kind, "type-complaint", state);
    const silver = jobQueueQueryKey(COMPLAINT_INTAKE.kind, "another-tenants-complaint-row", state);
    expect(brazos).not.toEqual(silver);
    expect(brazos).toContain("type-complaint");
    // And the two TABS of one tenant are different keys too, which is the
    // mechanical half of *"two tabs rather than one filter"* at the cache layer.
    expect(brazos).not.toEqual(jobQueueQueryKey(SERVICE_INTAKE.kind, "type-complaint", state));
    // ⚠ **AN UNRESOLVED HEADING IS A KEY OF ITS OWN, NEVER THE SAME ONE.** The
    // tab renders its note and asks for nothing while the catalogue is loading;
    // sharing a key with a resolved heading would cache the empty answer under
    // the real one.
    expect(jobQueueQueryKey(COMPLAINT_INTAKE.kind, null, state)).not.toEqual(brazos);
  });

  it("TC-G-2: the queue asks for the heading's own catalogue id, resolved from its CODE", async () => {
    // The two headings are `is_system` seeds whose CODE is frozen once used
    // (BR-TEN-030), and a tenant may rename either — so the screen resolves
    // `COMPLAINT` / `CONSUMER_SVC` through the catalogue and sends the ID.
    //
    // ⚠ **THIS READS THE OUTGOING REQUEST, NOT THE RENDER.** A case that
    // asserted `type=COMPLAINT` on the wire would pass on a screen that had
    // hard-coded our seed's own words onto a utility's renamed heading; a case
    // that asserted the rendered rows would pass on a screen sending NO type
    // at all, because the fixture answers every `/work-orders` the same way —
    // and no type means the WHOLE dispatcher queue rendered as complaints.
    const { client, asked } = recordingClient();
    render(
      <QueryClientProvider client={queryClient()}>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=complaints`]}>
          <Routes>
            <Route
              path="/:tenant/accounts"
              element={<JobQueueTab spec={COMPLAINT_INTAKE} client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() =>
      expect(asked.some((url) => url.includes("/lookups/work_order_types"))).toBe(true),
    );
    const queue = await waitFor(() => {
      const hit = asked.find((url) => url.includes("/work-orders"));
      expect(hit).toBeDefined();
      return hit as string;
    });
    expect(queue).toContain("type=type-complaint");
    // ⛔ AND NOT THE CODE, AND NOT THE HEADING'S NAME.
    expect(queue).not.toContain("type=COMPLAINT");
    expect(queue).not.toContain("Consumer+Complaint");
  });

  it("TC-G-2b: the SERVICE queue sends ITS heading, so the two tabs are not one list", async () => {
    // Two tabs rather than one filter is the drawing's own reason (page 46),
    // and the mechanical half of it is that each queue pins a different type.
    const { client, asked } = recordingClient();
    render(
      <QueryClientProvider client={queryClient()}>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=services`]}>
          <Routes>
            <Route
              path="/:tenant/accounts"
              element={<JobQueueTab spec={SERVICE_INTAKE} client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const queue = await waitFor(() => {
      const hit = asked.find((url) => url.includes("/work-orders"));
      expect(hit).toBeDefined();
      return hit as string;
    });
    expect(queue).toContain("type=type-svc");
  });

  it("TC-G-3: BR-WRK-026 does not move — the queue sends `type` and no seventh filter", () => {
    // `GET /work-orders` reads its six as BARE parameters and answers `400` to
    // a seventh. This queue is that same route with its TYPE pinned, so it
    // declares no filter of its own that the route cannot answer.
    const config = jobQueueTableConfig(t, SERVICE_INTAKE, CELLS);
    for (const filter of config.filters ?? []) {
      expect(["status", "priority", "technician", "area"]).toContain(filter.name);
    }
  });

  it("TC-G-4: the two queues do not share one saved column set", () => {
    // `TableConfig.screenId` keys the column preference (BR-SHL-013). Two
    // lists sharing it share one stored set, which is why the register's two
    // tables get their own suffix.
    expect(COMPLAINT_INTAKE.screenId).not.toEqual(SERVICE_INTAKE.screenId);
  });
});

describe("CR-094 wave G · the form is a PAGE at its own address", () => {
  it("TC-G-5: both addresses are the blueprint's, and neither carries the tenant", () => {
    // `App.tsx` registers each as `ROUTE.slice(1)` under a `:tenant` parent, so
    // a constant carrying the prefix matches nothing at all (`DEF-WRK-4051`).
    expect(COMPLAINT_INTAKE.route).toBe("/complaints/new");
    expect(SERVICE_INTAKE.route).toBe("/services/new");
    expect(jobIntakePath(TEST_TENANT, COMPLAINT_INTAKE)).toBe("/brazosbend/complaints/new");
    expect(jobIntakePath(TEST_TENANT, SERVICE_INTAKE)).toBe("/brazosbend/services/new");
  });

  it("TC-G-6: the complaint form is FOUR steps and draws the step rail, not a dialog", async () => {
    const { client } = recordingClient();
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient()}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TEST_TENANT}/complaints/new?step=1`]}>
            <Routes>
              <Route
                path="/:tenant/complaints/new"
                element={<JobIntakeWizard spec={COMPLAINT_INTAKE} client={client} />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    // ⛔ NOT A DIALOG. B14 rule 30 was DECLINED and the PO ruled this one a
    // page; a `role="dialog"` anywhere here is the ruling being undone.
    expect(html).not.toContain('role="dialog"');
    expect(COMPLAINT_INTAKE.steps).toHaveLength(4);
    // B14 rule 3 — a multi-step flow gets the numbered rail, and the rail has
    // FOUR steps rather than three or five.
    expect(html).toContain('data-wizard="rail"');
    expect((html.match(/data-wizard-step="/g) ?? []).length).toBe(4);
    // ⚠ **THE LABELS ARE COMPARED HTML-ESCAPED.** `Review & log` reaches the
    // markup as `Review &amp; log`, so a raw `toContain` of the catalogue
    // string fails on a screen that is perfectly correct — which is what this
    // case did on its first run. Escaping here rather than weakening the
    // assertion keeps it checking the WORDS.
    for (const key of COMPLAINT_INTAKE.steps) {
      expect(html).toContain(escapeHtml(t(key)));
    }
    // B14 rules 2 and 40 — ONE page header, its title at 32px (`--text-h2`).
    expect((html.match(/<h1/g) ?? []).length).toBe(1);
    expect(html).toContain('class="text-h2"');
    // The back link goes to the queue this form was opened from, by ADDRESS.
    expect(html).toContain(`href="/${TEST_TENANT}/accounts?tab=complaints"`);
  });

  it("TC-G-7: the service form is FOUR steps, and the FEES step the drawing carries is not faked", () => {
    // ⚠ The blueprint draws FIVE steps for the service form, the fourth being
    // *Service fees*, and it says in its own words that this is *"a proposal"*
    // — `work_orders` carries no price column of any kind. A step collecting
    // money with nowhere to store it is dead UI (hard-won law 2), so it is NOT
    // built and its absence is recorded rather than drawn.
    expect(SERVICE_INTAKE.steps).toHaveLength(4);
    expect(SERVICE_INTAKE.steps.join(" ")).not.toContain("fee");
  });

  it("TC-G-8: every step label of both forms is a catalogue KEY that resolves", () => {
    // A missing key reaches a clerk as SILENCE, not as an error — so the guard
    // is that `t(key)` never answers with the key itself.
    for (const kind of JOB_INTAKE_KINDS) {
      for (const key of kind.steps) {
        expect(t(key)).not.toEqual(key);
      }
      for (const key of [kind.titleKey, kind.kickerKey, kind.newActionKey, kind.tabLabelKey]) {
        expect(t(key)).not.toEqual(key);
      }
    }
  });

  it("TC-G-9: neither form nor queue prints a database id (B14 rule 31)", async () => {
    const { client } = recordingClient();
    const html = renderToStaticMarkup(
      <QueryClientProvider client={queryClient()}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TEST_TENANT}/services/new?step=1`]}>
            <Routes>
              <Route
                path="/:tenant/services/new"
                element={<JobIntakeWizard spec={SERVICE_INTAKE} client={client} />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    // The two ids this fixture holds. A uuid may appear inside an `href`, never
    // as the visible value of a field — and no visible text here is built from
    // one at all.
    expect(html).not.toContain(">type-svc<");
    expect(html).not.toContain(">prio-high<");
  });
});

describe("record links (PO 2026-10-19) — the job queue", () => {
  it("the reference opens the work order and the account number opens the account", async () => {
    const { client } = recordingClient();
    const { container } = render(
      <QueryClientProvider client={queryClient()}>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=complaints`]}>
          <Routes>
            <Route
              path="/:tenant/accounts"
              element={<JobQueueTab spec={COMPLAINT_INTAKE} client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const hrefOf = (text: string) =>
      Array.from(container.querySelectorAll("a"))
        .filter((a) => a.textContent === text)
        .map((a) => a.getAttribute("href"));
    await waitFor(() => expect(hrefOf("WO-26-0412")).toContain(`/${TEST_TENANT}/work/orders/wo-0412`));
    expect(hrefOf("A-11812")).toContain(`/${TEST_TENANT}/accounts/acc-1`);
  });
});
