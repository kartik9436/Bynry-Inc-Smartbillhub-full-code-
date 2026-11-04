/* CR-075 wave C · C1a — the Verdict block.
 *
 * Every assertion is what a READER sees on `RBS-006-R9`, never that a prop was
 * passed (hard-won law 2: a component with an optional prop nothing passes is
 * dead UI that renders nothing while every test passes). The sheet's own words
 * are the fixture, so a copy change shows up here rather than in a browser. */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { VerdictBand } from "./VerdictBand";

describe("VerdictBand — RBS-006-R9's band, region 2", () => {
  it("draws the sheet's three lines: the word, the count, the detail", () => {
    const html = renderToStaticMarkup(
      <VerdictBand
        word="Not balanced"
        tone="danger"
        count="6 of 9 steps clear"
        detail="Tax off by $14.25 · $312.00 unapplied · 3 bank lines unmatched"
      />,
    );
    expect(html).toContain("Not balanced");
    expect(html).toContain("6 of 9 steps clear");
    expect(html).toContain("Tax off by $14.25");
    expect(html).toContain("3 bank lines unmatched");
  });

  it("the balanced variant is the SAME band with different words — not a second component", () => {
    const html = renderToStaticMarkup(
      <VerdictBand
        word="Balanced"
        tone="success"
        count="9 of 9 steps clear"
        detail="Receivables · revenue · tax · deposits all tie · exports ready"
      />,
    );
    expect(html).toContain("Balanced");
    expect(html).toContain("9 of 9 steps clear");
    expect(html).toContain("bg-success-500");
  });

  it("THE WORD IS THE RUNBOOK'S, NEVER DERIVED FROM THE TONE", () => {
    // Six different words for three tones across the five sheets. A component
    // that mapped tone -> word would have to know every runbook, which is the
    // thing 12-the-contract.md says a renderer must not do.
    const words = ["No-go", "Not balanced", "Balanced", "Found", "Not ready", "14 eligible"];
    for (const word of words) {
      expect(renderToStaticMarkup(<VerdictBand word={word} tone="warning" count="x" />)).toContain(
        word,
      );
    }
  });

  it("each tone draws its own fill, and the fill is a colour this theme declares", () => {
    expect(
      renderToStaticMarkup(<VerdictBand word="Balanced" tone="success" count="9 of 9" />),
    ).toContain("bg-success-500");
    expect(
      renderToStaticMarkup(<VerdictBand word="14 eligible" tone="warning" count="9 removed" />),
    ).toContain("bg-warning-500");
    expect(
      renderToStaticMarkup(<VerdictBand word="No-go" tone="danger" count="2 of 9" />),
    ).toContain("bg-danger-500");
  });

  it("the detail line is OPTIONAL and its absence renders nothing, not an empty box", () => {
    const html = renderToStaticMarkup(<VerdictBand word="Found" tone="success" count="$182.40" />);
    expect(html).not.toContain("data-verdict-detail");
    expect(html).toContain("$182.40");
  });

  it("the commit control appears where the sheet draws it, and only when handed in", () => {
    // RBS-006-R9's balanced variant: "Close period ✓" on the right of the band.
    // B14 rule 6 makes it the danger tier; this component renders the control
    // the caller hands it and never decides when it enables (BR-RBS-030 —
    // closing a period stays a named person's act, OQ-RBS-1736 CLOSED).
    const withAction = renderToStaticMarkup(
      <VerdictBand
        word="Balanced"
        tone="success"
        count="9 of 9 steps clear"
        action={<button type="button">Close period ✓</button>}
      />,
    );
    expect(withAction).toContain("Close period ✓");
    const without = renderToStaticMarkup(
      <VerdictBand word="Not balanced" tone="danger" count="6 of 9 steps clear" />,
    );
    expect(without).not.toContain("data-verdict-action");
  });

  it("a screen reader reaches it in the page's order — a finished run is not an alert", () => {
    const html = renderToStaticMarkup(<VerdictBand word="No-go" tone="danger" count="2 of 9" />);
    expect(html).toContain('role="status"');
    expect(html).not.toContain('role="alert"');
  });
});
