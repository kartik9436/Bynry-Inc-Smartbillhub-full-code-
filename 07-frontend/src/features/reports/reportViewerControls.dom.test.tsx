// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 2 · **P2.10** — *"The control refuses. Assert
//          ZERO network calls on an inverted range."* Plus the cases that keep
//          `P2.5` (the table on `DataTable`), `P2.7` (real date fields) and
//          `P2.23` (the grain line) honest.
//          Read from `05-prototype/09 Reports Build Brief.pdf` p011 (the P2.10
//          row) and p025 (2·1b, where the message is drawn), as images.
// Rules:   CLAUDE.md hard-won law 2's MIRROR (nothing asks whether a REFUSAL is
//          still true) and its fixture clause (mount the routed component under
//          the REAL path pattern) · hard-won law 7 clause (2) — what would make
//          this check pass WRONGLY · B14 rule 7 · BR-SHL-011.
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE OUTCOME IS A NUMBER, AND THE NUMBER IS ZERO                         ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// Walked on the running product: on the billing register, typing **09/30** into
// *From* and then **09/01** into *To* sent TWO requests and collected TWO 422s,
// and the FIRST of them was fired by a *From* with no *To* at all. The screen
// replaced the report with a server error panel, twice, while the clerk was
// still typing.
//
// So the client records every request it is asked to make and the assertion is
// a count. A spy that only checked the LAST request would pass over the first
// 422, which is the one that fires before the clerk has finished.
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7 clause 2), because a check you
// cannot describe a false pass for is one you do not understand:
//
//   · **A client that is never reached at all.** If the page 403'd, crashed, or
//     rendered a permission wall, zero requests would be a true count of a
//     screen that is not working. So the FIRST case asserts a request IS made
//     for a valid window, against the same spy — a zero that cannot be told
//     from a broken screen is worth nothing.
//   · **A bare `MemoryRouter`.** `useParams().tenant` would be undefined, every
//     address would come out `//reports/…`, and the screen would render
//     something that is not this screen. The router below mounts the real
//     `/:tenant/reports/:reportKey`.
//   · **A one-directional message assertion.** A refusal that stays on screen
//     after the clerk has FIXED the range is the defect that shipped on this
//     branch today: ten browser cases passed because not one asked whether a
//     message had GONE. Every message case below asserts both directions.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

import { ReportViewerPage, reportExportFilters, reportTableConfig } from "./ReportViewerPage";
import { rangeProblem, reportRunnable } from "./ReportParameters";
import { grainFacts } from "./ReportGrainLine";
import { REPORTS_ROUTE } from "./reportsShared";

afterEach(cleanup);

const t = i18n.getFixedT("en");
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

const REGISTER = {
  key: "billing_register",
  basis: "posting",
  window: { start: "2026-09-01", end: "2026-09-30" },
  currency: "USD",
  columns: ["invoice_no", "account_no", "amount"],
  rows: [{ invoice_id: "i1", invoice_no: "BL-2609-000001", account_no: "100244", amount: "247.87" }],
  kpis: [],
  totals: { amount: "247.87" },
  unavailable: [],
  grain: "bill",
  page: { page: 1, per: 50, total: 38412, pages: 769 },
  controls: { sorts: ["invoice_no", "amount"], sort: "invoice_no", dir: "asc", searchable: true },
};

/** A client that REMEMBERS every path it was asked for. The count is the
 *  assertion; the paths are what a failure prints so it names itself. */
function recordingClient(): { client: ApiClient; reportCalls: string[] } {
  const reportCalls: string[] = [];
  const get = async (path: string, init?: { query?: Record<string, unknown> }) => {
    if (path.startsWith("/reports/")) {
      const query = new URLSearchParams();
      for (const [name, value] of Object.entries(init?.query ?? {})) {
        if (value !== undefined && value !== null && value !== "") {
          query.set(name, String(value));
        }
      }
      reportCalls.push(query.toString() === "" ? path : `${path}?${query.toString()}`);
      return { data: REGISTER, status: 200 };
    }
    if (path === "/reports") {
      return { data: { cards: [], vocabularies: { services: [], bill_types: [], purposes: [] } }, status: 200 };
    }
    if (path.startsWith("/lookups/")) {
      return { data: { results: [], count: 0 }, status: 200 };
    }
    return { data: {}, status: 200 };
  };
  const write = async () => ({ data: {}, status: 200 });
  return {
    reportCalls,
    client: {
      request: get,
      get,
      post: write,
      put: write,
      patch: write,
      delete: write,
    } as unknown as ApiClient,
  };
}

function mountViewer(client: ApiClient, search: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  // ⚠ THE REAL PATH PATTERN. A bare `MemoryRouter` gives `useParams().tenant`
  // undefined and every address this screen builds comes out `//reports/…`.
  const router = createMemoryRouter(
    [
      {
        path: `/:tenant${REPORTS_ROUTE}/:reportKey`,
        element: (
          <ReportViewerPage client={client} timeZone="America/Chicago" today="2026-09-26" />
        ),
      },
    ],
    { initialEntries: [`/${TENANT}${REPORTS_ROUTE}/billing-register${search}`] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return queryClient;
}

// ═══════════════════════════════════════════════════════════════════════════
// P2.10 — the control refuses, and the spy sees NOTHING
// ═══════════════════════════════════════════════════════════════════════════
describe("P2.10 · an inverted range is refused at the control", () => {
  it("a VALID window reaches the server — the zero below is not a broken screen", async () => {
    const { client, reportCalls } = recordingClient();
    mountViewer(client, "?f.from=2026-09-01&f.to=2026-09-30");
    await waitFor(() => expect(reportCalls.length).toBeGreaterThan(0));
    expect(reportCalls[0]).toContain("from=2026-09-01");
  });

  it("an INVERTED range sends nothing — and says so at the control", async () => {
    const { client, reportCalls } = recordingClient();
    // The screen opens on the tenant's period and that first request is real,
    // so the count is taken from here. A zero that cannot be told from a broken
    // screen is worth nothing (law 7 clause 2).
    mountViewer(client, "?f.from=2026-09-01&f.to=2026-09-30");
    await waitFor(() => expect(reportCalls.length).toBe(1));
    reportCalls.length = 0;

    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-08-01" } });
    await waitFor(() => expect(screen.getByText("To must not be before From.")).toBeTruthy());

    expect(
      reportCalls,
      `expected no report request; got ${reportCalls.length}: ${reportCalls.join(" · ")}`,
    ).toHaveLength(0);
  });

  it("a HALF window sends nothing — this is the request that used to 422 first", async () => {
    const { client, reportCalls } = recordingClient();
    // ⚠ **THIS IS NOW A URL CASE RATHER THAN A TYPING CASE, AND THAT IS THE
    // POINT.** Since the control echoes the APPLIED window, a clerk cannot
    // leave a box empty — clearing it refills from the report that ran. So the
    // half window is unreachable from the keyboard and reachable only from a
    // hand-edited or truncated link, which is exactly what a bookmark is. It
    // answers `reports.viewer.param_required` and it must not be sent.
    mountViewer(client, "?f.from=2026-09-30");
    await screen.findByLabelText("From");
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(
      reportCalls,
      `expected no report request; got ${reportCalls.length}: ${reportCalls.join(" · ")}`,
    ).toHaveLength(0);
    // …and NO refusal is shown either: a half window is not an inverted one,
    // and a red sentence under an empty box is the screen shouting.
    expect(screen.queryByText("To must not be before From.")).toBeNull();
  });

  it("and the refusal GOES AWAY when the clerk fixes it — both directions", async () => {
    const { client, reportCalls } = recordingClient();
    mountViewer(client, "?f.from=2026-09-01&f.to=2026-09-30");
    await waitFor(() => expect(reportCalls.length).toBe(1));
    reportCalls.length = 0;

    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-08-01" } });
    await waitFor(() => expect(screen.getByText("To must not be before From.")).toBeTruthy());

    // The clerk corrects it. The message must not survive the correction — a
    // refusal asserted in ONE direction only is how a defect shipped today.
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-10-31" } });
    await waitFor(() => expect(screen.queryByText("To must not be before From.")).toBeNull());
    await waitFor(() => expect(reportCalls.length).toBe(1));
  });

  it("the applied window is IN the boxes — the control states what it ran", async () => {
    // Until 2026-09-26 the As-of box read `mm/dd/yyyy` while the page head read
    // *As of 2026-09-30*: the server had defaulted the window and the control
    // said nothing about it.
    const { client } = recordingClient();
    mountViewer(client, "");
    await waitFor(() =>
      expect(screen.getByLabelText<HTMLInputElement>("From").value).toBe("2026-09-01"),
    );
    expect(screen.getByLabelText<HTMLInputElement>("To").value).toBe("2026-09-30");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// P2.5 — the table is the shared one, and it pages
// ═══════════════════════════════════════════════════════════════════════════
describe("P2.5 · 2·1 renders on the shared DataTable", () => {
  it("shows the SERVER's total, not the page's row count", async () => {
    const { client } = recordingClient();
    mountViewer(client, "?f.from=2026-09-01&f.to=2026-09-30");
    // "1–50 of 38,412" — a screen that read `rows.length` would say "1 of 1".
    await waitFor(() => expect(screen.getByText(/of 38[,.\u202f ]?412/)).toBeTruthy());
  });

  it("carries the toolbar's search box, because the report declares itself searchable", async () => {
    const { client } = recordingClient();
    mountViewer(client, "?f.from=2026-09-01&f.to=2026-09-30");
    // B14 rule 19 — the box names what it searches. It said the generic
    // "Search this list" until G43 refused it by name.
    await waitFor(() => expect(screen.getByPlaceholderText("Search this report")).toBeTruthy());
  });

  it("P2.23 · states its grain under the title, in four words", async () => {
    const { client } = recordingClient();
    mountViewer(client, "?f.from=2026-09-01&f.to=2026-09-30");
    await waitFor(() => expect(screen.getByText("One row per bill")).toBeTruthy());
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// The pure halves — provable without a browser
// ═══════════════════════════════════════════════════════════════════════════
describe("P2.7 · rangeProblem", () => {
  it("says nothing while the clerk is still typing", () => {
    expect(rangeProblem("2026-09-30", "")).toBeNull();
    expect(rangeProblem("", "2026-09-01")).toBeNull();
  });

  it("names the inverted range, and nothing else", () => {
    expect(rangeProblem("2026-09-30", "2026-09-01")).toBe("reports.param.rangeInverted");
    expect(rangeProblem("2026-09-01", "2026-09-30")).toBeNull();
    // Equal bounds are a ONE-DAY report and are perfectly lawful.
    expect(rangeProblem("2026-09-01", "2026-09-01")).toBeNull();
  });

  it("the message is six words, as B14 rule 33 caps an instruction", () => {
    expect(t("reports.param.rangeInverted").split(/\s+/).length).toBeLessThanOrEqual(6);
  });
});

describe("P2.10 · reportRunnable", () => {
  it("a window report needs both bounds, in order", () => {
    // ⚠ **EMPTY IS RUNNABLE.** The server falls back to the tenant's accounting
    // period, which is how this report has always opened from the catalogue.
    // Requiring both bounds here opened the billing register onto NOTHING —
    // found by walking it in a browser, not by any test.
    expect(reportRunnable("billing_register", {})).toBe(true);
    expect(reportRunnable("billing_register", { from: "2026-09-01" })).toBe(false);
    expect(reportRunnable("billing_register", { to: "2026-09-30" })).toBe(false);
    expect(reportRunnable("billing_register", { from: "2026-09-30", to: "2026-09-01" })).toBe(false);
    expect(reportRunnable("billing_register", { from: "2026-09-01", to: "2026-09-30" })).toBe(true);
  });

  it("a POSITION report needs neither — the server uses the tenant's period end", () => {
    // The ageing is a position at a date, not a flow over a window, and it has
    // always opened with no parameters at all.
    expect(reportRunnable("ar_aging", {})).toBe(true);
  });
});

describe("§8.2 · the export holds every row, never the page", () => {
  it("drops page and per and keeps every filter", () => {
    expect(
      reportExportFilters({
        from: "2026-09-01",
        to: "2026-09-30",
        q: "ruiz",
        class: "RES",
        sort: "amount",
        dir: "desc",
        page: "3",
        per: "50",
      }),
    ).toEqual({
      from: "2026-09-01",
      to: "2026-09-30",
      q: "ruiz",
      class: "RES",
      sort: "amount",
      dir: "desc",
    });
  });
});

describe("P2.2 · a sort caret is the SERVER's answer", () => {
  it("only the declared columns are sortable, and none is when nothing is declared", () => {
    const withControls = reportTableConfig(
      REGISTER as never,
      "billing_register",
      t as never,
      () => null,
    );
    expect(withControls.columns.find((c) => c.key === "amount")?.sortable).toBe(true);
    expect(withControls.columns.find((c) => c.key === "account_no")?.sortable).toBe(false);

    const bare = reportTableConfig(
      { ...REGISTER, controls: undefined } as never,
      "billing_register",
      t as never,
      () => null,
    );
    expect(bare.columns.every((c) => c.sortable !== true)).toBe(true);
    // …and no search box either.
    expect(bare.searchFields).toBeUndefined();
  });

  it("the stored column choice is per REPORT, so two reports cannot share a shape", () => {
    expect(reportTableConfig(undefined, "ar_aging", t as never, () => null).screenId).toBe(
      "S46.ar_aging",
    );
    expect(
      reportTableConfig(undefined, "billing_register", t as never, () => null).screenId,
    ).toBe("S46.billing_register");
  });
});

describe("P2.23 · grainFacts", () => {
  it("drops the empty ones and never states the same fact twice", () => {
    expect(grainFacts(["One row per account", null, undefined, ""])).toEqual([
      "One row per account",
    ]);
    expect(grainFacts(["One row per bill", "One row per bill"])).toEqual(["One row per bill"]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P2.10 (05-prototype/09 Reports Build Brief.pdf p011 · p025, read as RENDERED IMAGES per B14 rule 42)
// screens: S46 (2·1)
// generated: 2026-09-26 by lane REP-P2-VIEWER
// gates: RED PROVED FIRST — see the lane report for the verbatim failures on the tip
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
