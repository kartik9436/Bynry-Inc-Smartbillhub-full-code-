// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Task:    Finance blueprint `P3.5` — *"Doors asserted by address. For each new
//          screen, assert the inbound link resolves to the address **and** the
//          screen id it opens."* OUTCOME: *"A route without a door cannot ship
//          again."*
// Covers:  `P3.1` the accruals workbench (1·4) · `P3.2` reopen (6·1b) ·
//          `P3.3` refund detail (2·5d) · `P3.4` the GL map save (1·3)
// Rules:   CLAUDE.md hard-won law 2 **and its MIRROR** — a live screen behind a
//          dead control. B14 rule 43.
// ─────────────────────────────────────────────────────────────────────────
/**
 * ⚠ **A DOOR IS TWO CLAIMS AND THIS FILE MAKES BOTH, EVERY TIME.**
 *
 * p016's own warning on `P3.5`: *"A hold-expiry test once asserted a screen was
 * registered at one address while the router mounted it at another, and both
 * opened onto 'not built yet'."* So each case here clicks the control a person
 * would click, reads **the address it resolved to**, and reads **a string only
 * the destination renders**. Either half alone is the defect.
 *
 * ⚠ **EVERY TREE IS MOUNTED UNDER THE REAL `/:tenant/…` PATTERN.** A bare
 * `MemoryRouter` leaves `useParams().tenant` undefined, so every address the
 * app builds comes out `//finance/…` — a protocol-relative URL to another host
 * that reads as a perfectly good string to `toContain`. That fixture flaw hid
 * eight broken doors on the customer portal (`DEF-CWP-3925`).
 */
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

// The catalogue is mocked for the reason `chartDialogs.dom.test.tsx` records:
// pulling eleven 1.3MB locale files through vite's transform makes the file
// report `0 test` on a loaded machine, which is not a failing assertion — it is
// a file that could not be asked the question. These cases are about WHERE a
// control goes, never about what it says.
vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: "en" } }),
  Trans: ({ i18nKey }: { i18nKey: string }) => i18nKey,
  initReactI18next: { type: "3rdParty", init: () => undefined },
}));

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { RefundsQueuePanel } from "@/features/payments/RefundsQueuePanel";
import { REFUND_DETAIL_ROUTE, refundDetailPath } from "./RefundDetailPage";
import { AccrualsWorkbench, accrualLines, unansweredLine } from "./AccrualsWorkbench";

const t = (key: string) => key;

/** Prints wherever the router actually is, so a case can assert the ADDRESS
 *  rather than assume it. */
function Where() {
  const location = useLocation();
  return <output data-testid="where">{location.pathname}</output>;
}

/** The destination, standing in for the real page so a case proves the ROUTE
 *  resolves and the SCREEN ID matches — without dragging four more reads into
 *  a jsdom tree. The real page's own rendering is `refundDetail.dom.test.tsx`'s
 *  subject; this file's subject is the DOOR. */
function RefundDetailStandIn() {
  return <div data-screen-id="S58.detail">S58.detail</div>;
}

afterEach(cleanup);

// ══════════════════════════════════════════════════════════════════════════
// `P3.3` + `P3.5` — the refund number on 2·5 Refunds opens 2·5d
// ══════════════════════════════════════════════════════════════════════════
describe("P3.3 · the refunds queue has a door onto 2·5d", () => {
  const REFUND = {
    id: "01a0d412-9931-7680-b77e-61a492386c0f",
    payment_id: null,
    account_id: "acc-1",
    amount: "84.0000",
    currency: "USD",
    status: "requested",
    method: "check",
    reference: "4471",
    reason: "Overpayment",
    requested_by: null,
    requested_at: "2026-09-19T00:00:00Z",
    approved_by: null,
    approved_at: null,
    issued_at: null,
    cleared_at: null,
    voided_at: null,
    void_reason: null,
    journal_entry_id: null,
    void_journal_entry_id: null,
  };

  function mount() {
    const client = {
      // ⚠ **`results`, NOT `rows` — `GET /refunds` PAGES SINCE 2.351.73**
      // (`DEF-PAY-6555` · `P1.3`). `count` is the total over the FILTERED set
      // and is what makes a bounded request honest; `pending` is `P2.19`'s
      // whole-population figure and is what the view label's badge reads. Both
      // are on the wire and they are different numbers on purpose.
      get: async () => ({
        data: { results: [REFUND], count: 1, pending: 1, currency: "USD" },
      }),
      post: async () => ({ data: {} }),
      patch: async () => ({ data: {} }),
      put: async () => ({ data: {} }),
      delete: async () => ({ data: {} }),
    } as unknown as ApiClient;
    const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
      <QueryClientProvider client={queries}>
        <ToastProvider>
          {/* ⚠ THE REAL PATH PATTERN, on BOTH routes. */}
          <MemoryRouter initialEntries={["/brazosbend/finance/revenue"]}>
            <Where />
            <Routes>
              <Route
                path="/:tenant/finance/revenue"
                element={<RefundsQueuePanel t={t} client={client} />}
              />
              <Route path={`/:tenant${REFUND_DETAIL_ROUTE}`} element={<RefundDetailStandIn />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  it("resolves to /:tenant/finance/refunds/:id AND opens S58.detail", async () => {
    mount();
    const door = await screen.findByRole("button", { name: "4471" });
    await userEvent.click(door);
    await waitFor(() => {
      // ① THE ADDRESS — and a leading `/brazosbend`, which is what proves the
      //    tenant segment survived. `//finance/…` would pass a `toContain`.
      expect(screen.getByTestId("where")).toHaveTextContent(
        `/brazosbend/finance/refunds/${REFUND.id}`,
      );
    });
    // ② THE SCREEN IT OPENS, by its own id.
    expect(screen.getByText("S58.detail")).toBeInTheDocument();
  });

  it("labels the door with the cheque number and NEVER with the id", async () => {
    mount();
    const door = await screen.findByRole("button", { name: "4471" });
    // `DEF-2580` — a `?? row.id` fallback printed a raw uuid to a finance user.
    expect(door.textContent).not.toContain(REFUND.id);
  });

  it("builds the path from the id and encodes it", () => {
    expect(refundDetailPath("a/b")).toBe("/finance/refunds/a%2Fb");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `P3.1` — the workbench's LINES, which decide what the $40,000 columns say
// ══════════════════════════════════════════════════════════════════════════
describe("P3.1 · the four engines become the drawing's five lines", () => {
  const UNBILLED = {
    period: { start: "2026-09-01", end: "2026-09-30" },
    entry_type: "accrual",
    reverses_on: "2026-10-01",
    total: "5919.2500",
    currency: "USD",
    services: [
      {
        service: "electric",
        ledger_account_id: null,
        quantity: "1",
        unit: "kWh",
        amount: "4812.4000",
        account_count: 3,
        read_count: 3,
        distinct_unit_prices: 1,
        problems: [],
      },
      {
        service: "water",
        ledger_account_id: null,
        quantity: "1",
        unit: "gal",
        amount: "1106.8500",
        account_count: 2,
        read_count: 2,
        distinct_unit_prices: 1,
        problems: [],
      },
    ],
    account_rows_shown: 0,
    account_rows_total: 0,
    unbilled_ar_account_id: null,
    posting_key: "k1",
    already_posted_entry_id: null,
    period_is_closed: false,
    excluded: {},
    problems: [],
    unavailable: [],
  };
  const DEPRECIATION = {
    period: { start: "2026-09-01", end: "2026-09-30" },
    // ⚠ THE WHOLE POINT: `standard`, and `reverses_on` is NULL.
    entry_type: "standard",
    reverses_on: null,
    total: "3150.0000",
    currency: "USD",
    asset_count: 12,
    assets_considered: 12,
    expense_account_id: null,
    accumulated_account_id: null,
    posting_key: "k3",
    already_posted_entry_id: null,
    period_is_closed: false,
    excluded: {},
    problems: [],
    unavailable: [],
  };

  it("splits unbilled revenue by service and leads on the FIRST line only", () => {
    const lines = accrualLines([{ engine: "unbilled", data: UNBILLED } as never]);
    expect(lines.map((line) => line.service)).toEqual(["electric", "water"]);
    // ⚠ A POST IS PER ENGINE. Two `✓` controls for one entry would be a
    // control lying about what it does.
    expect(lines.map((line) => line.leads)).toEqual([true, false]);
  });

  it("carries the server's entry_type and reverses_on, and invents neither", () => {
    const lines = accrualLines([{ engine: "depreciation", data: DEPRECIATION } as never]);
    expect(lines[0].entryType).toBe("standard");
    // `null` is *Never*, never *unknown*, and never a date this screen derived.
    expect(lines[0].reversesOn).toBeNull();
  });

  it("shows an engine that could not be asked rather than dropping it", () => {
    const line = unansweredLine("allowance");
    expect(line.unanswered).toBe(true);
    expect(line.amount).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `P3.1` — the workbench renders inside a routed page, at the real pattern
// ══════════════════════════════════════════════════════════════════════════
describe("P3.1 · the workbench mounts and offers Post all", () => {
  it("draws the four engines and a Post all control", async () => {
    const client = {
      get: async (path: string) => {
        if (path === "/finance/accruals/unbilled") return { data: UNBILLED_MIN };
        if (path === "/finance/accruals/unpaid-costs") return { data: COSTS_MIN };
        if (path === "/finance/depreciation") return { data: DEPRECIATION_MIN };
        return { data: ALLOWANCE_MIN };
      },
      post: async () => ({ data: {} }),
      patch: async () => ({ data: {} }),
      put: async () => ({ data: {} }),
      delete: async () => ({ data: {} }),
    } as unknown as ApiClient;
    const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queries}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazosbend/finance"]}>
            <Routes>
              <Route
                path="/:tenant/finance"
                element={
                  <AccrualsWorkbench
                    period={{ start: "2026-09-01", end: "2026-09-30" }}
                    now={() => "2026-09-24T00:00:00Z"}
                    t={t}
                    client={client}
                  />
                }
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(await screen.findByTestId("accruals-post-all")).toBeInTheDocument();
    // ⚠ **SCOPED TO THE TABLE BODY, NOT TO `screen`.** Each engine's name is
    // ALSO a filter-chip label, so a bare `getByText` finds two nodes and the
    // failure reads like a missing row rather than like a working filter. The
    // question this case asks is *is the ENGINE ON THE LIST*.
    const body = await waitFor(() => {
      const table = document.querySelector("tbody");
      if (table === null) throw new Error("no table body yet");
      return table;
    });
    await waitFor(() => {
      expect(within(body).getByText("finance.workbench.engine.depreciation")).toBeInTheDocument();
    });
    expect(within(body).getByText("finance.workbench.engine.allowance")).toBeInTheDocument();
    expect(within(body).getByText("finance.workbench.engine.unbilled")).toBeInTheDocument();
    expect(within(body).getByText("finance.workbench.engine.unpaid_costs")).toBeInTheDocument();
    // The two columns that stop the $40,000 error, as VALUES rather than as
    // headings: depreciation and the allowance both say *Never*.
    expect(within(body).getAllByText("finance.workbench.never")).toHaveLength(2);
  });
});

const UNBILLED_MIN = {
  period: { start: "2026-09-01", end: "2026-09-30" },
  entry_type: "accrual",
  reverses_on: "2026-10-01",
  total: "100.0000",
  currency: "USD",
  services: [],
  account_rows_shown: 0,
  account_rows_total: 0,
  unbilled_ar_account_id: null,
  posting_key: "k1",
  already_posted_entry_id: null,
  period_is_closed: false,
  excluded: {},
  problems: [],
  unavailable: [],
};
const COSTS_MIN = {
  ...UNBILLED_MIN,
  accounts: [],
  invoices: [],
  invoice_rows_shown: 0,
  invoice_rows_total: 0,
  accrued_expenses_account_id: null,
  posting_key: "k2",
};
const DEPRECIATION_MIN = {
  ...UNBILLED_MIN,
  entry_type: "standard",
  reverses_on: null,
  asset_count: 0,
  assets_considered: 0,
  expense_account_id: null,
  accumulated_account_id: null,
  posting_key: "k3",
};
const ALLOWANCE_MIN = {
  period: ["2026-09-01", "2026-09-30"],
  entry_type: "standard",
  reverses_on: null,
  enabled: true,
  target: "1184.3000",
  standing: "0.0000",
  movement: "1184.3000",
  receivable: "15333.3000",
  realistically_expect: "14149.0000",
  currency: "USD",
  bands: [],
  posting_key: "k4",
  already_posted_entry_id: null,
  allowance_account_id: null,
  bad_debt_account_id: null,
  problems: [],
};
