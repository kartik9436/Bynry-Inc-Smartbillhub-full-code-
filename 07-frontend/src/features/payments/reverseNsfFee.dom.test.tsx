// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-PAY-10698 (the NSF penalty before Confirm, the untick with a
//           reason) · DEF-PAY-10699 (LBX-04 — "Bank memo", one per payment)
// Ruling:   PO 2026-10-30 (decision log, three rows that day)
// Screens:  S35 Reverse (single) · the Payments list's bulk Reverse · 2·2
// ───────────────────────────────────────────────────────
// The PO's own figures: cheque 4102 $76.40 on a plan whose NSF is $30.00 —
// the dialog says "+$30.00 NSF fee" BEFORE Confirm; PY-…-0098 Bank memo "NSF"
// and 4103 "ACCOUNT CLOSED" in one bulk run, each sent on its own payment.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { NsfFeeQuote, PaymentRow } from "@/api/endpoints";
import i18n from "@/i18n";

import { bounceLines } from "./paymentDetailShared";
import { bulkReverseSchema, reverseOne } from "./paymentsBulk";
import { BulkNsfFeeTable, nsfFeeText } from "./reverseNsfFee";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

function row(id: string, payment_no: string): PaymentRow {
  return {
    id,
    payment_no,
    account_id: "acc-3",
    account_no: "AC-2026-00003",
    customer_name: "Carl",
    type: "payment",
    method: "check",
    method_name: "Cheque",
    confirmation: payment_no,
    memo: null,
    amount: "76.400000",
    currency: "USD",
    status: "cleared",
    purpose: "bill",
    posted_at: "2026-10-20",
    cleared_at: "2026-10-21",
    applied_to: [],
    applied_total: "76.400000",
    deposit_batch_id: null,
    receipt_no: null,
    cheque_date: null,
    drawer_bank: null,
    bankable_from: null,
    moved_from_payment_no: null,
    moved_from_account_no: null,
    moved_to_payment_no: null,
    moved_to_account_no: null,
    origin: "entry",
    batch_ref: null,
    batch_kind: null,
  } as PaymentRow;
}

const CHARGED: NsfFeeQuote = { status: "charged", code: "NSF", amount: "30.0000", currency: "USD" };
const NOT_SET: NsfFeeQuote = {
  status: "nsf_fee_not_set_on_plan",
  code: null,
  amount: null,
  currency: "USD",
};

describe("DEF-PAY-10698 — the NSF fee before Confirm", () => {
  it("says +$30.00 NSF fee, or that the plan sets none — never $0.00", () => {
    expect(nsfFeeText(CHARGED, t)).toBe(t("payments.reverse.nsfFee.charged", { amount: "$30.00" }));
    expect(nsfFeeText(CHARGED, t)).toContain("$30.00");
    expect(nsfFeeText(NOT_SET, t)).toBe(t("payments.reverse.nsfFee.notSet"));
    expect(nsfFeeText(NOT_SET, t)).not.toContain("0.00");
  });

  it("shows each payment's own fee in the bulk table, from the server's quote", async () => {
    const get = vi.fn().mockImplementation((path: string) =>
      Promise.resolve({ data: path.includes("pay-0098") ? CHARGED : NOT_SET }),
    );
    const client = { get, post: vi.fn() } as unknown as ApiClient;
    const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queries}>
        <BulkNsfFeeTable
          rows={[row("pay-0098", "4102"), row("pay-0099", "4103")]}
          reason="nsf"
          returnedOn="2026-10-26"
          client={client}
          chargeFee
          memos={{}}
          onMemo={() => undefined}
          label={(r) => r.payment_no ?? ""}
        />
      </QueryClientProvider>,
    );
    expect(await screen.findByText(nsfFeeText(CHARGED, t))).toBeInTheDocument();
    expect(await screen.findByText(t("payments.reverse.nsfFee.notSet"))).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("/payments/pay-0098/nsf-fee?on=2026-10-26");
    expect(screen.getAllByLabelText(t("payments.reverse.bankMemo"))).toHaveLength(2);
  });

  it("refuses an unticked fee with no reason, and a Bank memo over 60", () => {
    const schema = bulkReverseSchema(t);
    expect(
      schema.safeParse({ returned_on: "2026-10-26", charge_nsf_fee: false, nsf_fee_waive_reason: " " })
        .success,
    ).toBe(false);
    expect(
      schema.safeParse({
        returned_on: "2026-10-26",
        charge_nsf_fee: false,
        nsf_fee_waive_reason: "bank error",
      }).success,
    ).toBe(true);
    expect(
      schema.safeParse({ returned_on: "2026-10-26", bank_memos: { p: "X".repeat(61) } }).success,
    ).toBe(false);
  });
});

describe("DEF-PAY-10699 — the Bank memo, one per payment", () => {
  it("sends each payment its own memo, and the fee choice", async () => {
    const post = vi.fn().mockResolvedValue({ data: {} });
    const client = { get: vi.fn(), post } as unknown as ApiClient;
    const memos = { "pay-0098": " NSF ", "pay-0099": "ACCOUNT CLOSED" };
    const body = { reason: "nsf" as const, returnedOn: "2026-10-26", resumeCollections: false };
    await reverseOne(row("pay-0098", "4102"), { ...body, bankMemos: memos }, "k1", client);
    await reverseOne(
      row("pay-0099", "4103"),
      { ...body, bankMemos: memos, chargeNsfFee: false, nsfFeeWaiveReason: "bank error" },
      "k2",
      client,
    );
    expect(post.mock.calls[0][1]).toMatchObject({
      bank_memo: "NSF",
      charge_nsf_fee: true,
      nsf_fee_waive_reason: null,
    });
    expect(post.mock.calls[1][1]).toMatchObject({
      bank_memo: "ACCOUNT CLOSED",
      charge_nsf_fee: false,
      nsf_fee_waive_reason: "bank error",
    });
  });

  it("reads Bank memo: NSF and the fee on the payment and its history", () => {
    expect(
      bounceLines(
        { bank_memo: "NSF", nsf_fee_status: "charged", nsf_fee_amount: "30.0000", nsf_fee_currency: "USD" },
        t,
      ),
    ).toEqual([
      t("payments.reverse.bankMemoLine", { memo: "NSF" }),
      t("payments.reverse.nsfFee.charged", { amount: "$30.00" }),
    ]);
    expect(bounceLines({ nsf_fee_waived_reason: "bank error" }, t)).toEqual([
      t("payments.reverse.nsfFee.waived", { reason: "bank error" }),
    ]);
  });
});
