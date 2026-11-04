// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 4 `P4.11`. Screen `3·1` region ⑧, drawn on p036
//          and annotated on p037 ⑧, read as IMAGES per B14 rule 42.
// Rules:   B14 rule 43 · rule 33 (a FACT ≤ 6 words; RATIONALE is ZERO words on
//          screen) · rule 31 (an ACCOUNT NUMBER is not a database id) ·
//          BR-REP-024 (an absent figure is an absence WITH its reason) ·
//          CLAUDE.md hard rule 3 (a quantity carries its unit)
// Tests:   07-frontend/src/features/reports/reportsDashboard.dom.test.tsx
// Impacts: ReportsDashboardPage.tsx
// ───────────────────────────────────────────────────────
//
// `Biggest movers` — THE PANEL THAT SHOWS NOTHING TODAY, AND SAYS SO.
//
// ⚠ **THE REPORT OPENS AND THE RANKING IS NOT PUBLISHED, AND THOSE ARE TWO
// DIFFERENT SENTENCES.** p037 ⑧ wants *top 3 by change · ⚠ one service at a
// time, always — ranking gallons against kilowatt-hours is the commonest way a
// usage report lies*. `usage_and_ranking` (R30) is producible on this
// deployment and serves the READS themselves, measured before this file was
// written. What no definition in the catalogue publishes is a per-account
// comparison of usage BETWEEN TWO PERIODS. Deriving one here is precisely the
// arithmetic p038 forbids: *"⚠ Nothing on this screen computes anything. The
// moment a panel does its own arithmetic, the dashboard and the report start
// disagreeing, and the utility stops trusting both."*
//
// ⚠ **SO THE DOOR STAYS OPEN.** The panel draws no rows and its LINK is live,
// because the report itself opens onto real rows. A panel that hid its link
// would be telling the reader the report is unavailable, which is false.
//
// ⚠ **AND THE SENTENCE ON SCREEN IS SIX WORDS AND CARRIES NO PROVENANCE.**
// B14 rule 33 puts RATIONALE at ZERO words on screen — no rule id, no report
// code, no paragraph about grain. Why it is absent is in this docstring and in
// the server's `unavailable` entry, which is where an agent looks.
//
// ⚠ **THE COLUMNS ARE KEPT IN THIS FILE RATHER THAN DELETED.** p037 draws
// ACCOUNT · CUSTOMER · USAGE · CHANGE, and the day a definition publishes the
// ranking this component has one place to fill rather than a shape to
// rediscover from a PDF. They are a comment, not dead code — a rendered empty
// table would be furniture that reads as a working panel with no data.
import { useTranslation } from "react-i18next";

export interface BiggestMoversPanelProps {
  /** The six-word sentence for why there are no rows. Already translated. */
  absence: string;
}

/** p037 ⑧'s four drawn columns, recorded for the lane that fills this panel:
 *  **ACCOUNT · CUSTOMER · USAGE · CHANGE**, top three by change, one service at
 *  a time. The ACCOUNT column is an account NUMBER — a business identifier a
 *  clerk quotes — and never the row's uuid (B14 rule 31). */
export const MOVERS_COLUMNS = ["account_no", "customer_name", "usage", "change_pct"] as const;

export function BiggestMoversPanel(props: BiggestMoversPanelProps) {
  const { t } = useTranslation();
  return (
    <p className="m-0 text-sm text-neutral-600" data-panel-body="biggest_movers">
      {props.absence || t("reports.dashboard.noFigure")}
    </p>
  );
}

export default BiggestMoversPanel;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P4.11 (05-prototype/09 Reports Build Brief.pdf p36 region ⑧ · p37 ⑧, read as IMAGES per B14 rule 42)
// screens: 3·1
// generated: 2026-09-27 by lane REP-P4-DASH
// checklist: A=n/a(no backend half) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — reportsDashboard.dom.test.tsx reported `Cannot find module './dashboard/BiggestMoversPanel'` before this file existed. G31: listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) the panel draws NO ROWS and keeps its link. No definition publishes a period-over-period per-account usage comparison; deriving one is the arithmetic p38 forbids. REPORTED as `usage_movers_are_not_published` on the payload and filed as a defect so it is countable rather than re-discovered
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
