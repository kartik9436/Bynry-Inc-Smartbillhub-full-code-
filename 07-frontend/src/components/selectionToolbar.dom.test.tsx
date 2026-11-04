// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `P0.10` of `05-prototype/06 Payments Page Blueprint.pdf` — *"Kit:
//           the selection toolbar"*. Outcome: *"Two lists use it and the third
//           inherits rather than inventing a fourth pattern."*
// Rules:    B14 rule 12 (a list has ONE toolbar) · B14 rule 32 (a row of
//           controls holds only things a person can press) · B14 rule 36 (the
//           kit is how you comply)
// Screens:  2·1b the payments bulk bar · 7·1 Debtors · the reads list
// ───────────────────────────────────────────────────────
//
// ⚠ **THE TWO LISTS THAT USE IT ARE ASSERTED BY NAME IN
// `selectionToolbarWiring.test.ts`**, which reads their source in the NODE
// environment — a kit component nothing renders is the dead UI hard-won law 2
// is about, and "two lists use it" is this task's own outcome. This file is
// the rendering half.
import "@testing-library/jest-dom/vitest";

import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Button } from "./Button";
import { SelectionToolbar } from "./SelectionToolbar";

afterEach(cleanup);

function mount(extra: Record<string, unknown> = {}) {
  return render(
    <SelectionToolbar label="Selection" count="3 selected" {...extra}>
      <Button variant="secondary" onClick={() => undefined}>
        Reverse 2
      </Button>
      <Button variant="ghost" onClick={() => undefined}>
        Clear
      </Button>
    </SelectionToolbar>,
  );
}

describe("P0.10 — the row every selection bar is drawn in", () => {
  it("draws the count BOLD, and nothing beside it", () => {
    // The count is the one fact in the row that changes as a clerk ticks; the
    // rest of the bar is constant. The drawing puts the two at different
    // weights and three screens had three answers.
    const { container } = mount();
    const bar = container.querySelector("[data-selection-toolbar]") as HTMLElement;
    expect(bar.querySelector("strong")?.textContent).toBe("3 selected");
    // ⚠ A BARE `<strong>`: the reads list asserts its exact markup, and a
    // `data-` hook added for this file's convenience would have broken it.
    expect(bar.querySelector("strong")?.attributes.length).toBe(0);
  });

  it("names itself, so a bar of controls is usable without a mouse", () => {
    const { container } = mount();
    const bar = container.querySelector("[data-selection-toolbar]") as HTMLElement;
    expect(bar.getAttribute("role")).toBe("group");
    expect(bar.getAttribute("aria-label")).toBe("Selection");
  });

  it("announces itself as a status when the caller asks, and keeps its test hook", () => {
    // What a screen-reader user hears on a shipped screen is not a side effect
    // of a refactor: the reads bar chose `status` before this component existed
    // and keeps it.
    const { container } = mount({ role: "status", "data-testid": "reads-bulk-bar" });
    const bar = container.querySelector("[data-selection-toolbar]") as HTMLElement;
    expect(bar.getAttribute("role")).toBe("status");
    expect(bar.getAttribute("data-testid")).toBe("reads-bulk-bar");
  });

  it("puts a sentence that is not a control at the FAR RIGHT", () => {
    // B14 rule 32's clause. A sentence standing between two buttons reads as a
    // disabled third.
    const { container } = mount({ note: "Accept only" });
    const note = container.querySelector("[data-selection-note]") as HTMLElement;
    expect(note.className).toContain("ml-auto");
    expect(note.textContent).toBe("Accept only");
  });

  it("draws no total, no eligibility line and no note when the caller has none", () => {
    // B14 rule 32: an empty slot is not drawn. A permanent "0 excluded" on a
    // bar a clerk reads before pressing Reverse is noise in the one row that
    // must be read.
    const { container } = mount();
    expect(container.querySelector("[data-selection-eligibility]")).toBeNull();
    expect(container.querySelector("[data-selection-note]")).toBeNull();
  });

  it("draws the eligibility line where the filter chips were", () => {
    const { container } = mount({ eligibility: "2 can be reversed · 1 cannot" });
    const slot = container.querySelector("[data-selection-eligibility]") as HTMLElement;
    expect(slot.textContent).toBe("2 can be reversed · 1 cannot");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: payments blueprint p13 `P0.10` · §03 screens 2·1b (p32–p33) and 7·1 (p81–p83) rendered at 2.0
// generated: 2026-09-22 by LANE P0-FE
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest src/components/selectionToolbar.dom.test.tsx + selectionToolbarWiring.test.ts · tsc --noEmit · routeBUtilities.test.ts
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
