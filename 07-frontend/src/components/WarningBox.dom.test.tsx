// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:  US-INT-027 (EP-INT-07) — the dated warning, CR-069 wave H task H4
// Rules:  B14 rule 36 (the shared kit is how a screen complies) · rule 32 (a
//         stated absence is CLOSED by default) · rule 21's per-file clause
//         (a utility is emitted only for a file on `route-b-migrated.txt`)
// ───────────────────────────────────────────────────────
//
// ⚠ `.dom.test.tsx` AND THE DOCBLOCK ON LINE 1 ARE BOTH LOAD-BEARING. The suite
// runs in a NODE environment by default — jsdom would slow every static test
// and can change their behaviour — so a file that renders has to opt in.
// Written as a plain `.test.tsx` this file failed with `document is not
// defined`, which is a loud failure and therefore the good kind.
//
// ⚠ AND `afterEach(cleanup)` IS NOT DECORATION. Without it every `render` in
// this file leaves its markup in `document.body`, and the second one reports
// *"Found multiple elements with the role status"* — a failure that reads like
// a bug in the component and is a bug in the test. It cost two runs here.
//
// ⚠ THERE ARE NO `toBeInTheDocument` MATCHERS IN THIS SUITE. jest-dom is not
// registered, so every assertion below is a plain one on a real node. That is
// the house style (`ConfirmDialogTier.dom.test.tsx`), and a chai property that
// does not exist fails as *"Invalid Chai property"* rather than as a passing
// assertion — which is the one thing that would have been dangerous.
import { cleanup, render, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { WarningBox } from "./WarningBox";

afterEach(cleanup);

describe("WarningBox", () => {
  it("shows the sentence it is given, whole", () => {
    const { container } = render(
      <WarningBox tone="soon" sentence="Needs re-authorising by 09/12/2026." />,
    );
    expect(container.textContent).toContain("Needs re-authorising by 09/12/2026.");
  });

  it("carries the tone as data so a walkthrough can tell the two apart", () => {
    const soon = render(<WarningBox tone="soon" sentence="soon" />);
    expect(
      soon.container.querySelector("[data-warning-tone]")?.getAttribute("data-warning-tone"),
    ).toBe("soon");
    cleanup();
    const now = render(<WarningBox tone="now" sentence="now" />);
    expect(
      now.container.querySelector("[data-warning-tone]")?.getAttribute("data-warning-tone"),
    ).toBe("now");
  });

  it("draws no note and no action when it was given none (B14 rule 32)", () => {
    const { container } = render(<WarningBox tone="soon" sentence="just the sentence" />);
    expect(container.querySelector("[data-warning-note]")).toBeNull();
    expect(container.querySelectorAll("button").length).toBe(0);
  });

  it("draws the note and the action when it has them", () => {
    const { container } = render(
      <WarningBox
        tone="soon"
        sentence="a sentence"
        note="It takes about a minute."
        action={<button type="button">Re-authorise now</button>}
      />,
    );
    expect(container.querySelector("[data-warning-note]")?.textContent).toBe(
      "It takes about a minute.",
    );
    expect(within(container).getByRole("button").textContent).toBe("Re-authorise now");
  });

  it("is a status rather than an alert — a lapse in eleven days is not a fire", () => {
    const { container } = render(<WarningBox tone="soon" sentence="eleven days" />);
    const box = container.querySelector("[data-warning-tone]");
    expect(box?.getAttribute("role")).toBe("status");
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });

  // ⚠ THE ONE THAT GUARDS THE SILENT FAILURE B14 RULE 21 IS ABOUT. A Tailwind
  // utility in a file NOT on `route-b-migrated.txt` renders as nothing at all
  // while every `toContain` assertion still passes, because the class IS in the
  // DOM. This asserts the other half of the same trap: the class is a WHOLE
  // string per tone, never `border-${tone}`, which the compiler never sees and
  // therefore never emits.
  it("uses a whole class string per tone, never an interpolated one", () => {
    const first = render(<WarningBox tone="soon" sentence="s" />);
    const soon = first.container.querySelector("[data-warning-tone]")?.className ?? "";
    cleanup();
    const second = render(<WarningBox tone="now" sentence="s" />);
    const now = second.container.querySelector("[data-warning-tone]")?.className ?? "";
    // ⚠ `border-warning-700`, NOT `border-amber-600`. The first was a Tailwind
    // DEFAULT-palette name this product does not have, so it was never emitted
    // and the box drew with no coloured border — `DEF-INT-4236`, found by
    // reading a screenshot. This assertion passed the whole time, because the
    // class WAS in the DOM. `routeBUtilities.test.ts` is where a name that no
    // stylesheet declares is caught; this one only pins the tone apart.
    expect(soon).toContain("border-warning-700");
    expect(now).toContain("border-danger");
    expect(soon).not.toEqual(now);
  });
});
