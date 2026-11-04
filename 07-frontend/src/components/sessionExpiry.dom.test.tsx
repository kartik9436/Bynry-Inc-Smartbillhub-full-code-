// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-6378 (2026-09-23) — the PO, on production v2.344.0 as System
//          Admin: *"whenever user session expire system show this message - You
//          don't have access to this. Your role can't open Payments. … we need to
//          say your session is expired and login again. this happens many
//          places"*.
// Rules:   BR-SHL-009 (no tenant data readable once the session is gone) ·
//          A18 §6 (the denial is for a ROLE refusal, and only for that) ·
//          hard-won law 6 (assert RENDERED OUTPUT) · law 7 (case (a) was run RED
//          on the unchanged tip before the fix existed)
// ───────────────────────────────────────────────────────
// ⚠ **THE REAL SHELL, THE REAL ROUTES AND THE PRODUCT'S OWN QueryClient.**
// The defect was a classifier shared by 78 screens, so a test of the classifier
// alone would prove the function and say nothing about what a clerk sees. This
// mounts `APP_ROUTES` at `/brazosbend/payments` through `createQueryClient()` —
// the one `App.tsx` builds — and answers every request the page makes with the
// status under test, exactly as a server does once a session has died.
//
// The shell's own boot reads are SEEDED, not answered: they are what the page
// had already loaded before the session ended, and the question is what the
// NEXT request does.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClientProvider } from "@tanstack/react-query";
import type { QueryClient } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { APP_ROUTES } from "@/App";
import type { MyPermissions, SessionUser, ShellDisplay } from "@/api/endpoints";
import { createQueryClient, queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

afterEach(cleanup);

const TENANT = "brazosbend";

const ADMIN: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@brazosbend.example",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [
    { code: "payments_record", label: "Payments", access: "Full" },
    { code: "finance_reconcile_export", label: "Finance", access: "Full" },
  ],
};

const DISPLAY: ShellDisplay = {
  regional: {
    country: "United States",
    timezone: "America/Chicago",
    language: "en-US",
    first_day_of_week: "sunday",
    currency: "USD",
    number_format: "1,234.56",
    date_format: "MM/DD/YYYY",
    time_format: "12-hour",
  },
  company: {
    legal_name: "Brazos Bend Utility District No. 1",
    dba_name: "Brazos Bend Utilities",
    has_logo: false,
    logo_ref: null,
    mark: { letters: "BB", background_hex: null, ink_hex: null, contrast_ratio: null },
    brand_primary_hex: null,
  },
  period: null,
};

/**
 * The server, standing in for every request the page makes.
 *
 * ⚠ **INSTALLED BEFORE ANY IMPORT, AND THAT IS NOT STYLE.** `api/client.ts`
 * builds the app-wide client when the module loads and captures `fetch` at that
 * moment, so a `vi.stubGlobal("fetch", …)` inside a test replaces a function
 * nobody calls any more. The first draft of this file did exactly that: every
 * case reached jsdom's own fetch, which failed with no status at all, and the
 * 403 case rendered *"the summary could not be loaded"* instead of the denial —
 * a harness that could not tell a 401 from a 403 from a dropped connection.
 * `vi.hoisted` runs before the imports, so the client captures THIS function.
 */
const server = vi.hoisted(() => {
  const state = { status: 401, calls: [] as string[] };
  const envelope: Record<number, { code: string; message_key: string }> = {
    // What `core/errors.py` answers for each status (G1).
    401: { code: "AUTH-001", message_key: "errors.auth-001" },
    403: { code: "AUTH-002", message_key: "errors.auth-002" },
  };
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    state.calls.push(String(input));
    return new Response(JSON.stringify({ ...envelope[state.status], params: {}, trace_id: "t1" }), {
      status: state.status,
      headers: { "Content-Type": "application/json" },
    });
  }) as typeof fetch;
  return state;
});

/** Every request the page makes gets `status` — a dead session refuses them all. */
function serverAnswers(status: 401 | 403): void {
  server.status = status;
  server.calls = [];
}

function openPayments(entry = `/${TENANT}/payments`): { queryClient: QueryClient } {
  // The transport reads the tenant off the BROWSER's address, not the router's
  // (`currentTenant()` in api/client.ts), so the address bar is set too — or
  // every tenant-scoped read throws before it is sent and no status is ever
  // under test.
  window.history.replaceState(null, "", entry);
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.me, ADMIN);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(queryKeys.shellDisplay, DISPLAY);
  queryClient.setQueryData(queryKeys.inAppMessages, { count: 0, results: [] });
  const router = createMemoryRouter(APP_ROUTES, { initialEntries: [entry] });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { queryClient };
}

/** Either answer the page can settle on — the one this defect is about, or the fix. */
const SETTLED = /^(Session expired|You don't have access to this\.)$/;

describe("DEF-SHL-6378 — an expired session is not a permission problem", () => {
  it("(a) a 401 on the Payments list says Session expired, NOT the role denial", async () => {
    serverAnswers(401);
    openPayments();
    // Wait for the page to SETTLE on one of the two answers before judging it,
    // so the unchanged build fails on the PO's own words rather than on a
    // timeout that could mean anything.
    await waitFor(() => expect(screen.queryByText(SETTLED)).toBeInTheDocument());
    // The PO's exact complaint, stated as its own negative so a regression
    // names itself rather than failing a positive match somewhere else.
    expect(screen.queryByText("You don't have access to this.")).not.toBeInTheDocument();
    expect(screen.queryByText(/Your role can't open Payments/)).not.toBeInTheDocument();
    expect(screen.getByText("Session expired")).toBeInTheDocument();
    expect(screen.getByText("Sign in again to continue.")).toBeInTheDocument();
  });

  it("(a) BR-SHL-009 — the tenant's data is gone from the cache before the state shows", async () => {
    serverAnswers(401);
    const { queryClient } = openPayments();
    await screen.findByText("Session expired");
    expect(queryClient.getQueryData(queryKeys.me)).toBeUndefined();
    expect(queryClient.getQueryData(queryKeys.myPermissions)).toBeUndefined();
    expect(queryClient.getQueryData(queryKeys.shellDisplay)).toBeUndefined();
    // …and no shell chrome that was drawn from it survives on screen.
    expect(screen.queryByText("Brazos Bend Utilities")).not.toBeInTheDocument();
    expect(screen.queryByText("Dana Whitfield")).not.toBeInTheDocument();
  });

  it("(b) a 403 still shows the role denial, exactly as before", async () => {
    serverAnswers(403);
    openPayments();
    expect(await screen.findByText("You don't have access to this.")).toBeInTheDocument();
    expect(screen.getByText("Your role can't open Payments. Ask a System Admin if you need it.")).toBeInTheDocument();
    expect(screen.queryByText("Session expired")).not.toBeInTheDocument();
  });

  it("(c) Sign in goes to THIS tenant's sign-in page and carries the page back", async () => {
    serverAnswers(401);
    openPayments(`/${TENANT}/payments?q=smith`);
    const link = await screen.findByRole("link", { name: "Sign in →" });
    expect(link).toHaveAttribute("href", `/${TENANT}/signin?next=%2Fpayments%3Fq%3Dsmith`);
  });
});
