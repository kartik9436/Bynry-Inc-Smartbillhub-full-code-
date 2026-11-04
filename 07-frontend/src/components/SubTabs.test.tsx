// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 1 · P1.3 — the kit's second-level tab strip.
// Rules:   B14 rule 43 (a piece of UI is a COMPONENT) · rule 21 (Tailwind
//          utilities, no stylesheet class) · rule 33 (a LABEL is three words)
//          · PO ruling 2026-09-26 *"go as per phases - tasks"*, whose callout
//          ③ is enforced by the length guard asserted below.
// ───────────────────────────────────────────────────────
//
// THE THREE THINGS THAT CAN GO WRONG WITH A TAB STRIP, AND ONLY ONE OF THEM IS
// ABOUT TABS.
//
// 1 · **A ONE-TAB STRIP.** p20 callout ③: *"The strip is not drawn until the
//     second tab exists — a one-tab strip is furniture."* It is enforced in the
//     component rather than remembered by each caller, because the caller that
//     forgets is the one that draws a strip a clerk cannot use.
// 2 · **A COUNT THAT HIDES AT ZERO.** Callout ④ is explicit that `Custom · 0`
//     is the point — *"an empty sub-tab is how a clerk learns they can author a
//     report"* — so a helpful `count && …` would delete the one thing the strip
//     exists for. Zero RENDERS; absent does not.
// 3 · **A STRIP THAT NAVIGATES.** It reports an id and owns nothing else, or it
//     only works on screens shaped like the one it was written for.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SubTabs } from "./SubTabs";

afterEach(cleanup);

const TABS = [
  { id: "standard", label: "Standard", count: 45 },
  { id: "custom", label: "Custom", count: 0 },
];

describe("SubTabs", () => {
  it("draws nothing at all when there is only one tab", () => {
    const { container } = render(
      <SubTabs tabs={[TABS[0]]} activeId="standard" onSelect={() => undefined} label="Source" />,
    );
    // Not "renders but hidden" and not "renders without a border" — NOTHING.
    expect(container.innerHTML).toBe("");
  });

  it("renders a ZERO count, because zero is the thing worth saying", () => {
    render(<SubTabs tabs={TABS} activeId="standard" onSelect={() => undefined} label="Source" />);
    expect(screen.getByRole("tab", { name: "Custom · 0" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Standard · 45" })).toBeTruthy();
  });

  it("draws no separator for a tab with no count", () => {
    render(
      <SubTabs
        tabs={[{ id: "a", label: "Alpha" }, { id: "b", label: "Beta" }]}
        activeId="a"
        onSelect={() => undefined}
        label="Source"
      />,
    );
    expect(screen.getByRole("tab", { name: "Alpha" })).toBeTruthy();
    expect(screen.queryByRole("tab", { name: /·/ })).toBeNull();
  });

  it("marks exactly one tab selected and names the strip", () => {
    render(<SubTabs tabs={TABS} activeId="custom" onSelect={() => undefined} label="Report source" />);
    const strip = screen.getByRole("tablist", { name: "Report source" });
    const selected = within(strip)
      .getAllByRole("tab")
      .filter((tab) => tab.getAttribute("aria-selected") === "true");
    expect(selected).toHaveLength(1);
    expect(selected[0].textContent).toBe("Custom · 0");
  });

  it("reports the id and navigates nowhere", () => {
    const onSelect = vi.fn();
    render(<SubTabs tabs={TABS} activeId="standard" onSelect={onSelect} label="Source" />);
    fireEvent.click(screen.getByRole("tab", { name: "Custom · 0" }));
    expect(onSelect).toHaveBeenCalledWith("custom");
    // No anchor, so there is nothing here that could carry a wrong address —
    // the caller decides where an id goes.
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("adds no stylesheet class — B14 rule 21", () => {
    render(<SubTabs tabs={TABS} activeId="standard" onSelect={() => undefined} label="Source" />);
    const strip = screen.getByRole("tablist");
    // `settings-tabs` is the stylesheet this component exists to stop a fourth
    // screen reaching for. If it ever appears here, rule 21 is broken and so is
    // the reason the file was written.
    expect(strip.className).not.toContain("settings-tabs");
    for (const tab of within(strip).getAllByRole("tab")) {
      expect(tab.className).not.toContain("settings-tabs");
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 Phase 1 · P1.3 (05-prototype/09 Reports Build Brief.pdf p20 callout ③/④ read as an IMAGE)
// screens: S44
// generated: 2026-09-26 by lane REP-P1
// gates: RED PROVED FIRST — the one-tab case returned a rendered strip and the zero-count case rendered "Custom" with no count, on the first draft of the component
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
