// ── Trace ──────────────────────────────────────────────
// Change:   DEF-CWP-3655 — the customer portal's second component kit is folded
//           onto this one under B14 rule 36. `Panel` gained `tone`, `trailing`
//           and `as="aside"` to hold what the two portal `Panel`s did.
// Rules:    B14 rule 36 (the kit is how a screen complies) · CR-018 §6 (a
//           migrated component renders identically to its pre-migration self)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE FIRST CASE IS THE ONLY ONE THAT PROTECTS 149 OTHER SCREENS.** Both
// new props are optional, and the claim in `Panel.tsx`'s own docstring is that
// absent takes the OLD path — no wrapper element, the same class string, the
// same attributes. That claim is exactly the kind hard-won law 1 is about: a
// comment saying a container is unchanged is not the container being unchanged.
// So the pre-change markup is written out here as a literal and compared byte
// for byte, rather than re-derived from the component that would have to be
// wrong for the test to matter.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Panel } from "./Panel";

const BEFORE_PLAIN =
  '<div data-panel="" class="border border-divider bg-surface p-4 mb-4 ' +
  '[&amp;_h3]:text-h5 [&amp;_h3]:m-0 [&amp;_h3]:mb-2">body</div>';

describe("Panel (DEF-CWP-3655 — the portal's two Panels fold onto this one)", () => {
  it("renders byte-for-byte what it rendered before `tone` and `trailing` existed", () => {
    expect(renderToStaticMarkup(<Panel>body</Panel>)).toBe(BEFORE_PLAIN);
  });

  it("a title with no trailing control is still a bare <h3>, with no wrapper row", () => {
    const html = renderToStaticMarkup(<Panel title="Opening hours">body</Panel>);
    expect(html).toContain("<h3>Opening hours</h3>body");
    expect(html).not.toContain("justify-between");
  });

  it("a trailing control puts the title in a row — and only then", () => {
    const html = renderToStaticMarkup(
      <Panel title="Answers" trailing={<span>See all</span>}>
        body
      </Panel>,
    );
    expect(html).toContain('class="flex items-start justify-between gap-3"');
    expect(html).toContain("<h3>Answers</h3><span>See all</span>");
  });

  // ⚠ ONE `border-color`, FILLED ONCE. Two utilities that set the same property
  // are decided at BUILD time, not by the order of the class attribute — the
  // finding `buttonKit.ts` records for variants, one container up. A tone that
  // APPENDED `border-info-700` would leave `border-divider` in the string and
  // render whichever the compiler emitted last.
  it("a tone REPLACES the border colour rather than adding a second one", () => {
    const info = renderToStaticMarkup(<Panel tone="info">body</Panel>);
    expect(info).toContain("border-info-700");
    expect(info).not.toContain("border-divider");
    expect(info).toContain('data-tone="info"');
    const warning = renderToStaticMarkup(<Panel tone="warning">body</Panel>);
    expect(warning).toContain("border-warning-500");
    expect(warning).not.toContain("border-divider");
    // A tone is a border, not a fill: the surface stays the surface.
    expect(warning).toContain("bg-surface");
  });

  it("plain writes no data-tone, so nothing downstream has to special-case it", () => {
    expect(renderToStaticMarkup(<Panel>body</Panel>)).not.toContain("data-tone");
  });

  // The portal's rail panels are `<aside>`s. Rendering one as a `<div>` moves
  // the accessibility tree — the mistake `Panel.tsx` already records for the 47
  // `<section>` call sites a codemod skipped.
  it("renders as the element the caller named", () => {
    expect(renderToStaticMarkup(<Panel as="aside">body</Panel>)).toMatch(/^<aside/);
    expect(renderToStaticMarkup(<Panel as="section">body</Panel>)).toMatch(/^<section/);
  });
});
