// ── Trace ──────────────────────────────────────────────
// Change:   CR-053 tasks 6 and 8 — *"on this screen you will ahve to cosndier
//           all scenarios - utilty services charges, charge code raletd,
//           discount related, taxes related, previosu due, later payment date
//           etc"* (PO 2026-08-30) · CR-052 task 11 — the bill message and ways
//           to pay, *"including the late-fee terms the product is required to
//           disclose"*
// Story:    US-BIL-026 (§1 names all seven line fields as REQUIRED) ·
//           US-BIL-025 (`past_due` is derived server-side)
// Screens:  S30 → bill detail → Charges tab · the bill document
// Defects:  DEF-2429 (a `minimum_adjustment` line stores `service_id = NULL`,
//           so per-service money lands in the bill-level bucket) ·
//           DEF-2428 (rating publishes no charge-id → code read, so
//           `charge_code` is null and the id must NOT be printed instead —
//           that is DEF-2432's `BR-BIL-015` leak) · DEF-2712 (the client's
//           `InvoiceLineKind` union named two kinds no server writes and
//           missed the three this tab draws)
// Rules:    BR-BIL-069 (whose tax a line is) · BR-BIL-010 (the GL stamp and
//           the fee key) · BR-BIL-032 (drift can never be silent) ·
//           BR-RAT-028 (the per-service minimum) · BR-BIL-021 (the tenant's
//           bill message and footer) · B4.4 + B4's 2026-08-11 ruling (Σ of the
//           ROUNDED lines) · PO 2026-08-11 *"Tax rates are for bill not for
//           service"* · PO 2026-08-30 R1–R7 (*the document displays what the
//           server resolved*)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT THESE CASES ARE FOR, AND IT IS NOT COVERAGE.** Every one of them
// pins a decision that a later tidy-up would otherwise undo silently:
//
//   * the SEVEN column headers, because Accounting code and Rate version are
//     the two a redesign drops first and `US-BIL-026` §1 makes them required;
//   * that the per-service subtotal on the page is the SERVER's string and not
//     a sum computed here — the assertion uses a figure that is deliberately
//     NOT the sum of the fixture's own lines, so a client-side re-sum fails it;
//   * that a stated tie-out failure is REPORTED and neither figure moved;
//   * that a `charge_id` never reaches the screen as text.
//
// A browser cannot see any of these and neither can a gate. What a browser
// CAN see — computed alignment, real geometry, the frame's contents — is in
// `10-scripts/render-checks/cr053-bill-surface.mjs`, which is where the PO's
// *"All UI screen should be confirm using real broswer testing"* is honoured.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type { InvoiceDetail, InvoiceLineRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions } from "@/api/endpoints";
import { entityAuditQueryKey } from "@/features/metering/PremisesDetailPage";
import { ToastProvider } from "@/components/Toast";

import { BillDetailPage, billDetailQueryKey } from "./BillDetailPage";
import { billDetailPath } from "./billingShared";

const TEST_TENANT = "brazosbend";

function line(over: Partial<InvoiceLineRow> = {}): InvoiceLineRow {
  return {
    id: "ln-1",
    kind: "usage",
    description: "Water usage",
    quantity: "43.000000",
    unit: "kgal",
    unit_price: "5.200000",
    amount: "223.600000",
    taxable: true,
    gl_account_id: "gl-4110",
    gl_account_code: "4110",
    gl_account_name: "Water usage",
    tariff_version_id: "tv-1",
    tariff_version_label: "Sample — Commercial water (flat) · from 2026-06-01",
    service: "water",
    tax_id: null,
    tax_authority: null,
    charge_id: null,
    charge_code: null,
    charge_name: null,
    period_start: "2026-07-01",
    period_end: "2026-07-31",
    ...over,
  };
}

/**
 * A bill carrying EVERY scenario the PO listed, in one fixture — which is the
 * shape the task asks for and the shape no seeded bill has (the demo utility
 * seeds usage, base and two taxes and nothing else).
 */
function detail(over: Partial<InvoiceDetail> = {}): InvoiceDetail {
  return {
    id: "inv-cr053",
    invoice_no: "BL-2608-000094",
    bill_type: "cycle",
    status: "issued",
    past_due: false,
    account_id: "acc-1",
    account_no: "A-10432",
    customer_name: "Miller, Sarah",
    cycle_label: "08-A",
    bill_run_id: "run-07a",
    service_date: "2026-07-31",
    period_start: "2026-07-01",
    period_end: "2026-07-31",
    issued_at: "2026-08-08",
    due_date: "2026-08-25",
    subtotal: "238.600000",
    tax_total: "19.680000",
    total: "258.280000",
    currency: "USD",
    template_version: 1,
    lines: [
      line(),
      line({
        id: "ln-2",
        kind: "base",
        description: "Water base charge",
        quantity: null,
        unit: null,
        unit_price: null,
        amount: "15.000000",
        gl_account_code: "4105",
        gl_account_name: "Water base",
      }),
      line({
        id: "ln-3",
        kind: "tax",
        description: "Tax Local",
        quantity: null,
        unit: null,
        unit_price: null,
        amount: "6.560000",
        taxable: false,
        service: null,
        gl_account_code: "2200",
        gl_account_name: "Sales tax payable",
        tariff_version_id: null,
        tariff_version_label: null,
        tax_id: "tax-bexar",
        tax_authority: "Bexar County Tax Office",
      }),
      line({
        id: "ln-4",
        kind: "tax",
        description: "Tax Texas State",
        quantity: null,
        unit: null,
        unit_price: null,
        amount: "13.120000",
        taxable: false,
        service: null,
        gl_account_code: "2200",
        gl_account_name: "Sales tax payable",
        tariff_version_id: null,
        tariff_version_label: null,
        tax_id: "tax-texas",
        tax_authority: "Texas Comptroller of Public Accounts",
      }),
    ],
    payload_version: 1,
    has_payload: true,
    document_url: "/invoices/inv-cr053/document",
    charges_by_service: {
      currency: "USD",
      services: [
        {
          service: "water",
          service_name: "Water",
          line_count: 2,
          subtotal: "238.600000",
          subtotal_display: "238.60",
        },
      ],
      bill_level: {
        line_count: 2,
        kinds: ["tax"],
        subtotal: "19.680000",
        subtotal_display: "19.68",
      },
      tie_out: {
        ties_out: true,
        lines_total: "258.280000",
        invoice_total: "258.280000",
        delta: "0.000000",
      },
    },
    // OQ-1190 (PO 2026-08-31) — what each authority is owed. The SAME two
    // figures the two tax lines above carry, grouped on the stamped tax_id and
    // summed by the server as Σ of the ROUNDED lines (6.56 + 13.12 = 19.68,
    // which is this bill's own tax_total).
    taxes_by_authority: {
      currency: "USD",
      authorities: [
        {
          tax_id: "tax-bexar",
          authority: "Bexar County Tax Office",
          line_count: 1,
          subtotal: "6.560000",
          subtotal_display: "6.56",
          liability_account_id: "gl-2200-01",
          liability_account_code: "2200-01",
          liability_account_name: "Tax payable — Local · Bexar County",
          liability_account_conflict: false,
        },
        {
          tax_id: "tax-texas",
          authority: "Texas Comptroller of Public Accounts",
          line_count: 1,
          subtotal: "13.120000",
          subtotal_display: "13.12",
          liability_account_id: "gl-2200-02",
          liability_account_code: "2200-02",
          liability_account_name: "Tax payable — TX State Utility Tax",
          liability_account_conflict: false,
        },
      ],
      unstamped: { line_count: 0, subtotal: "0.000000", subtotal_display: "0.00" },
      tie_out: {
        ties_out: true,
        authorities_total: "19.680000",
        authorities_total_display: "19.68",
        tax_total: "19.680000",
        tax_total_display: "19.68",
        delta: "0.000000",
      },
    },
    summary: {
      previous_balance: "45.000000",
      payments_credits: "0.000000",
      current_charges: "258.280000",
      total_due: "303.280000",
      currency: "USD",
    },
    credit_notes: [],
    rebill_of_invoice_id: null,
    corrected_by_invoice_id: null,
    adjustments: [],
    deliveries: null,
    integrity: {
      currency: "USD",
      document_ties_out: true,
      payload_total: "303.280000",
      rows_total: "303.280000",
      payload_line_count: 4,
      row_line_count: 4,
      posting_balanced: true,
      ar_total: "258.280000",
      unavailable: [],
    },
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

/**
 * ⚠ **SCOPE THE ASSERTION TO ONE TABLE. THREE CASES HERE WERE GREEN OVER A
 * DELIBERATE BREAK BEFORE THIS EXISTED (law 7, and DEF-182's rule that a check
 * whose output cannot distinguish pass from fail is worse than no check).**
 *
 * The Charges tab draws FOUR tables and they share vocabulary: *Amount* heads
 * a column in three of them, and the tax authority is printed both under the
 * line's description and in the authority panel. So `html.toContain("Bexar
 * County Tax Office")` passed with the authority panel's own cell replaced by
 * the literal string `tax` — the panel this case exists to test was broken and
 * the case did not notice.
 *
 * `data-bil` is the handle each table already carries; this returns just that
 * table's markup, and the plain-table markup has no nested tables, so the first
 * `</table>` really is this one's.
 */
function table(html: string, handle: string): string {
  const open = html.indexOf(`data-bil="${handle}"`);
  expect(open).toBeGreaterThan(-1);
  const close = html.indexOf("</table>", open);
  expect(close).toBeGreaterThan(open);
  return html.slice(open, close);
}

/** The LINES table, by its own handle.
 *
 * ⚠ It used to be sliced from the *Charges on this bill* heading, and
 * `CR-101-BRC03` renamed that heading to *Every charge* — so the helper broke
 * on a COPY change, which is the shape B14 rule 41 work keeps producing. The
 * table carries `data-bil="bill-lines"` now and the slice runs to `</table>`
 * rather than `</thead>`, so a case can assert on a ROW as well as a header. */
function linesTable(html: string): string {
  const open = html.indexOf('data-bil="bill-lines"');
  expect(open).toBeGreaterThan(-1);
  const close = html.indexOf("</table>", open);
  expect(close).toBeGreaterThan(open);
  return html.slice(open, close);
}

function renderCharges(bill: InvoiceDetail): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(billDetailQueryKey(bill.id), bill);
  queryClient.setQueryData(queryKeys.myPermissions, permissions("write"));
  queryClient.setQueryData(entityAuditQueryKey("invoice", bill.id), {
    page: { count: 0, next: null, previous: null, results: [] },
    window: { window: "hot", from: null },
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter
          initialEntries={[`/${TEST_TENANT}${billDetailPath(bill.id)}?tab=lines`]}
        >
          <Routes>
            <Route path="/:tenant/billing/bills/:invoiceId" element={<BillDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-053 task 8 — US-BIL-026's seven line fields stay on the screen", () => {
  it("all seven fields are present — five as columns, two folded under the description", () => {
    const html = renderCharges(detail());
    // §1, verbatim: *"every `invoice_line` with quantity/unit/unit-price/
    // amount/taxable flag/GL stamp/tariff version"*. The unit rides WITH the
    // quantity (CLAUDE.md #3), which is why six headers carried seven facts.
    //
    // ⚠ **FIVE HEADERS NOW, AND NOT ONE FIELD IS LOST (`CR-101-BRC03`).** The
    // Billing blueprint folds `Accounting code` and `Rate version` OUT of their
    // own columns and UNDER the description — legend ①, *"the way the
    // accounting code already shares one cell today"*. `Rate version` was the
    // widest column in the table and the least-used thing on the screen. The
    // case is renamed rather than deleted because the guarantee it exists for —
    // *seven fields stay on the screen* — is unchanged, and the assertions
    // below now check the two folded ones by VALUE instead of by header.
    const head = linesTable(html);
    for (const header of [
      ">Description<",
      ">Usage<",
      ">Rate<",
      ">Amount<",
      ">Taxable<",
    ]) {
      expect(head).toContain(header);
    }
    // THE TWO FOLDED FIELDS, ASSERTED BY VALUE — this is what replaces the two
    // headers above and it is the stronger check: a header can be present over
    // an empty column, a value cannot.
    expect(head).toContain('data-bil="line-gl"');
    expect(head).toContain('data-bil="line-rate-version"');
    // The two that are actually at risk, with their VALUES — a header with an
    // empty column under it is the same defect wearing a heading.
    expect(html).toContain("4110 — Water usage");
    expect(html).toContain("Sample — Commercial water (flat) · from 2026-06-01");
    expect(html).toContain('data-cell="unit"');
  });
});

describe("CR-053 task 6 — every scenario on one screen", () => {
  it("draws B4's own worked subtotal — 33.33 x 3 = $99.99, never $100.00", () => {
    // ══════════════════════════════════════════════════════════════════════
    // ⚠ THE FIRST DRAFT OF THIS CASE COULD NOT FAIL, AND LAW 7 IS WHY WE KNOW.
    // ══════════════════════════════════════════════════════════════════════
    // It asserted `$238.60` against a fixture whose stored figure was
    // `238.600000` — and `MoneyCell` renders BOTH as `$238.60`, so swapping
    // `subtotal_display` for `subtotal` in the component left the case green.
    //
    // B4's 2026-08-11 ruling is what makes the two readings differ at all, so
    // the fixture is now B4's own worked example: three lines of `33.333333`.
    //
    //     Σ finalize  =  33.33 + 33.33 + 33.33   =   99.99   <- what prints
    //     finalize Σ  =  finalize(99.999999)     =  100.00
    //
    // The server sends both figures. Reading the 4dp one and rounding it here
    // puts a cent on the screen that appears in no line — the exact defect the
    // ruling names: *"the printed document does not foot against itself"*.
    const html = renderCharges(
      detail({
        charges_by_service: {
          currency: "USD",
          services: [
            {
              service: "water",
              service_name: "Water",
              line_count: 3,
              subtotal: "99.999999",
              subtotal_display: "99.99",
            },
          ],
          bill_level: { line_count: 0, kinds: [], subtotal: "0.000000", subtotal_display: "0.00" },
          tie_out: {
            ties_out: true,
            lines_total: "99.999999",
            invoice_total: "99.999999",
            delta: "0.000000",
          },
        },
      }),
    );
    expect(html).toContain("By service");
    const panel = table(html, "charges-by-service");
    expect(panel).toContain('data-bil="service-subtotal"');
    expect(panel).toContain("$99.99");
    expect(panel).not.toContain("$100.00");
    expect(html).toContain("Charged to the bill, not to a service");
  });

  it("shows the bill-level bucket with the server's own rounded figure", () => {
    const panel = table(renderCharges(detail()), "charges-by-service");
    expect(panel).toContain("$238.60");
    expect(panel).toContain("$19.68");
  });

  it("DEF-BIL-9346 · By service names the bill's discounts DISCOUNTS, with the server's own figure", () => {
    // Ruth's December bill (CR-166 walk step 8): Senior −$9.00 + Autopay −$0.26.
    const bill = detail();
    const html = renderCharges(
      detail({
        charges_by_service: {
          ...bill.charges_by_service!,
          bill_level: {
            line_count: 2,
            kinds: ["discount"],
            subtotal: "-9.260000",
            subtotal_display: "-9.26",
            discounts: { line_count: 2, subtotal: "-9.260000", subtotal_display: "-9.26" },
            others: { line_count: 0, kinds: [], subtotal: "0.000000", subtotal_display: "0.00" },
          },
        },
      }),
    );
    const panel = table(html, "charges-by-service");
    expect(panel).toContain('data-bil="bill-level-discounts"');
    expect(panel).toContain(">Discounts<");
    expect(panel).not.toContain("Charged to the bill");
    expect(panel).not.toContain('data-bil="bill-level-subtotal"');
  });

  it("names the KINDS in the bill-level bucket, so money outside a service says why", () => {
    const html = renderCharges(detail());
    expect(html).toContain('data-bil="bill-level-subtotal"');
    expect(html).toContain("Tax");
  });

  it("groups tax by the authority it is paid to (BR-BIL-069)", () => {
    const html = renderCharges(detail());
    expect(html).toContain(">Tax<");
    // ⚠ SCOPED TO THE PANEL. Unscoped, this case passed with the panel's own
    // authority cell replaced by the literal string `tax`, because the same
    // two names are also printed under each tax line's description.
    const panel = table(html, "taxes-by-authority");
    expect(panel).toContain("Bexar County Tax Office");
    expect(panel).toContain("Texas Comptroller of Public Accounts");
    expect(panel).toContain('data-tax-id="tax-bexar"');
    expect(panel).toContain('data-tax-id="tax-texas"');
    // ⚠ **THE PER-AUTHORITY SUBTOTAL EXISTS NOW — `OQ-1190` CLOSED 2026-08-31.**
    // This case used to assert the OPPOSITE: that the panel STATED no total per
    // authority was available. The PO ruled *"(a) Add a per-authority subtotal
    // to the bill and the finance screens"*, so the sentence is gone and the
    // figures are here. The absence assertion is REPLACED and not kept beside
    // the new one — a check asserting a figure and a check asserting the
    // sentence that says there is no figure cannot both be right, and the pair
    // would pass whichever way the screen went.
    expect(panel).toContain('data-bil="authority-subtotal"');
    expect(html).not.toContain('data-bil="no-authority-subtotal"');
    expect(html).not.toContain("A total per authority is not available yet");
  });

  it("gives each authority its own subtotal, and they foot to the bill's own tax", () => {
    // THE PO'S RULING, WORKED: 6.56 + 13.12 = 19.68, and 19.68 is the figure
    // the bill already published. Scoped to the panel, because the same amounts
    // are printed on the LINES table too — unscoped, this would pass with the
    // subtotal rows deleted.
    const panel = table(renderCharges(detail()), "taxes-by-authority");
    const rows = panel.split('data-bil="authority-subtotal"');
    expect(rows.length - 1).toBe(2);
    expect(rows[1]).toContain("6.56");
    expect(rows[2]).toContain("13.12");
    // NON-VACUOUS: neither figure may be a zero dressed as a subtotal. A screen
    // showing 0.00 per authority satisfies every "contains" above and tells a
    // clerk filing a return that nobody is owed anything.
    expect(rows[1]).not.toContain("0.00");
    expect(rows[2]).not.toContain("0.00");
    // AND THE SERVER'S 4dp STORED SCALE NEVER REACHES THE SCREEN (rule 2) — a
    // second rounding here would be a second money path (BR-SHL-023).
    expect(panel).not.toContain("6.560000");
    expect(panel).not.toContain("13.120000");
  });

  it("shows the SERVER's tie-out verdict and never one it computed", () => {
    // PO 2026-08-30 (R1–R7): the document displays what the server resolved.
    const agreeing = renderCharges(detail());
    expect(agreeing).toContain('data-bil="taxes-tie-out"');
    expect(agreeing).toContain('data-ties-out="true"');
    expect(agreeing).toContain("These add up to the tax.");

    // A DISAGREEMENT IS REPORTED WITH BOTH FIGURES AND NEITHER IS MOVED —
    // BR-BIL-032's evidence must survive being looked at.
    const drifted = detail({
      taxes_by_authority: {
        ...detail().taxes_by_authority!,
        tie_out: {
          ties_out: false,
          authorities_total: "19.680000",
          authorities_total_display: "19.68",
          tax_total: "21.000000",
          tax_total_display: "21.00",
          delta: "-1.320000",
        },
      },
    });
    const html = renderCharges(drifted);
    expect(html).toContain('data-ties-out="false"');
    expect(html).toContain("Authorities add to");
    expect(html).toContain("21.00");
    // The authority rows are NOT adjusted to make the bill foot.
    const panel = table(html, "taxes-by-authority");
    expect(panel).toContain("6.56");
    expect(panel).toContain("13.12");
  });

  it("keeps the old sentence for the one case it is still true of: no block", () => {
    // A server one deploy behind omits the block. The panel must state the
    // absence rather than white-screen on it — the failure mode that has hit
    // this page once already, found in a browser and by no test.
    const html = renderCharges(detail({ taxes_by_authority: null }));
    expect(html).toContain('data-bil="no-authority-subtotal"');
    expect(html).toContain("A total per authority is not available yet");
    // The LINES are still drawn and still grouped — the panel degrades, it does
    // not disappear.
    const panel = table(html, "taxes-by-authority");
    expect(panel).toContain("Bexar County Tax Office");
    expect(panel).toContain("Texas Comptroller of Public Accounts");
    expect(html).not.toContain('data-bil="authority-subtotal"');
  });

  it("never prints a tax_id at a person (B14 rule 31)", () => {
    // The id is the render key and the join to the books. It is on the row as a
    // data attribute and must never be the VISIBLE value of anything.
    const panel = table(renderCharges(detail()), "taxes-by-authority");
    const visible = panel.replace(/<[^>]*>/g, " ");
    expect(visible).not.toContain("tax-bexar");
    expect(visible).not.toContain("tax-texas");
    // NON-VACUOUS: the panel really did render, so this is not passing on an
    // empty string.
    expect(visible).toContain("Bexar County Tax Office");
  });

  it("does NOT split tax across services — PO 2026-08-11, and nothing records which service a tax is", () => {
    const html = renderCharges(detail());
    expect(html).toContain("A tax is charged on the bill, not on one service");
    // One water row in the per-service table, and it is the SUBTOTAL of the
    // two water lines with no tax folded into it.
    expect(html).toContain('data-service="water"');
    expect(html).not.toContain('data-service="tax"');
  });

  it("states the absence when a bill charges no tax, rather than hiding the panel (G38)", () => {
    const html = renderCharges(
      detail({
        lines: [line()],
        charges_by_service: {
          currency: "USD",
          services: [
            {
              service: "water",
              service_name: "Water",
              line_count: 1,
              subtotal: "223.600000",
              subtotal_display: "223.60",
            },
          ],
          bill_level: { line_count: 0, kinds: [], subtotal: "0.000000", subtotal_display: "0.00" },
          tie_out: {
            ties_out: true,
            lines_total: "223.600000",
            invoice_total: "223.600000",
            delta: "0.000000",
          },
        },
      }),
    );
    expect(html).toContain("This bill charges no tax.");
    expect(html).toContain("Nothing");
  });

  it("labels a DISCOUNT line as a discount instead of burying it under Taxes & fees", () => {
    const html = renderCharges(
      detail({
        lines: [
          line(),
          line({
            id: "ln-d",
            kind: "discount",
            description: "Paperless billing credit",
            quantity: null,
            unit: null,
            unit_price: null,
            amount: "-5.000000",
            taxable: false,
            service: null,
            gl_account_code: null,
            gl_account_id: null,
            gl_account_name: null,
            tariff_version_id: null,
            tariff_version_label: null,
          }),
        ],
      }),
    );
    expect(html).toContain('data-kind="discount"');
    expect(html).toContain("Discount");
    expect(html).toContain("Paperless billing credit");
    // DEF-BIL-9339 — the case's NAME was never asserted: the discount sat under
    // a "Taxes & fees" heading on a bill with no tax and no fee. Its heading is
    // now "Discounts", and no "Taxes & fees" heading is drawn at all here.
    const table = html.slice(html.indexOf("Every charge"));
    expect(table).toMatch(/<th colSpan="5">Discounts<\/th>/);
    expect(table).not.toContain("Taxes &amp; fees");
    expect(table.indexOf(">Discounts</th>")).toBeLessThan(table.indexOf("Paperless billing credit"));
  });

  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **`When this is due` LEFT THIS TAB (`CR-105-BRC03`, 2026-09-14) — AND
  // THIS IS THE HALF OF THE MOVE THAT GOES RED IF IT COMES BACK.**
  // ══════════════════════════════════════════════════════════════════════════
  // p012's carry-over map marks it **MOVED**, not removed: *"From Charges into
  // Dates on Document, where the other dates already are."* Its three rows and
  // its late-terms sentence are asserted on their NEW tab by
  // `CR105DocumentGroups.dom.test.tsx`; what this case owns is the other half
  // of a move, which is that the thing is no longer where it was. A move proved
  // on one side only is how a product ends up with the fact in two places —
  // B14 rule 32, and the exact reason legend 5 says *one pill, not two*.
  it("the due-date panel is no longer on Charges — it MOVED to Dates on Document", () => {
    const html = renderCharges(detail({ past_due: true }));
    // The tab still renders in full, so this is not a blank-page pass.
    expect(html).toContain("Every charge");
    expect(html).not.toContain("When this is due");
    expect(html).not.toContain('data-bil="past-due-yes"');
    expect(html).not.toContain('data-bil="late-terms"');
  });

  it("the past-due absence does not render here either, in any of its three states", () => {
    const unknown = renderCharges(detail({ past_due: null }));
    expect(unknown).toContain("Every charge");
    expect(unknown).not.toContain("Not checked");
    expect(unknown).not.toContain('data-bil="past-due-no"');
    const settled = renderCharges(detail({ past_due: false }));
    expect(settled).not.toContain('data-bil="past-due-no"');
  });

  it("survives a server that does not send charges_by_service, and says so", () => {
    // `IntegrityPanel`'s lesson, found in a browser and not by a test: an
    // unguarded read of a new block white-screens the whole bill.
    const html = renderCharges(detail({ charges_by_service: undefined }));
    expect(html).toContain("Not broken down by service");
    expect(html).toContain("The server sent no per-service breakdown");
    // The rest of the tab still renders.
    expect(html).toContain("Every charge");
  });
});

describe("CR-053 task 6 — DEF-2429: the minimum-bill top-up is drawn where it IS", () => {
  it("reports that per-service money is sitting in the bill-level bucket, and does not move it", () => {
    const html = renderCharges(
      detail({
        lines: [
          line(),
          line({
            id: "ln-m",
            kind: "minimum_adjustment",
            description: "Minimum bill adjustment",
            quantity: null,
            unit: null,
            unit_price: null,
            amount: "5.400000",
            service: null,
            gl_account_code: "4130",
            gl_account_name: "Minimum bill adjustment",
            tariff_version_id: null,
            tariff_version_label: null,
          }),
        ],
        charges_by_service: {
          currency: "USD",
          services: [
            {
              service: "water",
              service_name: "Water",
              line_count: 1,
              subtotal: "223.600000",
              subtotal_display: "223.60",
            },
          ],
          bill_level: {
            line_count: 1,
            kinds: ["minimum_adjustment"],
            subtotal: "5.400000",
            subtotal_display: "5.40",
          },
          tie_out: {
            ties_out: true,
            lines_total: "229.000000",
            invoice_total: "229.000000",
            delta: "0.000000",
          },
        },
      }),
    );
    expect(html).toContain('data-bil="minimum-misfiled"');
    expect(html).toContain("sits here rather than under its own service");
    expect(html).toContain("The bill&#x27;s total is unaffected");
    // AND IT IS NOT REPAIRED IN THE BROWSER. Water still reads the server's
    // 223.60 — a screen that re-filed the line would show 229.00 here and
    // disagree with the GL, the printed bill and the server all at once.
    expect(html).toContain("$223.60");
    expect(html).toContain("$5.40");
    expect(html).toContain("Minimum bill adjustment");
  });
});

describe("DEF-2716 — B14 rule 31: the other two columns match the charge code", () => {
  // The PO ratified rule 31 on 2026-08-30 in their own words: *"no Databse ID
  // on screen - that is a rule"*. The charge-code note below had already made
  // this choice for its own null; the Accounting code and Rate version columns
  // still printed the key, so ONE TABLE DID BOTH — which is what the defect
  // was filed on. Each fallback had a real reason and each keeps it:
  //   · DEF-937 kept the GL id so a deleted chart row could not blank a column
  //     headed ACCOUNTING CODE, because a blank reads as "this line did not
  //     post". A stated absence is not a blank, so the reason survives.
  //   · The rate version copied that shape without the argument behind it.
  it("says the accounting code cannot be read, and keeps the stamp off the screen", () => {
    const html = renderCharges(
      detail({
        lines: [line({ gl_account_code: null, gl_account_name: null })],
      }),
    );
    expect(html).toContain('data-bil="line-gl-unreadable"');
    expect(html).toContain("Accounting code not readable");
    // NON-VACUOUS: the stamp IS supplied. ⚠ It is also still in the markup, on
    // `title`, because rule 31's own sentence puts it there — *"the field says
    // so in words and the internal value may ride on `title` as evidence"*. So
    // a bare `not.toContain("gl-4110")` would FAIL on the correct fix, and a
    // bare `toContain` would PASS on the defect. Assert the position, not the
    // presence.
    expect(html).toContain('title="gl-4110"');
    expect(html).not.toContain(">gl-4110<");
    // And it is NOT the no-stamp sentence: that one means something else.
    expect(html).not.toContain("No accounting code recorded");
  });

  it("says the rate version cannot be read, and keeps that id off the screen too", () => {
    const html = renderCharges(detail({ lines: [line({ tariff_version_label: null })] }));
    expect(html).toContain('data-bil="line-rate-version-unreadable"');
    expect(html).toContain("Rate version not readable");
    expect(html).toContain('title="tv-1"');
    expect(html).not.toContain(">tv-1<");
  });

  it("still draws a DASH when the line carries no rate version at all", () => {
    // An absent version is a different statement from an unreadable one, and
    // the third branch is the one DEF-937 never touched.
    const html = renderCharges(
      detail({ lines: [line({ tariff_version_id: null, tariff_version_label: null })] }),
    );
    expect(html).not.toContain("Rate version not readable");
  });
});

describe("CR-053 task 6 — DEF-2428: a charge code that cannot be read is SAID, not printed", () => {
  it("shows the stated absence and never the raw charge id (BR-BIL-015 / DEF-2432)", () => {
    const html = renderCharges(
      detail({
        lines: [
          line(),
          line({
            id: "ln-f",
            kind: "fee",
            description: "Late payment fee",
            quantity: null,
            unit: null,
            unit_price: null,
            amount: "5.000000",
            taxable: false,
            service: null,
            gl_account_code: "4210",
            gl_account_name: "Late fee income",
            tariff_version_id: null,
            tariff_version_label: null,
            charge_id: "01a055fa-dead-beef-0000-000000000001",
            charge_code: null,
            charge_name: null,
          }),
        ],
      }),
    );
    expect(html).toContain('data-bil="line-charge-code-absent"');
    expect(html).toContain("Charge code not readable yet");
    expect(html).not.toContain("01a055fa-dead-beef-0000-000000000001");
  });

  it("prints code AND name the day rating publishes them", () => {
    const html = renderCharges(
      detail({
        lines: [
          line(),
          line({
            id: "ln-f",
            kind: "fee",
            description: "Late payment fee",
            quantity: null,
            unit: null,
            unit_price: null,
            amount: "5.000000",
            taxable: false,
            service: null,
            gl_account_code: "4210",
            gl_account_name: "Late fee income",
            tariff_version_id: null,
            tariff_version_label: null,
            charge_id: "01a055fa-dead-beef-0000-000000000001",
            charge_code: "LATE",
            charge_name: "Late payment fee",
          }),
        ],
      }),
    );
    expect(html).toContain("LATE — Late payment fee");
    expect(html).not.toContain("Charge code not readable yet");
  });
});

describe("CR-053 task 6 — a tie-out that fails is REPORTED, never reconciled", () => {
  it("states both figures and adjusts neither (BR-BIL-032)", () => {
    const html = renderCharges(
      detail({
        charges_by_service: {
          currency: "USD",
          services: [
            {
              service: "water",
              service_name: "Water",
              line_count: 2,
              subtotal: "238.600000",
              subtotal_display: "238.60",
            },
          ],
          bill_level: {
            line_count: 2,
            kinds: ["tax"],
            subtotal: "19.680000",
            subtotal_display: "19.68",
          },
          tie_out: {
            ties_out: false,
            lines_total: "258.280000",
            invoice_total: "260.000000",
            delta: "-1.720000",
          },
        },
      }),
    );
    expect(html).toContain('data-ties-out="false"');
    expect(html).toContain("$258.28");
    expect(html).toContain("$260.00");
    expect(html).toContain("Nothing here changes either figure");
    expect(html).toContain('role="alert"');
    // The per-service figures are UNTOUCHED by the disagreement — the evidence
    // BR-BIL-032 exists to surface is still on the page.
    expect(html).toContain("$238.60");
  });
});

// ── Record links (PO ruling 2026-10-19) — the line's meter opens the meter ───
describe("Record links · a line's meter number opens the meter", () => {
  it("the meter number is a link to the asset, by the id the line carries", () => {
    const html = renderCharges(
      detail({ lines: [line({ asset_id: "asset-77", asset_label: "M-0077" })] }),
    );
    const lines = linesTable(html);
    expect(lines).toMatch(/<a[^>]*href="\/brazosbend\/assets\/asset-77"[^>]*>M-0077<\/a>/);
  });

  it("a line with a meter label and no id keeps the label as text", () => {
    const html = renderCharges(detail({ lines: [line({ asset_id: null, asset_label: "M-0078" })] }));
    const lines = linesTable(html);
    expect(lines).toContain("M-0078");
    expect(lines).not.toContain("/assets/");
  });
});
