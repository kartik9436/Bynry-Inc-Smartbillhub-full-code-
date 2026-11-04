// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Defect:   DEF-CWP-3977 (D2) — no portal list can be searched, sorted or
//           paged; 13-wireframe-delta X6 (no row icons) and X7 (no footer).
// Rules:    B14 rule 12 (toolbar) · 13 (asc → desc → clear) · 15 (row icons
//           with an accessible name) · 16 (footer) · 17 (empty state) ·
//           20 (ONE table type — this component draws no <table> of its own)
// ⚠ EVERY CASE HERE USES THE CONTROL RATHER THAN READING IT. The audit's D14 is
//   that 391 portal cases passed over every gap because each asserted the facts
//   its screen showed; a test that asserts a search box EXISTS passes on a
//   search box wired to nothing. So each case types, clicks or pages, and reads
//   what changed.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { EyeIcon } from "@/components/icons";
import { PortalListTable, compareValues, nextSort } from "./listTable";

interface Row {
  id: string;
  name: string;
  amount: number;
}

const ROWS: Row[] = [
  { id: "a", name: "Bravo", amount: 10 },
  { id: "b", name: "Alpha", amount: 9 },
  { id: "c", name: "Charlie", amount: 100 },
];

function draw(rows: Row[], extra: Record<string, unknown> = {}) {
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/things"]}>
      <Routes>
        <Route
          path="/:tenant/portal/things"
          element={
            <PortalListTable<Row>
              screen="TEST-01"
              caption="things"
              rows={rows}
              rowKey={(r) => r.id}
              empty={<p>Nothing yet.</p>}
              columns={[
                { key: "name", label: "Name", sortable: true, sortValue: (r) => r.name, cell: (r) => r.name },
                {
                  key: "amount",
                  label: "Amount",
                  align: "right",
                  sortable: true,
                  sortValue: (r) => r.amount,
                  cell: (r) => String(r.amount),
                },
              ]}
              {...extra}
            />
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("rule 13 · the sort cycle is asc → desc → clear", () => {
  it("returns to the SERVER's order on the third click, not to ascending", () => {
    // The third state is the one that is easy to drop, and dropping it means a
    // customer can never get back to the order the list opened in.
    expect(nextSort(null, "name")).toEqual({ key: "name", dir: "asc" });
    expect(nextSort({ key: "name", dir: "asc" }, "name")).toEqual({ key: "name", dir: "desc" });
    expect(nextSort({ key: "name", dir: "desc" }, "name")).toBeNull();
    // A DIFFERENT column starts its own cycle at ascending.
    expect(nextSort({ key: "name", dir: "desc" }, "amount")).toEqual({ key: "amount", dir: "asc" });
  });

  it("sorts a money column as a NUMBER, so 9 comes below 10", async () => {
    // Sorting the rendered string puts "9" after "100" and looks broken on the
    // one screen a customer checks arithmetic on.
    draw(ROWS);
    await userEvent.click(screen.getByRole("button", { name: "Sort by Amount" }));
    const cells = screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[1].textContent);
    expect(cells).toEqual(["9", "10", "100"]);
  });

  it("reverses on the second click and restores the original order on the third", async () => {
    draw(ROWS);
    const heading = screen.getByRole("button", { name: "Sort by Name" });
    await userEvent.click(heading);
    expect(rowNames()).toEqual(["Alpha", "Bravo", "Charlie"]);
    await userEvent.click(heading);
    expect(rowNames()).toEqual(["Charlie", "Bravo", "Alpha"]);
    await userEvent.click(heading);
    expect(rowNames()).toEqual(["Bravo", "Alpha", "Charlie"]); // as supplied
  });

  it("says which way it is sorted, to a screen reader as well as to the eye", async () => {
    draw(ROWS);
    const heading = screen.getByRole("button", { name: "Sort by Name" });
    expect(heading).toHaveAttribute("aria-sort", "none");
    await userEvent.click(heading);
    expect(heading).toHaveAttribute("aria-sort", "ascending");
    await userEvent.click(heading);
    expect(heading).toHaveAttribute("aria-sort", "descending");
  });

  it("puts a MISSING value last in both directions", () => {
    // An absent date is not "the earliest"; burying it under a descending sort
    // would hide the row entirely.
    expect(compareValues(null, "2026-01-01")).toBeGreaterThan(0);
    expect(compareValues("2026-01-01", null)).toBeLessThan(0);
    expect(compareValues(null, null)).toBe(0);
  });
});

describe("rule 12 · the toolbar actually narrows the list", () => {
  it("types in the search box and the rows change", async () => {
    draw(ROWS, {
      search: { placeholder: "Search things…", match: (r: Row, n: string) => r.name.toLowerCase().includes(n) },
    });
    expect(rowNames()).toHaveLength(3);
    await userEvent.type(screen.getByRole("searchbox", { name: "Search things…" }), "alp");
    expect(rowNames()).toEqual(["Alpha"]);
  });

  it("says so, in words, when a search matches nothing — and does not show an empty table", async () => {
    draw(ROWS, {
      search: { placeholder: "Search things…", match: (r: Row, n: string) => r.name.toLowerCase().includes(n) },
    });
    await userEvent.type(screen.getByRole("searchbox", { name: "Search things…" }), "zzz");
    expect(screen.getByText("Nothing here matches what you typed.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("has a search box that is LABELLED, not just placeheld", async () => {
    // A placeholder disappears the moment somebody types — which is exactly
    // when a screen-reader user needs to know what the field is. This is D4's
    // fault (a label written to aria-label only) caught from the other side.
    draw(ROWS, {
      search: { placeholder: "Search things…", match: () => true },
    });
    expect(screen.getByLabelText("Search things…")).toBeInTheDocument();
  });

  it("filters on a chip, and All puts everything back", async () => {
    // ⚠ The chips are `radio`s and not `button`s, because `SegmentedChoice`
    // became a real `radiogroup` on 2026-09-05 (the D4 fix, `DEF-CWP-3979`) —
    // it used to write its label to `aria-label` only and paint the selected
    // option in the danger colour. Addressed by ROLE and NAME so this case
    // follows the control rather than its markup.
    draw(ROWS, {
      chips: { label: "Which", options: [{ key: "big", label: "Big", match: (r: Row) => r.amount >= 10 }] },
    });
    expect(screen.getByRole("radiogroup", { name: "Which" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Big" }));
    expect(rowNames()).toEqual(["Bravo", "Charlie"]);
    await userEvent.click(screen.getByRole("radio", { name: "All" }));
    expect(rowNames()).toHaveLength(3);
  });
});

describe("rule 15 · row icons", () => {
  it("gives every icon an accessible name — an unnamed glyph is unusable without a mouse", () => {
    draw(ROWS, {
      icons: [{ key: "view", icon: <EyeIcon />, label: (r: Row) => `View ${r.name}`, to: () => "/x" }],
    });
    expect(screen.getByRole("link", { name: "View Alpha" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View Bravo" })).toBeInTheDocument();
  });

  it("keeps a blocked action VISIBLE and says why, rather than dropping it from the row", () => {
    draw(ROWS, {
      icons: [
        {
          key: "view",
          icon: <EyeIcon />,
          label: (r: Row) => `View ${r.name}`,
          to: () => "/x",
          reason: (r: Row) => (r.name === "Alpha" ? "No number yet." : null),
        },
      ],
    });
    const blocked = screen.getByRole("button", { name: "View Alpha" });
    expect(blocked).toBeDisabled();
    expect(blocked).toHaveAttribute("title", "No number yet.");
  });
});

describe("rule 16 · the footer", () => {
  it("counts the rows, names the page, and PAGES when there are more than fit", async () => {
    const many = Array.from({ length: 120 }, (_, i) => ({ id: String(i), name: `Row ${i}`, amount: i }));
    draw(many);
    expect(screen.getByText("1–50 of 120")).toBeInTheDocument();
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
    expect(rowNames()).toHaveLength(50);
    await userEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(screen.getByText("51–100 of 120")).toBeInTheDocument();
    expect(screen.getByText("Page 2 of 3")).toBeInTheDocument();
  });

  it("counts what the SEARCH left, not what the server sent", async () => {
    // A footer reading "1-50 of 120" over eleven rows is a lie with pagination
    // drawn on it.
    const many = Array.from({ length: 120 }, (_, i) => ({ id: String(i), name: `Row ${i}`, amount: i }));
    draw(many, {
      search: { placeholder: "Search things…", match: (r: Row, n: string) => r.name.toLowerCase().includes(n) },
    });
    await userEvent.type(screen.getByRole("searchbox", { name: "Search things…" }), "row 11");
    // Row 11 and Row 110..119 — eleven rows, and the footer must say eleven.
    expect(screen.getByText("1–11 of 11")).toBeInTheDocument();
  });

  it("goes back to page 1 when the result set changes under it", async () => {
    const many = Array.from({ length: 120 }, (_, i) => ({ id: String(i), name: `Row ${i}`, amount: i }));
    draw(many, {
      search: { placeholder: "Search things…", match: (r: Row, n: string) => r.name.toLowerCase().includes(n) },
    });
    await userEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(screen.getByText("Page 2 of 3")).toBeInTheDocument();
    await userEvent.type(screen.getByRole("searchbox", { name: "Search things…" }), "row 11");
    expect(screen.getByText("Page 1 of 1")).toBeInTheDocument();
  });

  it("is ABSENT where the drawing gives no footer, and every row is still there", () => {
    const many = Array.from({ length: 120 }, (_, i) => ({ id: String(i), name: `Row ${i}`, amount: i }));
    draw(many, { footer: false });
    expect(screen.queryByRole("button", { name: "Next page" })).not.toBeInTheDocument();
    expect(rowNames()).toHaveLength(120);
  });
});

describe("rule 17 · the empty state", () => {
  it("is a sentence, with no table and no toolbar over nothing", () => {
    draw([], { search: { placeholder: "Search things…", match: () => true } });
    expect(screen.getByText("Nothing yet.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
  });
});

describe("rule 20 · ONE table type", () => {
  it("draws exactly one <table>, and it is MiniTable's", () => {
    draw(ROWS);
    expect(screen.getAllByRole("table")).toHaveLength(1);
    expect(document.querySelector("table[data-minitable]")).not.toBeNull();
  });
});

function rowNames(): string[] {
  return screen
    .getAllByRole("row")
    .slice(1)
    .map((r) => within(r).getAllByRole("cell")[0].textContent ?? "");
}
