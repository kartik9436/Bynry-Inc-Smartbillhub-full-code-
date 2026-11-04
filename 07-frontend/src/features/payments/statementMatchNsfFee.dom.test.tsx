// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-PAY-10766 (W2) — the statement's Match to payment form shows
//           the NSF fee before Match ✓, as the Reverse dialog does
// Ruling:   decision log 2026-10-30 "Final-walk questions W1–W4 answered (PO)"
//           — *"W2-A"*
// ───────────────────────────────────────────────────────
// The tester's line RET1029-02, −$154.00, is cheque 4103, not reversed yet. On
// a plan whose NSF fee is $30.00 the form reads "+$30.00 NSF fee" before the
// clerk presses Match ✓; on a plan with none it says so — never "$0.00".
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { NsfFeeQuote } from "@/api/endpoints";
import i18n from "@/i18n";

import { MatchReturnForm } from "./StatementLineActions";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const CANDIDATE = {
  payment_id: "pay-4103",
  payment_no: "PY-2026-0103",
  cheque: "4103",
  account_id: "acc-2",
  account_no: "AC-2026-00002",
  amount: "154.000000",
  posted_on: "2026-10-26",
  already_reversed: false,
  reversal_id: null,
  reversed_on: null,
  reference_match: true,
};

function mount(quote: NsfFeeQuote) {
  const get = vi.fn().mockImplementation((path: string) =>
    Promise.resolve({ data: path.includes("/nsf-fee") ? quote : { rows: [CANDIDATE] } }),
  );
  const client = { get, post: vi.fn() } as unknown as ApiClient;
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queries}>
      <MatchReturnForm
        line={{
          bank_line_id: "l-ret2",
          reference: "RET1029-02",
          posted_on: "2026-10-29",
          amount: "-154.000000",
        }}
        currency="USD"
        client={client}
        onClose={() => undefined}
        onDone={() => undefined}
      />
    </QueryClientProvider>,
  );
  return get;
}

async function pickTheCheque() {
  await screen.findByRole("option", { name: /4103/ });
  const select = document.getElementById("payment_id") as HTMLSelectElement;
  fireEvent.change(select, { target: { value: "pay-4103" } });
}

describe("W2 — the NSF fee is shown before Match ✓", () => {
  it("says +$30.00 NSF fee, priced on the bank's return date", async () => {
    const get = mount({ status: "charged", code: "NSF", amount: "30.0000", currency: "USD" });
    expect(screen.queryByText(/NSF fee$/)).toBeNull();
    await pickTheCheque();
    expect(await screen.findByText("+$30.00 NSF fee")).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith("/payments/pay-4103/nsf-fee?on=2026-10-29");
  });

  it("says the plan has no NSF fee rather than $0.00", async () => {
    mount({ status: "nsf_fee_not_set_on_plan", code: null, amount: null, currency: "USD" });
    await pickTheCheque();
    expect(await screen.findByText(t("payments.reverse.nsfFee.notSet"))).toBeInTheDocument();
    expect(screen.queryByText(/\$0\.00/)).toBeNull();
  });
});
