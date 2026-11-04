/* CR-075 wave C · C1a — the Records block's sparkline cell.
 *
 * `RBS-006-R5` column *Twelve months*: five rows, five shapes — flat, a spike
 * with a dot, a fall to zero, a rollover, and a DASHED line where the months
 * were estimated rather than read. */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Sparkline } from "./Sparkline";

const TWELVE = [5100, 5250, 5180, 5300, 5220, 5400, 9100, 5300, 5250, 5310, 5280, 7240];

describe("Sparkline — RBS-006-R5, twelve months of a meter", () => {
  it("draws a line with one point per month", () => {
    const html = renderToStaticMarkup(
      <Sparkline points={TWELVE} label="Twelve months of water use, in gallons." />,
    );
    expect(html).toContain("<polyline");
    expect(html).toContain('data-sparkline-points="12"');
  });

  it("HARD RULE 3 REACHES A PICTURE: the unit is what a reader who cannot see it gets", () => {
    // A sparkline has no axis, so an unlabelled one is strictly worse than an
    // unlabelled number — nothing on screen could supply the unit.
    const html = renderToStaticMarkup(
      <Sparkline points={TWELVE} label="Twelve months of water use, in gallons." />,
    );
    expect(html).toContain('role="img"');
    expect(html).toContain('aria-label="Twelve months of water use, in gallons."');
    expect(html).toContain("<title>Twelve months of water use, in gallons.</title>");
  });

  it("an ESTIMATED series is dashed and a READ series is not", () => {
    const estimated = renderToStaticMarkup(
      <Sparkline points={TWELVE} label="Estimated, in gallons." source="estimated" />,
    );
    expect(estimated).toContain('stroke-dasharray="4 3"');
    expect(estimated).toContain('data-sparkline-source="estimated"');
    const read = renderToStaticMarkup(<Sparkline points={TWELVE} label="Read, in gallons." />);
    expect(read).not.toContain("stroke-dasharray");
    expect(read).toContain('data-sparkline-source="read"');
  });

  it("the spike carries a dot, and no dot appears when none is asked for", () => {
    const marked = renderToStaticMarkup(
      <Sparkline points={TWELVE} label="Spike in July, in gallons." markAt={6} />,
    );
    expect(marked).toContain("<circle");
    expect(marked).toContain("fill-accent");
    expect(renderToStaticMarkup(<Sparkline points={TWELVE} label="x" />)).not.toContain("<circle");
  });

  it("a FLAT series draws down the middle rather than vanishing", () => {
    // Zero span would divide by zero and put every point at NaN, which renders
    // an empty <polyline> that looks exactly like a working one.
    const html = renderToStaticMarkup(
      <Sparkline points={[100, 100, 100, 100, 100]} label="Flat for five months, in gallons." />,
    );
    expect(html).not.toContain("NaN");
    expect(html).toContain("<polyline");
  });

  it("a series with NO SHAPE says its label instead of drawing a false flat line", () => {
    // A flat line is a FINDING on this screen (*▬ Flat · 5 months*), so drawing
    // one for "no data" would report a pattern the meter never had.
    const html = renderToStaticMarkup(<Sparkline points={[]} label="No readings yet." />);
    expect(html).not.toContain("<polyline");
    expect(html).toContain("No readings yet.");
    expect(html).toContain("data-sparkline-empty");
  });

  it("it does not change the row height — B14 rule 20, one table type", () => {
    const html = renderToStaticMarkup(<Sparkline points={TWELVE} label="x" />);
    expect(html).toContain("h-[26px]");
  });
});
