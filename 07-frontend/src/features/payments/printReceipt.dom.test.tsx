// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Ruling:   PO 2026-10-30, Q3 = A — Print receipt (Rosa pays $68.00 cash)
// Defect:   DEF-PAY-10743
// ───────────────────────────────────────────────────────
/**
 * Rosa pays $68.00 cash at the counter and is handed a one-page receipt.
 *
 * The button opens a window of its own and the receipt is drawn INTO it; the
 * window here is a second jsdom document, so the assertions read what would be
 * printed and nothing of the app around it. RED FIRST: before this change there
 * was no `PrintReceiptButton` and no print view at all.
 */
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { PrintReceiptButton } from "./PrintReceipt";
import type { PrintReceiptFacts } from "./PrintReceipt";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const ROSA: PrintReceiptFacts = {
  payment_id: "0192f0aa-7c1e-7d3b-9a55-2f1d3c4b5a60",
  payment_no: "PY-261030-0068",
  posted_at: "2026-10-30T09:15:00+00:00",
  account_no: "AC-2026-00068",
  customer_name: "Rosa Delgado",
  amount: "68.000000",
  currency: "USD",
  method_name: "Cash",
  confirmation: null,
  status: "posted",
  bills: [{ number: "BL-2610-0068", amount: "68.000000" }],
  balance: "32.000000",
  taken_by: "Dana Whitfield",
  counter: "CTR-261030-DW",
};

const DISPLAY = {
  regional: { timezone: "America/Chicago", date_format: "MM/DD/YYYY", language: "en" },
  company: {
    legal_name: "Brazos Bend Water Supply Corp",
    dba_name: "Brazos Bend Water",
    has_logo: false,
    logo_ref: null,
    mark: { letters: "BB", background_hex: null, ink_hex: null, contrast_ratio: null },
    brand_primary_hex: null,
  },
  period: null,
};

function clientFor(): ApiClient {
  return {
    get: vi.fn(async (path: string) => {
      if (path.endsWith("/receipt/print")) {
        return { status: 200, data: ROSA, headers: new Headers() };
      }
      if (path === "/shell/display") {
        return { status: 200, data: DISPLAY, headers: new Headers() };
      }
      return { status: 404, data: null, headers: new Headers() };
    }),
  } as unknown as ApiClient;
}

function fakeWindow() {
  const doc = document.implementation.createHTMLDocument("receipt");
  const win = { document: doc, focus: vi.fn(), print: vi.fn() };
  return win;
}

function mount(openWindow: () => Window | null, client = clientFor()) {
  // The product opens `window.open` itself (DEF-PAY-10762); the test stubs it.
  vi.spyOn(window, "open").mockImplementation(openWindow);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <PrintReceiptButton paymentId={ROSA.payment_id} client={client} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return client;
}

describe("Q3 = A — Print receipt", () => {
  it("opens a page of its own showing every fact the PO listed, then prints", async () => {
    const win = fakeWindow();
    const client = mount(() => win as unknown as Window);
    fireEvent.click(screen.getByRole("button", { name: "Print receipt" }));

    const sheet = await waitFor(() => {
      const found = win.document.querySelector('[data-testid="receipt-sheet"]');
      if (!found) throw new Error("no receipt yet");
      return found as HTMLElement;
    });
    const view = within(sheet);
    expect(view.getByText("Brazos Bend Water").textContent).toBe("Brazos Bend Water");
    expect(view.getByText("PY-261030-0068").textContent).toBe("PY-261030-0068");
    expect(view.getByText("AC-2026-00068").textContent).toBe("AC-2026-00068");
    expect(view.getByText("Rosa Delgado").textContent).toBe("Rosa Delgado");
    expect(view.getByText("Cash").textContent).toBe("Cash");
    expect(view.getByText("BL-2610-0068").textContent).toBe("BL-2610-0068");
    // Money displays 2 places (hard rule 2): $68.00 twice (paid, bill), $32.00 left.
    expect(view.getAllByText("$68.00")).toHaveLength(2);
    expect(view.getByText("$32.00").textContent).toBe("$32.00");
    expect(view.getByText("Dana Whitfield").textContent).toBe("Dana Whitfield");
    expect(view.getByText("CTR-261030-DW").textContent).toBe("CTR-261030-DW");
    // B14 rule 31: the id is never printed.
    expect(sheet.textContent).not.toContain(ROSA.payment_id);
    // The window's document is NOT the app's: nothing of the frame is printed.
    expect(win.document.body.textContent).not.toContain("Print receipt");

    // DEF-PAY-10769: the app's stylesheet is copied into this window, so a
    // heading with no size class prints at the page-title size. Body size here.
    expect(sheet.querySelector("h2")?.className).toContain("text-base");

    await waitFor(() => expect(win.print).toHaveBeenCalledTimes(1));
    expect(client.get).toHaveBeenCalledWith(`/payments/${ROSA.payment_id}/receipt/print`);
  });

  // DEF-PAY-10770 — PO W4 = A: Hugo Hollis paid $68.00 cash that met no bill.
  // The books' net position is −68.00 (in credit), so the receipt reads
  // "Credit on account $68.00", never "Balance remaining $0.00" or "−$68.00".
  it("prints Credit on account $68.00 when the account is in credit (W4)", async () => {
    const hugo: PrintReceiptFacts = {
      ...ROSA,
      customer_name: "Hugo Hollis",
      bills: [],
      balance: "-68.000000",
    };
    const client = {
      get: vi.fn(async (path: string) => {
        if (path.endsWith("/receipt/print")) return { status: 200, data: hugo, headers: new Headers() };
        if (path === "/shell/display") return { status: 200, data: DISPLAY, headers: new Headers() };
        return { status: 404, data: null, headers: new Headers() };
      }),
    } as unknown as ApiClient;
    const win = fakeWindow();
    mount(() => win as unknown as Window, client);
    fireEvent.click(screen.getByRole("button", { name: "Print receipt" }));
    const sheet = await waitFor(() => {
      const found = win.document.querySelector('[data-testid="receipt-sheet"]');
      if (!found) throw new Error("no receipt yet");
      return found as HTMLElement;
    });
    const view = within(sheet);
    const credit = view.getByText("Credit on account");
    expect(credit.parentElement?.textContent).toBe("Credit on account$68.00");
    expect(sheet.textContent).not.toContain("Balance remaining");
    expect(sheet.textContent).not.toContain("-$68.00");
  });

  it("says so when the browser blocks the window", async () => {
    mount(() => null);
    fireEvent.click(screen.getByRole("button", { name: "Print receipt" }));
    expect(await screen.findByText("Allow pop-ups, then try again.")).toBeInTheDocument();
  });
});
