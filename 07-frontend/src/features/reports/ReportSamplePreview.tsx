// ── Trace ──────────────────────────────────────────────
// Change:  PO ruling 2026-09-28 — *"the report editor — panel or its own page
//          - own page"* (12-governance/02-decision-log.md). The ruling hands
//          ONE thing to whoever builds it: *"Whoever builds it owes an answer
//          to what does the clerk see while they are choosing."*
// Screens: 2·2 (A1 S47) — the report builder, now its own address
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT — this is why the page is
//          not 120 lines of table inline) · rule 44 (our kit and our tokens
//          win over the drawing, every time) · rule 33 (a LABEL ≤ 3 words · a
//          FACT ≤ 6 words · RATIONALE is ZERO words on screen) · rule 32 (one
//          sentence per section) · rule 31 (no database id is ever a visible
//          value) · rule 21 (Tailwind utilities; listed in
//          route-b-migrated.txt) · hard rule 2 (money displays at 2 decimals —
//          which `ReportCell` and `MoneyCell` own, and this file re-implements
//          nothing of)
// Tests:   07-frontend/src/features/reports/reportEditorPage.dom.test.tsx
// Impacts: ReportEditorPage.tsx (draws it beside the sections)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  THE REPORT'S OWN FIRST FIVE ROWS, WHILE IT IS BEING DESCRIBED           ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// ⚠ **THIS EXISTS BECAUSE THE PAGE COST THE LIVE TABLE AND THE PO ACCEPTED
// THAT COST WITH ITS PRICE IN FRONT OF THEM.** The panel was ruled on
// 2026-09-26 for one reason, in the Reports Build Brief's own words (p3):
// *"commit-at-the-end means you cannot see your report until you have finished
// describing it."* A page that answers nothing while a clerk works is the
// wizard that ruling refused, rebuilt at a new address.
//
// ⚠ **SO THE PAGE KEEPS THE ANSWER AND GIVES UP THE FURNITURE.** What a person
// building a report needs to see is *which columns, in what order, reading
// which way, over rows that are really mine*. What they do not need is a
// toolbar, a search box, a pager, a KPI band, an export button and fifty rows
// — every one of which belongs to the report a clerk is READING (2·1) and none
// of which is a decision they are making here. This draws the columns and five
// rows, and nothing else at all.
//
// ⚠ **THE ROWS ARE REAL AND THAT IS NOT THE SAME DECISION `ReportShapePreview`
// MADE.** That component draws grey bars, deliberately, because it fires where
// the query returned NOTHING and the only alternative there is an invented
// figure on a money screen. Here the server has answered with the tenant's own
// rows, run with the draft's own columns; there is nothing to invent. The two
// are a pair and the page picks between them on `rows.length`, so a clerk
// always has a shape in front of them and never a made-up number.
//
// ⚠ **IT RE-RENDERS NOTHING OF ITS OWN.** Every cell goes through `ReportCell`
// — the same function 2·1's table calls — so the preview and the report cannot
// disagree about a date format, a currency, a unit or a dash. A second
// renderer here would be the `7 of 5` defect one layer out: two derivations of
// one fact, drifting.
import { PlainTable } from "@/components/Surfaces";
import { Panel } from "@/components/Panel";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { ReportResponse, ReportRow } from "@/api/reportsEndpoints";
import { isReportGroupRow } from "@/api/reportsEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

import { ReportCell } from "./ReportViewerPage";
import { reportWord } from "./reportsShared";

/** The kinds that read right-aligned — the same set `ReportShapePreview` uses,
 *  and the same two `ReportCell` right-aligns. */
const NUMERIC = new Set(["money", "quantity", "percent", "count"]);

/** How many rows a preview is. Five is what the FACT on screen says, so the
 *  two can never disagree — change one and `reports.edit.preview.fact` moves
 *  with it, in all eleven catalogues. */
export const PREVIEW_ROWS = 5;

export function ReportSamplePreview(props: {
  report: ReportResponse;
  reportKey: string;
  t: Translator;
  locale?: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { report, t } = props;
  // ⚠ **FACT ROWS ONLY, AND A SUBTOTAL IS NOT ONE.** A grouped report
  // interleaves `ReportGroupRow`s among its rows, and a group row carries a
  // label and a subtotal rather than a value per column — 2·1 draws them
  // through `GroupLabelCell`/`GroupSubtotalCell` and a disclosure this preview
  // deliberately does not have. Five *rows of the report* is what the FACT on
  // screen promises, so the group rows are skipped rather than drawn as five
  // lines of dashes.
  const rows: ReportRow[] = [];
  for (const row of report.rows) {
    if (isReportGroupRow(row)) continue;
    rows.push(row);
    if (rows.length === PREVIEW_ROWS) break;
  }
  return (
    <Panel>
      <div className="fin-panel-head">
        {/* A LABEL — one word, no sentence (rule 33). */}
        <h3>{t("reports.edit.preview.title")}</h3>
      </div>
      {/* A FACT — five words. It says what is on screen, not why the product
          works this way, which is the line rule 33 actually draws. */}
      <p className="mb-3 text-sm text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
        {t("reports.edit.preview.fact")}
      </p>
      {/* ⚠ **THE TABLE SCROLLS INSIDE ITS OWN CONTAINER, NEVER THE PAGE.** A
          twelve-column register beside a column of sections is wider than the
          measure at 1280, and a staff page that scrolls sideways is the one
          thing the skill's §6 forbids at both supported widths. */}
      <div className="overflow-x-auto">
        <PlainTable data-report-sample="">
          <thead>
            <tr>
              {report.columns.map((column) => (
                <th
                  key={column}
                  className={
                    NUMERIC.has(report.column_meta?.[column]?.type ?? "") ? "fin-num" : undefined
                  }
                >
                  {/* ⚠ **A UTILITY'S OWN HEADING WINS, AND IT IS THE SERVER'S
                      WORD FOR IT.** `reportWord` is the one naming path on this
                      screen — the same function the checkbox beside it and 2·1's
                      own column heading call (`DEF-REP-7070`). */}
                  {reportWord(column, t)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              // ⚠ **THE INDEX IS THE KEY AND THAT IS DELIBERATE** (B14 rule
              // 31). A report row carries a record id on some datasets and
              // none on others, and five rows in source order need no identity
              // — reaching for one would put a database id one careless render
              // away from being drawn.
              <tr key={index}>
                {report.columns.map((column) => (
                  <td
                    key={column}
                    className={
                      NUMERIC.has(report.column_meta?.[column]?.type ?? "") ? "fin-num" : undefined
                    }
                  >
                    <ReportCell
                      reportKey={props.reportKey}
                      column={column}
                      value={row[column]}
                      currency={report.currency}
                      meta={report.column_meta?.[column]}
                      t={t}
                      locale={props.locale}
                      timeZone={props.timeZone}
                      dateFormat={props.dateFormat}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </PlainTable>
      </div>
    </Panel>
  );
}

export default ReportSamplePreview;

// ── Lifecycle ─────────────────────────────────────────────
// packet: PO ruling 2026-09-28 (12-governance/02-decision-log.md) · CR-142-BRC07 Phase 5 `P5.3` · 05-prototype/09 Reports Build Brief.pdf p031-p033 read as IMAGES per B14 rule 42
// screens: 2·2 (A1 S47)
// generated: 2026-09-28 by lane REP-EDITOR-PAGE
// checklist: A=n/a(no backend half) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — reportEditorPage.dom.test.tsx was shown red on every case before this file existed. G31: this file is listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) it draws NO toolbar, pager, search, KPI band or export — those belong to 2·1, and the drawing's *"the table below IS 2·1, running live"* describes a PANEL beside that table, which the 2026-09-28 ruling replaced · (2) five rows rather than the server's page: a preview is a shape, and fifty rows push the sections off the screen they are meant to be read beside
// status: VERIFIED-UNRATIFIED
