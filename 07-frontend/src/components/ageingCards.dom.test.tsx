// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `P0.11` of `05-prototype/06 Payments Page Blueprint.pdf` — *"Kit:
//           ageing cards and the stage rail"*. Outcome: *"Payments draws the
//           runner's rail and the debtor bands from the kit, not from copies."*
// Rules:    B14 rule 36 (the kit is how you comply) · B14 rule 37 (a drawn
//           figure is an ILLUSTRATION) · B14 rule 21 (utilities, no stylesheet
//           class)
// Screens:  7·1 Debtors
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT THIS FILE IS ACTUALLY FOR, AND IT IS NOT THE PIXELS.** The kit had a
// read-only strip (`KPIStrip`) and the drawing asks for cards that FILTER. The
// two are one keystroke apart to look at and opposite to use, so every case
// below is about the behaviour a clerk gets: pressing narrows, pressing the
// same one again clears, and the colour names the AGE rather than the amount.
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgeingCards } from "./AgeingCards";
import type { AgeingBand } from "./AgeingCards";

afterEach(cleanup);

/** ⚠ **THE FIGURES ARE THE BLUEPRINT'S AND THEY ARE ILLUSTRATIONS** (B14 rule
 *  37). Nothing here computes a share or a total; the caller does, and this
 *  component is asserted only on what it does with what it is handed. */
const BANDS: AgeingBand[] = [
  { id: "current", label: "Not yet due", value: "$389.64", detail: "4.4% of the debt", tone: "neutral" },
  { id: "1-30", label: "1–30 days", value: "$6,712.26", detail: "75.7% of the debt", tone: "warning" },
  { id: "31-60", label: "31–60 days", value: "$108.88", detail: "1.2% of the debt", tone: "warning" },
  { id: "61-90", label: "61–90 days", value: "$1,659.80", detail: "18.7% of the debt", tone: "danger" },
  { id: "90+", label: "90+ days", value: "$0.00", detail: null, tone: "danger" },
];

function mount(selectedId: string | null, onSelect = vi.fn()) {
  const result = render(
    <AgeingCards
      label="Ageing"
      bands={BANDS}
      selectedId={selectedId}
      onSelect={onSelect}
    />,
  );
  return { ...result, onSelect };
}

describe("P0.11 — the ageing cards are controls, not tiles", () => {
  it("draws one pressable card per band, in the order it is given", () => {
    const { container } = mount(null);
    const cards = [...container.querySelectorAll("button[data-band]")];
    expect(cards.map((card) => card.getAttribute("data-band"))).toEqual([
      "current",
      "1-30",
      "31-60",
      "61-90",
      "90+",
    ]);
    // ⚠ `aria-pressed` and NOT `aria-selected`: a screen reader announcing
    // "tab" for a filter tells a clerk the list will be REPLACED rather than
    // narrowed.
    expect(cards.every((card) => card.getAttribute("aria-pressed") === "false")).toBe(true);
  });

  it("pressing a card narrows the list to that band", () => {
    const { container, onSelect } = mount(null);
    fireEvent.click(container.querySelector('button[data-band="61-90"]') as HTMLButtonElement);
    expect(onSelect).toHaveBeenCalledWith("61-90");
  });

  it("pressing the SELECTED card again clears the filter", () => {
    // Without this a clerk who has narrowed to 61–90 has to find the toolbar's
    // ✕ to get back — which is the control the cards were meant to replace.
    const { container, onSelect } = mount("61-90");
    const card = container.querySelector('button[data-band="61-90"]') as HTMLButtonElement;
    expect(card.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(card);
    expect(onSelect).toHaveBeenCalledWith(null);
  });

  it("the colour names the AGE, and a band holding nothing keeps its tier", () => {
    // ⚠ **THE FALSE PASS THIS CASE EXISTS FOR.** A tone computed from the
    // AMOUNT would make `90+ DAYS` grey while it holds `$0.00` and red the
    // moment a bill crosses ninety days — a strip that changes shape as money
    // moves, which is the opposite of a scale a clerk reads by position.
    const { container } = mount(null);
    const ninety = container.querySelector('button[data-band="90+"]') as HTMLButtonElement;
    expect(ninety.textContent).toContain("$0.00");
    expect(ninety.className).toContain("border-t-danger-500");
    expect(
      (container.querySelector('button[data-band="current"]') as HTMLButtonElement).className,
    ).toContain("border-t-divider");
  });

  it("a band with nothing to say under the figure draws no second line", () => {
    // B14 rule 32 gives a section ONE sentence and permits none. A share of
    // nothing is undefined, and "0%" is a claim.
    const { container } = mount(null);
    const ninety = container.querySelector('button[data-band="90+"]') as HTMLButtonElement;
    expect(ninety.querySelectorAll("span").length).toBe(2);
    const first = container.querySelector('button[data-band="current"]') as HTMLButtonElement;
    expect(first.querySelectorAll("span").length).toBe(3);
  });

  it("the group carries a name, so five buttons in a row are usable without a mouse", () => {
    const { container } = mount(null);
    const group = container.querySelector("[data-ageing-cards]") as HTMLElement;
    expect(group.getAttribute("role")).toBe("group");
    expect(group.getAttribute("aria-label")).toBe("Ageing");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: payments blueprint p13 `P0.11` · §03 screen 7·1 rendered at 2.0
// generated: 2026-09-22 by LANE P0-FE
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest src/components/ageingCards.dom.test.tsx · tsc --noEmit · routeBUtilities.test.ts
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
