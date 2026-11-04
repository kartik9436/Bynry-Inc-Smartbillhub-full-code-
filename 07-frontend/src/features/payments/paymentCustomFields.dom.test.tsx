// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 wave W5 — payment custom fields, captured at entry only.
//          PO 2026-10-02, Part 2 row 14: *"Record payment (at entry only) ·
//          Payment detail · Can't be corrected afterwards; never used to apply
//          the payment to bills"*.
// Screens: S35 (Record payment — Input) · S33 (Payment detail — View)
// Rules:   BR-TEN-052 (required only where typed in) · B14 rule 43 (the ONE
//          `CustomFields` component, not a copy) · hard rule 4 (no edit control)
// ───────────────────────────────────────────────────────
// The worked example put to the PO: a cashier records **Drawer = 2** on a
// **$120.00** payment.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { AccountRow, CustomFieldRegistryEntry, PaymentMethodOption } from "@/api/endpoints";
import type { PaymentDetail } from "@/api/paymentDetailEndpoints";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { PaymentDetailPage } from "./PaymentDetailPage";
import { RecordPaymentForm } from "./RecordPaymentPage";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const METHODS: PaymentMethodOption[] = [{ id: "met-ach", code: "ach", name: "ACH" }];

const DRAWER: CustomFieldRegistryEntry = {
  id: "cf-1",
  key: "drawer",
  label: "Drawer",
  help_text: "",
  data_type: "text",
  options: [],
  is_required: true,
  display_order: 1,
  placement: { S35: "input", S33: "view" },
};

const ACCOUNT = {
  id: "acc-0050",
  account_no: "AC-2026-00050",
  name: "Miller, Sarah",
  balance: "120.000000",
  currency: "USD",
  status: "active",
} as unknown as AccountRow;

function recordClient(fields: CustomFieldRegistryEntry[], post: ReturnType<typeof vi.fn>): ApiClient {
  return {
    get: vi.fn((path: string, options?: { query?: Record<string, unknown> }) => {
      if (path === "/custom-fields") {
        // The registry is asked for THIS slot and no other.
        expect(options?.query).toMatchObject({ entity: "payments", screen: "S35", mode: "input" });
        return Promise.resolve({ data: { entity: "payments", fields } });
      }
      if (path === "/accounts") {
        return Promise.resolve({
          data: { results: [ACCOUNT], count: 1, page: 1, per: 50, rollup: {} },
        });
      }
      return Promise.resolve({ data: { results: [], count: 0 } });
    }),
    post,
  } as unknown as ApiClient;
}

function mountRecord(fields: CustomFieldRegistryEntry[], post = vi.fn()) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/payments/record/new"]}>
          <RecordPaymentForm
            client={recordClient(fields, post)}
            methods={METHODS}
            today="2026-10-02"
            dateFormat="MM/DD/YYYY"
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

async function chooseAccountAndAmount(): Promise<void> {
  const box = document.querySelector<HTMLInputElement>("#account_id") as HTMLInputElement;
  fireEvent.change(box, { target: { value: "AC-2026-00050" } });
  await waitFor(() => expect(document.querySelectorAll('[role="option"]').length).toBeGreaterThan(0));
  fireEvent.click(document.querySelectorAll<HTMLElement>('[role="option"]')[0]);
  const amount = document.querySelector<HTMLInputElement>("#amount") as HTMLInputElement;
  fireEvent.change(amount, { target: { value: "120.00" } });
}

const drawerBox = (): HTMLInputElement | null =>
  document.querySelector<HTMLInputElement>('[id="custom_data.drawer"]');

describe("CR-161 W5 · Record payment (S35) captures the utility's own fields", () => {
  it("a utility with no payment fields sees Record payment unchanged", async () => {
    const post = vi.fn();
    mountRecord([], post);
    await screen.findByText(t("payments.form.amount"));
    expect(drawerBox()).toBeNull();
    expect(document.body.textContent).not.toContain(t("customFields.sectionHeadingFallback"));
  });

  it("draws the Drawer field and sends the answer with the payment", async () => {
    const post = vi.fn(async () => ({
      status: 201,
      data: { id: "pay-1", payment_no: "PMT-1", created: true, status: "cleared", allocations: [] },
      headers: new Headers(),
    }));
    mountRecord([DRAWER], post);
    await waitFor(() => expect(drawerBox()).not.toBeNull());
    await chooseAccountAndAmount();
    fireEvent.change(drawerBox() as HTMLInputElement, { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: t("payments.form.submit") }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    const [path, body] = post.mock.calls[0] as unknown as [string, Record<string, unknown>];
    expect(path).toBe("/accounts/acc-0050/payments");
    expect(body.custom_data).toEqual({ drawer: "2" });
  });

  it("a required answer left blank is refused by name and the form keeps what was typed", async () => {
    const post = vi.fn(async () => {
      throw new ApiError(422, {
        code: "VAL-FORMAT",
        message_key: "customFields.invalid",
        field_errors: [
          { field: "custom_data.drawer", code: "VAL-REQUIRED", message_key: "customFields.required" },
        ],
      });
    });
    mountRecord([DRAWER], post);
    await waitFor(() => expect(drawerBox()).not.toBeNull());
    await chooseAccountAndAmount();
    fireEvent.click(screen.getByRole("button", { name: t("payments.form.submit") }));
    await waitFor(() => expect(post).toHaveBeenCalled());
    const [, body] = post.mock.calls[0] as unknown as [string, Record<string, unknown>];
    // Sent from THIS screen even when empty — that is how the server knows a
    // required field binds here (`apps/payments/custom_values.py`).
    expect(body.custom_data).toEqual({});
    await waitFor(() => expect(drawerBox()).toHaveAttribute("aria-invalid", "true"));
    // The form is kept: the amount the clerk typed is still there.
    expect((document.querySelector("#amount") as HTMLInputElement).value).toBe("120.00");
  });
});

function detail(over: Partial<PaymentDetail> = {}): PaymentDetail {
  return {
    id: "0190a5b2-0000-7000-8000-000000000418",
    payment_no: "PMT-2610-000001",
    account_id: "acc-0050",
    account_no: "AC-2026-00050",
    customer_name: "Sarah Miller",
    type: "payment",
    method: "ach",
    method_name: "ACH",
    confirmation: null,
    memo: null,
    amount: "120.000000",
    currency: "USD",
    status: "cleared",
    purpose: "bill",
    posted_at: "2026-10-02",
    cleared_at: "2026-10-02",
    applied_to: [],
    origin: "entry",
    batch_ref: null,
    source: { origin: "entry", origin_is_derived: false, taken_by: null, counter_session_ref: null },
    reconciled: null,
    actions: {
      edit: { allowed: true, reason: null, tender_locked: false },
      correction: { allowed: true, reason: null },
      cancel: { allowed: false, reason: null },
      receipt: { allowed: true, reason: null },
    },
    receipts: [],
    next_copy_no: 1,
    unavailable: [],
    custom_data: { drawer: "2" },
    ...over,
  } as unknown as PaymentDetail;
}

describe("CR-161 W5 · Payment detail (S33) shows the answers read-only", () => {
  it("shows Drawer = 2 and offers no control to change it", async () => {
    const client = {
      get: vi.fn(async (path: string, options?: { query?: Record<string, unknown> }) => {
        if (path === "/custom-fields") {
          expect(options?.query).toMatchObject({ entity: "payments", screen: "S33", mode: "view" });
          return { status: 200, data: { entity: "payments", fields: [DRAWER] }, headers: new Headers() };
        }
        if (path.includes("/history")) {
          return { status: 200, data: { results: [], count: 0, next: null, previous: null }, headers: new Headers() };
        }
        if (path.startsWith("/payments/")) {
          return { status: 200, data: detail(), headers: new Headers() };
        }
        return { status: 200, data: { results: [], methods: [] }, headers: new Headers() };
      }),
      post: vi.fn(),
    } as unknown as ApiClient;
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazosbend/payments/PMT-2610-000001"]}>
            <Routes>
              <Route path="/:tenant/payments/:paymentRef" element={<PaymentDetailPage client={client} />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    const label = await screen.findByText("Drawer");
    const row = label.closest("div") as HTMLElement;
    expect(row.textContent).toContain("2");
    const section = label.closest("section") as HTMLElement;
    // Read-only: no input, no select, no button inside the custom section.
    expect(section.querySelectorAll("input, select, textarea, button").length).toBe(0);
    expect(drawerBox()).toBeNull();
  });
});
