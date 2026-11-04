// ── Trace ──────────────────────────────────────────────
// Change:  CR-087 task A2 / PRB-02 — the charge-code amount screen draws the
//          customer-class × connection-size GRID that task A1 made storable.
// Ruling:  The blueprint's PRB-02, from the PO's review of 2026-09-08: *"A
//          different deposit, connection fee or penalty could not be set for a
//          different class on one screen — the class was a list on the code and
//          the size a flat table, so the grid a utility actually prices in
//          could not be written."*
// Rules:   BR-RAT-690 (a per-size table IS the flat amount, once per size) ·
//          DEF-277 (three states kept apart: no row · a row with no amount · a
//          typed zero) · B14 rule 32 (a section gets one sentence).
// Note:    Written BEFORE the grid and shown RED — hard-won law 7.
// ───────────────────────────────────────────────────────
/**
 * **THE ACCEPTANCE CASE IS CR-087's OWN WORKED EXAMPLE, ON SCREEN:** one charge
 * code prices a 5/8" connection at **$45.00** for everybody and **$85.00** for
 * Commercial, and the screen shows both, side by side, on one row.
 *
 * ⚠ **THE THIRD STATE IS WHAT THIS FILE EXISTS TO PIN.** A cell a code says
 * nothing about must read *not served* and must NOT read `$0.00` — the two are
 * different facts and only one of them bills. `DEF-277` was filed for exactly
 * that collapse on the flat table, and a grid multiplies the number of cells
 * that can fall into it by the number of customer types.
 */
import { describe, expect, it } from "vitest";

import type { ChargeRow } from "@/api/endpoints";

import { presentCharge } from "./definitionDetail";

/** A code as the server serves it once A1's column is populated. */
function servedCharge(): ChargeRow {
  return {
    id: "chg-1",
    code: "CONN",
    name: "Connection fee",
    charge_type: "one_time",
    service: "water",
    amount_rule: "flat",
    amount: null,
    amount_display: null,
    percent: null,
    min_amount: null,
    max_amount: null,
    currency: "USD",
    taxable_default: false,
    auto_apply: false,
    waivable: false,
    separate_line: false,
    is_base: false,
    applies_to_customer_classes: [],
    size_amounts: [
      { size_class: "W-58", amount: "45.0000", amount_display: "45.00", currency: "USD", customer_class: null },
      { size_class: "W-58", amount: "85.0000", amount_display: "85.00", currency: "USD", customer_class: "commercial" },
    ],
  } as unknown as ChargeRow;
}

// CR-156-BRC10 wave B (2026-10-01): the "customer-class × size grid" block
// walked the OLD CHG-02 `PerSizeAmounts` grid, replaced by the rebuild from
// the 83 charge-code images (step 2 is one price column per the PO, class
// pricing a plan option). The new wizard's class rows are asserted in
// `chargeCodeWaveB.dom.test.tsx`.

/**
 * ⚠ **THE CODE'S OWN PAGE HAS TO STOP LYING ABOUT WHAT IT CARRIES.**
 *
 * The per-size line on a charge code's Overview counted ROWS. Once one size can
 * hold two rows — $45.00 for every customer type and $85.00 for Commercial — a
 * code priced for one size reported *"2 connection sizes listed"*, which is a
 * false statement about the tenant's own data. That line had already been
 * rewritten once for making a false statement (DEF-2190); this stops it making
 * the next one.
 *
 * And a code priced differently for Commercial must not look identical, on its
 * own page, to one that is not — the difference is money.
 */
describe("CR-087 A2 — the charge code's own page", () => {
  const t = ((key: string, params?: Record<string, unknown>) =>
    params === undefined ? key : `${key}:${JSON.stringify(params)}`) as never;

  it("counts connection SIZES, not rows", () => {
    const amounts = presentCharge(servedCharge(), t, []).panels.amounts;
    const perSize = amounts.find((f) => f.labelKey === "rating.definition.charge.perSize");
    // one size, priced — not two sizes, however many rows say so
    expect(String(perSize?.value)).toContain('"count":1');
    expect(String(perSize?.value)).toContain('"served":1');
  });

  it("says which customer types are priced separately", () => {
    const amounts = presentCharge(servedCharge(), t, []).panels.amounts;
    const perClass = amounts.find((f) => f.labelKey === "rating.definition.charge.perClass");
    expect(perClass).toBeDefined();
    expect(String(perClass?.value)).toBe("rating.customerClass.commercial");
  });

  it("says nothing at all when a code prices every type the same", () => {
    const plain = servedCharge();
    plain.size_amounts = [plain.size_amounts[0]];
    const amounts = presentCharge(plain, t, []).panels.amounts;
    expect(
      amounts.find((f) => f.labelKey === "rating.definition.charge.perClass"),
    ).toBeUndefined();
  });
});

// The plan summary card's "a plan's deposit names itself" cases (DEF-RAT-4676)
// were retired with `PlanSummaryCard.tsx` (CR-167-BRC10 round 3 task 8): a
// plan's deposits are now drawn by `planSections/PlanSections.tsx`, by code
// and name (`PlanSections.dom.test.tsx`).
