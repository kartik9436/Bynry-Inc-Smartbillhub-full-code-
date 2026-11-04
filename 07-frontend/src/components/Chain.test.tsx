/* CR-075 wave C · C1a — the Chain block.
 *
 * Wave C's *goal a clerk can see* is this component: *Can we bill?* runs and
 * the result draws a TEN-CELL CHAIN, RED AT THE EARLIEST FAILURE. The fixture
 * below is `RBS-006-R1` region 3 verbatim — ten cells, red at 3, 5 and 6 — so
 * the goal is asserted rather than described. */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Chain } from "./Chain";
import type { ChainCell } from "./Chain";

/** `RBS-006-R1` region 3, cell for cell. */
const CONFIGURATION_CHECK: ChainCell[] = [
  { id: "s1", position: 1, label: "Services", state: "ok" },
  { id: "s2", position: 2, label: "Reference data", state: "ok" },
  { id: "s3", position: 3, label: "Tax", state: "bad", note: "No tax region set" },
  { id: "s4", position: 4, label: "Plans", state: "ok" },
  { id: "s5", position: 5, label: "Rate coverage", state: "bad", note: "No block above 20,000 gal" },
  { id: "s6", position: 6, label: "Account chain", state: "bad", note: "240 accounts have no unit" },
  { id: "s7", position: 7, label: "Meters", state: "ok" },
  { id: "s8", position: 8, label: "Reads", state: "ok" },
  { id: "s9", position: 9, label: "Documents", state: "ok" },
  { id: "s10", position: 10, label: "Books", state: "ok" },
];

describe("Chain — RBS-006-R1 region 3, the ten-cell chain", () => {
  it("draws ten cells, in the sheet's order, with the sheet's names", () => {
    const html = renderToStaticMarkup(
      <Chain cells={CONFIGURATION_CHECK} label="Ten steps, three stopped billing." />,
    );
    expect(html.match(/data-chain-cell=""/g)).toHaveLength(10);
    for (const cell of CONFIGURATION_CHECK) expect(html).toContain(cell.label);
    // the order is the run's order, so the first name precedes the last
    expect(html.indexOf("Services")).toBeLessThan(html.indexOf("Books"));
  });

  it("RED AT THE EARLIEST FAILURE — three cells carry the danger state and seven do not", () => {
    const html = renderToStaticMarkup(<Chain cells={CONFIGURATION_CHECK} label="Ten steps." />);
    expect(html.match(/data-chain-state="bad"/g)).toHaveLength(3);
    expect(html.match(/data-chain-state="ok"/g)).toHaveLength(7);
    expect(html).toContain("bg-danger-100");
  });

  it("A RED CELL NAMES THE BLOCKER — that is the sheet's own rule, not decoration", () => {
    const html = renderToStaticMarkup(<Chain cells={CONFIGURATION_CHECK} label="Ten steps." />);
    expect(html).toContain("No tax region set");
    expect(html).toContain("No block above 20,000 gal");
    expect(html).toContain("240 accounts have no unit");
  });

  it("a NEVER REACHED cell SAYS SO rather than sitting blank (RB-036, BR-RBS-027)", () => {
    // A blank cell and a passed cell look identical at a glance, which is how a
    // clerk concludes a step was fine when it never ran.
    const html = renderToStaticMarkup(
      <Chain
        label="Nine steps, the first stopped the run."
        cells={[
          { id: "a", position: 1, label: "Config passes", state: "bad", note: "3 blockers" },
          { id: "b", position: 2, label: "Counts", state: "notReached", note: "Never reached" },
          { id: "c", position: 3, label: "Balances", state: "notReached", note: "Never reached" },
        ]}
      />,
    );
    expect(html.match(/Never reached/g)).toHaveLength(2);
    expect(html.match(/data-chain-state="notReached"/g)).toHaveLength(2);
  });

  it("a step that never ran is NOT drawn as a failure — it is grey, not red", () => {
    const html = renderToStaticMarkup(
      <Chain
        label="Two steps."
        cells={[{ id: "b", position: 2, label: "Counts", state: "notReached", note: "Never reached" }]}
      />,
    );
    // Nobody knows what it would have done; colouring it red reports a blocker
    // the run never found.
    expect(html).not.toContain("bg-danger-100");
    expect(html).toContain("border-t-neutral-400");
  });

  it("the position is drawn and the id is NOT — B14 rule 31", () => {
    const html = renderToStaticMarkup(
      <Chain
        label="One step."
        cells={[
          {
            id: "8f14e45f-ceea-467a-9c1f-4b2d1e2f8a90",
            position: 1,
            label: "Services",
            state: "ok",
          },
        ]}
      />,
    );
    expect(html).toContain(">1<");
    expect(html).not.toContain("8f14e45f");
  });

  it("a NOTED cell is amber — seen, and it stops nothing (DEF-CUS-6350)", () => {
    // ⊕ 2026-09-23 — the Approve window's *2 documents not checked*. It must
    // read as neither a pass nor a blocker: amber, never the danger tint.
    const html = renderToStaticMarkup(
      <Chain
        label="Two steps."
        cells={[
          { id: "a", position: 1, label: "Unit", state: "ok" },
          { id: "b", position: 2, label: "Documents", state: "noted", note: "2 not checked" },
        ]}
      />,
    );
    expect(html.match(/data-chain-state="noted"/g)).toHaveLength(1);
    expect(html).toContain("border-t-warning-500 bg-warning-100");
    expect(html).not.toContain("bg-danger-100");
    expect(html).toContain("2 not checked");
  });

  it("it is an ordered list, because the steps ran in an order", () => {
    const html = renderToStaticMarkup(<Chain cells={CONFIGURATION_CHECK} label="Ten steps." />);
    expect(html).toContain("<ol");
    expect(html).toContain('aria-label="Ten steps."');
  });
});
