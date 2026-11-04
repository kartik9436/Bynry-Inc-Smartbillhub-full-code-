// @vitest-environment jsdom
// DEF-CUS-10053 (PO 2026-10-11: "show me all option dont drop it") — every
// deposit option stays drawn and the one the account's figures land on is
// highlighted with its amount.
import "@testing-library/jest-dom/vitest";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { DepositDisposition } from "./moveShared";
import type { MoneyLanding, SettlementMoney } from "./moveShared";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const m = (stored: string | null) => ({ stored, display: stored });

function money(over: Partial<SettlementMoney> = {}): SettlementMoney {
  const zero = m("0.0000");
  return {
    currency: "USD",
    priorBalance: zero,
    finalBill: zero,
    exportCredit: zero,
    finalBillNet: zero,
    outstanding: zero,
    depositHeld: m("150.0000"),
    depositInterest: zero,
    unappliedCredit: zero,
    applied: zero,
    net: zero,
    shortfall: zero,
    excess: zero,
    settledFromDeposit: zero,
    refundAmount: zero,
    ...over,
  } as SettlementMoney;
}

function mount(landing: MoneyLanding | null, over: Partial<SettlementMoney> = {}) {
  render(
    <DepositDisposition
      money={money(over)}
      landing={landing}
      movedOutOn="2026-10-14"
      depositOnFile="150.0000"
      currency="USD"
      timeZone="America/Chicago"
      dateFormat="MM/DD/YYYY"
      t={t}
    />,
  );
}

const card = (tracks: string) => document.querySelector(`[data-deposit-option="${tracks}"]`) as HTMLElement | null;

describe("DEF-CUS-10053 · the deposit options", () => {
  it("before the bill is priced: all options drawn and one pending line", () => {
    mount(null);
    for (const tracks of ["apply", "refund", "hold", "transfer"]) expect(card(tracks)).not.toBeNull();
    expect(document.querySelector("[data-deposit-pending]")).not.toBeNull();
  });

  it("a refund landing highlights Refund with its amount", () => {
    mount("refund_due", { refundAmount: m("59.0500") });
    expect(card("refund")?.textContent).toContain("59.05");
    expect(card("refund")?.getAttribute("data-selected")).toBe("yes");
    expect(card("hold")?.getAttribute("data-selected")).toBe("no");
    expect(document.querySelector("[data-deposit-pending]")).toBeNull();
    expect(card("hold")).not.toBeNull();
    expect(card("transfer")).not.toBeNull();
  });

  it("an excess under dispute highlights Hold with its amount", () => {
    mount("refused_excess", { excess: m("13.1200") });
    expect(card("hold")?.textContent).toContain("13.12");
    expect(card("hold")?.getAttribute("data-selected")).toBe("yes");
  });
});
