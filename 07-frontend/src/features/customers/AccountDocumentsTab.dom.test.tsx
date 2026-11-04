// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9147 — a clerk could FILE a document on an account and not
//          OPEN it: the Documents tab's row carried a bin and nothing else,
//          while the API served the file all along (hard-won law 2's mirror).
// Rules:   B14 rule 15 (row actions are icons, view first, at most two) ·
//          rule 43 (the opener is the kit's, not a second one written here).
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, ASKED FIRST** (law 7 habit 2):
//   * *"an Open control exists"* passes over a control that opens nothing —
//     so the case CLICKS it and reads the address the browser was sent to;
//   * *"the address contains /documents/"* passes over the bearer-link route,
//     which the developer's store answers with `file://` — so the case asserts
//     the CONTENT route, under THIS tenant, for THIS row, asking to VIEW;
//   * *"it is enabled"* passes over a disabled icon whose click does nothing —
//     the click is what is asserted, and a disabled button never fires it.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createApiClient } from "@/api/client";
import type { AccountDocument } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { AccountDocumentsTab, accountDocumentContentPath } from "./AccountDocumentsTab";

const TENANT = "brazosbend";
const ACCOUNT = "3f1a9c2e-0000-7000-8000-000000000001";
const DOC = "0198f3c2-0000-7000-8000-00000000000a";

function row(overrides: Partial<AccountDocument> = {}): AccountDocument {
  return {
    id: DOC,
    name: "signed-lease.pdf",
    doc_type: "contract",
    uploaded_at: "2026-10-02T14:02:00Z",
    uploaded_by_name: "Sam Reyes",
    uploaded_by_process: null,
    size_bytes: 696,
    content_type: "application/pdf",
    ...overrides,
  };
}

function mount(rows: AccountDocument[]) {
  const client = createApiClient({
    tenant: TENANT,
    // Two reads reach the network: the clerk's permission row (the tab's
    // write gate) and the list itself. Each gets its own answer.
    fetchImpl: async (input) => {
      const body = String(input).includes("/me/permissions")
        ? { permissions: [{ code: "premises_accounts", access: "Full" }] }
        : { count: rows.length, results: rows };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, AND THE WINDOW AT THE SAME
  // ADDRESS.** `openDocumentContent` reads the tenant from `window.location`,
  // exactly as every API call does; a bare harness would build `//…`.
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/accounts/${ACCOUNT}?tab=documents`]}>
          <Routes>
            <Route
              path="/:tenant/accounts/:accountId"
              element={<AccountDocumentsTab accountId={ACCOUNT} client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

let opened: ReturnType<typeof vi.fn>;

beforeEach(() => {
  window.history.pushState({}, "", `/${TENANT}/accounts/${ACCOUNT}?tab=documents`);
  opened = vi.fn();
  vi.spyOn(window, "open").mockImplementation(((...args: unknown[]) => {
    opened(...args);
    return null;
  }) as typeof window.open);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("DEF-CUS-9147 · a filed document can be OPENED", () => {
  it("the content address is this account's, this document's, under the API", () => {
    expect(accountDocumentContentPath(ACCOUNT, DOC)).toBe(
      `/accounts/${ACCOUNT}/documents/${DOC}/content`,
    );
  });

  it("each row carries Open, and pressing it opens the document's content route", async () => {
    mount([row()]);
    const tr = (await screen.findByText("signed-lease.pdf")).closest("tr");
    expect(tr).not.toBeNull();
    const open = within(tr as HTMLElement).getByRole("button", { name: "Open" });
    expect(open).toBeEnabled();

    await userEvent.click(open);

    expect(opened).toHaveBeenCalledTimes(1);
    const [url, target, features] = opened.mock.calls[0] as [string, string, string];
    expect(url).toMatch(
      new RegExp(`/api/${TENANT}/accounts/${ACCOUNT}/documents/${DOC}/content\\?as=view$`),
    );
    // A new tab, and never a handle back on the app that opened it.
    expect(target).toBe("_blank");
    expect(features).toContain("noopener");
  });

  it("view comes first and Remove last — the order every list draws (B14 rule 15)", async () => {
    mount([row({ doc_type: "correspondence" })]);
    const tr = (await screen.findByText("signed-lease.pdf")).closest("tr") as HTMLElement;
    const labels = within(tr)
      .getAllByRole("button")
      .map((button) => button.getAttribute("aria-label"));
    expect(labels).toEqual(["Open", "Remove"]);
  });

  it("an audit-locked contract still OPENS — the lock is on removal, not on reading", async () => {
    mount([row({ doc_type: "contract" })]);
    const tr = (await screen.findByText("signed-lease.pdf")).closest("tr") as HTMLElement;
    expect(within(tr).getByRole("button", { name: "Remove" })).toBeDisabled();
    expect(within(tr).getByRole("button", { name: "Open" })).toBeEnabled();
  });
});
