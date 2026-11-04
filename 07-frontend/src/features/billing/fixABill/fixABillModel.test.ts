// ── Trace ──────────────────────────────────────────────
// Change:  CR-180-BRC10 — the Fix a bill model (pure)
// Rulings: decision log 2026-10-12 *FIX A BILL REVAMP* items 1–3, 7, 10, 11
// Rules:   BR-BIL-042 (the strongest class wins, R > C > D) · BR-BIL-014
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import {
  CATALOG,
  ACCOUNT_ID,
  BILL_AUG,
  BILL_OCT,
  BILL_SEP,
  PLAN_ID,
} from "./__fixtures__/fixABillFixtures";
import {
  EMPTY_BILLS_FORM,
  REASON_ORDER,
  billsRefusalKey,
  chooseOption,
  chooseSub,
  itemsOf,
  newRow,
  reasonsFor,
  rowComplete,
  scopeOf,
  signOf,
  strongestClass,
  togglePicked,
} from "./fixABillModel";

const THREE = [BILL_AUG, BILL_SEP, BILL_OCT];

describe("step 1 · two options, four sub-options, unique and with no overlap", () => {
  it("the sub-option list depends on the option", () => {
    const bulk = chooseOption(EMPTY_BILLS_FORM, "bulk");
    expect(bulk.sub).toBe("run");
    expect(chooseOption(bulk, "one").sub).toBe("one_bill");
  });

  it("one bill is a radio; several months is ticks", () => {
    let form = { ...EMPTY_BILLS_FORM, accountId: ACCOUNT_ID };
    form = togglePicked(form, BILL_AUG);
    form = togglePicked(form, BILL_OCT);
    expect(form.pickedIds).toEqual([BILL_OCT]);
    form = chooseSub(form, "several");
    form = togglePicked(form, BILL_AUG);
    form = togglePicked(form, BILL_SEP);
    expect(form.pickedIds).toEqual([BILL_OCT, BILL_AUG, BILL_SEP]);
    form = togglePicked(form, BILL_AUG);
    expect(form.pickedIds).toEqual([BILL_OCT, BILL_SEP]);
  });

  it("the scope is the contract's: account + invoice_ids · run (+ part) · price mistake", () => {
    expect(scopeOf({ ...EMPTY_BILLS_FORM, accountId: ACCOUNT_ID }, false)).toEqual({
      scope_kind: "account",
      account_id: ACCOUNT_ID,
    });
    expect(scopeOf({ ...EMPTY_BILLS_FORM, accountId: ACCOUNT_ID, pickedIds: [BILL_OCT] })).toEqual({
      scope_kind: "account",
      account_id: ACCOUNT_ID,
      invoice_ids: [BILL_OCT],
    });
    const run = {
      ...chooseOption(EMPTY_BILLS_FORM, "bulk"),
      runId: "r1",
      runPart: "service:water",
    };
    expect(scopeOf(run)).toEqual({ scope_kind: "run", bill_run_id: "r1", service_code: "water" });
    const price = {
      ...chooseSub(chooseOption(EMPTY_BILLS_FORM, "bulk"), "price_mistake"),
      from: "2026-08-01",
      to: "2026-09-30",
      target: "rate:tier-w2",
    };
    expect(scopeOf(price)).toEqual({
      scope_kind: "price_mistake",
      period_start: "2026-08-01",
      period_end: "2026-09-30",
      wrong_kind: "rate",
      wrong_id: "tier-w2",
    });
    expect(billsRefusalKey({ ...price, to: "2026-07-01" })).toBe(
      "billing.fixBill.refuse.datesOrder",
    );
  });
});

describe("step 2 · every reason is a row type, filtered by option", () => {
  it("one customer offers all sixteen, in the drawn order", () => {
    expect(reasonsFor("one_bill", CATALOG)).toEqual([...REASON_ORDER]);
    expect(REASON_ORDER).toHaveLength(16);
  });

  it("a run offers the seven bulk reasons; a price mistake the same without the reprint", () => {
    expect(reasonsFor("run", CATALOG)).toEqual([
      "wrong_plan",
      "wrong_rate",
      "wrong_tax",
      "missed_charge",
      "charge_billed_in_error",
      "wrong_discount",
      "template_or_language",
    ]);
    expect(reasonsFor("price_mistake", CATALOG)).not.toContain("template_or_language");
    expect(reasonsFor("price_mistake", CATALOG)).not.toContain("goodwill");
  });

  it("a reason the server does not serve is not offered", () => {
    const narrow = {
      ...CATALOG,
      reasons: CATALOG.reasons.filter((r) => r.code !== "wrong_deposit"),
    };
    expect(reasonsFor("one_bill", narrow)).not.toContain("wrong_deposit");
  });

  it("strongest wins: R > C > D, across every row", () => {
    expect(strongestClass([], CATALOG)).toBeNull();
    expect(strongestClass([{ reason: "customer_name" }], CATALOG)).toBe("document");
    expect(strongestClass([{ reason: "customer_name" }, { reason: "goodwill" }], CATALOG)).toBe(
      "credit_only",
    );
    expect(
      strongestClass(
        [{ reason: "goodwill" }, { reason: "wrong_read" }, { reason: "customer_name" }],
        CATALOG,
      ),
    ).toBe("restatement");
  });

  it("a new row preloads what it can; goodwill starts on the last month only", () => {
    const defaults = {
      billIds: THREE,
      bulk: false,
      billed: { plan_id: PLAN_ID, deposit: "0.0000" },
    };
    expect(newRow("wrong_plan", defaults).item).toBe(PLAN_ID);
    expect(newRow("missed_charge", defaults)).toMatchObject({ act: "add", value: "1" });
    expect(newRow("charge_billed_in_error", defaults).act).toBe("remove");
    expect(newRow("wrong_read", defaults).applyTo).toEqual(THREE);
    expect(newRow("goodwill", defaults).applyTo).toEqual([BILL_OCT]);
    expect(newRow("wrong_rate", { billIds: [], bulk: true }).applyTo).toBeNull();
  });

  it("a half-typed row is not sent; a row on every bill is sent as bill_ids null", () => {
    const defaults = { billIds: THREE, bulk: false };
    const reading = { ...newRow("wrong_read", defaults), item: "m1", value: "1162.4" };
    const goodwill = { ...newRow("goodwill", defaults), value: "25.00" };
    const half = newRow("wrong_tax", defaults);
    expect(rowComplete(half)).toBe(false);
    expect(rowComplete({ ...reading, applyTo: [] })).toBe(false);
    expect(itemsOf([reading, goodwill, half], THREE)).toEqual([
      { reason: "wrong_read", item: "m1", value: "1162.4", bill_ids: null },
      { reason: "goodwill", item: "credit", value: "25.00", bill_ids: [BILL_OCT] },
    ]);
  });

  it("reads a sign off the string, never a float", () => {
    expect(signOf("18.7400")).toBe("up");
    expect(signOf("-11.3800")).toBe("down");
    expect(signOf("0.0000")).toBe("flat");
    expect(signOf(null)).toBe("flat");
  });
});

// DEF-BIL-10079 — a bill that falls tells the clerk the customer owes less; it
// never promises money back, which is the Refund row's fact alone (walked on
// BL-2610-000053: $198.90 → $183.60, nothing paid, Refund "No").
import en from "@/i18n/locales/en.json";
describe("Check band for a falling bill", () => {
  it("says the customer owes less, never that money goes back", () => {
    const words = (en as Record<string, string>)["billing.fixBill.check.asks.down"];
    expect(words).toBe("The customer owes less.");
    expect(words.toLowerCase()).not.toContain("back");
  });
});
