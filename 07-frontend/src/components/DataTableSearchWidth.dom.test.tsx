// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-1150 — the shared list search box matched NO css rule at all
//           after the Route B migration orphaned `.table-search`, so it fell
//           back to the browser's ~170px default and cut 20 of 27 prompts.
//           PO, v2.73.0, Assets page: "Search asset #, serial, r".
// Rules:    B14 rule 19 (a search prompt names what the box matches — a prompt
//           that is cut off names nothing) · B14 rule 21 · hard-won law 1
// ───────────────────────────────────────────────────────
// ⚠ **WHAT THIS SUITE CAN AND CANNOT CLAIM.**
//
// It CANNOT claim the box is 320px wide. jsdom computes no layout, the CSS is
// never applied, and no gate in this repo reads rendered output (hard-won law
// 6). Every width assertion here would pass on a 170px box and on a 512px one.
//
// What it CAN claim is the two things that actually broke, both of which are
// structural and both of which a jsdom render can see:
//
//   1. **The sizing is declared on the element the toolbar lays out.** The
//      wrapper is the flex item; sizing the INPUT instead leaves the wrapper
//      content-sized and the grow leg dead, which looks identical in source and
//      is wrong on screen.
//   2. **The ✕ is inside that same wrapper.** It is `absolute right-2`, so it
//      is positioned against whichever ancestor is `relative`. A wider box with
//      the ✕ stranded where 170px used to end is the obvious way this
//      regresses, and it is the one part of it a test can hold.
//
// The class NAMES are asserted deliberately, not as a proxy for pixels: the
// defect was a rule that existed and matched nothing, so "which element carries
// the declaration" is the exact question that went unasked for a whole migration.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { DataTable } from "./DataTable";
import { defaultRequestState } from "./tableTypes";
import type { TableConfig } from "./tableTypes";

interface Row {
  id: string;
  name: string;
}

const CONFIG: TableConfig<Row> = {
  screenId: "S25",
  columns: [{ key: "name", label: "Name", identity: true, sortable: true }],
  getRowId: (row) => row.id,
  defaultSort: { sort: "name", dir: "asc" },
  searchFields: ["name"],
  searchPlaceholder: "metering.reads.searchPlaceholder",
};

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

function searchBox(): HTMLInputElement {
  const found = document.querySelector<HTMLInputElement>('input[type="search"]');
  if (found === null) {
    throw new Error("the shared search box is not in the DOM");
  }
  return found;
}

afterEach(cleanup);

describe("DataTable search box · DEF-1150", () => {
  it("carries the field kit, so the box is not an unstyled browser default", () => {
    renderTable();
    // `.input` is FormModal.css's declared field kit — reused, not re-declared,
    // which is what B14 rule 21 is actually asking for (DEF-974).
    expect(searchBox().className.split(/\s+/)).toContain("input");
  });

  it("declares its sizing on the WRAPPER, which is what the toolbar lays out", () => {
    renderTable();
    const wrapper = searchBox().parentElement;
    expect(wrapper).not.toBeNull();
    const classes = wrapper?.className ?? "";
    // CR-045 R2: WANTS 320px, grows into whatever the toolbar leaves, SHRINKS
    // to a 240px floor before anything wraps, ceiling 512px.
    //
    // ⚠ THE FLOOR IS ASSERTED AT 15rem AND NOT 20rem ON PURPOSE. A hard 320px
    // floor adds width to a toolbar DEF-1085 already measured as over budget,
    // and would push the filters and the ▦ onto a second row on a narrow
    // viewport. The three wave A changes work as a set: search takes +150px,
    // the ↓ glyph returns ~95px, and R7's five-term prompt cap is what lets the
    // box shrink to 240px without cutting text. Filters wrap; search never does.
    expect(classes).toContain("flex-[1_1_20rem]");
    expect(classes).toContain("min-w-[15rem]");
    expect(classes).toContain("max-w-[32rem]");
    // …and the wrapper is the positioning context the ✕ needs.
    expect(classes).toContain("relative");
  });

  it("keeps the ✕ INSIDE that wrapper, so it follows the width instead of being stranded", async () => {
    renderTable();
    await userEvent.type(searchBox(), "M-40");

    const clear = document.querySelector('button[aria-label]');
    expect(clear, "the clear control did not appear after typing").not.toBeNull();
    // ⚠ THE WHOLE ASSERTION. `absolute right-2` resolves against the nearest
    // positioned ancestor. If the ✕ ever moves out of this wrapper it will
    // position against whatever else happens to be `relative` — and a box that
    // grew to 512px with its ✕ sitting at 170px is the regression this exists
    // to catch.
    expect(searchBox().parentElement?.contains(clear as Node)).toBe(true);
    expect(clear?.className).toContain("absolute");
    expect(clear?.className).toContain("right-2");
  });
});
