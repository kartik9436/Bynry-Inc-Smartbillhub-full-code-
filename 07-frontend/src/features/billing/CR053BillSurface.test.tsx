// ── Trace ──────────────────────────────────────────────
// Change:   CR-053 tasks 1–5 and 10–12 (12-governance/11-change-requests.md)
//           Screens: S30 (bill detail: Print · Document tab · Corrections tab)
//                    S30 (All-bills list: toolbar · row actions · pager)
// Defects:  DEF-2451 (Print bill said the endpoint did not exist; it did) ·
//           DEF-2450 (the Customer's-bill link went to a route that does not
//           exist) · DEF-2453 (rule 15's `…` overflow has no component) ·
//           DEF-2452 (rule 16's "page size remembered" was built by nothing)
// Rules:    BR-BIL-036 (print is the floor) · BR-BIL-030 (the bill is locked at
//           issue) · BR-BIL-048 / BR-BIL-064 (`is_latest` and the chain head) ·
//           BR-SHL-025 (a control that cannot act is DISABLED WITH ITS REASON) ·
//           BR-SHL-011 (a shared URL opens the page it names) ·
//           B14 rule 12 (toolbar) · rule 15 (row actions) · rule 16 (pager)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT THIS SUITE IS AND IS NOT EVIDENCE FOR.**
//
// It proves STRUCTURE: which controls exist, where they point, and what a
// disabled one says. It is not evidence that any of it is USABLE — jsdom
// performs no layout and renders no `<iframe>` content at all, and the whole of
// CR-053 task 3 is a promise about a page drawn inside a frame. The browser
// harness is `10-scripts/render-checks/cr053-bill-surface.mjs`, and the PO's
// rule of 2026-08-30 is why it exists: *"All UI screen should be confirm using
// real broswer testing and not just based on test cases"*.
//
// EVERY CASE HERE WAS PROVED RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7).
// The verbatim failures are in the lane report.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { InvoiceDetail, MyPermissions } from "@/api/endpoints";
import type { RenderedBillDocument } from "@/api/billingOpsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { PAGE_SIZES } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";
import { entityAuditQueryKey } from "@/features/metering/PremisesDetailPage";

import { BillDetailPage, billDetailQueryKey } from "./BillDetailPage";
import { DEFAULT_BILL_LAYOUT, billDocumentKey } from "./BillDocumentPage";
import { billChainKey } from "./billChainEndpoints";
import type { InvoiceChain } from "./billChainEndpoints";
import {
  BILLS_PAGE_SIZE_PREFERENCE_KEY,
  pageSizeFromPreference,
} from "./BillsListPage";
import { billDocumentPdfPath } from "./billingOpsShared";

const TENANT = "brazosbend";
const INVOICE = "inv-18410";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** WE-1's bill, issued, with its locked copy on the row. */
function detail(over: Partial<InvoiceDetail> = {}): InvoiceDetail {
  return {
    id: INVOICE,
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
    lines: [],
    payload_version: 1,
    has_payload: true,
    // THE SERVER'S OWN VALUE — a bare API path, no `/api`, no tenant (DEF-2450).
    document_url: `/invoices/${INVOICE}/document`,
    summary: null,
    credit_notes: [],
    rebill_of_invoice_id: null,
    corrected_by_invoice_id: null,
    adjustments: [],
    deliveries: null,
    integrity: {
      currency: "USD",
      document_ties_out: true,
      payload_total: "247.870000",
      rows_total: "247.870000",
      payload_line_count: 3,
      row_line_count: 3,
      posting_balanced: true,
      ar_total: "247.870000",
      unavailable: [],
    },
    ...over,
  };
}

/** `documents_api._rendered_dict`'s shape, with the `pdf_url` it really sends. */
function rendered(over: Partial<RenderedBillDocument> = {}): RenderedBillDocument {
  return {
    invoice_id: INVOICE,
    invoice_no: "BL-2608-018410",
    template_id: "tpl-1",
    template_version: 3,
    payload_version: 1,
    layout_source: "platform-layout-classic-letter-v1",
    // DEF-2826 — the layout's own switches, served since 2026-08-31.
    layout: DEFAULT_BILL_LAYOUT,
    currency: "USD",
    content_type: "text/html; charset=utf-8",
    body: "<article>bill</article>",
    pdf_content_type: "application/pdf",
    pdf_page_count: 1,
    pdf_url: `/invoices/${INVOICE}/document.pdf`,
    masthead: [],
    meta: [],
    services: [],
    groups: [],
    summary: [],
    remarks: [],
    // A19 §1.7 — CR-052 task 9. Empty here: these fixtures describe bills
    // with no frozen usage block, and the panel is omitted whole for them.
    usage: [],
    footer: [],
    stub: [],
    absent: [],
    pdf_unrepresentable: [],
    problems: [],
    unavailable: [],
    provenance: "original",
    message_key: "billing.document.original",
    provenance_detail: "this is the bill as it was issued.",
    unavailable_reason: null,
    original_html: "<article>bill</article>",
    frozen_document: null,
    frozen_page: null,
    ...over,
  };
}

function chain(over: Partial<InvoiceChain> = {}): InvoiceChain {
  return {
    invoice_id: INVOICE,
    invoice_no: "BL-2608-018410",
    status: "issued",
    // CR-101-BRC03 — the chain carries this bill's own date and total now, so
    // the drawn *What happened* table has a first row.
    issued_at: "2026-08-02T09:00:00+00:00",
    total: "247.870000",
    currency: "USD",
    replaces: null,
    replaced_by: null,
    credit_notes: [],
    case: null,
    net_effect: null,
    head: { invoice_id: INVOICE, invoice_no: "BL-2608-018410" },
    is_latest: true,
    br_ref: "BR-BIL-048 · BR-BIL-064",
    chain_column: "invoices.corrects_invoice_id (PO 2026-08-12, OQ-120)",
    ...over,
  };
}

function permissions(access: string): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: "reads_billing_runs", label: "Reads & Billing runs", access }],
  };
}

function renderDetail(
  seed: {
    bill?: InvoiceDetail;
    document?: RenderedBillDocument;
    chain?: InvoiceChain;
    tab?: string;
  } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const bill = seed.bill ?? detail();
  queryClient.setQueryData(billDetailQueryKey(bill.id), bill);
  queryClient.setQueryData(queryKeys.myPermissions, permissions("Full"));
  queryClient.setQueryData(entityAuditQueryKey("invoice", bill.id), {
    page: { count: 0, next: null, previous: null, results: [] },
    window: { window: "hot", from: null },
  });
  if (seed.document !== undefined) {
    queryClient.setQueryData(billDocumentKey(bill.id), seed.document);
  }
  if (seed.chain !== undefined) {
    queryClient.setQueryData(billChainKey(bill.id), seed.chain);
  }
  const suffix = seed.tab === undefined ? "" : `?tab=${seed.tab}`;
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/billing/bills/${bill.id}${suffix}`]}>
          <Routes>
            <Route path="/:tenant/billing/bills/:invoiceId" element={<BillDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// TASKS 1 + 2 — PRINT BILL WORKS, AND THE REFUSALS THAT ARE STILL TRUE STAY
// ══════════════════════════════════════════════════════════════════════════

describe("CR-053 task 1 — Print bill is a working control (DEF-2451)", () => {
  it("an issued bill with its locked copy offers a LIVE link to the printable page", () => {
    const html = renderDetail({ document: rendered() });
    // The href is the SERVER's `pdf_url`, given the `/api` prefix and the
    // tenant segment a browser navigation needs (DEF-2450's other half).
    expect(html).toContain(`href="/api/${TENANT}/invoices/${INVOICE}/document.pdf"`);
    // ⚠ `data-testid` SINCE `CR-101-BRC03` — the control moved into the header's
    // `…` overflow, where the kit's menu row owns the element and carries a
    // `data-testid` rather than a `data-bil`. It is still an ANCHOR, which is
    // the guarantee this case exists for: middle-click and open-in-new-tab work
    // on a document link and do not work on a button.
    expect(html).toContain('data-testid="bil-print-bill"');
    // …and it is an ANCHOR, not a disabled button wearing the same label.
    expect(html).not.toContain('title="A draft has not been issued');
  });

  it("the retired reason cannot come back: the endpoint-does-not-exist sentence is gone", () => {
    // The claim was FALSE from the day `documents_api` was included. Asserted as
    // an absence in BOTH the rendered page and the catalogue, because a reworded
    // survivor is the same defect (hard-won law 1).
    const html = renderDetail({ document: rendered() });
    expect(html).not.toContain("which has not been built");
    expect(t("billing.bill.action.reprintBlocked")).toBe("billing.bill.action.reprintBlocked");
  });

  it("the printable page's own path is composed in ONE place and matches what the server sends", () => {
    // `documents_api._rendered_dict` publishes
    //     "pdf_url": f"/invoices/{invoice_id}/document.pdf"
    // and a LIST row has no document to read it from, so it is composed. This
    // case is what stops the two drifting apart unnoticed.
    expect(billDocumentPdfPath(INVOICE)).toBe(rendered().pdf_url);
    expect(billDocumentPdfPath("a/b")).toBe("/invoices/a%2Fb/document.pdf");
  });
});

describe("CR-053 task 2 — the refusals that are still true, each with its reason", () => {
  it("a DRAFT refuses the print, and says a draft has nothing stamped (BR-BIL-030)", () => {
    const html = renderDetail({
      bill: detail({
        status: "draft",
        invoice_no: null,
        issued_at: null,
        due_date: null,
        template_version: null,
        payload_version: null,
        has_payload: false,
        document_url: null,
      }),
    });
    expect(html).toContain("A draft has not been issued, so there is no saved copy to print.");
    expect(html).not.toContain("document.pdf");
  });

  it("an ISSUED bill with no locked copy refuses, and says THAT — not that the route is missing", () => {
    // DEF-116's distinction, kept: `has_payload` is a fact about the ROW.
    const html = renderDetail({ bill: detail({ has_payload: false }) });
    expect(html).toContain("No saved copy was recorded for this bill");
  });

  it("VOID is still refused, because POST /invoices/{id}/void is mounted by nothing", () => {
    const html = renderDetail({ document: rendered() });
    expect(html).toContain(t("billing.bill.action.void"));
    // BR-BIL-009: the consequence message is SERVER-computed, so no dialog here
    // — the button carries the server-side reason and opens nothing.
    expect(html).toContain("the endpoint that does it has not been built");
  });

  it("CORRECT is refused on a draft only — an issued bill LINKS to the Fix-a-bill tab", () => {
    const issued = renderDetail({ document: rendered() });
    expect(issued).toContain(`href="/${TENANT}/billing/fix?bill=${INVOICE}"`);
    const draft = renderDetail({ bill: detail({ status: "draft", has_payload: false }) });
    expect(draft).toContain(t("billing.bill.action.correctDraft"));
  });
});

// ══════════════════════════════════════════════════════════════════════════
// TASKS 3 + 4 — THE DOCUMENT TAB IS THE DOCUMENT, AND THE PANELS SERVE IT
// ══════════════════════════════════════════════════════════════════════════

// ⚠ **TASK 3 WAS REVERSED BY THE PRODUCT OWNER ON 2026-09-11, AND THESE THREE
// CASES NOW GUARD THE REVERSAL (`CR-105-BRC03`, 2026-09-14).**
//
// They read, in order: *the printable page is EMBEDDED* · *never an empty grey
// frame* · *the five panels render in their ruled order, top to bottom*. Every
// one was a true statement about CR-053 task 3, which said **THE OUTPUT IS THE
// SCREEN**. The ruling, verbatim: *"we dont what full view of the document -
// you give a link to download but full view of document is not requires - it
// does not add any value to user"*.
//
// **THEY ARE REWRITTEN RATHER THAN DELETED, DELIBERATELY.** A removed case
// proves nothing; a case that goes RED if the frame comes back is the thing
// that keeps a ruling from being un-made by the next lane reading task 3's own
// still-quotable reasoning. Same for the panel order: the five panels became
// seven groups, and the order is now the blueprint's.
describe("CR-053 tasks 3 and 4, as REVERSED by the ruling of 2026-09-11", () => {
  it("the embedded viewer is GONE — no frame, on a bill that has a printable page", () => {
    const html = renderDetail({ document: rendered() });
    expect(html).not.toContain("<iframe");
    expect(html).not.toContain('data-bil="printable-page"');
    // What replaced it: a download and an open-in-a-new-tab, at the same URL
    // the header's Print control opens.
    expect(html).toContain(`href="/api/${TENANT}/invoices/${INVOICE}/document.pdf" download`);
    expect(html).toContain('target="_blank"');
  });

  it("a bill with no printable page REFUSES both controls with their reason", () => {
    const html = renderDetail({ bill: detail({ has_payload: false }) });
    expect(html).not.toContain("<iframe");
    // BR-SHL-025 — disabled WITH the reason, and the reason is the row's fact.
    expect(html).toContain(t("billing.bill.action.download"));
    expect(html).toContain(t("billing.bill.action.reprintNoDocument"));
    expect(html).not.toContain(`href="/api/${TENANT}/invoices/${INVOICE}/document.pdf"`);
  });

  it("the SEVEN drawn groups render in the blueprint's order, top to bottom", () => {
    const html = renderDetail({ document: rendered() });
    // p016: *"Amount → Breakdown → Usage → Dates → the document itself →
    // Origin → Record"*. Matched on the rendered markup rather than on a
    // component name, because the order is the thing the drawing decided.
    const order = [
      t("billing.bill.panel.summary"),
      t("billing.bill.panel.breakdown"),
      t("billing.bill.panel.usage"),
      t("billing.bill.panel.dates"),
      t("billing.bill.panel.theBill"),
      t("billing.bill.panel.originShort"),
      t("billing.bill.panel.record"),
    ]
      // React escapes on the way out, so an apostrophe in a catalogue string is
      // `&#x27;` in the markup — matching the raw string would fail over
      // correct behaviour (the cr049 harness records the same trap).
      .map((heading) => heading.replace(/'/g, "&#x27;"))
      .map((heading) => html.indexOf(`>${heading}<`));
    expect(order.every((at) => at > 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    // B14 rule 32 — the last two are CLOSED by default, and a `<details>` with
    // no `open` attribute is what closed means.
    expect(html).toContain('<details class="mt-4 border-t border-divider pt-3" data-bil="group-origin"');
    expect(html).not.toContain('data-bil="group-origin" open');
    expect(html).not.toContain('data-bil="group-record" open');
  });

  it("task 4: the customer's bill is an IN-APP LINK, and never the raw API path (DEF-2450)", () => {
    const html = renderDetail({ document: rendered() });
    expect(html).toContain(`href="/${TENANT}/billing/bills/${INVOICE}/document"`);
    expect(html).not.toContain(`href="/invoices/${INVOICE}/document"`);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// TASK 5 — THE CHAIN, AND THE ONE QUESTION IT ANSWERS THAT THE DETAIL CANNOT
// ══════════════════════════════════════════════════════════════════════════

describe("CR-053 task 5 — /invoices/{id}/chain, drawn with is_latest", () => {
  it("is_latest true says so plainly, on an uncorrected bill", () => {
    const html = renderDetail({ tab: "chain", chain: chain() });
    expect(html).toContain('data-bil="chain-latest"');
    // ⚠ **ONE PILL AND ONE SENTENCE SINCE `CR-101-BRC03`.** The blueprint
    // promotes the standing to a PILL and merges the two stacked sentences into
    // one line: *"every sentence on the live tab survives — one is promoted to
    // a pill, one is merged into the standing line."* Both halves are asserted
    // so neither can be dropped in a later tidy-up.
    expect(html).toContain("This is the current bill");
    expect(html).toContain(
      "Nothing has replaced it, and no credit note or replacement bill is recorded against it.",
    );
  });

  it("is_latest false NAMES the replacement and links to it — the failure this prevents", () => {
    // A superseded bill quoted to a customer is the whole reason BR-BIL-064
    // puts the head on the screen rather than leaving it to a clerk to walk.
    const html = renderDetail({
      bill: detail({ status: "corrected", corrected_by_invoice_id: "inv-99" }),
      tab: "chain",
      chain: chain({
        status: "corrected",
        is_latest: false,
        replaced_by: { invoice_id: "inv-99", invoice_no: "BL-2607-000048" },
        head: { invoice_id: "inv-99", invoice_no: "BL-2607-000048" },
      }),
    });
    expect(html).toContain('data-bil="chain-superseded"');
    expect(html).toContain("Replaced");
    expect(html).toContain("BL-2607-000048");
    expect(html).toContain(`href="/${TENANT}/billing/bills/inv-99"`);
  });

  it("the chain route failing does not blank the tab — the detail's own fields still draw", () => {
    // Seeded with NO chain: the query is left to fail rather than answered, so
    // this is the deployment-skew case and not a fixture of one.
    const html = renderDetail({
      bill: detail({ status: "corrected", corrected_by_invoice_id: "inv-99" }),
      tab: "chain",
    });
    // ⚠ **THE FALLBACK IS THE SAME AND ITS SHAPE MOVED (`CR-101-BRC03`).** The
    // replacement was a labelled `Replaced by bill` pair; it is now a ROW of the
    // *What happened* table, built from the same `corrected_by_invoice_id` when
    // the chain route does not answer. The guarantee this case exists for is
    // untouched: the tab does not blank, and the replacement is still named and
    // still linked.
    expect(html).toContain("replacement bill");
    expect(html).toContain(`href="/${TENANT}/billing/bills/inv-99"`);
    // …and it never claims the bill is current when its own column says
    // otherwise. `corrected_by_invoice_id` is set here, so the in-flight
    // standing reads *Replaced* — from this bill's own row, never from a walk
    // of a chain the server has not answered for.
    expect(html).not.toContain("This is the current bill");
    expect(html).toContain("Replaced");
  });

  // DEF-BIL-10147 — a case is numbered at Send (G3, PO 2026-10-14), so the
  // bill page's *correction opened* row names it; the words stay for the one
  // case a deleted series leaves unnumbered.
  it("DEF-BIL-10147 — the correction-opened row names the case number", () => {
    const opened = (caseNo: string | null) =>
      renderDetail({
        tab: "chain",
        chain: chain({
          // The history table draws once the case has a document behind it.
          credit_notes: [
            {
              id: "cn-1",
              credit_note_no: "CM-0041",
              amount: "-24.700000",
              currency: "USD",
              reason: "Meter misread",
              issued_at: "2026-10-15",
            },
          ],
          case: {
            case_no: caseNo,
            status: "pending_approval",
            reason_codes: ["wrong_read"],
            opened_at: "2026-10-14T10:00:00+00:00",
            opened_by: null,
            approved_on: null,
            approved_by: null,
          },
        }),
      });
    const numbered = opened("CC-2026-001");
    expect(numbered).toContain(t("billing.bill.event.caseNo", { caseNo: "CC-2026-001" }));
    expect(numbered).not.toContain(t("billing.fix.noCaseNo"));
    expect(opened(null)).toContain(t("billing.fix.noCaseNo"));
  });
});

// ══════════════════════════════════════════════════════════════════════════
// TASK 12 — THE REMEMBERED PAGE SIZE, AS THREE PROVABLE STATES (DEF-2452)
// ══════════════════════════════════════════════════════════════════════════

describe("CR-053 task 12 — page size remembered (B14 rule 16)", () => {
  it("the preference key matches the shared table's own key grammar", () => {
    // `table(\.[A-Za-z0-9_-]+)+` — the pattern `columnPreferenceKey` enforces.
    expect(BILLS_PAGE_SIZE_PREFERENCE_KEY).toBe("table.S30.pageSize");
    expect(/^table(\.[A-Za-z0-9_-]+)+$/.test(BILLS_PAGE_SIZE_PREFERENCE_KEY)).toBe(true);
  });

  it("only one of the five declared sizes is ever restored (BR-SHL-024)", () => {
    for (const size of PAGE_SIZES) {
      expect(pageSizeFromPreference(size)).toBe(size);
    }
    // Everything else reads as ABSENT and the caller keeps its default —
    // never an error, and never a page size the pager cannot show.
    for (const junk of [null, undefined, 0, 7, 51, "100", { per: 100 }, [100], NaN]) {
      expect(pageSizeFromPreference(junk)).toBeNull();
    }
  });
});
