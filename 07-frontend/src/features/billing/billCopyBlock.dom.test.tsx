// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-052 task 11 — *"Draw both on the document, including the late-fee
//          terms the product is required to disclose"*, over task 10's stamp
//          (`issue._stamp_bill_copy`, landed 2026-08-30).
// Story:   US-BIL-022 (the pinned document) · US-BIL-026 (S30 bill detail)
//          Screens: S30 → View the bill as sent
// Rules:   BR-BIL-021 (the tenant's bill message and footer) · BR-BIL-030 (the
//          copy is frozen at issue, so a reprint shows what was sent) ·
//          BR-SHL-020 (plain language when something is absent) · hard rule 4
//          (an issued bill is never edited) · law 7 (RED first)
// ───────────────────────────────────────────────────────
// THE ONE THING THIS SUITE EXISTS FOR:
//
//   **THE PLATFORM COMPOSES NO LATE-FEE COPY, AND THE PAGE MUST NOT START.**
//
// `issue._stamp_bill_copy` says it in the server's own words — the terms are
// the TENANT's to write, they are charged whether or not they are printed, and
// *"a platform that wrote a customer's disclosure for them would be inventing
// legal copy in one language"*. The prototype prints *"the greater of $5.00 or
// 1.5%"*; that figure is r10's sample utility's, not this product's, and the
// second case below is the guard that keeps it — or anything like it — off a
// real customer's bill. A future lane "completing" this feature by supplying a
// default sentence fails that case, which is exactly the point.
//
// The other half is ordinary and still worth pinning: when the tenant HAS
// written the copy, it is drawn as PROSE — the line breaks they typed survive,
// because a ways-to-pay block is an address and an address is not one line.
//
// ⚠ WHAT THIS SUITE CANNOT SEE. jsdom performs no layout, so the reading
// measure and the panel's position are the browser harness's evidence
// (`10-scripts/render-checks/cr053-bill-surface.mjs`), not this file's.
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

import { BillDocumentPage, DEFAULT_BILL_LAYOUT } from "./BillDocumentPage";

const T = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

/** The tenant's own words, exactly as `bill_template_versions.options` holds
 *  them — with the newlines a person typed into a textarea. */
const WAYS_TO_PAY =
  "Online: brazosbendutilities.com/pay\nBy phone: (281) 555-0100\n" +
  "By post: PO Box 4120, Rosenberg TX 77471";

/** ⚠ A REAL tenant's late-fee wording — the tenant's, not ours. It is here to
 *  prove the page PRINTS what a tenant writes, never that the page knows what
 *  a late fee is. */
const MESSAGE =
  "Thank you for your payment.\nA late charge of 1.5% per month applies to any " +
  "balance unpaid after the due date.";

function aDocument(overrides: Partial<RenderedBillDocument>): RenderedBillDocument {
  return {
    invoice_id: "inv-1",
    invoice_no: "BL-2607-000101",
    template_id: "tpl-1",
    template_version: 1,
    payload_version: 1,
    layout_source: "platform-layout-standard-letter-v1",
    // DEF-2826 — the layout's own switches, served since 2026-08-31.
    layout: DEFAULT_BILL_LAYOUT,
    currency: "USD",
    content_type: "text/html; charset=utf-8",
    body: "<article>today</article>",
    pdf_content_type: "application/pdf",
    pdf_page_count: 1,
    pdf_url: "/invoices/inv-1/document.pdf",
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
    provenance: "re_rendered_from_data_not_the_original",
    message_key: "billing.document.reRendered",
    provenance_detail: "no copy was kept when this bill was issued.",
    unavailable_reason: "issued_before_the_store_existed",
    original_html: null,
    frozen_document: null,
    frozen_page: null,
    ...overrides,
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

describe("CR-052 task 11 — the bill message and ways to pay, on the document", () => {
  it("draws the tenant's own words as prose, with the line breaks they typed", async () => {
    mount(
      aDocument({
        footer: [
          { label: "Message", value: MESSAGE, absent: null },
          { label: "Ways to pay", value: WAYS_TO_PAY, absent: null },
        ],
      }),
    );

    const panel = await waitFor(() => {
      const found = document.querySelector('[data-bil="bill-copy"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });

    // Both labels and both bodies reached the page.
    expect(panel.textContent).toContain("Message");
    expect(panel.textContent).toContain("Ways to pay");
    expect(panel.textContent).toContain("A late charge of 1.5% per month");
    expect(panel.textContent).toContain("PO Box 4120, Rosenberg TX 77471");

    // ⚠ THE LINE BREAKS ARE THE POINT AND NOTHING ELSE CAN SEE THEM. HTML
    // collapses a newline to a space, so a ways-to-pay block rendered without
    // `white-space: pre-line` prints three addresses as one sentence. The
    // value carries the raw newlines and the element asks for them to show.
    const values = panel.querySelectorAll('[data-bil="bill-copy-value"]');
    expect(values).toHaveLength(2);
    expect(values[1].textContent).toContain("\n");
    expect(values[1].className).toContain("whitespace-pre-line");

    // A tenant who HAS written its copy is told nothing about what is missing.
    expect(panel.querySelector('[data-bil="bill-copy-consequence"]')).toBeNull();
  });

  it("says the bill carries no late-payment terms, and INVENTS NONE", async () => {
    mount(
      aDocument({
        footer: [
          {
            label: "Message",
            value: "—",
            absent: {
              field: "message",
              why: "…this tenant has written no bill message. Nothing here composes one for them…",
              br_ref: "BR-BIL-021",
            },
          },
          {
            label: "Ways to pay",
            value: "—",
            absent: {
              field: "ways_to_pay",
              why: "…this absence means the tenant has written none…",
              br_ref: "BR-BIL-021",
            },
          },
        ],
      }),
    );

    const panel = await waitFor(() => {
      const found = document.querySelector('[data-bil="bill-copy"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });

    expect(panel.querySelectorAll('[data-bil="bill-copy-absent"]')).toHaveLength(2);
    expect(screen.getAllByText(T("billing.document.copyAbsent"))).toHaveLength(2);

    // ONE consequence sentence for the block, not one per field.
    const note = panel.querySelector('[data-bil="bill-copy-consequence"]');
    expect(note).not.toBeNull();
    expect(note?.textContent).toBe(T("billing.document.copyConsequence"));

    // ══════════════════════════════════════════════════════════════════════
    // THE GUARD THIS FILE EXISTS FOR. No default late-fee figure, ever.
    // ══════════════════════════════════════════════════════════════════════
    // The prototype prints "the greater of $5.00 or 1.5%". That is r10's
    // sample utility's wording. If a later lane "finishes" this feature by
    // shipping a default sentence, these four assertions fail — which is the
    // only thing standing between this product and a legal disclosure it
    // invented for a customer it has never met.
    const page = document.body.textContent ?? "";
    expect(page).not.toContain("1.5%");
    expect(page).not.toContain("$5.00");
    expect(page).not.toContain("greater of");
    expect(page).not.toContain("late fee of");

    // The SERVER's engineering sentence is kept for support and is NOT the
    // headline a clerk reads (DEF-1931's test, DEF-2715 for the other bands).
    const absent = panel.querySelector('[data-bil="bill-copy-absent"]');
    expect(absent?.getAttribute("title")).toContain("Nothing here composes one for them");
    expect(absent?.getAttribute("data-br-ref")).toBe("BR-BIL-021");
    expect(panel.textContent).not.toContain("Nothing here composes one for them");
  });

  it("renders nothing at all when the server sends an empty footer band", async () => {
    mount(aDocument({ footer: [] }));
    await waitFor(() => {
      expect(screen.getByText(T("billing.document.rebuiltBands"), { exact: false })).toBeInTheDocument();
    });
    expect(document.querySelector('[data-bil="bill-copy"]')).toBeNull();
  });
});
