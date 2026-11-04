// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-1085 — the column picker opens off the LEFT edge of the
//           viewport once the toolbar wraps and the ▦ lands near the margin.
// Rules:    B14 rule 14 (▦ opens show/hide with reorder and Reset) ·
//           hard-won law 2 ("built is not wired") · hard-won law 6
// ───────────────────────────────────────────────────────
// ⚠ **THIS SUITE CHECKS THE WIRING, AND ONLY THE WIRING.**
//
// `popoverAnchor.test.ts` owns whether the arithmetic is RIGHT — exhaustively,
// in both directions, with no DOM at all. What it cannot answer is whether
// `DataTable` ever CALLS it, or whether it throws the answer away: an optional
// decision nothing consumes is dead code that renders nothing and passes every
// test (hard-won law 2, four defects in one day, G13's whole reason).
//
// So this file measures the one thing jsdom can honestly measure: given a
// STUBBED rect, does the rendered panel carry the class the function chose?
// jsdom has no layout, so every real `getBoundingClientRect()` returns zeros —
// which is precisely why the rects here are stubbed rather than laid out, and
// why this suite can never claim to have seen the defect. It has seen the
// decision reach the DOM. That is a different, smaller and honest claim.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DataTable } from "./DataTable";
import { defaultRequestState } from "./tableTypes";
import type { TableConfig } from "./tableTypes";

interface Row {
  id: string;
  name: string;
}

const CONFIG: TableConfig<Row> = {
  screenId: "S25",
  columns: [
    { key: "name", label: "Name", identity: true, sortable: true },
    { key: "other", label: "Other" },
  ],
  getRowId: (row) => row.id,
  defaultSort: { sort: "name", dir: "asc" },
};

/** Put the ▦ summary at a given x, with the viewport a given width. */
function placeSummaryAt(left: number, viewportWidth: number): void {
  vi.spyOn(document.documentElement, "clientWidth", "get").mockReturnValue(viewportWidth);
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (
    this: HTMLElement,
  ) {
    if (this.tagName.toLowerCase() !== "summary") {
      return new DOMRect(0, 0, 0, 0);
    }
    return new DOMRect(left, 0, 32, 32);
  });
}

function renderTable() {
  return render(
    <DataTable<Row>
      config={CONFIG}
      state={defaultRequestState(CONFIG)}
      onStateChange={() => undefined}
      rows={[{ id: "1", name: "A" }]}
      totalRows={1}
      loading={false}
      error={null}
      empty={{ title: "Nothing here", helper: "", ctaLabel: "Add", ctaReason: null, onCta: () => undefined }}
    />,
  );
}

/** Open the ▦ the way a clerk does — by clicking the summary. */
async function openColumnPicker(): Promise<void> {
  const summary = document.querySelector("details > summary");
  if (summary === null) {
    throw new Error("the column picker summary is not in the DOM");
  }
  await userEvent.click(summary);
}

/** The panel is the ▦ `<details>`' only absolutely-positioned child. */
function panel(): HTMLElement {
  const found = document.querySelector("details > div.absolute");
  if (found === null) {
    throw new Error("the column panel is not in the DOM");
  }
  return found as HTMLElement;
}

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
});

describe("DataTable column picker · DEF-1085 anchoring", () => {
  it("hangs the panel from the LEFT when the ▦ is near the viewport's left margin", async () => {
    // The measured live case: a wrapped toolbar's second row starts at x=24.
    placeSummaryAt(24, 1280);
    renderTable();
    await openColumnPicker();

    expect(panel().className).toContain("left-0");
    expect(panel().className).not.toContain("right-0");
  });

  it("keeps the ratified RIGHT anchoring when the ▦ ends a wide toolbar", async () => {
    placeSummaryAt(1200, 1280);
    renderTable();
    await openColumnPicker();

    expect(panel().className).toContain("right-0");
    expect(panel().className).not.toContain("left-0");
  });
});
