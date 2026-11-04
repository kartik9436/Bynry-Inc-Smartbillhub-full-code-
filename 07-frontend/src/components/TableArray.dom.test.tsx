// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   the NEW CONNECT REDESIGN of 2026-09-28 — the table array, its
//           groups, its two error slots and its cell controls.
// Rules:    B14 rules 15, 17, 20, 21, 31, 33, 36, 43, 44 · BR-SHL-025 ·
//           hard rule 2 · hard-won law 2 (built is not wired) · law 6 (no gate
//           in this repo reads rendered output)
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY CASE READS RENDERED OUTPUT AND NONE OF THEM READS A PROP.** Law 6
// is that no gate here looks at what a screen draws, and law 2's whole lesson
// is that `expect(props.x).toBe(y)` passes over a component that renders
// nothing. So: markup for what is drawn, and real clicks for what acts.
//
// ⚠ `.dom.test.tsx` and the pragma BOTH, because half these cases PRESS a
// control and `vitest.config.ts` reserves the default `node` environment for
// the static-markup suites (DEF-523).
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EditableTable } from "./EditableTable";
import type { EditableRowGroup } from "./EditableTable";
import { CellNumber, CellSelect, CellStatic, CellText, CellTick, TableArray } from "./TableArray";

afterEach(cleanup);

interface Row {
  id: string;
  unit: string;
  service: string;
  qty: string;
}

const UNITS: Row[] = [
  { id: "a", unit: "1", service: "Water", qty: "1" },
  { id: "b", unit: "1", service: "Sewer", qty: "1" },
  { id: "c", unit: "15", service: "Broadband", qty: "1" },
];

const COLUMNS = [
  { key: "unit", label: "Unit", groupOnce: true, cell: (row: Row) => <span>{row.unit}</span> },
  { key: "service", label: "Service", cell: (row: Row) => <span>{row.service}</span> },
  { key: "qty", label: "Qty", numeric: true, cell: (row: Row) => <span>{row.qty}</span> },
];

const GROUPS: EditableRowGroup[] = [
  { key: "1", heading: "Unit 1 · Dwelling" },
  { key: "15", heading: "Unit 15 · Dwelling", summary: "4 service points" },
];

function grouped(extra: Partial<Parameters<typeof TableArray<Row>>[0]> = {}) {
  return (
    <TableArray<Row>
      title="Units and service points"
      collection="units"
      columns={COLUMNS}
      rows={UNITS}
      rowKey={(row) => row.id}
      emptyText="No service points yet."
      groups={GROUPS}
      groupOf={(row) => row.unit}
      onChange={vi.fn()}
      removeLabel="Remove"
      {...(extra as Record<string, unknown>)}
    />
  );
}

describe("TableArray — the frame the drawings put round the table", () => {
  it("draws the panel heading, the collection handle and the rows", () => {
    const html = renderToStaticMarkup(grouped());
    expect(html).toContain('data-array="units"');
    expect(html).toContain("Units and service points");
    expect(html).toContain('data-editable-table="units"');
    expect(html).toContain('data-editable-row="1"');
    expect(html).toContain('data-editable-row="3"');
  });

  it("puts every footer action on the row, left to right as drawn", () => {
    const html = renderToStaticMarkup(
      grouped({
        actions: [
          { key: "add-row", label: "+ Add row", onClick: vi.fn() },
          { key: "add-work-order", label: "+ Add work order", onClick: vi.fn() },
        ],
      }),
    );
    expect(html).toContain('data-array-action="add-row"');
    expect(html).toContain('data-array-action="add-work-order"');
    expect(html.indexOf("+ Add row")).toBeLessThan(html.indexOf("+ Add work order"));
  });

  it("BR-SHL-025 — a blocked action is DISABLED and carries its reason, never hidden", () => {
    render(
      grouped({
        actions: [
          {
            key: "add-row",
            label: "+ Add row",
            onClick: vi.fn(),
            blockedReason: "Every service is a row",
          },
        ],
      }),
    );
    const button = screen.getByRole("button", { name: "+ Add row" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("title", "Every service is a row");
  });

  // ⚠ **NO CASE HERE FOR THE FOOTER'S RIGHT-HAND BLOCK, AND THE ABSENCE IS
  // THE POINT.** `step4-charges.png` draws `Total · Paid now · Remaining`
  // beside `+ Add charge`, and `footerTrailing` was written and then REMOVED
  // before this landed: G13 refuses a prop that guards rendering and has no
  // non-test caller, and the repo's pattern is that a kit prop lands with its
  // first caller. **G13 is the check that fires if it comes back unwired** —
  // writing a second, weaker source-grep beside it would be two mechanisms for
  // one rule. Until the step-4 lane adds it, `children` does the job:

  it("children put a block under the table, inside the same panel", () => {
    const html = renderToStaticMarkup(
      grouped({
        actions: [{ key: "add-charge", label: "+ Add charge", onClick: vi.fn() }],
        children: <p data-totals="">Total $1,035.00</p>,
      }),
    );
    expect(html).toContain('data-totals=""');
    expect(html).toContain("Total $1,035.00");
  });

  it("the note under the table renders, and so does the fact beside the heading", () => {
    const html = renderToStaticMarkup(
      grouped({ note: "An extra order becomes a row.", fact: "3 service points" }),
    );
    expect(html).toContain('data-array-hint="units"');
    expect(html).toContain("An extra order becomes a row.");
    expect(html).toContain('data-array-note="units"');
    expect(html).toContain("3 service points");
  });

  it("read-only draws no remove control and no footer at all", () => {
    const html = renderToStaticMarkup(
      <TableArray<Row>
        readOnly
        title="Charges"
        collection="charges"
        columns={COLUMNS}
        rows={UNITS}
        rowKey={(row) => row.id}
        emptyText="Nothing charged."
      />,
    );
    expect(html).not.toContain("data-remove-row");
    expect(html).not.toContain("data-array-action");
  });

  it("B14 rule 17 — an empty collection says what is missing", () => {
    const html = renderToStaticMarkup(
      grouped({ rows: [], actions: [{ key: "add-row", label: "+ Add row", onClick: vi.fn() }] }),
    );
    expect(html).toContain("No service points yet.");
  });
});

describe("TableArray — grouped rows", () => {
  it("draws a heading row per group, in the order the groups are given", () => {
    const html = renderToStaticMarkup(grouped());
    expect(html).toContain('data-editable-group="1"');
    expect(html).toContain('data-editable-group="15"');
    expect(html.indexOf("Unit 1 · Dwelling")).toBeLessThan(html.indexOf("Unit 15 · Dwelling"));
  });

  it("the group's own column is drawn ONCE, on the group's first row", () => {
    // The drawing's instruction, verbatim: "the unit is named once at the head
    // of its group". Group "1" holds two rows; the second must not repeat it.
    const html = renderToStaticMarkup(grouped());
    expect(html).toContain('data-group-once=""');
    // Two rows in group 1, one silenced; group 15's single row is its own
    // first, so exactly ONE cell is silenced across the table.
    expect(html.match(/data-group-once=""/g)).toHaveLength(1);
  });

  it("a folded group draws its heading and NOT its rows", () => {
    const html = renderToStaticMarkup(
      grouped({
        groups: [
          { key: "1", heading: "Unit 1 · Dwelling" },
          {
            key: "15",
            heading: "Unit 15 · Dwelling",
            summary: "4 service points",
            collapsed: true,
            onToggle: vi.fn(),
          },
        ],
      }),
    );
    expect(html).toContain("Unit 15 · Dwelling");
    expect(html).toContain("4 service points");
    expect(html).not.toContain("Broadband");
    // Group 1's two rows are still there.
    expect(html).toContain("Water");
  });

  it("the folded heading is a real control — it announces its state and it fires", () => {
    const onToggle = vi.fn();
    render(
      grouped({
        groups: [
          { key: "1", heading: "Unit 1 · Dwelling" },
          { key: "15", heading: "Unit 15", collapsed: true, onToggle },
        ],
      }),
    );
    const toggle = screen.getByRole("button", { name: /Unit 15/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("a group with no toggle is NOT a button — nothing pretends to be pressable", () => {
    // Hard-won law 2's other face: a live control that means nothing.
    render(grouped());
    expect(screen.queryByRole("button", { name: /Unit 1 · Dwelling/ })).toBeNull();
    expect(screen.getByText("Unit 1 · Dwelling")).toBeInTheDocument();
  });

  it("a row no group claims is still DRAWN, and it is marked", () => {
    // An absence is invisible to every check this repo has (DEF-CUS-3653), so
    // the row is kept and the caller's bug is made visible instead.
    const html = renderToStaticMarkup(
      grouped({ groups: [{ key: "1", heading: "Unit 1 · Dwelling" }] }),
    );
    expect(html).toContain("Broadband");
    expect(html).toContain('data-editable-ungrouped=""');
  });

  it("reordering is OFF inside a grouped table", () => {
    // ↑ on the first row of group two would carry it into group one.
    const html = renderToStaticMarkup(grouped());
    expect(html).not.toContain('data-move="up"');
  });

  it("the heading row spans every column the header row has", () => {
    // ⚠ READ THE DOM, NOT THE MARKUP STRING. React spells this attribute
    // `colSpan` in the server string and `colspan` in the document, and HTML
    // attribute names are case-insensitive — so a `toContain` here would be a
    // check that passes or fails on a renderer's spelling rather than on
    // whether the heading reaches the last column.
    const { container } = render(grouped());
    const headers = container.querySelectorAll("thead th").length;
    const heading = container.querySelector("[data-editable-group='1'] th");
    expect(headers).toBe(4);
    expect(heading?.getAttribute("colspan")).toBe(String(headers));
  });
});

describe("TableArray — the two error slots", () => {
  it("a row refusal is a band under its row, and it is announced", () => {
    render(grouped({ rowError: (row: Row) => (row.id === "c" ? "Sewer follows water." : undefined) }));
    const band = screen.getByRole("alert");
    expect(band).toHaveTextContent("Sewer follows water.");
    expect(band).toHaveAttribute("data-row-error", "3");
  });

  it("a group refusal is a band under its heading", () => {
    render(
      grouped({
        groups: [
          { key: "1", heading: "Unit 1 · Dwelling" },
          {
            key: "15",
            heading: "Unit 15 · Dwelling",
            error: "Unit 15 takes Broadband. This address does not.",
          },
        ],
      }),
    );
    const band = screen.getByRole("alert");
    expect(band).toHaveTextContent("Unit 15 takes Broadband. This address does not.");
    expect(band).toHaveAttribute("data-group-error", "15");
  });

  it("a cell refusal sits under that cell's control and names its column", () => {
    const html = renderToStaticMarkup(
      grouped({
        cellError: (_row: Row, index: number, key: string) =>
          index === 0 && key === "unit" ? "already exists here" : undefined,
      }),
    );
    expect(html).toContain('data-cell-error="unit"');
    expect(html).toContain("already exists here");
  });

  it("a silenced group-once cell carries no cell error — the box it names is not there", () => {
    const html = renderToStaticMarkup(
      grouped({ cellError: (_row: Row, _index: number, key: string) => (key === "unit" ? "x" : undefined) }),
    );
    // Row 1 of group 1 draws the unit cell and its error; row 2 draws neither.
    expect(html.match(/data-cell-error="unit"/g)).toHaveLength(2);
  });

  it("no groups, no errors — the flat table is untouched", () => {
    const html = renderToStaticMarkup(
      <EditableTable<Row>
        data-collection="flat"
        caption="Tasks"
        rows={UNITS}
        rowKey={(row) => row.id}
        onChange={vi.fn()}
        emptyText="None."
        labels={{ moveUp: "Up", moveDown: "Down", remove: "Remove", position: "row" }}
        columns={COLUMNS}
      />,
    );
    expect(html).not.toContain("data-editable-group");
    expect(html).not.toContain("data-cell-error");
    expect(html).not.toContain("data-group-once");
    // The ungrouped table keeps its reordering and its numbers.
    expect(html).toContain('data-move="up"');
  });
});

describe("TableArray — the numeric column", () => {
  it("a numeric column is right-aligned and on tabular numerals, header and body", () => {
    const html = renderToStaticMarkup(grouped());
    expect(html).toContain("text-right align-top tabular-nums");
    // The header tier is the kit's one table type (`DEF-SHL-5771`), right-aligned here.
    expect(html).toContain("py-2 text-right font-heading text-table-header font-semibold uppercase tracking-table-header");
  });
});

describe("the cell controls", () => {
  it("a cell dropdown is named, offers its empty option first, and hands back the value", () => {
    const onChange = vi.fn();
    render(
      <CellSelect
        label="Service"
        name="service"
        value=""
        onChange={onChange}
        placeholder="Choose a service"
        options={[
          { value: "water", label: "Water" },
          { value: "sewer", label: "Sewer" },
        ]}
      />,
    );
    const select = screen.getByRole("combobox", { name: "Service" });
    expect(select).toHaveValue("");
    expect(screen.getByRole("option", { name: "Choose a service" })).toBeInTheDocument();
    fireEvent.change(select, { target: { value: "sewer" } });
    expect(onChange).toHaveBeenCalledWith("sewer");
  });

  it("B14 rule 31 — the option's VALUE is never the visible text", () => {
    const html = renderToStaticMarkup(
      <CellSelect
        label="Asset"
        name="asset"
        value=""
        onChange={vi.fn()}
        placeholder="Choose"
        options={[{ value: "3f0c5a10-0000-4000-8000-000000000000", label: "Meter" }]}
      />,
    );
    expect(html).toContain(">Meter<");
    expect(html).not.toContain(">3f0c5a10-0000-4000-8000-000000000000<");
  });

  it("BR-SHL-025 — a blocked cell is disabled AND says why", () => {
    render(
      <CellSelect
        label="Size"
        name="size"
        value=""
        onChange={vi.fn()}
        placeholder="—"
        options={[]}
        blockedReason="Choose a service first"
      />,
    );
    const select = screen.getByRole("combobox", { name: "Size" });
    expect(select).toBeDisabled();
    expect(select).toHaveAttribute("title", "Choose a service first");
  });

  it("a counted cell is right-aligned on tabular numerals and hands back a STRING", () => {
    const onChange = vi.fn();
    render(<CellNumber label="Qty" name="qty" value="1" min={1} onChange={onChange} />);
    const input = screen.getByRole("spinbutton", { name: "Qty" });
    expect(input).toHaveClass("input-num");
    fireEvent.change(input, { target: { value: "2" } });
    expect(onChange).toHaveBeenCalledWith("2");
    // Hard rule 2 — no parsing, no arithmetic: a string in, a string out.
    expect(onChange).not.toHaveBeenCalledWith(2);
  });

  it("a typed cell and a tick box are both named and both act", () => {
    const typed = vi.fn();
    const ticked = vi.fn();
    render(
      <>
        <CellText label="Unit" name="unit" value="1" onChange={typed} />
        <CellTick label="Completes" name="completes" checked={false} onChange={ticked} />
      </>,
    );
    fireEvent.change(screen.getByRole("textbox", { name: "Unit" }), { target: { value: "2" } });
    expect(typed).toHaveBeenCalledWith("2");
    fireEvent.click(screen.getByRole("checkbox", { name: "Completes" }));
    expect(ticked).toHaveBeenCalledWith(true);
  });

  it("a fact cell is NOT a disabled input — the PO ruled that out", () => {
    // "we dont display it like this at other places we will ahve to follow UI
    // rules". A fact is text, not a box a clerk might try to type in.
    const html = renderToStaticMarkup(<CellStatic name="amount">$135.00</CellStatic>);
    expect(html).toContain("$135.00");
    expect(html).not.toContain("<input");
    expect(html).not.toContain("disabled");
  });
});
