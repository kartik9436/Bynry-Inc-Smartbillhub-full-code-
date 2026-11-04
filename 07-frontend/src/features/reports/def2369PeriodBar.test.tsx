// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-2369 — the dashboard period bar could not align, because the
//          label was stacked ABOVE its dropdown.  Screens: S7 (Dashboard)
// Rules:   PO 2026-09-02 verbatim: "Period and Text infornt of it not aligned …
//          all should be in 1 line and aligned centrally - horizontal" ·
//          B14 rule 21 (DashboardPage.tsx IS on route-b-migrated.txt, checked)
// ───────────────────────────────────────────────────────
/**
 * **NO VALUE OF `align-items` COULD HAVE FIXED THIS, WHICH IS WHY THE FIX IS
 * STRUCTURAL AND SO IS THE TEST.**
 *
 * The bar already carried `items-center`. The parts still sat on different
 * lines because `.fin-params-field` is `flex-direction: column` — the label
 * stacked over the control, making the field two lines tall, so the one-line
 * sentence beside it had no shared line to sit on.
 *
 * The class is correct where it comes from: the S59/S60 report viewers put
 * several fields side by side, and stacking keeps each label with its own
 * control. So the fix is local to this bar, and this test pins THAT rather than
 * pinning a colour or a pixel — no gate in this repo reads rendered output, so
 * asserting the structure is the only check that can catch the shape coming
 * back.
 *
 * RED FIRST, quoted from the run against the shipped markup:
 *   `expected '<label class="fin-params-field">' not to contain
 *    'fin-params-field'`
 */
import "@/i18n";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import i18n from "i18next";

import { PeriodBar } from "./DashboardPage";

const t = i18n.getFixedT(null, null) as (k: string, o?: Record<string, unknown>) => string;

const FILTER = {
  selected: "last_30",
  default: "last_30",
  options: [
    { id: "last_30", start: "2026-08-04", end: "2026-09-02" },
    { id: "this_period", start: "2026-09-01", end: "2026-09-30" },
  ],
} as never;

function bar(): string {
  return renderToStaticMarkup(
    <PeriodBar
      filter={FILTER}
      asOf="2026-09-02"
      ageMinutes={null}
      locale="en-US"
      onSelect={() => undefined}
      t={t as never}
    />,
  );
}

describe("DEF-2369 — the period bar is one centred row", () => {
  it("does not stack the label above its control", () => {
    // The stacking class is the whole cause. Its absence is the fix.
    expect(bar()).not.toContain("fin-params-field");
  });

  it("lays the label and its control out as a row", () => {
    const html = bar();
    expect(html).toMatch(/<label[^>]*class="[^"]*flex-row/);
    expect(html).toMatch(/<label[^>]*class="[^"]*items-center/);
  });

  it("centres the dates on the same axis, not on a text baseline", () => {
    // `items-baseline` lines text up by its letters, which drifts the moment a
    // neighbour is a control with a box around it.
    const html = bar();
    expect(html).not.toContain("items-baseline");
  });

  it("still shows the range and the as-of day", () => {
    const html = bar();
    expect(html).toContain("Aug");
    expect(html).toContain("Sep");
    expect(html).toMatch(/data-dash="period-range"/);
    expect(html).toMatch(/data-dash="period-asof"/);
  });

  it("keeps the label readable to a screen reader", () => {
    // The visible label and the control's accessible name are both required —
    // laying it out as a row must not have dropped either.
    const html = bar();
    expect(html).toContain("Period");
    expect(html).toMatch(/aria-label="Period"/);
  });
});
