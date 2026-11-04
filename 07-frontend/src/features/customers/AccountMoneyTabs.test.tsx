// ── Trace ──────────────────────────────────────────────
// Screens:  S21 · ACC-02 tabs 2–5 (Bills · Payments · Credits · Payment plan)
// Drawing:  04-docs/05-modules/03-customers/blueprint/02-account-detail.md
//           lines 523–860 — ACC-T02 · ACC-T03 · ACC-T04 · ACC-T05
// Rules:    B14 rule 41 (the product matches the blueprint) · B14 rule 33
//           (on-screen text is capped by what it is for; RATIONALE is zero words)
// ───────────────────────────────────────────────────────
//
// PO ruling 2026-09-13: *"Product screen should match exactly in visual with
// Drawing in Blueprint - thats a test"*.
//
// ⚠ **WHAT THESE CASES CAN AND CANNOT SAY.** jsdom performs no layout, so none
// of them can tell you the screen LOOKS like the drawing — that is
// `10-scripts/render-checks/acc02-tab-conformance.mjs`, driven in a browser at
// 1280 and 1440 against `drawn/acc02-<tab>.json`. What they hold is PRESENCE
// and ORDER, which the browser census cannot hold for a list whose rows have
// not arrived: the shared `DataTable` swaps its whole table for the empty
// block, so on an unbilled account there are no column heads to measure. The
// two halves are complementary and neither is a substitute for the other.
//
// ⚠ **WHY THIS IS ITS OWN FILE AND NOT FIVE MORE CASES IN
// `AccountDetailPage.test.tsx` — MEASURED, NOT PREFERRED.** Added there, these
// same five cases turned two of the NOTES tab's cases red, on copy that was
// never missing: with three or more of them present the Notes table renders its
// loading skeleton. One of them alone is harmless and so is any pair, which is
// the signature of a cross-test leak in a 2,900-line file rather than of a
// defect in anything either lane wrote. Three lanes were editing that file at
// once; a file per lane costs nothing and cannot do this.
//
// These mount the GROUP COMPONENTS rather than the whole page, which is also
// why they need no account-detail, audit, notes or permissions seed.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { AccountDetail, PaymentPlanContext } from "@/api/endpoints";
import { billsCells, billsTableConfig } from "@/features/billing/BillsListPage";
import { paymentsCells, paymentsTableConfig } from "@/features/payments/PaymentsPage";
import { accountPlanKey } from "@/features/payments/paymentsShared";

import { AccountCreditsGroup, AccountPlanGroups, dunningNoticesParams } from "./AccountMoneyTabs";
import { accountCreditNotesKey } from "./creditNoteEndpoints";
import type { AccountCreditNote } from "./creditNoteEndpoints";

const TEST_TENANT = "brazosbend";
const ACCOUNT_ID = "acc-10432";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const tp = (path: string) => `/${TEST_TENANT}${path}`;

/** The account this tab is standing on. Only two of its fields are read here —
 *  the id, and the ageing the drawing labels `Oldest unpaid`. */
function detail(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: ACCOUNT_ID,
    account_no: "A-10432",
    kind: "regular",
    name: "Miller, Sarah",
    unit_id: "u-10432a",
    unit_label: "A",
    premise: "1408 Elm St · A",
    services: ["electric"],
    balance: "247.300000",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    balance_not_yet_billable: false,
    balance_cached: "0.000000",
    currency: "USD",
    status: "active",
    status_name: "Active",
    status_behavior_class: "billable",
    account_type: "residential",
    account_subtype: null,
    autopay: false,
    opened_at: "2024-02-14",
    closed_at: null,
    last_bill_at: null,
    aging: null,
    deposit_on_file: "0.000000",
    deposit_received_on: null,
    credit_tier: null,
    tax_exempt: false,
    tax_exempt_ref: null,
    tax_exempt_expires: null,
    bad_address: false,
    nsf_count: 0,
    preferred_language: null,
    custom_data: {},
    contacts: [],
    addresses: [],
    service_agreements: [],
    meters: [],
    plan: null,
    plan_snapshot_unavailable: "BR-CUS-029",
    unit_plan: null,
    customer: null,
    ...over,
  };
}

/** An account that has never agreed a plan, as the server answers it. */
function planContext(): PaymentPlanContext {
  return {
    account_id: ACCOUNT_ID,
    account_no: "A-10432",
    name: "Miller, Sarah",
    balance: "2410.000000",
    currency: "USD",
    balance_unavailable: null,
    balance_basis: "posting",
    as_of: "2026-09-13",
    plans: [],
    plans_unavailable: null,
    live_plan: null,
    can_propose: true,
    cannot_propose_reason: null,
    cadences: ["monthly"],
    agreement_channels: ["email"],
    defaults: { autopay_enabled: true, suspend_late_fees: false, suspend_disconnect: true },
    current_bill_still_due: true,
    plan_can_be_voided: false,
  };
}

function creditNote(over: Partial<AccountCreditNote> = {}): AccountCreditNote {
  return {
    id: "cn-1",
    credit_note_no: "CN-2606-000014",
    amount: "-86.400000",
    currency: "USD",
    reason: "Water charge billed in error",
    issued_at: "2026-06-28T00:00:00Z",
    invoice_id: "inv-1",
    invoice_no: "BL-2605-000163",
    ...over,
  };
}

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, NOT A BARE `MemoryRouter`.** Without
 * a `/:tenant/…` route `useParams().tenant` is undefined and every address the
 * page builds comes out `//…` — a protocol-relative URL to another host, which
 * reads as a perfectly good string to `toContain` (hard-won law 2).
 */
function render(node: React.ReactNode, seed: (q: QueryClient) => void = () => undefined): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  seed(queryClient);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts/${ACCOUNT_ID}`]}>
        <Routes>
          <Route path="/:tenant/accounts/:accountId" element={node} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Every group hook in the markup, in document order. */
function hooks(html: string): string[] {
  return (html.match(/data-overview-group="([a-z-]+)"/g) ?? []).map((one) =>
    one.replace(/^data-overview-group="/, "").replace(/"$/, ""),
  );
}

/** Asserts each string appears, and appears in this order. */
function inOrder(html: string, wrap: (s: string) => string, items: string[]): void {
  let at = 0;
  for (const item of items) {
    const next = html.indexOf(wrap(item), at);
    expect(next, `${item} is drawn, in the drawn order`).toBeGreaterThan(-1);
    at = next + 1;
  }
}

/** The column labels a clerk actually sees, in order. */
function shown(config: { columns: { label: string; defaultVisible?: boolean }[] }): string[] {
  return config.columns.filter((c) => c.defaultVisible !== false).map((c) => c.label);
}

describe("ACC-02 · the four money tabs are drawn as the blueprint draws them", () => {
  it("ACC-T02: Bills draws the nine columns the blueprint draws, in the drawn order", () => {
    const config = billsTableConfig(t, billsCells(t, tp, "UTC", "MM/DD/YYYY"), "account");
    expect(shown(config)).toEqual([
      t("billing.bills.col.billNo"),
      t("billing.bills.col.cycle"),
      t("billing.bills.col.issueDate"),
      t("billing.bills.col.dueDate"),
      t("billing.bills.col.subtotal"),
      t("billing.bills.col.tax"),
      t("billing.bills.col.total"),
      t("billing.bills.col.status"),
      t("billing.bills.col.actions"),
    ]);
  });

  it("ACC-T03: Payments drops Account and Customer on the account's own tab", () => {
    const cells = paymentsCells(t, tp, "UTC", "MM/DD/YYYY");
    const onTab = paymentsTableConfig(t, cells, undefined, undefined, { scope: "account" });
    // The eight the blueprint draws, in the drawn order. The account is the
    // page a clerk is standing on and its number is in the header three lines
    // above, so neither of the two that name it is drawn here.
    expect(shown(onTab)).toEqual([
      t("payments.col.paymentNo"),
      t("payments.col.postedAt"),
      t("payments.col.type"),
      t("payments.col.method"),
      t("payments.col.confirmation"),
      t("payments.col.appliedTo"),
      t("payments.col.amount"),
      t("payments.col.status"),
    ]);
    // S33 — the utility-wide list — is untouched: there the account is the one
    // thing that tells two rows apart.
    const wide = paymentsTableConfig(t, cells);
    expect(shown(wide)).toContain(t("payments.col.account"));
    expect(shown(wide)).toContain(t("payments.col.customer"));
  });

  it("ACC-T04: Credits keeps its six drawn column heads with nothing to list", () => {
    const html = render(
      <AccountCreditsGroup accountId={ACCOUNT_ID} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" />,
      (q) =>
        q.setQueryData(accountCreditNotesKey(ACCOUNT_ID), {
          account_id: ACCOUNT_ID,
          credit_notes: [],
          count: 0,
          truncated: false,
        }),
    );
    expect(hooks(html)).toEqual(["credits"]);
    inOrder(html, (s) => `<th>${s}</th>`, [
      t("customers.account.credits.col.creditNoteNo"),
      t("billing.bill.col.issued"),
      t("billing.bill.col.reason"),
      t("customers.account.credits.col.againstBill"),
      t("billing.bill.col.amount"),
      t("billing.bills.col.status"),
    ]);
    // An empty list states the absence in five words and draws no row.
    expect(html).toContain("No credits on this account.");
  });

  it("ACC-T04: a credit note draws its number, its bill and a STATUS nothing holds", () => {
    const html = render(
      <AccountCreditsGroup accountId={ACCOUNT_ID} t={t} timeZone="UTC" dateFormat="MM/DD/YYYY" />,
      (q) =>
        q.setQueryData(accountCreditNotesKey(ACCOUNT_ID), {
          account_id: ACCOUNT_ID,
          credit_notes: [creditNote()],
          count: 1,
          truncated: false,
        }),
    );
    expect(html).toContain("CN-2606-000014");
    expect(html).toContain("Water charge billed in error");
    expect(html).toContain("BL-2605-000163");
    // ⚠ **`billing.CreditNote` HAS NO STATUS COLUMN AT ALL.** The drawing reads
    // `Applied`; deriving it from *has a bill* would be this screen inventing a
    // word another module owns, so the cell states the absence.
    expect(html).toContain(t("customers.account.credits.statusAbsent"));
    // B14 rule 31 — the row's id is a React key and never a visible value.
    expect(html).not.toContain("cn-1");
  });

  it("ACC-T05: Payment plan is the three drawn groups, and the arrears facts are in order", () => {
    const html = render(<AccountPlanGroups detail={detail()} t={t} />, (q) =>
      q.setQueryData(accountPlanKey(ACCOUNT_ID), planContext()),
    );
    expect(hooks(html)).toEqual(["plan-now", "plan-history", "plan-instalments"]);
    inOrder(html, (s) => `<dt>${s}</dt>`, [
      t("customers.account.plan.field.arrears"),
      t("customers.account.plan.field.oldestUnpaid"),
      t("customers.account.plan.field.dunning"),
    ]);
    // The two tables' drawn heads.
    inOrder(html, (s) => `<th>${s}</th>`, [
      t("customers.account.plan.col.planNo"),
      t("customers.account.plan.col.opened"),
      t("customers.account.plan.col.spread"),
      t("customers.account.plan.col.instalments"),
      t("customers.account.plan.col.outcome"),
      t("customers.account.plan.col.seq"),
      t("customers.account.plan.col.due"),
      t("customers.account.plan.col.instalment"),
      t("customers.account.plan.col.paidOn"),
      t("customers.account.plan.col.state"),
    ]);
    // The one control the drawing puts on this tab, and it opens S24 — asserted
    // by ADDRESS, so a link built by guessing the label cannot pass.
    expect(html).toContain(t("customers.account.plan.propose"));
    expect(html).toContain(`/${TEST_TENANT}/accounts/${ACCOUNT_ID}/payment-plan`);
  });

  it("ACC-T05: `Oldest unpaid` is the account's own ageing, and states its absence", () => {
    const withAgeing = render(
      <AccountPlanGroups detail={{ ...detail(), ageing_days_past_due: 62 }} t={t} />,
      (q) => q.setQueryData(accountPlanKey(ACCOUNT_ID), planContext()),
    );
    expect(withAgeing).toContain("62 days");
    const without = render(<AccountPlanGroups detail={detail()} t={t} />, (q) =>
      q.setQueryData(accountPlanKey(ACCOUNT_ID), planContext()),
    );
    // Never a zero and never a blank: ageing needs each open bill's due date and
    // billing publishes none per account.
    expect(without).toContain(t("customers.account.plan.oldestUnpaidAbsent"));
    expect(without).not.toContain("0 days");
  });

  it("DEF-PAY-10655: `Dunning so far` counts notices SENT, never the skips beside them", () => {
    // The history serves sends and skips together (J4 step 2). On 2026-10-29
    // an account sent ONE printed letter read "3 notices issued" — the other
    // two rows were "email · no contact" and "SMS · no consent".
    expect(dunningNoticesParams(ACCOUNT_ID)).toEqual({
      filters: { account_id: ACCOUNT_ID, outcome: "sent" },
      per: 50,
    });
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: B14 rule 41 · the ACC-02 money tabs (PO ruling 2026-09-13)
// generated: 2026-09-13 by the ACC-02 Bills/Payments/Credits/Plan lane
// gates: tsc✔ · eslint --max-warnings 0✔ · the browser census reports 0
//        divergences on all four tabs at 1280 and 1440
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
