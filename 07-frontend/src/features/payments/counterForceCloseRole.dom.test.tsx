// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-PAY-10778 — Payments › Counter offered the billing clerk
//          "Force close" on a till, and the server refuses it to anyone but a
//          System Admin: a live control behind a refusal.
// Ruling:  PO 2026-10-31 P9 = A — greyed out with "Only an administrator can
//          do this." for roles that cannot use it, as Reverse is.
// Red first (law 7): on the tip, the clerk case found the button ENABLED.
// What would pass wrongly: a button disabled for everyone — the admin case
//          asserts it is live for a System Admin.
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import type { CounterRow } from "@/api/counterEndpoints";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { CountersTab } from "./CountersTab";

afterEach(cleanup);

const TENANT = "brazosbend";
const t = (key: string) => i18n.t(key);

const OPEN_TILL: CounterRow = {
  code: "CTR-261031-CM",
  owner_name: "Carl Mendez",
  service_centre_name: "Main counter",
  opened_at: "2026-10-31T08:55:00Z",
  closed_at: null,
  close_kind: null,
  declared_at: null,
  declared_by_name: null,
  payment_count: 3,
  taken_total: "120.0000",
  counted_total: null,
  difference: null,
  currency: "USD",
} as CounterRow;

function client(role: string): ApiClient {
  const answer = async (path: string) => {
    if (path === "/me/permissions") {
      return { status: 200, data: { role, role_name: role, permissions: [] } };
    }
    if (path === "/me") {
      return { status: 200, data: { id: "u", full_name: "Carl Mendez", email: "c@x", phone: null, role, role_name: role, must_change_password: false } };
    }
    if (path.startsWith("/counters")) {
      return {
        status: 200,
        data: {
          rows: [OPEN_TILL],
          count: 1,
          totals: {
            open_now: 1,
            open_owner_names: ["Carl Mendez"],
            taken_today: "120.0000",
            taken_today_payment_count: 3,
            not_counted: 0,
            not_counted_oldest: null,
            difference_this_week: "0.0000",
            currency: "USD",
          },
        },
      };
    }
    return { status: 200, data: { results: [], count: 0, next: null, previous: null } };
  };
  return { request: answer, get: answer, post: answer, put: answer, patch: answer, del: answer } as unknown as ApiClient;
}

function mount(role: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/payments/counter`]}>
          <Routes>
            <Route
              path="/:tenant/payments/counter"
              element={
                <CountersTab
                  client={client(role)}
                  timeZone="America/Chicago"
                  dateFormat="MM/DD/YYYY"
                  writeBlockedReason={null}
                  onOpenCounter={() => undefined}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function forceClose() {
  const label = await screen.findByText(t("payments.counter.action.forceClose"));
  return label.closest("button") as HTMLButtonElement;
}

describe("DEF-PAY-10778 · Force close is greyed for a role that cannot use it (P9 = A)", () => {
  it("a billing clerk sees it disabled, with the reason", async () => {
    mount("billing_clerk");
    const button = await forceClose();
    await screen.findByTitle(t("payments.counter.forceCloseAdminOnly"));
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("title", "Only an administrator can do this.");
  });

  it("a System Admin can still press it", async () => {
    mount("system_admin");
    const button = await forceClose();
    expect(button).toBeEnabled();
  });
});
