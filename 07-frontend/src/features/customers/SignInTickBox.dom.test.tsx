// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  DEF-CWP-10400 — "Also use this as the portal sign-in email" (PO
//          2026-10-22, closes OQ-CUS-12350): a tick box on BOTH clerk doors
//          that change a customer's email, unticked by default, shown only
//          when there is a portal login to move.
// Rules:   decision log 2026-10-22 "Who moves the portal sign-in email…" and
//          "…built: the judgments" items 1–4 · hard-won law 2 (a control that
//          writes nothing looks identical to one that works, so the PATCH
//          body is asserted key for key) · law 2's fixture clause (mounted
//          under a real route pattern).
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";
import type { ApiClient } from "@/api/client";
import type { AccountDetail } from "@/api/endpoints";

import { AccountPanelEditDialog } from "./AccountPanelEdits";
import { CustomerEditDialog } from "./CustomerEditDialog";
import type { CustomerRow } from "./customerEndpoints";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const LABEL = () => t("customers.customer.edit.alsoSignIn");

type Sent = { method: string; path: string; body: unknown };

function recordingClient(sent: Sent[]): ApiClient {
  const answer = <T,>(data: unknown) => ({ data: data as T, status: 200, headers: new Headers() });
  const remember = <T,>(method: string, path: string, body: unknown) => {
    sent.push({ method, path, body });
    return Promise.resolve(answer<T>({ accounts_updated: 1, account_ids: [] }));
  };
  return {
    request: <T,>(path: string, options?: { method?: string; body?: unknown }) =>
      remember<T>(options?.method ?? "GET", path, options?.body),
    get: <T,>() => Promise.resolve(answer<T>({ results: [], page: 1, per: 200, total: 0 })),
    patch: <T,>(path: string, body?: unknown) => remember<T>("PATCH", path, body),
    post: <T,>(path: string, body?: unknown) => remember<T>("POST", path, body),
    put: <T,>(path: string, body?: unknown) => remember<T>("PUT", path, body),
    del: () => Promise.reject(new Error("unplanned del()")),
    pollJob: () => Promise.reject(new Error("unplanned pollJob()")),
  } as unknown as ApiClient;
}

/** Mounted under the route the product mounts these on, never bare. */
function routed(node: ReactNode, at: string, pattern: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[at]}>
        <Routes>
          <Route path={pattern} element={node} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function customer(over: Partial<CustomerRow> = {}): CustomerRow {
  return {
    id: "01a05a61-bedb-7607-90a5-53ace7bb0e8f",
    customer_no: "C-00417",
    display_name: "Alvarez, Maria",
    kind: "person",
    external_ref: null,
    phone: "512-555-0142",
    email: "maria.alvarez@example.test",
    contact_by: "email",
    identity: {
      date_of_birth: null,
      ssn_held: false,
      ssn_last4: null,
      driving_licence_held: false,
      driving_licence_last4: null,
      tax_id_held: false,
      tax_id_last4: null,
    },
    account_count: 1,
    accounts: [],
    ...over,
  };
}

function mountCustomer(sent: Sent[], over: Partial<CustomerRow> = {}) {
  return routed(
    <CustomerEditDialog
      row={customer(over)}
      t={t}
      dateFormat="MM/DD/YYYY"
      client={recordingClient(sent)}
      onClose={() => undefined}
      onSaved={() => undefined}
    />,
    "/pine-hill/customers",
    "/:tenant/customers",
  );
}

function account(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: "a-11812",
    account_no: "AC-2026-00071",
    contacts: [
      {
        id: "c-1",
        full_name: "Maria Alvarez",
        email: "maria.alvarez@example.test",
        phone: "512-555-0142",
        is_primary: true,
      },
    ],
    addresses: [],
    custom_data: {},
    portal_access: { logins: 1, locked: 0, last_sign_in: null, unreadable: [] },
    ...over,
  } as unknown as AccountDetail;
}

function mountAccount(sent: Sent[], over: Partial<AccountDetail> = {}) {
  return routed(
    <AccountPanelEditDialog
      detail={account(over)}
      group="customer"
      client={recordingClient(sent)}
      t={t}
      dateFormat="MM/DD/YYYY"
      onClose={() => undefined}
      onSaved={() => undefined}
    />,
    "/pine-hill/accounts/a-11812",
    "/:tenant/accounts/:accountId",
  );
}

const patches = (sent: Sent[]) => sent.filter((one) => one.method === "PATCH");

describe("Edit customer — the sign-in tick box", () => {
  it("is offered, UNTICKED, when the customer has a portal login", () => {
    mountCustomer([], { has_portal_login: true });
    const box = screen.getByLabelText(LABEL());
    expect(box).not.toBeChecked();
  });

  it("is not offered when there is no login to move", () => {
    mountCustomer([], { has_portal_login: false });
    expect(screen.queryByLabelText(LABEL())).toBeNull();
  });

  it("unticked: the email moves alone and nothing about the sign-in is sent", async () => {
    const sent: Sent[] = [];
    const user = userEvent.setup();
    mountCustomer(sent, { has_portal_login: true });
    const email = screen.getByLabelText(t("customers.customer.edit.email"));
    await user.clear(email);
    await user.type(email, "maria.new@example.test");
    await user.click(screen.getByRole("button", { name: t("customers.customer.edit.submit") }));
    await waitFor(() => expect(patches(sent)).toHaveLength(1));
    expect(patches(sent)[0]!.body).toEqual({ email: "maria.new@example.test", custom_data: {} });
  });

  it("ticked: the flag travels WITH the email, and the consequence says the sign-in moves", async () => {
    const sent: Sent[] = [];
    const user = userEvent.setup();
    mountCustomer(sent, { has_portal_login: true });
    expect(screen.getByText(t("customers.customer.edit.effectBody"))).toBeTruthy();
    await user.click(screen.getByLabelText(LABEL()));
    expect(screen.getByText(t("customers.customer.edit.effectBodySignIn"))).toBeTruthy();
    // Email untouched: the clerk moves the sign-in to the email already on file.
    await user.click(screen.getByRole("button", { name: t("customers.customer.edit.submit") }));
    await waitFor(() => expect(patches(sent)).toHaveLength(1));
    expect(patches(sent)[0]!.body).toEqual({
      email: "maria.alvarez@example.test",
      portal_sign_in: true,
      custom_data: {},
    });
  });
});

describe("Account → Customer pencil — the sign-in tick box", () => {
  it("is offered when exactly one login holds the account, and sends the flag when ticked", async () => {
    const sent: Sent[] = [];
    const user = userEvent.setup();
    mountAccount(sent);
    const email = screen.getByLabelText(t("customers.account.field.email"));
    await user.clear(email);
    await user.type(email, "maria.new@example.test");
    await user.click(screen.getByLabelText(LABEL()));
    await user.click(screen.getByRole("button", { name: t("customers.account.edit.save") }));
    await waitFor(() => expect(patches(sent)).toHaveLength(1));
    expect(patches(sent)[0]!.body).toMatchObject({
      email: "maria.new@example.test",
      portal_sign_in: true,
    });
  });

  it("is not offered on a joint account with two logins, nor with none", () => {
    mountAccount([], {
      portal_access: { logins: 2, locked: 0, last_sign_in: null, unreadable: [] },
    } as Partial<AccountDetail>);
    expect(screen.queryByLabelText(LABEL())).toBeNull();
    cleanup();
    mountAccount([], {
      portal_access: { logins: 0, locked: 0, last_sign_in: null, unreadable: [] },
    } as Partial<AccountDetail>);
    expect(screen.queryByLabelText(LABEL())).toBeNull();
  });
});
