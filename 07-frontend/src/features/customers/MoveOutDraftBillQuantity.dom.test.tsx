// @vitest-environment jsdom
// DEF-BIL-10095 — step 3 printed a prorated tier quantity at 28 places
// (`193.5483870967741935483870968 kWh`). A computed quantity shows at most 2
// decimals, trailing zeros dropped; the unit price keeps up to 4 and the amount 2.
import "@testing-library/jest-dom/vitest";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { DraftBill } from "./moveOutTables";
import type { FinalBillPreview } from "./moveShared";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function line(quantity: string, unitPrice: string, amount: string) {
  return {
    description: "Energy tier 1",
    amount,
    quantity,
    unit: "kWh",
    estimated: false,
    service: "electric",
    unitPrice,
    kind: "consumption",
  };
}

function preview(lines: ReturnType<typeof line>[]): FinalBillPreview {
  return {
    priced: true,
    lines,
    total: "29.29",
    subtotal: "29.29",
    taxTotal: "0.00",
    currency: "USD",
    periodStart: "2026-10-01",
    periodEnd: "2026-10-12",
    fromUncommittedReads: false,
    unavailable: null,
    unavailableDetail: null,
  } as unknown as FinalBillPreview;
}

describe("DEF-BIL-10095 · a computed quantity shows at most two places", () => {
  it("rounds the prorated tier share and keeps the rate's four places", () => {
    render(
      <DraftBill
        preview={preview([
          line("193.5483870967741935483870968", "0.1125", "21.77"),
          line("50.000000", "0.0425", "2.13"),
        ])}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        t={t}
      />,
    );
    const text = document.body.textContent ?? "";
    expect(text).toContain("193.55 kWh");
    expect(text).not.toContain("193.548");
    expect(text).toContain("50 kWh");
    expect(text).toContain("$0.1125");
    expect(text).toContain("$0.0425");
  });
});
