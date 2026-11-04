/* DEF-CUS-6350 — the kit's check list, the Approve window's rows.
 *
 * Asserted on the RENDERED markup, per state, because the defect this kit piece
 * exists for is a clerk not being TOLD: a row that carried the right state and
 * drew the wrong glyph or colour would pass any assertion made on props. */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CheckList } from "./CheckList";
import type { CheckRow } from "./CheckList";

const STATE_LABELS = {
  ok: "Passed",
  bad: "Blocked",
  noted: "Noted",
  notReached: "Not reached",
} as const;

/** The PO-approved layout for a move-in, row for row (decision log 2026-09-23). */
const MOVE_IN: CheckRow[] = [
  { id: "premises_on_file", label: "Property", state: "ok", fact: "highland park, Ottumwa" },
  { id: "unit_chosen", label: "Unit", state: "ok", fact: "U-00003 · 1" },
  { id: "unit_free", label: "Unit free", state: "bad", fact: "Occupied · AC-2026-00012" },
  { id: "documents_verified", label: "Documents", state: "noted", fact: "2 not checked" },
  { id: "fee_settled", label: "Fee", state: "ok", fact: "$70.00 paid" },
];

function render(rows: CheckRow[] = MOVE_IN): string {
  return renderToStaticMarkup(
    <CheckList rows={rows} label="Checks before approving" stateLabels={STATE_LABELS} />,
  );
}

describe("CheckList — one row per check, ✓ ✗ ! –", () => {
  it("draws every row in the given order, with its label and what it found", () => {
    const html = render();
    expect(html.match(/data-check="/g)).toHaveLength(5);
    let at = -1;
    for (const row of MOVE_IN) {
      const here = html.indexOf(`data-check="${row.id}"`);
      expect(here).toBeGreaterThan(at);
      at = here;
      expect(html).toContain(row.label);
      expect(html).toContain(String(row.fact));
    }
  });

  it("the blocker is ✗ in the danger tone and NAMES what it found", () => {
    const html = render();
    const row = html.slice(html.indexOf('data-check="unit_free"'));
    expect(row).toContain("✗");
    expect(row).toContain("text-danger-700");
    expect(row).toContain("Occupied · AC-2026-00012");
  });

  it("a noted row is ! in amber — seen, and never drawn as a blocker", () => {
    const html = render();
    const row = html.slice(
      html.indexOf('data-check="documents_verified"'),
      html.indexOf('data-check="fee_settled"'),
    );
    expect(row).toContain("!");
    expect(row).toContain("text-warning-700");
    expect(row).not.toContain("text-danger-700");
  });

  it("a check that never ran says so in words, grey, not as a pass", () => {
    const html = render([
      { id: "a", label: "Property", state: "bad", fact: "Not in Premises" },
      { id: "b", label: "Unit free", state: "notReached", fact: "Needs the unit first" },
    ]);
    const row = html.slice(html.indexOf('data-check="b"'));
    expect(row).toContain("–");
    expect(row).toContain("text-neutral-600");
    expect(row).not.toContain("✓");
    expect(row).toContain("Not reached");
  });

  it("the glyph is hidden from a screen reader, which hears the state's word", () => {
    const html = render();
    expect(html).toContain('aria-hidden="true"');
    for (const word of ["Passed", "Blocked", "Noted"]) {
      expect(html).toContain(`<span class="sr-only">${word}</span>`);
    }
    expect(html).toContain('aria-label="Checks before approving"');
  });

  it("an action renders under its own row and nowhere else", () => {
    const html = render([
      { id: "a", label: "Address", state: "noted", fact: "looks like Highland Park", action: <button type="button">Same property</button> },
      { id: "b", label: "Fee", state: "ok", fact: "$70.00 paid" },
    ]);
    expect(html.match(/data-check-action=""/g)).toHaveLength(1);
    expect(html.indexOf("Same property")).toBeLessThan(html.indexOf('data-check="b"'));
  });
});
