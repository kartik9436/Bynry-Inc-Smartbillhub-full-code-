// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-6164 — RAT-03's tier ladder, reported by the Product Owner
//          on the deployed build v2.325.1 as THREE faults: "align all input
//          field in one row", "UI breaking at bottom", and "'Leave blank on the
//          last row for no upper limit.' This text is reapeted". The first and
//          the third were ONE cause: `help={t("rating.tier.toHelp")}` sat
//          inside `tiers.map(...)`, so the sentence printed once per block AND
//          made that one field's box 103px against 60px for its neighbours,
//          lifting the `To` input 43px off the row's baseline.
// Drawing: Plans & Rates Blueprint p046 — the sentence ONCE, after the last
//          row, with all four controls on one line.
// Record:  04-docs/05-modules/06-rating/conformance/CR-087-p045-create-step3-rates.md
//          divergence D4 recorded the repetition when it was written and
//          nothing turned that record into a check. This file is that check.
// Rules:   B14 rule 32 clause 3 (a row never repeats what its own control
//          offers) · rule 33 (an INSTRUCTION is <=6 words PER SENTENCE) ·
//          rule 38 (form CONSTRUCTION is ours where it disagrees with a
//          drawing) · hard-won law 7 (prove a guard RED before trusting it
//          green, and ask what would make it pass WRONGLY).
// Note:    ⚠ **WHAT THIS FILE CANNOT SEE, SAID OUT LOUD.** jsdom has no layout:
//          `getBoundingClientRect` is all zeroes, so NOTHING here can measure
//          the 43px or the 1088px-wide button. It checks the three SOURCE-
//          CHECKABLE halves — the sentence is written once, it is not inside a
//          field's box, and the last row points at it. The measurement lives in
//          `10-scripts/def_rat_6164_tier_row_walkthrough.mjs`, which runs a
//          browser. A test that claimed the row was aligned would be law 7's
//          fourth shape: a check looking at the wrong thing.
// ───────────────────────────────────────────────────────
import { cleanup, render as mount } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { TierLadder } from "./RateScheduleWizard";
import type { TierDraft } from "./RateScheduleWizard";

afterEach(cleanup);

const t = (key: string): string => i18n.t(key) as string;

/** `n` blocks, contiguous, the last one open-ended — the shape the drawing
 *  draws and the shape a clerk actually types. */
const ladder = (n: number): TierDraft[] =>
  Array.from({ length: n }, (_, i) => ({
    from_qty: String(i * 10),
    to_qty: i === n - 1 ? "" : String((i + 1) * 10),
    unit_price: "3.2000",
  }));

const renderLadder = (n: number): HTMLElement => {
  const { container } = mount(
    <TierLadder tiers={ladder(n)} fieldErrors={{}} onChange={() => undefined} />,
  );
  return container;
};

/** Every element whose text is the ladder's sentence, wherever it lives. Found
 *  by its TEXT and not by a class, so moving the sentence somewhere tidier
 *  cannot make this check stop looking at it. */
const sentences = (container: HTMLElement): HTMLElement[] =>
  Array.from(container.querySelectorAll("p")).filter(
    (p) => (p.textContent ?? "").trim() === t("rating.tier.toHelp"),
  );

// ═══════════════════════════════════════════════════════════════════════════
describe("DEF-RAT-6164 — the ladder states its one rule once", () => {
  // ⚠ **THE CONTROL CASE COMES FIRST**, so the fixture is shown able to FIND
  // the sentence before any case asserts how many there are. Without it,
  // "exactly one" and "the selector is broken and finds none" are the same
  // green.
  it("CONTROL: the sentence is on screen at all, and it is the catalogue's", () => {
    const container = renderLadder(3);
    expect(sentences(container)).toHaveLength(1);
    expect(sentences(container)[0]?.textContent).toBe(
      "Leave the last To blank. That block has no upper limit.",
    );
  });

  it.each([1, 2, 3, 6])("prints it exactly once over %i block(s)", (n) => {
    const container = renderLadder(n);
    expect(container.querySelectorAll(".rating-tier-row")).toHaveLength(n);
    // The reported defect, as a number: BEFORE this fix it was `n`.
    expect(sentences(container)).toHaveLength(1);
  });

  it("does not print it at all when the ladder has no rows", () => {
    // The percent card's flat case passes an EMPTY ladder and draws its price
    // above; there is no `To` box for the sentence to be about.
    const container = renderLadder(0);
    expect(sentences(container)).toHaveLength(0);
    expect(container.querySelector("button")?.textContent).toBe(t("rating.tier.add"));
  });

  it("writes it OUTSIDE every field's box, which is what kept the row off one line", () => {
    const container = renderLadder(3);
    // `TextField` spells a `help=` prop's element `${id}-help`. Not one may
    // exist: that spelling IS the defect, and it is what made the To box 43px
    // taller than its neighbours.
    for (let i = 0; i < 3; i += 1) {
      expect(container.querySelector(`#tier-to-${i}-help`)).toBeNull();
    }
    expect(sentences(container)[0]?.closest(".field")).toBeNull();
  });

  it("is still attached to the LAST row's To, and to no other row's", () => {
    const container = renderLadder(3);
    const id = sentences(container)[0]?.id;
    expect(id).toBeTruthy();
    const described = (i: number): string =>
      container.querySelector(`#tier-to-${i}`)?.getAttribute("aria-describedby") ?? "";
    expect(described(2).split(/\s+/)).toContain(id);
    // It says "the LAST row", so it is true of the last row only — printing it
    // against rows 0 and 1 is what made it wrong on five rows out of six.
    expect(described(0)).not.toContain(id);
    expect(described(1)).not.toContain(id);
  });

  it("keeps the sentence within B14 rule 33 — two sentences, six words each", () => {
    // An INSTRUCTION caps at 6 words PER SENTENCE, at most two sentences. The
    // old copy was ONE sentence of ten. No gate reads this string — G33 walks
    // refusal keys only and G129 walks `metering.premises*`/`metering.units*`
    // — so the cap is asserted here or it is asserted nowhere.
    const parts = t("rating.tier.toHelp")
      .split(/(?<=[.!?])\s+/)
      .filter((s) => s.trim() !== "");
    expect(parts.length).toBeLessThanOrEqual(2);
    for (const part of parts) {
      expect(part.split(/\s+/).length).toBeLessThanOrEqual(6);
    }
  });

  it("gives + Add tier a wrapper, so a column-flex Panel cannot stretch it", () => {
    // The "UI breaking at bottom" half. `Panel` is `display:flex;
    // flex-direction:column`, so a Button that is its DIRECT child becomes a
    // flex item and stretches across the cross axis — measured at 1088px,
    // against 69px for `Back`. jsdom cannot measure that; what it CAN check is
    // that the button has a wrapper OF ITS OWN.
    //
    // ⚠ **THE FIRST DRAFT OF THIS CASE PASSED AGAINST THE PRE-FIX CODE** —
    // hard-won law 7's second habit, *ask what would make this check pass
    // wrongly*, and it did. It asserted `parentElement.tagName === "DIV"`,
    // which is true either way: Testing Library mounts into a `<div>`, so an
    // UNWRAPPED button reports a DIV parent too. What separates the two worlds
    // is that the wrapper holds the button ALONE, where the mount container
    // holds the rows and the sentence as well.
    const container = renderLadder(2);
    const add = Array.from(container.querySelectorAll("button")).find(
      (b) => b.textContent === t("rating.tier.add"),
    );
    expect(add).toBeTruthy();
    const wrapper = add?.parentElement;
    expect(wrapper?.tagName).toBe("DIV");
    expect(wrapper?.children).toHaveLength(1);
    expect(wrapper?.querySelectorAll(".rating-tier-row")).toHaveLength(0);
  });
});
