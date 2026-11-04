// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-PAY-6435 — a payment page that failed to load: *Download error
//          report* downloaded the report and then took the clerk to the
//          Payments list, because the page still passed
//          `onDownloadReport={() => navigate(<the list>)}` from the days the
//          button downloaded nothing (DEF-SHL-6377, 2.350.2, made it download
//          and then run the caller's handler).
// Rules:   CLAUDE.md hard-won law 2 (mount a routed screen under its REAL path
//          pattern) · law 7 (proved RED on the unchanged tip)
// Screens: 2·2 (`S33`) — the payment's own page, failed state
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY (law 7, habit 2):** a page mounted with
// no Payments-list route would "stay put" whatever the handler did, because
// `navigate` to an unmatched address renders nothing and the old panel's text
// could simply vanish. So the LIST is mounted at its real address with a marker
// of its own, and the case asserts both halves: the report was downloaded, the
// list marker never appeared, and the failure panel is still on screen.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { PaymentDetailPage } from "./PaymentDetailPage";

const t = (key: string): string => i18n.t(key) as string;

let downloads = 0;

beforeEach(() => {
  downloads = 0;
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    writable: true,
    value: vi.fn(() => {
      downloads += 1;
      return `blob:report-${downloads}`;
    }),
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    writable: true,
    value: vi.fn(),
  });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/** A client whose payment read FAILS — the state the report button lives in. */
function failingClient(): ApiClient {
  return {
    get: vi.fn(async () => {
      throw new Error("502 from the API pass-through");
    }),
    post: vi.fn(),
  } as unknown as ApiClient;
}

function renderFailedPage() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/payments/PMT-2609-000418"]}>
          <Routes>
            <Route
              path="/:tenant/payments/:paymentRef"
              element={<PaymentDetailPage client={failingClient()} />}
            />
            <Route path="/:tenant/payments" element={<p>the payments list</p>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("DEF-PAY-6435 — Download error report stays on the page it reports", () => {
  it("downloads the report and does not leave the failed payment page", async () => {
    renderFailedPage();
    const button = await screen.findByRole("button", {
      name: t("states.failed.downloadReport"),
    });

    await userEvent.click(button);

    expect(downloads).toBe(1);
    expect(screen.queryByText("the payments list")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("Cancel still goes back to the list — the one exit the failed read offers", async () => {
    renderFailedPage();
    await userEvent.click(await screen.findByRole("button", { name: t("states.failed.cancel") }));
    expect(await screen.findByText("the payments list")).toBeInTheDocument();
  });
});
