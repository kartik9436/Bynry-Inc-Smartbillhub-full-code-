// @vitest-environment jsdom
// DEF-RAT-9311 and DEF-RAT-9312 — the discount details Overview (filed by the
// coordinator on 2026-10-03 against 2.480.0, fixed by CR-166-BRC10 round 3 task 7).
import "@testing-library/jest-dom/vitest";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { DiscountDetailRow } from "@/api/discountDetailEndpoints";
import { FactBlock, lastFactSpan } from "@/components/FactBlock";

import { money } from "./discountDetailModel";

afterEach(cleanup);

/** The served shape on PostgreSQL: the stored figure, the currency, and a
 *  `money_display` that carries the `$` and NO thousands separator. */
function row(extra: Record<string, unknown> = {}): DiscountDetailRow {
  return {
    currency: "USD",
    budget_cap: "2383.000000",
    budget_cap_display: "2383.00",
    budget_remaining: "12312.500000",
    money_display: { budget_cap: "$2383.00", budget_remaining: "$12312.50" },
    ...extra,
  } as unknown as DiscountDetailRow;
}

describe("DEF-RAT-9311 · money over 999 reads with its thousands separator", () => {
  it("2383 is $2,383.00 and 12312.5 is $12,312.50 — through the shared formatter", () => {
    expect(money(row(), "budget_cap")).toBe("$2,383.00");
    expect(money(row(), "budget_remaining")).toBe("$12,312.50");
  });

  it("a figure that did not arrive is still null (a dash on screen), never $0.00", () => {
    expect(money(row({ budget_cap: null, money_display: { budget_cap: null } }), "budget_cap")).toBeNull();
  });

  it("an older server with no currency falls back to its own display string", () => {
    expect(money(row({ currency: null }), "budget_cap")).toBe("$2383.00");
  });
});

describe("DEF-RAT-9312 · a fixed-column strip leaves no empty grid block", () => {
  it("the last fact runs to the end of its row, so the shell never shows through", () => {
    const facts = Array.from({ length: 13 }, (_, i) => ({ id: `f${i}`, label: `Fact ${i}`, value: String(i) }));
    render(<FactBlock name="grid" variant="strip" columns={3} facts={facts} />);
    const shell = document.querySelector("[data-facts=grid]") as HTMLElement;
    // 13 in three columns: the 13th starts a row and spans all three.
    expect(document.querySelector("[data-fact=f12]")?.className).toContain("col-span-3");
    expect(document.querySelector("[data-fact=f11]")?.className).not.toContain("col-span");
    // Nothing but dt/dd groups inside the <dl>: no filler element was added.
    expect(shell.children).toHaveLength(13);
  });

  it("the span is the cells left in the row, and a full row takes none", () => {
    expect(lastFactSpan(13, 3)).toBe("col-span-3");
    expect(lastFactSpan(14, 3)).toBe("col-span-2");
    expect(lastFactSpan(12, 3)).toBe("");
    expect(lastFactSpan(7, 4)).toBe("col-span-2");
    expect(lastFactSpan(5, undefined)).toBe("");
  });
});
