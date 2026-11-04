// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-004 (S33 Record payments — the IS-5 capability row, the
//           "Applied to" column, the filter totals) · US-PAY-001 (the S22/S35
//           Record modal: both BR-PAY-021 dates, the allocation choice, the
//           idempotent submit and the result panel that says what it paid)
//           Screens: S33 · S22 · S35
// Rules:    BR-PAY-001 (the staff allocation choice) · BR-PAY-002 (the list
//           mutates nothing) · BR-PAY-012 (purpose) · BR-PAY-021 (BOTH dates
//           are columns AND are collected) · BR-PAY-024 (no receipt is queued
//           — the result says so) · BR-PAY-026 (the method list is LIVE) ·
//           BR-PAY-027 (the capability row) · BR-PAY-028 (one submit token) ·
//           BR-PAY-033 (the posting date is pre-filled and overridable) ·
//           BR-SHL-010 (an undeclared capability is not rendered) ·
//           BR-SHL-020 (plain-language failure) · BR-SHL-023 (one money path)
//           · BR-SHL-025 (a control this deployment cannot honour renders
//           DISABLED with its reason)
// ───────────────────────────────────────────────────────
// §4 test data is EP-PAY-01's own: PE-1 (check #8842, $292.87, ACC-1042,
// settling BL-2607-018311 $45.00 then BL-2608-018410 $247.87) and the S33
// prototype fixture rows, rendered through the seeded query cache, never a
// network.
//
// THE ASSERTIONS THAT MATTER MOST ARE THE NEGATIVE ONES. This screen must not
// print a receipt number where no receipt was queued, a deposit batch where no
// batch exists, a "$0.00 today" where the filter matched nothing, or an enabled
// "Split across bills" control that the server would refuse. Each of those is
// one row in the defect log's fabricated-value family.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import { PAYMENT_FILTERS, PAYMENT_PURPOSES, PAYMENT_SORTS } from "@/api/endpoints";
import type {
  MyPermissions,
  PaymentMethodOption,
  PaymentRow,
  PaymentsPageResponse,
  RecordedPayment,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { filterParamNames, parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";

import {
  PaymentsPage,
  RecordPaymentPanel,
  paymentsCells,
  paymentsFailureReason,
  paymentsFilters,
  paymentsParamsFrom,
  paymentsQueryKey,
  paymentsTableConfig,
  recordPaymentSchema,
} from "./PaymentsPage";
// ⚠ **`RecordPaymentModal` BECAME `RecordPaymentForm` ON 2026-09-23 (`DEF-PAY-6317`).**
// 2·3a is a PAGE at `/:tenant/payments/record/new` (blueprint p037), so the form
// is a COMPONENT (B14 rule 43) inside `FormPage` rather than `FormModal`. Same
// props, with `onClose` renamed `onCancel`.
import { RecordPaymentForm } from "./RecordPaymentPage";
import {
  ALLOCATION_CHOICES,
  PAYMENTS_TABS,
  PAYMENTS_TAB_RECORD,
  choiceNeedsTargets,
  paymentStatusLabel,
  paymentStatusTone,
  paymentsTabFrom,
  remainingToAllocate,
  targetsBody,
} from "./paymentsShared";
import en from "@/i18n/locales/en.json";

const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const CELLS = paymentsCells(t, (p) => p, "UTC", "MM/DD/YYYY");
const CONFIG = paymentsTableConfig(t, CELLS);

// The ids are the tenant's own `payment_methods` keys (`DEF-3206`): the filter
// and the Record form key on `code`, and `POST /payments/{id}/correct-reference`
// resolves its `tender_id` as the row's primary key, so the list serves both.
const METHODS: PaymentMethodOption[] = [
  { id: "met-ach", code: "ach", name: "ACH" },
  { id: "met-card", code: "card", name: "Card" },
  { id: "met-cash", code: "cash", name: "Cash" },
  { id: "met-check", code: "check", name: "Check" },
];

/** PE-1's own row: check #8842, $292.87, settling two bills. */
function payment(over: Partial<PaymentRow> = {}): PaymentRow {
  return {
    id: "pay-0412",
    payment_no: "PMT-2608-000412",
    account_id: "acc-1042",
    account_no: "A-10432",
    customer_name: "Miller, Sarah",
    type: "payment",
    method: "check",
    method_name: "Check",
    confirmation: "8842",
    memo: null,
    amount: "292.870000",
    currency: "USD",
    status: "cleared",
    purpose: "bill",
    posted_at: "2026-08-08T10:30:00Z",
    cleared_at: "2026-08-08T10:30:00Z",
    applied_to: [
      { invoice_id: "inv-18311", invoice_number: "BL-2607-018311", amount: "45.000000" },
      { invoice_id: "inv-18410", invoice_number: "BL-2608-018410", amount: "247.870000" },
    ],
    applied_total: "292.870000",
    // Both permanently null on this deployment — see the negative cases below.
    deposit_batch_id: null,
    receipt_no: null,
    // CR-059 CS-30 · CS-32 — a cheque's own state and the move marks.
    // Null on an ordinary payment, which is a STATE and not a missing value.
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
    ...over,
  };
}

/** The prototype's A-11340 row: $8,240.00 ACH, still PROCESSING (no clearing). */
function processing(over: Partial<PaymentRow> = {}): PaymentRow {
  return payment({
    id: "pay-8091",
    payment_no: "PMT-2608-000413",
    account_no: "A-11340",
    customer_name: "Northwind Mfg.",
    method: "ach",
    method_name: "ACH",
    confirmation: "ACH-2028091",
    amount: "8240.000000",
    status: "processing",
    cleared_at: null,
    applied_to: [],
    applied_total: "0.000000",
    ...over,
  });
}

function page(
  rows: PaymentRow[],
  over: Partial<Pick<PaymentsPageResponse, "totals" | "methods">> = {},
): PaymentsPageResponse {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    totals: {
      count: rows.length,
      amount: "292.870000",
      currency: "USD",
      // CR-059 CS-35 task 23: how many matched rows the CASH figure left out.
      excluded_count: 0,
      amount_unavailable: null,
    },
    methods: METHODS,
    ...over,
  };
}

function permissions(access: string): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: "payments_record", label: "Payments (record)", access }],
  };
}

function renderPayments(
  path: string,
  seed: { list?: PaymentsPageResponse; access?: string } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = parseTableParams(new URLSearchParams(path.split("?")[1] ?? ""), CONFIG);
  if (seed.list !== undefined) {
    queryClient.setQueryData(
      paymentsQueryKey(`${serializeTableParams(state, CONFIG).toString()}|`),
      seed.list,
    );
  }
  if (seed.access !== undefined) {
    queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access));
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <Routes>
            <Route path="/:tenant/payments" element={<PaymentsPage />} />
            <Route path="/:tenant/payments/:tab" element={<PaymentsPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Copy as `renderToStaticMarkup` writes it — an apostrophe in real English
 *  prose comes out as `&#x27;`, and a test that compared the raw string would
 *  fail on the copy being written well rather than on the screen being wrong. */
function escaped(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

/** The rows region only — the awaiting panels name the gaps in prose, and a
 *  whole-document `not.toContain` would read that prose as the defect it exists
 *  to prevent. */
function rowsRegion(html: string): string {
  const start = html.indexOf("<tbody");
  const end = html.indexOf("</tbody>");
  return start === -1 || end === -1 ? "" : html.slice(start, end);
}

describe("US-PAY-004 — the S33 Record-payments ledger", () => {
  it("US-PAY-004 TC-1: the default load renders the capability row's columns, posting date desc", () => {
    const html = renderPayments("/payments/record", { list: page([payment()]) });
    expect(html).toContain("PMT-2608-000412");
    expect(html).toContain("A-10432");
    expect(html).toContain("Miller, Sarah");
    expect(html).toContain("8842");
    // The capability matrix's own default: posted_at desc, and the SERVER sorts.
    expect(CONFIG.defaultSort).toEqual({ sort: "posted_at", dir: "desc" });
    expect(CONFIG.columns.find((column) => column.identity === true)?.key).toBe("payment_no");
    // Every sortable column is a key the server accepts — a control offering an
    // ordering the API cannot do is a lie a clerk would trust.
    expect(
      CONFIG.columns
        .filter((column) => column.sortable === true)
        .map((column) => column.key)
        .sort(),
    ).toEqual([...PAYMENT_SORTS].sort());
    // IS-3 / the capability row: account #, customer, confirmation #, address.
    // ⚠ **`address` JOINED ON 2026-09-09 (`CR-089` wave K, `PUJ-52`)** — the
    // server ORs the accounts at a matching property into this list's own
    // `WHERE`, and the prompt names it in all eleven catalogues. The
    // declaration and the sentence move together or one of them is lying.
    expect(CONFIG.searchFields).toEqual([
      "account_no",
      "customer_name",
      "confirmation",
      "address",
    ]);
  });

  it("US-PAY-004 §5 / BR-SHL-023: every money figure renders through MoneyCell", () => {
    const html = renderPayments("/payments/record", { list: page([payment()]) });
    expect(html).toContain("cell-money");
    expect(html).toContain("$292.87");
    // The six-decimal string is FORMATTED, never parsed, summed or re-rounded
    // in the browser (CLAUDE.md rule 2).
    expect(rowsRegion(html)).not.toContain("292.870000");
  });

  it("US-PAY-004 §5: the Applied-to cell lists EVERY bill the payment met, not the first", () => {
    const html = renderPayments("/payments/record", { list: page([payment()]) });
    expect(html).toContain("BL-2607-018311");
    expect(html).toContain("BL-2608-018410");
  });

  it("BR-PAY-021: a payment with no clearing date reads as PROCESSING, never as a blank date", () => {
    const html = renderPayments("/payments/record", { list: page([processing()]) });
    const rows = rowsRegion(html);
    // The default column set carries the STATUS, and it says processing…
    expect(rows).toContain(t("payments.status.processing"));
    // …and the row is not silently shown as having met a bill.
    expect(rows).toContain(t("payments.row.appliedToNone"));
    // The clearing DATE is an IS-5 "available" column rather than a default one
    // (the capability row's own split), so the cell is asserted directly. A
    // missing clearing date is a STATE — the money has not arrived — and it must
    // never render as the same "—" a genuinely absent field would.
    const cell = renderToStaticMarkup(<MemoryRouter>{CELLS.clearedAt(processing())}</MemoryRouter>);
    expect(cell).toContain(t("payments.row.notCleared"));
    // …while a payment that HAS cleared renders its date and no such note.
    const cleared = renderToStaticMarkup(<MemoryRouter>{CELLS.clearedAt(payment())}</MemoryRouter>);
    expect(cleared).not.toContain(t("payments.row.notCleared"));
  });

  it("hard-won law 1: the receipt number is stated ABSENT, never invented", () => {
    // ⚠ **THIS CASE NAMED `deposit_batch_id` UNTIL `2.334.0` AND ITS REASON HAD
    // EXPIRED (`DEF-PAY-6216`).** It read *"EP-PAY-06's batches are unbuilt"*,
    // and `reconciliation.cut_deposit_batches` has stamped every member payment
    // since bank rec shipped. The batch is a REAL fact now and it is served as
    // the batch's own code in the `batch` column, so the half of this assertion
    // that was about it has gone; the RULE it exists for — a stated absence
    // rather than an invented value — is unchanged and still asserted below,
    // and for the batch it is asserted in `bulkActions.test.tsx`.
    const config = paymentsTableConfig(t, CELLS);
    // A declared IS-5 "available" column, so a clerk can turn it on…
    expect(config.columns.map((column) => column.key)).toContain("receipt_no");
    // …and it renders a stated absence with its reason rather than a number
    // nobody can act on: BR-PAY-024's receipt queue is genuinely unbuilt, and a
    // plausible value here would be a claim about a customer.
    const html = renderToStaticMarkup(
      <MemoryRouter>{CELLS.receiptNo(payment())}</MemoryRouter>,
    );
    expect(html).toContain(t("payments.row.noReceipt"));
  });

  it("US-PAY-004 TC-1: the filter totals tie to the current filter — and state nothing when empty", () => {
    const html = renderPayments("/payments/record", { list: page([payment()]) });
    expect(html).toContain("$292.87");
    const empty = renderPayments("/payments/record", {
      list: page([], {
        totals: {
          count: 0,
          amount: null,
          currency: null,
          amount_unavailable: "no_rows",
          excluded_count: 0,
        },
      }),
    });
    // "$0.00 received" and "nothing matched this filter" are different claims
    // about a day's takings, and only the second one is true.
    expect(empty).not.toContain("$0.00");
    expect(empty).toContain(t("payments.totals.unavailable.no_rows"));
  });

  it("BR-PAY-027 / BR-REP-006: the method filter enumerates the tenant's LIVE list", () => {
    const filters = paymentsFilters(t, METHODS, "YYYY-MM-DD");
    const methodFilter = filters.find((filter) => filter.name === "method");
    expect(methodFilter?.options.map((option) => option.value)).toEqual([
      "ach",
      "card",
      "cash",
      "check",
    ]);
    // Every `f.` PARAM a declared filter owns is one the server accepts
    // (BR-SHL-010/011).
    //
    // ⚠ **THIS WALKED `filter.name` UNTIL 2026-09-03 AND THAT STOPPED
    // BEING THE SAME QUESTION (CR-059 CS-40).** A date range's `name` is the
    // CHIP's identity and a React key - `posted`, `cleared` - and is NEVER a URL
    // param; the two params it owns are `posted_from` and `posted_to`. Walking
    // the name reported this test red on a correct declaration, which is the
    // honest failure. `filterParamNames` is the ONE statement of which params a
    // filter owns, and both halves of the URL round trip read it.
    for (const filter of filters) {
      for (const param of filterParamNames(filter)) {
        expect(PAYMENT_FILTERS).toContain(param as (typeof PAYMENT_FILTERS)[number]);
      }
    }
  });

  it("CS-40 - both date ranges are declared, on the server's own param names", () => {
    // ⚠ RED FIRST, PROVED. Before the two `dateRangeFilter` entries
    // existed, this case reported:
    //     AssertionError: expected undefined to be defined
    // ...which is the whole of DEF-3504 on this screen: the server accepted all
    // four date params, the client already declared them in `PAYMENT_FILTERS`,
    // and no clerk could reach any of them.
    const filters = paymentsFilters(t, METHODS, "YYYY-MM-DD");
    const posted = filters.find((filter) => filter.name === "posted");
    const cleared = filters.find((filter) => filter.name === "cleared");
    expect(posted?.dateRange).toBeDefined();
    expect(cleared?.dateRange).toBeDefined();
    expect(posted?.dateRange?.from).toBe("posted_from");
    expect(posted?.dateRange?.to).toBe("posted_to");
    expect(cleared?.dateRange?.from).toBe("cleared_from");
    expect(cleared?.dateRange?.to).toBe("cleared_to");
    // A range offers no options, and it carries the TENANT's date format,
    // because the chip is the only place a tenant ever sees one (IS-8).
    expect(posted?.options).toEqual([]);
    expect(posted?.dateRange?.dateFormat).toBe("YYYY-MM-DD");
  });

  it("CS-40 - a range reaches the request as TWO ordinary params, not a new shape", () => {
    // Nothing moves on the API: `paymentsParamsFrom` spreads `state.filters`
    // through, and each end is an ordinary entry keyed by its own server param
    // name. That is why the count and the total narrow with the rows - all three
    // come off the one filtered response.
    const params = paymentsParamsFrom({
      q: "",
      sort: "posted_at",
      dir: "desc",
      page: 1,
      per: 50,
      filters: { posted_from: "2026-08-01", posted_to: "2026-08-31" },
    });
    expect(params.filters).toEqual({ posted_from: "2026-08-01", posted_to: "2026-08-31" });
  });

  it("CS-40 - the panel that said this could not work is GONE from every catalogue", () => {
    // A screen claiming an absence is not the absence. `t()` returns the KEY
    // when nothing defines it, which is exactly what this asserts - the same
    // removal the reverse/refund panel got when those routes landed.
    expect(t("payments.list.awaits.filters")).toBe("payments.list.awaits.filters");
    expect(t("payments.list.awaits.filtersTitle")).toBe("payments.list.awaits.filtersTitle");
  });

  it("BR-SHL-020: a 404 from a COLLECTION route says the API serves no payments list", () => {
    const absent = paymentsFailureReason(
      new ApiError(404, { code: null, message_key: "api.error.unexpected" }),
      t,
    );
    expect(absent).toBe(t("payments.list.failed.noEndpoint"));
    // Anything else is the SERVER's own sentence, never this screen's guess.
    const refused = paymentsFailureReason(
      new ApiError(422, { code: "BIZ-COMPLETENESS", message_key: "payments.record.refused" }),
      t,
    );
    expect(refused).not.toBe(t("payments.list.failed.noEndpoint"));
  });

  it("the three prototype tabs are the three the sidebar declares, and ALL THREE are built", () => {
    // ⚠ AMENDED 2026-08-16 (returned-mail lane): the strip is FOUR WIDE and the
    // fourth is deliberate. `paymentsShared.tsx` states the case in full — the
    // ladder could only ever be DRIVEN (`POST /collections/run` sends, advances
    // the tier and writes history on every path, skips included), so a clerk had
    // no way to LOOK first, and the sidebar renders no submenus (PO 2026-08-10)
    // which makes a page's tab strip the only route to a sub-destination. The
    // Finance page has carried five tabs against four ratified sidebar children
    // since it shipped.
    //
    // What this test still guards, and what went red rather than being smoothed:
    // the sidebar's THREE come FIRST and in the sidebar's own order, so a
    // sidebar item can never land on a tab other than the one its label names.
    // Only the tail may grow. Asserting `.slice(0, 3)` and stopping would have
    // let a fifth tab arrive unread, so the whole list is pinned too.
    // ⚠ **AMENDED 2026-09-22 (`P0.8`), AND THE GUARANTEE ABOVE IS NARROWED
    // RATHER THAN DROPPED.** The payments blueprint draws SEVEN tabs, and
    // `CLAUDE.md`'s ruling of 2026-09-14 gives a blueprint the flows as well as
    // the layout, so the strip is the drawing's. The three sidebar children
    // still map to the three tabs their labels name — which is all this case
    // ever guaranteed — but they are no longer the first three in a row:
    // **Counter, Imports and Settlements sit between `record` and
    // `outstandings`**, exactly as §03 draws them, and `collections` has left
    // the strip for a door on the Debtors tab.
    //
    // The whole list is still pinned, for the reason the paragraph above gives:
    // an eighth tab arriving unread is what `.slice()` alone would permit.
    // `sevenTabs.dom.test.tsx` owns the labels, the addresses and the holds.
    expect(PAYMENTS_TABS.map((tab) => tab.id)).toEqual([
      "summary",
      "record",
      "counter",
      "imports",
      "settlements",
      "refunds",
      "outstandings",
    ]);
    // The sidebar's own three, each still reachable at the id its label names.
    for (const declared of ["summary", "record", "outstandings"]) {
      expect(PAYMENTS_TABS.some((tab) => tab.id === declared)).toBe(true);
    }
    // Every tab in the strip has a label a human reads — an id rendered raw is
    // how a missing catalogue entry reaches a screen (G18's failure mode).
    for (const tab of PAYMENTS_TABS) {
      expect(t(tab.labelKey)).not.toBe(tab.labelKey);
    }
    expect(paymentsTabFrom(undefined)).toBe("summary");
    expect(paymentsTabFrom("record")).toBe(PAYMENTS_TAB_RECORD);
    expect(paymentsTabFrom("nonsense")).toBe("summary");
    // Until 2026-08-15 the Summary and Outstandings tabs rendered an *awaiting*
    // panel over two complete, tested read-models — hard-won law 2 in its
    // purest form. Both now CALL their endpoint, so the landing tab asks the
    // server for a business day instead of apologising for itself.
    const summary = renderPayments("/payments");
    expect(summary).toContain('id="summary_as_of"');
    expect(summary).toContain(escaped(t("payments.summary.asOf")));
    const outstandings = renderPayments("/payments/outstandings");
    expect(outstandings).toContain('id="as_of"');
    expect(outstandings).toContain(escaped(t("payments.outstandings.asOf")));
  });

  it("A5 §Payment: all six statuses have a label and a tone, and none is invented", () => {
    for (const status of ["posted", "cleared", "cancelled", "processing", "failed", "reversed"] as const) {
      expect(paymentStatusLabel(status, t)).not.toBe("");
      expect(paymentStatusTone(status)).toBeTruthy();
    }
  });
});

describe("US-PAY-001 — the S22/S35 Record payment modal", () => {
  it("BR-PAY-001: all FOUR allocation choices are offered, and two of them aim at bills", () => {
    // ⚠ **THIS CASE IS REWRITTEN, NOT DELETED (CR-059 CS-4, task 12,
    // 2026-09-02), AND THE OLD ASSERTION IS THE RECORD OF WHY.** It read
    // *"only the two allocation choices this deployment can honour are
    // enabled"* and checked `disabled: ["specific", "split"]` plus a reason
    // sentence containing *"we cannot yet show what each open bill still
    // owes"*. Both were TRUE from 2026-08-11: the engine executed all four and
    // no endpoint served the account's open-bill position (OQ-154), so the two
    // rendered disabled with that sentence under the field, on BOTH modals,
    // from one shared function.
    //
    // `GET /accounts/{id}/open-bills` serves it now, `OQ-154` is CLOSED, and
    // CS-4's own Proof is that *"the two disabled options become enabled AND
    // the on-screen reason text is deleted with them"*. So: four offered, none
    // disabled, and the sentence gone from all eleven catalogues.
    expect(ALLOCATION_CHOICES.map((choice) => choice.value)).toEqual([
      "oldest_first",
      "specific",
      "carry_credit",
      "split",
    ]);
    // BR-PAY-001's two "name the bill" choices are the two the picker serves.
    expect(ALLOCATION_CHOICES.filter((c) => c.needsTargets === true).map((c) => c.value)).toEqual([
      "specific",
      "split",
    ]);
    expect(choiceNeedsTargets("specific")).toBe(true);
    expect(choiceNeedsTargets("split")).toBe(true);
    expect(choiceNeedsTargets("oldest_first")).toBe(false);
    expect(choiceNeedsTargets("carry_credit")).toBe(false);
    // The refusal sentence must be GONE from the catalogue, not merely
    // unreferenced — an orphan string is one a future screen re-renders.
    expect(Object.keys(en)).not.toContain("payments.applyTo.pickerUnavailable");
  });

  it("CS-4: the remainder is exact, and a bad box makes it UNKNOWN rather than smaller", () => {
    // ❄️ The repo's own worked figure: 247.87 issued, 200.00 paid, 47.87 open.
    // A clerk holding 100.00 who aims 47.87 at that bill has 52.13 left.
    expect(remainingToAllocate("100.00", { "BL-2608-018410": "47.87" })).toBe("52.130000");
    // `specific` states no amount — the bill takes what it owes — so nothing is
    // subtracted here and the whole tender is still to land.
    expect(remainingToAllocate("100.00", { "BL-2608-018410": "" })).toBe("100.000000");
    // Over-aimed goes NEGATIVE and is shown as such. A floor at zero would hide
    // exactly the mistake this control exists to prevent.
    expect(remainingToAllocate("40.00", { A: "47.87" })).toBe("-7.870000");
    // Not a decimal ⇒ null ⇒ the screen states it cannot say. A skipped box
    // would be a smaller number wearing the right label.
    expect(remainingToAllocate("100.00", { A: "4x.87" })).toBeNull();
    // The body: an empty amount is OMITTED, never sent blank — the server reads
    // a missing `amount` as "this bill, up to what it owes".
    expect(targetsBody({ A: "", B: "12.50" })).toEqual([
      { invoice_number: "A" },
      { invoice_number: "B", amount: "12.50" },
    ]);
  });

  it("US-PAY-001 §5: the result panel shows WHAT THE PAYMENT PAID, bill by bill", () => {
    const recorded: RecordedPayment = {
      id: "pay-0412",
      payment_no: "PMT-2608-000412",
      created: true,
      status: "cleared",
      amount: "292.870000",
      currency: "USD",
      applied: "292.870000",
      credit_carried: "0.000000",
      allocations: [
        {
          invoice_id: "inv-18311",
          invoice_number: "BL-2607-018311",
          amount: "45.000000",
          by_class: {},
        },
        {
          invoice_id: "inv-18410",
          invoice_number: "BL-2608-018410",
          amount: "247.870000",
          by_class: {},
        },
      ],
      journal_entry_id: "je-1",
      posting_key: "payment|pay-0412|cleared",
      posted_to_ledger: true,
      // ⚠ **THIS FIXTURE INVENTED A CODE THE SERVER STOPPED SENDING ON
      // 2026-08-18 (`DEF-PAY-6330`).** It was `no_receipt_queued`, whose
      // sentence said sending receipts "is not built" — false from the day
      // `receipts.queue_receipt_for_recorded_payment` started running on every
      // payment, which was the same commit that took the code out of
      // `RECORD_UNAVAILABLE`. The assertion below passed for five weeks over a
      // sentence no server could produce, because a test that feeds itself a
      // retired code can never notice the code is retired.
      //
      // `account_balance_cache_not_updated` is what `RECORD_UNAVAILABLE`
      // actually carries on every recorded payment today.
      // ⛔ `DEF-PAY-10733` / `DEF-PAY-10736` (2026-10-30) — the REAL rider list
      // a counter payment carried in the tester's screenshot (TC-1A step 4),
      // in the server's order, duplicates included. It was one code here, and
      // a one-code fixture is how ten raw keys reached a clerk unseen.
      problems: [
        "account_balance_cache_not_updated",
        "invoice_composition_unavailable",
        "receipt_queued",
        "channel_has_no_rule_toggle",
        "template_pin_resolved_at_queue_write",
        "receipt_email_queued",
        "template_pin_resolved_at_queue_write",
        "print_floor_channel_added",
        "receipt_sms_queued",
        "recipient_absent_on_record",
        "recipient_absent_on_record",
        "template_pin_resolved_at_queue_write",
        "print_floor_channel_added",
      ].map((code) => ({ code, br_ref: null, detail: "" })),
    };
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <RecordPaymentPanel recorded={recorded} onDismiss={() => undefined} />
      </MemoryRouter>,
    );
    // L3-01 + `DEF-PAY-10783` (P11 = A) — the payment number IS the receipt
    // number, said in the first sentence: "Recorded. Receipt # PMT-…".
    expect(html).toContain("Recorded. Receipt # PMT-2608-000412");
    expect(html).toContain("BL-2607-018311");
    expect(html).toContain("$45.00");
    expect(html).toContain("$247.87");
    // ⛔ `DEF-PAY-10783` — the ledger sentence is gone (rule 33: rationale).
    expect(html).not.toContain("The books were updated");
    // L2-05 — the balance-cache note is bookkeeping, never a clerk's fact.
    expect(html).not.toContain(t("payments.problem.account_balance_cache_not_updated"));
    // L3-01 — only the allow-list, once: the one clerk fact here.
    const items = html.match(/<li data-outcome="[a-z_]+">[^<]*<\/li>/g) ?? [];
    expect(items).toEqual([
      `<li data-outcome="recipient_absent_on_record">${t("payments.problem.recipient_absent_on_record")}</li>`,
    ]);
    // No raw key and no bare code, whatever the queue minted.
    expect(html).not.toContain("payments.problem.");
    expect(html.replace(/<[^>]+>/g, " ")).not.toMatch(/[a-z]_[a-z]/);
  });

  it("DEF-PAY-10783 (P11 = A): at most two sentences — Recorded. Receipt # …, plus ONE warning", () => {
    const recorded: RecordedPayment = {
      id: "pay-0414",
      payment_no: "PY-261031-0007",
      created: true,
      status: "processing",
      amount: "40.000000",
      currency: "USD",
      applied: "0.000000",
      credit_carried: "40.000000",
      allocations: [],
      journal_entry_id: null,
      posting_key: null,
      posted_to_ledger: false,
      problems: ["recipient_absent_on_record", "awaiting_finance_approval", "duplicate_submit_ignored"].map(
        (code) => ({ code, br_ref: null, detail: "" }),
      ),
    } as unknown as RecordedPayment;
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <RecordPaymentPanel recorded={recorded} onDismiss={() => undefined} />
      </MemoryRouter>,
    );
    // The heading, then ONE warning — the one that changes what the clerk does.
    const heading = /<h3>([^<]*)<\/h3>/.exec(html)?.[1];
    expect(heading).toBe("Recorded. Receipt # PY-261031-0007");
    const warnings = html.match(/<li data-outcome="[a-z_]+">[^<]*<\/li>/g) ?? [];
    expect(warnings).toHaveLength(1);
    expect(warnings[0]).toContain("awaiting_finance_approval");
    // Nothing else in the panel is a sentence: no ledger line, no met-no-bill.
    expect(html).not.toContain("Nothing was posted to the books");
    expect(html).not.toContain("This money met no bill");
    expect(html).not.toContain("<p");
  });

  it("BR-PAY-010 / BR-PAY-012: an overpayment shows the credit it carried, never a silent loss", () => {
    const recorded: RecordedPayment = {
      id: "pay-0413",
      payment_no: "PMT-2608-000413",
      created: true,
      status: "cleared",
      amount: "350.000000",
      currency: "USD",
      applied: "292.870000",
      credit_carried: "57.130000", // PE-4, verbatim
      allocations: [],
      journal_entry_id: "je-2",
      posting_key: "payment|pay-0413|cleared",
      posted_to_ledger: true,
      problems: [],
    };
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <RecordPaymentPanel recorded={recorded} onDismiss={() => undefined} />
      </MemoryRouter>,
    );
    expect(html).toContain("$57.13");
    expect(html).toContain(t("payments.result.creditCarried"));
  });

  it("BR-PAY-028: an idempotent replay is reported as such, never as a second payment", () => {
    const replay: RecordedPayment = {
      id: "pay-0412",
      payment_no: "PMT-2608-000412",
      created: false,
      status: "cleared",
      amount: "292.870000",
      currency: "USD",
      applied: "292.870000",
      credit_carried: "0.000000",
      allocations: [],
      journal_entry_id: null,
      posting_key: null,
      posted_to_ledger: false,
      problems: [
        {
          code: "duplicate_submit_ignored",
          br_ref: "BR-PAY-028",
          detail: "already recorded under this key",
        },
      ],
    };
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <RecordPaymentPanel recorded={replay} onDismiss={() => undefined} />
      </MemoryRouter>,
    );
    expect(html).toContain(t("payments.result.replay"));
  });

  it("BR-SHL-025: a role with View may read the ledger and may not open the Record form", () => {
    const html = renderPayments("/payments/record", {
      list: page([payment()]),
      access: "View",
    });
    expect(html).toContain(t("payments.rbac.readOnly"));
  });

  // ── DEF-088's second finding ────────────────────────────────────────────
  // HONEST ABOUT WHAT THIS TEST IS. It is a REGRESSION LOCK, not a red-proved
  // defect guard: the `Number.parseFloat(value) > 0` it replaced classified
  // every one of these inputs identically, because no value matching
  // AMOUNT_PATTERN is positive yet parses to zero. The violation it removes is
  // a float on a money string in a file whose docstring swore there was none
  // (CLAUDE.md rule 2 + hard-won law 1), and the cost of the next person
  // reaching for parseFloat again is a real defect, not this one.
  it("CLAUDE.md rule 2: the amount's positivity is decided on the DIGITS — no float ever parses a money string", () => {
    const schema = recordPaymentSchema(t);
    const body = (amount: string) => ({
      account_id: "acc-1042",
      amount,
      posted_at: "2026-08-08",
    });
    // Every-digit-zero is refused whatever the served precision looks like.
    for (const zero of ["0", "0.00", "0.000000"]) {
      expect(schema.safeParse(body(zero)).success).toBe(false);
    }
    // …and the smallest storable amount is accepted, not rounded away.
    expect(schema.safeParse(body("0.000001")).success).toBe(true);
    expect(schema.safeParse(body("292.87")).success).toBe(true);
    // A negative or non-numeric amount never reaches the positivity check.
    expect(schema.safeParse(body("-1.00")).success).toBe(false);
    expect(schema.safeParse(body("N/A")).success).toBe(false);
  });
});

// ── DEF-088 / BR-TEN-080 ──────────────────────────────────────────────────
// The SECOND real screen asserted on its rendered string. S33 is where a clerk
// reads what a customer paid, so a 4-decimal wire figure showing through here
// is the same defect in a different room.
describe("DEF-088 / BR-TEN-080 — S33 renders every money figure at exactly 2 decimals", () => {
  it("DEF-088: a 4-decimal payment amount from the API renders $8.30, and no money string on S33 carries a third decimal", () => {
    const html = renderPayments("/payments/record", {
      list: page([payment({ amount: "8.2985", applied_to: [] })]),
    });
    expect(html).toContain("$8.30");
    expect(html).not.toContain("8.2985");

    const rendered = html.replace(/<[^>]*>/g, " ");
    const fractions = [...rendered.matchAll(/\$[\d,]+\.(\d+)/g)].map((m) => m[1]);
    expect(fractions.length).toBeGreaterThan(0);
    for (const fraction of fractions) {
      expect(fraction).toHaveLength(2);
    }
  });
});

// ── US-PAY-002 · BR-PAY-012 — the purpose the form could not send ─────────
// Until 2026-08-15 both record forms sent `purpose: bill` and nothing else,
// because `services.record_payment` refused the other three BY NAME for
// linkages that did not exist. `apps/payments/purposes.py` built all three —
// a deposit is HELD and meets no bill, a plan-down reduces the arrears its plan
// spreads, a prepay carries as credit — and the forms kept sending one value,
// so a clerk taking a $150.00 move-in deposit had no way to say so.
describe("US-PAY-002 — the four purposes are offered, and each means something different", () => {
  it("BR-PAY-012: the record form renders a purpose picker carrying all four values", () => {
    // The modal opens on a click, which `renderToStaticMarkup` cannot make, so
    // it is rendered directly with the props the page passes it.
    const html = renderToStaticMarkup(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TEST_TENANT}/payments/record`]}>
            <RecordPaymentForm
              client={undefined as never}
              methods={METHODS}
              today="2026-08-15"
              dateFormat="MM/DD/YYYY"
              currency="USD"
              onCancel={() => undefined}
              onRecorded={() => undefined}
            />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(html).toContain('id="purpose"');
    expect(html).toContain(escaped(t("payments.form.purpose")));
    for (const code of PAYMENT_PURPOSES) {
      expect(html).toContain(`value="${code}"`);
      expect(html).toContain(escaped(t(`payments.purpose.${code}`)));
    }
    // `bill` is the default, matching the server's own (BR-PAY-012).
    expect(html).toContain('<option value="bill" selected="">');
  });

  it("the help line states what each purpose does to the money, not just its name", () => {
    const help = t("payments.form.purposeHelp");
    // TC-1: a deposit is held and meets NO bill and becomes NO credit.
    expect(help).toContain("held for the customer and pays no bill");
    // TC-3: a plan down payment reduces the arrears its plan spreads.
    expect(help).toContain("reduces the arrears");
    // TC-4: a prepay carries as credit until the next bill.
    expect(help).toContain("credit until the next bill");
  });

  it("the old note claiming the other three purposes are REFUSED is gone from the catalogue", () => {
    // Hard-won law 1: that sentence was a comment claiming a fact about
    // another file, and it stopped being true when purposes.py landed.
    expect(i18n.exists("payments.form.purposeNote")).toBe(false);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-004@0f1a7c3 (story+rules snapshot — EP-PAY-01 US-PAY-004 lead; co-packet US-PAY-001, same epic; 08-payments/02-business-rules.md; 11b §1 + §2.9)
// generated: 2026-08-11 by story-coder (W4 payments FRONTEND lane — S33 + the S22/S35 Record modal)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — this whole file failed to resolve `./PaymentsPage` and `./paymentsShared` before the screen existed; the verbatim failure is in the lane report · [2026-08-15 DEF-088 display-precision lane] RED PROVED FIRST — the S30 tax line rendered `<span class="cell-money-amount">$8.2985</span>` and all 6 new assertions failed against the pre-fix formatter (verbatim in the lane report). MEASURED, THIS LANE'S OWN FILES ONLY: MoneyCell.test.tsx 8 tests (was 6) · BillDetailPage.test.tsx 22 tests / 3 skipped (was 20 / 3) · PaymentsPage.test.tsx 17 tests (was 15) — 44 passed / 3 todo across the three, all green. The FULL suite total is deliberately not quoted: a concurrent 07-frontend settings lane was adding files throughout, so no whole-suite number here would be reproducible. tsc --noEmit✔ · eslint --max-warnings 0✔ · vite build✔ · node --test server.test.mjs 10/10✔ · tsc -p tsconfig.e2e.json✔ · run_gates: 20 PASS · 0 FAIL at this lane's 17:55 baseline; the failures present at hand-off are named in the lane report and none is this lane's — no file it touched appears in any of them
// exceptions: the submit path itself (a real click through FormModal into `recordPayment`) is NOT exercised here — these are `renderToStaticMarkup` cases with no DOM events, the same posture every other screen test in this repo takes. What IS covered end to end is the SERVER half, in 06-backend/tests/test_us_pay_004_payments_api.py, which drives the same body shape through the real view
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
