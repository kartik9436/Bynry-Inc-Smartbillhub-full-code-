// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 4 `P4.11`. Screen `3·1` region ⑨, drawn on p037
//          and annotated on p037 ⑨, read as IMAGES per B14 rule 42.
// Rules:   B14 rule 43 · rule 21 · rule 31 (no database id on screen) ·
//          BR-LED-007 (the Close Pack's verdict is the ledger's) ·
//          CLAUDE.md hard rule 2 (money DISPLAY 2)
// Tests:   07-frontend/src/features/reports/reportsDashboard.dom.test.tsx
// Impacts: ReportsDashboardPage.tsx
// ───────────────────────────────────────────────────────
//
// `Is the month closed?` — THE ONE PANEL ON THIS SCREEN THAT CAN BE RED.
//
// ⚠ **AND IT IS AT THE BOTTOM ON PURPOSE.** p037 ⑨, verbatim: *"the one panel
// that can be red, and it is at the bottom on purpose: a dashboard that opens
// on a problem gets ignored, and one that never shows a problem gets ignored
// faster."*
//
// ⚠ **THE VERDICT IS THE REPORT'S OWN FIELD AND IS NEVER RE-DERIVED HERE.**
// `close_pack` publishes `result` per row and `release_blocked` over the set.
// A panel that decided *red* from a non-zero `difference` would be a second
// opinion about a release blocker — DEF-104's shape, where four surfaces each
// computed one balance and each was internally consistent. It would also come
// out GREEN for an UNVERIFIABLE check, one that never ran at all, because its
// difference is absent rather than large.
//
// ⚠ **EVERY CELL CARRIES HORIZONTAL PADDING, AND THE FIRST DRAFT DID NOT.**
// Photographed at 1440 before this line: the head read **`DifferenceResult`**
// and the row read **`$0.00Foots`** — two columns touching, with nothing
// between them. `tsc`, the dom test and every gate passed, because a `<td>`
// with no padding is a perfectly good `<td>` and the text it contains is
// exactly right. It is CLAUDE.md hard-won law 6 in one line: no gate in this
// repo looks at rendered output, and this was found by looking.
//
// ⚠ **THE TONE IS THE RESULT'S, AND EVERY CLASS IS A WHOLE STRING.** Tailwind's
// scanner cannot see `text-${tone}-700`; an interpolated class is emitted by
// nothing and renders as no colour at all while every `toContain` assertion
// still passes — the fault `AgeingCards` records in its own header.
import { useTranslation } from "react-i18next";

import { MoneyCell } from "@/components/MoneyCell";

import type { TieOutRow } from "@/api/dashboardTabEndpoints";

/** The result word's colour. `agreed` is deliberately NOT green: a tie-out that
 *  foots is the ordinary case, and colouring the ordinary case makes the one
 *  exception harder to find. */
const RESULT_TONE: Record<string, string> = {
  agreed: "text-neutral-900",
  drifting: "text-danger-700",
  unverifiable: "text-warning-700",
};

export interface MonthClosedPanelProps {
  checks: readonly TieOutRow[];
  currency: string | null;
  locale?: string;
}

export function MonthClosedPanel(props: MonthClosedPanelProps) {
  const { t } = useTranslation();
  return (
    <table className="w-full border-collapse text-sm" data-panel-body="month_closed">
      <thead>
        <tr className="border-b border-divider text-left text-neutral-600">
          <th scope="col" className="px-3 py-2 font-semibold">
            {t("reports.dashboard.tieOut.check")}
          </th>
          <th scope="col" className="px-3 py-2 text-right font-semibold">
            {t("reports.dashboard.tieOut.ours")}
          </th>
          <th scope="col" className="px-3 py-2 text-right font-semibold">
            {t("reports.dashboard.tieOut.theirs")}
          </th>
          <th scope="col" className="px-3 py-2 text-right font-semibold">
            {t("reports.dashboard.tieOut.difference")}
          </th>
          <th scope="col" className="px-3 py-2 font-semibold">
            {t("reports.dashboard.tieOut.result")}
          </th>
        </tr>
      </thead>
      <tbody>
        {props.checks.map((row) => (
          <tr key={row.check} className="border-b border-divider" data-tie-out={row.check}>
            <td className="px-3 py-2 text-neutral-900">
              {t(`reports.dashboard.check.${row.check}`, { defaultValue: row.check })}
            </td>
            {([row.ours, row.theirs, row.difference] as const).map((amount, index) => (
              <td key={index} className="px-3 py-2 text-right tabular-nums text-neutral-900">
                {amount === null ? (
                  t("reports.dashboard.noFigure")
                ) : (
                  <MoneyCell
                    amount={amount}
                    currency={props.currency ?? "USD"}
                    locale={props.locale}
                  />
                )}
              </td>
            ))}
            <td
              className={`px-3 py-2 ${RESULT_TONE[row.result] ?? "text-neutral-900"}`}
              data-tie-out-result={row.result}
            >
              {t(`reports.dashboard.result.${row.result}`, { defaultValue: row.result })}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default MonthClosedPanel;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P4.11 (05-prototype/09 Reports Build Brief.pdf p37 region ⑨, read as IMAGES per B14 rule 42)
// screens: 3·1
// generated: 2026-09-27 by lane REP-P4-DASH
// checklist: A=n/a(no backend half) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — reportsDashboard.dom.test.tsx reported `Cannot find module './dashboard/MonthClosedPanel'` before this file existed. G31: listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) this is a plain `<table>` and NOT `DataTable` — p37 TABLE CONTROLS, verbatim: *"None. No panel here is a table in the `DataTable` sense — no search, no paging, no column picker. The full report has all four."* A `DataTable` here would draw a toolbar the drawing rules out
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
