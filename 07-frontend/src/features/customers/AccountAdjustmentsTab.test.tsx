// ── Trace ──────────────────────────────────────────────
// Change:   B14 rule 41 (PO 2026-09-13) — `ACC-T09`'s FRONTEND cases.
// Rules:    B14 rule 16 (the pagination footer) · rule 19 (the search prompt) ·
//           rule 31 (no database id on screen) · rule 33 (rationale is ZERO
//           words on screen) · hard-won law 2 (built is not wired).
// ───────────────────────────────────────────────────────
//
// ⚠ **THE FIRST CASE IS LAW 2 AND IT IS THE ONE THAT MATTERS.** This tab drew
// six column heads over ONE spanning cell for weeks while `GET /payments`
// accepted `f.account_id` AND `f.type`, paged in the database and served four
// of the six columns. Nothing had ever called it with `f.type=adjustment`, and
// nothing could see that: the frame rendered, every assertion passed, and the
// feature did not exist. So the first thing asserted is that the tab CALLS the
// endpoint, with BOTH filters on the wire.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import { getPayments } from "@/api/endpoints";
import type { PaymentRow } from "@/api/endpoints";
import { defaultRequestState } from "@/components/tableTypes";

import {
  AccountAdjustmentsTab,
  accountAdjustmentsKey,
  accountAdjustmentsRequest,
  adjustmentsTableConfig,
  appliedToLabel,
} from "./AccountAdjustmentsTab";

const TEST_TENANT = "brazosbend";
const ACCOUNT = "3f1a9c2e-0000-7000-8000-000000000001";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const CONFIG = adjustmentsTableConfig(t, {
  date: () => <span />,
  amount: () => <span />,
});

function row(overrides: Partial<PaymentRow> = {}): PaymentRow {
  return {
    id: "0198f3c2-0000-7000-8000-00000000000a",
    payment_no: "ADJ-2607-000031",
    account_id: ACCOUNT,
    account_no: "A-11812",
    customer_name: "Bramble Bakery",
    type: "adjustment",
    method: null,
    method_name: null,
    confirmation: null,
    memo: null,
    amount: "-118.2500",
    currency: "USD",
    status: "cleared",
    purpose: "bill",
    posted_at: "2026-07-03T00:00:00Z",
    cleared_at: "2026-07-03T00:00:00Z",
    applied_to: [
      { invoice_id: "0198f3c2-0000-7000-8000-00000000000b", invoice_number: "BL-2606-000181", amount: "-118.2500" },
    ],
    applied_total: "-118.2500",
    deposit_batch_id: null,
    receipt_no: null,
    cheque_date: null,
    drawer_bank: null,
    bankable_from: null,
    moved_from_payment_no: null,
    moved_from_account_no: null,
    moved_to_payment_no: null,
    moved_to_account_no: null,
    // `CR-135` `P1.9` — the blueprint's §03 2·1 Source and Batch.
    origin: "entry",
    batch_ref: null,
    batch_kind: null,
    ...overrides,
  } as PaymentRow;
}

async function renderTab(rows: PaymentRow[]): Promise<{ html: string; urls: string[] }> {
  const urls: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input) => {
      urls.push(String(input));
      return new Response(
        JSON.stringify({
          count: rows.length,
          next: null,
          previous: null,
          results: rows,
          totals: { count: rows.length, amount: null, currency: "USD", amount_unavailable: "no_cash_rows", excluded_count: rows.length },
          methods: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    },
  });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, retryOnMount: false } },
  });
  // ⚠ **PREFETCHED UNDER THE SAME KEY AND THE SAME FUNCTION THE COMPONENT
  // USES.** `renderToStaticMarkup` fires no effects, so a query that has not
  // already resolved renders PENDING — which is a loading skeleton, not the
  // table, and every assertion about a cell then fails for a reason that has
  // nothing to do with the screen. A harness that prefetches under a DIFFERENT
  // key does exactly the same thing while looking correct.
  const state = defaultRequestState(CONFIG);
  await queryClient.fetchQuery({
    queryKey: accountAdjustmentsKey(ACCOUNT, state),
    // The component's OWN builder — so a harness that drifts from the screen
    // is not possible, which is the flaw the law-2 case below records.
    queryFn: () => getPayments(accountAdjustmentsRequest(ACCOUNT, state), client),
  });
  const html = renderToStaticMarkup(
    // ⚠ **MOUNTED UNDER THE REAL PATH PATTERN**, so `useParams().tenant` is a
    // tenant and not `undefined` — otherwise every address this page builds
    // comes out `//…`, a protocol-relative URL to another host that reads as a
    // perfectly good string to `toContain` (hard-won law 2's fixture clause).
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts/${ACCOUNT}?tab=adjustments`]}>
        <AccountAdjustmentsTab
          accountId={ACCOUNT}
          client={client}
          t={t}
          timeZone="America/Chicago"
          dateFormat="MM/DD/YYYY"
          onNew={() => undefined}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { html, urls };
}

describe("ACC-T09 · the Adjustments tab", () => {
  it("law 2 — the tab's own request carries BOTH filters, and reaches the payments route", async () => {
    // ⚠ **THIS CASE READ THE HARNESS'S OWN URL UNTIL IT WAS MUTATION-TESTED.**
    // `renderToStaticMarkup` fires no queries, so every URL a stubbed `fetch`
    // records here is the PREFETCH's — deleting `f.type=adjustment` from the
    // component left this green (law 7, *looking at the wrong thing*). It
    // asserts the builder the component itself calls now, and the prefetch
    // calls the same one, so the two cannot differ.
    const state = defaultRequestState(CONFIG);
    const request = accountAdjustmentsRequest(ACCOUNT, state);
    expect(request.filters).toEqual({ account_id: ACCOUNT, type: "adjustment" });

    // …and the route it lands on is payments', under the tenant.
    const { urls } = await renderTab([row()]);
    expect(urls.length).toBeGreaterThanOrEqual(1);
    expect(urls[0]).toContain("/payments");
    expect(urls[0]).toContain(TEST_TENANT);
    expect(urls[0]).toContain(`f.account_id=${ACCOUNT}`);
    expect(urls[0]).toContain("f.type=adjustment");
  });

  it("draws `ACC-T09`'s six columns, in the drawn order", () => {
    expect(CONFIG.columns.map((column) => column.key)).toEqual([
      "date",
      "adjustmentNo",
      "reason",
      "appliedTo",
      "amount",
      "approvedBy",
    ]);
    expect(CONFIG.columns.map((column) => column.label)).toEqual([
      t("customers.account.adjustments.col.date"),
      t("customers.account.adjustments.col.adjustmentNo"),
      t("customers.account.adjustments.col.reason"),
      t("customers.account.adjustments.col.appliedTo"),
      t("customers.account.adjustments.col.amount"),
      t("customers.account.adjustments.col.approvedBy"),
    ]);
  });

  it("REASON and APPROVED BY state their absence — never blank, never a zero", async () => {
    const { html } = await renderTab([row()]);
    // Neither has a column anywhere in this product: the reason a clerk types
    // is written into the `audit_log` row alone (which is PRUNED), and nothing
    // records who approved an adjustment at either end.
    expect(html).toContain(t("customers.account.adjustments.notKept"));
    expect(html).toContain(t("customers.account.adjustments.notKeptWhy"));
    // ⚠ **AND NOT A ZERO.** `$0.00` in an Amount-adjacent cell is a claim
    // about a customer that nobody made.
    expect(html).not.toContain(">$0.00<");
  });

  it("B14 rule 33 — the rationale sentence is OFF the screen", async () => {
    const { html } = await renderTab([row()]);
    // The tab used to carry *"Adjustments show on the Payments tab, marked
    // Adjustment. This table needs two facts nothing keeps yet — the reason
    // and who approved it."* That is RATIONALE — why the product works this
    // way — and rule 33 puts it in the code and in the register. It is in the
    // component's own header.
    expect(html).not.toContain("Adjustments show on the Payments tab");
    expect(html).not.toContain(t("customers.account.arrives.adjustmentsListing"));
  });

  it("B14 rule 31 — the number is the visible value, and a row with none draws a dash", async () => {
    const { html } = await renderTab([row(), row({ id: "b", payment_no: null })]);
    expect(html).toContain("ADJ-2607-000031");
    // The uuid is the React key and the query nothing else; it must never be
    // the value of a cell.
    expect(html).not.toContain(">0198f3c2-0000-7000-8000-00000000000a<");
    expect(html).toContain("—");
  });

  it("APPLIED TO names the BILL, joins several, and is a dash when the money met none", () => {
    expect(appliedToLabel(row())).toBe("BL-2606-000181");
    expect(
      appliedToLabel(
        row({
          applied_to: [
            { invoice_id: "a", invoice_number: "BL-1", amount: "-1.0000" },
            { invoice_id: "b", invoice_number: "BL-2", amount: "-2.0000" },
          ],
        }),
      ),
    ).toBe("BL-1 · BL-2");
    // Carried as credit rather than applied — a real state, not a blank.
    expect(appliedToLabel(row({ applied_to: [] }))).toBeNull();
    // Billing could not resolve a number: the money it met is still shown in
    // the AMOUNT cell, and rule 31 forbids the id standing in here.
    expect(
      appliedToLabel(row({ applied_to: [{ invoice_id: "a", invoice_number: null, amount: "-1.0000" }] })),
    ).toBeNull();
  });

  it("B14 rule 16 — the list carries the toolbar and the pagination footer", async () => {
    const { html } = await renderTab([row()]);
    expect(html).toContain(t("customers.account.adjustments.search"));
    expect(html).toContain("table-pager");
    // rule 4 — the page header already carries this screen's one primary, so
    // the tab's own control is a SECONDARY.
    expect(html).toContain(t("customers.account.adjustments.new"));
    expect(html).toContain('data-variant="secondary"');
  });

  it("the census hook is on the drawn section, because no vitest case can see layout", async () => {
    const { html } = await renderTab([row()]);
    expect(html).toContain("data-account-overview");
    expect(html).toContain('data-overview-group="adjustments"');
  });
});


// ── Record links (PO ruling 2026-10-19) — the adjustment's number opens it ───
describe("Record links · an adjustment's number opens its payment page", () => {
  it("the number is a link to /payments/<number>, under the tenant", async () => {
    const { html } = await renderTab([row()]);
    expect(html).toMatch(
      new RegExp(`<a[^>]*href="/${TEST_TENANT}/payments/ADJ-2607-000031"[^>]*>ADJ-2607-000031</a>`),
    );
  });

  it("a row with no number draws no link", async () => {
    const { html } = await renderTab([row({ payment_no: null })]);
    expect(html).not.toContain(`/${TEST_TENANT}/payments/`);
  });
});
