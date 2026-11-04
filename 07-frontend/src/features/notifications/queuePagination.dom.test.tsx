// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-NOT-5746, 2026-09-18 — Settings → Notifications → Messages asked
//          `GET /outbound` for ONE page of fifty and then sliced those fifty
//          again in the browser. `GET /outbound` has paged in the DATABASE
//          since it was written, so rows 51+ of a queue were unreachable and
//          the footer read *"1–50 of 50"* whatever the queue held.
// Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
//          B14 rule 16 (a pagination footer on every list table) ·
//          CLAUDE.md hard-won law 7 (prove it RED first, and ask what would
//          make the check pass wrongly) · hard-won law 2's fixture clause
//          (mount under the REAL path pattern)
// Screens: SET-12 → Messages
// ───────────────────────────────────────────────────────
//
// ⚠ **A TEST THAT COUNTS RENDERED ROWS CANNOT TELL A SERVER PAGE FROM A CLIENT
// SLICE — IT PASSES EITHER WAY, AND THAT IS HOW THIS DEFECT LIVED FOR A MONTH.**
// Fifty rows and a footer is what both versions of this screen draw. So every
// case below asserts the REQUEST: which query went out, how many went out, and
// what the footer says about rows the browser is NOT holding.
//
// The three that go RED on the old code, and what each one caught:
//
//   1. **the first request carries `page` and `per`.** The old one sent `per`
//      alone, so the server's page one was the only page that existed.
//   2. **`›` issues a SECOND request, with `page=2`.** The old one re-sliced
//      the fifty rows in hand; the second page of a fifty-row array is empty,
//      so the click reached nothing and asked nothing.
//   3. **fifty rows over a count of 4,000 print *"1–50 of 4000"*.** The old
//      footer counted the array it was handed and printed *"1–50 of 50"* — a
//      list that looks complete and is not, which `NFR-3`'s own note calls a
//      worse defect than a slow one.
//
// ⚠ **WHAT WOULD MAKE THIS SUITE PASS WRONGLY.** A stub that answers the same
// body for every query would satisfy case 2's row assertion while the screen
// asked for nothing — so case 2 asserts the recorded QUERY, not the rows, and
// the stub answers a different page from a 4,000-row spine so the rows can
// disagree with it if the wiring is wrong.
//
// ⚠ **WHAT THIS SUITE CANNOT SEE.** jsdom does no layout and no gate here reads
// rendered output, so *does the footer look right* is not provable here.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import type { OutboundRow } from "@/api/endpoints";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { MESSAGES_SUB, NotificationsTab } from "./SettingsNotificationsTab";

afterEach(cleanup);

/** The queue a utility of this size actually has. Four thousand is `T5`'s shape
 *  rather than a round number: at 40,000 accounts a monthly bill run alone puts
 *  tens of thousands of messages through this table in a day. */
const QUEUED = 4_000;

/** The real address, so `useParams()` resolves the way the product resolves it. */
const MESSAGES_PATH = "/riverside/settings/notifications/messages";

/**
 * ⚠ **EVERY CASE CARRIES AN EXPLICIT TIMEOUT, AND THAT IS NOT PADDING.** Each one
 * mounts the WHOLE dispatch tab over a fifty-row table and then drives it, and
 * vitest's 5 s default is comfortable alone and not comfortable beside five
 * other suites on a shared box: the two interaction cases passed on their own
 * and then timed out in a six-file run, which is a test reporting a fault nobody
 * caused. A flaky red is worse than no red — it teaches the next reader to
 * dismiss this file (hard-won law 7). `delay: null` on `userEvent` removes the
 * per-event pause for the same reason.
 */
const CASE_MS = 120_000;

interface Recorded {
  path: string;
  query: Record<string, unknown>;
}

function aRow(index: number): OutboundRow {
  return {
    id: `msg-${index}`,
    source_type: "invoice",
    source_id: `inv-${index}`,
    account_id: null,
    channel: "email",
    copy_no: 0,
    status: "failed",
    held: false,
    held_reason: null,
    attempts: 3,
    last_error: "provider timeout",
    batch_id: null,
    provider_reference: null,
    template_code: "bill_residential",
    template_version: 2,
    template_language: "en",
    // ⚠ The recipient is what the row is IDENTIFIED BY in these assertions —
    // B14 rule 31: the id is never the visible value of a field, so a test that
    // looked for `msg-51` would be asserting something no clerk can see.
    recipient_address: `row-${index}@example.test`,
    unavailable_reason: null,
    queued_at: "2026-09-18T10:00:00Z",
    dispatch_not_before: null,
    last_attempt_at: null,
    sent_at: null,
    returned_at: null,
  } as OutboundRow;
}

/** The whole queue, server-side. Nothing hands this array to the browser. */
const SPINE: OutboundRow[] = Array.from({ length: QUEUED }, (_, i) => aRow(i + 1));

/**
 * A server that pages the way `apps/notifications/api.outbound` pages: it reads
 * `page` and `per` off the query, slices IN THE DATABASE, and answers the DRF
 * envelope with the true `count` beside the window.
 */
function pagingClient(calls: Recorded[]): ApiClient {
  return {
    get: async <T,>(path: string, options?: { query?: Record<string, unknown> }) => {
      const query = options?.query ?? {};
      calls.push({ path, query });
      if (path === "/outbound/summary") {
        return {
          data: {
            counts: [],
            totals: { failed: QUEUED },
            held: 0,
            returned: 0,
            retry_exhausted: 0,
            queued_by_channel: {},
            unpopulated_statuses: [],
            problems: [],
          } as T,
        };
      }
      if (path === "/outbound") {
        const per = Number(query.per ?? 50);
        const page = Number(query.page ?? 1);
        const from = (page - 1) * per;
        return {
          data: {
            count: SPINE.length,
            next: null,
            previous: null,
            results: SPINE.slice(from, from + per),
            vocabulary: {
              statuses: [],
              channels: [],
              source_types: [],
              unpopulated_statuses: [],
              disclosable_channels: [],
            },
          } as T,
        };
      }
      // The config cards each own their failure branch, so refusing them still
      // leaves the queue — this suite's subject — on the screen.
      throw new Error(`not part of this case: ${path}`);
    },
  } as unknown as ApiClient;
}

function mount(calls: Recorded[]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
          {/* ⚠ THE REAL PATH PATTERN, never a bare `MemoryRouter`. A component
              mounted with no matching route has `useParams().tenant`
              undefined, and every address it builds then comes out
              `//settings/…` — which still satisfies `toContain`. That fixture
              is how a whole page of dead portal links passed its own tests. */}
          <MemoryRouter initialEntries={[MESSAGES_PATH]}>
            <Routes>
              <Route
                path="/:tenant/settings/:tab/:sub"
                element={
                  <NotificationsTab
                    readOnly={false}
                    client={pagingClient(calls)}
                    sub={MESSAGES_SUB}
                    onOpenRule={() => undefined}
                  />
                }
              />
            </Routes>
          </MemoryRouter>
        </TenantRegionalProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const queueCalls = (calls: Recorded[]): Recorded[] => calls.filter((c) => c.path === "/outbound");

describe("DEF-NOT-5746 · the dispatch queue pages through the SERVER", () => {
  it("asks for a page and a size — not for fifty rows and nothing else", async () => {
    const calls: Recorded[] = [];
    mount(calls);
    await screen.findByText("row-1@example.test");

    // ⚠ RED ON THE OLD CODE: it called `getOutbound({ per: 50 })`, so `page`
    // was absent from the query and the server's page one was the only page
    // this screen could ever see.
    expect(queueCalls(calls)).toHaveLength(1);
    expect(queueCalls(calls)[0].query.page).toBe(1);
    expect(queueCalls(calls)[0].query.per).toBe(50);
  }, CASE_MS);

  it("counts the WHOLE queue in the footer, not the page it was handed", async () => {
    const calls: Recorded[] = [];
    mount(calls);
    await screen.findByText("row-1@example.test");

    // ⚠ RED ON THE OLD CODE: `total={props.rows.length}` made this "1–50 of
    // 50" — a list that reads as complete over 3,950 messages it is not
    // showing. NFR-3: never truncate silently.
    expect(screen.getByText("1–50 of 4000")).toBeInTheDocument();
    expect(screen.getByText("Page 1 of 80")).toBeInTheDocument();
  }, CASE_MS);

  it("turning a page is a REQUEST, and it reaches a row the browser never held", async () => {
    const user = userEvent.setup({ delay: null });
    const calls: Recorded[] = [];
    mount(calls);
    await screen.findByText("row-1@example.test");

    await user.click(screen.getByRole("button", { name: "Next page" }));

    // ⚠ THE ASSERTION THAT CANNOT PASS ON A CLIENT SLICE. The old table had
    // fifty rows in memory; page two of fifty rows is empty, and no request
    // went out at all. Asserting the recorded QUERY — rather than the rows —
    // is what tells the two apart (hard-won law 7).
    await waitFor(() => {
      expect(queueCalls(calls)).toHaveLength(2);
    });
    expect(queueCalls(calls)[1].query.page).toBe(2);
    expect(queueCalls(calls)[1].query.per).toBe(50);

    // …and row 51, which was never in the browser, is on the screen.
    expect(await screen.findByText("row-51@example.test")).toBeInTheDocument();
    expect(screen.queryByText("row-1@example.test")).not.toBeInTheDocument();
    expect(screen.getByText("51–100 of 4000")).toBeInTheDocument();
  }, CASE_MS);

  it("a bigger page size is a request too, and it returns to page one", async () => {
    const user = userEvent.setup({ delay: null });
    const calls: Recorded[] = [];
    mount(calls);
    await screen.findByText("row-1@example.test");

    await user.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => expect(queueCalls(calls)).toHaveLength(2));

    await user.selectOptions(screen.getByRole("combobox"), "200");

    await waitFor(() => {
      expect(queueCalls(calls)).toHaveLength(3);
    });
    expect(queueCalls(calls)[2].query.per).toBe(200);
    // A page number that survives a size change points at rows that are no
    // longer there; the footer would otherwise say "401–600 of 4000" over the
    // first two hundred.
    expect(queueCalls(calls)[2].query.page).toBe(1);
    expect(await screen.findByText("1–200 of 4000")).toBeInTheDocument();
  }, CASE_MS);
});
