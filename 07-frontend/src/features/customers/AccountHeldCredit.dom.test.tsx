// @vitest-environment jsdom
/**
 * DEF-PAY-10707 — the tester's L2-01: Farid Delacroix paid $170.00 on a $165.00
 * bill and the Credits tab said *"No credits on this account."* The $5.00 was
 * held as account credit and no screen listed it.
 *
 * RED FIRST (law 7): before this group existed the Credits tab rendered no
 * `[data-held-credit-row]` at all for the same server answer.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import i18n from "@/i18n";
import { ToastProvider } from "@/components/Toast";

import { AccountHeldCreditGroup, smallerAmount } from "./AccountHeldCredit";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const ACCOUNT = "acc-farid";

interface Call {
  method: string;
  path: string;
  body?: unknown;
}

function fakeClient(options: { openBills?: boolean; sources?: boolean } = {}) {
  const calls: Call[] = [];
  const ok = (data: unknown) => Promise.resolve({ status: 200, data, etag: null, notModified: false });
  const client = {
    get: (path: string) => {
      calls.push({ method: "GET", path });
      if (path === `/accounts/${ACCOUNT}/credit-sources`) {
        return ok({
          account_id: ACCOUNT,
          refundable: "5.000000",
          refundable_display: "$5.00",
          sources:
            options.sources === false
              ? []
              : [
                  {
                    payment_id: "pay-170",
                    payment_no: "PMT-2610-000031",
                    posted_at: "2026-10-21T15:00:00Z",
                    amount: "170.000000",
                    contributed: "5.000000",
                    currency: "USD",
                  },
                ],
          source_count: 1,
          problems: [],
        });
      }
      if (path === `/accounts/${ACCOUNT}/open-bills`) {
        return ok({
          account_id: ACCOUNT,
          account_no: "A-00031",
          currency: "USD",
          bills:
            options.openBills === true
              ? [
                  {
                    invoice_id: "inv-nov",
                    number: "BL-2611-000031",
                    issued_on: "2026-11-01",
                    total: "172.400000",
                    amount_due: "172.400000",
                    allocated: "0.000000",
                    open_balance: "172.400000",
                    currency: "USD",
                    composition: null,
                  },
                ]
              : [],
          total_open: "0.000000",
          bill_count: 0,
          problems: [],
        });
      }
      if (path === "/payments") {
        return ok({ results: [], count: 0, page: 1, per: 50, totals: {}, methods: [] });
      }
      return Promise.reject(new Error(`unexpected GET ${path}`));
    },
    post: (path: string, body?: unknown) => {
      calls.push({ method: "POST", path, body });
      return ok({ payment_id: "pay-170", payment_no: "PMT-2610-000031", problems: [] });
    },
  };
  return { client: client as unknown as ApiClient, calls };
}

function mount(client: ApiClient) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/accounts/acc-farid?tab=credits"]}>
          <Routes>
            <Route
              path="/:tenant/accounts/:accountId"
              element={
                <AccountHeldCreditGroup
                  accountId={ACCOUNT}
                  accountNo="A-00031"
                  client={client}
                  t={t}
                  timeZone="America/Chicago"
                  dateFormat="MM/DD/YYYY"
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("DEF-PAY-10707 · held credit on the account", () => {
  it("Farid's $5.00 is one row, with the payment it came from", async () => {
    const { client } = fakeClient();
    mount(client);
    const row = await waitFor(() => {
      const found = document.querySelector("[data-held-credit-row]") as HTMLElement | null;
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(within(row).getByText("PMT-2610-000031")).toBeInTheDocument();
    expect(within(row).getByText("$170.00")).toBeInTheDocument();
    expect(within(row).getByText("$5.00")).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "Refund" })).toBeEnabled();
  });

  it("an account holding nothing says so", async () => {
    const { client } = fakeClient({ sources: false });
    mount(client);
    expect(await screen.findByText("No held credit.")).toBeInTheDocument();
  });

  it("Apply now waits for an open bill", async () => {
    const { client } = fakeClient({ openBills: false });
    mount(client);
    const apply = await screen.findByRole("button", { name: "Apply now" });
    await waitFor(() => expect(apply).toBeDisabled());
    expect(apply).toHaveAttribute("title", "No open bill to apply to.");
  });

  it("Apply now puts the held $5.00 on the open bill and releases nothing", async () => {
    const { client, calls } = fakeClient({ openBills: true });
    mount(client);
    const apply = await screen.findByRole("button", { name: "Apply now" });
    await waitFor(() => expect(apply).toBeEnabled());
    fireEvent.click(apply);
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/^Why/), { target: { value: "Customer asked" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Apply ✓" }));
    await waitFor(() => {
      const post = calls.find((call) => call.method === "POST");
      expect(post?.path).toBe("/payments/pay-170/reapply");
      expect(post?.body).toMatchObject({
        targets: [{ invoice_id: "inv-nov", amount: "5.000000" }],
        release: [],
        reason: "Customer asked",
      });
    });
  });

  it("Refund opens the raise form on this account with the held amount", async () => {
    const { client } = fakeClient();
    mount(client);
    fireEvent.click(await screen.findByRole("button", { name: "Refund" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/A-00031/)).toBeInTheDocument();
    // DEF-PAY-10771 — the box reads 5.00, never the wire's six places.
    expect(within(dialog).getByDisplayValue("5.00")).toBeInTheDocument();
    expect(within(dialog).queryByDisplayValue("5.000000")).toBeNull();
  });
});

describe("smallerAmount", () => {
  it("compares decimal strings without a float", () => {
    expect(smallerAmount("5.000000", "172.400000")).toBe("5.000000");
    expect(smallerAmount("259.230000", "40.100000")).toBe("40.100000");
  });
});
