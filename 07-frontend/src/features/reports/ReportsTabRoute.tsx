// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 0 task `P0.8`
//          (*"Routes only, no screen"*). Outcome, verbatim: *"All seven
//          resolve; each reserved segment opens its own tab, not a 422"*.
// Rules:   B14 rule 43 (a piece of UI is built as a COMPONENT) · B14 rule 33
//          (a LABEL ≤ 3 words, a FACT ≤ 6 words, and RATIONALE is ZERO WORDS
//          ON SCREEN) · B14 rule 32 (a stated absence, CLOSED by default) ·
//          B14 rule 21 (Tailwind utilities; this file is on
//          `styles/route-b-migrated.txt`) · B14 rule 40 (the page-head title
//          is 32px on every screen — `PageHeader` owns it)
// Tests:   07-frontend/src/routing/reportsReservedSegments.test.tsx (`P0.11`)
// Impacts: App.tsx (the four routes) · routing/screenIds.ts (their ids)
// ───────────────────────────────────────────────────────
//
// THE FOUR RESERVED SEGMENTS OF `/reports`, AND WHY THEY EXIST BEFORE THE
// SCREENS THAT FILL THEM.
//
// ⚠ **`/reports/:reportKey` IS A CATCH-ALL OVER A TENANT-AUTHORED NAME.** A
// utility may save a report called *History*, or *Custom*, or *Dashboard* —
// those are four ordinary English words and every one of them is a plausible
// report name. Until each is a ROUTE, a user asking for the History tab gets
// the report viewer with `reportKey = "history"`, which the server refuses
// with `VAL-005`. The brief's own words: *"the catch-all swallows them and a
// user asking for History gets a report named 'history'"*.
//
// So the segments are claimed in Phase 0, when claiming them is a routing
// table entry, rather than in Phase 3, when it is a migration of everybody's
// bookmarks.
//
// ⚠ **THIS IS NOT A PLACEHOLDER WEARING A HOLD (hard-won law 2's mirror).**
// A hold is a control that refuses over a screen somewhere else; this is an
// address that answers for itself and says one true thing. The test that fires
// when it stops being true is `reportsReservedSegments.test.tsx`, which asserts
// each address resolves to THIS component and not to the viewer — so the day a
// real tab is mounted here, that test names the segment whose element changed
// and the lane updates it deliberately rather than by accident.
//
// ⚠ **THE COPY IS THREE WORDS AND FIVE WORDS, AND THAT IS RULE 33 RATHER THAN
// TERSENESS.** *Why* this tab is not here yet is RATIONALE, and rationale is
// zero words on screen. It lives in this docstring and in the brief.
import { useTranslation } from "react-i18next";

import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";

/** The four words `/reports/:reportKey` may never be allowed to swallow. */
export const RESERVED_REPORT_SEGMENTS = ["custom", "dashboard", "scheduled", "history"] as const;

export type ReservedReportSegment = (typeof RESERVED_REPORT_SEGMENTS)[number];

/**
 * One reserved `/reports` segment, rendered as itself.
 *
 * `segment` is REQUIRED and there is no default: a default would let a route
 * be mounted without saying which tab it is, and every one of these four looks
 * identical on screen until it names itself.
 */
export function ReportsTabRoute(props: { segment: ReservedReportSegment }) {
  const { t } = useTranslation();
  return (
    <div data-reports-tab={props.segment}>
      <PageHeader title={t(`reports.tab.${props.segment}.title`)} />
      <Panel>
        <p className="m-0 text-body text-text">{t("reports.tab.pending")}</p>
      </Panel>
    </div>
  );
}

export default ReportsTabRoute;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P0.8 (05-prototype/09 Reports Build Brief.pdf p8, read as images per B14 rule 42)
// screens: S45 · S47 (and the Reports dashboard tab, which A1 does not carry — see routing/screenIds.ts)
// generated: 2026-09-26 by lane REP-P0B
// checklist: A=n/a(no backend half) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — `reportsReservedSegments.test.tsx` was run against App.tsx BEFORE these routes existed and reported all four segments resolving to ReportViewerPage. G31: this file is listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) no `tab strip` is drawn — the strip is Phase 1's and a strip drawn here would be four nav words pointing at three addresses that say nothing, which is hard-won law 2's mirror · (2) the component states an absence and gives no reason, which is B14 rule 33 rather than an omission
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
