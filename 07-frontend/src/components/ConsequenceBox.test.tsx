// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-016 (the builder draws one on steps 3, 5, 7 and 8) — and
//           the thirteen Work screens `09-component-inventory.md` lists.
// Rules:    B14 rule 11 (a consequence preview before a commit) · rule 36 (the
//           shared kit is how you comply) · rule 21 (Tailwind utilities; this
//           file is on `src/styles/route-b-migrated.txt`)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE POINT OF THIS FILE IS THE FOLD, NOT THE BOX.** This component holds
// TWO shapes that used to be two components in two directories — the staff
// screens' tone-title-sentence strip and the customer portal's heading-and-
// bullets panel. Every case below asserts that each shape still renders what
// its own screens rendered before the move: the classes, the `data-` hooks and
// the markup. A fold that quietly changed either look would pass `tsc` and
// every screen test that only asks whether the box is present.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ConsequenceBox } from "./ConsequenceBox";

describe("ConsequenceBox — the staff shape", () => {
  it("draws the tag, the title and one sentence", () => {
    const html = renderToStaticMarkup(
      <ConsequenceBox tone="check" title="45 minutes total." body="Estimates matter." />,
    );
    expect(html).toContain("CHECK");
    expect(html).toContain("<b>45 minutes total.</b>");
    expect(html).toContain("Estimates matter.");
    expect(html).toContain('role="note"');
  });

  it("keeps the two tones the routes-and-cycles wizards shipped, class for class", () => {
    const move = renderToStaticMarkup(<ConsequenceBox tone="move" title="t" body="b" />);
    const check = renderToStaticMarkup(<ConsequenceBox tone="check" title="t" body="b" />);
    // The accent wash and the warning wash — the two the tenancy wizards drew
    // before this component moved into the kit. A fold that changed either
    // would move pixels on four live screens.
    expect(move).toContain("var(--color-accent)_6%");
    expect(check).toContain("var(--color-warning-700)_8%");
    expect(move).toContain("MOVE");
    expect(check).toContain("CHECK");
  });

  it("the tone class is a WHOLE string, never interpolated", () => {
    // B14 rule 21's per-file clause (`DEF-974`): Tailwind's scanner cannot see
    // `border-${tone}`, and a class the compiler never emitted renders as
    // NOTHING while every `toContain` still passes. Both washes appear in the
    // source as complete literals, which is what makes them compilable.
    const html = renderToStaticMarkup(<ConsequenceBox tone="publish" title="t" body="b" />);
    expect(html).toContain("border border-divider");
    expect(html).not.toContain("${");
  });

  it("a caller may name its own hook and its own tag word", () => {
    const html = renderToStaticMarkup(
      <ConsequenceBox tone="publish" title="t" body="b" tag="EFFECT" data-consequence="publish" />,
    );
    expect(html).toContain('data-consequence="publish"');
    expect(html).toContain("EFFECT");
  });

  it("the body is a node, so a consequence can bold the word that carries it", () => {
    const html = renderToStaticMarkup(
      <ConsequenceBox
        tone="publish"
        title="Publishing affects new work orders only."
        body={
          <>
            The <b>4</b> orders already raised keep what they were given.
          </>
        }
      />,
    );
    expect(html).toContain("<b>4</b>");
  });
});

describe("ConsequenceBox — the customer shape, folded in unchanged", () => {
  it("draws the heading, the bullets and the left brand rule", () => {
    const html = renderToStaticMarkup(
      <ConsequenceBox heading="What happens next" bullets={["Your service starts", "We bill you"]} />,
    );
    expect(html).toContain("What happens next");
    expect(html).toContain("Your service starts");
    expect(html).toContain("We bill you");
    // The exact classes `portal/components/primitives.tsx` rendered before the
    // fold — seventeen portal screens draw one of these.
    expect(html).toContain("border-l-4 border-l-accent");
    expect(html).toContain('data-consequence=""');
    expect(html).toContain('data-bullet="0"');
    expect(html).toContain('data-bullet="1"');
  });

  it("the two shapes are told apart by the props and never by a flag", () => {
    const customer = renderToStaticMarkup(<ConsequenceBox heading="h" bullets={["b"]} />);
    const staff = renderToStaticMarkup(<ConsequenceBox tone="check" title="t" body="b" />);
    // Neither shape leaks into the other: no bullet list on the staff strip, no
    // tag word on the customer panel.
    expect(customer).not.toContain('role="note"');
    expect(staff).not.toContain("<ul");
  });
});
