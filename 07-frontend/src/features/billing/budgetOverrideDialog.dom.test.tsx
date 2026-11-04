// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-BIL-5262 — "The override amount and reason boxes sit under the
//           table with no row attached, so a clerk cannot see which account
//           they will change." Filed 2026-09-14 against the Budget Bills tab.
// Story:    US-BIL-020 (the per-account override)   Screens: S30 · §05 entry 25
// Rules:    BR-BIL-017 (the ±30% bound is measured against the COMPUTED level,
//           so the computed figure is on screen while an override is typed) ·
//           B14 rule 38 (where a drawing and our UI rules disagree about how a
//           FORM is built, the UI rules win) · CLAUDE.md rule 2 (a money figure
//           travels as a decimal STRING, never through an IEEE double)
// ───────────────────────────────────────────────────────
/**
 * ⚠ **WHY THIS FILE CLICKS, AND WHY IT IS A SECOND FILE.**
 *
 * `budgetBillsTable.dom.test.tsx` beside it renders with `renderToStaticMarkup`
 * and proves what the table DRAWS. It cannot prove this: a dialog does not
 * exist until a row action is pressed, and the defect being fixed is precisely
 * that the form was not attached to a row. A case asserting that
 * `OverrideLevelModal` renders an account when handed one would have been green
 * on the broken day too — the component was not the broken part, the wiring
 * was. That is hard-won law 2 in one sentence, so this file presses the pencil.
 *
 * It is a SEPARATE file because the static suite has no `@vitest-environment
 * jsdom` docblock and its five original cases were written under that
 * environment; adding jsdom to it would change what they run in, which is a
 * change nobody asked for.
 *
 * ⚠ **AND `TC-D5` IS THE ONE THAT MAKES THE REST MEAN ANYTHING.** A dialog that
 * always named the FIRST row would pass every other case in this file. Two rows
 * are seeded and both are opened, so "it names an account" and "it names THE
 * account" cannot be confused.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";
import type { ApiClient } from "@/api/client";
import type { BudgetListResponse, BudgetStatusRow } from "@/api/billingOpsEndpoints";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { BudgetBillsTab, budgetListKey } from "./BudgetBillsTab";

afterEach(cleanup);

const t = (key: string): string => i18n.t(key);

/** ⚠ EVERY FIGURE IS THIS FIXTURE'S OWN — B14 rule 37. p121's `$88.00` is an
 *  illustration, and a case that asserted it would be a case about the
 *  illustrator. TWO enrolled rows, because one cannot catch a dialog that
 *  always opens the same account. */
const ROWS: BudgetStatusRow[] = [
  {
    account_id: "01a00000-0000-7000-8000-0000000000a1",
    account_no: "A-40001",
    customer_name: "Navarro, P.",
    status: "enrolled",
    level: "88.000000",
    level_override: null,
    level_override_reason: null,
    effective_level: "88.000000",
    variance_balance: "-12.400000",
    currency: "USD",
    settle_up_month: 1,
    enrolled_on: "2026-01-04",
    last_leveled_at: "2026-01-04",
    actual_to_date: "1056.000000",
    actual_months: 9,
    relevel_due_on: "2027-01-04",
    relevel_is_due: false,
    relevel_drift_unavailable: "nothing stores a recomputed level",
  },
  {
    account_id: "01a00000-0000-7000-8000-0000000000b2",
    account_no: "A-40002",
    customer_name: "Okafor, D.",
    status: "enrolled",
    level: "74.000000",
    level_override: null,
    level_override_reason: null,
    effective_level: "74.000000",
    variance_balance: "0.000000",
    currency: "USD",
    settle_up_month: 1,
    enrolled_on: "2026-02-04",
    last_leveled_at: "2026-02-04",
    actual_to_date: "888.000000",
    actual_months: 9,
    relevel_due_on: "2027-02-04",
    relevel_is_due: false,
    relevel_drift_unavailable: "nothing stores a recomputed level",
  },
];

const RESPONSE: BudgetListResponse = {
  results: ROWS,
  count: 2,
  parameters: { relevel_cadence_months: 6 },
  parameters_unavailable: null,
  statuses: ["enrolled", "off_budget"],
  summary: {
    enrolled: 2,
    accounts_total: 1284,
    accounts_total_unavailable: null,
    shortfall_accounts: 1,
    shortfall_amount: "-12.400000",
    shortfall_currency: "USD",
    shortfall_currencies: ["USD"],
    relevel_due: 0,
    relevel_cadence_months: 6,
    asks_waiting: null,
    asks_waiting_unavailable: "a level-pay ask carries no route, kind or account",
  },
  unavailable: [],
};

interface Posted {
  path: string;
  body: unknown;
}

/** A client that records the write and never reaches a network. */
function stubClient(posted: Posted[]): ApiClient {
  const refuse = (): never => {
    throw new Error("this fixture serves the list from the cache; nothing else is called");
  };
  return {
    request: refuse,
    get: refuse,
    put: refuse,
    patch: refuse,
    delete: refuse,
    post: async (path: string, body?: unknown) => {
      posted.push({ path, body });
      return { data: ROWS[0], status: 200, headers: new Headers() };
    },
  } as unknown as ApiClient;
}

/** ⚠ MOUNTED UNDER THE REAL PATH PATTERN (hard-won law 2's fixture clause). */
function mount(posted: Posted[]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: Infinity } },
  });
  // The key the tab builds for its FIRST request — status `enrolled`, no
  // re-level chip, no search, page 1 at the default size.
  queryClient.setQueryData(budgetListKey("enrolled|||1|50"), RESPONSE);
  return render(
    <QueryClientProvider client={queryClient}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazosbend/billing/budget"]}>
            <Routes>
              <Route
                path="/:tenant/billing/:tab"
                element={<BudgetBillsTab client={stubClient(posted)} locale="en-US" />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
}

/** The pencil on row `index`, by its accessible name. */
function pencil(index: number): HTMLElement {
  return screen.getAllByRole("button", { name: t("billing.budget.overrideAction") })[index];
}

describe("DEF-BIL-5262 — the override is asked about ONE row", () => {
  it("TC-D1 · the pencil is live, and it opens a dialog naming that account", async () => {
    const posted: Posted[] = [];
    mount(posted);
    // The control is not greyed over a form somewhere else on the page. This
    // half is the dead-control half: before the fix the pencil was disabled on
    // every row until two boxes that named no account had been filled in.
    expect(pencil(0)).not.toBeDisabled();
    expect(screen.queryByRole("dialog")).toBeNull();

    await userEvent.click(pencil(0));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/A-40001/)).toBeInTheDocument();
    expect(within(dialog).getByText(/Navarro, P\./)).toBeInTheDocument();
    expect(posted).toHaveLength(0); // opening a form writes nothing
  });

  it("TC-D2 · the dialog carries the COMPUTED figure the bound is measured against", async () => {
    mount([]);
    await userEvent.click(pencil(0));
    const dialog = await screen.findByRole("dialog");
    // p122's own rule row: "The ±30% bound is measured against the computed
    // figure, so hiding it is how an override gets typed blind." 88.00 is this
    // fixture's computed level; the customer pays it today.
    expect(within(dialog).getByText("$88.00")).toBeInTheDocument();
    expect(within(dialog).getByText(t("billing.budget.col.computed"))).toBeInTheDocument();
  });

  it("TC-D3 · an empty commit posts nothing and asks for both", async () => {
    const posted: Posted[] = [];
    mount(posted);
    await userEvent.click(pencil(0));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(
      within(dialog).getByRole("button", { name: t("billing.budget.overrideAction") }),
    );
    await waitFor(() => {
      expect(within(dialog).getByText(t("billing.budget.amount_required"))).toBeInTheDocument();
    });
    expect(within(dialog).getByText(t("billing.budget.reason_required"))).toBeInTheDocument();
    // ⚠ THE ASSERTION THAT MATTERS: a refused form does not reach the server.
    expect(posted).toHaveLength(0);
  });

  it("TC-D4 · a commit posts the decimal STRING, to that row's account", async () => {
    const posted: Posted[] = [];
    mount(posted);
    await userEvent.click(pencil(0));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(t("billing.budget.field.override"), { exact: false }), "96.50");
    await userEvent.type(
      within(dialog).getByLabelText(t("billing.budget.field.overrideReason"), { exact: false }),
      "agreed on the phone",
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: t("billing.budget.overrideAction") }),
    );

    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0].path).toBe(`/budget-billing/${ROWS[0].account_id}/override`);
    const body = posted[0].body as { override: unknown; reason: string };
    // A STRING, exactly as typed. `Number("96.50")` is 96.5 and NUMERIC(18,6)
    // does not survive an IEEE double — CLAUDE.md rule 2, and the server
    // refuses a float outright.
    expect(typeof body.override).toBe("string");
    expect(body.override).toBe("96.50");
    expect(body.reason).toBe("agreed on the phone");
  });

  it("TC-D5 · a SECOND row opens the SECOND account, not the first", async () => {
    // ⚠ WITHOUT THIS CASE, EVERY ONE ABOVE PASSES ON A DIALOG HARDWIRED TO ROW
    // ONE — which is the defect wearing a dialog's clothes rather than fixed.
    const posted: Posted[] = [];
    mount(posted);
    await userEvent.click(pencil(1));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/A-40002/)).toBeInTheDocument();
    expect(within(dialog).queryByText(/A-40001/)).toBeNull();
    expect(within(dialog).getByText("$74.00")).toBeInTheDocument();

    await userEvent.type(within(dialog).getByLabelText(t("billing.budget.field.override"), { exact: false }), "80.00");
    await userEvent.type(
      within(dialog).getByLabelText(t("billing.budget.field.overrideReason"), { exact: false }),
      "hardship arrangement",
    );
    await userEvent.click(
      within(dialog).getByRole("button", { name: t("billing.budget.overrideAction") }),
    );
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0].path).toBe(`/budget-billing/${ROWS[1].account_id}/override`);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-020@938d89c9 (sources: 04-docs/05-modules/07-billing/05-user-stories.md
//         US-BIL-020 — the per-account override; 12-governance/10-defect-log.csv row
//         DEF-BIL-5262, 2026-09-14; 05-prototype/04 Billing, As Built.pdf §05 entry 25
//         p121–p122, read as images per B14 rule 42)
// generated: 2026-09-15 by the §05 entry 25 table-walk lane (MAINTENANCE)
// checklist: A✔ B=deferred(maintenance, not a story — the defect row is the requirement) C✔ D=deferred(no endpoint moved) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
//            B: DEF-BIL-5262 is the requirement and §4 of the maintenance
//            process proves against its reproduction, not against a §3 TC list.
//            C: the override travels as a decimal STRING — TC-D4 asserts the
//            type, never Number(). D: POST /budget-billing/{id}/override is
//            unchanged; only which row asks for it moved.
// gates: RED PROVED FIRST through `npx vitest run
//        src/features/billing/budgetOverrideDialog.dom.test.tsx` in a
//        `git worktree` pinned at the tip before this change — verbatim in the
//        lane report and the conformance record.
// exceptions: E3 the fixture's money figures are its own, never p121's (B14
//        rule 37) · E3 the list is seeded into the query cache rather than
//        served, because budget enrolment needs twelve months of ISSUED bills
//        and this database holds zero invoices — the same posture the static
//        file beside this one takes, and it says so too
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
