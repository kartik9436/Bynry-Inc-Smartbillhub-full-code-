// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 4 `P4.12`. Screen `3·1` controls ② and ③, drawn
//          on p036 and annotated on p037, read as IMAGES per B14 rule 42.
// Rules:   B14 rule 43 (a COMPONENT) · rule 44 (our kit and tokens win over the
//          drawing, including the frame) · rule 33 (a LABEL ≤ 3 words) ·
//          rule 21 (Tailwind only) · BR-SHL-011 (an impossible value falls back)
// Tests:   07-frontend/src/features/reports/reportsDashboard.dom.test.tsx
// Impacts: ReportsDashboardPage.tsx
// ───────────────────────────────────────────────────────
//
// THE TWO CONTROLS THAT ARE THE WHOLE SURFACE OF `3·1`.
//
// p036 ③, verbatim: *"Set the period · set what to compare it against · open a
// panel. **That is the whole surface**"*, and ④: *"Nothing. **No write of any
// kind**, not even a remembered period."*
//
// ⚠ **SO NEITHER CONTROL WRITES ANYTHING — THEY MOVE THE URL.** The period
// rides in the address bar because p038 says that is what makes this screen
// usable in a board pack at all: *"the link you copy opens on the same month"*.
// A remembered preference would make the same link open on two different
// months for two people, which is the failure a board pack cannot survive.
//
// ⚠ **THE PERIOD'S LABEL IS COMPOSED FROM THE SERVED WINDOW, NOT FROM A TOKEN.**
// A tenant on a QUARTERLY close cadence has a three-month accounting period,
// and a label built from the word *month* would lie on every one of them.
import { useTranslation } from "react-i18next";

import type { DashboardPeriod } from "@/api/dashboardTabEndpoints";

/** *September 2026* — from the window the SERVER computed (BR-TEN-022). */
export function periodLabel(period: DashboardPeriod, locale: string | undefined): string {
  const start = new Date(`${period.start}T00:00:00`);
  const end = new Date(`${period.end}T00:00:00`);
  if (Number.isNaN(start.getTime())) return period.id;
  const month = new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" });
  // A window inside one calendar month reads as that month; a quarter reads as
  // its two ends, which is the only honest short form for a three-month period.
  if (start.getFullYear() === end.getFullYear() && start.getMonth() === end.getMonth()) {
    return month.format(start);
  }
  const short = new Intl.DateTimeFormat(locale, { month: "short", year: "numeric" });
  return `${short.format(start)} – ${short.format(end)}`;
}

export interface DashboardPeriodBarProps {
  periods: readonly DashboardPeriod[];
  selected: DashboardPeriod | null;
  comparison: string;
  comparisons: readonly { id: string }[];
  onPeriod: (id: string) => void;
  onComparison: (id: string) => void;
}

export function DashboardPeriodBar(props: DashboardPeriodBarProps) {
  const { t, i18n } = useTranslation();
  return (
    <div className="flex flex-wrap items-center gap-3" data-dashboard-controls="">
      <label className="sr-only" htmlFor="rep-dash-period">
        {t("reports.dashboard.periodLabel")}
      </label>
      <select
        id="rep-dash-period"
        className="input"
        value={props.selected?.id ?? ""}
        onChange={(event) => props.onPeriod(event.target.value)}
        data-dashboard-period=""
      >
        {props.periods.map((period) => (
          <option key={period.id} value={period.id}>
            {periodLabel(period, i18n.language)}
          </option>
        ))}
      </select>
      <label className="sr-only" htmlFor="rep-dash-compare">
        {t("reports.dashboard.compareLabel")}
      </label>
      <select
        id="rep-dash-compare"
        className="input"
        value={props.comparison}
        onChange={(event) => props.onComparison(event.target.value)}
        data-dashboard-compare=""
      >
        {props.comparisons.map((option) => (
          <option key={option.id} value={option.id}>
            {t(`reports.dashboard.compare.${option.id}`)}
          </option>
        ))}
      </select>
    </div>
  );
}

export default DashboardPeriodBar;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P4.12 (05-prototype/09 Reports Build Brief.pdf p36 controls ②③ · p37 ②③, read as IMAGES per B14 rule 42)
// screens: 3·1
// generated: 2026-09-27 by lane REP-P4-DASH
// checklist: A=n/a(no backend half) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — reportsDashboard.dom.test.tsx reported `Cannot find module './dashboard/DashboardPeriodBar'` before this file existed. G31: listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) p36 draws the two controls as pill buttons with a chevron; they are built as the kit's `select` under B14 rule 44 — the drawing says WHAT is on screen and our UI standard says how it is BUILT, and it wins every time · (2) `budget`, the third comparison p36 draws, is not in `comparisons`: the SERVER does not offer it and names why on the payload
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
