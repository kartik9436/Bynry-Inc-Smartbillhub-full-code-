// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   **DEF-2826** — the bill document screen NAMED the layout it was
//           rendered from and then drew a different one. `layout_source`
//           appeared exactly once in `BillDocumentPage.tsx` and only inside
//           that sentence; there was no branch on the layout anywhere.
//           **DEF-2715** — and the sentence printed the raw key
//           `platform-layout-compact-letter-v1` at a clerk while it was there.
//           Screens: S30 (bill detail → View the bill as sent)
// Rules:    BR-BIL-026 (a reprint renders the PINNED version, forever) ·
//           B14 rule 31 (nothing internal is the visible value of a field) ·
//           B14 rule 32 clause 4 · hard-won law 1 (a page that NARRATES a
//           guarantee instead of performing it) · law 7 (RED first)
// ───────────────────────────────────────────────────────
// **WHAT WAS MEASURED, IN A REAL BROWSER, BEFORE ANY OF THIS WAS WRITTEN.** Two
// bills issued minutes apart through the product's own doors: one pinned to
// `standard-letter-v1`, one to `compact-letter-v1`. The KEPT COPIES prove the
// SERVER is right — the standard bill's frozen HTML is 3,433 bytes and contains
// *Rate* once and *Usage* twice; the compact one is 2,019 bytes and contains
// NEITHER WORD, which is exactly what `LayoutSpec(compact-letter-v1,
// services_band=False, detail_columns=False)` says. **The screen drew
// DESCRIPTION / USAGE / RATE / AMOUNT for both.**
//
// So a utility that chose the compact layout was shown a page announcing
// compact and looking standard, directly above a link to the real compact page.
// Nothing about the money was wrong and no customer received the wrong page —
// what is posted is the frozen copy — so the whole cost is a clerk who cannot
// use this screen for the one thing it exists for.
//
// ⚠ **WHAT THIS SUITE CANNOT SEE.** jsdom performs no layout, so nothing here is
// evidence about geometry. What it proves is STRUCTURE: which bands and which
// COLUMNS a layout's switches put on the page, which is precisely what differed.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { BillDocumentLayout, RenderedBillDocument } from "@/api/billingOpsEndpoints";
import { ToastProvider } from "@/components/Toast";

import { BillDocumentPage, DEFAULT_BILL_LAYOUT } from "./BillDocumentPage";

const T = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const COMPACT: BillDocumentLayout = {
  key: "compact-letter-v1",
  masthead: true,
  services_band: false,
  detail_columns: false,
  summary_first: false,
  stub: true,
  reserve_rows: 0,
};

const LETTERHEAD: BillDocumentLayout = {
  ...DEFAULT_BILL_LAYOUT,
  key: "letterhead-letter-v1",
  masthead: false,
  reserve_rows: 6,
};

const NO_STUB: BillDocumentLayout = {
  ...DEFAULT_BILL_LAYOUT,
  key: "no-stub-letter-v1",
  stub: false,
};

/** A bill with something in every band, so a band that vanishes vanished
 *  because of the LAYOUT and not because it was empty — `DocumentBand` already
 *  renders nothing for an empty band, and a fixture with empty bands would let
 *  this whole suite pass over the defect. */
function aDocument(layout: BillDocumentLayout): RenderedBillDocument {
  return {
    invoice_id: "inv-1",
    invoice_no: "BL-2608-000097",
    template_id: "tpl-1",
    template_version: 3,
    payload_version: 1,
    layout_source: `platform-layout-${layout.key}`,
    layout,
    currency: "USD",
    content_type: "text/html; charset=utf-8",
    body: "<article>rebuilt</article>",
    pdf_content_type: "application/pdf",
    pdf_page_count: 1,
    pdf_url: "/invoices/inv-1/document.pdf",
    masthead: [{ label: "Utility", value: "Brazos Water", absent: null }],
    meta: [{ label: "Bill #", value: "BL-2608-000097", absent: null }],
    services: [{ label: "Services", value: "water", absent: null }],
    groups: [
      {
        heading: "Water",
        absent: null,
        lines: [
          {
            description: "Volumetric",
            quantity: "12.5 kgal",
            unit_price: "3.2000",
            amount: "40.00",
          },
        ],
      },
    ],
    summary: [{ label: "Total due", value: "40.00", absent: null }],
    remarks: [],
    usage: [],
    footer: [],
    stub: [{ label: "Amount enclosed", value: "—", absent: null }],
    absent: [],
    pdf_unrepresentable: [],
    problems: [],
    unavailable: [],
    // A REBUILD, deliberately: the original-bytes branch draws a sandboxed
    // frame and no bands at all, so a fixture with a kept copy would prove
    // nothing about which bands the rebuild draws.
    provenance: "re_rendered_from_data_not_the_original",
    message_key: "billing.document.reRendered",
    provenance_detail: "no copy of this bill was kept.",
    unavailable_reason: "document_not_stored",
    original_html: null,
    frozen_document: null,
    frozen_page: null,
  };
}

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

async function mount(layout: BillDocumentLayout) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazos/bills/inv-1/document"]}>
          <Routes>
            <Route
              path="/:tenant/bills/:invoiceId/document"
              element={<BillDocumentPage client={clientReturning(aDocument(layout))} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  await waitFor(() => {
    expect(screen.getByText(T("billing.document.band.meta"))).toBeInTheDocument();
  });
}

describe("DEF-2826 — the page draws the layout it says it drew", () => {
  it("the compact layout drops the services band and the Usage/Rate columns", async () => {
    await mount(COMPACT);

    // The two words the frozen compact copy does not contain. This is the
    // assertion the browser check found the defect with, in miniature.
    expect(screen.queryByText(T("billing.document.col.usage"))).not.toBeInTheDocument();
    expect(screen.queryByText(T("billing.document.col.rate"))).not.toBeInTheDocument();
    expect(
      screen.queryByText(T("billing.document.band.services")),
    ).not.toBeInTheDocument();

    // ⚠ AND THE MONEY IS STILL THERE. A layout suppresses DETAIL, never the
    // amount — a bill that dropped its own charge figures would be a far worse
    // defect than the one being fixed.
    // Twice — the charge line and the summary box — which is why this is
    // `getAllByText`: the figure is on the page in both places or neither.
    expect(screen.getAllByText("40.00")).toHaveLength(2);
    expect(screen.getByText(T("billing.document.col.amount"))).toBeInTheDocument();
    // And the quantity is gone WITH its column, not left orphaned in a cell
    // under the wrong heading.
    expect(screen.queryByText("12.5 kgal")).not.toBeInTheDocument();
  });

  it("the standard layout still draws everything it always drew", async () => {
    await mount(DEFAULT_BILL_LAYOUT);

    expect(screen.getByText(T("billing.document.col.usage"))).toBeInTheDocument();
    expect(screen.getByText(T("billing.document.col.rate"))).toBeInTheDocument();
    expect(screen.getByText(T("billing.document.band.services"))).toBeInTheDocument();
    expect(screen.getByText(T("billing.document.band.masthead"))).toBeInTheDocument();
    expect(screen.getByText(T("billing.document.band.stub"))).toBeInTheDocument();
  });

  it("the letterhead layout suppresses the masthead — its whole purpose", async () => {
    await mount(LETTERHEAD);

    expect(screen.queryByText(T("billing.document.band.masthead"))).not.toBeInTheDocument();
    expect(screen.queryByText("Brazos Water")).not.toBeInTheDocument();
    // Everything else is untouched: this layout suppresses ONE band.
    expect(screen.getByText(T("billing.document.band.services"))).toBeInTheDocument();
  });

  it("the no-stub layout drops the remittance stub and nothing else", async () => {
    await mount(NO_STUB);

    expect(screen.queryByText(T("billing.document.band.stub"))).not.toBeInTheDocument();
    expect(screen.getByText(T("billing.document.band.summary"))).toBeInTheDocument();
  });

  it("names the layout in words and keeps the key off the screen (B14 rule 31)", async () => {
    await mount(COMPACT);

    expect(
      screen.getByText(
        T("billing.document.layoutSource", {
          source: T("billing.document.layout.compact-letter-v1"),
        }),
        { exact: false },
      ),
    ).toBeInTheDocument();
    // ⚠ THE NEGATIVE IS THE POINT. The raw key was the VISIBLE VALUE of this
    // sentence; it is now on the element, where support reads it.
    expect(screen.queryByText(/platform-layout-compact-letter-v1/)).not.toBeInTheDocument();
    expect(
      document.querySelector('[data-layout-source="platform-layout-compact-letter-v1"]'),
    ).not.toBeNull();
  });
});
