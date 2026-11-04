// DEF-CUS-9819 (PO 2026-10-06) — the charge-code form marks the utility's
// application fee, and a $0.00 price is posted as a price, never as "no price".
import { describe, expect, it } from "vitest";

import { chargePayload, emptyDraft } from "./chargeCodeModel";

function oneTime(amount: string, applicationFee: boolean) {
  const draft = emptyDraft();
  return {
    ...draft,
    kind: "other" as const,
    code: "APP-FEE",
    name: "Application fee",
    chargeType: "one_time",
    pricedBy: "one" as const,
    applicationFee,
    effectiveFrom: "2026-10-06",
    rows: [{ ...draft.rows[0], amount }],
  };
}

describe("DEF-CUS-9819 · Application fee on the charge-code form", () => {
  it("posts the mark on a one-time code, with a $0.00 price as 0.00", () => {
    const payload = chargePayload(oneTime("0.00", true), false);
    expect(payload.is_application_fee).toBe(true);
    expect(payload.amount).toBe("0.00");
  });

  it("never posts the mark on a code that is not one-time", () => {
    const payload = chargePayload({ ...oneTime("3.00", true), chargeType: "recurring" }, false);
    expect(payload.is_application_fee).toBe(false);
  });
});
