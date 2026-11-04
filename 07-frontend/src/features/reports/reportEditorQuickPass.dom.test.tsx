// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-REP-7070 — Product Owner, deployed v2.380.3, on screen 2·2
//          (`/{tenant}/reports/statement?edit=1`): *"report editor is not user
//          friendly — as a user I don't know what I'm doing and how fields are
//          shown — no edit no adds"*.
//          Screens: 2·2 (A1 S47)
// Rules:   B14 rule 33 (a LABEL ≤ 3 words · a FACT ≤ 6 · RATIONALE zero words
//          on screen) · rule 31 (no database id is a visible value) · rule 43
//          (a component, not an inline block) · BR-REP-043 · BR-REP-038 ·
//          hard-won law 2's MIRROR · law 7 clause 2 (*"ask what would make this
//          check pass wrongly"*)
// Tests:   this file
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY CASE HERE WAS SHOWN RED BEFORE THE CODE IT CHECKS EXISTED**, and
// the failure text is quoted in the lane report. `reportWord`, `finderFor`,
// `ReportShapePreview` and the `requiredInputs` prop were all absent, so the
// file did not compile — which is a red, and is NOT the same as a red
// assertion. The count and the naming cases were therefore ALSO run against a
// copy of the panel at the tip, where they fail on the values the Product
// Owner photographed: `7 of 5` and `posted_on`.
//
// ⚠ **WHAT WOULD MAKE EACH OF THESE PASS WRONGLY** is recorded beside it.
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ReportDataset } from "@/api/reportsEndpoints";
import { ReportEditPanel, draftFrom } from "./ReportEditPanel";
import { ReportShapePreview } from "./ReportShapePreview";
import { finderFor } from "./ReportRequiredInput";
import { REPORTS_ROUTE, reportWord } from "./reportsShared";

afterEach(cleanup);

const TENANT = "brazosbend";

/**
 * The `journal_lines` dataset, shaped as `GET /reports/datasets` serves it and
 * carrying the EXACT five attributes and four measures the Product Owner
 * photographed. Copied from `apps/reports/datasets.JOURNAL_LINES` rather than
 * invented, because the whole defect is an arithmetic over those two lists.
 */
const JOURNAL_LINES: ReportDataset = {
  code: "journal_lines",
  owner_module: "ledger",
  grain: "one journal line",
  columns: [
    { name: "posted_on", type: "date", unit: null, unit_from: null, money_basis: null, scale: null },
    { name: "account_code", type: "text", unit: null, unit_from: null, money_basis: null, scale: null },
    { name: "account_name", type: "text", unit: null, unit_from: null, money_basis: null, scale: null },
    { name: "reference", type: "text", unit: null, unit_from: null, money_basis: null, scale: null },
    { name: "narrative", type: "text", unit: null, unit_from: null, money_basis: null, scale: null },
    { name: "debit", type: "money", unit: null, unit_from: null, money_basis: "posting", scale: 4 },
    { name: "credit", type: "money", unit: null, unit_from: null, money_basis: "posting", scale: 4 },
    { name: "balance", type: "money", unit: null, unit_from: null, money_basis: "posting", scale: 4 },
  ],
  measures: [
    { name: "debit", aggregation: "sum", additivity: "full", forbidden_across: [] },
    { name: "credit", aggregation: "sum", additivity: "full", forbidden_across: [] },
    { name: "balance", aggregation: "sum", additivity: "semi", forbidden_across: [] },
    { name: "lines", aggregation: "count", additivity: "full", forbidden_across: [] },
  ],
  dimensions: [
    { name: "time", attributes: ["accounting_period"], hierarchy: null, conformed: true },
    { name: "service", attributes: ["service_code"], hierarchy: null, conformed: true },
  ],
  filters: ["from", "to", "account_from", "account_to", "service", "basis", "source_type", "target", "level", "authority"],
  time_hierarchy: "calendar",
  paginates: true,
};

/** The seven columns `apps/reports/statement.STATEMENT_COLUMNS` actually serves. */
const STATEMENT_COLUMNS = [
  "entry_date",
  "type",
  "reference",
  "description",
  "charge",
  "payment",
  "running_balance",
];

function mountAt(element: React.ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [{ path: `/:tenant${REPORTS_ROUTE}/:reportKey`, element: <>{element}</> }],
    { initialEntries: [`/${TENANT}${REPORTS_ROUTE}/statement`] },
  );
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

function statementPanel(extra: Record<string, unknown> = {}) {
  return mountAt(
    <ReportEditPanel
      dataset={JOURNAL_LINES}
      datasets={[JOURNAL_LINES]}
      draft={draftFrom("journal_lines", { columns: [...STATEMENT_COLUMNS] })}
      onChange={() => {}}
      groups={[]}
      onSaveAs={() => {}}
      onCancel={() => {}}
      {...extra}
    />,
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TASK 4 · `ATTRIBUTES 7 of 5` WAS TWO COUNTS OF TWO DIFFERENT SETS
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-7070 · the attributes count says ONE true thing", () => {
  it("never reports more shown than the section lists", () => {
    // ⚠ **THE EXACT PHOTOGRAPHED CASE.** Seven served columns, five dataset
    // attributes, and the two sets intersect in exactly one name —
    // `reference`. Before the fix this read `7 of 5`.
    statementPanel();
    expect(screen.queryByText("7 of 5")).toBeNull();
    expect(screen.getByText("1 of 5")).toBeTruthy();
    // ⚠ PASSES WRONGLY IF: the section were simply not drawn. So the rows are
    // asserted too — five checkboxes, one of them on.
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes).toHaveLength(5);
    expect(boxes.filter((box) => (box as HTMLInputElement).checked)).toHaveLength(1);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// TASK 2 · EVERY FIELD IS NAMED IN WORDS, THROUGH THE VIEWER'S OWN PATH
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-7070 · the editor names fields in words", () => {
  it("reads a column, a measure and a filter out of the catalogues", () => {
    statementPanel();
    // attributes
    expect(screen.getByText("Posted")).toBeTruthy();
    expect(screen.getByText("Account code")).toBeTruthy();
    expect(screen.getByText("Narrative")).toBeTruthy();
    // a measure
    expect(screen.getByText("Lines")).toBeTruthy();
    // a FILTER, which `reports.col.*` has never had an entry for — this is the
    // case that proves the fallback to the parameter catalogue runs.
    expect(screen.getByText("Source")).toBeTruthy();
    expect(screen.getByText("Detail level")).toBeTruthy();
    // the dataset itself
    expect(screen.getByText("Ledger postings")).toBeTruthy();
    // ⚠ **THE MIRROR, AND IT IS THE HALF THAT WOULD HAVE SHIPPED.** A naming
    // helper that returned words for SOME names and the raw token for others
    // passes every assertion above. So: none of the raw tokens survives.
    for (const raw of ["posted_on", "account_code", "narrative", "source_type", "journal_lines"]) {
      expect(screen.queryByText(raw)).toBeNull();
    }
  });

  it("is the SAME function the table's headings call", () => {
    // `reportTableConfig` and this panel both call `reportWord`. Asserting the
    // function directly is what stops a second naming path being written.
    expect(reportWord("posted_on", i18n.t.bind(i18n))).toBe("Posted");
    // ⚠ A name NEITHER catalogue has authored survives as itself — a missing
    // entry must stay reportable, never become a blank a clerk cannot describe.
    expect(reportWord("no_such_column_anywhere", i18n.t.bind(i18n))).toBe(
      "no_such_column_anywhere",
    );
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// TASK 1 · THE REQUIRED INPUT IS ASKED FOR FIRST — AND ONLY WHERE REQUIRED
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-7070 · a report that is ABOUT one record asks first", () => {
  it("draws the required input ABOVE the dataset section", () => {
    statementPanel({ requiredInputs: <div data-testid="req">chooser</div> });
    const panel = document.querySelector("[data-report-edit-panel]");
    const chooser = screen.getByTestId("req");
    const report = screen.getByText("Report");
    expect(panel).toBeTruthy();
    // ⚠ **"FIRST" IS A POSITION, SO IT IS MEASURED AS ONE** — by DOCUMENT
    // ORDER, which is the only thing "above" can mean to a check in jsdom
    // (there is no layout). A `toBeTruthy()` on the chooser alone would pass
    // with it rendered at the bottom of the panel, which is the defect.
    expect(
      chooser.compareDocumentPosition(report) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("adds NO step to a report that requires nothing", () => {
    // Forty-five of the forty-six. The panel must open on REPORT, exactly as
    // it did before this defect was filed.
    statementPanel();
    expect(screen.queryByTestId("req")).toBeNull();
    const panel = document.querySelector("[data-report-edit-panel]");
    // ⚠ PASSES WRONGLY IF: an empty Panel were drawn with nothing in it. So
    // the FIRST section heading is asserted, not merely the chooser's absence.
    // ⚠ `Report`, not `REPORT` — the heading is uppercased by a Tailwind utility,
    // so `textContent` carries the AUTHORED case. Asserting the shouted form
    // passes only where the CSS has not loaded, which jsdom is.
    expect(panel?.querySelector("h3")?.textContent).toBe("Report");
  });

  it("offers a finder only for a kind this screen can actually search", () => {
    // ⚠ **THE VOCABULARY IS THE SERVER'S AND THE CAPABILITY IS OURS.**
    // `BR-REP-043` rules five subjects; `apps/reports/statement.py` refuses
    // `customer`, `premises` and `unit` BY NAME because the ledger publishes
    // no running record at those grains. A box over a query that will refuse
    // whatever is typed into it is hard-won law 2's mirror.
    expect(finderFor("account")).toBe("account");
    for (const refused of ["customer", "premises", "unit"]) {
      expect(finderFor(refused)).toBeNull();
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// TASK 3 · AN EXAMPLE THAT CANNOT BE MISTAKEN FOR A UTILITY'S OWN DATA
// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-REP-7070 · the shape of a report with no rows", () => {
  const columns = [
    { key: "entry_date", label: "Date" },
    { key: "charge", label: "Charge" },
  ];

  it("names itself and states what it is", () => {
    render(
      <ReportShapePreview columns={columns} columnMeta={undefined} t={i18n.t.bind(i18n)} />,
    );
    expect(screen.getByText("Example")).toBeTruthy();
    expect(screen.getByText("Shape only. No data here.")).toBeTruthy();
  });

  it("contains not one character a clerk could read as a figure", () => {
    render(
      <ReportShapePreview columns={columns} columnMeta={undefined} t={i18n.t.bind(i18n)} />,
    );
    const body = document.querySelector("[data-report-shape] tbody");
    expect(body).toBeTruthy();
    // ⚠ **THIS IS THE WHOLE GUARANTEE AND IT IS STRUCTURAL.** Not *"the
    // sample values look obviously fake"* — a judgement no check can make and
    // no screenshot preserves — but *"the example body has no text in it at
    // all"*. A later lane that puts `84.20` in a bar to "make it clearer"
    // turns this red on the character it added.
    expect((body?.textContent ?? "").trim()).toBe("");
    // …and the shape IS there: two columns × three rows of bars.
    expect(body?.querySelectorAll("tr")).toHaveLength(3);
    expect(body?.querySelectorAll("td")).toHaveLength(6);
  });

  it("draws nothing when there are no columns to describe", () => {
    // A heading over an empty frame is a promise with nothing behind it —
    // `ReportGapList` carries the same guard for the same reason.
    const { container } = render(
      <ReportShapePreview columns={[]} columnMeta={undefined} t={i18n.t.bind(i18n)} />,
    );
    expect(container.innerHTML).toBe("");
  });
});
