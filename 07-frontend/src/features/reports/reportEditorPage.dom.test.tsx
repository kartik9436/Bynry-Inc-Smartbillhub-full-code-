// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  PO ruling 2026-09-28 — *"the report editor — panel or its own page
//          - own page"* (12-governance/02-decision-log.md, `d8c4bc1cb`).
// Defects: DEF-REP-7073 (any control closed the editor) · DEF-REP-7080 (the
//          Filters section drew every declared filter) · DEF-REP-7072
//          (`columnChoices` — carried across the move, and this file is the
//          check that it WAS carried).
// Screens: 2·2 (A1 S47) at `/{tenant}/reports/{key}/edit`
// Rules:   CLAUDE.md hard-won law 2 and its MIRROR · law 7 clause 2 (*what
//          would make this pass WRONGLY*) · B14 rule 33 · rule 43
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  A JOURNEY: PRESS A CONTROL, THEN ASK WHETHER THE SCREEN IS STILL ITSELF ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// Every defect found on this screen in the last week — a dead chooser, a
// closing panel, collapsing columns — is INVISIBLE to a fixture that mounts a
// component directly, because each of them lives where two correct halves
// meet. So this file drives the REAL router through the REAL patterns, presses
// the real `Edit` door, changes a parameter, and then asks what address it is
// standing at.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 clause 2):
//   · **A bare `MemoryRouter`.** `useParams().tenant` would be undefined and
//     every address these pages build would come out `//reports/…` — a
//     protocol-relative URL to another host, which reads as a perfectly good
//     string to `toContain`. The routes below are built from
//     `REPORT_EDITOR_ROUTE_PATTERN`, the same constant `App.tsx` registers,
//     never a literal repeated here.
//   · **Asserting the editor is still MOUNTED after a keystroke.** It would
//     be, in a router with one route and nowhere to go. The assertion is on
//     `router.state.location.pathname`, which is what actually moved when
//     `DEF-REP-7073` fired.
//   · **A `waitFor` over a rendered count.** `waitFor` succeeds on its FIRST
//     tick, so it reads the table from BEFORE the request. The column case
//     waits on a request CARRYING `columns=` having been ANSWERED, then
//     settles, then asserts plainly — a plain assertion cannot pass early.
//     The sibling statement suite learned this the hard way and says so.
//   · **Counting every checkbox on the page.** The attributes section has its
//     own count and that is what is read.
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

import { ReportEditorPage } from "./ReportEditorPage";
import { ReportViewerPage } from "./ReportViewerPage";
import {
  REPORTS_ROUTE,
  REPORT_BUILDER_NEW_ROUTE,
  REPORT_EDITOR_ROUTE_PATTERN,
  editorRouteFor,
} from "./reportsShared";

afterEach(cleanup);

const TENANT = "brazosbend";
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
 *  `DEF-REP-7072`, written down here so the premise cannot rot silently. */
const JOURNAL_LINES_ATTRIBUTES = [
  "posted_on",
  "account_code",
  "account_name",
  "reference",
  "narrative",
];

/** ⚠ **THIRTEEN, WHICH IS THE NUMBER `DEF-REP-7080` IS ABOUT.** The defect is
 *  a section that drew one stacked row per DECLARED filter, so the fixture has
 *  to declare more than a handful or the drawing and the defect look alike. */
const THIRTEEN_FILTERS = [
  "from",
  "to",
  "account_from",
  "account_to",
  "service",
  "basis",
  "source_type",
  "target",
  "level",
  "authority",
  "class",
  "area",
  "route",
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
  filters: THIRTEEN_FILTERS,
  time_hierarchy: "calendar",
  paginates: true,
};

function row(n: number) {
  return {
    entry_date: `2026-09-0${n}`,
    type: "Invoice",
    reference: `BL-2609-01831${n}`,
    description: "September bill",
    charge: "84.200000",
    payment: "0",
    running_balance: "84.200000",
  };
}

/** Eight rows, so the five-row cap is a cap and not a coincidence. */
const EIGHT_ROWS = [1, 2, 3, 4, 5, 6, 7, 8].map(row);

function statementPayload(columns: string[], rows: unknown[], withChoices: boolean) {
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
    rows,
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
    page: { page: 1, per: 50, total: rows.length },
  };
}

/**
 * A stub that answers the way the RUNNER does, transcribed from
 * `apps/reports/runner.served_columns`: a `columns` run control is narrowed
 * against the REPORT's own vocabulary where it declares one, and against the
 * DATASET's attributes where it does not.
 *
 * `withChoices: false` is the shape the defect had and reproduces it exactly.
 */
function statementClient(options: { withChoices?: boolean; rows?: unknown[] } = {}) {
  const withChoices = options.withChoices !== false;
  const rows = options.rows ?? EIGHT_ROWS;
  const reportCalls: string[] = [];
  const posts: { path: string; body: unknown }[] = [];
  const get = async (path: string, init?: { query?: Record<string, unknown> }) => {
    if (path === "/reports/datasets") {
      return { data: { datasets: [JOURNAL_LINES] }, status: 200 };
    }
    if (path.startsWith("/reports/")) {
      // ⚠ `runReport` puts the query in the PATH, not in `init.query` — a
      // recorder reading `init.query` records empty strings, and a recorder
      // that records nothing reads exactly like a screen that requests nothing.
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
          .filter((one) => STATEMENT_COLUMNS.includes(one));
        if (narrowed.length > 0) columns = narrowed;
      }
      return { data: statementPayload(columns, rows, withChoices), status: 200 };
    }
    if (path === "/reports") {
      return {
        data: {
          cards: [],
          groups: [],
          vocabularies: { services: [], bill_types: [], purposes: [] },
        },
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
    client: {
      request: get,
      get,
      post,
      put: write,
      patch: write,
      delete: write,
    } as unknown as ApiClient,
  };
}

/**
 * BOTH real patterns, so a journey can actually travel between them.
 *
 * ⚠ **THE PATTERNS ARE THE CONSTANTS `App.tsx` REGISTERS.** A test that
 * repeats a path as a literal compares a mistake with itself — a hold-expiry
 * test once asserted a screen was registered at an address while the router
 * mounted it somewhere else, and both opened onto *"not built yet"* with every
 * check green.
 */
function mountAt(client: ApiClient, entry: string) {
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
    [
      {
        path: `/:tenant${REPORT_EDITOR_ROUTE_PATTERN}`,
        element: (
          <ReportEditorPage client={client} timeZone="America/Chicago" today="2026-09-28" />
        ),
      },
      {
        path: `/:tenant${REPORTS_ROUTE}/:reportKey`,
        element: (
          <ReportViewerPage client={client} timeZone="America/Chicago" today="2026-09-28" />
        ),
      },
    ],
    { initialEntries: [`/${TENANT}${entry}`] },
  );
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return router;
}

const WINDOW = `?f.from=2026-09-01&f.to=2026-09-30&subject_id=${ACCOUNT_ID}`;
const EDITOR_ENTRY = `${editorRouteFor("statement")}${WINDOW}`;

function attributeBoxes(): HTMLInputElement[] {
  const sections = document.querySelector("[data-report-edit-panel]");
  return Array.from(sections?.querySelectorAll('input[type="checkbox"]') ?? []);
}

// ═══════════════════════════════════════════════════════════════════════════
// PO 2026-09-28 · THE EDITOR IS AN ADDRESS, AND THE DOOR OPENS ON IT
// ═══════════════════════════════════════════════════════════════════════════
describe("the report editor has its own page", () => {
  it("the Edit door on 2·1 lands on the address App.tsx registers", async () => {
    const { client } = statementClient();
    const router = mountAt(client, `${REPORTS_ROUTE}/statement${WINDOW}`);
    fireEvent.click(await screen.findByRole("button", { name: "Edit" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/${TENANT}${editorRouteFor("statement")}`),
    );
    // …and it carries the question the clerk could see, or the builder previews
    // a report nobody asked for.
    expect(router.state.location.search).toContain(`subject_id=${ACCOUNT_ID}`);
    await screen.findByText("Attributes");
  });

  it("the retired `?edit=1` bookmark redirects here, carrying the rest", async () => {
    const { client } = statementClient();
    const router = mountAt(client, `${REPORTS_ROUTE}/statement${WINDOW}&edit=1`);
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(`/${TENANT}${editorRouteFor("statement")}`),
    );
    expect(router.state.location.search).toContain(`subject_id=${ACCOUNT_ID}`);
    expect(router.state.location.search).not.toContain("edit=1");
  });

  it("DEF-REP-7073 · a control changes the rows and NOT the address", async () => {
    const { client } = statementClient();
    const router = mountAt(client, EDITOR_ENTRY);
    await screen.findByText("Attributes");
    const before = router.state.location.pathname;

    // Any control on the bar reaches `update()`. This is the one that fired the
    // defect: typing into the window took `?edit=1` off the URL mid-keystroke.
    const to = document.querySelector('input[name="f.to"], input[type="date"]');
    if (to !== null) {
      fireEvent.change(to, { target: { value: "2026-09-29" } });
    } else {
      // No date control on this report's bar — press the one thing that is
      // always there rather than silently asserting nothing (law 7's
      // *reporting zero over a scope it excludes*).
      fireEvent.click(attributeBoxes()[0]);
    }
    await waitFor(() => expect(router.state.location.pathname).toBe(before));
    expect(router.state.location.pathname.endsWith("/edit")).toBe(true);
    // ⚠ **AND THE SCREEN IS STILL THE BUILDER, NOT MERELY AT ITS ADDRESS.**
    expect(document.querySelector('[data-report-edit-variant="page"]')).toBeTruthy();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DEF-REP-7201 · A STYLESHEET SELECTOR NOTHING IN THE COMPONENT MENTIONS
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-7201 · the Dataset row reads as a row", () => {
  it("never wraps its select in the label, because a global rule stacks those", async () => {
    // ⚠ **THIS IS A PROXY AND IT SAYS SO** (law 7 clause 2). The real fault is
    // a COMPUTED `flex-direction: column`, from
    // `.view label:has(> select)` at specificity (0,1,2) beating the
    // component's `flex` utility at (0,1,0) — and **jsdom applies no
    // stylesheet, so no case in this file can measure that.** What a case CAN
    // assert is the shape that makes the selector match, which is the thing
    // this lane changed and the thing a future edit would undo. The computed
    // style itself is measured in a real browser by
    // `10-scripts/rep_editor_page_walkthrough.mjs`.
    const { client } = statementClient();
    mountAt(client, EDITOR_ENTRY);
    await screen.findByText("Attributes");
    const panel = document.querySelector("[data-report-edit-panel]");
    expect(panel).toBeTruthy();
    expect(
      panel?.querySelectorAll("label:has(> select)").length,
      "a label wrapping a select is stacked by a global rule this component " +
        "does not mention; make the label a SIBLING instead",
    ).toBe(0);
    // …and the control is still bound to its word, which is what the wrapper
    // was doing before.
    expect(screen.getByLabelText("Dataset")).toBeTruthy();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DEF-REP-7072 · `columnChoices` SURVIVED THE MOVE
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-7072 · the statement opens on its own seven columns", () => {
  it("offers the SEVEN this report serves, not the dataset's five", async () => {
    const { client } = statementClient();
    mountAt(client, EDITOR_ENTRY);
    await screen.findByText("Attributes");
    expect(screen.getByText("7 of 7")).toBeTruthy();
    expect(screen.queryByText("7 of 5")).toBeNull();
    expect(attributeBoxes()).toHaveLength(7);
    expect(attributeBoxes().filter((box) => box.checked)).toHaveLength(7);
    // ⚠ **THE DATASET'S OWN ATTRIBUTES ARE NOT AMONG THEM.** `posted_on` is a
    // real `journal_lines` column and a name this report cannot serve.
    expect(screen.queryByRole("checkbox", { name: "Posted" })).toBeNull();
    // ⚠ **AND NO MEASURES SECTION AT ALL** — a viewer's columns ARE its
    // columns, and an empty *Measures* panel over a statement says nothing.
    expect(screen.queryByText("Measures")).toBeNull();
  });

  it("the preview still shows seven headings after the first tick", async () => {
    const { client, reportCalls } = statementClient();
    mountAt(client, EDITOR_ENTRY);
    await screen.findByText("Attributes");
    // ⚠ Wait on the REQUEST having been answered, never on the rendered count:
    // `waitFor` succeeds on its first tick and would read the table from
    // BEFORE the request.
    await waitFor(() =>
      expect(
        reportCalls.some((one) => one.includes("columns=")),
        `the editor must send its ticked columns; calls seen: ${reportCalls.join(" · ")}`,
      ).toBe(true),
    );
    await new Promise((resolve) => setTimeout(resolve, 400));
    const sample = document.querySelector("[data-report-sample]");
    expect(sample, "the preview draws the report's own rows").toBeTruthy();
    expect(
      sample?.querySelectorAll("thead th").length,
      "narrowed against the journal_lines dataset these collapse to `reference` alone",
    ).toBe(7);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// PO 2026-09-28 · WHAT THE CLERK SEES WHILE THEY ARE CHOOSING
// ═══════════════════════════════════════════════════════════════════════════
describe("the preview answers while the report is being described", () => {
  it("draws the report's own rows, capped at five of the eight served", async () => {
    const { client } = statementClient();
    mountAt(client, EDITOR_ENTRY);
    const sample = await waitFor(() => {
      const found = document.querySelector("[data-report-sample]");
      expect(found).toBeTruthy();
      return found;
    });
    expect(sample?.querySelectorAll("tbody tr")).toHaveLength(5);
    // A FACT of five words, and it is the same five the cap is.
    expect(screen.getByText("First five rows, updating live")).toBeTruthy();
    // ⚠ The rows are REAL — the reference the stub served, not an invention.
    expect(sample?.textContent).toContain("BL-2609-018311");
  });

  it("falls back to the SHAPE — headings over bars — where nothing came back", async () => {
    const { client } = statementClient({ rows: [] });
    mountAt(client, EDITOR_ENTRY);
    await screen.findByText("Attributes");
    await waitFor(() => expect(screen.getByText("Example")).toBeTruthy());
    expect(screen.getByText("Shape only. No data here.")).toBeTruthy();
    expect(document.querySelector("[data-report-sample]")).toBeNull();
    // ⚠ **AND NOT ONE CHARACTER A CLERK COULD READ AS A FIGURE.**
    const bars = document.querySelector("[data-report-shape] tbody");
    expect((bars?.textContent ?? "").trim()).toBe("");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DEF-REP-7080 · THE FILTERS SECTION DREW EVERY DECLARED FILTER
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-7080 · filters are disclosed, not stacked thirteen deep", () => {
  function filterRows(): number {
    // ⚠ **THE FILTER INPUTS BY NAME, NOT `input[type="text"]`.** The first
    // draft of this helper counted text inputs inside the section and caught
    // the required-record chooser as well: the two cases expecting ZERO rows
    // failed on 1, and the two expecting ONE **passed for the wrong reason**.
    // That is law 7 clause 2 — *what would make this pass wrongly* — answered
    // by the half of the suite that could still fail.
    return document.querySelectorAll("[data-report-filter]").length;
  }

  it("draws NO filter rows until one is added, over thirteen declared", async () => {
    const { client } = statementClient();
    mountAt(client, EDITOR_ENTRY);
    await screen.findByText("Filters");
    // The drawing's header form: `FILTERS · 13 AVAILABLE`.
    expect(screen.getByText("13 available")).toBeTruthy();
    // ⚠ **THE DEFECT WAS THIRTEEN STACKED ROWS.** A statement carries no
    // filter value of its own, so the drawn state is the `+ Add filter`
    // control and nothing else.
    expect(filterRows()).toBe(0);
    expect(screen.getByRole("combobox", { name: "Add filter" })).toBeTruthy();
    expect(screen.getByText("Show on the bar")).toBeTruthy();
    expect(screen.getByText("0 of 13")).toBeTruthy();
  });

  it("adds exactly the filter that was chosen, and counts it on the bar", async () => {
    const { client } = statementClient();
    mountAt(client, EDITOR_ENTRY);
    const add = await screen.findByRole("combobox", { name: "Add filter" });
    fireEvent.change(add, { target: { value: "source_type" } });
    await waitFor(() => expect(filterRows()).toBe(1));
    expect(screen.getByText("1 of 13")).toBeTruthy();
    // ⚠ **AND IT IS GONE FROM WHAT THE CONTROL STILL OFFERS**, or a clerk can
    // add the same filter twice and the second one silently replaces the first.
    const options = Array.from(
      (screen.getByRole("combobox", { name: "Add filter" }) as HTMLSelectElement).options,
    ).map((option) => option.value);
    expect(options).not.toContain("source_type");
  });

  it("clearing the value leaves the row on the bar — it does NOT vanish", async () => {
    const { client } = statementClient();
    mountAt(client, EDITOR_ENTRY);
    const add = await screen.findByRole("combobox", { name: "Add filter" });
    fireEvent.change(add, { target: { value: "source_type" } });
    await waitFor(() => expect(filterRows()).toBe(1));
    const input = document.querySelector("[data-report-filter]") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "manual" } });
    fireEvent.change(input, { target: { value: "" } });
    // ⚠ The drawing's own second row is `Consumer class → All`: on the bar,
    // narrowing nothing. A row that disappeared under the clerk mid-edit is
    // the same class of fault as the panel that closed on a keystroke.
    await waitFor(() => expect(filterRows()).toBe(1));
    expect(screen.getByText("1 of 13")).toBeTruthy();
  });

  it("removes the row when the clerk says so, and offers the filter again", async () => {
    const { client } = statementClient();
    mountAt(client, EDITOR_ENTRY);
    const add = await screen.findByRole("combobox", { name: "Add filter" });
    fireEvent.change(add, { target: { value: "source_type" } });
    await waitFor(() => expect(filterRows()).toBe(1));
    fireEvent.click(screen.getByRole("button", { name: /^Remove filter:/ }));
    await waitFor(() => expect(filterRows()).toBe(0));
    expect(screen.getByText("0 of 13")).toBeTruthy();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// `DEF-REP-7640` · THE SAME SCREEN, OPENED ON NOTHING
// ═══════════════════════════════════════════════════════════════════════════
//
// PO ruling 2026-09-28, verbatim: *"Opens the editor on a blank definition,
// then Save as"*. The Product Owner pressed `+ Build your own` on deployed
// `v2.388.0` and nothing happened; the fix is this page, in `blank` mode, at
// `/reports/custom/new`.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 clause 2), asked before
// they were written:
//   · **Asserting the page RENDERS.** It rendered before the fix too — a
//     permanent `LoadingSkeleton` over a report that is never coming. So the
//     cases assert the SECTIONS are there and the draft is EMPTY, which a
//     skeleton cannot satisfy.
//   · **Asserting the preview panel EXISTS.** `ReportShapePreview` would
//     satisfy that once a column is ticked. The blank case reads
//     `[data-report-blank-preview]`, which only one component draws.
//   · **Asserting the refusal through `t(key)` on both sides.** That compares
//     the code with itself and is green over a raw catalogue key on screen, so
//     the English literal is typed out here (`renderedCopy.test.tsx`'s lesson).
//   · **Asserting `Save as` is DISABLED.** It is not, deliberately — a greyed
//     button is rule 33's *you cannot* over something a clerk very much can
//     do. The refusal is what is asserted, and that it names the missing
//     thing.
describe("DEF-REP-7640 · the builder opens on a blank definition", () => {
  const INVOICES = {
    code: "invoices",
    owner_module: "billing",
    grain: "one invoice",
    columns: ["account_no", "customer", "class"].map((name) => ({
      name,
      type: "text",
      unit: null,
      unit_from: null,
      money_basis: null,
      scale: null,
    })),
    measures: [{ name: "total", aggregation: "sum", additivity: "full", forbidden_across: [] }],
    dimensions: [],
    filters: ["from", "to"],
    time_hierarchy: "calendar",
    paginates: true,
  };

  const GROUPS = [
    {
      code: "receivables",
      name: "Receivables",
      sub_groups: [{ code: "receivables_arrears", name: "Arrears" }],
    },
  ];

  /** A server that knows about datasets and the catalogue and nothing else —
   *  which is exactly the world a report that has never been saved lives in.
   *  ⚠ It RECORDS its posts, because `based_on: null` is a wire fact and a
   *  test that only watched the screen could not see it. */
  function blankClient() {
    const posts: { path: string; body: Record<string, unknown> }[] = [];
    const reads: string[] = [];
    const get = async (path: string) => {
      reads.push(path);
      if (path === "/reports/datasets") return { data: { datasets: [INVOICES] }, status: 200 };
      if (path === "/reports") {
        return {
          data: {
            cards: [],
            groups: GROUPS,
            vocabularies: { services: [], bill_types: [], purposes: [] },
          },
          status: 200,
        };
      }
      return { data: {}, status: 200 };
    };
    const post = async (path: string, body: Record<string, unknown>) => {
      posts.push({ path, body });
      return {
        data: {
          id: "01a0e7ff-0000-7000-8000-000000000001",
          key: "blank-one",
          name: String(body.name ?? ""),
          dataset: String(body.dataset ?? ""),
          group: String(body.group ?? ""),
          sub_group: null,
          visibility: "private",
          owner_user_id: null,
          based_on: body.based_on ?? null,
          created: true,
        },
        status: 201,
      };
    };
    const write = async () => ({ data: {}, status: 200 });
    return {
      posts,
      reads,
      client: { request: get, get, post, put: write, patch: write, delete: write } as unknown as ApiClient,
    };
  }

  /** The REAL pattern `App.tsx` registers for the blank builder, and `blank`
   *  passed the way the router passes it. A literal here would compare a
   *  mistake with itself. */
  function mountBlank(client: ApiClient) {
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
      [
        {
          path: `/:tenant${REPORT_BUILDER_NEW_ROUTE}`,
          element: (
            <ReportEditorPage
              blank
              client={client}
              timeZone="America/Chicago"
              today="2026-09-28"
            />
          ),
        },
        { path: `/:tenant${REPORTS_ROUTE}/:reportKey`, element: <p>the viewer</p> },
        { path: `/:tenant${REPORTS_ROUTE}/custom`, element: <p>the custom catalogue</p> },
      ],
      { initialEntries: [`/${TENANT}${REPORT_BUILDER_NEW_ROUTE}`] },
    );
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <RouterProvider router={router} />
        </ToastProvider>
      </QueryClientProvider>,
    );
    return router;
  }

  /**
   * Pick the one dataset, once the server has actually offered it.
   *
   * ⚠ **THE WAIT IS THE POINT AND IT IS A FACT ABOUT THE SCREEN, NOT A TEST
   * CONVENIENCE.** A blank builder draws its sections on the FIRST render —
   * the draft is seeded in `useState`, not from a response — so the chooser
   * exists before `GET /reports/datasets` has answered and holds only the
   * unchosen option for those milliseconds. `fireEvent.change` to a value
   * whose option does not exist yet is a silent no-op in jsdom:
   * `selectedIndex` goes to `-1`, `value` stays `""`, React's handler fires
   * with the empty string, and the case fails three assertions later with
   * `expected 0 to be greater than 0` — which names neither the race nor the
   * select. Measured here on 2026-09-28 before this helper existed.
   */
  async function chooseDataset(): Promise<HTMLSelectElement> {
    const chooser = (await screen.findByLabelText("Dataset")) as HTMLSelectElement;
    await waitFor(() =>
      expect(
        Array.from(chooser.options).map((one) => one.value),
        "the dataset list has not arrived, so there is nothing to choose",
      ).toContain("invoices"),
    );
    fireEvent.change(chooser, { target: { value: "invoices" } });
    return chooser;
  }

  it("draws the sections with NO subject, NO column and NO filter", async () => {
    mountBlank(blankClient().client);
    const chooser = (await screen.findByLabelText("Dataset")) as HTMLSelectElement;
    // The draft is `draftFrom("")`. A `<select>` whose value matches no option
    // shows the FIRST one, so an unchosen option has to exist or the screen
    // says *Invoices* over a draft holding nothing.
    expect(chooser.value, "the blank builder opened on a dataset nobody chose").toBe("");
    expect(
      Array.from(chooser.options).map((one) => one.value),
      "there is no unchosen option, so the select cannot show an empty draft",
    ).toContain("");
    expect(attributeBoxes().filter((box) => box.checked)).toHaveLength(0);
    expect(document.querySelectorAll("[data-report-filter]")).toHaveLength(0);
  });

  it("says the preview has nothing to show, in words, with no figure in it", async () => {
    mountBlank(blankClient().client);
    await screen.findByLabelText("Dataset");
    const blank = document.querySelector("[data-report-blank-preview]");
    expect(blank, "the right-hand column rendered nothing at all").not.toBeNull();
    // The English literal, never `t(key)` on both sides — a raw catalogue key
    // on screen satisfies the second and nobody finds out.
    expect(blank?.textContent?.trim()).toBe("Nothing to show yet.");
    // And no number a clerk could read as their utility's money.
    expect(blank?.textContent ?? "").not.toMatch(/\d/);
  });

  it("reads NEW rather than EDITING, and exits to Custom rather than a viewer", async () => {
    const router = mountBlank(blankClient().client);
    await screen.findByLabelText("Dataset");
    expect(screen.getByText("New report")).toBeTruthy();
    expect(document.body.textContent ?? "").not.toMatch(/EDITING/);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    // `viewerRouteFor("")` would have built `/reports/`, which is the
    // catalogue wearing a trailing slash — a real address that is not the one
    // anybody meant.
    expect(router.state.location.pathname).toBe(`/${TENANT}${REPORTS_ROUTE}/custom`);
  });

  it("refuses `Save as` on an empty definition and NAMES what is missing", async () => {
    mountBlank(blankClient().client);
    await screen.findByLabelText("Dataset");
    fireEvent.click(screen.getByRole("button", { name: "Save as" }));
    const refusal = document.querySelector("[data-report-save-refusal]");
    expect(refusal, "pressing Save as on a blank draft said nothing at all").not.toBeNull();
    expect(refusal?.textContent?.trim()).toBe("Choose a dataset first.");
    // And it did NOT open the dialog over a draft the server would refuse.
    expect(document.querySelector("input#name")).toBeNull();
  });

  it("names the COLUMNS once a subject is chosen — the second missing thing", async () => {
    mountBlank(blankClient().client);
    const chooser = await chooseDataset();
    expect(chooser.value).toBe("invoices");
    await waitFor(() => expect(attributeBoxes().length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole("button", { name: "Save as" }));
    const refusal = document.querySelector("[data-report-save-refusal]");
    expect(refusal?.textContent?.trim()).toBe("Select at least one column."); // DEF-SHL-8836: US English
  });

  it("opens the dialog once the draft is real, and the name box is EMPTY", async () => {
    mountBlank(blankClient().client);
    await chooseDataset();
    await waitFor(() => expect(attributeBoxes().length).toBeGreaterThan(0));
    fireEvent.click(attributeBoxes()[0]);
    fireEvent.click(screen.getByRole("button", { name: "Save as" }));
    // ⚠ **BY ID, NOT BY LABEL TEXT.** `getByLabelText(/Name/i)` matches the
    // dialog's *Name* field AND a column whose words contain it, and a
    // multiple-match error reads like the dialog never opened. `FormModal`
    // gives every field the id it is passed, which is the stable hook.
    const nameBox = (await waitFor(() =>
      document.querySelector<HTMLInputElement>("input#name"),
    )) as HTMLInputElement;
    expect(nameBox, "the Save-as dialog did not open over a real draft").not.toBeNull();
    // ⚠ Prefilling the page's own title would save a report called *New
    // report* for every clerk who pressed Save without reading the field.
    expect(nameBox.value).toBe("");
    expect(document.querySelector("[data-report-save-refusal]")).toBeNull();
  });

  it("creates it with `based_on: null` — *from scratch*, not an empty string", async () => {
    // p022 callout ⑤: the *Based on* column is the difference between a
    // catalogue and a junk drawer, and `""` in it names no report at all.
    const server = blankClient();
    mountBlank(server.client);
    await chooseDataset();
    await waitFor(() => expect(attributeBoxes().length).toBeGreaterThan(0));
    fireEvent.click(attributeBoxes()[0]);
    fireEvent.click(screen.getByRole("button", { name: "Save as" }));
    const nameBox = (await waitFor(() =>
      document.querySelector<HTMLInputElement>("input#name"),
    )) as HTMLInputElement;
    fireEvent.change(nameBox, { target: { value: "Blank one" } });
    fireEvent.change(document.querySelector("select#group") as HTMLSelectElement, {
      target: { value: "receivables" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(server.posts.filter((one) => one.path === "/reports/definitions")).toHaveLength(1),
    );
    const body = server.posts[server.posts.length - 1].body;
    expect(body.based_on, "a blank build sent a based_on it was never copied from").toBeNull();
    expect(body.dataset).toBe("invoices");
    expect(body.name).toBe("Blank one");
    expect(Array.isArray(body.columns) && (body.columns as string[]).length).toBeGreaterThan(0);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: PO ruling 2026-09-28 (12-governance/02-decision-log.md, `d8c4bc1cb`) · DEF-REP-7073 · DEF-REP-7080 · DEF-REP-7072
// screens: 2·2 (A1 S47)
// generated: 2026-09-28 by lane REP-EDITOR-PAGE
// gates: RED PROVED, AND THE TWO HALVES ARE PROVED BY DIFFERENT MEANS BECAUSE THEY FAIL FOR DIFFERENT REASONS.
//   (1) `offers the SEVEN this report serves` — run with `columnChoices` DELETED from ReportEditorPage.tsx: `Unable to find an element with the text: 7 of 7`. That is the CLIENT half of DEF-REP-7072.
//   (2) `the preview still shows seven headings` — run with the fixture's `withChoices: false`, i.e. a server that publishes no `column_choices`: `narrowed against the journal_lines dataset these collapse to `reference` alone: expected 1 to be 7`. ⚠ **IT DOES NOT GO RED ON (1)'s CHANGE AND MUST NOT BE READ AS PROVING IT** — the draft is seeded from the report's own seven columns, so the page goes on SENDING seven whatever the panel offers. Recorded rather than left implied (law 7 clause 2).
//   (3) the two DEF-REP-7080 cases expecting ZERO filter rows caught their own helper: `input[type="text"]` inside the section also matches the required-record chooser, so the two cases expecting ONE were passing for the wrong reason. `[data-report-filter]` is the fix.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
