// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-BIL-5339 (rule ids, open-question ids and Python identifiers
//           reached a clerk at /:tenant/billing/budget through two sites that
//           printed the server's sentences unchanged) · DEF-BIL-5340 (the
//           search's empty state said "No results for ''" and named neither
//           the set it searched nor the way to enrol)
// Screen:   S30 · §05 entry 25 (Budget Bills), and every other screen that
//           mounts `GapNotes`
// Rules:    B14 rule 31 · rule 32 · rule 33 · hard-won law 2 (a fixture that
//           cannot tell a working link from a broken one is how a dead door
//           hides — mounted under the REAL path pattern) · law 6 (no gate
//           reads rendered output) · law 7 (proved RED first)
// ───────────────────────────────────────────────────────
/**
 * THE REGRESSION TEST THE PRODUCT OWNER ASKED FOR: IT READS WHAT A CLERK SEES.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHY THE FIXTURE IS THE SERVER'S OWN PAYLOAD, VERBATIM
 * ══════════════════════════════════════════════════════════════════════════
 * The two existing tests of this tab seed `unavailable: []` and
 * `parameters_unavailable: null` — the ONE shape of response on which the
 * defect cannot appear. So they were green for four weeks over a screen that
 * printed `BR-RAT-043`, `OQ-237`, `OQ-142`, `budget_service.enroll` and
 * `budget.settle_up_gl_account` at a clerk. `SERVED` below is what
 * `GET /budget-billing/enrollments` actually puts on the wire — copied from
 * `apps/billing/budget_api.py` `BUDGET_UNAVAILABLE` and the settings seam's
 * refusal — and the backend test `test_def_bil_5339_clerk_facing_copy.py` ties
 * the served `detail` to the `en` catalogue so this copy cannot silently drift
 * from the server.
 *
 * ⚠ PROVED RED BEFORE THE FIX. With the pre-fix payload (the same four entries
 * carrying their ids in `detail` and no `message_key`) TC-C1 printed the exact
 * strings the clerk was reading; they are quoted in
 * `04-docs/05-modules/07-billing/conformance/CR-103-BRC03-budget-bills-maintenance.md`
 * under the 2026-09-15 section.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHAT WOULD MAKE THIS PASS WRONGLY (law 7, habit 2)
 * ══════════════════════════════════════════════════════════════════════════
 *   · a fixture with an empty gap list — which is why `SERVED` is never empty;
 *   · a component that renders the reference into a `data-` attribute — which
 *     the helper deliberately does not read, because the 2026-08-19 ruling put
 *     `data-br-ref` there on purpose;
 *   · a catalogue key that resolves to its own name because the key is missing
 *     — `billing.budget.gap.planFlag` contains no id, so TC-C6 asserts the
 *     rendered sentence is the catalogue's and not the key.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";
import type {
  BudgetListResponse,
  SettleUpForecastResponse,
  Unavailable,
} from "@/api/billingOpsEndpoints";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import { SEARCH_DEBOUNCE_MS } from "@/components/DataTable";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";
import { internalReferencesIn } from "@/testSupport/internalReferences";

import { BudgetBillsTab, budgetListKey } from "./BudgetBillsTab";
import { SettleUpForecastPage, settleUpForecastKey } from "./SettleUpForecastPage";
import { GapNotes } from "./billingOpsShared";
import { BUDGET_ENROL_ROUTE, BUDGET_FORECAST_ROUTE } from "./billingShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** An account that EXISTS and is NOT enrolled — the PO's reproduction used
 *  `AC-2026-00038` on the Ottumwa tenant. The number is a search term here;
 *  the point is that the enrolled list correctly has no row for it. */
const UNENROLLED_ACCOUNT_NO = "AC-2026-00038";

/**
 * What `GET /budget-billing/enrollments` serves for `unavailable` — one entry
 * per row of `BUDGET_UNAVAILABLE`, in its order, `detail` as the server writes
 * it. `br_ref` keeps the rule for support; it never renders as text.
 */
const SERVED: Unavailable[] = [
  {
    code: "plan_budget_flag_is_a_caller_fact",
    br_ref: "BR-RAT-043 · OQ-237",
    message_key: "billing.budget.gap.planFlag",
    detail: "Plan eligibility is not shown here. Confirm it when enrolling.",
  },
  {
    code: "settle_up_has_no_ledger_side",
    br_ref: "BR-BIL-011 · OQ-142",
    message_key: "billing.budget.gap.settleUpNotPosted",
    detail: "Settle-up amounts are shown, not posted.",
  },
  {
    code: "no_bulk_enrolment",
    br_ref: "BR-BIL-017 · BR-BIL-060",
    message_key: "billing.budget.gap.oneAtATime",
    detail: "Enrol accounts one at a time. No list import.",
  },
  {
    code: "drop_off_rule_is_superseded",
    br_ref: "BR-BIL-017",
    message_key: "billing.budget.gap.noAutoRemoval",
    detail: "Nobody leaves budget billing automatically.",
  },
];

/** What the same route serves when tenancy's settings read is not published. */
const PARAMETERS_UNREADABLE: Unavailable = {
  code: "budget_parameters_unreadable",
  br_ref: "BR-BIL-017 · BR-BIL-021",
  message_key: "billing.budget.gap.parametersUnreadable",
  detail: "Budget settings could not be read.",
};

const LIST: BudgetListResponse = {
  results: [
    {
      account_id: "01a00000-0000-7000-8000-0000000000a1",
      account_no: "A-40001",
      customer_name: "Navarro, P.",
      status: "enrolled",
      level: "88.000000",
      level_override: null,
      level_override_reason: null,
      effective_level: "88.000000",
      variance_balance: "-212.800000",
      currency: "USD",
      settle_up_month: 1,
      enrolled_on: "2026-01-04",
      last_leveled_at: "2026-01-04",
      actual_to_date: "1056.000000",
      actual_months: 9,
      relevel_due_on: "2026-07-04",
      relevel_is_due: true,
      relevel_drift_unavailable: "nothing stores a recomputed level",
    },
  ],
  count: 1,
  parameters: null,
  parameters_unavailable: PARAMETERS_UNREADABLE,
  statuses: ["enrolled", "off_budget"],
  summary: {
    enrolled: 1,
    accounts_total: 1284,
    accounts_total_unavailable: null,
    shortfall_accounts: 1,
    shortfall_amount: "-212.800000",
    shortfall_currency: "USD",
    shortfall_currencies: ["USD"],
    relevel_due: 1,
    relevel_cadence_months: 6,
    asks_waiting: null,
    asks_waiting_unavailable: "a level-pay ask carries no route, kind or account",
  },
  unavailable: SERVED,
};

const FORECAST: SettleUpForecastResponse = {
  count: 0,
  as_of: "2026-09-15",
  directions: ["collect", "credit"],
  results: [],
  summary: {
    settling_this_month: 0,
    settling_month: 9,
    settling_year: 2026,
    to_collect_amount: null,
    to_collect_accounts: 0,
    to_credit_amount: null,
    to_credit_accounts: 0,
    currency: null,
    currencies: [],
    later_accounts: 0,
    later_months: 0,
    no_settle_month: 0,
  },
  unavailable: SERVED,
};

function newClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity, staleTime: Infinity } },
  });
}

/** ⚠ MOUNTED UNDER THE REAL PATH PATTERN (law 2's fixture clause). */
function mountTab(client: QueryClient) {
  return render(
    <QueryClientProvider client={client}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazosbend/billing/budget"]}>
            <Routes>
              <Route path="/:tenant/billing/:tab" element={<BudgetBillsTab />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
}

/** The key the tab builds: `status|relevel|q|page|per`. */
const firstPageKey = (q = "") => budgetListKey(`enrolled||${q}|1|${DEFAULT_PAGE_SIZE}`);

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("DEF-BIL-5339 — nothing internal reaches a clerk on the Budget Bills tab", () => {
  it("TC-C1 · the tab, served the real gap list and an unreadable-settings note, shows no id and no identifier", () => {
    const client = newClient();
    client.setQueryData(firstPageKey(), LIST);
    const { container } = mountTab(client);
    // The gap list IS on the page — this is not a pass over an empty list.
    expect(container.querySelector('[data-bil="gaps"]')).not.toBeNull();
    expect(internalReferencesIn(container)).toEqual([]);
  });

  it("TC-C2 · `GapNotes` on its own — the contract every mount inherits", () => {
    const { container } = render(<GapNotes gaps={SERVED} t={t} />);
    expect(container.querySelectorAll("li")).toHaveLength(SERVED.length);
    expect(internalReferencesIn(container)).toEqual([]);
    // The reference is still there for support, on the element, never as text.
    expect(container.querySelector('[data-br-ref="BR-RAT-043 · OQ-237"]')).not.toBeNull();
  });

  it("TC-C3 · the settle-up forecast page, served the same list, shows none either", () => {
    const client = newClient();
    client.setQueryData(settleUpForecastKey(`|||1|${DEFAULT_PAGE_SIZE}`), FORECAST);
    const { container } = render(
      <QueryClientProvider client={client}>
        <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
          <ToastProvider>
            <MemoryRouter initialEntries={[`/brazosbend${BUDGET_FORECAST_ROUTE}`]}>
              <Routes>
                <Route path="/:tenant/billing/budget/settle-up" element={<SettleUpForecastPage />} />
              </Routes>
            </MemoryRouter>
          </ToastProvider>
        </TenantRegionalProvider>
      </QueryClientProvider>,
    );
    expect(container.querySelector('[data-bil="gaps"]')).not.toBeNull();
    expect(internalReferencesIn(container)).toEqual([]);
  });

  it("TC-C4 · the gap list's heading derives its count from the list, and the settings note is a catalogue sentence", () => {
    const client = newClient();
    client.setQueryData(firstPageKey(), LIST);
    mountTab(client);
    expect(screen.getByText(t("billing.gaps.title", { count: SERVED.length }))).toBeInTheDocument();
    expect(screen.getByText(t("billing.budget.gap.parametersUnreadable"))).toBeInTheDocument();
  });

  it("TC-C5 · the stated absences survive: what the screen cannot do is still on it, in six words or fewer", () => {
    const client = newClient();
    client.setQueryData(firstPageKey(), LIST);
    mountTab(client);
    for (const gap of SERVED) {
      const sentence = t(gap.message_key ?? "");
      expect(screen.getByText(sentence)).toBeInTheDocument();
      for (const clause of sentence.split(/[.!?]\s*/).filter((s) => s.length > 0)) {
        expect(clause.split(/\s+/).length, `"${clause}" is over rule 33's cap`).toBeLessThanOrEqual(6);
      }
    }
    // The one absence the server list does not carry: the yearly cap is a setting.
    expect(screen.getByText(t("billing.budget.awaitsTitle"))).toBeInTheDocument();
    expect(screen.getByText(t("billing.budget.awaits"))).toBeInTheDocument();
  });

  it("TC-C6 · a rendered gap is the catalogue's sentence, never its key", () => {
    const { container } = render(<GapNotes gaps={SERVED} t={t} />);
    for (const gap of SERVED) {
      expect(container.textContent).not.toContain(gap.message_key);
    }
  });
});

describe("DEF-BIL-5340 — an empty search names the set it searched and points at enrolment", () => {
  it("TC-C7 · searching for an unenrolled account says which set was searched and links to Enrol", async () => {
    vi.useFakeTimers();
    const client = newClient();
    client.setQueryData(firstPageKey(), LIST);
    client.setQueryData(firstPageKey(UNENROLLED_ACCOUNT_NO), { ...LIST, results: [], count: 0 });
    const { container } = mountTab(client);

    const box = screen.getByPlaceholderText(t("billing.budget.search"));
    // A clerk types; the toolbar debounces before it fires (`SEARCH_DEBOUNCE_MS`).
    // `fireEvent.change` rather than a hand-built `input` event: React reads
    // its value tracker, so a value set by assignment never reaches `onChange`
    // and the first draft of this case searched for nothing at all.
    await act(async () => {
      fireEvent.change(box, { target: { value: UNENROLLED_ACCOUNT_NO } });
      vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS + 10);
    });

    const scope = container.querySelector('[data-bil="search-scope"]');
    expect(scope, "the scope note is missing under the empty list").not.toBeNull();
    expect(scope).toHaveTextContent(t("billing.budget.searchScope"));
    const door = scope?.querySelector("a");
    expect(door).toHaveTextContent(t("billing.budgetEnrol.door"));
    expect(door).toHaveAttribute("href", `/brazosbend${BUDGET_ENROL_ROUTE}`);
    // The empty-quote echo is the sentence the PO photographed; it must not return.
    expect(container.textContent).not.toContain("No results for ''");
    expect(internalReferencesIn(container)).toEqual([]);
  });

  it("TC-C8 · with no term and nobody under the default chip, the note says the list holds enrolled accounts only — never \"No results for ''\"", () => {
    const client = newClient();
    client.setQueryData(firstPageKey(), { ...LIST, results: [], count: 0 });
    const { container } = mountTab(client);
    expect(container.textContent).not.toContain("''");
    expect(container.textContent).toContain(t("states.zeroResults.filtered"));
    const scope = container.querySelector('[data-bil="search-scope"]');
    expect(scope).toHaveTextContent(t("billing.budget.listScope"));
    expect(scope?.querySelector("a")).toHaveAttribute("href", `/brazosbend${BUDGET_ENROL_ROUTE}`);
  });
});
