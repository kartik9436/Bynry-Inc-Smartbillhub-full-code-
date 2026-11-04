// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9788 — after Complete the PO number recorded at move-in
//          (M7, Cedar Ford Independent School District, PO-2026-118) was on no
//          screen. The move's Account tab now shows it when one was recorded.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/Toast";

import { AccountTab } from "./AccountTab";

afterEach(cleanup);

function mount(account: Record<string, unknown>) {
  const get = vi.fn(async () => ({
    status: 200,
    data: { id: "acc-57", account_no: "AC-2026-00057", contacts: [], addresses: [], ...account },
  }));
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <AccountTab
          accountId="acc-57"
          coOwners={[]}
          regional={{ timeZone: "UTC", dateFormat: "MM/DD/YYYY" }}
          client={{ get } as never}
        />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("DEF-CUS-9788 — the move's Account tab shows the PO on bills", () => {
  it("draws PO on bills with the recorded number", async () => {
    mount({ name: "Cedar Ford Independent School District", po_number: "PO-2026-118" });
    expect(await screen.findByText("PO-2026-118")).toBeInTheDocument();
    expect(screen.getByText("PO on bills")).toBeInTheDocument();
  });

  it("an account with no PO draws no PO row", async () => {
    mount({ name: "Harold Whitfield", po_number: null });
    expect(await screen.findByText(/Harold Whitfield/)).toBeInTheDocument();
    expect(screen.queryByText("PO on bills")).toBeNull();
  });
});
