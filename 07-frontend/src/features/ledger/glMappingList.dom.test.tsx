// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// CR:       CR-197-BRC10 — the ONE GL mapping list (Settings › Accounting ›
//           GL mapping). Design: https://claude.ai/artifact/Ue5p1oSzgQquUva1KZjf8Y v4.
// Rules:    BR-LED-800..802 · NFR-3 · BR-SHL-025 · B14 rules 15, 31, 33
// Note:     Mounted under the REAL path pattern (`/:tenant/settings/accounting/
//           mapping`), and the load-bearing assertions read the WIRE.
//           RED FIRST: before `GlMappingList.tsx` existed this file failed at
//           import (`Failed to resolve import "./GlMappingList"`).
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import { NotSentPanel, glMappingFixPath } from "@/features/billing/bulkRun/SendStep";
import { AccountingTab } from "@/features/tenancy/SettingsAccountingTab";
import i18n from "@/i18n";

import { GL_MAPPING_CREATE_LINKS } from "./GlMappingList";
import type { GlMappingPage, GlMappingRow } from "./glMappingEndpoints";

const TENANT = "ann-arbor-seu";

interface Sent {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

function row(over: Partial<GlMappingRow>): GlMappingRow {
  return {
    key: "x",
    group: "billing",
    type: "charge_code",
    mapped_for: "X",
    mapped_for_key: null,
    detail: null,
    detail_key: null,
    detail_params: {},
    account: null,
    status: "not_mapped",
    can_disable: false,
    can_enable: false,
    kinds: ["revenue"],
    ...over,
  };
}

const SOLAR = row({
  key: "svc:solar:usage:*",
  type: "service_revenue",
  mapped_for: "Solar",
  detail: "Usage · All classes",
  detail_key: "glMapping.detail.usage",
  detail_params: { cls: null },
  account: { id: "acc-4150", code: "4150", name: "Solar" },
  status: "mapped",
});
const SOLAR_COMMERCIAL = row({
  key: "svc:solar:usage:commercial",
  type: "service_revenue",
  mapped_for: "Solar",
  detail_key: "glMapping.detail.usage",
  detail_params: { cls: "Commercial" },
  account: { id: "acc-7110", code: "0117-080-1000-0000-7110", name: "Solar Service" },
  status: "mapped",
  can_disable: true,
});
const PENALTY = row({
  key: "chg:11111111-1111-4111-8111-111111111111",
  mapped_for: "PENALTY",
  detail: "Late Fee",
  detail_key: "glMapping.detail.otherCharge",
  detail_params: { name: "Late Fee" },
  account: { id: "acc-7218", code: "0117-080-1000-0000-7218", name: "Late Fees" },
  status: "mapped",
  can_disable: true,
});
const NSF = row({
  key: "chg:22222222-2222-4222-8222-222222222222",
  mapped_for: "NSF",
  detail: "Returned payment fee",
  detail_key: "glMapping.detail.otherCharge",
  detail_params: { name: "Returned payment fee" },
  can_disable: true,
});
const TAX = row({
  key: "tax:33333333-3333-4333-8333-333333333333",
  type: "tax",
  mapped_for: "MI Sales Tax",
  detail: "Michigan Sales Tax-Commercial",
  account: { id: "acc-7126", code: "0117-080-1000-0000-7126", name: "Bryant Sales Tax Collection" },
  status: "mapped",
});
const RECEIVABLES = row({
  key: "des:accounts_receivable",
  group: "payments",
  type: "system_account",
  mapped_for: "Receivables",
  mapped_for_key: "glMapping.for.accounts_receivable",
  detail_key: "glMapping.about.accounts_receivable",
  account: { id: "acc-1100", code: "1100", name: "Accounts receivable" },
  status: "mapped",
});

const PAGE: GlMappingPage = {
  count: 6,
  page: 1,
  per: 50,
  results: [SOLAR, SOLAR_COMMERCIAL, PENALTY, NSF, TAX, RECEIVABLES],
  counts: { total: 37, not_mapped: 6, disabled: 0 },
  gl_accounts: [],
};

function recordingClient(sent: Sent[], answer: (s: Sent) => Response | undefined = () => undefined): ApiClient {
  return createApiClient({
    tenant: TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const one = {
        method: init?.method ?? "GET",
        url: String(input),
        body: init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null,
      };
      sent.push(one);
      const given = answer(one);
      if (given !== undefined) {
        return given;
      }
      if (one.url.includes("/add-options")) {
        const typed = /type=([a-z_]+)/.exec(one.url)?.[1];
        return json({
          types: [
            { type: "service_revenue", group: "billing", open: 3 },
            { type: "charge_code", group: "billing", open: 1 },
            { type: "discount", group: "billing", open: 1 },
            { type: "tax", group: "billing", open: 0 },
          ],
          ...(typed === "charge_code"
            ? {
                items: [NSF],
                accounts: [{ id: "acc-7219", code: "0117-080-1000-0000-7219", name: "Fees", type: "revenue" }],
              }
            : typed
              ? { items: [], accounts: [] }
              : {}),
        });
      }
      if (one.url.includes("/edit-options")) {
        return json({ row: PENALTY, accounts: [{ id: "acc-7219", code: "7219", name: "Late fees (new)", type: "revenue" }] });
      }
      if (one.method === "POST") {
        return json({ ...NSF, status: "mapped" });
      }
      return json(PAGE);
    },
  });
}

function mount(client: ApiClient, entry = `/${TENANT}/settings/accounting/mapping`, readOnly = false) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[entry]}>
          <Routes>
            <Route
              path="/:tenant/settings/accounting/:sub"
              element={<AccountingTab readOnly={readOnly} client={client} sub="mapping" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => cleanup());

describe("Settings › Accounting › GL mapping — one list (CR-197-BRC10)", () => {
  it("draws the drawn columns, in order, and one row per mapping — never an id", async () => {
    const sent: Sent[] = [];
    mount(recordingClient(sent));
    await screen.findByText("PENALTY");
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent?.trim());
    const want = ["Group", "Type", "Mapped for", "Detail", "GL account", "Status", "Actions"];
    expect(headers.filter((h) => want.includes(h ?? ""))).toEqual(want);
    const penalty = screen.getByText("PENALTY").closest("tr") as HTMLElement;
    expect(within(penalty).getByText("Billing")).toBeInTheDocument();
    expect(within(penalty).getByText("Charge code")).toBeInTheDocument();
    expect(within(penalty).getByText("Other charge · Late Fee")).toBeInTheDocument();
    expect(within(penalty).getByText("0117-080-1000-0000-7218")).toBeInTheDocument();
    expect(within(penalty).getByText("Mapped")).toBeInTheDocument();
    const solar = screen.getAllByText("Solar")[0]?.closest("tr") as HTMLElement;
    expect(within(solar).getByText("Usage · All classes")).toBeInTheDocument();
    expect(screen.getByText("Usage · Commercial")).toBeInTheDocument();
    expect(screen.getByText("Payments & balances")).toBeInTheDocument();
    expect(screen.getAllByText("Not mapped").length).toBeGreaterThan(0);
    const page = document.body.textContent ?? "";
    expect(page).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
    expect(page).not.toContain("svc:");
    const list = sent.find((s) => s.method === "GET" && /\/ledger\/gl-mappings\/rows\?/.test(s.url));
    expect(list?.url).toMatch(/page=1/);
  });

  it("the three chips carry the server's counts and the not-mapped chip filters on the server", async () => {
    const sent: Sent[] = [];
    mount(recordingClient(sent));
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "6 not mapped" }));
    expect(screen.getByRole("button", { name: "37 mappings" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "0 disabled" })).toBeInTheDocument();
    await waitFor(() => expect(sent.some((s) => /f\.status=not_mapped/.test(s.url))).toBe(true));
  });

  it("a deep link opens the list filtered (Plans & Rates, the bill run's warning)", async () => {
    const sent: Sent[] = [];
    mount(recordingClient(sent), `/${TENANT}/settings/accounting/mapping?type=charge_code&q=PENALTY`);
    await screen.findByText("PENALTY");
    const list = sent.find((s) => /\/ledger\/gl-mappings\/rows\?/.test(s.url));
    expect(list?.url).toMatch(/f\.type=charge_code/);
    expect(list?.url).toMatch(/q=PENALTY/);
  });

  it("Add: types grouped, a fully mapped type greyed, unmapped items only, one create link, and the POST", async () => {
    const sent: Sent[] = [];
    mount(recordingClient(sent));
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "+ Add mapping" }));
    const dialog = await screen.findByRole("dialog");
    const type = within(dialog).getByLabelText(/^Type/) as HTMLSelectElement;
    await waitFor(() => expect(within(type).getByRole("option", { name: "Tax (all mapped)" })).toBeDisabled());
    expect(within(type).getByRole("group", { name: "Billing" })).toBeInTheDocument();
    await user.selectOptions(type, "charge_code");
    const item = within(dialog).getByLabelText(/^Mapped for/) as HTMLSelectElement;
    await waitFor(() => expect(within(item).getByRole("option", { name: "NSF · Other charge · Returned payment fee" })).toBeInTheDocument());
    expect(within(item).queryByRole("option", { name: /PENALTY/ })).toBeNull();
    const link = within(dialog).getByRole("link", { name: "New charge code ›" });
    expect(link.getAttribute("href")).toBe(`/${TENANT}${GL_MAPPING_CREATE_LINKS.charge_code}`);
    expect(within(dialog).getByText("Applies to new bills and payments.")).toBeInTheDocument();
    await user.selectOptions(item, NSF.key);
    const account = within(dialog).getByLabelText(/^GL account/);
    await user.click(account);
    await user.click(await within(dialog).findByText("0117-080-1000-0000-7219 Fees"));
    await user.click(within(dialog).getByRole("button", { name: "Save ✓" }));
    await waitFor(() => expect(sent.some((s) => s.method === "POST")).toBe(true));
    const post = sent.find((s) => s.method === "POST");
    expect(post?.url).toMatch(/\/ledger\/gl-mappings\/rows$/);
    expect(post?.body).toEqual({ act: "add", key: NSF.key, account_id: "acc-7219" });
  });

  it("Edit sends the new account; Disable confirms and posts the key; a tax has no Disable", async () => {
    const sent: Sent[] = [];
    mount(recordingClient(sent));
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Edit PENALTY" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("New bills and payments use it. Issued bills keep theirs.")).toBeInTheDocument();
    await user.click(within(dialog).getByLabelText(/^GL account/));
    await user.click(await within(dialog).findByText("7219 Late fees (new)"));
    await user.click(within(dialog).getByRole("button", { name: "Save ✓" }));
    await waitFor(() => expect(sent.some((s) => s.method === "POST")).toBe(true));
    expect(sent.find((s) => s.method === "POST")?.body).toEqual({ act: "edit", key: PENALTY.key, account_id: "acc-7219" });

    await user.click(screen.getByRole("button", { name: "Disable NSF" }));
    const confirm = await screen.findByRole("alertdialog");
    expect(within(confirm).getByText("Can't go on new bills. Issued bills keep it.")).toBeInTheDocument();
    await user.click(within(confirm).getByRole("button", { name: "Disable" }));
    await waitFor(() => expect(sent.some((s) => /\/rows\/disable$/.test(s.url))).toBe(true));
    expect(sent.find((s) => /\/rows\/disable$/.test(s.url))?.body).toEqual({ key: NSF.key });

    const tax = screen.getByText("MI Sales Tax").closest("tr") as HTMLElement;
    expect(within(tax).getByRole("button", { name: "Disable MI Sales Tax" })).toBeDisabled();
  });

  it("read-only staff see the controls disabled with their reason (BR-SHL-025)", async () => {
    mount(recordingClient([]), undefined, true);
    await screen.findByText("PENALTY");
    expect(screen.getByRole("button", { name: "+ Add mapping" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Edit PENALTY" })).toBeDisabled();
  });
});

describe("Phase 3 — the doors into the list (CR-197-BRC10)", () => {
  it("a bill-run break for a missing account opens the list filtered to that type", () => {
    expect(glMappingFixPath("charge_code_has_no_live_account")).toBe(
      "/settings/accounting/mapping?type=charge_code&status=not_mapped",
    );
    expect(glMappingFixPath("line_has_no_gl_account")).toBe(
      "/settings/accounting/mapping?type=service_revenue&status=not_mapped",
    );
    expect(glMappingFixPath("issue_failed_unexpectedly")).toBeNull();
    render(
      <NotSentPanel
        breaks={[
          { id: "b1", account_no: "A-1", account_id: null, reason: "charge_code_has_no_live_account" } as never,
          { id: "b2", account_no: "A-2", account_id: null, reason: "issue_failed_unexpectedly" } as never,
        ]}
        working={false}
        onRetry={() => undefined}
        onClose={() => undefined}
        t={(key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string}
        tenantHref={(path) => `/${TENANT}${path}`}
      />,
    );
    const links = screen.getAllByRole("link", { name: "Fix on GL mapping ›" });
    expect(links).toHaveLength(1);
    expect(links[0]?.getAttribute("href")).toBe(`/${TENANT}/settings/accounting/mapping?type=charge_code&status=not_mapped`);
  });
});
