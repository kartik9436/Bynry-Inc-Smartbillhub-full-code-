// @vitest-environment jsdom
// DEF-SHL-5378 — a row's `…` menu inside a table that scrolls sideways.
//
// `overflow-x: auto` clips the y axis as well, so once the shared table got a
// scroll box the last row's menu was cut: measured on Units at 1280, one item
// of four showed. The menu now opens UPWARD when that box would cut it, and
// only then. jsdom performs no layout, so the rectangles are planted.
//
// RED ON THE OLD CODE: before the fix the panel carried no `data-opens` at all
// and was always anchored `top-[…]`, so the first case fails.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { act, cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RowActionsMore, RowMenuAction } from "./RowActions";

type Rect = { top: number; bottom: number; height: number };
const rects = new Map<string, Rect>();

beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (
    this: HTMLElement,
  ) {
    const key =
      this.dataset.tableScroll !== undefined
        ? "box"
        : this.dataset.rowMore !== undefined
          ? "details"
          : this.parentElement?.dataset.rowMore !== undefined && this.tagName === "DIV"
            ? "panel"
            : "other";
    const r = rects.get(key) ?? { top: 0, bottom: 0, height: 0 };
    return { ...r, left: 0, right: 0, width: 0, x: 0, y: r.top, toJSON() {} } as DOMRect;
  });
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockImplementation(function (
    this: HTMLElement,
  ) {
    return this.dataset.tableScroll !== undefined ? 500 : 0;
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  rects.clear();
});

function renderMenu(scrolling: boolean) {
  return render(
    <div data-table-scroll="" style={scrolling ? { overflowX: "auto" } : undefined}>
      <RowActionsMore label="More actions">
        <RowMenuAction label="Assign plan" icon={<span />} onClick={() => undefined} />
        <RowMenuAction label="Move out" icon={<span />} onClick={() => undefined} />
      </RowActionsMore>
    </div>,
  );
}

function open(container: HTMLElement): HTMLElement {
  const details = container.querySelector("details") as HTMLDetailsElement;
  act(() => {
    details.open = true;
    fireEvent(details, new Event("toggle"));
  });
  return details.querySelector(":scope > div") as HTMLElement;
}

describe("DEF-SHL-5378 — the … menu is never cut by the table's scroll box", () => {
  it("on the last row of a scrolling table it opens UPWARD", () => {
    rects.set("box", { top: 0, bottom: 500, height: 500 });
    rects.set("details", { top: 450, bottom: 482, height: 32 });
    rects.set("panel", { top: 486, bottom: 630, height: 144 });
    const panel = open(renderMenu(true).container);
    expect(panel.dataset.opens).toBe("up");
    expect(panel.className).toContain("bottom-[calc(100%+var(--space-1))]");
    expect(panel.className).not.toContain("top-[calc(100%+var(--space-1))]");
  });

  it("where it fits below, it opens DOWN as it always did", () => {
    rects.set("box", { top: 0, bottom: 500, height: 500 });
    rects.set("details", { top: 40, bottom: 72, height: 32 });
    rects.set("panel", { top: 76, bottom: 220, height: 144 });
    const panel = open(renderMenu(true).container);
    expect(panel.dataset.opens).toBeUndefined();
    expect(panel.className).toContain("top-[calc(100%+var(--space-1))]");
  });

  it("outside a scrolling table nothing changes, even near the bottom", () => {
    rects.set("box", { top: 0, bottom: 500, height: 500 });
    rects.set("details", { top: 450, bottom: 482, height: 32 });
    rects.set("panel", { top: 486, bottom: 630, height: 144 });
    const panel = open(renderMenu(false).container);
    expect(panel.dataset.opens).toBeUndefined();
  });
});
