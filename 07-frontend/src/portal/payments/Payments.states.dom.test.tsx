// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Defect:   DEF-CWP-10341 — portal payment words did not follow CR-186's
//           lifecycle (posted at entry, cleared on bank reconciliation,
//           cancelled only from posted)
// Story:    US-CWP-048 (EP-CWP-09) · Screen: CWP-041
// Rules:    B14 rule 35 (the catalogue writes the words) · BR-CWP-061 (only a
//           bounce reads *returned by the bank*)
// Cases:    every state the server sends draws its own word · an unknown state
//           draws *Status unavailable* and never a raw key · a cancel pair is
//           two muted *Canceled* rows with no bank sentence
// Why its   A separate path so no sibling editing `Payments.dom.test.tsx`
// own file: collides with it (hard-won law 11).
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalMoney, PortalMoneyRow } from "../api/portalClient";

let money: PortalMoneyRow[] = [];
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getMoneyList: async (): Promise<PortalMoney> => ({
      money,
      count: money.length,
      page: 1,
      per: 50,
      populated: money.length > 0,
    }),
  };
});

const { PaymentsView, moneyState } = await import("./Payments");

const PAYMENT: PortalMoneyRow = {
  kind: "payment",
  date: "2026-10-20",
  how: "Card",
  reference: "PMT-26-10001",
  receipt_reference: "PMT-26-10001",
  receipt_available: false,
  applied_to: ["BL-2609-0150"],
  returned_by_the_bank: false,
  amount: "129.0200",
  currency: "USD",
  state: "received",
  money_type: "payment",
};

function draw(rows: PortalMoneyRow[]) {
  money = rows;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/payments"]}>
      <Routes>
        <Route path="/:tenant/portal/payments" element={<PaymentsView />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("moneyState — the chip never borrows a word (DEF-CWP-10341)", () => {
  it("passes every state the server sends", () => {
    for (const state of [
      "received",
      "processing",
      "failed",
      "cancelled",
      "unknown",
      "bounced",
      "reversed",
      "credited",
      "written_off",
      "write_off_reversed",
    ]) {
      expect(moneyState(state)).toBe(state);
    }
  });

  it("an unrecognised state, and the retired `cleared`, read `unknown`", () => {
    expect(moneyState("cleared")).toBe("unknown");
    expect(moneyState("posted")).toBe("unknown");
    expect(moneyState("something_new")).toBe("unknown");
    expect(moneyState("toString")).toBe("unknown");
  });
});

describe("CWP-041 · the words a customer reads per state", () => {
  it.each([
    ["received", "Received"],
    ["processing", "Processing"],
    ["failed", "Failed"],
    ["cancelled", "Canceled"],
  ] as const)("%s reads %s", async (state, word) => {
    const { container } = draw([{ ...PAYMENT, state }]);
    await screen.findByRole("table");
    expect(container.querySelector("[data-money-card='0']")?.textContent).toContain(word);
  });

  it("an unknown state reads Status unavailable, never a key", async () => {
    const odd = { ...PAYMENT, state: "something_new" } as unknown as PortalMoneyRow;
    const { container } = draw([odd]);
    await screen.findByRole("table");
    const card = container.querySelector("[data-money-card='0']")?.textContent ?? "";
    expect(card).toContain("Status unavailable");
    expect(card).not.toContain("portal.money.state");
  });

  it("a cancel is two muted Canceled rows and no bank sentence", async () => {
    const reversing: PortalMoneyRow = {
      ...PAYMENT,
      kind: "reversal",
      reference: "PMT-26-10002",
      receipt_reference: null,
      applied_to: [],
      amount: "-129.0200",
      state: "cancelled",
    };
    const original: PortalMoneyRow = { ...PAYMENT, state: "cancelled" };
    const { container } = draw([reversing, original]);
    await screen.findByRole("table");

    const cards = [...container.querySelectorAll("[data-money-card]")];
    expect(cards).toHaveLength(2);
    for (const card of cards) {
      expect(card.textContent).toContain("Canceled");
      expect(card.className).toContain("text-neutral-600"); // Group A F-01: muted text is grey-600, never grey-500
    }
    expect(container.textContent).not.toContain("Returned by the bank");
    expect(container.textContent).not.toContain("Bounced");
    expect(container.querySelector("[data-reversal]")).toBeNull();
  });
});
