// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-PAY-10706 — Grand Vista AC-2026-00618 (a master) had no way to
//          pay its units' bills (tester L1-08)
// Ruling:  PO 2026-10-30 Q4 = A — the approved mock-up's piece 6: a "Pay
//          units" button on a master account's page opens Record payment on
//          "Several accounts" with the master already chosen
// ───────────────────────────────────────────────────────
/**
 * The DOOR, asserted by ADDRESS and by what it carries (hard-won law 2's
 * mirror): a master shows *Pay units*, a regular account does not, and the
 * click lands on `/:tenant/payments/record/new` with the master in router
 * STATE — never in the URL (B14 rule 31).
 *
 * RED FIRST: before this change there was no `Pay units` button at all.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { AccountDetail } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { AccountDetailPage, accountDetailQueryKey } from "./AccountDetailPage";
import { ACCOUNTS_PERMISSION, ACCOUNT_CATEGORIES_QUERY_KEY } from "./customersShared";

afterEach(cleanup);

const TENANT = "brazosbend";
const ACCOUNT = "0192f0aa-0618-7d3b-9a55-2f1d3c4b5a60";

function detail(kind: string): AccountDetail {
  return {
    id: ACCOUNT,
    account_no: "AC-2026-00618",
    kind,
    name: "Grand Vista Properties",
    unit_id: null,
    unit_label: null,
    premises_id: "prm-grand-vista",
    premise: "6405 Grand Vista Blvd",
    services: ["water"],
    balance: "0.000000",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    balance_not_yet_billable: false,
    balance_cached: "0.000000",
    currency: "USD",
    status: "active",
    status_name: "Active",
    status_behavior_class: "billable",
    account_type: "commercial",
    account_subtype: null,
    autopay: false,
    opened_at: "2026-10-01",
    closed_at: null,
    last_bill_at: null,
    aging: null,
    deposit_on_file: "0.000000",
    deposit_received_on: null,
    credit_tier: null,
    tax_exempt: false,
    tax_exempt_ref: null,
    tax_exempt_expires: null,
    bad_address: false,
    nsf_count: 0,
    preferred_language: null,
    custom_data: {},
    contacts: [],
    addresses: [],
    service_agreements: [],
    meters: [],
    plan: null,
    plan_snapshot_unavailable: "BR-CUS-029",
    unit_plan: null,
    customer: null,
    covered_units: 8,
  } as unknown as AccountDetail;
}

function Landed() {
  const location = useLocation();
  return (
    <pre data-testid="landed">
      {JSON.stringify({ path: location.pathname, state: location.state })}
    </pre>
  );
}

function mount(kind: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(ACCOUNT_CATEGORIES_QUERY_KEY, {
    selectable: [{ code: "commercial", name: "Commercial" }],
    legacy: [],
  });
  queryClient.setQueryData(accountDetailQueryKey(ACCOUNT), detail(kind));
  queryClient.setQueryData(queryKeys.myPermissions, {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/accounts/${ACCOUNT}`]}>
          <Routes>
            <Route path="/:tenant/accounts/:accountId" element={<AccountDetailPage />} />
            <Route path="/:tenant/payments/record/new" element={<Landed />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("DEF-PAY-10706 — Pay units on a master account", () => {
  it("a master's page offers Pay units, and it opens Record payment with the master chosen", () => {
    mount("master");
    fireEvent.click(screen.getByRole("button", { name: "Pay units" }));
    const landed = JSON.parse(screen.getByTestId("landed").textContent ?? "{}");
    expect(landed.path).toBe(`/${TENANT}/payments/record/new`);
    expect(landed.state).toEqual({
      payFor: { id: ACCOUNT, accountNo: "AC-2026-00618", kind: "master" },
    });
  });

  it("a regular account's page does not", () => {
    mount("regular");
    expect(screen.queryByRole("button", { name: "Pay units" })).toBeNull();
  });
});
