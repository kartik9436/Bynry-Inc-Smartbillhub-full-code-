// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-052 task 9 — "Draw the twelve-month block on the bill document
//           and in the printable page", unblocked by closing DEF-2714.
// Screens:  S30 → "View the bill as sent"
// Rules:    A19 §1.7 (the twelve-month usage block) · BR-MET-106 (one stored
//           row per account/service/month; an unmeasured month is ABSENT,
//           never 0, and estimates COUNT and are MARKED) · BR-BIL-030 (the
//           bill's contents are frozen at issue — no live join) · B14 rule 31
//           (no database id is ever the visible value of a field) ·
//           hard-won law 2 (built is not wired)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **WHAT THESE CASES CANNOT PROVE, SO NOBODY READS THEM AS PROOF.** jsdom
 * computes no layout: a bar with `height: 42%` and a bar with `height: 0%` are
 * both "in the document" here. The heights and the colours are proved in
 * Chromium by `10-scripts/render-checks/cr052-usage-history.mjs`, and a green
 * run of this file is not evidence that a chart drew (hard-won law 6).
 *
 * What these DO pin is the thing a browser check reads too late: that an absent
 * month never becomes a zero.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { DocumentUsageSeries } from "@/api/billingOpsEndpoints";

import { BillUsagePanel } from "./billingOpsShared";

const t = ((key: string) => key) as never;

// Each case renders into the same jsdom document, so without this the panel
// from the previous case is still mounted and `screen` finds both.
afterEach(cleanup);

function month(label: string, quantity: string | null, extra: Partial<Record<string, unknown>> = {}) {
  return {
    label,
    quantity: quantity ?? "",
    quantity_display: quantity ?? "",
    unit: "kWh",
    absent: quantity === null,
    estimated: false,
    ...extra,
  };
}

/** A-10432's real shape on BL-2608-000095: three measured months, nine absent. */
const ELECTRIC: DocumentUsageSeries = {
  heading: "Electric",
  unit: "kWh",
  months_present: 3,
  absent: null,
  months: [
    month("2025-09", null),
    month("2025-10", null),
    month("2025-11", null),
    month("2025-12", null),
    month("2026-01", null),
    month("2026-02", null),
    month("2026-03", null),
    month("2026-04", null),
    month("2026-05", null),
    month("2026-06", "412"),
    month("2026-07", "842"),
    month("2026-08", "628"),
  ],
};

describe("CR-052 task 9 — the twelve-month block on the bill document", () => {
  it("TC-1 draws one slot per month, per service", () => {
    render(<BillUsagePanel series={[ELECTRIC]} t={t} />);
    expect(document.querySelectorAll('[data-bil="bill-usage-bar"]')).toHaveLength(12);
    expect(screen.getByText("2026-08")).toBeTruthy();
  });

  it("TC-2 an ABSENT month draws no bar and claims no figure (BR-MET-106)", () => {
    render(<BillUsagePanel series={[ELECTRIC]} t={t} />);
    const absent = document.querySelectorAll('[data-bil="bill-usage-bar"][data-absent="true"]');
    expect(absent).toHaveLength(9);
    // ⚠ THE CASE THAT MATTERS. A zero-height bar would be a claim that the
    // meter was read and showed nothing. An absent slot carries NO height at
    // all — not `height: 0%`.
    for (const slot of Array.from(absent)) {
      expect((slot as HTMLElement).style.height).toBe("");
      expect((slot as HTMLElement).getAttribute("title")).toBe(
        "billing.document.usageNoReading",
      );
    }
  });

  it("TC-3 scales the measured months against the tallest one", () => {
    render(<BillUsagePanel series={[ELECTRIC]} t={t} />);
    const drawn = Array.from(
      document.querySelectorAll('[data-bil="bill-usage-bar"][data-absent="false"]'),
    ) as HTMLElement[];
    expect(drawn).toHaveLength(3);
    // 842 is the peak, so it is full height and 412 is 412/842 = 48.93%.
    expect(drawn[1].style.height).toBe("100%");
    expect(drawn[0].style.height).toBe(`${(412 / 842) * 100}%`);
  });

  it("TC-4 marks an estimated month and says so once", () => {
    const estimated: DocumentUsageSeries = {
      ...ELECTRIC,
      months: ELECTRIC.months.map((m) =>
        m.label === "2026-07" ? { ...m, estimated: true } : m,
      ),
    };
    render(<BillUsagePanel series={[estimated]} t={t} />);
    expect(
      document.querySelectorAll('[data-bil="bill-usage-bar"][data-estimated="true"]'),
    ).toHaveLength(1);
    expect(screen.getByText("billing.document.usageEstimated")).toBeTruthy();
  });

  it("TC-5 says nothing about estimates when none is estimated", () => {
    render(<BillUsagePanel series={[ELECTRIC]} t={t} />);
    expect(screen.queryByText("billing.document.usageEstimated")).toBeNull();
  });

  it("TC-6 renders NOTHING when the bill froze no block", () => {
    const { container } = render(<BillUsagePanel series={[]} t={t} />);
    // Omitted whole, never a heading over nothing — the remarks-band posture.
    expect(container.innerHTML).toBe("");
  });

  it("TC-7 names the service and never its id (B14 rule 31)", () => {
    render(<BillUsagePanel series={[ELECTRIC]} t={t} />);
    const caption = document.querySelector('[data-bil="bill-usage-caption"]');
    expect(caption?.textContent).toBe("Electric · kWh");
    // Nothing uuid-shaped anywhere on the panel.
    expect(document.body.innerHTML).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    );
  });

  it("TC-8 states a mixed-unit window instead of drawing one axis", () => {
    const mixed: DocumentUsageSeries = {
      ...ELECTRIC,
      unit: null,
      absent: { field: "usage_history.unit", br_ref: "A19 §1.7 · OQ-358", why: "mixed units" },
    };
    render(<BillUsagePanel series={[mixed]} t={t} />);
    expect(screen.getByText("billing.document.usageMixedUnits")).toBeTruthy();
  });
});
