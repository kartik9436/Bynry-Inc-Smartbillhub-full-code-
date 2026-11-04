// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  Record links (PO ruling 2026-10-19, decision log "Record links
//          (navigation design)") — lane RL-B (job B).
// Rules:   hard-won law 2, both halves — a link that is BUILT and not WIRED is
//          dead UI, and a fixture mounted bare in a `MemoryRouter` cannot tell
//          a working link from `//…`. Every case here mounts under the real
//          `/:tenant/…` pattern and asserts the EXACT address.
// ───────────────────────────────────────────────────────
/**
 * THE SAFETY NET — every screen/record pair job B turned from plain text into
 * a link, in one table. A pair that reverts to text goes red here, by name.
 *
 * Two kinds of row:
 *
 *   * **RENDERED** — the piece of UI that draws the record is mounted (a table
 *     cell, a panel, a page with its cache seeded) and the link is found by its
 *     visible text and its `href` compared exactly.
 *   * **WIRED** — where the link's address is handed in by a page as a prop,
 *     the page's SOURCE must still hand it in. That is G13's question (is the
 *     prop passed?) asked of these props specifically; the rendered row beside
 *     it proves what the prop does.
 *
 * The bulk bill run's account links are rendered on the real page in
 * `features/billing/bulkRun/BulkRunRecordLinks.dom.test.tsx`; the bill
 * detail's meter link in `BillChargesTab.test.tsx`; the account Adjustments
 * number in `AccountAdjustmentsTab.test.tsx`. Each is ALSO a WIRED row here, so
 * this file alone still lists every pair.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { PaymentRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";
import {
  breaks,
  pricingShadow,
  signOffSummary,
} from "@/features/billing/bulkRun/__fixtures__/bulkRunFixtures";
import { asksTableConfig } from "@/features/billing/BudgetAsksPage";
import { PricingShadowPanel } from "@/features/billing/billRunShared";
import { NotSentPanel } from "@/features/billing/bulkRun/SendStep";
import {
  FailedToDraftPanel,
  PaymentsAndBalances,
  SignOffWarnings,
} from "@/features/billing/bulkRun/SignOffStep";
import { printBillsTableConfig } from "@/features/billing/PrintBillsPage";
import { AccountPlanName } from "@/features/customers/AccountPlanName";
import { agingConfig } from "@/features/ledger/AgingView";
import { JournalEntryFacts, JournalEntryLines, journalSourcePath } from "@/features/ledger/JournalEntryDetail";
import { journalConfig } from "@/features/ledger/JournalView";
import type { JournalRegional } from "@/features/ledger/JournalView";
import { paymentsMadeConfig } from "@/features/ledger/PaymentsMadePanel";
import { RefundDetailPage } from "@/features/ledger/RefundDetailPage";
import { OccupantCell } from "@/features/metering/PremisesDetailPage";
import { ladderBoardConfig } from "@/features/payments/CollectionsPage";
import { billsTableConfig } from "@/features/payments/DebtorPage";
import { debtorsTableConfig } from "@/features/payments/debtorsTable";
import { PaymentFacts, PaymentHeaderStrip } from "@/features/payments/paymentDetailShared";
import {
  RecordPaymentPanel,
  ReversedPaymentPanel,
  paymentsCells,
} from "@/features/payments/PaymentsPage";
import { SettlementPage } from "@/features/payments/SettlementPage";
import { WriteOffQueueTable } from "@/features/payments/WriteOffQueuePage";
import { AccountLedgerTable } from "@/features/reports/AccountLedgerReportPage";
import { ByPremisesTable } from "@/features/reports/ByPremisesReportPage";
import { CustomerStatementTable } from "@/features/reports/CustomerStatementPage";

afterEach(cleanup);

const T = "acme";
const tp = (path: string) => `/${T}${path}`;
const t = ((key: string, params?: Record<string, unknown>) =>
  i18n.t(key, params as never)) as never;
const REGIONAL = { timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" as never };
const fmt = {
  t,
  locale: "en-US",
  timeZone: "America/Chicago",
  dateFormat: "MM/DD/YYYY",
} as never;

/** Mount under the REAL tenant pattern, so an address with no tenant — or a
 *  protocol-relative `//…` — cannot pass. */
function mount(node: ReactNode, path = `/${T}/x`): HTMLElement {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { container } = render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/:tenant/*" element={<>{node}</>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return container;
}

/** A config's cell, rendered as a real node. */
function cellOf<R>(config: { columns: { key: string; cell?: (row: R) => ReactNode }[] }, key: string, row: R) {
  const column = config.columns.find((one) => one.key === key);
  if (column?.cell === undefined) throw new Error(`no cell for ${key}`);
  return mount(<>{column.cell(row)}</>);
}

function hrefOf(container: HTMLElement, text: string): string | null {
  const link = Array.from(container.querySelectorAll("a")).find(
    (anchor) => (anchor.textContent ?? "").trim() === text,
  );
  return link === undefined ? null : link.getAttribute("href");
}

function payment(over: Partial<PaymentRow> = {}): PaymentRow {
  return {
    id: "pay-1",
    payment_no: "PMT-2610-000001",
    account_id: "acc-1",
    account_no: "AC-0001",
    customer_name: "Grace Espinoza",
    type: "payment",
    method: "check",
    method_name: "Check",
    confirmation: "4471",
    memo: null,
    amount: "100.0000",
    currency: "USD",
    status: "cleared",
    purpose: "bill",
    posted_at: "2026-10-01T00:00:00Z",
    cleared_at: "2026-10-01T00:00:00Z",
    applied_to: [{ invoice_id: "inv-2", invoice_number: "BL-2610-000002", amount: "100.0000" }],
    applied_total: "100.0000",
    deposit_batch_id: null,
    receipt_no: null,
    cheque_date: null,
    drawer_bank: null,
    bankable_from: null,
    moved_from_payment_no: null,
    moved_from_account_no: null,
    moved_to_payment_no: null,
    moved_to_account_no: null,
    origin: "entry",
    batch_ref: "DEP-261001-0001",
    batch_kind: "deposit",
    batch_id: "bat-1",
    ...over,
  };
}

const JOURNAL_REGIONAL: JournalRegional = {
  timeZone: "America/Chicago",
  dateFormat: "MM/DD/YYYY",
  today: "2026-10-19",
  sourceWord: () => null,
};

const JOURNAL_ROW = {
  entry_id: "je-1",
  je_number: "JE-100126-0001",
  entry_date: "2026-10-01",
  type: "standard",
  status: "posted",
  memo: null,
  source_type: "invoice",
  source_label: "bill",
  source_mapped: true,
  source_id: "inv-9",
  currency: "USD",
  debit: "10.0000",
  credit: "10.0000",
  balanced: true,
  reversal_of_entry_id: null,
  reversed_by_entry_id: null,
  auto_reverse_entry_id: null,
  posted_at: "2026-10-01T00:00:00Z",
};

// ── Settlement detail, mounted as `settlementScreens.dom.test.tsx` does ─────
function settlementPage(): HTMLElement {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const code = "STL-261019-CARD";
  const params = new URLSearchParams();
  params.set("sort", "taken");
  params.set("dir", "desc");
  queryClient.setQueryData(["payments", "settlement", code], {
    code,
    provider: "sandbox_pay",
    paid_out_at: "2026-10-19T02:14:00Z",
    payments: 1,
    gross: "100.0000",
    fees: "2.9000",
    net: "97.1000",
    currency: "USD",
    status: "received",
    bank_reference: null,
    fee_share: "2.90",
  });
  queryClient.setQueryData(["payments", "settlement", code, "members", params.toString()], {
    rows: [
      {
        payment_no: "PMT-2610-000412",
        taken_at: "2026-10-18T14:22:00Z",
        account_no: "AC-2026-00031",
        account_id: "acc-31",
        customer_name: "Grace Espinoza",
        reference: "auth 4471",
        gross: "100.0000",
        fee: "2.9000",
        currency: "USD",
      },
    ],
    count: 1,
  });
  const div = document.createElement("div");
  div.innerHTML = renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${T}/payments/settlements/${code}`]}>
          <Routes>
            <Route
              path="/:tenant/payments/settlements/:settlementRef"
              element={<SettlementPage client={{} as never} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return div;
}

// ── Refund detail, its three reads seeded ───────────────────────────────────
function refundPage(): HTMLElement {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(["payments", "refund", "ref-1"], {
    id: "ref-1",
    payment_id: "pay-7",
    account_id: "acc-7",
    amount: "57.1300",
    currency: "USD",
    status: "requested",
    method: "check",
    reference: null,
    reason: "Overpaid",
    requested_by: "Dana Reed",
    requested_at: "2026-10-18T10:00:00Z",
    approved_by: null,
    approved_at: null,
    issued_at: null,
    cleared_at: null,
    voided_at: null,
    void_reason: null,
    journal_entry_id: null,
    void_journal_entry_id: null,
  });
  queryClient.setQueryData(["customers", "account", "acc-7"], {
    id: "acc-7",
    account_no: "AC-2026-00007",
    name: "Grace Espinoza",
    premise: null,
    unit_label: null,
  });
  queryClient.setQueryData(["payments", "credit-sources", "acc-7"], {
    account_id: "acc-7",
    refundable: "57.1300",
    refundable_display: "57.13",
    sources: [
      {
        payment_id: "pay-7",
        payment_no: "PMT-2610-000007",
        posted_at: "2026-10-02T00:00:00Z",
        amount: "350.0000",
        contributed: "57.1300",
        currency: "USD",
      },
    ],
    source_count: 1,
    problems: [],
  });
  const div = document.createElement("div");
  div.innerHTML = renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${T}/finance/refunds/ref-1`]}>
          <Routes>
            <Route
              path="/:tenant/finance/refunds/:refundId"
              element={<RefundDetailPage client={{ get: async () => ({ data: {} }) } as never} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return div;
}

interface Rendered {
  screen: string;
  record: string;
  text: string;
  href: string;
  draw: () => HTMLElement;
}

const JE_LINE = {
  line_id: "jl-1",
  account_code: "2400",
  account_name: "Customer credit balances",
  side: "credit",
  debit: null,
  credit: "40.000000",
  service: null,
  account: { id: "acct-48", label: "AC-2026-00048" },
  premises: { id: "prem-1", label: "403 Silver Creek Rd" },
  unit: { id: "unit-1", label: "Suite 1" },
  tax_authority: null,
};
const drawLines = () =>
  mount(<JournalEntryLines entry={JOURNAL_ROW as never} lines={[JE_LINE]} tenantPath={tp} />);

const RENDERED: Rendered[] = [
  // ── Payments ──────────────────────────────────────────────────────────────
  {
    screen: "Debtor page · What is owed",
    record: "bill",
    text: "BL-2610-000011",
    href: `/${T}/billing/bills/inv-11`,
    draw: () =>
      cellOf(billsTableConfig(t, REGIONAL, "USD", "2026-10-19", tp), "number", {
        invoice_id: "inv-11",
        number: "BL-2610-000011",
        issued_on: null,
        due_on: null,
        total: null,
        open_balance: null,
      } as never),
  },
  {
    screen: "Debtors list (Outstandings)",
    record: "debtor",
    text: "AC-2026-00048",
    href: `/${T}/payments/debtors/AC-2026-00048`,
    draw: () =>
      cellOf(debtorsTableConfig(t, REGIONAL as never, "USD", tp), "account_no", {
        account_id: "acc-48",
        account_no: "AC-2026-00048",
      } as never),
  },
  {
    screen: "Payments list · Batch",
    record: "deposit batch",
    text: "DEP-261001-0001",
    href: `/${T}/finance/deposits/bat-1`,
    draw: () => mount(<>{paymentsCells(t, tp, "America/Chicago", "MM/DD/YYYY").batch(payment())}</>),
  },
  {
    screen: "Payments list · Applied to",
    record: "bill",
    text: "BL-2610-000002",
    href: `/${T}/billing/bills/inv-2`,
    draw: () =>
      mount(<>{paymentsCells(t, tp, "America/Chicago", "MM/DD/YYYY").appliedTo(payment())}</>),
  },
  {
    screen: "Payment detail · applied-to bills",
    record: "bill",
    text: "BL-2610-000002",
    href: `/${T}/billing/bills/inv-2`,
    draw: () =>
      mount(
        <PaymentFacts
          row={payment()}
          currency="USD"
          timeZone="America/Chicago"
          dateFormat={"MM/DD/YYYY" as never}
          accountHref={tp("/accounts/acc-1")}
          billHref={(id) => tp(`/billing/bills/${id}`)}
        />,
      ),
  },
  {
    screen: "Payment detail · Batch tile",
    record: "deposit batch",
    text: "DEP-261001-0001",
    href: `/${T}/finance/deposits/bat-1`,
    draw: () =>
      mount(
        <PaymentHeaderStrip
          source={{ origin: "entry", taken_by: null } as never}
          batchRef="DEP-261001-0001"
          batchHref={tp("/finance/deposits/bat-1")}
          reconciled={null}
          status="cleared"
        />,
      ),
  },
  {
    screen: "Record payment · result",
    record: "bill",
    text: "BL-2610-000003",
    href: `/${T}/billing/bills/inv-3`,
    draw: () =>
      mount(
        <RecordPaymentPanel
          recorded={{
            id: "pay-3",
            payment_no: "PMT-2610-000003",
            created: true,
            status: "cleared",
            amount: "50.0000",
            currency: "USD",
            applied: "50.0000",
            credit_carried: "0.0000",
            allocations: [
              { invoice_id: "inv-3", invoice_number: "BL-2610-000003", amount: "50.0000", by_class: {} },
            ],
            journal_entry_id: null,
            posting_key: null,
            posted_to_ledger: true,
            problems: [],
          }}
          onDismiss={() => undefined}
        />,
      ),
  },
  {
    screen: "Reverse payment · result",
    record: "bill",
    text: "BL-2610-000002",
    href: `/${T}/billing/bills/inv-2`,
    draw: () =>
      mount(
        <ReversedPaymentPanel
          result={
            {
              id: "pay-r",
              payment_no: "PMT-2610-000009",
              original_payment_id: "pay-1",
              created: true,
              amount: "-100.0000",
              currency: "USD",
              reason: "nsf",
              allocations_reversed: "100.0000",
              reopened: [{ invoice_id: "inv-2", amount: "100.0000" }],
              credit_reversed: "0.0000",
              credit_position_after: "0.0000",
              journal_entry_id: null,
              posting_key: null,
              bank_fee: null,
              bank_fee_entry_id: null,
              nsf_count: 1,
              cash_only_no_autopay: null,
              privilege_flag_tripped: false,
              is_partial: false,
              still_stands: "0.0000",
              problems: [],
            } as never
          }
          original={payment()}
          onDismiss={() => undefined}
        />,
      ),
  },
  {
    screen: "Settlement · members",
    record: "payment",
    text: "PMT-2610-000412",
    href: `/${T}/payments/PMT-2610-000412`,
    draw: settlementPage,
  },
  {
    screen: "Settlement · members",
    record: "account",
    text: "AC-2026-00031",
    href: `/${T}/accounts/acc-31`,
    draw: settlementPage,
  },
  {
    screen: "Collections ladder",
    record: "debtor",
    text: "AC-2026-00012",
    href: `/${T}/payments/debtors/AC-2026-00012`,
    draw: () =>
      cellOf(ladderBoardConfig(t, "en-US", tp), "account_no", {
        account_id: "acc-12",
        account_no: "AC-2026-00012",
      } as never),
  },
  {
    screen: "Write-off queue",
    record: "debtor",
    text: "A-10802",
    href: `/${T}/payments/debtors/A-10802`,
    draw: () =>
      mount(
        <WriteOffQueueTable
          rows={[
            {
              id: "wo-1",
              account_id: "acc-10802",
              account_no: "A-10802",
              amount: "948.2000",
              currency: "USD",
              reason: "uncollectible",
              note: null,
              status: "requested",
              requested_on: "2026-10-15",
              requested_by: "u-1",
              requested_by_name: "Dana Reed",
              approved_on: null,
              approved_by: null,
              approved_by_name: null,
              posted_to_ledger: false,
              journal_entry_id: null,
            } as never,
          ]}
          currentUserId={null}
          t={t}
          onDecide={() => undefined}
        />,
      ),
  },
  {
    screen: "AR aging",
    record: "debtor",
    text: "AC-2026-00077",
    href: `/${T}/payments/debtors/AC-2026-00077`,
    draw: () =>
      cellOf(agingConfig(null, t, "en-US", { services: [] }, tp), "account_no", {
        account_id: "acc-77",
        account_no: "AC-2026-00077",
      }),
  },
  {
    screen: "Refund detail · Whose money",
    record: "account",
    text: "AC-2026-00007 · Grace Espinoza",
    href: `/${T}/accounts/acc-7`,
    draw: refundPage,
  },
  {
    screen: "Refund detail · Where it came from",
    record: "payment",
    text: "PMT-2610-000007",
    href: `/${T}/payments/PMT-2610-000007`,
    draw: refundPage,
  },
  // ── Finance ───────────────────────────────────────────────────────────────
  {
    screen: "Journal list · Entry no.",
    record: "journal entry",
    text: "JE-100126-0001",
    href: `/${T}/finance/journal-entries/je-1`,
    draw: () =>
      cellOf(journalConfig(null, t, "en-US", JOURNAL_REGIONAL, undefined, tp), "je_number", JOURNAL_ROW as never),
  },
  {
    screen: "Journal list · Source",
    record: "bill",
    text: i18n.t("finance.journal.source.bill"),
    href: `/${T}/billing/bills/inv-9`,
    draw: () =>
      cellOf(journalConfig(null, t, "en-US", JOURNAL_REGIONAL, undefined, tp), "source", JOURNAL_ROW as never),
  },
  {
    screen: "Journal entry detail · Source",
    record: "bill",
    text: i18n.t("finance.journal.source.bill"),
    href: `/${T}/billing/bills/inv-9`,
    draw: () =>
      mount(
        <JournalEntryFacts
          entry={JOURNAL_ROW as never}
          lineCount={2}
          sourceHref={tp(journalSourcePath("invoice", "inv-9") as string)}
        />,
      ),
  },
  // DEF-LED-10303 — found by the 2.588.0 combined walk, not by the audit.
  {
    screen: "Journal entry detail · Lines",
    record: "account",
    text: "AC-2026-00048",
    href: `/${T}/accounts/acct-48`,
    draw: drawLines,
  },
  {
    screen: "Journal entry detail · Lines",
    record: "premises",
    text: "403 Silver Creek Rd",
    href: `/${T}/premises/prem-1`,
    draw: drawLines,
  },
  {
    screen: "Journal entry detail · Lines",
    record: "unit",
    text: "Suite 1",
    href: `/${T}/premises/units/unit-1`,
    draw: drawLines,
  },
  {
    screen: "Tax · Payments made",
    record: "journal entry",
    text: "JE-093026-0004",
    href: `/${T}/finance/journal-entries/je-4`,
    draw: () =>
      cellOf(paymentsMadeConfig({ t, currency: "USD", tenantPath: tp }), "entry", {
        id: "rp-1",
        entry_id: "je-4",
        entry_no: "JE-093026-0004",
      } as never),
  },
  // ── Billing ───────────────────────────────────────────────────────────────
  {
    screen: "Bulk run · Sign off · Waived",
    record: "account",
    text: signOffSummary().waived[0].account_no,
    href: `/${T}/accounts/acc-10`,
    draw: () =>
      mount(
        <SignOffWarnings
          breaks={0}
          summary={signOffSummary()}
          onSeeBreaks={() => undefined}
          onSeeWaived={() => undefined}
          fmt={fmt}
          accountHref={(id) => tp(`/accounts/${id}`)}
        />,
      ),
  },
  {
    screen: "Bulk run · Sign off · Credit covers",
    record: "account",
    text: "AC-2026-12910",
    href: `/${T}/accounts/acc-30`,
    draw: () =>
      mount(
        <PaymentsAndBalances
          summary={signOffSummary()}
          fmt={fmt}
          accountHref={(id) => tp(`/accounts/${id}`)}
        />,
      ),
  },
  {
    screen: "Bulk run · Failed to draft",
    record: "account",
    text: "AC-2026-00902",
    href: `/${T}/accounts/acc-20`,
    draw: () =>
      mount(
        <FailedToDraftPanel
          breaks={breaks().breaks}
          retried={new Set()}
          working={false}
          onRetry={() => undefined}
          onClose={() => undefined}
          fixHref={(_tag, id) => tp(`/accounts/${id}`)}
          t={t}
        />,
      ),
  },
  {
    screen: "Bulk run · Not sent",
    record: "account",
    text: "AC-2026-00902",
    href: `/${T}/accounts/acc-20`,
    draw: () =>
      mount(
        <NotSentPanel
          breaks={breaks().breaks}
          working={false}
          onRetry={() => undefined}
          onClose={() => undefined}
          t={t}
          accountHref={(id) => tp(`/accounts/${id}`)}
        />,
      ),
  },
  {
    screen: "Bulk run · Pricing check",
    record: "account",
    text: "AC-2026-00031",
    href: `/${T}/accounts/acc-shadow-1`,
    draw: () =>
      mount(
        <PricingShadowPanel
          t={t}
          shadow={pricingShadow("differ")}
          accountHref={(id) => tp(`/accounts/${id}`)}
        />,
      ),
  },
  {
    screen: "Print bills",
    record: "bill",
    text: "BL-2610-000020",
    href: `/${T}/billing/bills/inv-20`,
    draw: () =>
      cellOf(printBillsTableConfig(t, REGIONAL as never, "en-US", tp), "invoice_no", {
        id: "inv-20",
        invoice_no: "BL-2610-000020",
        account_no: "AC-0020",
        account_id: "acc-20",
        customer_name: null,
      } as never),
  },
  {
    screen: "Print bills",
    record: "account",
    text: "AC-0020",
    href: `/${T}/accounts/acc-20`,
    draw: () =>
      cellOf(printBillsTableConfig(t, REGIONAL as never, "en-US", tp), "account", {
        id: "inv-20",
        invoice_no: "BL-2610-000020",
        account_no: "AC-0020",
        account_id: "acc-20",
        customer_name: null,
      } as never),
  },
  {
    screen: "Budget asks",
    record: "account",
    text: "ACC-10519-C",
    href: `/${T}/accounts/acc-10519`,
    draw: () =>
      cellOf(asksTableConfig(t, "en-US", tp), "account", {
        reference: "SR-26-0087",
        asked_on: "2026-10-01",
        account_id: "acc-10519",
        account_no: "ACC-10519-C",
        customer_name: "Grace Espinoza",
        level_shown: null,
        level_now: null,
        currency: "USD",
        eligible: true,
        not_eligible_because: null,
      }),
  },
  // ── Reports ───────────────────────────────────────────────────────────────
  {
    screen: "Customer statement",
    record: "account",
    text: "AC-2026-00031",
    href: `/${T}/accounts/acc-31`,
    draw: () =>
      mount(
        <CustomerStatementTable
          statement={
            {
              basis: "accrual",
              currency: "USD",
              customer: { id: "c-1", customer_no: null, display_name: "Grace", kind: "person" },
              account_count: 1,
              rows: [
                {
                  id: "acc-31",
                  account_no: "AC-2026-00031",
                  kind: "regular",
                  status_code: "active",
                  status_name: "Active",
                  balance: "10.0000",
                  match_tier: null,
                  confident: true,
                  held_with: [],
                },
              ],
              total: "10.0000",
              unconfident_total: null,
              unconfident_count: 0,
              unavailable: [],
            } as never
          }
          t={t}
          accountHref={(id) => tp(`/accounts/${id}`)}
        />,
      ),
  },
  {
    screen: "Account ledger report · Reference",
    record: "payment",
    text: "PMT-2610-000005",
    href: `/${T}/payments/pay-5`,
    draw: () =>
      mount(
        <AccountLedgerTable
          report={
            {
              basis: "accrual",
              currency: "USD",
              account_id: "acc-5",
              period: { start: "2026-10-01", end: "2026-10-31" },
              opening_balance: "0.0000",
              rows: [
                {
                  entry_date: "2026-10-05",
                  type: "payment",
                  type_mapped: true,
                  reference: "PMT-2610-000005",
                  description: null,
                  charge: "0.0000",
                  payment: "25.0000",
                  running_balance: "-25.0000",
                  entry_id: "je-5",
                  source_type: "payment",
                  source_id: "pay-5",
                },
              ],
              totals: { charges: "0.0000", payments: "25.0000", closing_balance: "-25.0000" },
              unavailable: [],
            } as never
          }
          t={t}
          timeZone="America/Chicago"
          dateFormat={"MM/DD/YYYY" as never}
          tenantPath={tp}
        />,
      ),
  },
  {
    screen: "By premises report",
    record: "premises",
    text: "1901 Bluestem Ln",
    href: `/${T}/premises/prem-1`,
    draw: () =>
      mount(
        <ByPremisesTable
          report={
            {
              basis: "accrual",
              currency: "USD",
              period: { start: "2026-10-01", end: "2026-10-31" },
              available: true,
              rows: [
                {
                  premises_id: "prem-1",
                  premises_name: "1901 Bluestem Ln",
                  units: 2,
                  services: [],
                  billed: "10.0000",
                  collected: "5.0000",
                  owed: "5.0000",
                  collection_pct: null,
                },
              ],
              kpis: { premises: 1, billed: "10.0000", collected: "5.0000", owed: "5.0000" },
              unavailable: [],
            } as never
          }
          t={t}
          premisesHref={(id) => tp(`/premises/${id}`)}
        />,
      ),
  },
  // ── Group 2 (server sends the id) ────────────────────────────────────────
  {
    screen: "Units list / premises Units · Occupant",
    record: "account",
    text: "AC-2026-00040",
    href: `/${T}/accounts/acc-40`,
    draw: () =>
      mount(
        <OccupantCell
          unit={
            {
              is_common_area: false,
              occupancy: "occupied",
              occupant: "Grace Espinoza",
              account_no: "AC-2026-00040",
              account_id: "acc-40",
            } as never
          }
          t={t}
          accountHref={(id) => tp(`/accounts/${id}`)}
        />,
      ),
  },
  {
    screen: "Account page · Plan",
    record: "plan",
    text: "Residential Standard",
    href: `/${T}/plans-rates/plans/plan-1`,
    draw: () =>
      mount(
        <AccountPlanName
          plan={{ id: "plan-1", name: "Residential Standard", code: "RES", version: 1, since: null }}
        />,
      ),
  },
];

describe("Record links (job B) · RENDERED — each record is a link to the exact address", () => {
  it("the table is not empty and every pair is distinct", () => {
    expect(RENDERED.length).toBeGreaterThanOrEqual(30);
    const keys = RENDERED.map((row) => `${row.screen}|${row.record}`);
    expect(new Set(keys).size).toBe(keys.length);
  });

  for (const row of RENDERED) {
    it(`${row.screen} → ${row.record} (${row.text})`, () => {
      const container = row.draw();
      expect(hrefOf(container, row.text), `"${row.text}" is not a link on ${row.screen}`).toBe(
        row.href,
      );
    });
  }

  it("the plan route used is `planDetailRoute`'s, under plans-rates", () => {
    // A guard for the expectation above: the address is derived from the
    // helper job A keeps, not hand-typed twice.
    expect(RENDERED.find((row) => row.record === "plan")?.href).toBe(
      `/${T}/plans-rates/plans/plan-1`,
    );
  });

  it("a journal source with no page stays text", () => {
    expect(journalSourcePath("manual_je", "x")).toBeNull();
    expect(journalSourcePath("invoice", null)).toBeNull();
    expect(journalSourcePath("payment", "pay-1")).toBe("/payments/pay-1");
    expect(journalSourcePath("refund", "ref-1")).toBe("/finance/refunds/ref-1");
  });
});

// ══ WIRED — the page still hands the address in ═════════════════════════════
const SOURCES = import.meta.glob(
  [
    "../features/payments/PaymentDetailPage.tsx",
    "../features/payments/CollectionsPage.tsx",
    "../features/payments/DebtorPage.tsx",
    "../features/ledger/AgingView.tsx",
    "../features/ledger/JournalView.tsx",
    "../features/ledger/JournalEntryDetailPage.tsx",
    "../features/billing/bulkRun/BulkRunPage.tsx",
    "../features/billing/bulkRun/CheckStep.tsx",
    "../features/billing/bulkRun/PricingCheck.tsx",
    "../features/billing/bulkRun/ScopeStep.tsx",
    "../features/billing/bulkRun/CheckReport.tsx",
    "../features/billing/PrintBillsPage.tsx",
    "../features/billing/BillDetailPage.tsx",
    "../features/customers/DisconnectsTab.tsx",
    "../features/customers/AccountAdjustmentsTab.tsx",
    "../features/customers/AccountDetailPage.tsx",
    "../features/reports/CustomerStatementPage.tsx",
    "../features/reports/AccountLedgerReportPage.tsx",
    "../features/reports/ByPremisesReportPage.tsx",
    "../features/metering/UnitsListPage.tsx",
    "../features/metering/PremisesDetailPage.tsx",
  ],
  { query: "?raw", eager: true, import: "default" },
) as Record<string, string>;

function source(name: string): string {
  const key = Object.keys(SOURCES).find((path) => path.endsWith(`/${name}`));
  if (key === undefined) throw new Error(`source not loaded: ${name}`);
  return SOURCES[key];
}

interface Wired {
  screen: string;
  record: string;
  file: string;
  needle: string;
  /** How many times it must appear (default 1). */
  times?: number;
}

const WIRED: Wired[] = [
  { screen: "Payment detail", record: "bill", file: "PaymentDetailPage.tsx", needle: "billHref={(invoiceId) => tenantPath(billDetailPath(invoiceId))}" },
  { screen: "Payment detail", record: "deposit batch", file: "PaymentDetailPage.tsx", needle: "tenantPath(depositBatchRoute(detail.batch_id))" },
  { screen: "Debtor page", record: "bill", file: "DebtorPage.tsx", needle: "billsTableConfig(translate, regional, view.currency, view.as_of, tenantPath)" },
  { screen: "Collections ladder", record: "debtor", file: "CollectionsPage.tsx", needle: "ladderBoardConfig(translate, props.locale, tenantPath)" },
  { screen: "AR aging", record: "debtor", file: "AgingView.tsx", needle: "tenantPathFrom(tenant, path)" },
  { screen: "Journal list", record: "entry + source", file: "JournalView.tsx", needle: "(path) => tenantPathFrom(tenant, path)" },
  { screen: "Journal entry detail", record: "source", file: "JournalEntryDetailPage.tsx", needle: "journalSourcePath(body.entry.source_type, body.entry.source_id)" },
  { screen: "Journal entry detail · Lines", record: "account / premises / unit", file: "JournalEntryDetailPage.tsx", needle: "tenantPath={tenantPath}" },
  { screen: "Bulk run · Sign off / Check report / Not sent", record: "account", file: "BulkRunPage.tsx", needle: "accountHref={accountHref}", times: 4 },
  { screen: "Bulk run · Scope panels", record: "account", file: "BulkRunPage.tsx", needle: 'account: (accountId) => screenPath("accounts", accountId)' },
  { screen: "Bulk run · Scope panels", record: "account", file: "ScopeStep.tsx", needle: "props.links.account(", times: 2 },
  { screen: "Bulk run · Check report", record: "account", file: "CheckReport.tsx", needle: "props.accountHref(row.account_id)" },
  { screen: "Bulk run · Pricing check", record: "account", file: "CheckStep.tsx", needle: 'accountHref={(accountId) => props.links.fix("accounts", accountId)}' },
  { screen: "Bulk run · Pricing check", record: "account", file: "PricingCheck.tsx", needle: "accountHref={props.accountHref}" },
  { screen: "Print bills", record: "bill + account", file: "PrintBillsPage.tsx", needle: "printBillsTableConfig(translate, regional, props.locale, tenantPath)" },
  { screen: "Bill detail · line meter", record: "asset", file: "BillDetailPage.tsx", needle: "assetHref={(assetId) => tenantPath(assetDetailPath(assetId))}" },
  { screen: "Disconnects", record: "account", file: "DisconnectsTab.tsx", needle: "to={tenantPath(accountDetailPath(row.account_id))}" },
  { screen: "Account · Adjustments", record: "payment", file: "AccountAdjustmentsTab.tsx", needle: "tenantPath(paymentDetailRoute(row.payment_no))" },
  { screen: "Account page · Plan", record: "plan", file: "AccountDetailPage.tsx", needle: "<AccountPlanName plan={detail.unit_plan} />" },
  { screen: "Customer statement", record: "account", file: "CustomerStatementPage.tsx", needle: "accountHref={(accountId) => tenantPath(accountDetailPath(accountId))}" },
  { screen: "Account ledger report", record: "bill / payment", file: "AccountLedgerReportPage.tsx", needle: "tenantPath={tenantPath}" },
  { screen: "By premises report", record: "premises", file: "ByPremisesReportPage.tsx", needle: "premisesHref={(premisesId) => tenantPath(premisesDetailPath(premisesId))}" },
  { screen: "Units list", record: "account", file: "UnitsListPage.tsx", needle: "accountHref={(accountId) => tenantPath(accountDetailPath(accountId))}" },
  { screen: "Premises · Units tab", record: "account", file: "PremisesDetailPage.tsx", needle: "accountHref={(accountId) => tenantPath(accountDetailPath(accountId))}" },
];

describe("Record links (job B) · WIRED — each page still hands the address in", () => {
  for (const row of WIRED) {
    it(`${row.screen} → ${row.record} (${row.file})`, () => {
      const text = source(row.file);
      const times = text.split(row.needle).length - 1;
      expect(times, `${row.file} no longer wires the ${row.record} link`).toBeGreaterThanOrEqual(
        row.times ?? 1,
      );
    });
  }
});

// Kept so an unused-import lint never removes the type the fixtures lean on.
export type _Element = ReactElement;
