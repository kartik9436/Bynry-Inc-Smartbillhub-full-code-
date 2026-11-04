/* CR-075 wave C · C1a — the Ranked block.
 *
 * The fixture is `RBS-006-R4` region 4 verbatim: six rows, largest first,
 * *More water used* down to *Meter · $0.00*. */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ContributionBars } from "./ContributionBars";
import type { ContributionRow } from "./ContributionBars";

/** `RBS-006-R4` region 4. The weights are the money each cause contributed. */
const WHY_HIGHER: ContributionRow[] = [
  {
    id: "usage",
    label: "More water used",
    detail: "7,240 gal vs 5,250 gal · 4 more days",
    weight: 46.4,
    value: "+$46.40",
  },
  {
    id: "tier",
    label: "Reached tier 2",
    detail: "Usage above 5,000 gal priced higher",
    weight: 14.8,
    value: "+$14.80",
  },
  { id: "late", label: "Late fee", detail: "August paid 12 days late", weight: 12, value: "+$12.00" },
  { id: "tax", label: "Tax on the above", detail: "Follows the charges", weight: 9, value: "+$9.00" },
  {
    id: "rate",
    label: "Rate change",
    detail: "None between the two bills",
    weight: 0,
    value: "$0.00",
  },
  { id: "meter", label: "Meter", detail: "Same meter, same multiplier", weight: 0, value: "$0.00" },
];

describe("ContributionBars — RBS-006-R4 region 4, what caused it · largest first", () => {
  it("draws every row's label, its quieter second line, and its figure", () => {
    const html = renderToStaticMarkup(
      <ContributionBars rows={WHY_HIGHER} label="What caused it, largest first." />,
    );
    expect(html).toContain("More water used");
    expect(html).toContain("7,240 gal vs 5,250 gal · 4 more days");
    expect(html).toContain("+$46.40");
    expect(html).toContain("Same meter, same multiplier");
    expect(html.match(/data-bar-row=""/g)).toHaveLength(6);
  });

  it("the bar is proportional to the LARGEST ROW, not to the total", () => {
    // Share-of-total would draw the top bar at 46% and read as a bug: every
    // sheet draws the widest bar on the top row.
    const html = renderToStaticMarkup(
      <ContributionBars rows={WHY_HIGHER} label="What caused it." />,
    );
    expect(html).toContain("width:100%"); // the largest row fills its track
    // 14.8 / 46.4 = 31.9%, and it is NOT 14.8/82.2 = 18%
    expect(html).toContain("width:31.896551724137932%");
  });

  it("a cause that contributed NOTHING still gets a row, with an empty track", () => {
    // RBS-006-R4's *Rate change · None between the two bills · $0.00* is a
    // cause that was CHECKED and found not guilty, which is worth a row.
    const html = renderToStaticMarkup(
      <ContributionBars rows={WHY_HIGHER} label="What caused it." />,
    );
    expect(html).toContain("Rate change");
    expect(html).toContain('data-bar-weight="0"');
    expect(html).toContain("width:0%");
  });

  it("a list where NOTHING moved draws six empty tracks, not a crash", () => {
    // Every weight zero would divide by zero and put every bar at NaN.
    const html = renderToStaticMarkup(
      <ContributionBars
        label="Nothing moved."
        rows={[
          { id: "a", label: "Rate change", weight: 0, value: "$0.00" },
          { id: "b", label: "Meter", weight: 0, value: "$0.00" },
        ]}
      />,
    );
    expect(html).not.toContain("NaN");
    expect(html.match(/width:0%/g)).toHaveLength(2);
  });

  it("rows are drawn in the order given — sorting is the runbook's job", () => {
    const html = renderToStaticMarkup(
      <ContributionBars rows={WHY_HIGHER} label="What caused it." />,
    );
    expect(html.indexOf("More water used")).toBeLessThan(html.indexOf("Reached tier 2"));
    expect(html.indexOf("Reached tier 2")).toBeLessThan(html.indexOf("Late fee"));
  });

  it("the figure arrives already formatted — this component formats no number", () => {
    // BR-SHL-023 keeps one formatting path. A second one here is how a screen
    // ends up showing $46.4 beside a real charge.
    const html = renderToStaticMarkup(
      <ContributionBars
        label="One row."
        rows={[{ id: "a", label: "Late fee", weight: 12, value: "+$12.00" }]}
      />,
    );
    expect(html).toContain("+$12.00");
    expect(html).not.toContain("12.0000");
  });

  it("the bar itself is hidden from a screen reader — the figure beside it says the same thing", () => {
    const html = renderToStaticMarkup(
      <ContributionBars rows={WHY_HIGHER} label="What caused it, largest first." />,
    );
    expect(html).toContain('aria-hidden="true"');
    expect(html).toContain('aria-label="What caused it, largest first."');
  });
});
