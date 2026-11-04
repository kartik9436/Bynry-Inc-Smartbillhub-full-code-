// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Change:   CR-196-BRC10 (PO 2026-10-29) — a System Admin may change a chart
//           account's CODE even when it is used; a confirmation counts what it
//           touches; Q2's warning names an exported or closed month; the old
//           code is shown as "formerly"; TYPE stays locked; a clerk reads the
//           code locked.  Screen: SET-11 · S56
// Rules:    BR-LED-040 (amended for the code) · B14 rules 6, 31, 33, 43
// ─────────────────────────────────────────────────────────────────────────
/**
 * The catalogue is mocked to the KEY (the `chartDialogs.dom.test.tsx`
 * precedent — eleven 1.3MB catalogues time the file out), so these cases
 * assert WHICH sentence renders and WHERE; G33 and G15 own the words.
 */
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: "en" } }),
  Trans: ({ i18nKey }: { i18nKey: string }) => i18nKey,
  initReactI18next: { type: "3rdParty", init: () => undefined },
}));

import type { ApiClient } from "@/api/client";
import type { LedgerAccountUsage } from "@/api/endpoints";

import { ToastProvider } from "@/components/Toast";

import {
  ChartOfAccountsPanel,
  codeChangeConsequence,
  codeChangeWarning,
} from "./ChartOfAccountsPanel";
import { TrialBalanceTable } from "./GeneralLedgerPage";

/** Key plus its params, so a case can see WHICH month a warning names. */
const t = (key: string, params?: Record<string, unknown>) =>
  params === undefined ? key : `${key} ${JSON.stringify(params)}`;

const SOLAR = {
  account_id: "acc-4150",
  code: "4150",
  name: "Solar",
  type: "revenue",
  category: null,
  designation: null,
  status: "active",
  qbo_ref: null,
  xero_ref: null,
  created_at: null,
  finance_signed: true,
  seeded: true,
  former_code: null,
  code_history: [],
};

const RENAMED = {
  ...SOLAR,
  account_id: "acc-7110",
  code: "0117-080-1000-0000-7110",
  former_code: "4150",
};

const CHART = {
  rows: [SOLAR, RENAMED],
  types: ["asset", "liability", "equity", "revenue", "expense"],
  categories: [],
  designations: ["cash"],
  roles_needing_account: [],
  pending_finance_re_sign: [],
  pending_finance_re_sign_cost: [],
  pending_finance_re_sign_books: [],
};

const USED: LedgerAccountUsage = {
  bills: 12,
  payments: 3,
  journal_lines: 40,
  closed_period: { start: "2026-09-01", end: "2026-09-30" },
  exported_period: { start: "2026-09-01", end: "2026-09-30", target: "csv" },
};

function aClient(role: string, usage: LedgerAccountUsage = USED) {
  const patches: { path: string; body: Record<string, unknown> }[] = [];
  const client = {
    get: async (path: string) => {
      if (path === "/me/permissions") {
        return { data: { role, role_name: role, permissions: [] } };
      }
      if (path.startsWith("/ledger/accounts/")) {
        return { data: { ...SOLAR, usage } };
      }
      return { data: CHART };
    },
    patch: async (path: string, body: Record<string, unknown>) => {
      patches.push({ path, body });
      return { data: { ...SOLAR, code: body.code ?? SOLAR.code } };
    },
    post: async () => ({ data: {} }),
    put: async () => ({ data: {} }),
    delete: async () => ({ data: {} }),
  } as unknown as ApiClient;
  return { client, patches };
}

function mount(client: ApiClient) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/settings/accounting"]}>
          <Routes>
            <Route
              path="/:tenant/settings/accounting"
              element={
                <ChartOfAccountsPanel
                  client={client}
                  now={() => "2026-10-29T00:00:00Z"}
                  t={t}
                  sections="chart"
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function openEdit(user: ReturnType<typeof userEvent.setup>, index = 0) {
  const edits = await screen.findAllByRole("button", { name: "finance.coa.action.edit" });
  await user.click(edits[index]);
  return screen.findByRole("dialog");
}

afterEach(cleanup);

describe("CR-196-BRC10 · the chart account code", () => {
  it("shows a changed code with its former one beside it", async () => {
    mount(aClient("system_admin").client);
    const row = (await screen.findByText("0117-080-1000-0000-7110")).closest("tr");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText(/finance\.coa\.formerly/)).toHaveTextContent(
      '"code":"4150"',
    );
  });

  it("lets a System Admin change it, behind a confirmation that counts and warns", async () => {
    const { client, patches } = aClient("system_admin");
    mount(client);
    const user = userEvent.setup();
    const dialog = await openEdit(user);

    const code = within(dialog).getByLabelText(/finance\.coa\.col\.code/);
    await waitFor(() => expect(code).not.toHaveAttribute("readonly"));
    await user.clear(code);
    await user.type(code, "0117-080-1000-0000-7110");
    await user.click(within(dialog).getByRole("button", { name: "finance.coa.edit.submit" }));

    const confirm = await screen.findByRole("alertdialog");
    expect(within(confirm).getByText(/finance\.coa\.code\.confirmTitle/)).toBeInTheDocument();
    const text = confirm.textContent ?? "";
    expect(text).toContain("finance.coa.code.usedOn");
    expect(text).toContain("finance.coa.code.appliesEverywhere");
    // Q2 — the export warning names the month.
    expect(text).toContain("finance.coa.code.exported");
    expect(text).toContain("Sep 2026");
    // Nothing is sent until the admin confirms.
    expect(patches).toHaveLength(0);

    await user.click(within(confirm).getByRole("button", { name: "finance.coa.code.confirm" }));
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0].body.code).toBe("0117-080-1000-0000-7110");
  });

  it("sends nothing when the confirmation is cancelled, and says so in the dialog", async () => {
    const { client, patches } = aClient("system_admin");
    mount(client);
    const user = userEvent.setup();
    const dialog = await openEdit(user);
    const code = within(dialog).getByLabelText(/finance\.coa\.col\.code/);
    await waitFor(() => expect(code).not.toHaveAttribute("readonly"));
    await user.clear(code);
    await user.type(code, "9999");
    await user.click(within(dialog).getByRole("button", { name: "finance.coa.edit.submit" }));
    const confirm = await screen.findByRole("alertdialog");
    await user.click(within(confirm).getByRole("button", { name: "confirm.cancel" }));

    await waitFor(() => expect(within(dialog).getByText("finance.coa.code.kept")).toBeVisible());
    expect(patches).toHaveLength(0);
  });

  it("never sends the code when it did not change, so a rename needs no confirmation", async () => {
    const { client, patches } = aClient("system_admin");
    mount(client);
    const user = userEvent.setup();
    const dialog = await openEdit(user);
    const name = within(dialog).getByLabelText(/finance\.coa\.col\.name/);
    await user.clear(name);
    await user.type(name, "Solar service");
    await user.click(within(dialog).getByRole("button", { name: "finance.coa.edit.submit" }));
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect("code" in patches[0].body).toBe(false);
  });

  it("shows a clerk the code LOCKED, with the reason, and the type locked for everyone", async () => {
    mount(aClient("billing_clerk").client);
    const user = userEvent.setup();
    const dialog = await openEdit(user);
    const code = within(dialog).getByLabelText(/finance\.coa\.col\.code/);
    await waitFor(() => expect(code).toHaveAttribute("readonly"));
    expect(within(dialog).getByText("finance.coa.edit.codeAdminOnly")).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/finance\.coa\.col\.type/)).toHaveAttribute("readonly");
    expect(within(dialog).getByText("finance.coa.edit.typeFrozen")).toBeInTheDocument();
    // The retired sentence ("the number … cannot change") is gone.
    expect(within(dialog).queryByText("finance.coa.edit.frozen")).toBeNull();
  });
});

describe("CR-196-BRC10 · the confirmation's words", () => {
  it("prefers the export warning, falls back to the closed month, else says nothing", () => {
    expect(codeChangeWarning(USED, t)).toContain("finance.coa.code.exported");
    expect(codeChangeWarning({ ...USED, exported_period: null }, t)).toContain(
      "finance.coa.code.closedMonth",
    );
    expect(
      codeChangeWarning({ ...USED, exported_period: null, closed_period: null }, t),
    ).toBeNull();
  });

  it("puts the warning on its own line, after the counts", () => {
    const lines = codeChangeConsequence(USED, t).split("\n");
    expect(lines).toHaveLength(2);
    expect(lines[0]).toContain("finance.coa.code.usedOn");
    expect(lines[1]).toContain("finance.coa.code.exported");
    expect(codeChangeConsequence({ ...USED, exported_period: null, closed_period: null }, t)
      .split("\n")).toHaveLength(1);
  });
});

describe("CR-196-BRC10 · Q1 A — the GL report shows the new code, formerly the old", () => {
  it("draws the renamed account's old code beside its new one on the trial balance", () => {
    render(
      <TrialBalanceTable
        report={{
          basis: "posting",
          currency: "USD",
          period: { start: "2026-09-01", end: "2026-09-30" },
          rows: [
            {
              account_id: "acc-7110",
              code: "0117-080-1000-0000-7110",
              former_code: "4150",
              name: "Solar",
              type: "revenue",
              debit: "0.000000",
              credit: "120.000000",
              gross_debit: "0.000000",
              gross_credit: "120.000000",
              opening: "0.000000",
              closing: "-120.000000",
            },
          ],
          total_debit: "120.000000",
          total_credit: "120.000000",
          total_opening: "0.000000",
          total_closing: "0.000000",
          difference: "0.000000",
          balanced: true,
        }}
        t={t}
        state={{ q: "", sort: "code", dir: "asc", page: 1, per: 50, filters: {} }}
        onStateChange={() => undefined}
      />,
    );
    const cell = screen.getByText(/finance\.coa\.formerly/);
    expect(cell).toHaveTextContent('"code":"4150"');
    expect(cell.closest("tr")).toHaveTextContent("0117-080-1000-0000-7110");
  });
});
