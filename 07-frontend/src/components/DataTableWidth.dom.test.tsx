// @vitest-environment jsdom
// DEF-SHL-5378 · DEF-RAT-8842 — a list never overflows its column, the
// row-action icons are never the part cut off, and the toolbar's drop-down
// panels are never inside the box that scrolls.
//
// ⚠ jsdom performs NO layout, so the widths are planted: the table reports
// 1,188px and its box 1,120px — the Rate schedules list at 1440, as measured in
// Chromium on 2026-10-01. What this suite proves is the kit's RESPONSE to a
// measured overflow. Whether a real list fits is a browser question, answered
// by `10-scripts/render-checks/table-width-fit.mjs`.
//
// RED ON THE OLD CODE, checked before it was trusted green (law 7): with the
// pre-fix DataTable.tsx and DataTable.css every case below fails — there is no
// `[data-table-scroll]` box, nothing is pinned, and the header rule still
// carries `white-space: nowrap`.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DataTable } from "./DataTable";
import { defaultRequestState } from "./tableTypes";
import type { TableConfig } from "./tableTypes";

// A `?raw` CSS import comes back EMPTY under this vitest config, so the sheet
// is read from disk — the dynamic `node:` import `PageHeader.test.tsx` uses,
// because a static one passes vitest and fails `tsc --noEmit` (DEF-2354).
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
};
// Under jsdom `import.meta.url` is not a file: URL, so the path is taken from
// the working directory vitest runs in (07-frontend).
const nodeProcess = (await import(/* @vite-ignore */ ["node", "process"].join(":"))) as {
  cwd(): string;
};
const dataTableCss = nodeFs.readFileSync(
  `${nodeProcess.cwd()}/src/components/DataTable.css`,
  "utf8",
);

vi.mock("@/api/endpoints", () => ({
  getUserPreference: () => new Promise(() => undefined),
  putUserPreference: () => Promise.resolve(),
}));

interface Row {
  id: string;
  name: string;
  status: string;
}

const ROWS: Row[] = [
  { id: "1", name: "Residential water", status: "Active" },
  { id: "2", name: "Commercial water", status: "Active" },
];

function config(order: "actions-last" | "actions-middle"): TableConfig<Row> {
  const name = { key: "name", label: "Name", identity: true, sortable: true };
  const status = { key: "status", label: "Status" };
  const actions = {
    key: "actions",
    label: "Actions",
    cell: (row: Row) => (
      <button type="button" aria-label={`Retire ${row.name}`}>
        x
      </button>
    ),
  };
  return {
    screenId: "S-WIDTH",
    columns: order === "actions-last" ? [name, status, actions] : [name, actions, status],
    getRowId: (row) => row.id,
    defaultSort: { sort: "name", dir: "asc" },
    searchFields: ["name"],
  };
}

// ── planted layout ──────────────────────────────────────────────────────────
let tableWidth = 1188;
const BOX_WIDTH = 1120;
const observers: Array<() => void> = [];

beforeEach(() => {
  observers.length = 0;
  vi.stubGlobal(
    "ResizeObserver",
    class {
      private readonly cb: () => void;
      constructor(cb: () => void) {
        this.cb = cb;
        observers.push(cb);
      }
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (
    this: HTMLElement,
  ) {
    const width = this.tagName === "TABLE" ? tableWidth : BOX_WIDTH;
    return { width, height: 0, top: 0, left: 0, right: width, bottom: 0, x: 0, y: 0, toJSON() {} };
  });
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockImplementation(() => BOX_WIDTH);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  tableWidth = 1188;
});

function renderTable(order: "actions-last" | "actions-middle" = "actions-last", filter = true) {
  const cfg = config(order);
  return render(
    <DataTable<Row>
      config={cfg}
      state={defaultRequestState(cfg)}
      onStateChange={() => undefined}
      rows={ROWS}
      totalRows={ROWS.length}
      loading={false}
      visibleColumns={cfg.columns.map((c) => c.key)}
      filterBarSlot={filter ? <div data-testid="filter-panel">+ Filter</div> : undefined}
      empty={{ title: "t", helper: "h" }}
    />,
  );
}

function scrollBox(container: HTMLElement): HTMLElement {
  const box = container.querySelector<HTMLElement>("[data-table-scroll]");
  expect(box, "the table has its own box to scroll in").not.toBeNull();
  return box as HTMLElement;
}

describe("DEF-SHL-5378 — the shared table fits its column", () => {
  it("a table wider than its column scrolls inside its OWN box, never the page", () => {
    const { container } = renderTable();
    const box = scrollBox(container);
    expect(box.querySelector("table.data-table")).not.toBeNull();
    expect(box.className).toContain("overflow-x-auto");
  });

  it("the + Filter panel and the toolbar are NOT inside the box that scrolls (it would clip them)", () => {
    const { container, getByTestId } = renderTable();
    const box = scrollBox(container);
    expect(box.contains(getByTestId("filter-panel"))).toBe(false);
    expect(box.contains(container.querySelector(".table-toolbar"))).toBe(false);
  });

  it("DEF-RAT-8842: while it scrolls, the row-actions column is pinned to the right edge", () => {
    const { container } = renderTable();
    const header = [...container.querySelectorAll("thead th")].pop() as HTMLElement;
    expect(header.textContent).toBe("Actions");
    expect(header.className).toMatch(/\bsticky\b/);
    expect(header.className).toMatch(/\bright-0\b/);
    for (const row of container.querySelectorAll("tbody tr")) {
      const cell = row.lastElementChild as HTMLElement;
      expect(cell.querySelector("button")).not.toBeNull();
      expect(cell.className).toMatch(/\bsticky\b/);
      expect(cell.className).toMatch(/\bright-0\b/);
      // Opaque, or the scrolled cells show through the icons.
      expect(cell.className).toContain("!bg-bg");
      // No z-index: it would put the next row's cell over a row's … menu.
      expect(cell.className).not.toMatch(/\bz-/);
    }
  });

  it("a table that FITS keeps no clipping box and pins nothing, so a row's … menu is never cut", () => {
    tableWidth = 1120;
    const { container } = renderTable();
    const box = scrollBox(container);
    expect(box.className).not.toContain("overflow");
    for (const cell of container.querySelectorAll("th, td")) {
      expect(cell.className).not.toMatch(/\bsticky\b/);
    }
  });

  it("re-measures when the layout changes: a table that grows starts scrolling", () => {
    tableWidth = 1120;
    const { container } = renderTable();
    expect(scrollBox(container).className).not.toContain("overflow-x-auto");
    tableWidth = 1300;
    act(() => observers.forEach((cb) => cb()));
    expect(scrollBox(container).className).toContain("overflow-x-auto");
  });

  it("an actions column moved off the end (▦ reorder) is NOT pinned — it would cover its neighbour", () => {
    const { container } = renderTable("actions-middle");
    for (const cell of container.querySelectorAll("th, td")) {
      expect(cell.className).not.toMatch(/\bsticky\b/);
    }
  });

  it("the header may break between words: `.data-table th` no longer forbids wrapping", () => {
    const rule = /\.data-table th \{([^}]*)\}/.exec(dataTableCss.replace(/\/\*[\s\S]*?\*\//g, ""));
    expect(rule, "the .data-table th rule exists").not.toBeNull();
    expect((rule as RegExpExecArray)[1]).not.toMatch(/white-space:\s*nowrap/);
  });
});
