// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Defect:  DEF-CWP-9164 — PO 2026-10-02: Back on the LEFT, Continue / Send on
//          the RIGHT, on every step and every portal form. `WizardFooter` is the
//          one place that order lives; this file asserts it, and asserts that
//          every portal screen with a way back in its footer goes through it.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { WizardFooter } from "./primitives";

afterEach(cleanup);

/** Read through Vite's `?raw`, never `node:fs` — this app's tsconfig carries no
 *  `@types/node` (`ConfirmDialogTier.dom.test.tsx` records the same trap). */
const PORTAL_SOURCES = import.meta.glob("../**/*.tsx", {
  query: "?raw",
  eager: true,
  import: "default",
}) as Record<string, string>;

describe("WizardFooter (DEF-CWP-9164)", () => {
  it("puts the way back FIRST and on the left, the commit LAST and on the right", () => {
    const { container } = render(
      <WizardFooter back={<button data-k="back">Back</button>} forward={<button data-k="go">Continue</button>} />,
    );
    const footer = container.querySelector("[data-wizard-footer]") as HTMLElement;
    expect(footer.className).toContain("justify-between");
    const order = Array.from(footer.querySelectorAll("button")).map((one) => one.getAttribute("data-k"));
    // DOM order IS the reading and tab order — Back, then the commit.
    expect(order).toEqual(["back", "go"]);
    expect(footer.querySelector('[data-footer-side="back"] [data-k="back"]')).not.toBeNull();
    const forward = footer.querySelector('[data-footer-side="forward"]') as HTMLElement;
    expect(forward.className).toContain("ml-auto");
    expect(forward.querySelector('[data-k="go"]')).not.toBeNull();
  });

  it("with no way back, the commit still sits on the right", () => {
    const { container } = render(<WizardFooter forward={<button>Continue</button>} />);
    expect(container.querySelector('[data-footer-side="back"]')?.children).toHaveLength(0);
    expect(container.querySelector('[data-footer-side="forward"]')?.className).toContain("ml-auto");
  });

  /**
   * ⚠ **THE ORDER IS ONLY ONE PLACE IF EVERY SCREEN USES THE ONE PLACE.** Each
   * of these screens hand-placed its own *commit, then Back* row until
   * 2026-10-02. A source read is the cheapest check that none of them went
   * back to a hand-made row with its way back in it.
   */
  it.each([
    "../guest/ApplyForService.tsx",
    "../guest/QuickService.tsx",
    "../requests/StopOrRestart.tsx",
    "../requests/DisputeBill.tsx",
    "../payments/PayNow.tsx",
    "../payments/PayNowCheck.tsx",
    "../methods/Methods.tsx",
  ])("%s builds its footer from WizardFooter", (file) => {
    const source = PORTAL_SOURCES[file];
    expect(source, `${file} was not found`).toBeDefined();
    expect(source).toContain("<WizardFooter");
  });
});
