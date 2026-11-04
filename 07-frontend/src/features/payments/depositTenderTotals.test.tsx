// ── Trace ──────────────────────────────────────────────
// Change:   CR-186-BRC10 (lane PAY-CORE) — one batch per till or provider per
//           day, all tenders, with a total per tender (PO 2026-10-21).
// Screens:  S37 (Deposits list — the owner cell) · S39 (batch — Totals by tender)
// ───────────────────────────────────────────────────────
// Dana · 14 Oct: cash $300.00 + cheques $500.00 = ONE batch of $800.00. The
// figures are the engine's (`reconciliation.tender_totals`), copied, never summed.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { DepositBatchDetail } from "@/api/bankRecEndpoints";

import { TenderTotalsPanel } from "./DepositBatchPage";
import { depositOwnerLabel } from "./depositsShared";

const t = i18n.t.bind(i18n);

function detail(overrides: Partial<DepositBatchDetail["batch"]> = {}): DepositBatchDetail {
  return {
    batch: {
      id: "b1",
      code: "DEP-261014-0001",
      method_code: null,
      method_name: null,
      all_tenders: true,
      channel: null,
      deposited_on: "2026-10-14",
      recorded_total: "800.000000",
      bank_total: null,
      difference: null,
      currency: "USD",
      payment_count: 3,
      status: "in_transit",
      locked: false,
      ...overrides,
    },
    live_total: "800.000000",
    tender_totals: [
      { method_code: "cash", method_name: "Cash", amount: "300.000000", count: 1 },
      { method_code: "check", method_name: "Check", amount: "500.000000", count: 2 },
    ],
    members: [],
    bank_line: null,
    trail: [],
    resolutions: [],
    unavailable: [],
  };
}

describe("CR-186-BRC10 · a batch carries a total per tender", () => {
  it("draws Dana's cash and cheques as two tender rows of one batch", () => {
    const html = renderToStaticMarkup(<TenderTotalsPanel detail={detail()} t={t} locale="en-US" />);
    expect(html).toContain("Totals by tender");
    expect(html).toContain("Cash");
    expect(html).toContain("$300.00");
    expect(html).toContain("Check");
    expect(html).toContain("$500.00");
  });

  it("draws nothing for a batch banked before the change (one tender)", () => {
    const html = renderToStaticMarkup(
      <TenderTotalsPanel
        detail={detail({ all_tenders: false, method_code: "check", method_name: "Check" })}
        t={t}
      />,
    );
    expect(html).toBe("");
  });
});

describe("CR-186-BRC10 · whose deposit an all-tenders batch is", () => {
  it("names a person's till, our two channels, and a provider by its own name", () => {
    expect(depositOwnerLabel(null, t)).toBe("All tenders");
    expect(depositOwnerLabel("office", t)).toBe("Office");
    expect(depositOwnerLabel("lockbox", t)).toBe("Lockbox");
    expect(depositOwnerLabel("invoice_cloud", t)).toBe("Invoice Cloud");
    expect(depositOwnerLabel("paymentus", t)).toBe("Paymentus");
  });

  it("Q6 — a store network's own batch reads Store · Hy-Vee, not Store:hy-vee", () => {
    expect(depositOwnerLabel("store:hy-vee", t)).toBe("Store · Hy-Vee");
    expect(depositOwnerLabel("store:checkfreepay", t)).toBe("Store · Checkfreepay");
  });
});
