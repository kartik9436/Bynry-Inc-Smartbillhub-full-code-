// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9775 — M5 MVI-26-0007's Billing tab read "Tax: Taxed" for a
//          church whose move-in recorded certificate CF-REL-2026-0412 against
//          the City's tax. Ruling (A) (DEF-CUS-9724) leaves the account's
//          blanket flag false, so the cell reads the certificate itself.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BillingTab } from "./BillingTab";

afterEach(cleanup);

const fact = (value: unknown = null) => ({ value, unavailable: null });

const record = {
  facts: { details: { account: { id: "acc-57", account_no: "AC-2026-00057" }, plan: null } },
  tiles: { fees: { total: "325.0000", currency: "USD", lines: 2, paid: null, unavailable: null } },
  fee_lines: [],
  money_taken: {
    required: fact("300.0000"),
    taken: fact("300.0000"),
    taken_on: null,
    awaiting_clearance: fact(null),
    still_to_collect: fact("0.0000"),
    tender: fact(),
    currency: "USD",
  },
  still_owed: { demand_register: fact(), visit: fact(), carry_forward: fact() },
};

const CERT = {
  id: "cert-1",
  certificate_ref: "CF-REL-2026-0412",
  issued_on: "2026-01-15",
  expires_on: "2028-12-31",
  state: "live",
  tax_id: "tax-city",
  tax_name: "City of Cedar Ford utility tax",
  category_name: "Religious",
};

function mount(account: Record<string, unknown>) {
  const get = vi.fn(async (url: string) =>
    url.startsWith("/accounts/")
      ? { status: 200, data: { id: "acc-57", tax_exempt_ref: null, tax_exempt_expires: null, ...account } }
      : {
          status: 200,
          data: { count: 0, next: null, previous: null, results: [], totals: { amount: null, currency: "USD" } },
        },
  );
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <BillingTab
        record={record as never}
        regional={{ timeZone: "UTC", dateFormat: "MM/DD/YYYY" }}
        client={{ get } as never}
      />
    </QueryClientProvider>,
  );
}

describe("DEF-CUS-9775 — the move's Tax cell names the certificate", () => {
  it("reads Exempt from the certificate's tax, its number and its expiry", async () => {
    mount({ tax_exempt: false, tax_exemptions: [CERT] });
    expect(await screen.findByText(/Exempt from City of Cedar Ford utility tax · CF-REL-2026-0412/)).toBeInTheDocument();
    expect(screen.getByText("12/31/2028")).toBeInTheDocument();
    expect(screen.queryByText("Taxed")).toBeNull();
  });

  it("an expired certificate exempts nothing: Taxed", async () => {
    mount({ tax_exempt: false, tax_exemptions: [{ ...CERT, state: "expired" }] });
    expect(await screen.findByText("Taxed")).toBeInTheDocument();
  });

  it("the blanket exemption still reads Exempt", async () => {
    mount({ tax_exempt: true, tax_exempt_ref: "TX-EX-1", tax_exemptions: [] });
    expect(await screen.findByText(/^Exempt · TX-EX-1/)).toBeInTheDocument();
  });
});
