// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-PAY-10767 (W3) — a statement imported from the screen had no
//           opening or closing balance, so the reconciliation always read
//           "Not on this statement"
// Ruling:   decision log 2026-10-30 "Final-walk questions W1–W4 answered (PO)"
//           — *"W3-A"*; worked: 26–31 Oct statement, closing $616.10
// ───────────────────────────────────────────────────────
// The tester's statement: Bank of America ••7895, 26–31 Oct 2026, opening
// $0.00, closing $616.10. Step 1 asks for both; the file cannot be sent until
// they are typed; the import carries them to the server as decimal strings.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { BankImportWizard, isStatementBalance } from "./BankImportWizard";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

interface Call {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
}

function stub(calls: Call[]) {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const body = typeof init?.body === "string" ? JSON.parse(init.body) : null;
      calls.push({ method, url, body });
      const json = (b: unknown, status = 200) =>
        new Response(JSON.stringify(b), {
          status,
          headers: { "Content-Type": "application/json" },
        });
      if (url.includes("/bank-accounts")) {
        return json({ rows: [{ id: "ba-1", name: "Bank of America", mask: "7895" }] });
      }
      if (method === "POST" && url.includes("/bank-statements")) {
        return json({ statement_import_id: "si-1", line_count: 4, review: null }, 201);
      }
      return json({ detail: "not here" }, 404);
    },
  });
}

function mount(calls: Call[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/finance/deposits/import`]}>
          <Routes>
            <Route
              path="/:tenant/finance/deposits/import"
              element={<BankImportWizard client={stub(calls)} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const input = (id: string) => document.getElementById(id) as HTMLInputElement;

describe("W3 — the import asks for the statement's opening and closing balance", () => {
  it("reads a printed balance as a balance, and blank as nothing", () => {
    expect(isStatementBalance("616.10")).toBe(true);
    expect(isStatementBalance("0.00")).toBe(true);
    expect(isStatementBalance("-12.5")).toBe(true);
    expect(isStatementBalance("")).toBe(false);
    expect(isStatementBalance("616,10")).toBe(false);
    expect(isStatementBalance("1.23456")).toBe(false);
  });

  it("keeps the file closed until both balances are typed, then sends 0.00 and 616.10", async () => {
    const calls: Call[] = [];
    mount(calls);

    await waitFor(() => expect(input("bank_account_id")).toBeTruthy());
    await screen.findByRole("option", { name: /Bank of America/ });
    expect(screen.getByText(t("payments.deposits.form.openingBalance"), { exact: false })).toBeTruthy();
    expect(screen.getByText(t("payments.deposits.form.closingBalance"), { exact: false })).toBeTruthy();

    fireEvent.change(input("bank_account_id"), { target: { value: "ba-1" } });
    fireEvent.change(input("period_start"), { target: { value: "2026-10-26" } });
    fireEvent.change(input("period_end"), { target: { value: "2026-10-31" } });
    // Dates and account but no balances: the file is still closed, and says why.
    expect(input("statement_file").disabled).toBe(true);
    expect(screen.getByText(t("payments.deposits.form.fileBlocked"))).toBeTruthy();

    fireEvent.change(input("opening_balance"), { target: { value: "0.00" } });
    fireEvent.change(input("closing_balance"), { target: { value: "616.10" } });
    expect(input("statement_file").disabled).toBe(false);

    const text = "2026-10-27,LBX4521-1026,870.50\n";
    const file = new File([text], "stmt.csv", { type: "text/csv" });
    // jsdom's File has no arrayBuffer(); the browser's does.
    Object.defineProperty(file, "arrayBuffer", {
      value: async () => new TextEncoder().encode(text).buffer,
    });
    fireEvent.change(input("statement_file"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));

    await waitFor(() =>
      expect(calls.some((call) => call.method === "POST" && call.url.includes("/bank-statements"))).toBe(true),
    );
    const post = calls.find((call) => call.method === "POST");
    expect(post?.body?.opening_balance).toBe("0.00");
    expect(post?.body?.closing_balance).toBe("616.10");
    expect(post?.body?.period_end).toBe("2026-10-31");
  });
});
