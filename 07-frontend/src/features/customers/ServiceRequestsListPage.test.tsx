// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// ⚠ **THIS FILE OPTED INTO jsdom ON 2026-08-25 (DEF-664).** Every case below
// the `REQ-01 · EMBEDDED MODE` block was written against the default `node`
// environment and `renderToStaticMarkup`, and each still runs exactly as it
// did — `renderToStaticMarkup` needs no DOM and does not care that one is
// present (verified: 10/10 unchanged cases pass under the pragma). The pragma
// is here because DEF-664's fix is only provable by CLICKING: the claim is
// *"changing the page inside the tab does not touch the query string"*, and a
// first-paint string cannot answer a question about what a second render did.
// `vite.config.ts` documents the pragma as the per-file opt-in.
//
// Change:   CR-030 W4 task 4.15 — the `TC-REQ-*` cases with a FRONTEND surface,
//           for **S83 · REQ-01**. The cases are B18 §5.3.9's, written BEFORE
//           this code existed (r11 step 2c: test code is written for the cases
//           §3 already declares, never authored to match the code).
// Rules:    BR-CUS-093 · BR-CUS-091 · **BR-CUS-106** (the AGE accent — seven
//           days, inclusive; PO 2026-08-25, closing decision D4)
// ───────────────────────────────────────────────────────
//
// ✅ **TC-REQ-14 WAS REPLACED ON 2026-08-25, NOT DELETED.**
// This block said *"TC-REQ-14 is asserted INVERTED, and that is the honest form
// of it"*: the case as B18 §5.3.9 wrote it reads *"a request aged 15 days → the
// row renders → `AGE` in the accent (D4's threshold)"*, **D4 was not ruled**,
// B19 §12.1 could only bound the threshold *between 6 and 11 days*, and
// `list_row` refused to serve `age_is_accented` so that no lane could quietly
// pick 7. The assertion was therefore that a 15-day row and a 2-day row were
// styled IDENTICALLY.
//
// **BR-CUS-106 closed D4 at SEVEN DAYS, INCLUSIVE**, so the inversion is
// obsolete — and deleting it would leave the behaviour with no guard at all.
// The case now asserts the real rule, and it asserts the **boundary**: a row at
// exactly 7 days accents. That is the half a `>`-instead-of-`>=` reading gets
// wrong, and **the eight seeded requests cannot catch it** — their ages are
// 15 · 11 · 5 · 4 · 3 · 2 · 1 · 0, so the nearest row to the line is `5d`, two
// days clear of it, and a `>` reading passes on the whole fixture.
//
// ⛔ **AND THE THRESHOLD IS NOT IN THIS FILE EITHER.** The server computes it
// once and `AgeCell` renders the flag, so the last case below feeds a 15-day
// row with `age_is_accented: false` and proves the cell draws it PLAIN. If that
// case ever goes green-by-accident the screen has grown a second threshold.
//
// TC-REQ-8 · TC-REQ-11 · TC-REQ-12 are SERVER cases (an approval threshold, a
// two-way child link, tenant isolation) with no frontend surface; they live in
// `06-backend/tests/test_cr031_service_request*.py` and are not duplicated here.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// Registers `toBeInTheDocument` and friends on vitest's `expect`, scoped to
// this file — the repo has no global setup file, deliberately.
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import {
  AgeCell,
  ServiceRequestsListPage,
  TypeCell,
  requestsTableConfig,
  DEFAULT_SEGMENT,
  segmentFromState,
  withSegment,
  serviceRequestsQueryKey,
} from "./ServiceRequestsListPage";
import { listServiceRequests } from "./serviceRequestEndpoints";
import type { ServiceRequestList, ServiceRequestRow } from "./serviceRequestEndpoints";
import { defaultRequestState } from "@/components/tableTypes";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** B19 §12.1's own eight rows, as `list_row` serves them. */
function row(over: Partial<ServiceRequestRow> = {}): ServiceRequestRow {
  return {
    id: "sr-0039",
    request_no: "SR-26-0039",
    number_absence: null,
    type: "move_in",
    type_absence: null,
    applicant: "Osei, Grace",
    // CR-068 wave B — `BR-CWP-076`'s column. B19 §12.1's own rows were taken
    // at the counter, so `walk_in` is the honest default for this fixture.
    channel: "walk_in",
    address: "3450 Oak Ridge Dr",
    address_unit: null,
    received_at: "2026-08-08T09:00:00Z",
    age_days: 15,
    // BR-CUS-106 — the SERVER's answer, carried on the fixture row the way the
    // payload carries it. 15 >= 7, so Osei's row accents.
    age_is_accented: true,
    waiting_on: "documents",
    state: "more_info",
    ...over,
  };
}

/** B19 §12.1's pager reads *"Showing 1–8 of 42 (filtered from 118)"* — the
 *  server sends ONE `count`, which is the 42. */
function payload(over: Partial<ServiceRequestList> = {}): ServiceRequestList {
  return {
    count: 42,
    next: null,
    previous: null,
    results: [
      row(),
      row({
        id: "sr-0048",
        request_no: "SR-26-0048",
        // ✅ TC for BR-CUS-091 — the list drew a DISCONNECT and the decision
        // panel said one could not exist. The PO ruled the LIST was right.
        type: "disconnect",
        applicant: "Ridge Coffee Co.",
        address: "500 Main",
        address_unit: "200",
        age_days: 3,
        age_is_accented: false,
        waiting_on: "third_party",
        state: "under_review",
      }),
      row({
        id: "sr-0044",
        request_no: "SR-26-0044",
        type: null,
        type_absence: { reason: "not_yet_classified" },
        applicant: "Alvarez, Rosa",
        address: "1408 Elm St",
        address_unit: "Unit A",
        age_days: 2,
        age_is_accented: false,
        waiting_on: null,
        state: "submitted",
      }),
    ],
    kpis: {
      open: 42,
      waiting_on_customer: 6,
      oldest_waiting: { days: 15, request_no: "SR-26-0039", waiting_on: "documents" },
      approved_not_started: 4,
      refused_this_month: 3,
      period_basis: "server_month_to_date",
    },
    segment: "open",
    ...over,
  };
}

/**
 * The rendered TEXT — every tag and attribute stripped, leaving only what a
 * person actually reads. Borrowed from `MoveInsTab.test.tsx`, which carries it
 * because a raw `html.includes(...)` cannot tell a string being SHOWN from one
 * riding in an attribute — and B14 rule 31 puts the internal value on `title`
 * precisely so it is carried and not shown.
 */
function visibleText(html: string): string {
  return html.replace(/<[^>]*>/g, " ").replace(/&[a-z]+;/g, " ").replace(/\s+/g, " ");
}

/** The EMBEDDED copy — `urlState={false}`, as `AccountsListPage` mounts it on
 *  `?tab=requests`. The surface the PO was actually looking at. */
async function renderEmbedded(body: ServiceRequestList): Promise<string> {
  return renderList(body, { embedded: true });
}

async function renderList(
  body: ServiceRequestList | "unreadable",
  opts: { embedded?: boolean } = {},
): Promise<string> {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      body === "unreadable"
        ? new Response(JSON.stringify({ detail: "boom" }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          })
        : new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // ⛔ **`DEF-CUS-5011` — THE HELPER HAS TO ASK WHAT THE SCREEN ASKS.** The
  // screen applies its drawn default (`Show: Open`) as a real filter now, so
  // its query key carries `segment: open`. A helper that prefetched under the
  // unfiltered key put the right rows in the cache under the wrong name and
  // every case below rendered the loading skeleton — four of them failed on
  // exactly that, which is the useful kind of failure: the fixture stopped
  // modelling the component the moment the component moved.
  const state = withSegment(
    defaultRequestState(
      requestsTableConfig(t, {
      request: () => <span />,
      type: () => <span />,
      received: () => <span />,
      channel: () => <span />,
      age: () => <span />,
      waitingOn: () => <span />,
        state: () => <span />,
        actions: () => <span />,
      }),
    ),
    DEFAULT_SEGMENT,
  );
  try {
    await queryClient.prefetchQuery({
      queryKey: serviceRequestsQueryKey("/requests", state),
      queryFn: () =>
        listServiceRequests(
          { segment: "open", q: "", page: state.page, per: state.per },
          client,
        ),
    });
  } catch {
    // An unreadable payload is one of the cases under test.
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={[
          opts.embedded
            ? `/${TEST_TENANT}/accounts?tab=requests`
            : `/${TEST_TENANT}/requests`,
        ]}
      >
        <ServiceRequestsListPage
          client={client}
          urlState={opts.embedded === true ? false : undefined}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("REQ-01 · the Requests list (CR-030 W4 task 4.11)", () => {
  it("TC-REQ-13 · renders the SERVED count and never a second, unserved total", async () => {
    const html = await renderList(payload());
    // The shared pager prints `1–N of 42` from the envelope's own `count`.
    expect(html).toContain("42");
    // ⚠ B19 draws *"(filtered from 118)"*. The envelope carries ONE count, so
    // an unfiltered total would have to be invented — and a fabricated figure
    // on a list header is the DEF-127 shape. It must not appear.
    expect(html).not.toContain("118");
  });

  it("TC-REQ-14 (BR-CUS-106) · AGE accents at seven days — and 7 itself accents", () => {
    // The two rows B19 §12.1 actually drew, which is what bounded the threshold
    // to 6–11 days before the PO ruled it.
    const fifteen = renderToStaticMarkup(
      <AgeCell row={row({ age_days: 15, age_is_accented: true })} t={t} />,
    );
    const five = renderToStaticMarkup(
      <AgeCell row={row({ age_days: 5, age_is_accented: false })} t={t} />,
    );
    expect(fifteen).toContain('data-age-accented="true"');
    expect(fifteen).toContain("text-accent-700");
    expect(five).toContain('data-age-accented="false"');
    expect(five).not.toContain("text-accent-700");

    // ⚠ **THE BOUNDARY, AND IT IS THE REASON THIS CASE EXISTS.** BR-CUS-106 is
    // *"7 days old or MORE"* — inclusive. Neither drawn row can prove it: the
    // nearest is `5d`, two days clear of the line, so a `>` reading renders
    // both of the rows above exactly as a `>=` reading does.
    const seven = renderToStaticMarkup(
      <AgeCell row={row({ age_days: 7, age_is_accented: true })} t={t} />,
    );
    expect(seven).toContain('data-age-accented="true"');
    expect(seven).toContain("text-accent-700");

    // ⛔ **AND THE CELL DOES NOT KNOW WHERE THE LINE IS.** A 15-day row the
    // server did NOT accent renders plain. This is what fails if anyone
    // re-derives `age_days >= 7` in the component — two thresholds, and the
    // second one drifts.
    const contradicted = renderToStaticMarkup(
      <AgeCell row={row({ age_days: 15, age_is_accented: false })} t={t} />,
    );
    expect(contradicted).not.toContain("text-accent-700");
  });

  it("the AGE cell never prints a number where the server sent none", () => {
    const html = renderToStaticMarkup(<AgeCell row={row({ age_days: null })} t={t} />);
    expect(html).toContain(t("customers.serviceRequest.list.ageUnknown"));
    expect(html).toContain('data-tracks="BR-CUS-093"');
  });

  it("BR-CUS-091 · a DISCONNECT is a lawful TYPE on this list", async () => {
    const html = await renderList(payload());
    expect(html).toContain('data-request-type="disconnect"');
  });

  it("an unclassified request says so — it is never an empty cell", () => {
    const html = renderToStaticMarkup(<TypeCell row={row({ type: null })} t={t} />);
    expect(html).toContain(t("customers.serviceRequest.type.notYetClassified"));
    // A blank would read as data we lost. B19 §12.2 badges it `NOT YET
    // CLASSIFIED` on the detail for the same reason.
    expect(html).not.toMatch(/>\s*<\/span>/);
  });

  it("BR-CUS-093 · a row that predates the ruling says why it has no number", async () => {
    const html = await renderList(
      payload({
        results: [row({ request_no: null, number_absence: { tracks: "BR-CUS-093" } })],
      }),
    );
    expect(html).toContain(t("customers.serviceRequest.number.absent"));
  });

  it("the five KPI tiles are the five B18 §5.3.1 designs, and OLDEST is not zero", async () => {
    const html = await renderList(
      payload({
        kpis: {
          open: 0,
          waiting_on_customer: 0,
          oldest_waiting: { days: null, request_no: null, waiting_on: null },
          approved_not_started: 0,
          refused_this_month: 0,
          period_basis: "server_month_to_date",
        },
      }),
    );
    // ⚠ A tenant with nothing parked has NO oldest waiting item. "0 days" is a
    // different claim from "there is none" — the AwaitsCell precedent.
    expect(html).toContain(t("customers.serviceRequest.kpi.oldestNone"));
  });

  // ⛔ **THIS CASE SAID "falls back to Open" UNTIL 2026-09-12 AND IT WAS HALF
  // OF `DEF-CUS-5011`.** An absent or unreadable segment meant `open` here
  // while the shared `FilterBar` lit its `All` chip over the same state — so
  // the screen said *nothing is filtered* and asked the server for the open
  // ones. `All` means all now, and the screen's default arrives as an APPLIED
  // filter instead. BR-SHL-011's half is untouched: an undeclared value still
  // never 4xxs and still never guesses; it simply falls back to the chip's own
  // meaning rather than to a second, invisible default.
  it("the segment rides in the URL and an unknown value falls back to All — the chip's own meaning", () => {
    const config = requestsTableConfig(t, {
      request: () => <span />,
      type: () => <span />,
      received: () => <span />,
      channel: () => <span />,
      age: () => <span />,
      waitingOn: () => <span />,
      state: () => <span />,
      actions: () => <span />,
    });
    const state = defaultRequestState(config);
    expect(segmentFromState({ ...state, filters: { segment: "closed" } })).toBe("closed");
    // BR-SHL-011: an undeclared value never 4xxs a list and never guesses.
    expect(segmentFromState({ ...state, filters: { segment: "nonsense" } })).toBe("all");
    // And an ABSENT one is `all` too — which is what the `All` chip says when
    // no filter is applied. `DEF-CUS-5011`.
    expect(segmentFromState(state)).toBe("all");
    // The drawn default is applied, not implied (B19 §12.1 selects `Open`).
    expect(segmentFromState(withSegment(state, DEFAULT_SEGMENT))).toBe("open");
  });

  /**
   * ⛔ **`DEF-CUS-5011` — THE CHIP AND THE QUERY STRING, IN ONE ASSERTION.**
   *
   * That is the defect's own prevention line, and it is the shape that matters:
   * a control's LABEL and a request PARAMETER came from two defaults that were
   * each correct and were never compared. Measured in Chromium before the fix:
   * chip `All` with `aria-pressed="true"`, footer `1–18 of 18`, and the one
   * network call `?segment=open&…` on a tenant holding 20 requests.
   *
   * A case that read only the markup, or only the URL, would have passed then
   * and would pass over the mirror fault now.
   */
  it("says on screen exactly what it asks the server for", async () => {
    const asked: string[] = [];
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async (input) => {
        asked.push(typeof input === "string" ? input : String((input as Request).url));
        return new Response(JSON.stringify(payload()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/requests`]}>
          <ServiceRequestsListPage client={client} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await screen.findByText(
      t("table.filters.chip", {
        label: t("customers.serviceRequest.list.segment"),
        value: t("customers.serviceRequest.segment.open"),
      }),
    );
    // THE OTHER HALF, in the same case: every call this screen made named the
    // segment the chip is showing.
    expect(asked.length).toBeGreaterThan(0);
    for (const url of asked) {
      expect(url).toContain("segment=open");
    }
    // And the `All` chip is NOT claiming to be the applied state. Its
    // accessible name is `Clear all` precisely BECAUSE something is applied —
    // IS-4's design, and a second reading of the same fact.
    const all = screen.getByRole("button", { name: t("table.filters.clearAll") });
    expect(all).toHaveAttribute("aria-pressed", "false");
    expect(all).toHaveTextContent(t("table.filters.all"));
    cleanup(); // this block has no afterEach; the next describe queries by text
  });

  it("DEF-1701: the segment filter is REACHABLE — the declaration finally renders a control", async () => {
    // ⚠ **THE THIRD INSTANCE, AND IT WAS A STATED ABSENCE.** This file's own
    // lifecycle trailer read *"the segment FILTER is still not reachable from
    // either copy: this screen passes no `filterBarSlot`, which predates this
    // packet and is untouched by it"* — while the file's header had ALREADY
    // ruled the shape: *"the five segments render as a filter CHIP … the URL
    // as `f.segment=` and a reload restores it (BR-SHL-011)"*. The decision was
    // made, the config declared it, and the one line that renders it was never
    // written. A comment naming a gap is a note, never a plan (hard-won law 1).
    //
    // It was found by G45's SWEEP and not by a screenshot — the PO could only
    // report the two screens they were looking at, which is DEF-1702's lesson
    // one defect earlier: a count taken by looking misses what was not opened.
    const html = await renderList(payload());
    expect(html).toContain("+ Filter");
    expect(html).toContain(t("customers.serviceRequest.list.segment"));
  });

  // ── `BR-CUS-1046` (PO 2026-09-10, EXTENDED 2026-09-12) ────────────────────
  // ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-12, AND IT WAS RIGHT AT
  // THE TIME.** It was named *"no column is sortable"* and it held the line
  // correctly for as long as the server took no `sort`: a sort control over a
  // fixed order is a live button that does nothing (hard-won law 2).
  //
  // `OQ-CUS-1790` measured that on six of this screen's eight lists and the PO
  // ruled option (c), verbatim: ***"All eight open newest-first and the six
  // gain a sort control. Largest job: six server-side sorts."*** So the
  // assertion is INVERTED rather than deleted, and the pair it now checks is
  // the pair that can rot apart: a `sortable` column with no server sort behind
  // it is the old defect, and a server sort no column offers is the mirror.
  it("declares four sortable columns, and RECEIVED is the urgency order it opened on", () => {
    const config = requestsTableConfig(t, {
      request: () => <span />,
      type: () => <span />,
      received: () => <span />,
      channel: () => <span />,
      age: () => <span />,
      waitingOn: () => <span />,
      state: () => <span />,
      actions: () => <span />,
    });
    expect(config.columns.filter((column) => column.sortable === true).map((c) => c.key)).toEqual(
      ["request_no", "applicant", "received_at", "state"],
    );
    // ⚠ **`received_at` IS THE LOAD-BEARING ONE.** This tab opened on it
    // ascending under B18 §5.2.2 — *"the oldest thing waiting is the thing to
    // look at"*. That ordering is not lost by the ruling; it becomes one click
    // that survives a refresh, which is the only reading under which
    // `BR-CUS-1046`'s second clause is true of this list.
    expect(config.defaultSort).toEqual({ sort: "created", dir: "desc" });
  });

  it("a failed read never renders the empty state — that would assert 'you have none'", async () => {
    const html = await renderList("unreadable");
    // ⚠ **WHAT THIS HARNESS CAN AND CANNOT SEE, STATED RATHER THAN ASSUMED.**
    // `renderToStaticMarkup` never resolves a promise, so a query whose
    // prefetch REJECTED still reports `pending/fetching` on first paint and the
    // screen draws its skeleton — the same measurement `AccountUsageTab.test`
    // records in its own comment. So the positive assertion (*the failure line
    // appears*) belongs to the browser walkthrough, and what is provable here
    // is the NEGATIVE one that actually matters: a list that could not be read
    // must never draw the shared empty state, because that state asserts *"you
    // have none"* about requests we simply failed to fetch.
    expect(html).not.toContain(t("customers.serviceRequest.list.emptyTitle"));
    expect(html).not.toContain(t("customers.serviceRequest.list.emptyHelper"));
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-664 · EMBEDDED MODE — the Accounts → Requests tab
// ══════════════════════════════════════════════════════════════════════════
//
// DEF-664's stated blocker, verbatim from the register: *"`ServiceRequestsList
// Page` and `AccountsListPage` BOTH serialise their table state into the SAME
// query string … so nesting one inside the other has each one's `?page=`/
// `?sort=`/`?q=` silently overwrite the other's."* It is real, and the fix does
// not need the namespacing it seemed to need: **the embedded copy does not own
// the URL at all.**
//
// So there are two claims, and each needs its own case, because a fix that
// silenced the embedded copy by silencing BOTH copies would pass the first
// case and break every shareable `/requests` link in the product:
//
//   1. embedded (`urlState={false}`) — paging and re-sizing change the LIST and
//      leave the query string byte-identical;
//   2. standalone (default) — paging still writes `?page=2`, unchanged.
//
// ⚠ **AND THE READ HALF IS TESTED TOO, WHICH THE DEFECT TEXT DOES NOT MENTION.**
// The embedded case mounts at `…/accounts?tab=requests&page=3&per=100&q=smith`
// — the outer accounts list's own params — and asserts the requests list opens
// on page 1, 50 rows, empty search. A copy that only stopped WRITING would
// still have opened the tab on page 3 of somebody else's search.
//
// ⚠ **PROVED RED FIRST (hard-won law 7).** See the lane report for the exact
// failures; both breaks were made in `ServiceRequestsListPage.tsx` and undone.
//
// ⛔ **NO SORT CASE, AND THE REASON IS THIS SCREEN'S OWN RULE.** The brief asks
// for "page/sort". `requestsTableConfig` declares NO sortable column — the
// server orders by `received_at, id` and reads no `sort` param — so DataTable
// draws no sort control and there is nothing to click. The suite exercises the
// two controls this table really has (the pager and the rows-per-page select),
// and `sort` is still covered by the byte-identical assertion: the standalone
// copy writes `sort=` into the URL and the embedded copy writes nothing at all.
describe("DEF-664 · the Requests list embedded in the Accounts tab", () => {
  afterEach(cleanup);

  /** A live read of the query string. The assertions below are about what the
   *  URL DID and DID NOT do, which no amount of reading the component's own
   *  markup can answer. */
  function UrlProbe() {
    const location = useLocation();
    return <output data-testid="url-search">{location.search}</output>;
  }

  /** 120 rows, so the pager's `Next page` is actually enabled — the eight-row
   *  fixture above is one page and its next button is correctly disabled. */
  function paged(): ServiceRequestList {
    return payload({ count: 120 });
  }

  function mount(entry: string, urlState?: boolean): void {
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async () =>
        new Response(JSON.stringify(paged()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    });
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={[entry]}>
          <UrlProbe />
          <ServiceRequestsListPage client={client} urlState={urlState} />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  const range = (from: number, to: number): string =>
    t("table.pager.range", { from, to, total: 120 });
  const search = (): string => screen.getByTestId("url-search").textContent ?? "";

  /** The accounts list's OWN params, exactly as `AccountsListPage.writeParams`
   *  leaves them when a user has paged and searched before opening the tab. */
  const OUTER = "/brazosbend/accounts?tab=requests&sort=account_no&dir=desc&page=3&per=100&q=smith";

  it("opens on page 1 of its own list — the OUTER page's ?page=/?per=/?q= never reach it", async () => {
    mount(OUTER, false);
    expect(await screen.findByText(range(1, 50))).toBeInTheDocument();
    // `?per=100` would have made this `1–100 of 120`; `?page=3` would have made
    // it `101–120 of 120`.
    expect(screen.queryByText(range(1, 100))).toBeNull();
    // And `?q=smith` is the accounts search, not this one.
    expect(
      screen.getByLabelText(t("customers.serviceRequest.list.searchPlaceholder")),
    ).toHaveValue("");
  });

  it("paging inside the tab changes the LIST and leaves the query string byte-identical", async () => {
    mount(OUTER, false);
    expect(await screen.findByText(range(1, 50))).toBeInTheDocument();
    const before = search();

    await userEvent.click(screen.getByRole("button", { name: t("table.pager.next") }));

    // The list really moved — without this the case would pass on a page whose
    // button does nothing at all.
    expect(await screen.findByText(range(51, 100))).toBeInTheDocument();
    expect(search()).toBe(before);
    expect(search()).toBe("?tab=requests&sort=account_no&dir=desc&page=3&per=100&q=smith");
  });

  it("changing rows-per-page inside the tab also leaves the query string untouched", async () => {
    mount(OUTER, false);
    expect(await screen.findByText(range(1, 50))).toBeInTheDocument();
    const before = search();

    await userEvent.selectOptions(screen.getByLabelText(t("table.pager.pageSize")), "100");

    expect(await screen.findByText(range(1, 100))).toBeInTheDocument();
    expect(search()).toBe(before);
  });

  it("suppresses the standalone page chrome — one H1 and one primary on the tab", async () => {
    mount(OUTER, false);
    expect(await screen.findByText(range(1, 50))).toBeInTheDocument();
    // The `Requests.` H1, the `SERVICE REQUESTS` kicker, the `← Dashboard` back
    // link and the `+ New request` primary are the standalone screen's; the tab
    // sits under the Accounts header and its own strip.
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
    expect(screen.queryByText(t("customers.serviceRequest.list.kicker"))).toBeNull();
    expect(
      screen.queryByRole("button", { name: t("customers.serviceRequest.action.new") }),
    ).toBeNull();
    // The KPI strip, the search, the table and the pager all stay.
    // ⚠ **SCOPED TO THE KPI TILE (DEF-1701).** This read
    // `getByText(kpi.open)` and went red with *"Found multiple elements with
    // the text: Open"* the moment this screen finally rendered its declared
    // filter panel — whose `segment` group has an `Open` checkbox. Two
    // legitimate controls carrying one English word is not an ambiguity in the
    // product, it is an under-specified query: the claim here is about the KPI
    // STRIP, so the query says so. A `getAllByText` would have hidden which of
    // the two it found, which is the DEF-182 shape.
    expect(
      document.querySelector(".kpi .k")?.textContent,
    ).toContain(t("customers.serviceRequest.kpi.open"));
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("the STANDALONE screen still writes its table state to the URL — links stay shareable", async () => {
    mount("/brazosbend/requests");
    expect(await screen.findByText(range(1, 50))).toBeInTheDocument();
    expect(search()).toBe("");

    await userEvent.click(screen.getByRole("button", { name: t("table.pager.next") }));

    expect(await screen.findByText(range(51, 100))).toBeInTheDocument();
    // BR-SHL-011's grammar, unchanged by this packet.
    expect(search()).toContain("page=2");
    // `BR-CUS-1046` — this read `sort=received_at`, which was this screen's
    // default until 2026-09-12. The default is the creation order now and
    // `received_at` is a column a clerk clicks, so the URL carries whichever of
    // them is in force. What this case is really about is that the standalone
    // copy writes its table state to the URL at all (`DEF-664`), so it asserts
    // the parameter is PRESENT and names the default.
    expect(search()).toContain("sort=created");
  });

  it("…and the standalone screen still draws its own chrome", async () => {
    mount("/brazosbend/requests");
    expect(await screen.findByText(range(1, 50))).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      t("customers.serviceRequest.list.title"),
    );
    expect(
      screen.getByRole("button", { name: t("customers.serviceRequest.action.new") }),
    ).toBeInTheDocument();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W4 task 4.15 · B18 §5.3.9's TC-REQ catalogue
// generated: 2026-08-24 by the CR-031 W4 FRONTEND lane (M3)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: vitest✔
// exceptions: E3 TC-REQ-14 is asserted INVERTED — decision D4 is unruled and
//   the honest claim today is that no row is accented. REPORTED, not passed by
//   picking 7 days · E3 TC-REQ-8 · 11 · 12 are server cases with no frontend
//   surface and are not duplicated here
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// ══════════════════════════════════════════════════════════════════════════
// THE REQUEST NUMBER IS THE DOOR — `DEF-CUS-6005`
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **REPORTED FROM THE LIVE PRODUCT.** PO, verbatim: *"in list view user
// cannot click on SR-26-0013 and open it"*. The only way into a request was a
// `RowActionLink` at the far right of a nine-column row, drawn as an unlabelled
// eye.
//
// ⚠ **THIS IS THE RULING THE PO ALREADY MADE ONE LIST OVER, NOT A NEW
// JUDGMENT.** `NewConnectsTab.tsx:492` carries it in their words — *"can you
// imporve the interaction design"* — and the note there states the remedy
// exactly: *"a clerk's hand goes to the number they came here to find … The eye
// stays: it is B14 rule 15's row action."* Move-ins and Move-outs link their
// reference too (`data-move-in-record` / `data-move-out-record`), both approved
// 2026-09-19. Re-putting it to the PO would be hard-won law 13's bug.
//
// ⚠ **TWO DOORS, ONE DESTINATION — AND THAT IS WHAT IS ASSERTED.** A case that
// only checked "the number is a link" would pass while the two doors pointed at
// different requests, which is the drift the NewConnects note names. Both are
// resolved to the SAME address and compared.
//
// ⚠ **B14 RULE 31 IS THE OTHER HALF:** the visible text stays `SR-26-0048`, the
// human reference; the id rides in the href alone and never reaches the screen.
describe("the request number opens the request (DEF-CUS-6005)", () => {
  // ⚠ **THE MARKER IS LOAD-BEARING, AND THE FIRST DRAFT OF THIS SUITE PROVED
  // IT.** Two of these cases were written as *"the html contains
  // `href=/brazosbend/requests/sr-0048`"* and BOTH PASSED against the tip's own
  // unfixed code — because the EYE already points there. They were true
  // sentences about the wrong element, and they would have reported this defect
  // fixed while the number stayed dead (law 7: ask what makes a check pass
  // WRONGLY). The reference link carries `data-request-record`, exactly as
  // Move-ins and Move-outs carry `data-move-in-record` / `data-move-out-record`,
  // so a case can name the cell it means.
  const refLink = (html: string, requestNo: string): string | null => {
    const m = html.match(
      new RegExp(`<a\\b[^>]*data-request-record="${requestNo}"[^>]*>`, "i"),
    );
    if (m === null) return null;
    const href = m[0].match(/href="([^"]*)"/);
    return href === null ? null : href[1];
  };

  it("wraps the reference itself in a link to that request", async () => {
    const html = await renderList(payload());

    // BY ADDRESS, off the REFERENCE element and not off any href on the row.
    expect(refLink(html, "SR-26-0048")).toBe(`/${TEST_TENANT}/requests/sr-0048`);
    // a bare `//requests/...` is protocol-relative — another host, and a
    // perfectly good string to `toContain` (law 2's fixture trap)
    expect(html).not.toContain('href="//requests');
    // B14 rule 31 — the WORD on screen is the human reference; the id rides in
    // the href alone
    expect(html).toContain("SR-26-0048");
    expect(visibleText(html)).not.toContain("sr-0048");
  });

  it("keeps the eye, and both doors open the SAME request", async () => {
    const html = await renderList(payload());

    // ⚠ **TWO DOORS, ONE DESTINATION.** `NewConnectsTab` names the risk this
    // guards: two ways in that drift to different addresses. Removing the eye
    // would trade one missing door for another — it is rule 15's row action and
    // where a clerk who works by the actions column looks.
    const hrefs = [...html.matchAll(/href="([^"]*\/requests\/sr-0048)"/g)].map((m) => m[1]);
    expect(hrefs.length).toBe(2);
    expect(hrefs[0]).toBe(hrefs[1]);
    expect(hrefs[0]).toBe(refLink(html, "SR-26-0048"));
  });

  it("links the reference on the EMBEDDED mount too", async () => {
    // ⚠ **THIS LIST HAS TWO MOUNTS.** `App.tsx` routes the standalone
    // `/requests`; `AccountsListPage.tsx:1526` mounts the SAME component with
    // `urlState={false}` on `?tab=requests`, which is the surface the PO was
    // looking at when they reported it. Asserted separately so "one cell serves
    // both" is measured rather than inferred.
    const html = await renderEmbedded(payload());

    expect(refLink(html, "SR-26-0048")).toBe(`/${TEST_TENANT}/requests/sr-0048`);
    expect(html).not.toContain('href="//requests');
  });

  it("does not wrap a request that HAS no number, and still leaves the eye", async () => {
    // BR-CUS-093 — a request raised before numbering carries NULL forever, and
    // `RequestNumber` states that in words. A link round a sentence is not a
    // door a clerk can read. The eye still opens it, so the row is not stranded:
    // that is the difference between withholding one affordance and removing
    // the only one.
    const html = await renderList(
      payload({
        results: [
          row({ id: "sr-none", request_no: null, number_absence: { tracks: "BR-CUS-093" } }),
        ],
      }),
    );

    expect(html).not.toContain("data-request-record");
    expect(html).toContain(`href="/${TEST_TENANT}/requests/sr-none"`);
  });
});
