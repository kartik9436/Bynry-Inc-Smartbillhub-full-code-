// @vitest-environment jsdom
// DEF-CUS-10041 (PO 2026-10-11) — New request step 3's Payment details: the
// heading, Pay now / Pay later, and each method's own inputs (the table the PO
// accepted; decision log 2026-10-11).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import i18n from "@/i18n";

import {
  RequestPaymentDetails,
  changeDue,
  feeCollectionBody,
  paymentDetailsProblem,
  requiredPaymentFields,
} from "./RequestPaymentDetails";
import type { PaymentDetailsForm } from "./RequestPaymentDetails";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

const EMPTY: PaymentDetailsForm = {
  fee_timing: "",
  fee_method: "",
  fee_receipt_no: "",
  cash_received: "",
  card_last4: "",
  card_brand: "",
  card_auth_code: "",
  cheque_no: "",
  cheque_bank: "",
  cheque_date: "",
  ach_holder: "",
  ach_last4: "",
  ach_reference: "",
  money_order_no: "",
  money_order_issuer: "",
  wire_reference: "",
  wire_bank: "",
  wire_date: "",
};

const METHODS = ["ach", "card", "check", "cash", "lockbox", "wire", "money_order"];

function Harness() {
  const [form, setForm] = useState<PaymentDetailsForm>(EMPTY);
  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL) => {
      const path = new URL(String(input), "http://x").pathname.replace(/^\/api\/brazosbend/, "");
      const body =
        path === "/payments"
          ? {
              count: 0,
              next: null,
              previous: null,
              results: [],
              totals: {},
              methods: METHODS.map((code) => ({ id: code, code, name: code })),
            }
          : { count: 0, next: null, previous: null, results: [] };
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    },
  });
  return (
    <RequestPaymentDetails
      form={form}
      update={(patch) => setForm((previous) => ({ ...previous, ...patch }))}
      owing="45.0000"
      owingText="$45.00"
      client={client}
      timeZone="America/Chicago"
      dateFormat="MM/DD/YYYY"
      t={t}
    />
  );
}

function mount() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <Harness />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function payNowWith(method: string) {
  fireEvent.click(screen.getByRole("radio", { name: t("customers.serviceRequest.pay.now") }));
  const select = await waitFor(() => {
    const node = document.getElementById("fee_method") as HTMLSelectElement | null;
    if (node === null || node.options.length < 2) throw new Error("methods not loaded");
    return node;
  });
  fireEvent.change(select, { target: { value: method } });
}

const labelOf = (key: string) => screen.queryByLabelText(t(key), { exact: false });

describe("DEF-CUS-10041 · Payment details", () => {
  it("is titled Payment details and asks Pay now or Pay later first", () => {
    mount();
    expect(screen.getByText(t("customers.serviceRequest.pay.heading"))).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: t("customers.serviceRequest.pay.now") })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: t("customers.serviceRequest.pay.later") })).toBeInTheDocument();
    expect(document.getElementById("fee_method")).toBeNull();
  });

  it("Pay later asks for nothing", () => {
    mount();
    fireEvent.click(screen.getByRole("radio", { name: t("customers.serviceRequest.pay.later") }));
    expect(screen.getByText(t("customers.serviceRequest.pay.laterLine"))).toBeInTheDocument();
    expect(document.getElementById("fee_method")).toBeNull();
    expect(paymentDetailsProblem({ ...EMPTY, fee_timing: "collect_later" }, "45.0000")).toBeNull();
  });

  it("Pay now lists the utility's methods without Lockbox, and the amount is the fee, read-only", async () => {
    mount();
    await payNowWith("");
    const offered = Array.from((document.getElementById("fee_method") as HTMLSelectElement).options)
      .map((option) => option.value)
      .filter(Boolean);
    expect(offered).toEqual(["ach", "card", "check", "cash", "wire", "money_order"]);
    const amount = document.getElementById("fee_amount") as HTMLInputElement;
    expect(amount.value).toBe("$45.00");
    expect(amount).toHaveAttribute("readonly");
  });

  it.each([
    ["cash", ["customers.serviceRequest.pay.cashReceived", "customers.serviceRequest.pay.changeDue"]],
    ["check", ["customers.serviceRequest.capture.chequeNo", "customers.serviceRequest.capture.chequeBank", "customers.serviceRequest.capture.chequeDate"]],
    ["card", ["customers.serviceRequest.capture.cardBrand", "customers.serviceRequest.capture.cardLast4", "customers.serviceRequest.capture.cardAuthCode"]],
    ["ach", ["customers.serviceRequest.pay.achHolder", "customers.serviceRequest.pay.achLast4", "customers.serviceRequest.pay.achReference"]],
    ["money_order", ["customers.serviceRequest.pay.moNumber", "customers.serviceRequest.pay.moIssuer"]],
    ["wire", ["customers.serviceRequest.pay.wireReference", "customers.serviceRequest.pay.wireBank", "customers.serviceRequest.pay.wireDate"]],
  ])("%s asks for its own inputs and a receipt number", async (method, keys) => {
    mount();
    await payNowWith(method);
    for (const key of keys) {
      expect(labelOf(key)).not.toBeNull();
    }
    expect(labelOf("customers.serviceRequest.collect.receipt")).not.toBeNull();
    // …and not another method's: a card never shows a check number.
    if (method !== "check") {
      expect(labelOf("customers.serviceRequest.capture.chequeNo")).toBeNull();
    }
  });

  it("cash shows the change: $50.00 handed over on $45.00 is $5.00", async () => {
    mount();
    await payNowWith("cash");
    fireEvent.change(document.getElementById("cash_received") as HTMLInputElement, { target: { value: "50.00" } });
    expect((document.getElementById("cash_change") as HTMLInputElement).value).toBe("5.00");
  });

  it("Pay now refuses until the method's inputs and the receipt are given", () => {
    const now = { ...EMPTY, fee_timing: "collect_now", fee_method: "check" };
    expect(paymentDetailsProblem(now, "45.0000")).toBe("customers.serviceRequest.pay.detailsMissing");
    expect(
      paymentDetailsProblem(
        { ...now, cheque_no: "10241", cheque_bank: "First National", cheque_date: "2026-10-11", fee_receipt_no: "R-1" },
        "45.0000",
      ),
    ).toBeNull();
    expect(
      paymentDetailsProblem(
        { ...EMPTY, fee_timing: "collect_now", fee_method: "cash", cash_received: "40.00", fee_receipt_no: "R-1" },
        "45.0000",
      ),
    ).toBe("customers.serviceRequest.pay.receivedTooLittle");
    expect(requiredPaymentFields("cheque")).toEqual(requiredPaymentFields("check"));
  });

  it("the fee-collection body takes the whole fee, never the cash handed over", () => {
    expect(changeDue("50", "45.0000")).toBe("5.00");
    expect(
      feeCollectionBody(
        { ...EMPTY, fee_method: "cash", cash_received: "50.00", fee_receipt_no: "R-1" },
        "45.0000",
        "2026-10-11",
      ),
    ).toMatchObject({ amount: "45.0000", method: "cash", receipt_no: "R-1", posted_at: "2026-10-11" });
    expect(
      feeCollectionBody(
        { ...EMPTY, fee_method: "wire", wire_reference: "FW-88", wire_bank: "Chase", wire_date: "2026-10-10", fee_receipt_no: "R-2" },
        "45.0000",
        "2026-10-11",
      ),
    ).toMatchObject({ confirmation: "FW-88", memo: "Chase · 2026-10-10" });
  });
});
