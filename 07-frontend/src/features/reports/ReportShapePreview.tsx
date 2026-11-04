// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-REP-7070 — Product Owner, deployed v2.380.3, on screen 2·2:
//          *"report editor is not user friendly — as a user I don't know what
//          I'm doing and how fields are shown — no edit no adds"*.
// Screens: 2·2 (A1 S47) — the edit panel beside the live table
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT) · rule 44 (our kit and
//          our tokens win) · rule 33 (a LABEL ≤ 3 words · a FACT ≤ 6 words ·
//          RATIONALE is ZERO words on screen) · rule 32 (one sentence per
//          section) · rule 21 (Tailwind utilities; listed in
//          route-b-migrated.txt) · hard rule 2 (money displays at 2 decimals —
//          which is why NO FIGURE APPEARS HERE AT ALL)
// Tests:   07-frontend/src/features/reports/reportShapePreview.dom.test.tsx
// Impacts: ReportViewerPage.tsx (draws it under an empty table while editing)
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHY THIS DRAWS BARS AND NOT SAMPLE ROWS                                 ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// The task was *"where the real query returns nothing, show a few example rows
// so the shape is visible while a person builds"*, with the condition that
// **a clerk must never mistake them for their utility's data.**
//
// ⚠ **THE SKILL FILE FORBIDS THE OBVIOUS IMPLEMENTATION BY NAME**, and it is
// right to: *"❌ Filling an empty state with placeholder or sample data."* An
// invented `AC-2026-00041 · 84.20` on a money screen is a figure somebody will
// eventually read, quote or reconcile — and this product's whole posture is
// that a wrong number is worse than no number (`queries._report`: *"a confident
// wrong fact is worse than having none"*).
//
// ⚠ **SO THE EXAMPLE CONTAINS NO CHARACTERS.** Each cell is a grey bar. It
// carries the thing a person building a report actually needs — how many
// columns there are, in what order, how wide each one is and which are
// right-aligned — and it carries NOTHING that can be read as a value, in any
// language, by any reader, ever. That is not a weaker guarantee than a
// disclaimer; it is a structural one, and it is the only kind that survives a
// screenshot being pasted into an email.
//
// ⚠ **AND IT IS NAMED, BECAUSE A BAR ALONE MEANS *LOADING*.** The kit's
// `LoadingSkeleton` draws bars for a list that is fetching, so bars with no
// heading over them would state the one thing that is false here — that rows
// are on their way. The heading is the word **Example** and the line under it
// is a FACT of five words. Both are removed the instant a row exists.
//
// ⚠ **IT IS DRAWN ONLY WHILE EDITING.** A clerk READING a report that returns
// nothing is told *No rows match* and is not shown a diagram of a table they
// did not ask to design. The shape is a builder's tool, and `?edit=1` is what
// says somebody is building.
import { Panel } from "@/components/Panel";
import { PlainTable } from "@/components/Surfaces";
import type { ReportColumnMeta } from "@/api/reportsEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

/** The kinds that read right-aligned — the same two `ReportCell` right-aligns. */
const NUMERIC = new Set(["money", "quantity", "percent", "count"]);

/** Three bar widths, cycled, so the example does not read as one grey block. */
const WIDTHS = ["w-full", "w-3/4", "w-1/2"];

/**
 * THE SHAPE OF A REPORT THAT HAS NO ROWS YET — columns, order, alignment.
 *
 * Draws nothing at all when there are no columns to show: an empty frame under
 * a heading is a promise with nothing behind it (`ReportGapList` carries the
 * same guard for the same reason).
 */
export function ReportShapePreview(props: {
  columns: readonly { key: string; label: string }[];
  columnMeta: Record<string, ReportColumnMeta> | undefined;
  t: Translator;
}) {
  const { t } = props;
  if (props.columns.length === 0) {
    return null;
  }
  return (
    <Panel>
      <div className="fin-panel-head">
        {/* A LABEL — one word, no sentence (rule 33). */}
        <h3>{t("reports.shape.title")}</h3>
      </div>
      {/* A FACT — five words. NOT rationale: it says what is on screen, not
          why the product works this way. */}
      <p className="mb-3 text-sm text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
        {t("reports.shape.fact")}
      </p>
      <PlainTable data-report-shape="">
        <thead>
          <tr>
            {props.columns.map((column) => (
              <th
                key={column.key}
                className={
                  NUMERIC.has(props.columnMeta?.[column.key]?.type ?? "") ? "fin-num" : undefined
                }
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody aria-hidden="true">
          {/* ⚠ `aria-hidden` on the BODY and never on the head. A screen
              reader hears the heading, the sentence and the column names —
              every word that carries meaning — and is not read three rows of
              nothing. */}
          {[0, 1, 2].map((row) => (
            <tr key={row}>
              {props.columns.map((column, index) => (
                <td key={column.key}>
                  <span
                    className={`block h-3 bg-[color-mix(in_srgb,var(--color-text)_10%,transparent)] ${
                      WIDTHS[(row + index) % WIDTHS.length]
                    }`}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </PlainTable>
    </Panel>
  );
}

export default ReportShapePreview;

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-REP-7070 (PO report, deployed v2.380.3, 2026-09-27) · CR-142-BRC07 Phase 5 `P5.3`
// screens: 2·2 (A1 S47)
// generated: 2026-09-27 by lane REP-EDITOR-A
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — reportShapePreview.dom.test.tsx was shown red on every case before this file existed. G31: this file is listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) the task asked for EXAMPLE ROWS and this draws bars — the skill file forbids placeholder data by name, and a bar carries the shape without carrying a figure anybody could read as their utility's money. The difference is recorded here rather than resolved quietly · (2) the body is `aria-hidden`: three rows of nothing are noise to a screen reader, and every word that carries meaning is outside it
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
