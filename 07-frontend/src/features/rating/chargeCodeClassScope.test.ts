// ── Trace ──────────────────────────────────────────────
// Defect: DEF-RAT-9176 — editing a seeded base code that applies to TWO
//         customer classes (BASE-W: residential + municipal) and saving with
//         only the amount changed posted `applies_to_customer_classes: []`.
//         The server reads an empty list as EVERY class, so the save collided
//         with BASE-W-COM ("BASE-W-COM already covers this class.") — or, with
//         no sibling, would have silently widened the code to every class.
// Introduced: 2.431.0 (CR-156-BRC10 wave B), whose single-select class field
//         had no value for a stored scope of more than one class.
// ───────────────────────────────────────────────────────
//
// ⚠ THE LOAD-BEARING CASE IS TWO CLASSES. Every test before this one edited a
// base code with zero or one class, and both of those round-tripped correctly
// under the defect. Only the two-class round trip goes red on the old code.
import { describe, expect, it } from "vitest";

import type { ChargeRow } from "@/api/endpoints";

import { STORED_CLASSES, chargePayload, draftFromCharge, emptyDraft, pricedByWords } from "./chargeCodeModel";

function base(classes: string[]): ChargeRow {
  return {
    id: "chg-basew",
    code: "BASE-W",
    name: "Water base charge — residential",
    charge_type: "recurring",
    service: "water",
    is_base: true,
    kind: "base",
    amount_rule: "flat",
    amount: "8.0000",
    amount_display: "8.00",
    percent: null,
    percent_display: null,
    min_amount: null,
    min_amount_display: null,
    max_amount: null,
    max_amount_display: null,
    taxable_default: true,
    auto_apply: true,
    waivable: false,
    separate_line: false,
    applies_to_customer_classes: classes,
    status: "active",
    gl_account_id: null,
    size_amounts: [],
    prices: [],
    price_range: null,
  } as unknown as ChargeRow;
}

/** Open the code on Edit, change ONLY the amount, and read what a save posts. */
function amountOnlySave(classes: string[]): unknown {
  const draft = draftFromCharge(base(classes), []);
  const edited = { ...draft, rows: draft.rows.map((row) => ({ ...row, amount: "9.00" })) };
  return chargePayload(edited, true).applies_to_customer_classes;
}

describe("an amount-only edit never changes a base code's class scope (DEF-RAT-9176)", () => {
  it("keeps an every-class base code every class", () => {
    expect(amountOnlySave([])).toEqual([]);
  });

  it("keeps a one-class base code on its one class", () => {
    expect(amountOnlySave(["commercial"])).toEqual(["commercial"]);
  });

  it("keeps a TWO-class base code on both of its classes, never [] (= every class)", () => {
    expect(amountOnlySave(["residential", "municipal"])).toEqual(["residential", "municipal"]);
  });

  it("still lets the clerk deliberately change a two-class code to all, or to one", () => {
    const draft = draftFromCharge(base(["residential", "municipal"]), []);
    expect(chargePayload({ ...draft, customerClass: "" }, true).applies_to_customer_classes).toEqual([]);
    expect(chargePayload({ ...draft, customerClass: "residential" }, true).applies_to_customer_classes).toEqual([
      "residential",
    ]);
  });

  it("reads a two-class code as neither 'Every class' nor 'One class'", () => {
    const draft = draftFromCharge(base(["residential", "municipal"]), []);
    expect(draft.customerClass).toBe(STORED_CLASSES);
    expect(pricedByWords(draft, null)).toEqual({ key: "rating.chargeCode.pricedBy.base.some", params: { count: 2 } });
  });

  it("never posts the stored-scope marker from Add, where nothing was stored", () => {
    const draft = { ...emptyDraft(), kind: "base" as const, customerClass: STORED_CLASSES };
    expect(chargePayload(draft, false).applies_to_customer_classes).toEqual([]);
  });
});
