// @vitest-environment jsdom
// CR-175-BRC10 — Mark returned on the payment detail (PO 2026-10-07).
// What would make this pass wrongly: a fixture with no role read (the button
// is offered on a null role by design), so every role case names the role it
// mounts as and the executive case asserts DISABLED, not merely present.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { PaymentDetail } from "@/api/paymentDetailEndpoints";
import { ToastProvider } from "@/components/Toast";

import { markReturnedSchema } from "./MarkReturnedModal";
import { PaymentDetailPage } from "./PaymentDetailPage";

afterEach(() => cleanup());

const t = (key: string) => i18n.t(key);

function detail(markReturned: PaymentDetail["actions"]["mark_returned"]): PaymentDetail {
  return {
    id: "8f14e45f-ea5c-4f31-9c1b-0c2c0a1a7d11",
    payment_no: "PY-261007-0012",
    account_id: "1c383cd3-0b7c-4b7e-9c94-1d38f8f2e4aa",
    account_no: "00077889",
    customer_name: "Rosa Delgado",
    type: "payment",
    method: "ach",
    method_name: "ACH",
    confirmation: null,
    memo: null,
    amount: "100.0000",
    currency: "USD",
    status: "cleared",
    purpose: "bill",
    posted_at: "2026-10-07",
    cleared_at: "2026-10-07",
    applied_to: [],
    origin: "entry",
    batch_ref: null,
    source: { origin: "entry", origin_is_derived: false, taken_by: null, counter_session_ref: null },
    reconciled: null,
    actions: {
      edit: { allowed: true, reason: null, tender_locked: false },
      correction: { allowed: true, reason: null },
      cancel: { allowed: false, reason: "cancel_refused_cleared_use_reverse" },
      receipt: { allowed: true, reason: null },
      mark_returned: markReturned,
    },
    receipts: [],
    next_copy_no: 2,
    unavailable: [],
    custom_data: {},
  } as unknown as PaymentDetail;
}

function mount(row: PaymentDetail, role: string) {
  const post = vi.fn(async () => ({
    status: 201,
    data: { id: "r1", payment_no: "PY-261010-0001", created: true, amount: "-100.0000", currency: "USD" },
    headers: new Headers(),
  }));
  const client = {
    get: vi.fn(async (path: string) => {
      if (path.includes("permissions")) {
        return { status: 200, data: { role, permissions: {} }, headers: new Headers() };
      }
      if (path.includes("/history")) {
        return { status: 200, data: { results: [], count: 0, next: null, previous: null }, headers: new Headers() };
      }
      if (path.startsWith("/payments/")) {
        return { status: 200, data: row, headers: new Headers() };
      }
      return { status: 200, data: { results: [], methods: [] }, headers: new Headers() };
    }),
    post,
  } as unknown as ApiClient;
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/brazosbend/payments/${row.payment_no}`]}>
          <Routes>
            <Route path="/:tenant/payments/:paymentRef" element={<PaymentDetailPage client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { post, client };
}

const OPEN = { offered: true, allowed: true, reason: null };

describe("Mark returned (CR-175-BRC10)", () => {
  it("is offered to a billing clerk on an ACH payment, in the danger tier", async () => {
    mount(detail(OPEN), "billing_clerk");
    const button = await screen.findByRole("button", { name: "Mark returned" });
    await waitFor(() => expect(button).toBeEnabled());
    expect(button.className).toMatch(/danger/);
  });

  it("is not drawn at all on a payment that is not ACH", async () => {
    mount(detail({ offered: false, allowed: false, reason: null }), "billing_clerk");
    await screen.findByText("PY-261007-0012", { selector: "h1" });
    expect(screen.queryByRole("button", { name: "Mark returned" })).toBeNull();
  });

  it("is disabled with its reason for another role, never hidden", async () => {
    mount(detail(OPEN), "executive");
    const button = await screen.findByRole("button", { name: "Mark returned" });
    await waitFor(() => expect(button).toBeDisabled());
    expect(button).toHaveAttribute("title", "Billing clerks and admins only.");
  });

  it("is disabled once the payment is already returned", async () => {
    mount(detail({ offered: true, allowed: false, reason: "already_returned" }), "billing_clerk");
    const button = await screen.findByRole("button", { name: "Mark returned" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("title", "Already returned.");
  });

  it("sends the reason, the upper-cased code and the bank's date to the new door", async () => {
    const { post } = mount(detail(OPEN), "billing_clerk");
    fireEvent.click(await screen.findByRole("button", { name: "Mark returned" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(dialog.querySelector("#return_code") as HTMLInputElement, { target: { value: "r01" } });
    fireEvent.change(dialog.querySelector("#returned_on") as HTMLInputElement, { target: { value: "2026-10-10" } });
    expect(dialog).toHaveTextContent("$100.00 is owed again.");
    const submit = Array.from(dialog.querySelectorAll("button")).find(
      (one) => one.textContent === "Mark returned",
    ) as HTMLButtonElement;
    fireEvent.click(submit);
    await waitFor(() => expect(post).toHaveBeenCalled());
    const [path, body] = post.mock.calls[0] as unknown as [string, Record<string, unknown>];
    expect(path).toBe("/payments/8f14e45f-ea5c-4f31-9c1b-0c2c0a1a7d11/mark-returned");
    expect(body).toMatchObject({ reason: "nsf", return_code: "R01", returned_on: "2026-10-10" });
    expect(typeof body.idempotency_key).toBe("string");
  });
});

describe("the dialog's checks", () => {
  it("requires a code and refuses one that is not a Nacha code", () => {
    const schema = markReturnedSchema(t);
    expect(schema.safeParse({ returned_on: "2026-10-10", return_code: "" }).success).toBe(false);
    expect(schema.safeParse({ returned_on: "2026-10-10", return_code: "X01" }).success).toBe(false);
    expect(schema.safeParse({ returned_on: "2026-10-10", return_code: "R1" }).success).toBe(false);
    expect(schema.safeParse({ returned_on: "2026-10-10", return_code: "r01" }).success).toBe(true);
    expect(schema.safeParse({ returned_on: "", return_code: "R01" }).success).toBe(false);
  });
});
