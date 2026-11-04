// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-SHL-10643 — the `+ Filter` panel opened UNDER THE SIDEBAR when
//           `+ Filter` was the first control of a toolbar (Work › From the
//           field › Finished jobs, which has no search box): `right-0` hung the
//           320px panel to the left of a button 73px from the content
//           column's edge, and the 2.608.0 walk could not tick *Not done —
//           payment received*.
// Rules:    B14 rule 12 (the toolbar's grammar) · hard-won law 6 (no gate reads
//           rendered output) · DEF-1085 (the same shape for the column picker,
//           measured against the viewport only)
// ───────────────────────────────────────────────────────
// jsdom has no layout, so the rects are mocked: the `+ Filter` summary where
// the walk measured it (x 313–384) and the content column (`<main>`) starting
// at the sidebar's right edge, x 240.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FilterBar } from "./FilterBar";
import type { TableFilterConfig, TableRequestState } from "./tableTypes";

const FILTERS: TableFilterConfig[] = [
  {
    name: "outcome",
    label: "Outcome",
    options: [
      { value: "passed", label: "Passed" },
      { value: "not_done_paid", label: "Not done — payment received" },
    ],
  },
];

const STATE: TableRequestState = { q: "", sort: "completed_at", dir: "asc", page: 1, per: 50, filters: {} };

function place(summaryLeft: number, mainLeft: number, viewportWidth = 1440): void {
  vi.spyOn(document.documentElement, "clientWidth", "get").mockReturnValue(viewportWidth);
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    const tag = this.tagName.toLowerCase();
    if (tag === "summary") return new DOMRect(summaryLeft, 0, 71, 28);
    if (tag === "main") return new DOMRect(mainLeft, 0, viewportWidth - mainLeft, 900);
    return new DOMRect(0, 0, 0, 0);
  });
}

function mount() {
  return render(
    <main>
      <FilterBar filters={FILTERS} state={STATE} onStateChange={() => undefined} />
    </main>,
  );
}

async function open(): Promise<HTMLElement> {
  const summary = document.querySelector("details > summary");
  if (summary === null) throw new Error("no + Filter summary");
  await userEvent.click(summary);
  const panel = document.querySelector("details > div.absolute");
  if (panel === null) throw new Error("no + Filter panel");
  return panel as HTMLElement;
}

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
});

describe("FilterBar panel · DEF-SHL-10643 anchoring", () => {
  it("hangs from the LEFT when right-anchoring would put it behind the sidebar (the walk's WRK-26 case)", async () => {
    place(313, 240);
    mount();
    const panel = await open();
    // Right-anchored: 384 - 320 = 64, which is inside the 1440px viewport and
    // 176px BEHIND the content column's edge at 240.
    expect(panel.className).toContain("left-0");
    expect(panel.className).not.toContain("right-0");
  });

  it("keeps the drawn RIGHT anchoring when the panel fits inside the content column", async () => {
    place(900, 240);
    mount();
    const panel = await open();
    expect(panel.className).toContain("right-0");
    expect(panel.className).not.toContain("left-0");
  });
});
