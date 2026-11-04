// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   the NEW CONNECT REDESIGN of 2026-09-28 — the read-only fact block,
//           promoted out of `features/customers/disconnect/DisconnectFacts.tsx`.
// Rules:    B14 rules 21, 31, 33, 36, 43, 44 · hard rule 2 · hard-won law 6
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PROMOTION IS ASSERTED, NOT ASSUMED.** `DisconnectFacts` is now a
// delegation, so a case here renders it and checks the handle its own test and
// its walkthrough read (`data-facts="account"`) is still there. A refactor that
// quietly changed that handle would leave both of them looking at nothing.
import "@testing-library/jest-dom/vitest";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DisconnectFacts } from "@/features/customers/disconnect/DisconnectFacts";

import { FactBlock } from "./FactBlock";

const FACTS = [
  { id: "3f0c5a10-0000-4000-8000-000000000000", label: "Customer", value: "1 new" },
  { id: "premises", label: "Premises", value: "1" },
  { id: "charges", label: "One-time charges", value: "$1,035.00" },
];

describe("FactBlock", () => {
  it("draws the label ABOVE the value — a definition list, not a table", () => {
    // The PO rejected read-only values drawn as disabled input boxes; this is
    // the shape that replaced them.
    const html = renderToStaticMarkup(<FactBlock facts={FACTS} name="at-a-glance" />);
    expect(html).toContain('data-facts="at-a-glance"');
    expect(html).toContain("<dl");
    expect(html.indexOf("<dt")).toBeLessThan(html.indexOf("<dd"));
    expect(html.indexOf("Customer")).toBeLessThan(html.indexOf("1 new"));
  });

  it("is never a box a clerk could try to type in", () => {
    const html = renderToStaticMarkup(<FactBlock facts={FACTS} name="plan" />);
    expect(html).not.toContain("<input");
    expect(html).not.toContain("disabled");
  });

  it("B14 rule 31 — the id keys the row and is never rendered", () => {
    const html = renderToStaticMarkup(<FactBlock facts={FACTS} name="plan" />);
    // It rides on `data-fact` as a handle; it is never TEXT a person reads.
    expect(html).toContain('data-fact="3f0c5a10-0000-4000-8000-000000000000"');
    expect(html).not.toContain(">3f0c5a10-0000-4000-8000-000000000000<");
  });

  it("absent variant is the card — byte-for-byte what the disconnect wizard drew", () => {
    const html = renderToStaticMarkup(<FactBlock facts={FACTS} name="account" />);
    expect(html).toContain("grid-cols-[repeat(auto-fit,minmax(180px,1fr))]");
    expect(html).toContain("border border-divider bg-bg p-4");
  });

  it("the strip divides its cells with the grid's own gap, so a wrapped row is ruled too", () => {
    const html = renderToStaticMarkup(
      <FactBlock facts={FACTS} name="summary" variant="strip" />,
    );
    expect(html).toContain("gap-px");
    expect(html).toContain("bg-divider");
    // Every cell paints over the container, which is what shows the hairline.
    expect(html.match(/bg-bg px-3 py-2/g)).toHaveLength(FACTS.length);
  });

  it("`rows` (CR-171 P2.32, image 45) sets label LEFT on a tinted sixth, value right, one ruled row per fact", () => {
    const html = renderToStaticMarkup(<FactBlock facts={FACTS} name="review" variant="rows" />);
    expect(html.match(/grid grid-cols-6 border-b border-divider last:border-b-0/g)).toHaveLength(FACTS.length);
    expect(html.match(/col-span-1 bg-neutral-100/g)).toHaveLength(FACTS.length);
    expect(html.match(/col-span-5/g)).toHaveLength(FACTS.length);
    // `columns` means nothing to a row table and must not leak a grid into it.
    const fixed = renderToStaticMarkup(<FactBlock facts={FACTS} name="review" variant="rows" columns={3} />);
    expect(fixed).not.toContain("grid-cols-3");
    expect(fixed).not.toContain("col-span-3");
  });

  it("a value may be nodes — the services badges on the review step", () => {
    const html = renderToStaticMarkup(
      <FactBlock
        name="services"
        facts={[{ id: "svc", label: "Services", value: <span data-badges="">W S T F</span> }]}
      />,
    );
    expect(html).toContain('data-badges=""');
  });

  it("nothing carries a fixed height, so a long value grows the block", () => {
    const html = renderToStaticMarkup(<FactBlock facts={FACTS} name="plan" variant="strip" />);
    expect(html).not.toMatch(/\bh-\d/);
    expect(html).not.toContain("height:");
  });
});

describe("DisconnectFacts — the promotion moved nothing", () => {
  it("still renders the card and still carries the handle its walkthrough reads", () => {
    const html = renderToStaticMarkup(<DisconnectFacts facts={FACTS} name="account" />);
    expect(html).toContain('data-facts="account"');
    expect(html).toContain("grid-cols-[repeat(auto-fit,minmax(180px,1fr))]");
    expect(html).toContain("Customer");
  });

  it("renders exactly what the kit renders — one implementation, not two", () => {
    // Hard-won law 5, one component down: if these two ever differ, one of
    // them is a copy that has started to drift.
    expect(renderToStaticMarkup(<DisconnectFacts facts={FACTS} name="account" />)).toBe(
      renderToStaticMarkup(<FactBlock facts={FACTS} name="account" variant="card" />),
    );
  });
});
