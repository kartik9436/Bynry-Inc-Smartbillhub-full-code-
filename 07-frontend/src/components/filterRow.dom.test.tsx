// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-LED-6728 — the Finance params band was one row on three
//          baselines. PO: *"filter is not align - it is not in 1 line."*
// Rules:   B14 rule 44 / 38 (our spacing and kit decide HOW a form is built) ·
//          rule 43 (it is a COMPONENT) · rule 21 (utilities, no stylesheet class).
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT THIS CAN AND CANNOT PROVE, SAID FIRST (hard-won law 7).**
// jsdom has no layout engine: `getBoundingClientRect` returns zeroes, so NO
// test in this file can measure that the controls share a baseline. The
// measurement lives in `10-scripts/finance_filter_row_baseline.mjs`, which drives a
// real Chromium against a real PostgreSQL and prints each control's top.
//
// What this file pins is the two STRUCTURAL decisions the measurement depends
// on, because those are what a later edit would undo:
//
//   1. the row aligns from the TOP (`items-start`), never the bottom
//      (`items-end`) — bottom alignment IS the defect, and it is the line a
//      tidy-up would most plausibly write back;
//   2. the action reserves its slot with a real `<label>` inside a `.field`,
//      which is what makes its height the KIT's rather than a guess. The first
//      draft used a `<span>` and the button measured 1px high.
//
// **What would make this pass wrongly:** asserting only that the component
// renders its children, which passes with `items-end` restored and with the
// reserved slot deleted. Both assertions below name the thing that must be
// true, not the thing that happens to be there.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FilterRow, FilterRowAction } from "./FilterRow";

describe("FilterRow (DEF-LED-6728)", () => {
  it("aligns from the top, so nothing under a control moves it", () => {
    const { container } = render(
      <FilterRow data-filter-row="probe">
        <div className="field">
          <label className="field-label" htmlFor="a">
            A
          </label>
          <input id="a" />
        </div>
      </FilterRow>,
    );
    const row = container.querySelector('[data-filter-row="probe"]');
    expect(row).not.toBeNull();
    expect(row?.className).toContain("items-start");
    // The defect, named so it cannot come back quietly.
    expect(row?.className).not.toContain("items-end");
  });

  it("reserves the action's label slot with the kit's own element", () => {
    const { container } = render(
      <FilterRowAction>
        <button type="button">Apply</button>
      </FilterRowAction>,
    );
    const cell = container.querySelector("[data-filter-row-action]");
    expect(cell).not.toBeNull();
    // `.field` + `<label>` is what earns the kit's 5px rule; a `<span>` gets
    // the other one and the button lands 1px high.
    expect(cell?.classList.contains("field")).toBe(true);
    const reserved = cell?.querySelector("label.field-label");
    expect(reserved).not.toBeNull();
    expect(reserved?.getAttribute("aria-hidden")).toBe("true");
    // Reserved means EMPTY of words, not absent: it is a slot, not a label.
    expect((reserved?.textContent ?? "").trim()).toBe("");
    expect(screen.getByRole("button", { name: "Apply" })).toBeTruthy();
  });

  it("applies on Enter when the caller asks for a form", () => {
    let applied = 0;
    const { container } = render(
      <FilterRow onSubmit={() => (applied += 1)} action={<button type="submit">Apply</button>}>
        <div className="field" />
      </FilterRow>,
    );
    const form = container.querySelector("form");
    expect(form).not.toBeNull();
    form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    expect(applied).toBe(1);
  });
});
