// ── Trace ──────────────────────────────────────────────
// Task:    Finance blueprint `P1.21` — the batch screen, the door half of
//          `BR-LED-798` whose backend half is `P1.22`.
// Drawing: 05-prototype/07 Finance Blueprint.pdf p029 (wireframe, eight notes,
//          the FIELDS table) · p030 (DOORS, PRIMARY ACTION, RULES)
// ───────────────────────────────────────────────────────
/**
 * The batch composer's rules, on the PURE functions rather than through a
 * mounted screen.
 *
 * ⚠ **WHAT THIS PROVES AND WHAT IT DOES NOT.** It proves the composer refuses
 * what `BR-LED-003` and `BR-LED-025` refuse, and that it refuses them BEFORE
 * the one irreversible button — which is the half of the PO's option (c) that
 * lives on the screen. It proves nothing about layout; no check here reads
 * rendered output.
 */
import { describe, expect, it } from "vitest";

import { amountProblem, batchProblem, composerProblem } from "./JournalBatchPage";

const good = {
  entryDate: "2026-09-30",
  type: "standard",
  memo: "Depreciation, September",
  debitAccountId: "acc-6910",
  creditAccountId: "acc-1600",
  amount: "812.00",
};

describe("BR-LED-025 — two decimals at the edge, and the edge is the composer", () => {
  it("takes a plain two-decimal figure", () => {
    expect(amountProblem("812.00")).toBeNull();
    expect(amountProblem("506")).toBeNull();
    expect(amountProblem("1106.85")).toBeNull();
  });

  it("refuses a third decimal, which the server refuses too", () => {
    // Caught here so the clerk fixes it while the form is open, rather than
    // after pressing the one button on this screen that cannot be undone.
    expect(amountProblem("12.345")).toBe("decimals");
  });

  it("refuses anything that is not digits", () => {
    expect(amountProblem("-50.00")).toBe("shape");
    expect(amountProblem("1,200.00")).toBe("shape");
    expect(amountProblem("abc")).toBe("shape");
    expect(amountProblem("")).toBe("empty");
  });
});

describe("p029 note 3 — two accounts and one amount cannot be unbalanced", () => {
  it("accepts a complete entry", () => {
    expect(composerProblem(good)).toBeNull();
  });

  it("refuses one account on both sides", () => {
    // The FIELDS table's own Credit account row: "Refused if equal to the debit
    // account." Such an entry moves nothing and would post cleanly — a
    // balanced, numbered, immutable no-op in the books.
    expect(composerProblem({ ...good, creditAccountId: good.debitAccountId })).toBe(
      "sameAccount",
    );
  });

  it("refuses a half-picked pair", () => {
    expect(composerProblem({ ...good, creditAccountId: "" })).toBe("accounts");
    expect(composerProblem({ ...good, debitAccountId: "" })).toBe("accounts");
  });

  it("refuses an entry with no date", () => {
    expect(composerProblem({ ...good, entryDate: "" })).toBe("date");
  });
});

describe("BR-LED-798 — what stops the BATCH, checked before anything is attempted", () => {
  const entry = (over: Partial<typeof good> = {}) => ({ ...good, ...over, key: "k" });

  it("refuses an empty batch", () => {
    // A batch of nothing that reported success would tell a finance officer
    // their month-end had posted.
    expect(batchProblem([])).toBe("empty");
  });

  it("refuses the whole batch when ONE entry has no memo", () => {
    // The PO's own worked case: five entries totalling $2,142.75, the third
    // with no memo, and NOTHING posts. This is the screen saying so first,
    // which is the single difference between the option the PO chose and the
    // one they did not.
    expect(
      batchProblem([entry(), { ...entry({ memo: "" }), key: "b" }, { ...entry(), key: "c" }]),
    ).toBe("memo");
  });

  it("lets a clean batch through", () => {
    expect(batchProblem([entry(), { ...entry(), key: "b" }])).toBeNull();
  });

  it("does not require a memo to ADD an entry, only to post it", () => {
    // p029's FIELDS table: Memo is `Required: To post`. A clerk composing five
    // rows gets the figures down first.
    expect(composerProblem({ ...good, memo: "" })).toBeNull();
    expect(batchProblem([{ ...good, memo: "", key: "k" }])).toBe("memo");
  });
});
