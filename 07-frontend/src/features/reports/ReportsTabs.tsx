// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 3 `P3.2`. Drawing
//          p39 (screen `5·1`), read as an IMAGE per B14 rule 42.
// Rules:   B14 rule 43 (a piece of UI is built as a COMPONENT) · B14 rule 33
//          (a LABEL ≤ 3 words) · B14 rule 21 (Tailwind utilities only) ·
//          CLAUDE.md hard-won law 2's mirror (a live screen behind a dead
//          control, and its twin: a live nav word over a screen that is not
//          built)
// Tests:   07-frontend/src/features/reports/runHistory.dom.test.tsx
// Impacts: RunHistoryPage.tsx · ReportLibraryPage.tsx (the door in)
// ───────────────────────────────────────────────────────
//
// THE `/reports` TAB STRIP — AND THE TAB THAT IS STILL DELIBERATELY NOT IN IT.
//
// The drawing on p39 shows FOUR words: *Catalogue · Dashboard · Scheduled · 4 ·
// History*. This strip draws all four as of `P4.11`; the history of how each
// one arrived is below, because each arrival is a hold expiring and the next
// lane needs to know what that looked like.
//
// ── `CR-142-BRC07` `P4.5` (2026-09-27) · `Scheduled` ARRIVES ──────────────
//
// ⚠ **THE HOLD ON `Scheduled` HAS EXPIRED AND THIS IS THE COMMIT THAT CLOSES
// IT, WHICH IS THE WHOLE POINT OF HAVING WRITTEN THE TEST.** Until today
// `/reports/scheduled` resolved to `ReportsTabRoute`'s *"Arrives in a later
// release."* placeholder and this strip refused to draw a nav word over it —
// the exact fault CLAUDE.md records as hard-won law 2's mirror, where the
// customer portal shipped with *"two working doors out of eight"*. `P4.5`
// mounts `ScheduledTab` at that address, so the expiry case in
// `runHistory.dom.test.tsx` went RED and NAMED the segment, exactly as it was
// written to. The tab is added here deliberately rather than being owed for
// ever, and the expired case is deleted in the same commit — a hold test that
// outlives its hold is the next reader's false alarm.
//
// ── `CR-142-BRC07` `P4.11`–`P4.13` (2026-09-27) · `Dashboard` ARRIVES ────
//
// ⚠ **THE LAST HOLD ON THIS STRIP HAS EXPIRED AND THIS IS THE COMMIT THAT
// CLOSES IT.** Until today `/reports/dashboard` resolved to `ReportsTabRoute`'s
// placeholder and this strip refused to draw a nav word over it. `P4.11` mounts
// `ReportsDashboardPage` at that address, so THREE hold cases went RED and each
// named the segment in its own failure message — `runHistory.dom.test.tsx`,
// `phaseHolds.dom.test.tsx` and `routing/reportsReservedSegments.test.tsx`. All
// three were run and READ before any of them was edited, which is the whole
// point of having written them, and all three expired cases are deleted in this
// same commit: a hold test that outlives its hold is the next reader's false
// alarm.
//
// ⚠ **IT POINTS AT `/reports/dashboard` AND NEVER AT `DASHBOARD_ROUTE`.** There
// is also a `DashboardPage`, at the shell's own address — a different screen,
// fenced by PO ruling (p36: *"dont replace existing one"*). Pointing this tab
// at it would silently redefine which screen the drawing's word means.
//
// ⚠ **SO THE STRIP NOW DRAWS ALL FOUR WORDS THE DRAWING SHOWS**, and the only
// remaining divergence from p39 is the count badge below.
//
// ⚠ **THE COUNT BADGE p39 DRAWS ON `Scheduled · 4` IS NOT DRAWN.** The strip
// takes a static label list and the count is a fact about a server page this
// component never fetches; wiring one here would make every screen that mounts
// the strip issue a schedules query to decorate a tab. DIVERGENCE FROM p39,
// REPORTED.
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { SubTabs } from "@/components/SubTabs";

import { REPORTS_ROUTE } from "./reportsShared";

export const DASHBOARD_TAB_SEGMENT = "dashboard";
export const DASHBOARD_TAB_ROUTE = `${REPORTS_ROUTE}/${DASHBOARD_TAB_SEGMENT}`;
export const HISTORY_SEGMENT = "history";
export const HISTORY_ROUTE = `${REPORTS_ROUTE}/${HISTORY_SEGMENT}`;
export const SCHEDULED_SEGMENT = "scheduled";
export const SCHEDULED_ROUTE = `${REPORTS_ROUTE}/${SCHEDULED_SEGMENT}`;

/** The tabs that have a screen behind them today, in the drawing's order.
 *
 * ⚠ **THE ORDER IS p39's AND `Scheduled` GOES BEFORE `History`, NOT AFTER.**
 * The drawing reads *Catalogue · Dashboard · Scheduled · History*, and p38
 * says why in one sentence: *"A schedule is a run that has not happened yet; a
 * run is a schedule that fired."* Appending a new tab to the end because that
 * is where new things go would put the future after the past. */
export const LIVE_REPORT_TABS = [
  { id: "catalogue", path: REPORTS_ROUTE },
  { id: DASHBOARD_TAB_SEGMENT, path: DASHBOARD_TAB_ROUTE },
  { id: SCHEDULED_SEGMENT, path: SCHEDULED_ROUTE },
  { id: HISTORY_SEGMENT, path: HISTORY_ROUTE },
] as const;

export type ReportTabId = (typeof LIVE_REPORT_TABS)[number]["id"];

/**
 * The strip above every `/reports` screen.
 *
 * ⚠ **IT NAVIGATES BY ADDRESS, AND THE ADDRESS IS TENANT-SCOPED.** Every
 * screen in this product lives under `/:tenant/…`, and a strip that built
 * `/reports/history` without the tenant produces a protocol-relative URL that
 * `toContain` reads as a perfectly good string — the fixture fault CLAUDE.md
 * records under hard-won law 2. So the tenant comes off `useParams` and a
 * missing one is a bug the tests mount for, never a silent prefix.
 */
export function ReportsTabs(props: { active: ReportTabId }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { tenant } = useParams();
  return (
    <SubTabs
      data-sub-tabs="reports"
      label={t("reports.tabs.label")}
      activeId={props.active}
      tabs={LIVE_REPORT_TABS.map((tab) => ({
        id: tab.id,
        label: t(`reports.tabs.${tab.id}`),
      }))}
      onSelect={(id) => {
        const tab = LIVE_REPORT_TABS.find((candidate) => candidate.id === id);
        if (tab !== undefined && tenant !== undefined) {
          navigate(`/${tenant}${tab.path}`);
        }
      }}
    />
  );
}

export default ReportsTabs;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P3.2 (05-prototype/09 Reports Build Brief.pdf p39, read as an image per B14 rule 42)
// screens: 5·1
// generated: 2026-09-27 by lane REP-P3 · AMENDED 2026-09-27 by lane REP-P4 (P4.5 — `Scheduled` mounts a real screen, so its hold expired and its tab is drawn) · AMENDED 2026-09-27 by lane REP-P4-DASH (P4.11 — `Dashboard` mounts a real screen; the LAST hold on this strip expired and its three cases are deleted)
// checklist: A=n/a(no backend half) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — `runHistory.dom.test.tsx` was run before this file existed and reported `Cannot find module './ReportsTabs'`. G31: this file is listed in styles/route-b-migrated.txt in the same commit.
// exceptions: [REP-P4-DASH] (1) ALL FOUR tabs the drawing shows are now drawn — `P4.11` mounted a real screen at `/reports/dashboard`, three hold cases went RED naming the segment, and all three are deleted in the same commit · (2) the count badge p39 shows on `Scheduled · 4` is not drawn — the strip fetches nothing and a count would make every screen mounting it issue a query. REPORTED · [REP-P3, superseded] (1) TWO tabs are drawn where the drawing shows FOUR — `Scheduled` is Phase 4 and unbuilt, and `/reports/dashboard` is a reserved segment still rendering the Phase 0 placeholder. Both are held with a test that fires when the hold expires, asserted BY ADDRESS. DIVERGENCE FROM THE DRAWING, REPORTED · (2) the count badge the drawing shows on `Scheduled · 4` is not drawn, because the tab is not drawn
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
