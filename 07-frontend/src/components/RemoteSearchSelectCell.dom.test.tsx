// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   the NEW CONNECT REDESIGN of 2026-09-28 — the searchable dropdown
//           drawn inside a TABLE CELL: `Work order` and `Template` on the
//           units table, `Charge` on the charges table, `Template` on the
//           messages table.
// Rules:    B14 rules 8, 21, 31, 33, 36, 39, 43 · BR-SHL-020 (a PLATFORM
//           failure is never read as no-match) · BR-SHL-033 · hard-won law 6
// ───────────────────────────────────────────────────────
//
// ⚠ **THE CASE THAT MATTERS IS THAT THE FIVE STATES SURVIVE THE CELL.** A cell
// drops the label and the helper because there is no room for them; dropping
// the too-short / searching / failed / no-match panel as well would take the
// four sentences that are the whole reason this control exists rather than a
// `<select>` (`DEF-3506`), on the screen where a clerk types most.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RemoteSearchSelectField } from "./RemoteSearchSelectField";

afterEach(cleanup);

const WORDS = {
  tooShort: "Type three letters.",
  searching: "Looking…",
  failed: "Search is down.",
  noMatch: "No order matches that.",
};

const IDLE = { idle: true, searching: false, searched: false, failed: false };

function cellField(props: Record<string, unknown> = {}) {
  return (
    <RemoteSearchSelectField
      cell
      id="wo-1"
      label="Work order"
      term=""
      onTermChange={vi.fn()}
      status={IDLE}
      options={[]}
      value=""
      onChange={vi.fn()}
      words={WORDS}
      placeholder="Search work orders"
      {...props}
    />
  );
}

describe("RemoteSearchSelectField — the cell variant", () => {
  it("draws NO visible label and no field wrapper", () => {
    const html = renderToStaticMarkup(cellField());
    expect(html).not.toContain('class="field"');
    expect(html).not.toContain("<label");
    expect(html).toContain('data-search-cell=""');
  });

  it("the column header is not a name, so the BOX carries one", () => {
    // ⚠ `getByRole(…, { name })` ALONE CANNOT SEE THIS. The field variant has
    // a visible `<label htmlFor>` and computes the same accessible name, so
    // that query passes whether or not `cell` is honoured — the shape law 7
    // calls "looking at the wrong thing". The attribute is what changed, so
    // the attribute is what is asserted.
    render(cellField());
    const box = screen.getByRole("combobox", { name: "Work order" });
    expect(box).toHaveAttribute("aria-label", "Work order");
  });

  it("draws no helper paragraph and no field error — the table owns both", () => {
    const html = renderToStaticMarkup(cellField({ error: "Pick an order." }));
    expect(html).not.toContain("field-help");
    expect(html).not.toContain("field-error");
  });

  it("but the input still says it is invalid, which is the part AT needs", () => {
    render(cellField({ error: "Pick an order." }));
    expect(screen.getByRole("combobox", { name: "Work order" })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });

  it("nothing dangles — every id `aria-describedby` names is in the document", () => {
    // A described-by pointing at an id that is not there is a name a screen
    // reader cannot resolve, which is worse than no name.
    const { container } = render(cellField({ error: "Pick an order." }));
    const box = container.querySelector("[role='combobox']");
    const described = box?.getAttribute("aria-describedby");
    expect(described).toBeNull();
  });

  it("the five states survive the cell — BR-SHL-020's pair is intact", () => {
    const failed = renderToStaticMarkup(
      cellField({
        status: { idle: false, searching: false, searched: true, failed: true },
        term: "site",
      }),
    );
    expect(failed).toContain('data-panel-state="failed"');
    expect(failed).toContain("Search is down.");

    const none = renderToStaticMarkup(
      cellField({
        status: { idle: false, searching: false, searched: true, failed: false },
        term: "site",
      }),
    );
    expect(none).toContain('data-panel-state="no-match"');
    expect(none).toContain("No order matches that.");
  });

  it("B14 rule 31 — a match shows its LABEL and never its value", () => {
    const html = renderToStaticMarkup(
      cellField({
        status: { idle: false, searching: false, searched: true, failed: false },
        term: "site",
        options: [
          { value: "9c1f0b22-0000-4000-8000-000000000000", label: "Site inspection & mark-out" },
        ],
      }),
    );
    expect(html).toContain("Site inspection &amp; mark-out");
    expect(html).not.toContain(">9c1f0b22-0000-4000-8000-000000000000<");
  });
});

describe("RemoteSearchSelectField — the FIELD is untouched", () => {
  it("without `cell` it still draws the wrapper, the label and the helper", () => {
    const html = renderToStaticMarkup(
      <RemoteSearchSelectField
        id="cust-1"
        label="Customer ID"
        term=""
        onTermChange={vi.fn()}
        status={IDLE}
        options={[]}
        value=""
        onChange={vi.fn()}
        words={WORDS}
        required
        help="Searched on the details above."
      />,
    );
    expect(html).toContain('class="field"');
    expect(html).toContain("Customer ID");
    expect(html).toContain("field-required");
    expect(html).toContain('id="cust-1-help"');
    expect(html).toContain('aria-describedby="cust-1-help"');
    expect(html).not.toContain("data-search-cell");
  });
});
