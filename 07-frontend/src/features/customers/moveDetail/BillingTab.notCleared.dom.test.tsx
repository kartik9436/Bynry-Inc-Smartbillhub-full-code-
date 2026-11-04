// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9755 — right after the clerk took the deposit by check, the
//          move's Billing tab read "Deposit taken $0.00 · Still to collect
//          $150.00" (M1, MVI-26-0008). The server now serves the uncleared
//          deposit as `awaiting_clearance` and counts it out of still-to-collect;
//          this screen says it, beside the taken figure it does not change
//          (DEF-BIL-9751, 2026-10-06: it counts as paid for the first bill only).
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BillingTab } from "./BillingTab";

afterEach(cleanup);

const fact = (value: unknown = null) => ({ value, unavailable: null });

function record(awaiting: string | null) {
  return {
    facts: { details: { account: null, plan: null } },
    tiles: { fees: { total: "175.0000", currency: "USD", lines: 2, paid: null, unavailable: null } },
    fee_lines: [],
    money_taken: {
      required: fact("150.0000"),
      taken: fact("0.0000"),
      taken_on: null,
      awaiting_clearance: fact(awaiting),
      still_to_collect: fact(awaiting ? "0.0000" : "150.0000"),
      tender: fact(),
      currency: "USD",
    },
    still_owed: { demand_register: fact(), visit: fact(), carry_forward: fact() },
  };
}

function mount(awaiting: string | null) {
  const client = { get: vi.fn(async () => ({ status: 200, data: {} })) } as never;
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <BillingTab record={record(awaiting) as never} regional={{ timeZone: "UTC", dateFormat: "MM/DD/YYYY" }} client={client} />
    </QueryClientProvider>,
  );
}

describe("DEF-CUS-9755 — a deposit in the drawer reads as not cleared, not still to collect", () => {
  it("names the uncleared amount beside Deposit taken", () => {
    mount("150.0000");
    expect(screen.getAllByText("$150.00 not cleared yet").length).toBeGreaterThanOrEqual(1);
  });

  it("says nothing of clearing when nothing is waiting", () => {
    mount(null);
    expect(screen.queryByText(/not cleared yet/)).toBeNull();
  });
});
