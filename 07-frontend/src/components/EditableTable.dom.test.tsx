// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-014 (a bundle is ROWS and `seq` is what the phone shows) ·
//           US-WRK-016 (the builder's steps 2 to 6). Screens: Work-015,
//           Work-016
// Rules:    BR-WRK-009 · B14 rule 20 (one table type) · rule 15 (icons for row
//           actions) · rule 21 · A12 (a wide table scrolls inside its own box)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE REORDERING IS THE POINT, AND IT IS WHY THE BUTTONS EXIST.** HTML5
// drag-and-drop cannot be driven by `@testing-library`, by a keyboard or by a
// screen reader, so a component whose only reordering path is a pointer gesture
// is one whose reordering CANNOT be tested — the shape hard-won law 2 keeps
// finding. Every case below drives the real controls.
//
// ⚠ `.dom.test.tsx` and `@vitest-environment jsdom` BOTH, because half these
// cases PRESS a button and the project's default environment has no document.
// The naming convention is the repo's own (`ImportWorkflowPage.dom.test.tsx`).
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EditableTable } from "./EditableTable";

// Without this each `render` leaves its markup in the document and the NEXT
// `getByLabelText` finds three *Remove — row 1* controls. The repo's other
// DOM suites do the same (`DataTable.dom.test.tsx`).
afterEach(cleanup);

const LABELS = { moveUp: "Move up", moveDown: "Move down", remove: "Remove", position: "row" };

interface Row {
  title: string;
}

function table(rows: Row[], onChange = vi.fn()) {
  return (
    <EditableTable<Row>
      data-collection="tasks"
      caption="Tasks — 3 steps"
      rows={rows}
      rowKey={(row) => row.title}
      onChange={onChange}
      emptyText="No steps yet."
      labels={LABELS}
      columns={[{ key: "title", label: "Task", cell: (row) => <span>{row.title}</span> }]}
      addRow={<button type="button">+ Add</button>}
    />
  );
}

const THREE: Row[] = [{ title: "First" }, { title: "Second" }, { title: "Third" }];

describe("EditableTable", () => {
  it("numbers the rows from 1 and draws the caption", () => {
    const html = renderToStaticMarkup(table(THREE));
    expect(html).toContain('data-editable-table="tasks"');
    expect(html).toContain("Tasks — 3 steps");
    expect(html).toContain('data-editable-row="1"');
    expect(html).toContain('data-editable-row="3"');
  });

  it("B14 rule 17 — an empty collection says so, and the add row is still there", () => {
    const html = renderToStaticMarkup(table([]));
    expect(html).toContain("No steps yet.");
    expect(html).toContain("+ Add");
    expect(html).not.toContain("data-editable-row");
  });

  it("moving a row up hands back the WHOLE list, in its new order", () => {
    const onChange = vi.fn();
    render(table(THREE, onChange));
    fireEvent.click(screen.getByLabelText("Move up — row 2"));
    // The order IS the data (`wot_tasks.seq`), so the consumer is handed the
    // list rather than a "moved from 2 to 1" event: `PUT …/{collection}` is
    // replace-in-full and a partial move would leave two rows claiming seq 2.
    expect(onChange).toHaveBeenCalledWith([{ title: "Second" }, { title: "First" }, { title: "Third" }]);
  });

  it("moving a row down does the mirror of it", () => {
    const onChange = vi.fn();
    render(table(THREE, onChange));
    fireEvent.click(screen.getByLabelText("Move down — row 1"));
    expect(onChange).toHaveBeenCalledWith([{ title: "Second" }, { title: "First" }, { title: "Third" }]);
  });

  it("the first row cannot move up and the last cannot move down", () => {
    render(table(THREE));
    // `jest-dom`'s matchers are not installed here, so the DOM property is read
    // directly — which is the thing a browser acts on anyway.
    expect((screen.getByLabelText("Move up — row 1") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByLabelText("Move down — row 3") as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByLabelText("Move up — row 2") as HTMLButtonElement).disabled).toBe(false);
  });

  it("removing a row hands back the list without it", () => {
    const onChange = vi.fn();
    render(table(THREE, onChange));
    fireEvent.click(screen.getByLabelText("Remove — row 2"));
    expect(onChange).toHaveBeenCalledWith([{ title: "First" }, { title: "Third" }]);
  });

  it("every row control has an accessible name that says WHICH row", () => {
    // A screen of three identical ✕ glyphs is three controls a screen reader
    // cannot tell apart, which is the same failure as a button with no label.
    render(table(THREE));
    for (const n of [1, 2, 3]) {
      expect(screen.getByLabelText(`Remove — row ${n}`)).toBeTruthy();
    }
  });

  it("the drag handle is hidden from the accessibility tree", () => {
    // It is decorative: the two buttons at the end of the row are the real
    // controls, so announcing a handle that does nothing would be worse than
    // silence.
    const html = renderToStaticMarkup(table(THREE));
    expect(html).toContain('aria-hidden="true"');
  });

  it("A12 — a wide table scrolls inside its own box, not across the page", () => {
    const html = renderToStaticMarkup(table(THREE));
    expect(html).toContain("overflow-x-auto");
  });

  // ── `reorderable={false}` · DEF-RAT-5731 ─────────────────────────────────
  //
  // ⚠ **THE FIRST CASE IS THE CONTROL AND IT COMES FIRST ON PURPOSE.** Every
  // assertion below is an ABSENCE, and a component that rendered nothing at all
  // would satisfy all of them. So prove the table still draws its rows before
  // proving it draws no ordering controls.
  describe("reorderable={false} — a collection with no order", () => {
    const unordered = (
      <EditableTable<Row>
        data-collection="charges"
        caption="c"
        rows={THREE}
        rowKey={(row) => row.title}
        onChange={vi.fn()}
        emptyText="e"
        reorderable={false}
        labels={{ remove: "Remove" }}
        columns={[{ key: "t", label: "Task", cell: (row) => <span>{row.title}</span> }]}
      />
    );

    it("still draws every row — the CONTROL for the absences below", () => {
      const html = renderToStaticMarkup(unordered);
      for (const row of THREE) expect(html).toContain(row.title);
      expect(html).toContain('data-editable-row="3"');
    });

    it("draws no drag handle and makes no row draggable", () => {
      const html = renderToStaticMarkup(unordered);
      expect(html).not.toContain("draggable");
      expect(html).not.toContain("cursor-grab");
      expect(html).not.toContain("≡");
    });

    it("draws neither move button", () => {
      const html = renderToStaticMarkup(unordered);
      expect(html).not.toContain('data-move="up"');
      expect(html).not.toContain('data-move="down"');
    });

    it("keeps REMOVE, which is not an ordering control", () => {
      const html = renderToStaticMarkup(unordered);
      expect(html).toContain('data-remove-row="1"');
      // …and names the row it acts on without an ordering label to borrow.
      expect(html).toContain("Remove — 1");
      expect(html).not.toContain("undefined");
    });

    it("still reorders when the prop is absent — the five existing callers", () => {
      const html = renderToStaticMarkup(table(THREE));
      expect(html).toContain('data-move="up"');
      expect(html).toContain("draggable");
    });
  });

  // ── `rowRemoveBlocked` · DEF-RAT-5731, the plan wizard's discounts step ───
  //
  // ⚠ **A REMOVE CAN BE REFUSED BY A RULE, AND THE ROW MUST SAY SO.** Written
  // for a plan's discount while `OQ-322` was open (CLOSED 2026-10-03 — an
  // unbind now ends its enrolments); the prop stays for any rule that refuses
  // a remove (`ChargeCodeWizard`'s one row). The two-pane screen this table replaces
  // already disabled its unbind and named the count; the prop is what carries
  // that guarantee across the rewrite instead of losing it.
  describe("rowRemoveBlocked — a row whose × a rule refuses", () => {
    // ⚠ THE TITLES ARE `THREE`'s OWN. A predicate naming a row this fixture
    // does not hold matches NOTHING, and then every case below passes for the
    // wrong reason — the red proof caught exactly that on the first run.
    const BLOCKED = (row: Row) => (row.title === "Second" ? "72 enrolled" : undefined);

    function guarded(onChange = vi.fn()) {
      return (
        <EditableTable<Row>
          data-collection="tasks"
          caption="c"
          rows={THREE}
          rowKey={(row) => row.title}
          onChange={onChange}
          emptyText="e"
          labels={LABELS}
          rowRemoveBlocked={BLOCKED}
          columns={[{ key: "t", label: "Title", cell: (row) => <span>{row.title}</span> }]}
        />
      );
    }

    // ⚠ THE CONTROL CASE. If this fails, nothing below is measuring the table.
    it("CONTROL: the fixture renders three rows, each with its own ×", () => {
      const html = renderToStaticMarkup(guarded());
      expect(html).toContain('data-remove-row="1"');
      expect(html).toContain('data-remove-row="2"');
      expect(html).toContain('data-remove-row="3"');
      expect(html).not.toContain("a string this table never renders");
    });

    it("the refused row's × is DISABLED and carries its reason", () => {
      render(guarded());
      const blocked = document.querySelector('[data-remove-row="2"]') as HTMLButtonElement;
      expect(blocked.disabled).toBe(true);
      expect(blocked.getAttribute("title")).toBe("72 enrolled");
      expect(blocked.hasAttribute("data-remove-blocked")).toBe(true);
    });

    it("every OTHER row stays removable, and carries no stray title", () => {
      render(guarded());
      for (const at of ["1", "3"]) {
        const free = document.querySelector(`[data-remove-row="${at}"]`) as HTMLButtonElement;
        expect(free.disabled).toBe(false);
        expect(free.getAttribute("title")).toBeNull();
        expect(free.hasAttribute("data-remove-blocked")).toBe(false);
      }
    });

    it("pressing a free row's × still removes exactly that row", () => {
      const onChange = vi.fn();
      render(guarded(onChange));
      fireEvent.click(document.querySelector('[data-remove-row="1"]') as HTMLElement);
      expect(onChange).toHaveBeenCalledTimes(1);
      expect(onChange.mock.calls[0][0].map((row: Row) => row.title)).toEqual([
        "Second",
        "Third",
      ]);
    });

    it("pressing the REFUSED row's × removes nothing — the rule holds", () => {
      const onChange = vi.fn();
      render(guarded(onChange));
      fireEvent.click(document.querySelector('[data-remove-row="2"]') as HTMLElement);
      expect(onChange).not.toHaveBeenCalled();
    });

    // The whole point of an opt-in: the six collections that predate it.
    it("ABSENT means every row is removable, exactly as before", () => {
      const onChange = vi.fn();
      render(table(THREE, onChange));
      const free = document.querySelector('[data-remove-row="2"]') as HTMLButtonElement;
      expect(free.disabled).toBe(false);
      expect(free.hasAttribute("data-remove-blocked")).toBe(false);
      fireEvent.click(free);
      expect(onChange).toHaveBeenCalledTimes(1);
    });
  });

  it("a numeric column is right-aligned and on tabular numerals", () => {
    const html = renderToStaticMarkup(
      <EditableTable<Row>
        data-collection="tasks"
        caption="c"
        rows={THREE}
        rowKey={(row) => row.title}
        onChange={vi.fn()}
        emptyText="e"
        labels={LABELS}
        columns={[{ key: "m", label: "Minutes", numeric: true, cell: () => <span>3</span> }]}
      />,
    );
    expect(html).toContain("text-right");
    expect(html).toContain("tabular-nums");
  });
});

// ── WHERE THE ADD ROW SITS (PO ruling 2026-09-18) ─────────────────────────
//
// ⚠ **THESE ASSERT DOM ORDER, NOT A CLASS OR AN ATTRIBUTE.** The requirement is
// that a clerk meets the control BEFORE the list on the plan wizard's three
// binding steps, and only document order expresses that. A test reading
// `data-editable-addrow` would pass over a block that carries the right marker
// and renders in the wrong place — the "looking at the wrong thing" shape.
//
// The default case is the load-bearing one: the work template builder passes
// `addRow` five times and asked for none of this. If `below` ever stops being
// the default, that screen rearranges and this goes red first.
describe("the add row's position", () => {
  const withAddRow = (position?: "above" | "below") =>
    render(
      <EditableTable<{ id: string }>
        caption="POSITION"
        columns={[{ key: "id", label: "Id", cell: (r) => r.id }]}
        rows={[{ id: "one" }]}
        rowKey={(r) => r.id}
        onChange={() => {}}
        emptyText="nothing yet"
        addRow={<button type="button">+ Add</button>}
        labels={{ remove: "Remove", moveUp: "Up", moveDown: "Down" }}
        data-collection="position"
        {...(position ? { addRowPosition: position } : {})}
      />,
    );

  const addRowIsBeforeTable = (container: HTMLElement) => {
    const add = container.querySelector("[data-editable-addrow]");
    const table = container.querySelector("table");
    expect(add, "the add row should render").not.toBeNull();
    expect(table, "the table should render").not.toBeNull();
    // Node.DOCUMENT_POSITION_FOLLOWING === 4 — `table` comes AFTER `add`.
    return Boolean(add!.compareDocumentPosition(table!) & 4);
  };

  it("sits BELOW the table by default, so nothing that exists moves", () => {
    const { container } = withAddRow();
    expect(addRowIsBeforeTable(container)).toBe(false);
    expect(container.querySelector("[data-editable-addrow]")!.getAttribute("data-editable-addrow"))
      .toBe("below");
  });

  it("sits ABOVE the table when a screen asks for it", () => {
    const { container } = withAddRow("above");
    expect(addRowIsBeforeTable(container)).toBe(true);
  });

  it("still sits BELOW when a screen asks for that explicitly", () => {
    const { container } = withAddRow("below");
    expect(addRowIsBeforeTable(container)).toBe(false);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 2026-09-23 · FOUR OPT-INS FOR THE SERVICE-REQUEST FEE LINES (B14 rules 36/43)
// ══════════════════════════════════════════════════════════════════════════
// The kit gained `readOnly`, `numbered`, `footerCells` and `onRemove` so ONE
// fee table reads the same on four screens. Each is opt-in, and the first case
// is the one that matters most: absent, nothing an existing collection renders
// has moved.
describe("EditableTable — the fee lines' opt-ins", () => {
  it("absent, the six collections that predate them render exactly as before", () => {
    const html = renderToStaticMarkup(table(THREE));
    expect(html).toContain(">#</th>");
    expect(html).not.toContain("data-editable-footer");
    expect(html).toContain('data-remove-row="1"');
  });

  it("readOnly draws the rows and NO controls — no remove, no reorder, no add row", () => {
    const html = renderToStaticMarkup(
      <EditableTable<Row>
        data-collection="fees"
        caption="Fees"
        rows={THREE}
        rowKey={(row) => row.title}
        emptyText="None."
        readOnly
        columns={[{ key: "title", label: "Fee", cell: (row) => <span>{row.title}</span> }]}
        addRow={<button type="button">+ Add</button>}
      />,
    );
    expect(html).toContain("Second");
    expect(html).not.toContain("data-remove-row");
    expect(html).not.toContain("data-move");
    expect(html).not.toContain("+ Add");
    expect(html).not.toContain("≡");
  });

  it("numbered={false} drops the # column and nothing else", () => {
    const html = renderToStaticMarkup(
      <EditableTable<Row>
        data-collection="fees"
        caption="Fees"
        rows={THREE}
        rowKey={(row) => row.title}
        onChange={vi.fn()}
        emptyText="None."
        numbered={false}
        reorderable={false}
        labels={{ remove: "Remove" }}
        columns={[{ key: "title", label: "Fee", cell: (row) => <span>{row.title}</span> }]}
      />,
    );
    expect(html).not.toContain(">#</th>");
    expect(html).toContain('data-remove-row="3"');
  });

  it("footerCells draws a footer lined up by column key — and adds NOTHING up itself", () => {
    const html = renderToStaticMarkup(
      <EditableTable<{ fee: string; amount: string }>
        data-collection="fees"
        caption="Fees"
        rows={[
          { fee: "A", amount: "25.0000" },
          { fee: "B", amount: "60.0000" },
        ]}
        rowKey={(row) => row.fee}
        emptyText="None."
        readOnly
        numbered={false}
        columns={[
          { key: "fee", label: "Fee", cell: (row) => row.fee },
          { key: "amount", label: "Amount", numeric: true, cell: (row) => row.amount },
        ]}
        footerCells={{ fee: "Total", amount: "SERVER-SAID-85.00" }}
      />,
    );
    expect(html).toContain("data-editable-footer");
    // The footer prints what it was HANDED. A kit that summed its own cells
    // would be money arithmetic in a browser (hard rule 2).
    expect(html).toContain("SERVER-SAID-85.00");
    expect(html).not.toContain("85.0000");
  });

  it("an empty caption draws no caption bar — the panel's heading already names the table", () => {
    const html = renderToStaticMarkup(
      <EditableTable<Row>
        data-collection="fees"
        caption=""
        rows={THREE}
        rowKey={(row) => row.title}
        emptyText="None."
        readOnly
        columns={[{ key: "title", label: "Fee", cell: (row) => <span>{row.title}</span> }]}
      />,
    );
    expect(html).not.toContain("tracking-tag uppercase\"></div>");
    expect(html).not.toMatch(/<div class="border-b border-divider px-3 py-2 font-mono/);
  });

  it("onRemove is called WITH THE ROW instead of onChange — the server owns the rows", () => {
    const onChange = vi.fn();
    const onRemove = vi.fn();
    render(
      <EditableTable<Row>
        data-collection="fees"
        caption="Fees"
        rows={THREE}
        rowKey={(row) => row.title}
        onChange={onChange}
        onRemove={onRemove}
        emptyText="None."
        reorderable={false}
        labels={{ remove: "Remove", position: "row" }}
        columns={[{ key: "title", label: "Fee", cell: (row) => <span>{row.title}</span> }]}
      />,
    );
    fireEvent.click(screen.getByLabelText("Remove — row 2"));
    expect(onRemove).toHaveBeenCalledWith({ title: "Second" }, 1);
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("DEF-SHL-5771 — ONE table type: the header tier is the kit's, not monospace", () => {
  // B14 rule 20 allows one table type. `DataTable.css` sets the header tier —
  // the heading face, the 12px header token, semibold, uppercase, 0.08em —
  // and EditableTable (every TableArray in the product) drew its caption and
  // every header in `font-mono … tracking-tag` instead.
  it("every column header and the caption carry the header tier and no font-mono", () => {
    render(table(THREE));
    const heads = [...document.querySelectorAll("thead th")].filter((th) => th.textContent !== "");
    expect(heads.map((th) => th.textContent)).toEqual(["#", "Task"]);
    const caption = screen.getByText("Tasks — 3 steps");
    for (const el of [...heads, caption]) {
      const classes = el.className.split(" ");
      expect(classes).not.toContain("font-mono");
      expect(classes).not.toContain("tracking-tag");
      for (const tier of ["font-heading", "text-table-header", "font-semibold", "uppercase", "tracking-table-header"]) {
        expect(classes).toContain(tier);
      }
    }
  });
});
