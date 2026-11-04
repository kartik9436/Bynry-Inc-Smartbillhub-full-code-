// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-PAY-10157` — $25.00 cash taken into counter CTR-261102-DW-2
//          through Record a payment stayed PROCESSING: the form left Clearing
//          date blank, so nothing posted and Ana still owed $1,181.38, while
//          the Check box said "$25.00 goes to this account. It meets the
//          oldest bills first."
//          ⛔ SUPERSEDED ON THE RECORD PAGE 2026-10-30 by `DEF-PAY-10737`
//          (L2-07): CR-186-BRC10 (PO 2026-10-21) makes every payment `posted`
//          and applied at entry and `cleared` only at bank reconciliation, and
//          the server never stored the box's value — so the box is REMOVED.
//          The cases below assert the new truth. `clearingDate.ts` is DELETED
//          since `DEF-PAY-10750` took the same box off the account screen's
//          form (`AccountActions.dom.test.tsx` asserts that one).
// Code:    `RecordPaymentPage.tsx` · `AccountActions.tsx`
// Rules:   BR-PAY-021 · BR-PAY-033 · CR-186-BRC10
// ───────────────────────────────────────────────────────
// RED PROVED FIRST (2026-10-30, `DEF-PAY-10737`): against the tip's
// RecordPaymentPage.tsx the "no Clearing date box" case failed — `#cleared_at`
// was drawn — and the cheque case read "It meets no bill until cleared."
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { AccountRow, PaymentMethodOption } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { RecordPaymentForm } from "./RecordPaymentPage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const METHODS: PaymentMethodOption[] = [
  { id: "m-cash", code: "cash", name: "Cash" },
  { id: "m-check", code: "check", name: "Check" },
  { id: "m-ach", code: "ach", name: "ACH" },
];

const ANA = {
  id: "acc-0001",
  account_no: "AC-2026-00001",
  name: "Alvarez, Ana",
  balance: "1181.380000",
  currency: "USD",
  status: "active",
} as unknown as AccountRow;

function mount(post = vi.fn()) {
  const client = {
    get: vi.fn((path: string) => {
      if (path === "/accounts") {
        return Promise.resolve({ data: { results: [ANA], count: 1, page: 1, per: 50, rollup: {} } });
      }
      return Promise.resolve({ data: { results: [], count: 0 } });
    }),
    post,
  } as unknown as ApiClient;
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/payments/record/new"]}>
          <RecordPaymentForm
            client={client}
            methods={METHODS}
            today="2026-11-02"
            dateFormat="YYYY-MM-DD"
            currency="USD"
            onCancel={() => undefined}
            onRecorded={() => undefined}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return post;
}

function recorded() {
  return vi.fn(async () => ({
    status: 201,
    data: { id: "pay-1", payment_no: "PY-261102-0087", created: true, status: "posted", allocations: [] },
    headers: new Headers(),
  }));
}

async function anaPays(method: string): Promise<void> {
  const box = document.querySelector<HTMLInputElement>("#account_id") as HTMLInputElement;
  fireEvent.change(box, { target: { value: "AC-2026-00001" } });
  await waitFor(() => expect(document.querySelectorAll('[role="option"]').length).toBeGreaterThan(0));
  fireEvent.click(document.querySelectorAll<HTMLElement>('[role="option"]')[0]);
  fireEvent.change(document.querySelector("#amount") as HTMLInputElement, {
    target: { value: "25.00" },
  });
  fireEvent.change(document.querySelector("#method") as HTMLSelectElement, {
    target: { value: method },
  });
}

async function submitted(post: ReturnType<typeof vi.fn>): Promise<Record<string, unknown>> {
  fireEvent.click(screen.getByRole("button", { name: t("payments.form.submit") }));
  await waitFor(() => expect(post).toHaveBeenCalled());
  return (post.mock.calls[0] as unknown as [string, Record<string, unknown>])[1];
}

describe("DEF-PAY-10737 · Record payment asks no clearing date (CR-186)", () => {
  it("there is no Clearing date box, and no clearing date is sent", async () => {
    const post = mount(recorded());
    await anaPays("ach");
    expect(document.querySelector("#cleared_at")).toBeNull();
    expect(document.body.textContent).not.toContain(t("payments.form.clearedAt"));
    const body = await submitted(post);
    expect(body.method).toBe("ach");
    expect(body.posted_at).toBe("2026-11-02");
    expect(body.cleared_at).toBeNull();
  });

  it("every tender's Check box says the money meets the oldest bills", async () => {
    for (const method of ["cash", "check"]) {
      mount(recorded());
      await anaPays(method);
      expect(document.body.textContent).toContain(t("payments.form.consequence.oldest"));
      expect(document.body.textContent).not.toContain(t("payments.form.consequence.notCleared"));
      cleanup();
    }
  });
});
