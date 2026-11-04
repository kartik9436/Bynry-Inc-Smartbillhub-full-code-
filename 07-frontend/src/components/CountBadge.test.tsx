// @vitest-environment jsdom
//
// ── Trace ──────────────────────────────────────────────
// Change:  Finance blueprint `P2.15` — the pending count that rides in a view
//          label. Named by three of the blueprint's *Components to use* tables.
// Rules:   B14 rule 43 (a piece of UI used twice is a COMPONENT) · rule 32 (a
//          screen has a description budget) · rule 33 (a LABEL is ≤ 3 words;
//          this renders a NUMBER and no words at all)
// ───────────────────────────────────────────────────────
import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CountBadge } from "./CountBadge";

afterEach(cleanup);

describe("P2.15 · CountBadge", () => {
  it("renders the count, and names what it is OF for a screen reader", () => {
    render(<CountBadge count={2} srLabel="waiting for a decision" />);
    expect(screen.getByText("2")).toBeTruthy();
    // ⚠ **THE NUMBER ALONE TELLS A NON-SIGHTED USER NOTHING.** *"Write-offs 2"*
    // works visually because the label is beside it; read aloud out of order it
    // is just "two".
    expect(screen.getByText("waiting for a decision")).toBeTruthy();
  });

  it("the number is not announced twice", () => {
    const { container } = render(<CountBadge count={2} srLabel="waiting" />);
    // The digit and the sentence describe ONE fact. The digit is hidden from
    // the accessibility tree rather than read as a second thing.
    expect(container.querySelector('[aria-hidden="true"]')?.textContent).toBe("2");
  });

  it("ZERO renders nothing at all", () => {
    // A badge reading `0` beside *Write-offs* is noise on four of five views
    // for a whole quiet month. PROVED RED FIRST against an early draft whose
    // guard was `if (!count)` reversed — it rendered `0` and this case failed
    // with: expected '<span class="ml-1.5 …">0…</span>' to be null.
    const { container } = render(<CountBadge count={0} srLabel="waiting" />);
    expect(container.querySelector("[data-count]")).toBeNull();
  });

  it("a count that is not known yet renders nothing either", () => {
    // `null` and `undefined` mean *not loaded*, and a clerk acts identically on
    // *nothing waiting* and *we do not know yet* — so the two are deliberately
    // indistinguishable on screen. B14 rule 33 puts the rationale at ZERO words.
    for (const count of [null, undefined]) {
      cleanup();
      const { container } = render(<CountBadge count={count} srLabel="waiting" />);
      expect(container.querySelector("[data-count]"), String(count)).toBeNull();
    }
  });

  it("carries the count as data, so a strip test can read it without the label", () => {
    const { container } = render(<CountBadge count={17} srLabel="waiting" />);
    expect(container.querySelector("[data-count]")?.getAttribute("data-count")).toBe("17");
  });

  it("uses only tokens the theme declares", () => {
    // ⚠ `src/styles/tailwind.css` sets `--color-*: initial`, which DELETES
    // Tailwind's stock palette — `text-gray-500` would compile to NOTHING while
    // `tsc`, eslint and `toContain("text-gray-500")` all passed, because the
    // class IS in the DOM (`DEF-974` · `DEF-SHL-5088`). This file is on
    // `route-b-migrated.txt`, so `routeBUtilities.test.ts` compiles every class
    // here through the real Tailwind and is the check that actually knows.
    // This case pins only the one decision a reader would otherwise have to
    // guess at: the default tone is the muted one.
    const { container } = render(<CountBadge count={3} srLabel="waiting" />);
    expect(container.querySelector("[data-count]")?.className).toContain("text-neutral-700");
    cleanup();
    const accent = render(<CountBadge count={3} srLabel="waiting" tone="accent" />);
    expect(accent.container.querySelector("[data-count]")?.className).toContain("text-accent");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/07 Finance Blueprint.pdf p014 (`P2.15`), p030, p039,
//         p041 — rendered at scale 3 and read as IMAGES (B14 rule 42)
// generated: 2026-09-24 by LANE FIN-P2B
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
