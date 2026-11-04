// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-025 (S30 All-bills list) · US-CUS-010 (the S21 Bills tab —
//           the same list scoped by `f.account_id`)
//           Screens: S30 · S21
// Rules:    BR-BIL-004 (immutable issued history — no edit affordance) ·
//           BR-BIL-018 (the six bill types the list filters on) · BR-BIL-063 (a
//           draft has NO bill number) · BR-BIL-024 (the due date is derived at
//           issue) · BR-BIL-026 (the template version pinned at issue) ·
//           BR-SHL-010 (an undeclared capability is not rendered) ·
//           BR-SHL-011 (URL grammar) · BR-SHL-020 (plain-language failure) ·
//           BR-SHL-023 (one money path) · BR-SHL-025 (disabled WITH the reason)
// ───────────────────────────────────────────────────────
// §4 test data is Brazos Bend Utilities (US-BIL-025 §4) — BL-2608-018410, the
// draft run, the WE-9 corrected chain and the past-due fixture — rendered
// through the seeded query cache, never a network.
//
// The assertions that matter most here are the NEGATIVE ones. This screen must
// not print a blank where a draft has no bill number, a date where a bill has
// not been issued, or "current" where the server did not say so. Each of those
// is one line in the defect log's fabricated-value family.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import { BILL_TYPES, INVOICE_FILTERS, INVOICE_SORTS, INVOICE_STATUSES } from "@/api/endpoints";
import type { InvoiceRow, InvoicesPage, MyPermissions } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";

import {
  AccountBillsTab,
  BillsListPage,
  billsCells,
  billsFailureReason,
  billsFilters,
  billsParamsFrom,
  billsQueryKey,
  billsTableConfig,
} from "./BillsListPage";
import {
  BILLING_TABS,
  BILL_STATUS_SEGMENTS,
  billDetailPath,
  billStatusLabel,
  billStatusTone,
  billTypeLabel,
  billingTabFrom,
  billsForAccountPath,
  groupLinesByService,
  isLockedBill,
  listRouteAbsent,
} from "./billingShared";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…`.
const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const CELLS = billsCells(t, (p) => p, "UTC", "MM/DD/YYYY");
const CONFIG = billsTableConfig(t, CELLS, "all");
const ACCOUNT_CONFIG = billsTableConfig(t, CELLS, "account");

/** WE-1's shape: BL-2608-018410, issued, 15 lines, total 247.87. */
function bill(over: Partial<InvoiceRow> = {}): InvoiceRow {
  return {
    id: "inv-18410",
    invoice_no: "BL-2608-018410",
    bill_type: "cycle",
    status: "issued",
    past_due: false,
    account_id: "acc-1042",
    account_no: "A-10432",
    customer_name: "Miller, Sarah",
    cycle_label: "08-A",
    bill_run_id: "run-07a",
    service_date: "2026-07-31",
    period_start: "2026-07-01",
    period_end: "2026-07-31",
    issued_at: "2026-08-08",
    due_date: "2026-08-25",
    subtotal: "226.900000",
    tax_total: "20.970000",
    total: "247.870000",
    currency: "USD",
    template_version: 3,
    ...over,
  };
}

/** The draft the open run produced: no number, no issue date, no due date. */
function draft(over: Partial<InvoiceRow> = {}): InvoiceRow {
  return bill({
    id: "inv-18320",
    // BR-BIL-063 (PO 2026-08-11): a draft CARRIES its number. This fixture
    // used to set it null, which was the previous reading of the rule.
    invoice_no: "BL-2608-018320",
    status: "draft",
    past_due: null,
    issued_at: null,
    due_date: null,
    template_version: null,
    total: "145.700000",
    ...over,
  });
}

function page(rows: InvoiceRow[], rollupOver: Partial<InvoicesPage["rollup"]> = {}): InvoicesPage {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    rollup: {
      // Nothing serves this list yet, so every member is honestly not-counted.
      bills: null,
      billed_this_cycle: null,
      billed_currency: null,
      unresolved_from_last_run: null,
      ...rollupOver,
    },
  };
}

function permissions(access: string): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: "reads_billing_runs", label: "Reads & Billing runs", access }],
  };
}

function renderList(path: string, seed: { list?: InvoicesPage; access?: string } = {}): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = parseTableParams(new URLSearchParams(path.split("?")[1] ?? ""), CONFIG);
  if (seed.list !== undefined) {
    queryClient.setQueryData(
      billsQueryKey(`${serializeTableParams(state, CONFIG).toString()}|`),
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
            <Route path="/:tenant/billing" element={<BillsListPage />} />
            <Route path="/:tenant/billing/:tab" element={<BillsListPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function renderAccountTab(path: string, accountId: string, list?: InvoicesPage): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = parseTableParams(new URLSearchParams(path.split("?")[1] ?? ""), ACCOUNT_CONFIG);
  if (list !== undefined) {
    queryClient.setQueryData(
      billsQueryKey(`${serializeTableParams(state, ACCOUNT_CONFIG).toString()}|${accountId}`),
      list,
    );
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <Routes>
            <Route
              path="/:tenant/accounts/:accountId"
              element={<AccountBillsTab accountId={accountId} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The rows region only — the awaiting panels deliberately name the gaps in
 *  prose, and a whole-document `not.toContain` would read that prose as the
 *  defect it exists to prevent. */
function rowsRegion(html: string): string {
  const start = html.indexOf("<tbody");
  const end = html.indexOf("</tbody>");
  return start === -1 || end === -1 ? "" : html.slice(start, end);
}

describe("US-BIL-025 — the S30 All-bills list", () => {
  it("US-BIL-025 TC-1: the default load renders the capability row's columns, issue-date desc", () => {
    const html = renderList("/billing", { list: page([bill(), draft()]) });
    expect(html).toContain("BL-2608-018410");
    expect(html).toContain("A-10432");
    expect(html).toContain("Miller, Sarah");
    expect(html).toContain("08-A");
    // IS-2 / the capability row: newest bill first, and the SERVER orders it.
    expect(CONFIG.defaultSort).toEqual({ sort: "issue_date", dir: "desc" });
    expect(CONFIG.columns.find((column) => column.identity === true)?.key).toBe("invoice_no");
    // The default column set is the capability row's eight, in its order —
    // plus the ACTIONS cell, which is US-BIL-025 §1's own IS-6 (*"Row states
    // drive actions … issued rows offer Reprint/Correct/Void per state"*) and
    // was unbuilt until CR-053 task 11. It is last because it is not data.
    expect(CONFIG.columns.filter((c) => c.defaultVisible !== false).map((c) => c.key)).toEqual([
      "invoice_no",
      "cycle",
      "account",
      "customer",
      "issue_date",
      "due_date",
      "total",
      "status",
      "actions",
    ]);
    // Sortable set = INVOICE_SORTS, and every sortable key is one the server
    // accepts — a control offering an ordering the API cannot do is a lie.
    expect(CONFIG.columns.filter((c) => c.sortable === true).map((c) => c.key).sort()).toEqual(
      [...INVOICE_SORTS].sort(),
    );
  });

  it("US-BIL-025 TC-1 / BR-SHL-023: the total renders through MoneyCell with its own currency", () => {
    const html = renderList("/billing", { list: page([bill()]) });
    expect(html).toContain("cell-money");
    expect(html).toContain("$247.87");
    // The six-decimal string is FORMATTED, never parsed or re-rounded here.
    expect(html).not.toContain("247.870000");
    const cad = renderList("/billing", {
      list: page([bill({ total: "64.000000", currency: "CAD" })]),
    });
    expect(cad).toContain("CA$64.00");
  });

  it("US-BIL-025 / BR-BIL-063: a DRAFT shows its number, and a SERVED NULL shows a stated absence", () => {
    // THIS TEST REVERSED ON 2026-08-11 and the reversal is the point. It used
    // to assert that a draft shows "No number yet", on the reading that the
    // series is consumed at issue. The PO ruled the other way — a number is
    // allocated when the draft is created and an unused one is lost — so the
    // prototype's numbered draft rows were right all along and DEF-033 with
    // them.
    const html = renderList("/billing", { list: page([draft()]) });
    expect(html).toContain("BL-2608-018320");
    expect(html).not.toContain("Number not shown");

    // The absence branch is NOT dead code: the field is SERVED, and a served
    // field can be null (a row written under the previous reading, a partial
    // response). A blank identity cell would read as a value that failed to
    // load, so the absence is still STATED with its reason.
    const noNumber = renderList("/billing", {
      list: page([draft({ invoice_no: null })]),
    });
    expect(noNumber).toContain("Number not shown");
    expect(noNumber).toContain("drafts included");

    // The row OPENS either way — the link hangs off the invoice id, never off
    // the number, which is what makes both cases reachable.
    expect(html).toContain(`href="/${TEST_TENANT}${billDetailPath("inv-18320")}"`);
    expect(noNumber).toContain(`href="/${TEST_TENANT}${billDetailPath("inv-18320")}"`);
    // BR-BIL-024 + BR-BIL-026: an unissued bill has no issue date, no due date
    // and no pinned template. None of the three renders as a date or a "v1".
    expect(rowsRegion(html)).toContain("Not issued yet");
    expect(rowsRegion(html)).not.toContain("08/25/2026");
  });

  it("US-BIL-025 §5: past-due is the SERVER's answer — a null never becomes 'not past due'", () => {
    // The derived state, when the server computed it.
    const overdue = renderList("/billing", {
      list: page([bill({ past_due: true, status: "issued" })]),
    });
    expect(overdue).toContain("Past-due");
    expect(overdue).toContain('class="pill past"');
    // …and when it did not: an issued row says the derivation is unknown rather
    // than showing a clean "Issued" that reads as "not overdue".
    //
    // ⚠ **THIS ASSERTION CHANGED ON 2026-08-27 AND THE RULE BEHIND IT DID NOT
    // (DEF-967, CR-043 finding 6).** It used to require *"Past-due unknown"* in
    // the ROW, and the row is where the note was wrong: `past_due` is null on
    // every issued bill this server serves, so the note printed on all 47 rows
    // of the live deployment and became the status column's content.
    //
    // **An absence true of EVERY row is a fact about the LIST.** So the note is
    // asserted ONCE, above the table, and asserted ABSENT from the rows — which
    // is the half that would silently come back if somebody re-added the cell.
    const unknown = renderList("/billing", {
      list: page([bill({ past_due: null, status: "issued" })]),
    });
    expect(unknown).toContain("Issued");
    expect(unknown).toContain('data-bil="past-due-unknown"');
    expect(unknown).toContain("no bill below is marked past due");
    expect(rowsRegion(unknown)).not.toContain("Past-due unknown");
    // …and it is not printed when the server DID answer: the pill carries it.
    expect(overdue).not.toContain('data-bil="past-due-unknown"');
    // Nothing anywhere turns the due date into an ageing state client-side.
    expect(rowsRegion(unknown)).not.toContain("Past-due<");
    // The tone keys off the derived flag first, then the stored status.
    expect(billStatusTone("issued", true)).toBe("danger");
    expect(billStatusTone("issued", null)).toBe("neutral");
    expect(billStatusTone("paid", false)).toBe("success");
    expect(billStatusTone("corrected", false)).toBe("warning");
    expect(billStatusTone("void", false)).toBe("danger");
    expect(billStatusLabel({ status: "issued", past_due: true }, t)).toBe("Past-due");
    expect(billStatusLabel({ status: "void", past_due: null }, t)).toBe("Void");
  });

  it("US-BIL-025 TC-2: search and the status segments are URL state the server resolves", () => {
    const html = renderList("/billing?q=1042&sort=issue_date&dir=desc&f.status=past_due", {
      list: page([bill({ past_due: true })]),
    });
    expect(html).toContain("BL-2608-018410");
    // BR-SHL-011: the filter chip round-trips through the URL — shareable.
    const state = parseTableParams(
      new URLSearchParams("q=1042&sort=issue_date&dir=desc&f.status=past_due"),
      CONFIG,
    );
    expect(state.q).toBe("1042");
    expect(state.filters.status).toBe("past_due");
    expect(billsParamsFrom(state).filters).toEqual({ status: "past_due" });
    // IS-3: the four searched fields are the capability row's, declared here
    // and matched SERVER-side. ⚠ `address` was ADDED on 2026-09-13 (cf45a3d2)
    // and this assertion was not moved with it, so it pinned the defect for a
    // day — DEF-BIL-5263/5294/5304 are the same red, filed four times over by
    // four lanes that each correctly reported a failure they had not caused.
    // It is METERING's own match and is wider than the word: the server ANDs
    // in `_account_ids_at_address`, so a bill whose address matches is found
    // even though no column on the bill holds one.
    expect(CONFIG.searchFields).toEqual([
      "invoice_no",
      "account_no",
      "customer_name",
      "address",
    ]);
    // The prototype's segment strip, minus `void` — which the prototype has no
    // segment for. Reported in the file's exceptions, not invented here.
    expect([...BILL_STATUS_SEGMENTS]).toEqual(["draft", "issued", "paid", "past_due", "corrected"]);
    expect([...INVOICE_STATUSES]).toContain("void");
    expect(BILL_STATUS_SEGMENTS as readonly string[]).not.toContain("void");
  });

  it("US-BIL-025 §5 / BR-BIL-018: the bill_type filter offers all six values", () => {
    const filters = billsFilters(t);
    const billType = filters.find((filter) => filter.name === "bill_type");
    expect(billType?.options.map((option) => option.value)).toEqual([...BILL_TYPES]);
    expect(BILL_TYPES.length).toBe(6);
    expect(billTypeLabel("backbill", t)).toBe("Back-bill");
    // An unknown type still renders its code rather than an empty cell.
    expect(billTypeLabel("mystery", t)).toBe("mystery");
    // Every declared filter is one the endpoint accepts (BE-05 ignores others).
    for (const filter of filters) {
      expect(INVOICE_FILTERS as readonly string[]).toContain(filter.name);
    }
  });

  it("US-BIL-025 TC-3: bill_type and template version are available columns, and the identity column cannot be hidden", () => {
    const available = CONFIG.columns.filter((c) => c.defaultVisible === false).map((c) => c.key);
    // On S30 the subtotal/tax split is available but not shown (its capability
    // row lists Total only, and the split is one click away on the detail);
    // bill_type and template version are the two the row names as available.
    expect(available).toEqual(["subtotal", "tax_total", "bill_type", "template_version"]);
    expect(CONFIG.columns.find((c) => c.key === "invoice_no")?.identity).toBe(true);
    // The capability row's other two available columns (run, delivery status)
    // are deliberately ABSENT — both would be permanently empty.
    expect(CONFIG.columns.map((c) => c.key)).not.toContain("bill_run");
    expect(CONFIG.columns.map((c) => c.key)).not.toContain("delivery_status");
  });

  it("US-BIL-025 TC-4 / BR-BIL-004: a corrected row badges, and carries no edit affordance", () => {
    const html = renderList("/billing", {
      list: page([bill({ status: "corrected", past_due: false })]),
      access: "Full",
    });
    expect(html).toContain("Corrected");
    expect(html).toContain('class="pill bg-warning-100 text-warning-700"'); // CR-018: the warn tone's utilities
    // The chain itself lives on the DETAIL — the row links there and claims
    // nothing about the chain it cannot see.
    expect(html).toContain(`href="/${TEST_TENANT}${billDetailPath("inv-18410")}"`);
  });

  it("US-BIL-025 TC-5 (negative): no row offers an edit — issued history is immutable", () => {
    const html = renderList("/billing", { list: page([bill()]), access: "Full" });
    const rows = rowsRegion(html);
    expect(rows).not.toContain("<input");
    expect(rows).not.toContain("contenteditable");
    // ⚠ **THIS USED TO READ `expect(rows).not.toContain("<button")` AND THAT
    // WAS AN ASSERTION ABOUT THE IMPLEMENTATION, NOT ABOUT THE CASE.** TC-5 is
    // *"Any inline-edit attempt on an issued row … No edit affordance;
    // immutable history (BR-BIL-004)"*. A `<button>` in a row is not an edit —
    // CR-053 task 11 puts B14 rule 15's two READ actions there (open the bill,
    // print it), and neither writes anything at all. The blanket ban would have
    // failed the story's OWN `IS-6` row actions, which §1 has declared since
    // 2026-08-11.
    //
    // So the case is asserted as what it actually says: nothing in a row may
    // WRITE. Every control in the cell is named and checked, which is stricter
    // than counting tags — a third action arriving would fail this list.
    const rowButtonLabels = [...rows.matchAll(/aria-label="([^"]+)"/g)].map((m) => m[1]);
    expect(rowButtonLabels.sort()).toEqual(["Open this bill", "Print bill"]);
    for (const forbidden of ["Edit", "Delete", "Void", "Correct", "Adjust", "Record payment"]) {
      expect(rows).not.toContain(`aria-label="${forbidden}`);
    }
    // BR-BIL-004 in one predicate: everything past draft is locked.
    expect(isLockedBill("draft")).toBe(false);
    for (const status of ["issued", "paid", "void", "corrected"]) {
      expect(isLockedBill(status)).toBe(true);
    }
  });

  it("US-BIL-025 TC-6 / BR-SHL-025: the export glyph renders DISABLED with its reason — and the gap is named in the REGISTER", () => {
    const html = renderList("/billing", { list: page([bill()]), access: "Full" });
    // ══════════════════════════════════════════════════════════════════════
    // ⚠ **THIS ASSERTION WAS INVERTED BY CR-053 TASK 10, AND THE FACT UNDER IT
    // HAS NOT CHANGED.** `POST /exports` still registers no `bills` resource —
    // re-measured 2026-08-30: there is no `apps/billing/exports.py` at all —
    // so this list still cannot produce a file, and nothing here produces one.
    //
    // What changed is WHICH honest answer B14 rule 12 asks for. The toolbar's
    // shape is *one search, one filter set, one download glyph*, and the glyph
    // renders DISABLED WITH ITS REASON (BR-SHL-025), exactly as the four
    // finance screens already do. An absent control tells a clerk nothing; a
    // greyed one with a sentence tells them the product knows.
    //
    // BOTH HALVES ARE ASSERTED, because only the pair is the rule: the control
    // is present, and it is disabled and says why.
    expect(html).toContain('data-download="button"');
    expect(html).toContain("disabled=");
    expect(html).toContain("Bills cannot be downloaded yet. No export is built for this list.");
    // ⚠ **THE SECOND HALF OF THIS TEST WAS INVERTED ON 2026-08-27 BY A PO
    // RULING (CR-043 finding 10)**, verbatim: *"you ahve to remove - Filters
    // that arrive later … + Export and column choices"*. It used to require the
    // two `ArrivesWith` panels ON THE SCREEN.
    //
    // **The ruling narrows WHERE an unbuilt feature is stated, not WHETHER.** A
    // feature we have not built is stated in the register — `DEF-1062` (no
    // cycle / run / date-range filter) and `DEF-1063` (no export, no remembered
    // columns) — because a utility clerk cannot act on our backlog and it
    // occupied their screen on every visit. A SECTION WITH NO DATA IN IT still
    // says so on screen; that is the PO's other sentence and it is not this.
    //
    // Asserted as an ABSENCE so the panels cannot drift back in unnoticed, and
    // `G38`'s `UNTRACKED_BASELINE` fell 71 → 69 in the same commit as a MOVE.
    expect(html).not.toContain("Export and column choices");
    expect(html).not.toContain("Filters that arrive later");
    expect(html).not.toContain("A download button that produced no file would be worse than none.");
  });

  it("US-BIL-025 §1 / BR-SHL-020: a 404 on the collection route is reported as 'no bills list', derived", () => {
    // A served list endpoint answers 200-with-zero-results; it never 404s. So
    // the distinction is READ OFF the response, not off a build flag — which is
    // what makes it stop being reachable the day the route is registered.
    const notFound = new ApiError(404, { code: "NOT_FOUND", message_key: "api.error.unexpected" });
    const serverError = new ApiError(500, {
      code: "SERVER",
      message_key: "api.error.unexpected",
    });
    expect(listRouteAbsent(notFound)).toBe(true);
    expect(listRouteAbsent(serverError)).toBe(false);
    expect(listRouteAbsent(new Error("offline"))).toBe(false);
    expect(billsFailureReason(notFound, t)).toContain(
      "does not serve a bills list yet",
    );
    expect(billsFailureReason(notFound, t)).toContain("Nothing is missing from your data.");
    // Any other failure is the SERVER's own message through the catalog — this
    // screen never relabels a real server error as a build gap.
    expect(billsFailureReason(serverError, t)).not.toContain("does not serve a bills list");
  });

  it("US-BIL-025 §1: the roll-up renders every figure as not-counted, never as zero", () => {
    const html = renderList("/billing", { list: page([bill()]) });
    expect(html).toContain("Bills lifetime");
    expect(html).toContain("Out this cycle");
    expect(html).toContain("Unresolved from the last run");
    // "3 unresolved" and "we have not counted" are different claims.
    expect(html).toContain("Not counted yet");
    // ⚠ **AMENDED 2026-09-14 (CR-101-BRC03 / DEF-BIL-5231).** This asserted the
    // tooltip's old words, *"…so no count is shown — and zero would be a
    // claim"*. The whole sentence read *"Nothing serves that list yet"*, which
    // was FALSE: `GET /invoices` has been served for weeks and answers
    // `count: 92` on the seeded tenant — the CLIENT was not asking, because the
    // roll-up query carried `enabled: active === BILLING_TAB_ALL`. A sentence
    // that blames the server for the client's silence had to go. The assertion
    // this case actually exists for — a null renders as NOT COUNTED and never
    // as `0` — is the line above and is unchanged.
    expect(html).toContain("The bills list has not answered.");
    expect(html).not.toContain("Nothing serves that list yet");
    // …and a served figure renders as the figure, with its currency.
    const counted = renderList("/billing", {
      list: page([bill()], {
        bills: 7240,
        billed_this_cycle: "342180.000000",
        billed_currency: "USD",
        unresolved_from_last_run: 3,
      }),
    });
    // DEF-BIL-9007 — grouped, as the drawing writes it ("7,240 bills lifetime").
    expect(counted).toContain("7,240");
    expect(counted).not.toContain(">7240<");
    expect(counted).toContain("$342,180.00");
    expect(counted).toContain(">3<");
  });

  it("US-BIL-025 §1 / BR-SHL-025: the ONE primary STARTS the run; only the role disables it", () => {
    // ⚠ **THIS CASE ASSERTED THE DEFECT (DEF-2421).** It required the primary
    // to carry *"there is no endpoint to start a run yet"* — true when written,
    // false since `apps/billing/api.py` mounted `path("billing/runs",
    // bill_runs)` under `@api_view(["GET", "POST"])`. A green test held the one
    // screen-level way to start a billing run switched off, which is why the PO
    // reported bills were not being generated. Hard-won law 1 reaches tests too:
    // a case asserting a stale claim keeps the claim alive.
    const html = renderList("/billing", { list: page([bill()]), access: "Full" });
    expect(html).toContain("Start a billing run →");
    expect(html).not.toContain("there is no endpoint to start a run yet");
    // Enabled means: no `disabled` ATTRIBUTE on the ONE primary. Matching the
    // bare word `disabled` does NOT work and is worth the extra line — the
    // kit's own class list carries `disabled:opacity-45` and
    // `disabled:cursor-not-allowed` on every button, enabled or not, so that
    // assertion fails on a correct button and would pass on nothing.
    const primary = /<button[^>]*data-variant="primary"[^>]*>Start a billing run/.exec(html);
    expect(primary).not.toBeNull();
    expect(primary?.[0]).not.toContain('disabled=""');
    // A View-only role sees the same control with the ROLE's reason first.
    const readOnly = renderList("/billing", { list: page([bill()]), access: "View" });
    expect(readOnly).toContain("Your role can view billing but not change it.");
    // …and a role with no cell at all never sees the surface (A18 §6).
    const denied = renderList("/billing", { access: "—" });
    expect(denied).toContain("Your role does not include billing.");
    expect(denied).not.toContain("Start a billing run");
  });

  it("US-BIL-025 §1: the strip is the prototype's six PLUS Print bills", () => {
    // ⚠ **AMENDED 2026-09-14 (CR-101-BRC03). SIX UNTIL THEN, AND THE SEVENTH IS
    // A DATED PO RULING RATHER THAN A LOOSENED TEST** — decision log, the
    // fifteen of 2026-09-12, ruling #10, verbatim: *"We will need Print bills as
    // tab at Billing level"*. The billing blueprint's entry 01 draws the strip
    // seven wide with `Print bills` last. This is the `SignupWizard.test.tsx`
    // shape — a hand-typed list that a screen cannot grow on its own, so the
    // count is asserted rather than trusted.
    expect(BILLING_TABS.map((tab) => t(tab.labelKey))).toEqual([
      "All bills",
      "Run bills",
      "One-time bill",
      "Budget Bills",
      "Fix a bill",
      "Past billing runs",
      "Print bills",
    ]);
    // BR-SHL-011's spirit: an unknown tab falls back rather than erroring.
    expect(billingTabFrom(undefined)).toBe("all");
    expect(billingTabFrom("nonsense")).toBe("all");
    expect(billingTabFrom("fix")).toBe("fix");
    // ⚠ AMENDED 2026-08-16. This block used to assert that the Fix-a-bill tab
    // rendered the "Fixing a bill never edits it — it arrives with …" panel.
    // That panel is GONE: the correction engine got its route and its screen,
    // so the tab renders the workflow. The sentence about not editing survives
    // and is now on the working screen rather than in place of it, which is the
    // assertion below.
    const fix = renderList("/billing/fix");
    expect(fix).toContain("Fix a bill");
    // `settings-arrives` is the class the "arrives with …" panel renders as.
    // Its ABSENCE is what proves the tab body is the workflow and not a note.
    expect(fix).not.toContain("settings-arrives");
    // ⚠ **THE ONE-TIME BILL IS ITS OWN PAGE FROM 2026-09-30** (the redrawn
    // four-step bill, `11-one-time-bill-redesign.md`). In the product the
    // router mounts `OneTimeBillPage` at `/billing/one-time` and never this list
    // — `oneTimeBill/OneTimeBillDoor.test.tsx` asserts that BY ADDRESS. What is
    // asserted here is the other half of hard-won law 2's mirror: a bare mount
    // of the list at that tab must not fall through to the "arrives with …"
    // note, which would be a refusal over a screen that is live.
    const oneTime = renderList("/billing/one-time");
    expect(oneTime).toContain("One-time bill");
    expect(oneTime).not.toContain("settings-arrives");
    expect(oneTime).toContain('href="/brazosbend/billing/one-time"');
  });

  it.todo(
    "US-BIL-025 TC-3: the chosen column set persists per user — needs US-SHL-013's preference service",
  );
  it.todo(
    "US-BIL-025 TC-7 (isolation): a Lone Star Ridge session sees only its bills — server/RLS scope (G5)",
  );
});

describe("US-CUS-010 — the account's Bills tab is billing's list, scoped", () => {
  it("US-CUS-010 TC-1: the tab renders the account's bills with the prototype's column set", () => {
    const html = renderAccountTab("/accounts/acc-1042?tab=bills", "acc-1042", page([bill()]));
    expect(html).toContain("BL-2608-018410");
    // The prototype's Bills tab shows the subtotal/tax split; S30's own row
    // does not. One config, two column sets.
    expect(html).toContain("$226.90");
    expect(html).toContain("$20.97");
    // …and it never repeats the account whose page it is on.
    expect(ACCOUNT_CONFIG.columns.map((c) => c.key)).not.toContain("account");
    expect(ACCOUNT_CONFIG.columns.map((c) => c.key)).not.toContain("customer");
    expect(CONFIG.columns.map((c) => c.key)).toContain("account");
  });

  it("US-CUS-010 §1: the tab scopes the SAME endpoint by account, and exits to the full list", () => {
    // 11b §2.6: the S21 tabs reuse the owning module's list with an account
    // filter — not a customers-owned read model (BR-CUS-034).
    expect(billsForAccountPath("acc-1042")).toBe(
      "/billing?sort=issue_date&dir=desc&f.account_id=acc-1042",
    );
    expect(INVOICE_FILTERS as readonly string[]).toContain("account_id");
    const html = renderAccountTab("/accounts/acc-1042?tab=bills", "acc-1042", page([bill()]));
    expect(html).toContain("All bills");
    expect(html).toContain(`href="/${TEST_TENANT}/billing?sort=issue_date`);
  });

  it("US-CUS-010 TC-1: the tab states the absence as a fact and explains nothing", () => {
    const html = renderAccountTab("/accounts/acc-1042?tab=bills", "acc-1042", page([bill()]));
    // ⚠ **REWRITTEN 2026-09-13 — NOT DELETED — AND THEN REWRITTEN AGAIN THE
    // SAME HOUR.** This case used to require the panel titled *"Columns this
    // tab cannot show"* over *"The design also shows the usage behind each bill
    // on this tab… no number is drawn from nothing"*: 36 words the Product
    // Owner pasted back out of the running product as text they do not want on
    // screen. B14 rule 33 makes RATIONALE — why a column is absent — ZERO words
    // on screen. The block STAYS, because the absence itself is a fact a clerk
    // needs; both keys are rewritten to the three and five words the rule
    // allows. What the case is FOR is unchanged and is the last line: the
    // usage column is still not drawn, because a zero there would read as
    // *they used nothing*. The two negatives are what cannot rot into a
    // tautology — one for the old copy, one for the raw key an absent
    // catalogue entry would print (DEF-FE-4058's shape).
    expect(html).toContain("Usage not shown");
    expect(html).toContain("Usage is not summed yet.");
    expect(html).not.toContain("Columns this tab cannot show");
    expect(html).not.toContain("no number is drawn from nothing");
    // A retired key reaches a clerk as its own NAME, never as silence
    // (`DEF-FE-4058`), so the raw key is asserted absent beside the copy.
    expect(html).not.toContain("billing.bills.awaits.accountTab\"");
    expect(rowsRegion(html)).not.toContain("kWh");
  });

  it("US-CUS-010 TC-5 (negative): the tab writes nothing — no record-payment, no adjust", () => {
    const html = renderAccountTab("/accounts/acc-1042?tab=bills", "acc-1042", page([bill()]));
    expect(html).not.toContain("+ Record payment");
    expect(html).not.toContain("+ New adjustment");
    // Same correction as US-BIL-025 TC-5 above, one tab along: the account's
    // Bills tab is the SAME table, so it grew the same two READ row actions and
    // the same blanket `<button>` ban would have failed on them. What the case
    // says is that the tab WRITES nothing, and that is what is asserted.
    const rows = rowsRegion(html);
    expect([...rows.matchAll(/aria-label="([^"]+)"/g)].map((m) => m[1]).sort()).toEqual([
      "Open this bill",
      "Print bill",
    ]);
    expect(rows).not.toContain("<input");
    expect(rows).not.toContain("contenteditable");
  });

  it.todo(
    "US-CUS-010 TC-6 (isolation): the scoped read re-checks the tenant — server/RLS scope (G5)",
  );
});

describe("line grouping — the bill prints per service, taxes last", () => {
  it("US-BIL-007 §5: lines group by service in the served order, with taxes and fees trailing", () => {
    const lines = [
      { id: "1", service: "electric", kind: "usage" },
      { id: "2", service: null, kind: "tax" },
      { id: "3", service: "electric", kind: "base" },
      { id: "4", service: "water", kind: "usage" },
      { id: "5", service: "electric", kind: "tax" },
      { id: "6", service: null, kind: "fee" },
    ];
    const groups = groupLinesByService(lines);
    expect(groups.map((group) => group.service)).toEqual(["electric", "water", "__other__"]);
    // The order WITHIN a group is the engine's and is never re-sorted: a tiered
    // usage block reads in the order it was priced.
    expect(groups[0].lines.map((line) => line.id)).toEqual(["1", "3"]);
    // A tax line carrying a service still lands with the taxes, because that is
    // where the document prints it.
    expect(groups[2].lines.map((line) => line.id)).toEqual(["2", "5", "6"]);
  });

  it("DEF-BIL-9339: a bill-level discount has a Discounts group of its own, after the services and before taxes & fees", () => {
    const lines = [
      { id: "1", service: "water", kind: "usage" },
      { id: "2", service: null, kind: "discount" },
      { id: "3", service: null, kind: "tax" },
      { id: "4", service: null, kind: "discount" },
      { id: "5", service: "water", kind: "discount" },
    ];
    const groups = groupLinesByService(lines);
    expect(groups.map((group) => group.service)).toEqual(["water", "__discounts__", "__other__"]);
    // A discount scoped to one service stays with that service.
    expect(groups[0].lines.map((line) => line.id)).toEqual(["1", "5"]);
    expect(groups[1].lines.map((line) => line.id)).toEqual(["2", "4"]);
    expect(groups[2].lines.map((line) => line.id)).toEqual(["3"]);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-025@f4c9d21 (story+rules snapshot — EP-BIL-07 lead story; co-packet US-CUS-010 EP-CUS-03)
// generated: 2026-08-11 by story-coder (W3 billing FRONTEND lane — S30 All bills + the S21 Bills tab)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — GET /invoices is contracted at 11b §2.8 and unserved) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 738 passed / 174 todo across 53 files✔ (702 passed / 168 todo across 51 files was the pre-lane baseline — this lane adds 36 passing + 6 todo across 2 new files and dropped nothing) · vite build✔ · run_gates 15 PASS · 0 FAIL · 1 SKIP✔ (G13 unwired-props, G14 prototype-conformance and G15 i18n-parity included; 5 locales × 2628 keys, identical sets)
// exceptions: E4 the 404-means-no-list distinction is asserted on the PURE `listRouteAbsent`/`billsFailureReason` pair rather than on a rendered failure frame: this suite renders through `renderToStaticMarkup`, where effects never run and a query can only be seeded with SUCCESS data — so the rendered error path stays a browser-scope assertion and the decision itself is proven here · E4 TC-3's per-user column persistence is an honest it.todo — it needs US-SHL-013's preference service, which is not wired · E4 every TC-7 isolation row is server/RLS scope (G5) · E4 US-CUS-010 TC-6 likewise
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
