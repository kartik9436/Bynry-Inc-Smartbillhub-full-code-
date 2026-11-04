// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:   CR-142-BRC07 Phase 5 · `P5.3` (screen 2·2, the edit panel beside
//          the live table — *"Adding a column shows it in the rows below
//          without a save"*) · `P5.4` (screen 2·4, Save as) · `P5.10` (the
//          Custom sub-tab, and the `+ Build your own` action whose hold
//          expired in this commit) · `P5.11` (columns reorder and rename).
//          Screens: 1·1 · 1·2 · 2·2 · 2·4
// Rules:   PO ruling 2026-09-26 — a PANEL, not a wizard · B14 rule 43
//          (component, not inline) · rule 33 · rule 31 · hard-won law 2 and
//          its mirror (a live screen behind a dead control) · law 7 clause 2
//          (*"ask what would make this check pass wrongly"*)
// Tests:   this file
// ───────────────────────────────────────────────────────
//
// ⚠ **THE COMPONENTS ARE MOUNTED UNDER THE REAL `/:tenant/reports` PATTERN.**
// `DEF-CWP-3925`'s fixture mounted a component bare inside a `MemoryRouter`
// with no `/:tenant/portal` route, so `useParams().tenant` was undefined and
// every address the page built came out `//portal/…` — a protocol-relative URL
// to another host, which reads as a perfectly good string to `toContain`. The
// one assertion that could have caught eight dead doors could not be written.
//
// ⚠ **EVERY ASSERTION RUNS IN BOTH DIRECTIONS.** The cases below were each
// asked *what would make this pass wrongly* before being written, and the
// answer is recorded beside it.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ReportDataset } from "@/api/reportsEndpoints";
import { ReportEditPanel, draftFrom, draftToWire, moved } from "./ReportEditPanel";
import type { ReportDraftState } from "./ReportEditPanel";
import { SaveReportAsModal } from "./SaveReportAsModal";
import { REPORTS_ROUTE, reportWord } from "./reportsShared";

afterEach(cleanup);

const TENANT = "brazosbend";

/** One dataset, shaped exactly as `GET /reports/datasets` serves it. */
const DATASET: ReportDataset = {
  code: "invoices",
  owner_module: "billing",
  grain: "one invoice",
  columns: [
    { name: "account_no", type: "text", unit: null, unit_from: null, money_basis: null, scale: null },
    { name: "customer", type: "text", unit: null, unit_from: null, money_basis: null, scale: null },
    { name: "class", type: "text", unit: null, unit_from: null, money_basis: null, scale: null },
    { name: "total", type: "money", unit: null, unit_from: null, money_basis: "posting", scale: 4 },
  ],
  measures: [
    { name: "total", aggregation: "sum", additivity: "full", forbidden_across: [] },
    { name: "invoices", aggregation: "count", additivity: "full", forbidden_across: [] },
  ],
  dimensions: [
    { name: "time", attributes: ["accounting_period"], hierarchy: null, conformed: true },
    { name: "service", attributes: ["service_code"], hierarchy: null, conformed: true },
  ],
  filters: ["from", "to", "service"],
  time_hierarchy: "calendar",
  paginates: true,
};

const GROUPS = [
  {
    code: "receivables",
    name: "Receivables",
    sub_groups: [{ code: "receivables_arrears", name: "Arrears" }],
  },
  { code: "billing", name: "Billing", sub_groups: [] },
];

/** Mount a component at the REAL address pattern. See the header. */
function mountAt(element: React.ReactNode) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const router = createMemoryRouter(
    [{ path: `/:tenant${REPORTS_ROUTE}/:reportKey`, element: <>{element}</> }],
    { initialEntries: [`/${TENANT}${REPORTS_ROUTE}/ar_ageing`] },
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
// P5.3 · THE PANEL IS A PANEL — AND THE PREVIEW IS THE THING IT CHANGES
// ═══════════════════════════════════════════════════════════════════════════
describe("P5.3 · screen 2·2, the edit panel", () => {
  function panel(
    onChange: (next: ReportDraftState) => void = () => {},
    draft = draftFrom("invoices"),
  ) {
    return mountAt(
      <ReportEditPanel
        dataset={DATASET}
        datasets={[DATASET]}
        draft={draft}
        onChange={onChange}
        groups={GROUPS}
        onSaveAs={() => {}}
        onCancel={() => {}}
      />,
    );
  }

  it("ticking a column reports the change UPWARDS, which is what re-runs the preview", async () => {
    // ⚠ **THIS IS `P5.3`'s OUTCOME AT THE SEAM THAT CARRIES IT.** The rows
    // below change because the viewer puts `draft.columns` into the run query
    // (`ReportViewerPage`'s `previewColumns`), and the panel's whole
    // contribution is reporting the tick. A panel that held its ticks in its
    // OWN state and told nobody would render perfectly and change nothing —
    // hard-won law 2 exactly, and it is the failure this case exists for.
    const seen: string[][] = [];
    panel((next) => seen.push(next.columns));
    fireEvent.click(screen.getByLabelText("customer"));
    expect(seen).toHaveLength(1);
    expect(seen[0]).toContain("customer");
  });

  it("an unticked column is an EMPTY BOX and is never disabled", async () => {
    // ⚠ **THE DEFECT THE PO FOUND, ASSERTED AS THE THING THEY SAW.** p31
    // callout ②: *"An unticked column is an empty box, never greyed — grey
    // means you cannot, and these you can."* A `disabled` checkbox is exactly
    // that grey, and it reads as a refusal where the truth is *you have not*.
    panel();
    // ⚠ **`customer` AND `Account` — TWO NAMES, ONE RULE (`DEF-REP-7070`).**
    // A checkbox's accessible name is now the column's WORDS, through
    // `reportWord`: `reports.col.account_no` is authored and reads *Account*,
    // `reports.col.customer` is not authored yet and the raw name survives on
    // purpose, so a missing catalogue entry stays reportable instead of
    // becoming a blank a clerk cannot describe. Both halves are asserted here
    // rather than left in a comment.
    const box = screen.getByLabelText("customer") as HTMLInputElement;
    expect(box.checked).toBe(false);
    expect(box.disabled).toBe(false);
    // The other direction — a panel that ticked everything would pass the
    // `disabled` assertion above and prove nothing about the empty box.
    expect((screen.getByLabelText("Account") as HTMLInputElement).checked).toBe(false);
  });

  it("says how many columns there are, so the list is visibly complete", async () => {
    // p31 callout ②/④ and p32's box: *"The panel says how many columns the
    // dataset has — 7 available — so a clerk can see the list is complete
    // rather than wondering what is hidden."* Three of the four declared
    // columns are attributes; `total` is a measure and is counted with the
    // measures.
    panel(() => {}, draftFrom("invoices", { columns: ["account_no"] }));
    expect(screen.getByText("1 of 3")).toBeTruthy();
  });

  it("every filter the DATASET declares is OFFERED, and none that it does not", async () => {
    // ⚠ **THE SECURITY BOUNDARY, SEEN FROM THE SCREEN** (§8.1). The panel
    // offers what the declaration carries and nothing else, so a clerk cannot
    // reach past what a reviewed dataset produces. The count is read off the
    // same list, so the screen and the engine cannot be counting different
    // things — which is what the six hand-typed maps `P0.7` deleted were doing.
    //
    // ⚠ **AMENDED 2026-09-28 BY LANE REP-EDITOR-PAGE (`DEF-REP-7080`), AND
    // THIS CASE WAS PINNING THE DEFECT.** It asserted a rendered INPUT per
    // declared filter — which is the section drawing one stacked row per
    // declaration, thirteen deep on the statement, where p031 §4 draws only
    // the filters carrying a value and then `+ Add filter`. **The guarantee
    // this case exists for has not moved one inch**: the offer is still
    // `DATASET.filters`, still in the declaration's own order, still spelled
    // in a clerk's words (`DEF-REP-7070`) and still nothing else. Only WHERE
    // the offer is drawn has moved — from thirteen inputs to the options of
    // one `+ Add filter` control.
    panel();
    expect(screen.getByText("3 available")).toBeTruthy();
    const offer = screen.getByRole("combobox", {
      name: i18n.t("reports.edit.addFilter"),
    }) as HTMLSelectElement;
    const offered = Array.from(offer.options)
      .map((option) => option.value)
      .filter((value) => value !== "");
    expect(offered).toEqual([...DATASET.filters]);
    // …and each one by its WORDS, not by its stored name.
    const words = Array.from(offer.options)
      .map((option) => option.textContent)
      .filter((text) => text !== `+ ${i18n.t("reports.edit.addFilter")}`);
    for (const name of DATASET.filters) {
      expect(words).toContain(reportWord(name, i18n.t.bind(i18n)));
    }
    expect(offered).not.toContain("ballance");
    // ⚠ **AND NOT ONE FILTER ROW IS DRAWN UNTIL A CLERK ADDS ONE.** That is
    // the defect this case used to require.
    expect(document.querySelectorAll("[data-report-filter]")).toHaveLength(0);
  });

  it("offers three group levels and no more", async () => {
    // `P2.17` — three at most, and the server refuses a fourth at save. A
    // panel offering four would let a clerk build something that is refused
    // only after they press Save.
    panel();
    expect(screen.getByLabelText("Level 1")).toBeTruthy();
    expect(screen.getByLabelText("Level 3")).toBeTruthy();
    expect(screen.queryByLabelText("Level 4")).toBeNull();
  });

  it("shows no database id anywhere on the panel (B14 rule 31)", async () => {
    // A definition carries a `key` AND an `id`, and neither is the visible
    // value of a field. The panel names the DATASET and the COLUMNS, which are
    // vocabulary rather than identifiers.
    const { container } = panel();
    expect(container.textContent ?? "").not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    );
  });

  it("says nothing about WHY a built-in is copied — rationale is zero words", async () => {
    // B14 rule 33. The reason lives in `definitions.py` and in this file's
    // header; a panel that explained copy-on-write on screen would break rule
    // 33 while trying to be helpful, which is the `CorrectionRetentionNote`
    // defect one screen over.
    const { container } = panel();
    expect(container.textContent ?? "").not.toMatch(/because|copy-on-write|platform row/i);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// P5.11 · REORDER AND RENAME — DEFINITION DATA, NOT A DATASET CHANGE
// ═══════════════════════════════════════════════════════════════════════════
describe("P5.11 · a column can move left and its heading can change", () => {
  it("`moved` walks a name one place in either direction and refuses the ends", () => {
    // Arithmetic, asserted directly. `P5.11`'s outcome is *"Account can become
    // Account No and move left, without touching code"* — this is the *move
    // left* half, and asserting it on the function means it is true whether the
    // affordance is a drag, a pair of buttons or a keyboard shortcut.
    expect(moved(["a", "b", "c"], "b", -1)).toEqual(["b", "a", "c"]);
    expect(moved(["a", "b", "c"], "b", 1)).toEqual(["a", "c", "b"]);
    // The ends are NOT wrapped — a column that jumped from first to last on a
    // stray click would look exactly like a bug.
    expect(moved(["a", "b", "c"], "a", -1)).toEqual(["a", "b", "c"]);
    expect(moved(["a", "b", "c"], "c", 1)).toEqual(["a", "b", "c"]);
    // And an unknown name changes nothing rather than throwing.
    expect(moved(["a", "b"], "zz", 1)).toEqual(["a", "b"]);
  });

  it("a rename travels on the DEFINITION and names no new column", () => {
    // ⚠ **THE OTHER HALF OF `P5.11`.** `Account` becoming `Account No` reads
    // no new column and changes no query — it is a heading a utility chose. So
    // it rides in `filters` under one reserved key the runner already passes
    // through, and `columns` is untouched: a rename that quietly added a
    // column name would be refused at save for a column the clerk never typed.
    const draft = draftFrom("invoices", {
      columns: ["account_no"],
      renames: { account_no: "Account No" },
      group: "billing",
    });
    const wire = draftToWire(draft, "Overdue 60+", "ar_ageing");
    expect(wire.columns).toEqual(["account_no"]);
    expect(JSON.parse(String(wire.filters?.renames))).toEqual({ account_no: "Account No" });
    expect(wire.based_on).toBe("ar_ageing");
  });

  it("a draft with no renames sends no renames key at all", () => {
    // The other direction: an empty map would be a filter the dataset does not
    // declare arriving on every single save, which the server passes through
    // only because the key is on its bookkeeping list. Sending nothing is what
    // keeps that list honest.
    const wire = draftToWire(draftFrom("invoices", { group: "billing" }), "X", null);
    expect(wire.filters?.renames).toBeUndefined();
  });

  it("private is the default on a draft — the ruling, not the column", () => {
    // `BR-REP-019` / `P5.7`. The COLUMN has no database default at all
    // (measured on PostgreSQL 16 by
    // `10-scripts/rep_p5_isolation_and_savepoint_proof.py`), so this constant
    // and the server's `DEFAULT_TENANT_VISIBILITY` are the whole of the rule.
    expect(draftFrom("invoices").visibility).toBe("private");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// P5.4 · SAVE AS — A FormModal, FOUR FIELDS, PRIVATE BY DEFAULT
// ═══════════════════════════════════════════════════════════════════════════
describe("P5.4 · screen 2·4", () => {
  function saveAs(onSave = async () => ({}) as never) {
    return mountAt(
      <SaveReportAsModal
        initialName="Overdue 60+"
        initialGroup="receivables"
        initialSubGroup="receivables_arrears"
        groups={GROUPS}
        onSave={onSave}
        onSaved={() => {}}
        onClose={() => {}}
      />,
    );
  }

  it("draws FOUR fields, which is the drawing's count and not the summary's", async () => {
    // ⚠ The task table says *"name, category, visibility"* — three. p35's own
    // FIELDS row says **Four**: Name · Group · Sub-group · Visible to. The
    // drawing is the specification (B14 rule 42) and this is the case that
    // would have caught the summary being followed instead.
    saveAs();
    await settle();
    expect(screen.getByLabelText(/Name/i)).toBeTruthy();
    expect(screen.getByLabelText(/^Group/i)).toBeTruthy();
    expect(screen.getByLabelText(/Sub-group/i)).toBeTruthy();
    expect(screen.getByLabelText(/Visible to/i)).toBeTruthy();
  });

  it("opens on *Only me* — the ruling, and it is not a preference", async () => {
    // `BR-REP-019`, brief §8: *"a half-finished report appearing on a
    // colleague's catalogue is how people stop saving."*
    saveAs();
    await settle();
    const control = screen.getByLabelText(/Visible to/i) as HTMLSelectElement;
    expect(control.value).toBe("private");
    // The other direction — a control with only one option would pass the
    // assertion above and make the ruling unexpressible.
    expect(control.querySelectorAll("option").length).toBeGreaterThan(1);
  });

  it("says *Share it later.* and explains nothing (rule 33)", async () => {
    saveAs();
    await settle();
    expect(i18n.t("reports.saveAs.shareLater")).toBe("Share it later.");
    expect(document.body.textContent ?? "").not.toMatch(/because|colleague|half-finished/i);
  });

  it("is not a WizardFrame — no numbered rail, no step count", async () => {
    // ⚠ **THE TASK ROW'S OWN ⚠, ASSERTED.** *"A `FormModal`, the shared one —
    // NEVER `WizardFrame`."* p34 callout ①: *"The report and its parameters are
    // already chosen — you are standing on them. Three fields do not need a
    // rail."* A wizard here would also have broken the PO's 2026-09-26 ruling
    // about the panel, one screen along.
    const { container } = saveAs();
    await settle();
    expect(container.querySelector("[data-wizard-frame]")).toBeNull();
    expect(container.querySelector("[data-wizard-rail]")).toBeNull();
    expect(document.body.textContent ?? "").not.toMatch(/Step \d of \d/i);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 Phase 5 (05-prototype/09 Reports Build Brief.pdf p16-p17 the task table, p20-p23 screens 1·1 and 1·2, p31-p33 screen 2·2, p35 screen 2·4 — all read as IMAGES per B14 rule 42) · PO ruling 2026-09-26 "panel, not wizard"
// screens: 1·1 · 1·2 · 2·2 · 2·4
// generated: 2026-09-27 by lane REP-P5
// gates: RED PROVED FIRST — the whole file was run against the branch BEFORE ReportEditPanel.tsx and SaveReportAsModal.tsx existed and failed at import; each behavioural case was then run against a deliberately broken component (a panel holding its ticks in its own state, a disabled checkbox, a three-field dialog) and shown to fail by name. Quoted in the lane report.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
