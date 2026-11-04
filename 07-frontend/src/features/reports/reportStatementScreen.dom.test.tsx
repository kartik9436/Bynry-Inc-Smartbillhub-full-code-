// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-REP-7072 (opening the editor cut the statement from SEVEN
//          columns to ONE) · DEF-REP-7052 (no statement named what it is about)
//          · DEF-REP-7053 (the Download button was never drawn).
// Screens: 2·1 Report viewer at `/{tenant}/reports/statement`, and 2·2 beside it.
// Rules:   CLAUDE.md hard-won law 2 and its MIRROR · law 7 clause 2 (*what
//          would make this pass WRONGLY*) · B14 rule 31 (no database id is a
//          visible value) · rule 33 · rule 43 · hard rule 8.
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  A JOURNEY: PRESS A CONTROL, THEN ASK WHETHER THE SCREEN IS STILL ITSELF ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// Every defect found on this screen this week — a dead chooser, a closing
// panel, collapsing columns — is INVISIBLE to a fixture that mounts a component
// directly, because each of them lives where two correct halves meet. So this
// file drives `ReportViewerPage` through its real URL, presses **Edit**, and
// then counts the table's headers again.
//
// ⚠ **THE STUB SERVER IMPLEMENTS THE RUNNER'S OWN NARROWING RULE, TRANSCRIBED**
// — a `columns` request is narrowed against the report's `column_choices` where
// it declares them and against the DATASET's attributes where it does not. That
// is what makes this able to go red: deleting `column_choices` from the fixture
// reproduces the defect exactly, and the failure it prints is quoted in the
// lane report — `expected 7 headers, got 1`.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 clause 2):
//   · **A bare `MemoryRouter`.** `useParams().tenant` would be undefined and
//     every address this page builds would come out `//reports/…`, which reads
//     as a perfectly good string. The router below mounts the REAL pattern,
//     built from `REPORTS_ROUTE` rather than from a literal repeated here.
//   · **Counting headers before the panel has opened.** The count is taken
//     AFTER the editor's own section has rendered, so a still-closed panel
//     cannot be mistaken for an unchanged table.
//   · **Asserting the head's presence only.** A head carrying the account's
//     uuid would pass that. The id is asserted ABSENT from `textContent`.
//   · **Asserting the Download button renders.** A drawn button over a 404 is
//     the defect one door along, so the resource name the control POSTs is
//     asserted too, and the HTTP proof is
//     `10-scripts/rep_stmt_screen_walkthrough.mjs`, against a real file.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

import { ReportViewerPage } from "./ReportViewerPage";
import { ReportSubjectHead, subjectHeadParts } from "./ReportSubjectHead";
import { ReportEditorPage } from "./ReportEditorPage";
import { REPORTS_ROUTE, REPORT_EDITOR_ROUTE_PATTERN } from "./reportsShared";

afterEach(cleanup);

const TENANT = "brazosbend";
/** A real uuid shape, so rule 31 is tested against the thing rule 31 is about. */
const ACCOUNT_ID = "01a0d23a-3a8e-7caa-9803-170d8fcfaa5c";

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

/** The seven `apps/reports/statement.STATEMENT_COLUMNS` serves. */
const STATEMENT_COLUMNS = [
  "entry_date",
  "type",
  "reference",
  "description",
  "charge",
  "payment",
  "running_balance",
];

/** The five attributes `apps/reports/datasets.JOURNAL_LINES` declares. The two
 *  lists intersect in `reference` and in nothing else — that single overlap IS
 *  the defect, and it is written down here so the premise cannot rot silently. */
const JOURNAL_LINES_ATTRIBUTES = [
  "posted_on",
  "account_code",
  "account_name",
  "reference",
  "narrative",
];

const JOURNAL_LINES = {
  code: "journal_lines",
  owner_module: "ledger",
  grain: "one journal line",
  columns: JOURNAL_LINES_ATTRIBUTES.map((name) => ({
    name,
    type: "text",
    unit: null,
    unit_from: null,
    money_basis: null,
    scale: null,
  })),
  measures: [
    { name: "debit", aggregation: "sum", additivity: "full", forbidden_across: [] },
    { name: "credit", aggregation: "sum", additivity: "full", forbidden_across: [] },
  ],
  dimensions: [],
  filters: ["from", "to"],
  time_hierarchy: "calendar",
  paginates: true,
};

const ROW = {
  entry_date: "2026-09-01",
  type: "Invoice",
  reference: "BL-2609-018310",
  description: "September bill",
  charge: "84.200000",
  payment: "0",
  running_balance: "84.200000",
};

function statementPayload(columns: string[], withChoices: boolean) {
  return {
    key: "statement",
    dataset: "journal_lines",
    name: "Statement",
    basis: "posting",
    window: { start: "2026-09-01", end: "2026-09-30" },
    currency: "USD",
    columns,
    ...(withChoices ? { column_choices: STATEMENT_COLUMNS } : {}),
    head: {
      subject: "account",
      fields: [
        { field: "account_no", value: "AC-2026-00032" },
        { field: "customer_name", value: "Hugo Faulkner" },
      ],
    },
    rows: [ROW],
    kpis: [],
    totals: {},
    unavailable: [],
    grain: "posting",
    exportable: true,
    controls: {
      sorts: [],
      sort: "",
      dir: "asc",
      searchable: false,
      requires: [{ param: "subject_id", finds: "account" }],
    },
    page: { page: 1, per: 50, total: 1 },
  };
}

/**
 * A stub that answers the way the RUNNER does, transcribed from
 * `apps/reports/runner.served_columns`: a `columns` run control is narrowed
 * against the REPORT's own vocabulary where it declares one, and against the
 * DATASET's attributes where it does not.
 *
 * `withChoices: false` is the tip's behaviour and reproduces the defect.
 */
function statementClient(options: { withChoices?: boolean } = {}) {
  const withChoices = options.withChoices !== false;
  const posts: { path: string; body: unknown }[] = [];
  /** Every report request, as a query string. ⚠ **THE ASSERTION WAITS ON THIS
   *  AND NOT ON A TIMER.** The first draft of the journey case used `waitFor`
   *  over the header count alone; `waitFor` succeeds on its FIRST tick, which
   *  happened before the preview request had come back, so the case passed
   *  over the defect when it was deliberately reintroduced. That is law 7
   *  clause 2 in this file's own test, and it is why the count below is taken
   *  only once a request CARRYING `columns=` has been answered. */
  const reportCalls: string[] = [];
  const get = async (path: string, init?: { query?: Record<string, unknown> }) => {
    if (path === "/reports/datasets") {
      return { data: { datasets: [JOURNAL_LINES] }, status: 200 };
    }
    if (path.startsWith("/reports/")) {
      // ⚠ **`runReport` PUTS THE QUERY IN THE PATH, NOT IN `init.query`.** The
      // first draft of this stub read `init.query` and recorded two EMPTY
      // strings, so the wait below could never be satisfied — a recorder that
      // records nothing reads exactly like a screen that requests nothing.
      const [, rawQuery = ""] = path.split("?");
      const search = new URLSearchParams(rawQuery);
      const asked = search.get("columns") ?? init?.query?.columns;
      reportCalls.push(rawQuery);
      let columns = STATEMENT_COLUMNS;
      if (typeof asked === "string" && asked !== "") {
        const vocabulary = withChoices ? STATEMENT_COLUMNS : JOURNAL_LINES_ATTRIBUTES;
        const narrowed = asked
          .split(",")
          .map((one) => one.trim())
          .filter((one) => vocabulary.includes(one))
          // …and then intersected with what the query actually served, exactly
          // as `runner._shaped` does.
          .filter((one) => STATEMENT_COLUMNS.includes(one));
        if (narrowed.length > 0) columns = narrowed;
      }
      return { data: statementPayload(columns, withChoices), status: 200 };
    }
    if (path === "/reports") {
      return {
        data: { cards: [], groups: [], vocabularies: { services: [], bill_types: [], purposes: [] } },
        status: 200,
      };
    }
    if (path.startsWith("/lookups/")) return { data: { results: [], count: 0 }, status: 200 };
    return { data: {}, status: 200 };
  };
  const post = async (path: string, body: unknown) => {
    posts.push({ path, body });
    return { data: { job_id: "job-1" }, status: 202 };
  };
  const write = async () => ({ data: {}, status: 200 });
  return {
    posts,
    reportCalls,
    client: { request: get, get, post, put: write, patch: write, delete: write } as unknown as ApiClient,
  };
}

function mountStatement(client: ApiClient, search: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, PERIOD),
  );
  // ⚠ THE REAL PATH PATTERN, built from the route constant `App.tsx` registers
  // — never a literal repeated here. A test comparing a mistake with itself
  // passed over every unit link on the Units screen being a 404.
  // ⚠ **BOTH PATTERNS, BECAUSE `Edit` NOW TRAVELS** (PO ruling 2026-09-28 —
  // *"the report editor — panel or its own page - own page"*). Until that
  // ruling the editor was `?edit=1` on this very screen and one route was
  // enough. With only the viewer registered the journey below would press a
  // door onto nothing, and React Router would render its own no-match — which
  // looks, to `queryBy`, exactly like an editor that failed to open.
  const router = createMemoryRouter(
    [
      {
        path: `/:tenant${REPORT_EDITOR_ROUTE_PATTERN}`,
        element: <ReportEditorPage client={client} timeZone="America/Chicago" today="2026-09-26" />,
      },
      {
        path: `/:tenant${REPORTS_ROUTE}/:reportKey`,
        element: <ReportViewerPage client={client} timeZone="America/Chicago" today="2026-09-26" />,
      },
    ],
    { initialEntries: [`/${TENANT}${REPORTS_ROUTE}/statement${search}`] },
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

function headerCount(): number {
  return screen.getAllByRole("columnheader").length;
}

// ═══════════════════════════════════════════════════════════════════════════
// DEF-REP-7072 · THE JOURNEY — press Edit, then ask whether the table survived
// ═══════════════════════════════════════════════════════════════════════════
// ⚠ **AMENDED 2026-09-28 BY LANE REP-EDITOR-PAGE.** The Product Owner ruled
// the editor onto its own page, so *"press Edit and count the table's headers
// again"* now counts the BUILDER's preview rather than the viewer's table —
// the same seven names, resolved through the same `column_choices`, at a
// different address. **The guarantee is unchanged and is still the one that
// matters**: ticking nothing and merely OPENING the editor must not narrow a
// seven-column statement to one. Deleting `column_choices` from the fixture
// still reproduces the defect exactly.
describe("DEF-REP-7072 · opening the editor leaves the statement whole", () => {
  const WINDOW = `?f.from=2026-09-01&f.to=2026-09-30&subject_id=${ACCOUNT_ID}`;

  it("draws seven columns while the report is simply being READ", async () => {
    const { client } = statementClient();
    mountStatement(client, WINDOW);
    await waitFor(() => expect(headerCount()).toBe(7));
  });

  it("STILL draws seven after Edit is pressed — the defect, as a journey", async () => {
    const { client, reportCalls } = statementClient();
    mountStatement(client, WINDOW);
    await waitFor(() => expect(headerCount()).toBe(7));

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    // ⚠ The count is taken only once the PANEL has rendered AND the preview
    // request has been ANSWERED. `waitFor` succeeds on its first tick, so a
    // bare `waitFor(() => expect(headerCount()).toBe(7))` here passed over the
    // defect when it was deliberately reintroduced — it was measuring the
    // table from before the request. Law 7 clause 2, in this file's own test.
    await screen.findByText("Attributes");
    await waitFor(() =>
      expect(
        reportCalls.some((one) => one.includes("columns=")),
        `the editor must send its ticked columns; calls seen: ${reportCalls.join(" · ")}`,
      ).toBe(true),
    );
    // …and then let the answer render before counting. A `waitFor` over the
    // count itself succeeds on its FIRST tick, which is the table from BEFORE
    // the request — so it passed over the defect when it was deliberately
    // reintroduced. The wait above is on the REQUEST; this is the settle; the
    // assertion below is plain, and a plain assertion cannot pass early.
    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(
      headerCount(),
      "opening the editor sends the ticked columns as a run control. Narrowed " +
        "against the journal_lines dataset they collapse to `reference` alone.",
    ).toBe(7);
    const drawn = screen.getAllByRole("columnheader").map((cell) => cell.textContent?.trim());
    expect(drawn).toContain("Date");
    expect(drawn).toContain("Balance");
  });

  it("the editor offers the SEVEN this report serves, not the dataset's five", async () => {
    const { client } = statementClient();
    mountStatement(client, WINDOW);
    fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
    await screen.findByText("Attributes");
    // ⚠ **THE SECTION'S OWN COUNT, NOT EVERY CHECKBOX ON THE PAGE.** The table
    // draws its own; counting all of them measured 14 and would have passed or
    // failed for reasons that have nothing to do with this defect.
    expect(screen.getByText("7 of 7")).toBeTruthy();
    expect(screen.queryByText("7 of 5")).toBeNull();
    // Every one of the report's own columns is a tickable row, by its word.
    for (const word of ["Date", "Reference", "Balance"]) {
      // ⚠ `getAllBy`, NOT `getBy`: the table's own row-select boxes take their
      // accessible name from the cell they sit in, so a `getBy` here failed on
      // *"found multiple elements"* rather than on anything about this defect.
      const boxes = screen.getAllByRole("checkbox", { name: word });
      expect(
        boxes.some((box) => (box as HTMLInputElement).checked),
        `the editor offers ${word} and it is ticked`,
      ).toBe(true);
    }
    // ⚠ **AND THE DATASET'S OWN ATTRIBUTES ARE NOT AMONG THEM.** `posted_on`
    // is a real `journal_lines` column and a name this report cannot serve;
    // offering it is what made the count read `7 of 5`.
    expect(screen.queryByRole("checkbox", { name: "Posted" })).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DEF-REP-7052 · THE HEAD
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-7052 · the statement names what it is about", () => {
  it("draws the composed head and NEVER the id that selected it", async () => {
    const { client } = statementClient();
    const { container } = render(<div />);
    void container;
    mountStatement(client, `?f.from=2026-09-01&f.to=2026-09-30&subject_id=${ACCOUNT_ID}`);
    const head = await screen.findByText("AC-2026-00032 · Hugo Faulkner");
    expect(head.getAttribute("data-report-head")).toBe("account");
    // B14 rule 31 — the id travels in the URL and is never on screen.
    expect(document.body.textContent).not.toContain(ACCOUNT_ID);
  });

  it("renders NOTHING where the server published no head", () => {
    render(<ReportSubjectHead head={undefined} />);
    expect(document.querySelector("[data-report-head]")).toBeNull();
  });

  it("drops an empty part rather than drawing a stray separator", () => {
    expect(
      subjectHeadParts({
        subject: "unit",
        fields: [
          { field: "premises_address", value: "1408 Elm Street" },
          { field: "unit_label", value: "   " },
        ],
      }),
    ).toEqual(["1408 Elm Street"]);
  });

  it("joins the parts in the SERVER's order — hard rule 8's two halves", () => {
    render(
      <ReportSubjectHead
        head={{
          subject: "unit",
          fields: [
            { field: "premises_address", value: "1408 Elm Street" },
            { field: "unit_label", value: "Apt 3B" },
          ],
        }}
      />,
    );
    // The building's address, then the unit's label. There is no unit address.
    expect(screen.getByText("1408 Elm Street · Apt 3B")).toBeTruthy();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DEF-REP-7053 · THE DOWNLOAD BUTTON
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-7053 · the statement offers its download", () => {
  it("draws the control and POSTs the resource the registry holds", async () => {
    const { client, posts } = statementClient();
    mountStatement(client, `?f.from=2026-09-01&f.to=2026-09-30&subject_id=${ACCOUNT_ID}`);
    const button = await screen.findByRole("button", { name: /download/i });
    fireEvent.click(button);
    await waitFor(() => expect(posts.length).toBe(1));
    expect(posts[0].path).toBe("/exports");
    const body = posts[0].body as { resource: string; filters: Record<string, string> };
    expect(body.resource).toBe("statement");
    // ⚠ **WITHOUT THE SUBJECT THE FILE IS A STATEMENT ABOUT NOBODY.**
    expect(body.filters.subject_id).toBe(ACCOUNT_ID);
    // …and never the screen's page (§8.2: the right path never holds one).
    expect(body.filters.page).toBeUndefined();
    expect(body.filters.per).toBeUndefined();
  });
});
