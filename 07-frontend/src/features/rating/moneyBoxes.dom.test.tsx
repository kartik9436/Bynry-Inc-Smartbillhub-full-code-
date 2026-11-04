// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-2361 — *"decimal"* (Product Owner, 2026-09-03), walking Plans &
//          Rates on the deployed build: the charge code's Amount box read
//          `0.000000` and the fire schedule's per-size prices read `12.000000`.
//          Six places is the PERCENTAGE precision.
//          DEF-2358 — `moneyIn` was landed described as *proved* with no test
//          anywhere naming it. The five worked examples below are that proof.
// Screens: S12 / CHG-02 (charge code wizard) · S9 / RAT-03 (rate schedule)
// Rules:   CLAUDE.md hard rule 2 (money stored 4, percentages 6, both DISPLAY 2)
// Note:    Written and shown RED before the split existed — hard-won law 7. The
//          failures are quoted case by case below.
// ───────────────────────────────────────────────────────
/**
 * **WHY A `.dom` SUITE AND NOT A MARKUP ASSERTION — hard-won law 2.**
 *
 * The whole of `DEF-2361` is a disagreement between what a box SHOWS and what
 * it POSTS, and only one of those is visible in first-paint markup. A static
 * `toContain("12.00")` would pass on a component that shows the trimmed value
 * and then posts it — which is the backed-out one-line fix, the one that
 * rewrites a stored price on every save. So every case here TYPES and then
 * reads the value that would go over the wire.
 *
 * ⚠ **THE CASE THAT MATTERS MOST IS THE ONE WHERE NOBODY TYPES.** A person
 * opening a charge code, changing its NAME and saving must re-post
 * `12.000000` byte for byte. That is not a nicety: `moneyIn` is lossless by
 * construction, but the moment a draft loader is allowed to re-format, every
 * save becomes an edit to a stored money value that no one asked for and
 * nothing records. `draftFromCharge` and `sizeLadders` are therefore NOT
 * touched by this change, and the six tests that pin them are unmodified.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { MoneyTextField, moneyIn } from "./ratingShared";

afterEach(cleanup);

// ── moneyIn, the five worked examples its own docstring writes out ─────────

describe("DEF-2358 · moneyIn is proved rather than described as proved", () => {
  /**
   * ⚠ **THIS FUNCTION SHIPPED ON 2026-09-03 DESCRIBED AS *written, proved and
   * left UNWIRED* IN THREE PLACES — its docstring, the commit message and the
   * `DEF-2361` register row — AND `grep -rln moneyIn src/` RETURNED EXACTLY
   * ONE FILE: the one that defines it.** Nothing was proved. Hard-won law 1:
   * a comment claiming a guarantee is not the guarantee, and an UNWIRED
   * function has no call site for coverage to miss either, so no tool in this
   * repo could have said so.
   */
  it("removes only zeros beyond the second place, and never a digit", () => {
    // The docstring's own table, byte for byte.
    expect(moneyIn("0.000000")).toBe("0.00");
    expect(moneyIn("12.000000")).toBe("12.00");
    expect(moneyIn("8.290000")).toBe("8.29");
    // KEPT — the third place is a digit, and on a rate schedule it is a
    // different price. This is the assertion that separates `moneyIn` from
    // `formatMoney`, which would round it to `8.30`.
    expect(moneyIn("8.295000")).toBe("8.295");
    expect(moneyIn("")).toBe("");
  });

  it("null and undefined read back BLANK, never as a zero amount", () => {
    // BR-RAT-690 · DEF-277 — a blank amount is a size the utility DOES NOT
    // SERVE and it refuses the bill. `?? "0"` here would silently price it.
    expect(moneyIn(null)).toBe("");
    expect(moneyIn(undefined)).toBe("");
  });

  it("hands back anything that is not a plain decimal, untouched", () => {
    // No decimal point, a partly typed value, a sign — none of these is this
    // function's business, and rewriting one would be the bug it exists to
    // avoid. Bounds and shape belong to the server (`decimalShapeError` is a
    // SHAPE test and this is not even that).
    expect(moneyIn("12")).toBe("12");
    expect(moneyIn("12.")).toBe("12.");
    expect(moneyIn("-4.500000")).toBe("-4.50");
    expect(moneyIn("abc")).toBe("abc");
  });
});

// ── the split itself, driven ──────────────────────────────────────────────

/**
 * A one-box stand-in for a wizard step: it holds a draft exactly as the real
 * ones do, and it publishes it so a case can read WHAT WOULD BE POSTED rather
 * than what is on screen.
 */
function DraftHarness(props: { initial: string; onDraft: (value: string) => void }) {
  const [draft, setDraft] = useState(props.initial);
  props.onDraft(draft);
  return (
    <MoneyTextField
      id="harness-amount"
      label="Amount"
      value={draft}
      onChange={(next) => setDraft(next)}
    />
  );
}

describe("DEF-2361 · a money box shows two places and posts the stored bytes", () => {
  /**
   * ⚠ **PROVED RED FIRST.** With `MoneyTextField` passing `props.value`
   * straight to the input — which is what all four boxes did until this
   * change — six of the eleven cases here failed, this one with:
   *
   *     Error: expect(element).toHaveValue(12.00)
   *     Expected the element to have value:
   *       12.00
   *     Received:
   *       12.000000
   *
   * which is the Product Owner's screenshot, in an assertion.
   */
  it("shows the trimmed value while nobody has typed", () => {
    let draft = "";
    render(<DraftHarness initial="12.000000" onDraft={(v) => (draft = v)} />);
    expect(screen.getByLabelText("Amount")).toHaveValue("12.00");
    // AND THE DRAFT IS UNTOUCHED. This is the half the one-line fix got wrong:
    // trimming on the way IN would make this `12.00`, and a save by somebody
    // who only edited the code's NAME would rewrite a stored price.
    expect(draft).toBe("12.000000");
  });

  it("a zero base charge reads 0.00, which is what the PO was shown", () => {
    let draft = "";
    render(<DraftHarness initial="0.000000" onDraft={(v) => (draft = v)} />);
    expect(screen.getByLabelText("Amount")).toHaveValue("0.00");
    expect(draft).toBe("0.000000");
  });

  /**
   * ⚠ **THE CASE THE BRIEF ASKS FOR: type into a trimmed field and the posted
   * body carries what was typed.**
   *
   * PROVED RED FIRST — it is one of the six that fail when the box has no
   * split at all and simply renders `props.value`.
   */
  it("typing appends to the TRIMMED value, and the draft carries exactly that", async () => {
    const user = userEvent.setup();
    let draft = "";
    render(<DraftHarness initial="12.000000" onDraft={(v) => (draft = v)} />);
    const box = screen.getByLabelText("Amount");
    await user.click(box);
    await user.keyboard("5");
    // What the person sees is what the person typed — no re-formatting behind
    // the cursor.
    expect(box).toHaveValue("12.005");
    // And what posts is the same string. This is the whole point of the split.
    expect(draft).toBe("12.005");
  });

  /**
   * ⚠ **THE MID-TYPING CASE, AND IT IS THE ONE THAT CATCHES THE *NAIVE* SPLIT
   * RATHER THAN THE MISSING ONE.** `moneyIn("12.0")` is `"12.00"` — correct
   * for a STORED value and wrong for a person half way through typing `12.05`:
   * their first keystroke after the point gets two zeros pushed in behind it.
   *
   * PROVED RED against a `MoneyTextField` written the obvious way, as
   * `moneyIn(editing ? typed : props.value)` — every other case in this file
   * passes on that version, and these two do not:
   *
   *     Error: expect(element).toHaveValue(12.0)
   *     Expected the element to have value:
   *       12.0
   *     Received:
   *       12.00
   *
   * That is why the trim is on ONE branch of the conditional and not around
   * it. A reviewer moving it back out has this case to answer to.
   */
  it("does not re-trim a value while it is being typed", async () => {
    const user = userEvent.setup();
    let draft = "";
    render(<DraftHarness initial="" onDraft={(v) => (draft = v)} />);
    const box = screen.getByLabelText("Amount");
    await user.click(box);
    await user.keyboard("12.0");
    expect(box).toHaveValue("12.0");
    expect(draft).toBe("12.0");
    await user.keyboard("5");
    expect(box).toHaveValue("12.05");
    expect(draft).toBe("12.05");
  });

  it("clearing the box posts blank, which is NOT zero", async () => {
    const user = userEvent.setup();
    let draft = "";
    render(<DraftHarness initial="12.000000" onDraft={(v) => (draft = v)} />);
    const box = screen.getByLabelText("Amount");
    await user.clear(box);
    expect(box).toHaveValue("");
    // BR-RAT-690 · DEF-277 again: blank is "not served" and stops the bill.
    // A box that answered "0" here would price a size the utility refuses.
    expect(draft).toBe("");
  });

  /**
   * The guard is the VALUE and not a mounted flag, and this is the case that
   * says so. A parent that loads a different row puts the box back into
   * display mode with no stale keystrokes to clear — which also means a React
   * instance reused across two rows of the per-size table cannot carry one
   * row's typing onto another.
   */
  it("goes back to showing the trimmed value when the draft moves underneath it", async () => {
    const user = userEvent.setup();
    function Swapper() {
      const [value, setValue] = useState("12.000000");
      return (
        <>
          <MoneyTextField id="swap" label="Amount" value={value} onChange={setValue} />
          <button type="button" onClick={() => setValue("30.000000")}>
            load another row
          </button>
        </>
      );
    }
    render(<Swapper />);
    const box = screen.getByLabelText("Amount");
    await user.click(box);
    await user.keyboard("5");
    expect(box).toHaveValue("12.005");
    await user.click(screen.getByRole("button", { name: "load another row" }));
    expect(box).toHaveValue("30.00");
  });
});

// CR-156-BRC10 wave B (2026-10-01): the third block of this file walked the
// OLD CHG-02 per-size table (`PerSizeAmounts`), which the rebuild from the 83
// charge-code images replaced. What it pinned — a typed amount is posted as
// the typed STRING — is asserted on the new wizard in
// `chargeCodeWaveB.dom.test.tsx` ("posts what was typed").
