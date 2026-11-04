// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-029 RC-W3-T0 — the kit gains expandable rows (B17 §7)
// Screens:  SET-06.3 (route wizard step 3: premises rows → unit/meter sub-table)
// Rules:    BR-SHL-010 (an undeclared capability never renders) · B14 rule 20
//           (one table type) · B14 rule 12 (the toolbar's grammar is fixed)
// ───────────────────────────────────────────────────────
// ⚠ **THIS SUITE IS THE WIRING (hard-won law 2).** `renderExpanded` lands a
// wave before the screens that pass it, so on the day it merges NO consuming
// screen exists. "A component with an optional prop that nothing passes is dead
// UI: it renders nothing, every test passes, and the feature does not exist" —
// four defects in one day. The only honest defence when a kit row is
// deliberately built ahead of its consumer is to drive the real states here:
// collapsed → expanded → collapsed, one row and all rows, by POINTER and by
// KEYBOARD, asserting what a person actually gets.
//
// A first-paint (`renderToStaticMarkup`) test cannot do that at all — disclosure
// is state, and state needs an event. That is DEF-523's finding, and this file
// follows `ImportWorkflowPage.dom.test.tsx`'s `.dom.test.tsx` + jsdom pragma
// convention so the two layers stay visibly distinct.
import "@/i18n";
// Registers `toBeInTheDocument` on vitest's `expect`, scoped to this file so
// the 200+ static-markup suites are untouched.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { DataTable } from "./DataTable";
import { defaultRequestState } from "./tableTypes";
import type { TableConfig } from "./tableTypes";

const noop = () => undefined;

type PremisesRow = { id: string; premises_no: string; address: string; meters: string };

// SET-06.3's shape: premises rows, each opening into the units and meters read
// at that stop. The sub-table is a TABLE — that is what the content is — and it
// carries `.data-table` so B14 rule 20's one type reaches it too.
const rows: PremisesRow[] = [
  { id: "p1", premises_no: "PRM-001", address: "12 Mill St", meters: "3" },
  { id: "p2", premises_no: "PRM-002", address: "14 Mill St", meters: "1" },
  { id: "p3", premises_no: "PRM-003", address: "16 Mill St", meters: "8" },
];

const SUB_ROWS: Record<string, string[]> = {
  p1: ["Unit 1 · MTR-W1001", "Unit 2 · MTR-W1002"],
  p2: ["Unit 1 · MTR-W1010"],
  p3: ["Unit 1 · MTR-W1020"],
};

function config(withCapability: boolean): TableConfig<PremisesRow> {
  const base: TableConfig<PremisesRow> = {
    screenId: "SET-06.3",
    columns: [
      { key: "premises_no", label: "Premises #", identity: true, sortable: true },
      { key: "address", label: "Address", sortable: true },
      { key: "meters", label: "Meters", numeric: true },
    ],
    getRowId: (row) => row.id,
    defaultSort: { sort: "premises_no", dir: "asc" },
  };
  if (!withCapability) {
    return base;
  }
  return {
    ...base,
    renderExpanded: (row) => (
      <table className="data-table">
        <tbody>
          {SUB_ROWS[row.id].map((line) => (
            <tr key={line}>
              <td>{line}</td>
            </tr>
          ))}
        </tbody>
      </table>
    ),
  };
}

function mount(withCapability = true) {
  const cfg = config(withCapability);
  return render(
    <DataTable
      config={cfg}
      state={defaultRequestState(cfg)}
      onStateChange={noop}
      rows={rows}
      totalRows={rows.length}
      loading={false}
      empty={{ title: "t", helper: "h", ctaLabel: "c", onCta: noop }}
    />,
  );
}

afterEach(cleanup);

describe("RC-W3-T0 — a premises row opens into its unit/meter sub-table", () => {
  it("RC-W3-T0: clicking Expand reveals the sub-table and flips aria-expanded; clicking again removes it", async () => {
    const user = userEvent.setup();
    mount();

    const control = screen.getByRole("button", { name: "Expand PRM-001" });
    expect(control).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Unit 1 · MTR-W1001")).not.toBeInTheDocument();

    await user.click(control);

    // The SAME control is now named for the action it performs next — a button
    // still reading "Expand" over an open row lies to a screen reader.
    const open = screen.getByRole("button", { name: "Collapse PRM-001" });
    expect(open).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Unit 1 · MTR-W1001")).toBeInTheDocument();
    expect(screen.getByText("Unit 2 · MTR-W1002")).toBeInTheDocument();
    // Only the row that was clicked opened.
    expect(screen.queryByText("Unit 1 · MTR-W1010")).not.toBeInTheDocument();

    await user.click(open);
    expect(screen.queryByText("Unit 1 · MTR-W1001")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Expand PRM-001" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("RC-W3-T0: the expanded content sits in ONE cell spanning every visible column plus the expander column", async () => {
    const user = userEvent.setup();
    mount();
    // Rendered through the component's own state rather than a prop, so this
    // is what a person sees, not what a test constructed.
    await user.click(screen.getByRole("button", { name: "Expand PRM-003" }));
    const cell = document.querySelector("td[colspan]");
    expect(cell).not.toBeNull();
    // three declared columns + the expander column
    expect(cell?.getAttribute("colspan")).toBe("4");
    expect(within(cell as HTMLElement).getByText("Unit 1 · MTR-W1020")).toBeInTheDocument();
    // B14 rule 20: the sub-table is the ONE table type, not a second one.
    expect(cell?.querySelector("table")?.className).toContain("data-table");
  });

  it("RC-W3-T0 (keyboard): the control is reachable by Tab and operated by Enter and Space", async () => {
    const user = userEvent.setup();
    mount();

    const control = screen.getByRole("button", { name: "Expand PRM-001" });
    control.focus();
    expect(document.activeElement).toBe(control);

    await user.keyboard("{Enter}");
    expect(screen.getByText("Unit 1 · MTR-W1001")).toBeInTheDocument();

    // Focus stays on the control across the toggle — a disclosure that moves
    // focus strands a keyboard user outside the region they just opened.
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Collapse PRM-001" }));

    await user.keyboard(" ");
    expect(screen.queryByText("Unit 1 · MTR-W1001")).not.toBeInTheDocument();

    // And it is genuinely in the tab order, not focusable only by script.
    await user.tab();
    await user.tab();
    expect(document.activeElement).not.toBe(document.body);
  });
});

describe("RC-W3-T0 — Expand all", () => {
  it("RC-W3-T0: Expand all opens every row on the page, renames itself, and collapses them all again", async () => {
    const user = userEvent.setup();
    mount();

    const all = screen.getByRole("button", { name: "Expand all rows" });
    await user.click(all);

    expect(screen.getByText("Unit 1 · MTR-W1001")).toBeInTheDocument();
    expect(screen.getByText("Unit 1 · MTR-W1010")).toBeInTheDocument();
    expect(screen.getByText("Unit 1 · MTR-W1020")).toBeInTheDocument();
    expect(document.querySelectorAll("td[colspan]")).toHaveLength(3);
    for (const premises of ["PRM-001", "PRM-002", "PRM-003"]) {
      expect(screen.getByRole("button", { name: `Collapse ${premises}` })).toHaveAttribute(
        "aria-expanded",
        "true",
      );
    }

    const collapse = screen.getByRole("button", { name: "Collapse all rows" });
    await user.click(collapse);
    expect(document.querySelectorAll("td[colspan]")).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Expand all rows" })).toBeInTheDocument();
  });

  it("RC-W3-T0: the bulk control follows the rows — opening the last closed row by hand turns it into Collapse all", async () => {
    const user = userEvent.setup();
    mount();

    for (const premises of ["PRM-001", "PRM-002"]) {
      await user.click(screen.getByRole("button", { name: `Expand ${premises}` }));
    }
    // Two of three open — the bulk control still offers the expanding action.
    expect(screen.getByRole("button", { name: "Expand all rows" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Expand PRM-003" }));
    expect(screen.getByRole("button", { name: "Collapse all rows" })).toBeInTheDocument();
  });
});

describe("RC-W3-T0 — BR-SHL-010: an undeclared capability does not exist", () => {
  it("RC-W3-T0: a list with no renderExpanded has no expander column, no per-row control and no Expand all", () => {
    mount(false);
    expect(screen.queryByRole("button", { name: /Expand/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Collapse/ })).not.toBeInTheDocument();
    expect(document.querySelector("[aria-expanded]")).toBeNull();
    expect(document.querySelectorAll("thead th")).toHaveLength(3);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-029 RC-W3-T0 (B17 §7 · the kit prerequisite SET-06.3 needs)
// generated: 2026-08-23 by the CR-029 RC-W3-T0 kit lane
// checklist: A✔ B✔ C✔ D✔ (every case here was written and run RED before a
//         line of the capability existed — "Unable to find an accessible
//         element with the role \"button\" and name \"Expand PRM-001\"", five
//         cases, plus six in DataTable.test.tsx) E✔ F✔ G✔ H=n/a (no screen
//         consumes this yet — RC-W3-T1..T5 is the consumer)
// gates: vitest 2100 passed / 184 todo across 122 files✔ (jsdom via this
//         file's pragma; the default environment stays `node`) · tsc✔ ·
//         eslint --max-warnings 0 on src/components✔ · g13✔ · g15/g18 —
//         the four `table.expand.*` keys are in all eleven catalogues with a
//         call site each; both gates' failures name other lanes' keys · g31 —
//         DataTable.tsx is a Route B file, so its classes are compiled by
//         src/styles/routeBUtilities.test.ts, which is green · g37✔
// exceptions: E3 the disclosure glyph is a TEXT marker (▸/▾), not an SVG from
//         icons.tsx — B14 rule 15's vocabulary is for row actions ("this only
//         for table actions ; not for buttons", PO 2026-08-20) and G37
//         refuses one inside a plain <button>; adding a triangle to that
//         vocabulary would widen a ruled list without a ruling · E3 the open
//         set is INTERNAL state with no controlled prop pair, because two more
//         optional props nothing passes is exactly DEF-007..010
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
