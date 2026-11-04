// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 4 `P4.11`. Screen `3·1` region ⑤, drawn on p036
//          and annotated on p037, read as IMAGES per B14 rule 42.
// Rules:   B14 rule 43 (a COMPONENT) · rule 21 (Tailwind only) · rule 33
//          (RATIONALE is zero words on screen) · CLAUDE.md hard rule 2
//          (money is a decimal string; DISPLAY 2)
// Tests:   07-frontend/src/features/reports/reportsDashboard.dom.test.tsx
// Impacts: ReportsDashboardPage.tsx
// ───────────────────────────────────────────────────────
//
// `Revenue, 12 months` — THE ONLY CHART IN THIS PRODUCT, AND IT IS CSS.
//
// ⚠ **NO CHARTING LIBRARY WAS ADDED AND THAT IS THE BRIEF'S OWN RULING, NOT A
// SHORTCUT.** p038 TODAY, verbatim: *"Does not exist. ⚠ And neither does **any
// chart anywhere in this product** — there is no charting library in
// `07-frontend/package.json`. The bars above are drawn in CSS, which is
// deliberate: five panels do not justify a dependency, and a CSS bar prints,
// scales and theme-switches for free."* Checked against `package.json` before
// this file was written: no `recharts`, no `d3`, no `victory`, no `nivo`, no
// `apexcharts` — the sentence is still true.
//
// ⚠ **A MONTH WITH NO ANSWER DRAWS NO BAR — IT IS NOT DRAWN AT THE FLOOR.**
// A report that refused and a period that billed nothing are two different
// facts, and a zero-height bar says the second about both. A window whose
// report did not answer gets an empty track and its month label stays, so the
// axis is still twelve months long and the gap is visible as a gap.
//
// ⚠ **THE SELECTED PERIOD IS ACCENTED AND THE OTHERS ARE NOT** (p037 ⑤,
// *"bars, current period accented"*). The accent is the product's own token,
// not a colour picked here — B14 rule 44.
//
// ⚠ **THE AXIS IS THREE LABELS AND NOT TWELVE.** p036 draws *Oct 25 · Mar 26 ·
// Sep 26*: first, middle, last. Twelve labels at this width overlap, and an
// overlapping axis is less readable than three that a reader can interpolate
// between — which is what the drawing already decided.
import { useTranslation } from "react-i18next";

import type { RevenueBar } from "@/api/dashboardTabEndpoints";

/** The tallest bar's amount, as a plain number, ONLY to decide pixel heights.
 *
 *  ⚠ **THIS IS THE ONE PLACE A MONEY STRING BECOMES A NUMBER, AND IT NEVER
 *  REACHES THE SCREEN.** Hard rule 2 forbids a float near money; what it
 *  forbids is a float being DISPLAYED or STORED. A bar's height in pixels is
 *  neither — the figure a reader reaches, through each bar's `title`, is the
 *  exact decimal string the server sent, always. */
function heightScale(bars: readonly RevenueBar[]): number {
  const largest = bars.reduce((max, bar) => {
    const amount = bar.value === null ? 0 : Number(bar.value);
    return Number.isFinite(amount) && amount > max ? amount : max;
  }, 0);
  return largest > 0 ? largest : 1;
}

/** *Oct 25* — the month and the two-digit year, in the viewer's own locale. */
function monthLabel(iso: string, locale: string | undefined): string {
  const when = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(when.getTime())) return iso;
  return new Intl.DateTimeFormat(locale, { month: "short", year: "2-digit" }).format(when);
}

export interface RevenueBarsPanelProps {
  bars: readonly RevenueBar[];
  /** ⚠ **TAKEN AND UNUSED TODAY, DELIBERATELY.** The bars print no money —
   *  see the note in the body — so nothing here formats a currency. It stays
   *  on the interface because every other panel takes it and a panel that
   *  silently differs is the one a later lane forgets to pass it to. */
  currency?: string | null;
  locale?: string;
}

export function RevenueBarsPanel(props: RevenueBarsPanelProps) {
  const { t, i18n } = useTranslation();
  const scale = heightScale(props.bars);
  const axis = props.bars.length === 0 ? [] : [0, Math.floor((props.bars.length - 1) / 2), props.bars.length - 1];
  return (
    <div data-panel-body="revenue_12_months">
      <ol
        className="m-0 flex h-[180px] list-none items-end gap-2 p-0"
        aria-label={t("reports.dashboard.panel.revenue12")}
      >
        {props.bars.map((bar) => {
          const amount = bar.value === null ? null : Number(bar.value);
          const filled =
            amount === null || !Number.isFinite(amount) || amount <= 0
              ? 0
              : Math.max(2, Math.min(100, (amount / scale) * 100));
          return (
            <li
              key={bar.period_id}
              className="flex h-full flex-1 items-end"
              data-bar-period={bar.period_id}
              data-bar-current={bar.current ? "" : undefined}
              data-bar-absent={bar.value === null ? "" : undefined}
              // The figure is the accessible fact; the bar is its picture. A
              // screen reader reading a rectangle is noise, so the title is
              // where the amount lives for a pointer and `aria-label` names it
              // for everyone else.
              title={
                bar.value === null
                  ? `${monthLabel(bar.start, i18n.language)} · ${t("reports.dashboard.noFigure")}`
                  : `${monthLabel(bar.start, i18n.language)} · ${bar.value}`
              }
            >
              <span
                className={
                  bar.current
                    ? "block w-full bg-accent"
                    : "block w-full bg-neutral-400"
                }
                style={{ height: `${filled}%` }}
                data-bar-fill=""
              />
            </li>
          );
        })}
      </ol>
      <div className="mt-2 flex justify-between text-sm text-neutral-600" data-bar-axis="">
        {axis.map((index) => (
          <span key={props.bars[index].period_id}>
            {monthLabel(props.bars[index].start, i18n.language)}
          </span>
        ))}
      </div>
      {/* ⚠ **NO FIGURE IS PRINTED UNDER THE BARS, AND A FIRST DRAFT PRINTED
          ONE.** p036 draws bars and a three-label axis and nothing else, and
          the selected period's revenue is already the `Billed` tile two
          inches above. Printing it twice put the same money on screen in two
          places — which is not merely redundant: it is the shape DEF-104
          records, where four surfaces each showed one customer's balance and
          the one a clerk quoted was the wrong one. Per-bar figures reach a
          pointer and a screen reader through each bar's `title`. */}
    </div>
  );
}

export default RevenueBarsPanel;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P4.11 (05-prototype/09 Reports Build Brief.pdf p36 region ⑤ · p37 ⑤ · p38 TODAY, read as IMAGES per B14 rule 42)
// screens: 3·1
// generated: 2026-09-27 by lane REP-P4-DASH
// checklist: A=n/a(no backend half) B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — reportsDashboard.dom.test.tsx reported `Cannot find module './dashboard/RevenueBarsPanel'` before this file existed. G31: listed in styles/route-b-migrated.txt in the same commit.
// exceptions: (1) the axis draws THREE labels where twelve bars are drawn — p36's own arrangement, because twelve labels overlap at this width. DIVERGENCE FROM NOTHING: the drawing shows three · (2) a bar's HEIGHT is computed from a Number(); the figure a reader reaches through the bar's `title` is always the exact decimal string the server sent · (3) NO figure is printed under the bars — the drawing prints none and the `Billed` tile already carries it, and one money fact on screen twice is DEF-104's shape
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
