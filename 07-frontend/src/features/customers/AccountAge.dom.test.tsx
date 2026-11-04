// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CUS-10180 (Account age column) · DEF-CUS-10181 (Aging reads bills)
// Ruling:   decision log 2026-10-17 — "ACCOUNT AGE ON THE ACCOUNTS LIST; AGING
//           STAYS MONEY AND IS FIXED TO READ BILLS"
// Screen:   ACC-01 / S17, mounted at its REAL route pattern (/:tenant/accounts)
// ───────────────────────────────────────────────────────
// Every Account age cell the PO was shown (open · closed · pending · reopened ·
// imported), the Aging cell for a bill 77 days overdue and for nothing owed,
// and both sorts as the REQUEST the screen sends. The clock is pinned to the
// ruling's own day, 10/17/2026, so the PO's worked figures are the assertions.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import type { AccountRow, AccountsPage } from "@/api/endpoints";

import { AccountsListPage } from "./AccountsListPage";
import type { AccountRowWithAgeing } from "./accountsListCells";
import { ACCOUNT_CATEGORIES_QUERY_KEY, ACCOUNTS_PERMISSION } from "./customersShared";

const TEST_TENANT = "brazosbend";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-17T16:00:00Z"));
});
afterEach(() => {
  vi.useRealTimers();
  cleanup();
});

function row(over: Partial<AccountRowWithAgeing>): AccountRowWithAgeing {
  const base: AccountRow = {
    id: "acc-x",
    account_no: "A-X",
    customer_no: null,
    kind: "regular",
    name: "Miller, Sarah",
    unit_id: "u-x",
    unit_label: "A",
    premise: "1408 Elm St · A",
    services: ["electric"],
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
    account_type: "residential",
    account_subtype: null,
    autopay: false,
    opened_at: null,
    closed_at: null,
    last_bill_at: null,
    aging: null,
  };
  return {
    ...base,
    ageing_segment: null,
    ageing_days_past_due: null,
    ageing_source: null,
    ageing_unavailable: null,
    ...over,
  };
}

const ROWS: AccountRowWithAgeing[] = [
  row({ id: "a-open", account_no: "A-OPEN", opened_at: "2019-03-14" }),
  row({ id: "a-closed", account_no: "A-CLOSED", opened_at: "2019-03-14", closed_at: "2025-03-14" }),
  row({ id: "a-pending", account_no: "A-PEND", status: "pending_activation", opened_at: null }),
  row({ id: "a-reopen", account_no: "A-REOPEN", opened_at: "2026-10-14" }),
  row({
    id: "a-waiting",
    account_no: "A-WAIT",
    status: "pending_activation",
    opened_at: "2026-11-01",
  }),
  row({ id: "a-import", account_no: "A-IMPORT", opened_at: "2012-03-01" }),
  row({
    id: "a-late",
    account_no: "A-LATE",
    opened_at: "2026-06-02",
    balance: "120.000000",
    ageing_segment: "d61_90",
    ageing_days_past_due: 77,
    ageing_source: "bills",
  }),
];

function envelope(): AccountsPage {
  return {
    count: ROWS.length,
    next: null,
    previous: null,
    results: ROWS as AccountRow[],
    rollup: {
      accounts: ROWS.length,
      outstanding: "120.000000",
      currency: "USD",
      outstanding_basis: "posting",
      outstanding_unavailable: [],
      past_due_60_plus: null,
      by_status: [],
    },
  };
}

function mount(initial = "/accounts") {
  const urls: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input) => {
      const url = String(input);
      const body = url.includes("/accounts")
        ? (urls.push(url), envelope())
        : { selectable: [], legacy: [] };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  });
  queryClient.setQueryData(ACCOUNT_CATEGORIES_QUERY_KEY, { selectable: [], legacy: [] });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${initial}`]}>
          <Routes>
            <Route path="/:tenant/accounts" element={<AccountsListPage client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { urls };
}

/** The Account age cell of the row whose account number is `accountNo`. */
async function ageCell(accountNo: string): Promise<HTMLElement> {
  const link = await screen.findByRole("link", { name: accountNo });
  const tr = link.closest("tr");
  if (tr === null) throw new Error(`no row for ${accountNo}`);
  const cell = tr.querySelector<HTMLElement>("[data-account-age]");
  if (cell === null) throw new Error(`no Account age cell for ${accountNo}`);
  return cell;
}

describe("DEF-CUS-10180 — the Account age column, the PO's worked figures", () => {
  it("renders the header, next to Aging", async () => {
    mount();
    const table = await screen.findByRole("table");
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((th) => th.textContent?.replace(/[▲▼]/g, "").trim());
    const aging = headers.indexOf("Aging");
    expect(aging).toBeGreaterThan(-1);
    expect(headers[aging + 1]).toBe("Account age");
  });

  it("open since 03/14/2019 → 7 yrs 7 mos, Opened beneath", async () => {
    mount();
    const cell = await ageCell("A-OPEN");
    expect(cell).toHaveAttribute("data-account-age", "open");
    expect(cell).toHaveTextContent("7 yrs 7 mos");
    expect(cell).toHaveTextContent("03/14/2019");
  });

  it("a closed account stops ageing at its Closed date and says so", async () => {
    mount();
    const cell = await ageCell("A-CLOSED");
    expect(cell).toHaveAttribute("data-account-age", "closed");
    expect(cell).toHaveTextContent("6 yrs");
    expect(cell).toHaveTextContent("closed 03/14/2025");
  });

  it("pending activation → Not opened", async () => {
    mount();
    const cell = await ageCell("A-PEND");
    expect(cell).toHaveAttribute("data-account-age", "not-opened");
    expect(cell).toHaveTextContent("Not opened");
  });

  it("pending with a move-in date already typed is still Not opened", async () => {
    mount();
    const cell = await ageCell("A-WAIT");
    expect(cell).toHaveAttribute("data-account-age", "not-opened");
    expect(cell).toHaveTextContent("Not opened");
  });

  it("reopened 10/14/2026 → 3 days (the age restarts)", async () => {
    mount();
    expect(await ageCell("A-REOPEN")).toHaveTextContent("3 days");
  });

  it("imported with Opened 03/01/2012 → 14 yrs 7 mos", async () => {
    mount();
    expect(await ageCell("A-IMPORT")).toHaveTextContent("14 yrs 7 mos");
  });
});

describe("DEF-CUS-10181 — Aging reads the bills", () => {
  it("a bill 77 days overdue reads 61–90, with the days on hover", async () => {
    mount();
    const link = await screen.findByRole("link", { name: "A-LATE" });
    const tr = link.closest("tr") as HTMLElement;
    const pill = within(tr).getByText("61–90 days past");
    expect(pill.closest("[title]")).toHaveAttribute("title", "77 days past due");
  });

  it("nothing owed is a dash with no reason attached", async () => {
    mount();
    const link = await screen.findByRole("link", { name: "A-OPEN" });
    const none = (link.closest("tr") as HTMLElement).querySelector("[data-ageing='none']");
    expect(none).not.toBeNull();
    expect(none).not.toHaveAttribute("title");
  });
});

describe("the two sorts, as the request the screen sends", () => {
  it("Account age sorts by the server's `account_age`, both directions", async () => {
    const { urls } = mount();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /Account age/ }));
    await waitFor(() => expect(urls[urls.length - 1]).toContain("sort=account_age"));
    const first = new URL(urls[urls.length - 1], "http://x").searchParams.get("dir");
    await user.click(within(await screen.findByRole("table")).getByRole("button", { name: /Account age/ }));
    await waitFor(() => {
      const last = new URL(urls[urls.length - 1], "http://x").searchParams;
      expect(last.get("sort")).toBe("account_age");
      expect(last.get("dir")).not.toBe(first);
    });
  });

  it("Aging is sortable and sends `sort=ageing`", async () => {
    const { urls } = mount();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const table = await screen.findByRole("table");
    await user.click(within(table).getByRole("button", { name: /^Aging/ }));
    await waitFor(() => expect(urls[urls.length - 1]).toContain("sort=ageing"));
  });

  it("a deep link with sort=account_age&dir=asc is honoured on load", async () => {
    const { urls } = mount("/accounts?sort=account_age&dir=asc");
    await screen.findByRole("table");
    const last = new URL(urls[urls.length - 1], "http://x").searchParams;
    expect(last.get("sort")).toBe("account_age");
    expect(last.get("dir")).toBe("asc");
  });
});
