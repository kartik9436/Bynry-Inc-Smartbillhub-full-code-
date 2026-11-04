// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:  Finance blueprint `P5.9` (p067–p068) — 6·1 is a CLOSE, not a board ·
//         `P5.10` — the amounts · `DEF-LED-6600` — the seventh checklist item
//         rendered its raw code to a clerk.
// Rules:  B14 rule 31 (no database id or internal code is ever a visible
//         value) · rules 32/33 (a description budget; RATIONALE is ZERO words
//         on screen) · rule 43 (a piece of UI is a COMPONENT) · BR-LED-018
//         (WARN + CONFIRM — never a lockout) · BR-SHL-025 (a figure this
//         deployment cannot state travels WITH its reason) · CLAUDE.md
//         hard rule 2 (money DISPLAYS to two decimals) · hard-won law 2 (built
//         is not wired — and its mirror, a live screen behind a dead control)
// ───────────────────────────────────────────────────────
/*
WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per hard-won law 7
---------------------------------------------------------------------------
**(a) A FIXTURE WHOSE ITEMS ARE ALL THE SAME.** Seven complete rows would draw
no door and no amount and every case here would pass over a component that
could render neither. The fixture holds one of each: complete, incomplete with
money, incomplete with a count, and `unknown`.

**(b) A BARE `MemoryRouter` WITH NO `/:tenant` ROUTE.** `useTenantPath` then
returns `//finance/...` — a protocol-relative URL to another host, which reads
as a perfectly good string to `toContain`. CLAUDE.md records this costing the
portal eight doors. Every render here mounts under the real path pattern and
the door assertions check the href STARTS WITH `/<tenant>/`.

**(c) ASSERTING THE LABEL MAP AGAINST ITSELF.** A test that listed the seven
codes it expects would agree with a map that had the same seven typed into it
and would say nothing about the EIGHTH item the day one lands — which is
exactly how `unpaid_cost_accrual` reached a clerk as a raw string. So the
coverage case reads the codes off the FIXTURE and, more importantly, asserts
that **no rendered cell equals its own code**, which is the property that was
false in the running product.
*/
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { CloseChecklistItem, CloseChecklistResponse } from "@/api/endpoints";

import { CloseView, checklistTone } from "./CloseView";
import { FINANCE_ROUTE } from "./financeShared";

afterEach(cleanup);

const TENANT = "brazosbend";

function item(over: Partial<CloseChecklistItem> & { code: string }): CloseChecklistItem {
  return {
    state: "complete",
    complete: true,
    detail: "the server's own English, which no screen renders",
    wanted_reads: [],
    outstanding: null,
    amount: null,
    ...over,
  };
}

/**
 * One of each kind of row, per (a). ⚠ **`unpaid_cost_accrual` IS IN IT ON
 * PURPOSE** — it is the code a clerk read on the live screen from 2026-09-02
 * until today (`DEF-LED-6600`), and a fixture without it cannot prove the fix.
 */
const CHECKLIST: CloseChecklistResponse = {
  period: { start: "2026-09-01", end: "2026-09-30" },
  items: [
    item({ code: "runs_issued", state: "unknown", complete: false,
      wanted_reads: ["apps.billing.selectors.unissued_run_count(start, end) -> int"] }),
    item({ code: "batches_reconciled" }),
    item({ code: "bank_rec_current", state: "incomplete", complete: false, outstanding: 3 }),
    item({ code: "accruals_posted" }),
    item({ code: "unbilled_accrual", state: "incomplete", complete: false,
      amount: "12653.550000", outstanding: 4 }),
    item({ code: "unpaid_cost_accrual", state: "incomplete", complete: false,
      amount: "2400.000000", outstanding: 1 }),
    item({ code: "remittance_recorded" }),
  ],
  incomplete: ["runs_issued", "bank_rec_current", "unbilled_accrual", "unpaid_cost_accrual"],
  ready: false,
  closed: false,
  unavailable: [],
  closed_periods: [
    { period: { start: "2026-08-01", end: "2026-08-31" }, status: "closed",
      closed_at: "2026-09-05T10:00:00Z", reason: "two items left", incomplete_items: [{ code: "runs_issued", state: "unknown", detail: "not published" }],
      reopened_at: null, reopen_reason: null },
  ],
  currency: "USD",
};

function draw(checklist: CloseChecklistResponse = CHECKLIST): void {
  render(
    <MemoryRouter initialEntries={[`/${TENANT}${FINANCE_ROUTE}/export`]}>
      <Routes>
        <Route
          path={`/:tenant${FINANCE_ROUTE}/export`}
          element={
            <CloseView
              checklist={checklist}
              currency="USD"
              month="September"
              canClose
              onClose={() => undefined}
            />
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("P5.9 · 6·1 is a close, not a board", () => {
  it("draws TWO numbered steps, in order", () => {
    draw();
    // The drawing's bands: finish the month, then close it. A close is a job
    // with an order, and the board it replaced had none.
    expect(screen.getByRole("heading", { name: "Step 1 · Finish" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Step 2 · Close" })).toBeInTheDocument();

    const headings = screen
      .getAllByRole("heading")
      .map((node) => node.textContent ?? "");
    expect(headings.indexOf("Step 1 · Finish")).toBeLessThan(headings.indexOf("Step 2 · Close"));
  });

  it("gives EVERY unfinished row a door, and every finished row none", () => {
    draw();
    // p068 item 4 calls this "the change that makes this usable". The board had
    // no door on any row at all.
    for (const code of CHECKLIST.incomplete) {
      const row = screen.getByRole("row", { name: new RegExp(labelOf(code)) });
      expect(within(row).getAllByRole("link").length).toBe(1);
    }
    const done = screen.getByRole("row", { name: /Tax remittance recorded/ });
    expect(within(done).queryAllByRole("link").length).toBe(0);
  });

  it("every door is a REAL tenant address, not a protocol-relative one", () => {
    // ⚠ (b) above. `//finance/taxes` is a URL to another HOST and it reads as a
    // perfectly good string to `toContain` — which is how the customer portal
    // shipped eight broken doors with 391 green cases over them.
    draw();
    const links = screen.getAllByRole("link");
    expect(links.length).toBe(CHECKLIST.incomplete.length);
    for (const link of links) {
      const href = link.getAttribute("href") ?? "";
      expect(href.startsWith(`/${TENANT}/`)).toBe(true);
      expect(href.startsWith("//")).toBe(false);
    }
  });
});

describe("P5.10 · what each row is worth", () => {
  it("shows the money figure to TWO decimals off four stored", () => {
    draw();
    // hard rule 2: stored to four, DISPLAYED to two. The server sends
    // "12653.550000" and a clerk reads a figure they can say out loud.
    const row = screen.getByRole("row", { name: /Unbilled revenue accrued/ });
    expect(within(row).getByText(/12,653\.55/)).toBeInTheDocument();
    expect(within(row).queryByText(/12653\.550000/)).not.toBeInTheDocument();
  });

  it("shows a COUNT where the item is counted rather than valued", () => {
    draw();
    const row = screen.getByRole("row", { name: /Bank reconciliation/ });
    expect(within(row).getByText("3 bank lines unmatched")).toBeInTheDocument();
  });

  it("says NOTHING in the amount cell of a row that is done", () => {
    // ⚠ `$0.00` beside a tick reads as a measurement somebody took. The absence
    // reads as nothing to measure, which is what is true (DEF-127's shape).
    draw();
    const row = screen.getByRole("row", { name: /Tax remittance recorded/ });
    const cells = within(row).getAllByRole("cell");
    expect(cells[1].textContent).toBe("");
  });

  it("states an unmeasurable figure WITH its reason, never as a blank", () => {
    // BR-SHL-025. `runs_issued` is `unknown` because billing publishes no read.
    draw();
    const row = screen.getByRole("row", { name: /Bill runs issued|billing runs issued/i });
    expect(within(row).getByText("Not measured")).toBeInTheDocument();
  });
});

describe("DEF-LED-6600 · no checklist row renders its own code", () => {
  it("the seventh item reads as English, not as `unpaid_cost_accrual`", () => {
    draw();
    expect(screen.queryByText("unpaid_cost_accrual")).not.toBeInTheDocument();
    expect(screen.getByText("Supplier costs accrued")).toBeInTheDocument();
  });

  it("NO row's label equals its own code — the property, not a list of seven", () => {
    // ⚠ (c) above. A case listing the seven codes would agree with a map that
    // had the same seven typed into it and would be silent on the EIGHTH item
    // the day one lands, which is exactly how the seventh reached a clerk.
    draw();
    for (const one of CHECKLIST.items) {
      expect(screen.queryByText(one.code)).not.toBeInTheDocument();
    }
  });

  it("renders no module path or callable name anywhere (B14 rule 31)", () => {
    draw();
    expect(document.body.textContent ?? "").not.toContain("apps.billing.selectors");
  });
});

describe("BR-LED-018 · the close warns and is never a lockout", () => {
  it("names the count and leaves the button live", () => {
    draw();
    // p068's PRIMARY ACTION: `Close September ✓`. B14 rule 4 — `Verb ✓`
    // commits, and naming the month is what the clerk reads last.
    const button = screen.getByRole("button", { name: "Close September ✓" });
    expect(button).toBeEnabled();
    expect(screen.getByText(/4 items are not done/)).toBeInTheDocument();
  });

  it("maps unknown to neutral, not to the same tone as not-done", () => {
    expect(checklistTone("complete")).toBe("success");
    expect(checklistTone("incomplete")).toBe("warning");
    expect(checklistTone("unknown")).toBe("neutral");
  });
});

describe("the closed months came with the screen", () => {
  it("draws the history under the same head as the two steps", () => {
    // It was a third Panel on the page until `P5.9`; p067 draws all three
    // bands under one head, and leaving it behind would have split one drawn
    // screen across two files.
    draw();
    expect(screen.getByRole("heading", { name: "Months already closed" })).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /2026-08-01/ })).toBeInTheDocument();
  });

  it("draws nothing at all when nothing has ever been closed", () => {
    draw({ ...CHECKLIST, closed_periods: [] });
    expect(screen.queryByRole("heading", { name: "Months already closed" })).toBeNull();
  });
});

/** The English a row is expected to read as, for the door case's row lookup. */
function labelOf(code: string): string {
  const words: Record<string, string> = {
    runs_issued: "runs issued",
    batches_reconciled: "Deposit batches reconciled",
    bank_rec_current: "Bank reconciliation",
    accruals_posted: "Accruals",
    unbilled_accrual: "Unbilled revenue accrued",
    unpaid_cost_accrual: "Supplier costs accrued",
    remittance_recorded: "Tax remittance recorded",
  };
  return words[code] ?? code;
}
