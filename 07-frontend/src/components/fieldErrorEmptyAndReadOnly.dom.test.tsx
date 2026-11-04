// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-7800 — the Product Owner reported the charge-code Amount
//          box as "outlined red, will not accept typing, and shows no
//          message". The red turned out to be the accent FOCUS RING on an
//          empty read-only box, not a validation mark — but the field kit
//          could paint exactly that picture for real, because every component
//          branched on `error !== undefined` and that is TRUE for "".
// Rules:   B14 rule 33 (rationale is zero words on screen; a fact caps at six
//          words) · BR-SHL-017 / IS-10 (the error is announced with the input
//          it belongs to) · CLAUDE.md hard-won law 6 (no gate reads rendered
//          output) · law 7 habit 2 (ask what would make this check pass
//          wrongly).
// ───────────────────────────────────────────────────────
/**
 * **THESE CASES READ THE RENDERED DOM, NEVER THE PROPS.**
 *
 * The thing being asserted is what a person SEES: whether the danger border
 * class is on the input, whether the browser is told the field is invalid, and
 * whether a message node exists at all. A test that asserted the component was
 * *given* an empty error would pass on the bug and on the fix alike.
 *
 * ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 habit 2): asserting only
 * `queryByText("")`, which matches nothing either way, or asserting on
 * `props.error`. So each case asserts the THREE marks together — the class,
 * `aria-invalid`, and the `.field-error` node — and the control case proves a
 * real message still turns all three on.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { TextField } from "./FormModal";

afterEach(cleanup);

function marks(id: string) {
  const input = document.getElementById(id) as HTMLInputElement;
  return {
    red: input.classList.contains("input-invalid"),
    ariaInvalid: input.getAttribute("aria-invalid"),
    describedBy: input.getAttribute("aria-describedby"),
    errorNode: document.getElementById(`${id}-error`),
  };
}

describe("DEF-RAT-7800 · a field is never marked wrong with nothing to read", () => {
  it("a REAL message turns every mark on — the control case, so the others mean something", () => {
    render(
      <TextField id="probe" label="Amount" value="" onChange={() => undefined} error="Enter a number." />,
    );
    const seen = marks("probe");
    expect(seen.red).toBe(true);
    expect(seen.ariaInvalid).toBe("true");
    expect(seen.errorNode).not.toBeNull();
    expect(seen.errorNode?.textContent).toBe("Enter a number.");
    expect(seen.describedBy).toContain("probe-error");
  });

  it("an EMPTY message is no error — no red, no aria-invalid, no empty message node", () => {
    render(<TextField id="probe" label="Amount" value="" onChange={() => undefined} error="" />);
    const seen = marks("probe");
    expect(seen.red).toBe(false);
    expect(seen.ariaInvalid).toBeNull();
    expect(seen.errorNode).toBeNull();
    expect(seen.describedBy ?? "").not.toContain("probe-error");
  });

  it("a WHITESPACE message is no error either — a space is not a sentence", () => {
    render(<TextField id="probe" label="Amount" value="" onChange={() => undefined} error="   " />);
    const seen = marks("probe");
    expect(seen.red).toBe(false);
    expect(seen.ariaInvalid).toBeNull();
    expect(seen.errorNode).toBeNull();
  });

  /**
   * A clerk cannot fix a box they cannot type in, so an error drawn on one is
   * an instruction with no act attached. The refusal still reaches them on the
   * form's own refusal strip, which this kit does not own.
   */
  it("a READ-ONLY field is never marked invalid, even with a real message", () => {
    render(
      <TextField
        id="probe"
        label="Amount"
        value="12.00 – 60.00 · 6 sizes"
        readOnly
        onChange={() => undefined}
        error="Enter a number."
      />,
    );
    const seen = marks("probe");
    expect(seen.red).toBe(false);
    expect(seen.ariaInvalid).toBeNull();
    expect(seen.errorNode).toBeNull();
    // …and it is still announced as read-only rather than silently ordinary.
    expect((document.getElementById("probe") as HTMLInputElement).readOnly).toBe(true);
    expect(document.getElementById("probe")?.getAttribute("aria-readonly")).toBe("true");
  });

  it("the same field WITHOUT readOnly still shows the message, so the guard is not a blanket", () => {
    render(
      <TextField id="probe" label="Amount" value="12" onChange={() => undefined} error="Enter a number." />,
    );
    expect(marks("probe").errorNode?.textContent).toBe("Enter a number.");
  });
});
