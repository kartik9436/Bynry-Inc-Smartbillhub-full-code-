// @vitest-environment jsdom
/* CR-075 wave C · C1a — the Records block's GRID DISPLAY MODE.
 *
 * ⚠ THERE IS NO BUILD SHEET. `RBS-004-R24` draws the coverage grid's SETUP and
 * there is no `RBS-006-R24` among the 48 result frames — wave `F1` records the
 * same absence for runbook 23. The fixture below is built from the ONE sentence
 * the pack gives, `RBS-004-R24`'s own Outcome box, quoted verbatim:
 *
 *     "A grid: 21 clean · 2 estimated · 2 refused, each cell opening that
 *      account's test bill with the engine's own refusal sentence."
 *
 * so the counts are 21 / 2 / 2 and they are asserted as such. When wave F1
 * draws the frame, THIS is the file that has to change.
 *
 * ⚠ AND IT IS MOUNTED UNDER THE REAL PATH PATTERN. Bare in a `MemoryRouter`
 * with no route, every address a component builds comes out `//…` and reads as
 * a perfectly good string to `toContain` (DEF-CWP-3925). */
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { RecordGrid } from "./RecordGrid";
import type { RecordGridCell } from "./RecordGrid";

afterEach(cleanup);

const TENANT = "silvercreek";

/** 21 clean · 2 estimated · 2 refused — RBS-004-R24's own sentence. */
const COVERAGE: RecordGridCell[] = [
  ...Array.from({ length: 21 }, (_, i) => ({
    id: `c${i}`,
    label: `Account ${i + 1}`,
    state: "clean" as const,
    to: `/${TENANT}/runbooks/coverage-grid/records/c${i}`,
  })),
  ...Array.from({ length: 2 }, (_, i) => ({
    id: `e${i}`,
    label: `Estimated ${i + 1}`,
    state: "estimated" as const,
    to: `/${TENANT}/runbooks/coverage-grid/records/e${i}`,
  })),
  {
    id: "r0",
    label: "Marsh Farms",
    state: "refused",
    to: `/${TENANT}/runbooks/coverage-grid/records/r0`,
    reason: "No rate above 20,000 gal",
  },
  {
    id: "r1",
    label: "Riverside Apts",
    state: "refused",
    to: `/${TENANT}/runbooks/coverage-grid/records/r1`,
    reason: "No tax region set",
  },
];

function mount(cells: RecordGridCell[]) {
  return render(
    <MemoryRouter initialEntries={[`/${TENANT}/runbooks/coverage-grid/runs/today`]}>
      <Routes>
        <Route
          path="/:tenant/runbooks/:key/runs/:run"
          element={
            <RecordGrid
              cells={cells}
              label="25 accounts priced."
              empty={<span>Nothing priced yet. Run the coverage grid.</span>}
            />
          }
        />
        <Route path="/:tenant/runbooks/:key/records/:record" element={<div>a test bill</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RecordGrid — the coverage grid, 21 clean · 2 estimated · 2 refused", () => {
  it("draws one cell per record, in the three states the sentence names", () => {
    mount(COVERAGE);
    expect(document.querySelectorAll('[data-record-state="clean"]')).toHaveLength(21);
    expect(document.querySelectorAll('[data-record-state="estimated"]')).toHaveLength(2);
    expect(document.querySelectorAll('[data-record-state="refused"]')).toHaveLength(2);
  });

  it("EVERY CELL IS A REAL DOOR — 25 of 25, resolved, none protocol-relative", () => {
    // DEF-CWP-3925: the portal's front page shipped with two working doors out
    // of eight and G13 could not see it, because G13 asks whether a prop is
    // passed and never whether a refusal is still true. A grid of 25 cells that
    // do not open is that defect twenty-five times over.
    mount(COVERAGE);
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(25);
    for (const link of links) {
      const href = link.getAttribute("href") ?? "";
      expect(href.startsWith(`/${TENANT}/runbooks/coverage-grid/records/`)).toBe(true);
      expect(href.startsWith("//")).toBe(false);
    }
  });

  it("a REFUSED cell carries the engine's own sentence, reachable without a hover", () => {
    mount(COVERAGE);
    expect(screen.getByText("No rate above 20,000 gal")).toBeInTheDocument();
    expect(screen.getByText("No tax region set")).toBeInTheDocument();
    // and as the title too, so a mouse reader gets it as well
    const refused = document.querySelector('[data-record-state="refused"]');
    expect(refused).toHaveAttribute("title", "No rate above 20,000 gal");
  });

  it("the ACCOUNT'S NAME is what a reader sees, never its id — B14 rule 31", () => {
    mount([
      {
        id: "8f14e45f-ceea-467a-9c1f-4b2d1e2f8a90",
        label: "Marsh Farms",
        state: "clean",
        to: `/${TENANT}/runbooks/coverage-grid/records/x`,
      },
    ]);
    expect(screen.getByText("Marsh Farms")).toBeInTheDocument();
    expect(document.body.innerHTML).not.toContain("8f14e45f");
  });

  it("an EMPTY grid says what is missing and what fills it — B14 rule 17", () => {
    mount([]);
    expect(screen.getByText("Nothing priced yet. Run the coverage grid.")).toBeInTheDocument();
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(document.querySelector("[data-record-grid-empty]")).not.toBeNull();
  });

  it("it is a labelled list, so a screen reader can say what it is", () => {
    mount(COVERAGE);
    expect(screen.getByRole("list", { name: "25 accounts priced." })).toBeInTheDocument();
  });
});
