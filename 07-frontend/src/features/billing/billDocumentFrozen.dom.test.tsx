// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-049 task 4 — "The bill: store the PDF and HTML at issue", and
//          DEF-2553, the page titled *view the bill as sent* that rebuilt the
//          bill on every open.
//          Screens: S30 (bill detail → View the bill as sent)
// Rules:   BR-NOT-027 (a legal document is FROZEN as the document — PO
//          2026-08-30) · BR-BIL-030 (the bill's INPUTS are frozen, which is a
//          DIFFERENT rule) · BR-SHL-020 (plain language when something is
//          absent) · B14 rule 21 (this file's screen is on
//          route-b-migrated.txt) · hard-won law 2 (built is not wired) ·
//          law 7 (RED first)
// ───────────────────────────────────────────────────────
// THE ONE THING THIS SUITE EXISTS FOR:
//
//   **A CLERK OPENING "THE BILL AS IT WAS SENT" MUST BE ABLE TO TELL THE BILL
//   FROM A REBUILD OF IT.** If they cannot, the store, the freeze at issue and
//   the route are worth nothing — a screen showing a rebuild as though it were
//   the bill is the whole of what `DEF-2553` was filed for.
//
// So the two acceptance cases are a matched pair. The first proves the ORIGINAL
// bytes reach the page; the second proves a bill with no kept copy is announced
// as a rebuild, in a warning, with no original drawn anywhere.
//
// ⚠ WHAT THIS SUITE CANNOT SEE. jsdom performs no layout, so nothing here is
// evidence about geometry — that is the browser harness's job
// (`10-scripts/render-checks/cr049-bill-document.mjs`). What it proves is
// STRUCTURE: which words are in the document and which are absent.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { RenderedBillDocument } from "@/api/billingOpsEndpoints";
import { ToastProvider } from "@/components/Toast";

import { BillDocumentPage, DEFAULT_BILL_LAYOUT, byteLabel } from "./BillDocumentPage";

const T = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

/** The bill AS IT WAS ISSUED — on the layout the tenant had chosen that day. */
const ISSUED_HTML =
  '<article class="bill"><section class="services"><h2>Services this period</h2>' +
  "<table><tr><th>electric</th><td>read</td></tr></table></section></article>";

/** What the SAME bill re-renders to today, after somebody changed the layout.
 *  The services band is gone. It must never appear on a bill that has an
 *  original, and the original must never be replaced by it. */
const TODAYS_LAYOUT_KEY = "platform-layout-compact-letter-v1";

function aDocument(overrides: Partial<RenderedBillDocument>): RenderedBillDocument {
  return {
    invoice_id: "inv-1",
    invoice_no: "BL-2607-000101",
    template_id: "tpl-1",
    template_version: 1,
    payload_version: 1,
    layout_source: TODAYS_LAYOUT_KEY,
    // DEF-2826 — the switches the page branches on. These fixtures describe
    // bills on the DEFAULT layout, which is what they always drew.
    layout: DEFAULT_BILL_LAYOUT,
    currency: "USD",
    content_type: "text/html; charset=utf-8",
    body: "<article>today</article>",
    pdf_content_type: "application/pdf",
    pdf_page_count: 1,
    pdf_url: "/invoices/inv-1/document.pdf",
    masthead: [],
    meta: [{ label: "Bill #", value: "BL-2607-000101", absent: null }],
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
    original_html: ISSUED_HTML,
    frozen_document: {
      id: "doc-1",
      kind: "bill",
      display_name: "bill/2026/07/A-10432-BL-2607-000101.html",
      content_type: "text/html; charset=utf-8",
      content_hash: "a1b2c3d4e5f6",
      byte_length: 2048,
      stored_at: "2026-07-08T09:00:00Z",
      storage_backend: "filesystem",
    },
    frozen_page: null,
    ...overrides,
  };
}

/** A transport that answers the permission probe and the document, and nothing
 *  else. `client` is PASSED into the page, never defaulted at the call site —
 *  the DEF-007..010 class is a component whose prop nothing supplies. */
function clientReturning(body: RenderedBillDocument): ApiClient {
  return {
    get: vi.fn().mockImplementation((path: string) => {
      if (path.includes("permissions")) {
        return Promise.resolve({
          data: { permissions: [{ code: "reads_billing_runs", access: "Full" }] },
        });
      }
      return Promise.resolve({ data: body });
    }),
  } as unknown as ApiClient;
}

function mount(body: RenderedBillDocument) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazos/bills/inv-1/document"]}>
          <Routes>
            <Route
              path="/:tenant/bills/:invoiceId/document"
              element={<BillDocumentPage client={clientReturning(body)} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-049 task 4 — the bill as it was issued, and a rebuild of it, are different", () => {
  it("draws the ORIGINAL bill, in its own frame, with the checksum that proves it", async () => {
    mount(aDocument({}));

    await waitFor(() => {
      expect(
        screen.getByText(
          T("billing.document.original", {
            sealedOn: new Date("2026-07-08T09:00:00Z").toLocaleString(),
          }),
        ),
      ).toBeInTheDocument();
    });

    // ⚠ THE BYTES, NOT A RE-DERIVATION OF THEM. The frame carries the kept HTML
    // exactly as it was stored — which is the only thing that makes this page's
    // title true — and it is sandboxed with no `allow-scripts`, so the document
    // is inert.
    const frame = screen.getByTitle(T("billing.document.originalFrameTitle"));
    expect(frame).toHaveAttribute("srcdoc", ISSUED_HTML);
    expect(frame).toHaveAttribute("sandbox", "");

    expect(screen.getByText("a1b2c3d4e5f6")).toBeInTheDocument();
    expect(screen.getByText(byteLabel(2048))).toBeInTheDocument();
    expect(
      screen.getByText("bill/2026/07/A-10432-BL-2607-000101.html"),
    ).toBeInTheDocument();

    // The printable link says WHICH page it opens. A PDF response cannot carry
    // a caption, so the button is where a person is told.
    expect(screen.getByText(T("billing.document.openOriginalPdf"))).toBeInTheDocument();

    // And the honest-half sentence is NOT on this page.
    expect(screen.queryByText(T("billing.document.reRendered"))).not.toBeInTheDocument();
  });

  it("says a bill with no kept copy is REBUILT, and draws no original at all", async () => {
    mount(
      aDocument({
        provenance: "re_rendered_from_data_not_the_original",
        message_key: "billing.document.reRendered",
        provenance_detail:
          "no copy of this bill was kept as it was issued, so anything shown here is REBUILT.",
        unavailable_reason: "document_not_stored",
        original_html: null,
        frozen_document: null,
      }),
    );

    await waitFor(() => {
      expect(screen.getByText(T("billing.document.reRendered"))).toBeInTheDocument();
    });

    // ⚠ **NO ORIGINAL IS DRAWN.** Not the frame, not a checksum, not the
    // "as it was issued" sentence. A rebuild under a reassuring caption is the
    // defect; the caption is what nobody reads.
    expect(
      screen.queryByTitle(T("billing.document.originalFrameTitle")),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(T("billing.document.checksum"))).not.toBeInTheDocument();
    expect(screen.queryByText(T("billing.document.openOriginalPdf"))).not.toBeInTheDocument();
    expect(screen.getByText(T("billing.document.openPdf"))).toBeInTheDocument();

    // The warning is a warning, not a note: it carries `role="alert"`, so it
    // reaches a screen reader as one.
    expect(screen.getByRole("alert")).toHaveTextContent(T("billing.document.reRendered"));
  });

  it("labels the structured bands as a rebuild on BOTH states, so neither is mistaken for the bill", async () => {
    mount(aDocument({}));
    await waitFor(() => {
      expect(screen.getByText(/Rebuilt below/)).toBeInTheDocument();
    });
    // The bands are still drawn — a clerk on a phone call needs the figures, and
    // every one of them is the FROZEN figure (BR-BIL-030). What must never
    // happen is their being presented AS the bill.
    expect(screen.getByText("BL-2607-000101")).toBeInTheDocument();
  });
});
