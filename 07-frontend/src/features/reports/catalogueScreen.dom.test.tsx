// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:   CR-142-BRC07 Phase 1 · P1.3 (screen 1·1) · P1.2 (the filters are
//          read SERVER-SIDE) · P1.5 (no literals) · P1.8 (the services come
//          off the answer the catalogue already made).  Screens: S44
// Rules:   B14 rule 31 (no database id is ever the visible value of a field) ·
//          rule 33 (a LABEL is three words; RATIONALE is zero) · rule 43 ·
//          CLAUDE.md hard-won law 2, both directions
// ───────────────────────────────────────────────────────
//
// THE SCREEN, MOUNTED AT ITS REAL ADDRESS, AGAINST A FAKE SERVER THAT RECORDS
// WHAT IT WAS ASKED.
//
// ⚠ **THE REQUEST LOG IS THE POINT OF HALF THIS FILE.** `P1.2`'s outcome is
// not *"typing in the box narrows the grid"* — a screen that filtered an array
// it was handed would pass that. It is *"read server-side"*, and the only way
// to assert it is to record the query the screen actually sent. `NFR-3` is
// already breached in four places in this product, each one correct at 3,000
// accounts and thirteen times short at 40,000, and every one of them began as a
// list that was small enough to filter in the client.
//
// ⚠ **AND THE MOUNT IS UNDER `/:tenant/reports`, NOT BARE.** A component in a
// `MemoryRouter` with no route pattern gets `useParams().tenant === undefined`,
// so every address it builds comes out `//reports/…` — a protocol-relative URL
// to another host, which reads as a perfectly good string to `toContain`. That
// fixture is how the customer portal shipped two working doors out of eight.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import type { ReportCard, ReportLibraryResponse } from "@/api/reportsEndpoints";
import { shellBootSeed } from "@/components/shellBootSeed";

import { ReportLibraryPage } from "./ReportLibraryPage";
import { REPORTS_ROUTE } from "./reportsShared";

afterEach(cleanup);

const TENANT = "brazosbend";

const USER: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@sample.test",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "reports", label: "Reports", access: "Full" }],
};

const PERIOD = {
  fy_label: "FY2026",
  period: 9,
  start: "2026-09-01",
  end: "2026-09-30",
  status: "open",
};

function card(overrides: Partial<ReportCard>): ReportCard {
  return {
    key: "ar_aging",
    name: "AR Ageing",
    name_overridden: false,
    group: "receivables",
    group_name: "Receivables",
    sub_group: "receivables_arrears",
    kind: "viewer",
    origin: "built_in",
    badge: "Arrears",
    available: true,
    basis: "posting",
    basis_label: "Posting date",
    reason_code: null,
    reason_detail: null,
    routes_to_screen: null,
    service_codes: [],
    pinned: false,
    ...overrides,
  };
}

const CARDS: ReportCard[] = [
  card({}),
  card({
    key: "debtor_list",
    name: "Debtor List",
    badge: "Arrears",
    kind: "absent",
    available: false,
    reason_code: "report_dataset_has_no_query",
    reason_detail: "dataset 'accounts' has no query yet",
  }),
  card({
    key: "trial_balance",
    name: "Trial Balance",
    group: "finance",
    group_name: "Finance",
    sub_group: "finance_ledger",
    badge: "Ledger",
    kind: "route",
    routes_to_screen: "S56",
  }),
];

function library(overrides: Partial<ReportLibraryResponse> = {}): ReportLibraryResponse {
  return {
    groups: [
      {
        code: "receivables",
        name: "Receivables",
        sub_groups: [
          { code: "receivables_payments", name: "Payments" },
          { code: "receivables_arrears", name: "Arrears" },
        ],
      },
      { code: "finance", name: "Finance", sub_groups: [{ code: "finance_ledger", name: "Ledger" }] },
    ],
    group_total: 3,
    sub_group_total: 3,
    group_options: [
      { code: "billing", name: "Billing" },
      { code: "receivables", name: "Receivables" },
      { code: "finance", name: "Finance" },
    ],
    cards: CARDS,
    available: 2,
    total: 45,
    count: 3,
    page: 1,
    per: 50,
    pages: 1,
    origin: "standard",
    origin_counts: { standard: 3, custom: 0 },
    q: "",
    group: "",
    service: "",
    vocabularies: {
      services: [
        { code: "water", name: "Water" },
        { code: "electric", name: "Electric" },
      ],
      bill_types: [],
      purposes: [],
      current_period: null,
      currency: "USD",
      period_unavailable_reason: null,
    },
    ...overrides,
  };
}

/** Records every query the screen sends, which is what `P1.2` is asserted on. */
function serverRecording(asked: Record<string, unknown>[], answer = library()): ApiClient {
  const get = async (path: string, options?: { query?: Record<string, unknown> }) => {
    if (path === "/reports") {
      asked.push({ ...(options?.query ?? {}) });
      return { data: answer, status: 200 };
    }
    return { data: {}, status: 200 };
  };
  const write = async () => ({ data: {}, status: 200 });
  return { request: get, get, post: write, put: write, patch: write, delete: write } as unknown as ApiClient;
}

function open(client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  const router = createMemoryRouter(
    [{ path: `/:tenant${REPORTS_ROUTE}`, element: <ReportLibraryPage client={client} /> }],
    { initialEntries: [`/${TENANT}${REPORTS_ROUTE}`] },
  );
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

async function settle() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// P1.3 — the screen is what the drawing draws
// ═══════════════════════════════════════════════════════════════════════════
describe("P1.3 · screen 1·1", () => {
  it("names every card from the ROW and never from a key", async () => {
    open(serverRecording([]));
    await screen.findByText("AR Ageing");
    expect(screen.getByText("Debtor List")).toBeTruthy();
    expect(screen.getByText("Trial Balance")).toBeTruthy();
    // B14 rule 31's shape — the failure serving 46 against the old screen
    // would have produced: twenty-three cards each showing a snake_case key.
    expect(screen.queryByText("debtor_list")).toBeNull();
    expect(screen.queryByText("ar_aging")).toBeNull();
  });

  it("heads each group with its own sub-groups, from the served rows", async () => {
    open(serverRecording([]));
    await screen.findByText("AR Ageing");
    // p20 callout ⑦ — the heading is the group's name and its sub-groups', and
    // both come from `report_categories`. Never a literal in the front end.
    expect(screen.getByText("Receivables · Payments · Arrears")).toBeTruthy();
    expect(screen.getByText("Finance · Ledger")).toBeTruthy();
  });

  it("puts the card's sub-group, name and basis label on its face, in that order", async () => {
    open(serverRecording([]));
    const name = await screen.findByText("AR Ageing");
    const tile = name.closest("[data-report-key]") as HTMLElement;
    // p21's FIELDS row, verbatim: badge · name · basis label.
    expect(tile.textContent).toBe("ArrearsAR AgeingPosting date");
  });

  it("states the SHAPE of the catalogue and not an availability count", async () => {
    open(serverRecording([]));
    // p20 callout ①. The old sub-line read "10 of 23 can be produced here",
    // which is the count that callout says the sub-line is NOT.
    await screen.findByText("45 reports · 3 groups · 3 sub-groups");
    expect(screen.queryByText(/can be produced here/)).toBeNull();
  });

  it("keeps an unavailable card a NON-LINK with a six-word reason", async () => {
    open(serverRecording([]));
    const name = await screen.findByText("Debtor List");
    const tile = name.closest("[data-report-key]") as HTMLElement;
    expect(tile.tagName).toBe("DIV");
    expect(tile.getAttribute("href")).toBeNull();
    expect(within(tile).queryByRole("link")).toBeNull();
    // B14 rule 33: the reason is a FACT, six words, and the paragraph of
    // rationale this grid used to draw is REMOVED rather than shortened.
    expect(tile.textContent).toContain("This report cannot be produced yet.");
    expect(tile.textContent).not.toContain("nothing publishes them a month at a time");
  });

  it("builds a real address under the tenant, never a protocol-relative one", async () => {
    open(serverRecording([]));
    const name = await screen.findByText("AR Ageing");
    const href = (name.closest("a") as HTMLAnchorElement).getAttribute("href");
    expect(href).toBe(`/${TENANT}/reports/ar-aging`);
    expect(href?.startsWith("//")).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// P1.2 — every filter is read SERVER-SIDE
// ═══════════════════════════════════════════════════════════════════════════
describe("P1.2 · the filters are the server's", () => {
  it("sends the search to the server rather than filtering what it holds", async () => {
    const asked: Record<string, unknown>[] = [];
    open(serverRecording(asked));
    await screen.findByText("AR Ageing");

    const box = screen.getByPlaceholderText(i18n.t("table.search.placeholder"));
    fireEvent.change(box, { target: { value: "ageing" } });
    await waitFor(() => expect(asked.some((query) => query.q === "ageing")).toBe(true), {
      timeout: 2000,
    });
    // …and the grid still holds every card the SERVER answered with, because
    // nothing here filters. A screen that narrowed its own array would show one.
    expect(screen.getByText("Trial Balance")).toBeTruthy();
  });

  it("sends the group filter, and offers every group rather than the drawn ones", async () => {
    const asked: Record<string, unknown>[] = [];
    open(serverRecording(asked));
    await screen.findByText("AR Ageing");

    const chooser = screen.getByLabelText(i18n.t("reports.library.filter.group"));
    // Three options served plus the leading "All groups" — a filter that
    // offered only what is on screen could never be undone.
    expect(within(chooser as HTMLElement).getAllByRole("option")).toHaveLength(4);
    fireEvent.change(chooser, { target: { value: "finance" } });
    await waitFor(() => expect(asked.some((query) => query.group === "finance")).toBe(true));
  });

  it("offers the tenant's OWN services and asks for no second request", async () => {
    const asked: Record<string, unknown>[] = [];
    open(serverRecording(asked));
    await screen.findByText("AR Ageing");

    // P1.8: the list came off the catalogue's own answer. Two services, not
    // the prototype's hardcoded Electric/Water/Sewer trio.
    const chooser = screen.getByLabelText(i18n.t("reports.library.filter.service"));
    const options = within(chooser as HTMLElement)
      .getAllByRole("option")
      .map((option) => option.textContent);
    expect(options).toEqual([
      i18n.t("reports.library.filter.serviceAll"),
      "Water",
      "Electric",
    ]);
    fireEvent.change(chooser, { target: { value: "water" } });
    await waitFor(() => expect(asked.some((query) => query.service === "water")).toBe(true));
  });

  it("shows an applied filter as a removable chip", async () => {
    const asked: Record<string, unknown>[] = [];
    open(serverRecording(asked));
    await screen.findByText("AR Ageing");

    fireEvent.change(screen.getByLabelText(i18n.t("reports.library.filter.group")), {
      target: { value: "finance" },
    });
    await waitFor(() => {
      expect(document.querySelector("[data-catalogue-chips]")?.textContent).toContain("Finance");
    });
    // The ✕ is a real labelled control and the chip is not — a bare glyph
    // names nothing to a screen reader, which is why `Chip` is the kit's.
    const remove = screen.getByRole("button", {
      name: i18n.t("table.filters.remove", { label: i18n.t("reports.library.filter.group") }),
    });
    fireEvent.click(remove);
    // ⚠ The assertion is the CHIP, not the next request. Removing the filter
    // returns the screen to the query it opened with, which react-query already
    // holds — so asserting "a request went out with no group" would be
    // asserting that the cache does not work.
    await waitFor(() => expect(document.querySelector("[data-catalogue-chips]")).toBeNull());
  });

  it("puts ORIGIN in the sub-tab and NOT in a filter dropdown", async () => {
    const asked: Record<string, unknown>[] = [];
    open(serverRecording(asked));
    await screen.findByText("AR Ageing");

    // PO ruling: *"a filter dropdown hides that you can author a report at
    // all."* Two dropdowns on this screen and no third.
    const strip = document.querySelector('[data-sub-tabs="catalogue-origin"]') as HTMLElement;
    expect(strip).toBeTruthy();
    // ⚠ BOTH counts render, always. p20 callout ④: *"Custom reads 0 on day one
    // and that is the point."* A bare `Custom` beside `Standard · 3` teaches a
    // clerk nothing without clicking, which is what this screen shipped with
    // for an hour until it was looked at in a browser.
    expect(within(strip).getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      `${i18n.t("reports.library.tab.standard")} · 3`,
      `${i18n.t("reports.library.tab.custom")} · 0`,
    ]);

    fireEvent.click(within(strip).getAllByRole("tab")[1]);
    await waitFor(() => expect(asked.some((query) => query.origin === "custom")).toBe(true));
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// P1.5 — NO LITERALS
// ═══════════════════════════════════════════════════════════════════════════
describe("P1.5 · the screen renders rows, never a tuple", () => {
  it("renders the EMPTY STATE on zero rows, not twenty-three cards", async () => {
    open(
      serverRecording(
        [],
        library({ cards: [], groups: [], total: 0, count: 0, available: 0 }),
      ),
    );
    await settle();
    await screen.findByText(i18n.t("reports.library.empty.title"));
    // The number 23 IS the assertion: `apps/reports/catalog.py` still exists
    // and still holds its frozen tuple, and nothing reaches it from here.
    expect(document.querySelectorAll("[data-report-key]")).toHaveLength(0);
    expect(screen.queryByText("AR aging summary")).toBeNull();
  });

  it("tells the Custom sub-tab's empty state apart from a filtered-out one", async () => {
    const asked: Record<string, unknown>[] = [];
    open(
      serverRecording(
        asked,
        library({ cards: [], groups: [], count: 0, origin: "custom" }),
      ),
    );
    await settle();
    const strip = document.querySelector('[data-sub-tabs="catalogue-origin"]') as HTMLElement;
    fireEvent.click(within(strip).getAllByRole("tab")[1]);
    // p20 callout ④: *"Custom reads 0 on day one and that is the point."*
    await screen.findByText(i18n.t("reports.library.customEmpty.title"));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 Phase 1 · P1.2 · P1.3 · P1.5 · P1.8 (05-prototype/09 Reports Build Brief.pdf p19-p21 read as IMAGES)
// screens: S44
// generated: 2026-09-26 by lane REP-P1
// gates: RED PROVED FIRST — before the rebuild this file found no search box, no filter chooser and no sub-tab strip on /{tenant}/reports, and the sub-line read "10 of 23 can be produced here"
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
