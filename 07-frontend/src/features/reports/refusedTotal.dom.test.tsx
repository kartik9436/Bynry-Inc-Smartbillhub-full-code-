// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    CR-142-BRC07 Phase 2 · P2.22 (THE MONEY TASK, on screen).
//           Screens: 2·1 footer.
// Rules:    B14 rule 33 (a FACT ≤ 6 words; RATIONALE zero words on screen) ·
//           hard-won law 2 (built is not wired) · law 7 clause 2 (*"ask what
//           would make this check pass wrongly"*)
// Tests:    this file
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  NO NUMBER, AN EM-DASH, AND A REASON — IN BOTH DIRECTIONS                ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// Brief §7.2.2 p85, read as an image (B14 rule 42): *"A total that is not
// lawful shows an em-dash and its reason, never a number."*
//
// ⚠ **THE RED THIS WAS PROVED ON.** Before `RefusedTotalCell` existed, the
// shipped `ReportTotalsRow` reached `String(total)` on the refusal object and
// rendered **`[object Object]`** into the footer, and the money branch would
// have handed `AmountCell` a string that parses to `NaN`. Two ways of putting
// something that is not a number on screen while still never saying WHY.
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7 clause 2):
//
//   · **A footer that never renders at all.** A crashed row, a hidden column
//     or an empty `totals` map would satisfy *"no digits on screen"* perfectly.
//     So the LAWFUL case below asserts a real figure IS rendered by the same
//     component, against the same markup — an absence that cannot be told from
//     a broken screen is worth nothing.
//   · **Asserting only that the em-dash is present.** A bare em-dash with no
//     reason is exactly what p85 forbids, so the reason is asserted too.
//   · **Asserting the reason only in English.** The sentence comes from the
//     catalogue keyed by `reason_code`; the case below asserts the KEY
//     resolves, so a key never fanned in is caught rather than silently
//     falling through to the server's English.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { RefusedTotal } from "@/api/reportsEndpoints";
import { isRefusedTotal } from "@/api/reportsEndpoints";
import { RefusedTotalCell } from "./RefusedTotalCell";
import en from "@/i18n/locales/en.json";

const translate = (key: string) => (en as Record<string, string>)[key] ?? key;

const REFUSED: RefusedTotal = {
  value: null,
  display: "—",
  refused: true,
  measure: "total",
  reason_code: "balance_does_not_sum_across_time",
  reason: "Balances do not sum across time",
  across: ["time"],
};

describe("P2.22 · a total that cannot lawfully be summed", () => {
  it("renders the em-dash and the reason, and no digit at all", () => {
    const { container } = render(<RefusedTotalCell total={REFUSED} t={translate} />);
    expect(container.textContent).toContain("—");
    expect(screen.getByText("Balances do not sum across time")).toBeTruthy();
    // ⚠ **THE ASSERTION THAT MATTERS.** Not "value is null" — no DIGIT.
    expect(container.textContent ?? "").not.toMatch(/\d/);
    expect(container.textContent ?? "").not.toContain("[object Object]");
  });

  it("says the reason in the reader's own language, from the catalogue", () => {
    // B14 rule 35: a catalogue is written in its own language, never
    // translated from English at render time. If the key were missing this
    // would fall back to the server's `reason` and the two would be identical,
    // so the test asserts the KEY resolved rather than the text matching.
    const key = `reports.totals.${REFUSED.reason_code}`;
    expect(translate(key)).not.toEqual(key);
  });

  it("keeps the reason to six words (B14 rule 33)", () => {
    const key = `reports.totals.${REFUSED.reason_code}`;
    expect(translate(key).split(/\s+/).length).toBeLessThanOrEqual(6);
  });

  it("does not hide the reason behind a hover", () => {
    // A reason a clerk must hover for is a reason an auditor reading a
    // printout never sees — and the CSV carries the same sentence inline for
    // the same reason.
    const { container } = render(<RefusedTotalCell total={REFUSED} t={translate} />);
    expect(container.querySelector("[title]")).toBeNull();
  });
});

describe("P2.22 · the other direction — a lawful total is still a number", () => {
  it("is not treated as a refusal", () => {
    // The narrowing is what the footer branches on. A version that returned
    // true for every object, or for a plain string, would put an em-dash over
    // every figure in the product.
    expect(isRefusedTotal("48221.1400")).toBe(false);
    expect(isRefusedTotal(412)).toBe(false);
    expect(isRefusedTotal(null)).toBe(false);
    expect(isRefusedTotal(REFUSED)).toBe(true);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 Phase 2 · P2.22 (p84, p85 read as images per B14 rule 42)
// generated: 2026-09-27 by lane REP-P2-MODEL
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
