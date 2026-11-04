// ── Trace ──────────────────────────────────────────────
// Defect: DEF-RAT-9209 — the charge-code Edit wizard's *What changes* summary
//         never listed a change of customer class, so a base code's SCOPE
//         could be changed (BASE-W residential + municipal → commercial) and
//         committed without the review step showing it.
// Introduced: 2.431.0 (CR-156-BRC10 wave B), whose `draftChanges` compared
//         the bill line, the type, the four yes/no settings and the prices,
//         and nothing else.
// ───────────────────────────────────────────────────────
//
// ⚠ THE SECOND BLOCK IS THE PREVENTION, NOT DECORATION: it changes every
// field the Edit form lets a clerk change, one at a time, and asserts the
// summary names it. A field added to the form and not to the summary goes red
// here instead of being committed unseen.
import { describe, expect, it } from "vitest";

import type { ChargeRow } from "@/api/endpoints";

import { STORED_CLASSES, type ChargeCodeDraft, draftChanges, draftFromCharge } from "./chargeCodeModel";

const NAMES: Record<string, string> = {
  residential: "Residential",
  municipal: "Municipal",
  commercial: "Commercial",
};

const WORDS = {
  field: (key: string) => `field:${key}`,
  yesNo: (value: boolean) => (value ? "Yes" : "No"),
  type: (value: string) => `type:${value}`,
  money: (value: string) => `$${value}`,
  notPriced: "Not priced",
  priceItem: () => "price",
  classes: (codes: string[]) => (codes.length === 0 ? "All classes" : codes.map((code) => NAMES[code] ?? code).join(", ")),
};

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

const classRow = (before: ChargeCodeDraft, after: ChargeCodeDraft) =>
  draftChanges(before, after, WORDS).find((row) => row.item === "field:customerClass");

describe("Edit's What changes names a change of customer class (DEF-RAT-9209)", () => {
  it("two stored classes to one: old and new scope, in class names", () => {
    const before = draftFromCharge(base(["residential", "municipal"]), []);
    expect(before.customerClass).toBe(STORED_CLASSES);
    const row = classRow(before, { ...before, customerClass: "commercial" });
    expect(row).toEqual({ item: "field:customerClass", now: "Residential, Municipal", next: "Commercial" });
  });

  it("one class to every class", () => {
    const before = draftFromCharge(base(["residential"]), []);
    expect(classRow(before, { ...before, customerClass: "" })).toEqual({
      item: "field:customerClass",
      now: "Residential",
      next: "All classes",
    });
  });

  it("an untouched scope is not a change, whatever its shape", () => {
    for (const classes of [[], ["residential"], ["residential", "municipal"]]) {
      const before = draftFromCharge(base(classes), []);
      expect(classRow(before, { ...before, rows: before.rows.map((r) => ({ ...r, amount: "9.00" })) })).toBeUndefined();
    }
  });
});

describe("every field the Edit form can change appears in What changes", () => {
  const before = draftFromCharge(base(["residential"]), []);
  const edits: [string, Partial<ChargeCodeDraft>][] = [
    ["field:billLine", { name: "Water base" }],
    ["field:type", { chargeType: "one_time" }],
    ["field:customerClass", { customerClass: "commercial" }],
    ["field:taxed", { taxable: !before.taxable }],
    ["field:auto", { autoApply: !before.autoApply }],
    ["field:waive", { waivable: !before.waivable }],
    ["field:ownLine", { separateLine: !before.separateLine }],
    ["price", { rows: before.rows.map((row) => ({ ...row, amount: "9.00" })) }],
  ];
  for (const [item, edit] of edits) {
    it(`names ${item}`, () => {
      const items = draftChanges(before, { ...before, ...edit }, WORDS).map((row) => row.item);
      expect(items).toContain(item);
    });
  }

  it("names nothing when nothing changed", () => {
    expect(draftChanges(before, { ...before }, WORDS)).toEqual([]);
  });
});
