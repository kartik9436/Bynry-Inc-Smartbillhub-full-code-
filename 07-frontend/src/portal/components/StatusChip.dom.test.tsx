// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    CR-068 (the customer portal) — the KIT half
// Screens:  every portal screen that draws a status word (12 of them)
// Defect:   DEF-CWP-4002 — the portal's status chips render in sentence case
//           (`Cleared`, `In service`) where the wireframe draws them
//           UPPERCASE and letter-spaced (`CLEARED`, `IN SERVICE`, `DUE`,
//           `BOUNCED`). `13-wireframe-delta.md` row X3.
// Rules:    B14 rule 36 (one visual decision, in the kit) · rule 21 (Tailwind
//           utilities, and this folder is on route-b-migrated.txt)
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **WHY THIS ASSERTS CLASSES AND WHAT ANSWERS THE OBVIOUS OBJECTION.** A
// `toContain("uppercase")` is the assertion shape CLAUDE.md warns about: a
// class name is in the DOM whether or not any stylesheet declares it, so the
// test passes on a chip that renders in sentence case. Two things close that
// hole here and neither is this file:
//
//   1. `src/styles/routeBUtilities.test.ts` loads the REAL Tailwind compiler
//      and fails any class in a listed file that compiles to nothing —
//      `portal/` is a listed directory, so these two utilities are checked
//      against the compiler by a merge-blocking test.
//   2. `uppercase tracking-wide` is the pair `SectionTitle` already writes in
//      this same file, so the theme demonstrably emits both.
//
// The case itself is only ever finally confirmed by looking at the screen
// (hard-won law 6), and that is recorded in the lane report rather than
// claimed here.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { StatusChip } from "./primitives";

afterEach(cleanup);

describe("StatusChip", () => {
  it("draws a status word UPPERCASE and letter-spaced (DEF-CWP-4002, delta X3)", () => {
    render(<StatusChip tone="success">Cleared</StatusChip>);
    const chip = document.querySelector("[data-chip]") as HTMLElement;
    expect(chip).not.toBeNull();
    expect(chip.className).toContain("uppercase");
    expect(chip.className).toContain("tracking-wide");
  });

  it("keeps the WORD itself in the catalogue's own case", () => {
    // ⚠ The case is a PRESENTATION decision and belongs to the kit; the word
    // is the owning screen's and its catalogue's. Uppercasing in CSS rather
    // than in the string is what lets `ja-JP`, `ko-KR` and `hi` — which have
    // no letter case at all — render the same chip unharmed, and it keeps the
    // accessible name readable rather than shouted.
    render(<StatusChip tone="warning">Due in 12 days</StatusChip>);
    expect(screen.getByText("Due in 12 days")).toBeInTheDocument();
  });

  it("still carries the tone handle every screen's test selects on", () => {
    render(
      <StatusChip tone="danger" testKey="state-BL-1">
        Overdue
      </StatusChip>,
    );
    expect(document.querySelector('[data-chip="state-BL-1"]')).not.toBeNull();
  });
});
