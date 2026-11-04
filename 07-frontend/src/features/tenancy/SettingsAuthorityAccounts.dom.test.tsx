// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 2 task 3 — Settings › Accounting › Authority
//           accounts (CR §7 item 1).
// Rules:    B14 rule 31 (no id on screen) · NFR-3 (the list asks for a page)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { AuthorityAccountsPanel, authorityAccountPayload, draftOf } from "./SettingsAuthorityAccounts";
import { ACCOUNTING_SUB_TABS } from "./SettingsAccountingTab";

const t = (key: string) => i18n.t(key);

const COMPTROLLER = {
  id: "0190aaaa-0000-7000-8000-000000000001",
  authority_name: "TX Comptroller",
  account_number: "32-1180455",
  jurisdiction_id: null,
  active: true,
};

const AUTHORITIES = [
  { id: "j-state", name: "State Department of Revenue", authority: null, level: "state", reference_no: null },
  { id: "j-wapello", name: "Wapello County", authority: null, level: "county", reference_no: null },
];

interface Call {
  method: "GET" | "POST" | "PATCH";
  path: string;
  query?: unknown;
  body?: unknown;
}

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { status, data, etag: null, notModified: false };
}

function stubClient(calls: Call[], rows: unknown[]): ApiClient {
  return {
    get: async <T,>(path: string, options?: { query?: unknown }): Promise<ApiResponse<T>> => {
      calls.push({ method: "GET", path, query: options?.query });
      if (path === "/settings/authority-accounts") {
        return ok({ count: rows.length, next: null, previous: null, results: rows } as T);
      }
      if (path === "/tax-jurisdictions") {
        return ok({ count: AUTHORITIES.length, next: null, previous: null, results: AUTHORITIES } as T);
      }
      throw new Error(`unstubbed GET ${path}`);
    },
    post: async <T,>(path: string, body?: unknown): Promise<ApiResponse<T>> => {
      calls.push({ method: "POST", path, body });
      return ok({ ...COMPTROLLER, ...(body as object), id: "new" } as T, 201);
    },
    patch: async <T,>(path: string, body?: unknown): Promise<ApiResponse<T>> => {
      calls.push({ method: "PATCH", path, body });
      return ok({ ...COMPTROLLER, ...(body as object) } as T);
    },
  } as unknown as ApiClient;
}

function mount(calls: Call[], rows: unknown[], readOnly = false) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthorityAccountsPanel readOnly={readOnly} client={stubClient(calls, rows)} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("Settings › Accounting › Authority accounts", () => {
  it("is a sub-tab of Settings › Accounting, after the three that were there", () => {
    expect(ACCOUNTING_SUB_TABS).toEqual(["chart", "mapping", "controls", "authorities"]);
  });

  it("lists each account by authority and number, asks for a PAGE, and shows no id", async () => {
    const calls: Call[] = [];
    const view = mount(calls, [COMPTROLLER]);
    expect(await screen.findByText("TX Comptroller")).toBeInTheDocument();
    expect(screen.getByText("32-1180455")).toBeInTheDocument();
    expect(screen.getByText(t("settings.accounting.authorities.active"))).toBeInTheDocument();
    expect(calls[0].query).toMatchObject({ page: 1, per: 50 });
    expect(view.container.innerHTML).not.toContain(COMPTROLLER.id);
  });

  it("says so when the utility has recorded none", async () => {
    mount([], []);
    expect(await screen.findByText(t("settings.accounting.authorities.empty"))).toBeInTheDocument();
  });

  it("adds a number through POST with the PICKED authority and the trimmed number (DEF-RAT-10027)", async () => {
    const calls: Call[] = [];
    mount(calls, []);
    await userEvent.click(
      await screen.findByRole("button", { name: t("settings.accounting.authorities.add") }),
    );
    // By the field ids the form gives them — the labels share words with the
    // panel's own title, so a text query would match twice.
    const authority = document.getElementById("authority_jurisdiction") as HTMLSelectElement;
    expect(authority.tagName).toBe("SELECT");
    await screen.findByRole("option", { name: "Wapello County" });
    await userEvent.selectOptions(authority, "j-wapello");
    await userEvent.type(document.getElementById("account_number") as HTMLElement, " WC-77 ");
    await userEvent.click(
      screen.getByRole("button", { name: t("settings.accounting.authorities.save") }),
    );
    await waitFor(() => expect(calls.some((call) => call.method === "POST")).toBe(true));
    const posted = calls.find((call) => call.method === "POST");
    expect(posted?.path).toBe("/settings/authority-accounts");
    expect(posted?.body).toEqual({
      jurisdiction_id: "j-wapello",
      authority_name: "Wapello County",
      account_number: "WC-77",
      active: true,
    });
  });

  it("the add control is refused with its reason for a read-only role", async () => {
    mount([], [COMPTROLLER], true);
    const add = await screen.findByRole("button", {
      name: t("settings.accounting.authorities.add"),
    });
    expect(add).toBeDisabled();
  });

  it("DEF-RAT-10027 · the section and its pop-up are headed Tax filing accounts, never GL code mapping", async () => {
    const view = mount([], [COMPTROLLER]);
    expect(await screen.findByRole("heading", { name: "Tax filing accounts" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: t("settings.accounting.authorities.add") }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Tax filing accounts");
    expect(view.baseElement).not.toHaveTextContent(t("settings.accounting.kicker"));
  });

  it("DEF-RAT-10027 · a typed row keeps its name until linked, and editing links it", async () => {
    const calls: Call[] = [];
    mount(calls, [COMPTROLLER]);
    await userEvent.click(await screen.findByRole("button", { name: t("settings.accounting.authorities.edit") }));
    const authority = document.getElementById("authority_jurisdiction") as HTMLSelectElement;
    // Unpicked, the box shows the name it was typed with.
    expect(authority.options[authority.selectedIndex].text).toBe("TX Comptroller");
    await screen.findByRole("option", { name: "State Department of Revenue" });
    await userEvent.selectOptions(authority, "j-state");
    await userEvent.click(screen.getByRole("button", { name: t("settings.accounting.authorities.save") }));
    await waitFor(() => expect(calls.some((call) => call.method === "PATCH")).toBe(true));
    expect(calls.find((call) => call.method === "PATCH")?.body).toEqual({
      jurisdiction_id: "j-state",
      authority_name: "State Department of Revenue",
      account_number: "32-1180455",
      active: true,
    });
  });

  it("DEF-RAT-10027 · a typed row saved without picking keeps its typed name", async () => {
    const calls: Call[] = [];
    mount(calls, [COMPTROLLER]);
    await userEvent.click(await screen.findByRole("button", { name: t("settings.accounting.authorities.edit") }));
    await userEvent.click(screen.getByRole("button", { name: t("settings.accounting.authorities.save") }));
    await waitFor(() => expect(calls.some((call) => call.method === "PATCH")).toBe(true));
    expect(calls.find((call) => call.method === "PATCH")?.body).toEqual({
      authority_name: "TX Comptroller",
      account_number: "32-1180455",
      active: true,
    });
  });

  it("a draft of an existing row round-trips into the PATCH payload", () => {
    expect(authorityAccountPayload({ ...draftOf(COMPTROLLER), active: false })).toEqual({
      authority_name: "TX Comptroller",
      account_number: "32-1180455",
      active: false,
    });
  });
});
