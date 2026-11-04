// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9820 — PO ruling 2026-10-06 D4 (a), verbatim: *"Yes: add an
//          editable "PO on bills" field to the account's Billing preferences.
//          Bills drafted after the change print the new PO; bills already issued
//          keep the old one"*.
// ───────────────────────────────────────────────────────
// RED FIRST (law 7): on tip `4a75e8831` the dialog has no "PO on bills" field,
// so `getByLabelText("PO on bills")` throws in all three cases.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { AccountDetail } from "@/api/endpoints";

import { AccountPanelEditDialog } from "./AccountPanelEdits";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

type Sent = { method: string; path: string; body: unknown };

function recordingClient(sent: Sent[]): ApiClient {
  const answer = <T,>(data: unknown) => ({ data: data as T, status: 200, headers: new Headers() });
  return {
    request: <T,>(path: string, options?: { method?: string; body?: unknown }) => {
      sent.push({ method: options?.method ?? "GET", path, body: options?.body });
      return Promise.resolve(answer<T>({}));
    },
    get: <T,>(path: string) => {
      sent.push({ method: "GET", path, body: undefined });
      return Promise.resolve(answer<T>({ results: [], page: 1, per: 200, total: 0 }));
    },
  } as unknown as ApiClient;
}

function mount(sent: Sent[], po: string | null) {
  const detail = {
    id: "a-57",
    account_no: "AC-2026-00057",
    autopay: false,
    paperless: false,
    sms_reminders: false,
    preferred_language: null,
    po_number: po,
    contacts: [{ id: "c-1", full_name: "Cedar Ford Independent School District" }],
    addresses: [],
    custom_data: {},
  } as unknown as AccountDetail;
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <AccountPanelEditDialog
        detail={detail}
        group="billingPrefs"
        client={recordingClient(sent)}
        t={t}
        dateFormat="MM/DD/YYYY"
        onClose={() => undefined}
        onSaved={() => undefined}
      />
    </QueryClientProvider>,
  );
}

describe("DEF-CUS-9820 — PO on bills is edited in Billing preferences", () => {
  it("shows the current PO and sends only the new one, PO-2026-118 → PO-2027-044", async () => {
    const sent: Sent[] = [];
    const user = userEvent.setup();
    mount(sent, "PO-2026-118");
    const field = screen.getByLabelText(t("customers.moveIn.review.po"));
    expect(field).toHaveValue("PO-2026-118");
    await user.clear(field);
    await user.type(field, " PO-2027-044 ");
    // The recap names the change before it commits (B14 rule 11).
    expect(screen.getByText("PO-2027-044")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: t("customers.account.edit.save") }));
    const patch = sent.find((call) => call.method === "PATCH");
    expect(patch?.path).toBe("/accounts/a-57");
    expect(patch?.body).toEqual({ po_number: "PO-2027-044" });
  });

  it("blank clears it, and the recap says None", async () => {
    const sent: Sent[] = [];
    const user = userEvent.setup();
    mount(sent, "PO-2026-118");
    await user.clear(screen.getByLabelText(t("customers.moveIn.review.po")));
    expect(screen.getByText(t("customers.moveIn.review.none"))).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: t("customers.account.edit.save") }));
    expect(sent.find((call) => call.method === "PATCH")?.body).toEqual({ po_number: "" });
  });

  it("an account with no PO can be given one, and an untouched PO is not sent", async () => {
    const sent: Sent[] = [];
    const user = userEvent.setup();
    mount(sent, null);
    const field = screen.getByLabelText(t("customers.moveIn.review.po"));
    expect(field).toHaveValue("");
    await user.click(screen.getByLabelText(t("customers.account.portal.paperless")));
    await user.click(screen.getByRole("button", { name: t("customers.account.edit.save") }));
    expect(sent.find((call) => call.method === "PATCH")?.body).toEqual({ paperless: true });
  });
});
