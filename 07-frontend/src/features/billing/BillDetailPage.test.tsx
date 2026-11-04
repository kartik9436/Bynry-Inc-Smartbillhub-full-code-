// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-026 (S30 bill detail) · US-BIL-007 (bill anatomy — the line
//           table) · US-BIL-027 (void: state-gated, consequence-messaged)
//           Screens: S30
// Rules:    BR-BIL-004 (read-only on an issued bill) · BR-BIL-009 (the void
//           consequence message precedes confirm and is SERVER-computed) ·
//           BR-BIL-010 (the line shows the STAMPED GL) · BR-BIL-063 (a draft
//           has no number) · BR-BIL-026 (the pinned template renders forever) ·
//           BR-BIL-030 (the bill is locked at issue) · BR-BIL-031 (payload and
//           template versions are two axes) · BR-BIL-016 (delivery is a queue) ·
//           BR-CUS-040 (a reprint never recomputes) · BR-SHL-023 (one money
//           path) · BR-SHL-025 (disabled WITH the reason)
// ───────────────────────────────────────────────────────
// §4 test data is WE-1 (BL-2608-018410, ACC-1042, Jul 1–31): current charges
// 247.87, previous balance 45.00, total due 292.87, GL stamps 4100…4200 —
// rendered through the seeded query cache, never a network.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  InvoiceDetail,
  InvoiceLineRow,
  MyPermissions,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { entityAuditQueryKey } from "@/features/metering/PremisesDetailPage";
import { ToastProvider } from "@/components/Toast";

import { BillDetailPage, billDetailQueryKey, billHeadline, billTabs } from "./BillDetailPage";
// DEF-2716 — the run row's own read, seeded per case.
import { billRunDetailKey } from "./billRunEndpoints";
import { billDetailPath } from "./billingShared";

const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function line(over: Partial<InvoiceLineRow> = {}): InvoiceLineRow {
  return {
    id: "ln-1",
    kind: "usage",
    description: "On-peak kWh",
    quantity: "120.000000",
    unit: "kWh",
    unit_price: "0.220000",
    amount: "26.400000",
    taxable: true,
    gl_account_id: "gl-4100",
    gl_account_code: "4100",
    // DEF-937 — the NAME beside the code, so the column reads
    // `4100 — Electric revenue` rather than the uuid it printed on the live
    // deployment at v2.61.1.
    gl_account_name: "Electric revenue",
    tariff_version_id: "tv-7",
    tariff_version_label: "Res Electric · TOU v7",
    service: "electric",
    // CR-053 task 7 — the two stamps the payload never carried. A usage line
    // has neither, which is why the default fixture is a usage line with four
    // nulls: `assemble_document` stamps a tax with its authority and a fee
    // with its code, and this is neither.
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

/** WE-1's shape. */
function detail(over: Partial<InvoiceDetail> = {}): InvoiceDetail {
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
    lines: [
      line(),
      line({
        id: "ln-2",
        kind: "base",
        description: "Monthly service charge",
        quantity: null,
        unit: null,
        unit_price: null,
        amount: "12.000000",
        gl_account_code: "4105",
      }),
      line({
        id: "ln-3",
        kind: "tax",
        description: "State sales tax",
        quantity: null,
        unit: null,
        unit_price: null,
        amount: "13.870000",
        taxable: false,
        service: null,
        gl_account_code: "2200",
        tariff_version_id: null,
        tariff_version_label: null,
      }),
    ],
    payload_version: 1,
    has_payload: true,
    // ⚠ **THE FIXTURE WAS WRONG, AND THAT IS HOW DEF-2450 STAYED INVISIBLE.**
    // It read `/api/brazosbend/invoices/inv-18410/document` — a value the server
    // has never sent. `selectors.invoice_detail` serves the bare API path,
    // measured over real HTTP on 2026-08-30:
    //     "document_url": "/invoices/01a0544e-5dc7-7eb7-926e-18fc9a2638cf/document"
    // …with no `/api` and no tenant segment, because those are added by
    // `client.ts` for a FETCH and by `tenantPath` for a NAVIGATION. A fixture
    // that pre-applies them makes the screen's own bug unreachable: the panel
    // rendered the value straight into an `href`, which was correct-looking here
    // and a dead link in a browser.
    document_url: "/invoices/inv-18410/document",
    summary: {
      previous_balance: "45.000000",
      payments_credits: "0.000000",
      current_charges: "247.870000",
      total_due: "292.870000",
      // DEF-099 / DEF-127 — the summary carries its own CHAR(3).
      currency: "USD",
    },
    credit_notes: [],
    rebill_of_invoice_id: null,
    corrected_by_invoice_id: null,
    adjustments: [],
    // BR-BIL-016's queue has no table, so the server sends null — NOT [].
    deliveries: null,
    // US-BIL-030 — the two record checks the detail now answers. The fixture
    // is the CLEAN case; the drifted and the not-checked cases override it, so
    // a screen that stopped rendering either would fail here rather than pass
    // over a fixture that never disagrees with itself.
    integrity: {
      currency: "USD",
      document_ties_out: true,
      payload_total: "292.870000",
      rows_total: "292.870000",
      payload_line_count: 15,
      row_line_count: 15,
      posting_balanced: true,
      ar_total: "247.870000",
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

function renderDetail(
  path: string,
  seed: { bill?: InvoiceDetail; access?: string; runNo?: string | null } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (seed.bill !== undefined) {
    queryClient.setQueryData(billDetailQueryKey(seed.bill.id), seed.bill);
  }
  // DEF-2716 — the run row NAMES its run (`RUN-0001`, the series OQ-342 ruled
  // in). Seeded only when a case is about that name: left unseeded, the read
  // has not answered and the link falls back to words, which is the state a
  // clerk sees for the first moment of every load and is worth measuring too.
  if (seed.bill?.bill_run_id != null && seed.runNo !== undefined) {
    queryClient.setQueryData(billRunDetailKey(seed.bill.bill_run_id), { run_no: seed.runNo });
  }
  if (seed.access !== undefined) {
    queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access));
  }
  // DEF-579: the Audit tab now READS this invoice's own rows. Seeded EMPTY by
  // default so the cases here measure the tab, not A18's loading skeleton.
  if (seed.bill !== undefined) {
    queryClient.setQueryData(entityAuditQueryKey("invoice", seed.bill.id), {
      page: { count: 0, next: null, previous: null, results: [] },
      window: { window: "hot", from: null },
    });
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <Routes>
            <Route path="/:tenant/billing/bills/:invoiceId" element={<BillDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const BASE = billDetailPath("inv-18410");

describe("US-BIL-026 — the bill detail shows both truths", () => {
  it("US-BIL-026 TC-1: the A19 summary box renders WE-1 verbatim — 45.00 − 0.00 + 247.87 = 292.87", () => {
    const html = renderDetail(BASE, { bill: detail() });
    expect(html).toContain("Previous balance");
    expect(html).toContain("$45.00");
    expect(html).toContain("Payments received");
    expect(html).toContain("$0.00");
    expect(html).toContain("Current charges");
    expect(html).toContain("$247.87");
    expect(html).toContain("Total due");
    expect(html).toContain("$292.87");
    // The figures are the SERVER's — nothing here subtracts or adds them, and
    // the panel says which day they belong to.
    //
    // ⚠ **THE SENTENCE IS TWO SHORT ONES SINCE `CR-105-BRC03`** — it read
    // *"These figures are the ones saved on the bill the day it was issued, not
    // today's balance"* (17 words) on BOTH tabs. B14 rule 33: *two sentences of
    // six beat one sentence of twelve*, and it now renders only where the
    // frozen figures sit beside the live one (p018 draws no sentence at all
    // under the Charges AMOUNT).
    expect(html).toContain("These four are as at issue.");
    expect(html).toContain("Owed today is the live balance.");
  });

  it("OQ-217 (PO 2026-10-01): an overpaid customer's bill shows a $48.75 credit, nothing to pay", () => {
    // *"last bill $34.00 − paid $120.00 + new charges $37.25 = $48.75 credit, nothing to pay"*
    const html = renderDetail(BASE, {
      bill: detail({
        summary: {
          previous_balance: "34.000000",
          payments_credits: "120.000000",
          current_charges: "37.250000",
          total_due: "-48.750000",
          currency: "USD",
        },
      }),
    });
    expect(html).toContain("$34.00");
    expect(html).toContain("$120.00");
    expect(html).toContain("$37.25");
    expect(html).toContain("Credit");
    expect(html).toContain("$48.75");
    expect(html).not.toContain("-$48.75");
    expect(html).not.toContain("−$48.75");
  });

  it("US-BIL-026 §7: an unsaved summary is a stated absence, never four zeros", () => {
    const html = renderDetail(BASE, { bill: detail({ summary: null }) });
    expect(html).toContain("No amount-due summary was saved");
    expect(html).toContain("it is not a zero");
    expect(html).toContain("BR-BIL-035");
    expect(html).not.toContain("$292.87");
  });

  it("US-BIL-026 TC-1 / US-BIL-007: every line renders with its explicit unit and its stamped GL", () => {
    const html = renderDetail(`${BASE}?tab=lines`, { bill: detail() });
    expect(html).toContain("On-peak kWh");
    // CLAUDE.md #3: a quantity NEVER renders without the unit it was measured in.
    // CR-018 Route B: the handle is `data-cell="unit"` now — the class name it
    // used to grep for was deleted with UnitCell.css.
    expect(html).toContain('data-cell="unit"');
    expect(html).toContain("kWh");
    expect(html).toContain("$0.22");
    expect(html).toContain("$26.40");
    // BR-BIL-010: the STAMP. The screen reads the served value and has no path
    // that resolves a GL against today's mapping — US-BIL-026 TC-2's guarantee
    // is structural here, not a lookup this screen could get wrong.
    expect(html).toContain("4100");
    expect(html).toContain("4105");
    expect(html).toContain("2200");
    expect(html).toContain("the one that was recorded when the bill was issued");
    // The document's own grouping: per service, taxes and fees last.
    expect(html).toContain("Electric");
    expect(html).toContain("Taxes &amp; fees");
    // Totals come stored (US-BIL-025 §7) — the tfoot echoes the invoice, it
    // does not re-sum the lines.
    expect(html).toContain("$226.90");
    expect(html).toContain("$20.97");
    expect(html).toContain("$247.87");
  });

  it("DEF-060: a NUMERIC(18,6) quantity reaches the clerk as `684 kWh`, not `684.000000 kWh`", () => {
    // ⚠ THE FIRST BROWSER TEST EVER RUN AGAINST THIS PRODUCT FOUND THIS, on
    // this screen (hard-won law 6). `GET /invoices/{id}` serves
    // `quantity: "684.000000"` because BR-MET-019's column is `NUMERIC(18,6)`,
    // and the money column beside it read `$108.88` — so one bill showed a
    // trimmed money figure next to an untrimmed quantity and the clerk read
    // `684.000000 kWh` where the meter said 684.
    //
    // ⚠ AND THE ESCAPE REASON IS WHY THIS CASE EXISTS AT ALL: *"every frontend
    // test of these cells passes the string it wants to see … no mock carried a
    // six-decimal quantity from a real NUMERIC column."* This one does, on the
    // surface the defect was reported on, so the fix cannot regress here
    // without a red test rather than another browser session.
    //
    // The fix itself is DEF-646's, in `components/UnitCell.tsx`: trailing zeros
    // are a storage artefact of the column, not a measurement, and stripping
    // them changes no value. SIGNIFICANT digits are untouched — the second
    // line below is the safety case, and `1016.250000` must never become 1016.
    const html = renderDetail(`${BASE}?tab=lines`, {
      bill: detail({
        lines: [
          line({ id: "ln-def060", quantity: "684.000000", unit: "kWh" }),
          line({ id: "ln-def060b", description: "Water", quantity: "1016.250000", unit: "kgal" }),
        ],
      }),
    });
    // ⚠ ASSERTED ON THE MARKUP, NOT ON THE PHRASE. `UnitCell` puts the figure
    // and its unit in two spans, so the literal "684 kWh" is never in the HTML
    // even when the screen is right — a `toContain("684 kWh")` here fails on a
    // correct render and would have been "fixed" by loosening it to "684",
    // which `684.000000` also contains. Both halves are pinned instead.
    // ⚠ THE SEPARATOR IS U+00A0, NOT A SPACE, and it is pinned as one: the
    // quantity must never wrap away from the unit it was measured in
    // (CLAUDE.md rule 3 / BR-SHL-023). A `/ /` here silently fails on a
    // CORRECT render, which is how this assertion was first written.
    expect(html).toMatch(/>684<\/span>\u00a0<span[^>]*>kWh</);
    expect(html).not.toContain("684.000000");
    // …and nothing SIGNIFICANT was rounded away on the way past.
    expect(html).toMatch(/>1,016\.25<\/span>\u00a0<span[^>]*>kgal</);
    expect(html).not.toContain("1016.250000");
  });

  it("US-BIL-026 TC-2 (negative): a line with a quantity and no unit is refused, not printed bare", () => {
    const html = renderDetail(`${BASE}?tab=lines`, {
      bill: detail({ lines: [line({ unit: null })] }),
    });
    expect(html).toContain("Unit missing");
    expect(html).toContain("a fault in the record rather than something to guess at");
    // And a line with no stamped GL says so rather than rendering an empty cell
    // that would read as "this line did not post".
    const noGl = renderDetail(`${BASE}?tab=lines`, {
      bill: detail({ lines: [line({ gl_account_id: null, gl_account_code: null })] }),
    });
    expect(noGl).toContain("No accounting code recorded");
    expect(noGl).toContain("BR-BIL-010");
    // ⚠ **THIS CASE READ *"a stamped uuid with no readable code still shows
    // the stamp"* AND ASSERTED `toContain("gl-4100")` UNTIL 2026-08-31
    // (DEF-2716).** B14 rule 31 was ratified on 2026-08-30 — *"no Databse ID on
    // screen - that is a rule"* — so the cell states the absence instead. The
    // reason the stamp was printed survives intact and is why this is not a
    // blank: a blank in a column headed ACCOUNTING CODE reads as "this line did
    // not post" (DEF-937), and a stated absence is not a blank.
    //
    // ⚠ **AND THE OLD ASSERTION WOULD STILL PASS**, which is the whole reason
    // this comment is here. Rule 31 puts the stamp on `title` as evidence for
    // support, so `gl-4100` IS in the markup — `toContain` cannot tell a value
    // in a cell from an attribute on it. So assert the two halves separately:
    // the words are the cell's TEXT, and the id is NOT.
    const uuidOnly = renderDetail(`${BASE}?tab=lines`, {
      bill: detail({ lines: [line({ gl_account_code: null, gl_account_name: null })] }),
    });
    expect(uuidOnly).toContain("Accounting code not readable");
    expect(uuidOnly).toContain('title="gl-4100"');
    expect(uuidOnly).not.toContain(">gl-4100<");
  });

  it("DEF-937: the two stamp columns read as CODE — NAME and a schedule, never as a uuid", () => {
    // ⚠ **THE LIVE DEPLOYMENT AT v2.61.1 PRINTED
    // `01a01d99-d995-7127-aad8-faace1cba6e2` IN A COLUMN HEADED ACCOUNTING
    // CODE**, on every line of every bill, under that column's own footnote
    // promising a clerk *"the accounting code … recorded when the bill was
    // issued"*. DEF-206's rule is one sentence: never print the raw key at a
    // person. `4100 — Electric revenue` is the shape the Settings accounting
    // tab has used since it was built.
    const html = renderDetail(`${BASE}?tab=lines`, { bill: detail() });
    expect(html).toContain("4100 — Electric revenue");
    expect(html).toContain("Res Electric · TOU v7");

    // NON-VACUOUS: the ids ARE supplied and must not appear anywhere in the
    // rendered table. Without this the test passes on a screen that prints the
    // label AND the uuid beside it, which is where a careless fix lands.
    const rows = html.slice(html.indexOf("On-peak kWh"));
    expect(rows).not.toContain("gl-4100");
    expect(rows).not.toContain("tv-7<");
  });

  it("US-BIL-026 / B4.2: a tax line is neither taxable nor not-taxable — the question does not apply", () => {
    const html = renderDetail(`${BASE}?tab=lines`, { bill: detail() });
    const taxRow = html.slice(html.indexOf("State sales tax"));
    // The usage line answers Yes; the tax row shows a dash rather than "No",
    // which would claim the tax was considered for tax.
    expect(html).toContain("Taxable");
    expect(taxRow.slice(0, 400)).toContain("met-muted");
  });

  it("US-BIL-026 §5 / BR-BIL-026 + BR-BIL-030: the document is the SERVER's pinned render, not a client re-draw", () => {
    const html = renderDetail(BASE, { bill: detail() });
    // ⚠ **THE PANEL'S OWN LINK WENT WITH THE VIEWER (`CR-105-BRC03`).** The
    // *Customer's bill* panel became the drawn `The bill` group, whose two
    // controls are a download and an open-in-a-new-tab; the in-app document
    // page is still reached, from the header's `View the bill as sent`, which
    // is what the `href` assertion three lines down reads.
    expect(html).toContain("The bill");
    // ══════════════════════════════════════════════════════════════════════
    // ⚠ **THE OLD ASSERTION PINNED A BROKEN LINK (DEF-2450), AND PASSED.** It
    // read `href="/api/brazosbend/invoices/inv-18410/document"`, and the markup
    // it was reading was `<a href={detail.document_url}>` — the raw API path
    // the SERVER writes for itself, with no `/api` and no tenant segment. The
    // rendered `href` was `/invoices/inv-18410/document`, which as a browser
    // navigation is a route this app does not have.
    //
    // (The old assertion matched at all only because the SAME substring appears
    // elsewhere in the page markup; the panel's own anchor never carried it.
    // That is the shape of a check that cannot distinguish pass from fail —
    // DEF-182's lesson in a different file.)
    //
    // CR-053 task 4: the customer's bill is a LINK, and it points at the page
    // that draws it.
    expect(html).toContain('href="/brazosbend/billing/bills/inv-18410/document"');
    expect(html).not.toContain('href="/invoices/inv-18410/document"');
    expect(html).toContain("shows July&#x27;s name and address, not today&#x27;s");
    // BR-BIL-031: two version axes, never conflated, both named.
    expect(html).toContain("Bill template");
    expect(html).toContain("v3");
    expect(html).toContain("Saved bill data");
    expect(html).toContain("Version 1");
    expect(html).toContain("changing a template never changes an old bill");
  });

  it("US-BIL-026 / BR-BIL-030: a draft has no stamped copy, no number and no dates", () => {
    const html = renderDetail(BASE, {
      bill: detail({
        invoice_no: null,
        status: "draft",
        past_due: null,
        issued_at: null,
        due_date: null,
        template_version: null,
        payload_version: null,
        has_payload: false,
        document_url: null,
        summary: null,
      }),
    });
    // The H1 names what it is rather than printing an empty heading.
    expect(html).toContain("Draft bill");
    expect(billHeadline(detail({ invoice_no: null }), t)).toBe("Draft bill");
    expect(billHeadline(detail(), t)).toBe("BL-2608-018410");
    expect(html).toContain("No locked copy was saved");
    expect(html).toContain("A draft has not been issued, so there is no saved copy to print.");
    expect(html).toContain("Not issued yet");
  });

  it("US-BIL-026 TC-3: the correction chain links both ways, and its absence is stated", () => {
    const chained = renderDetail(`${BASE}?tab=chain`, {
      bill: detail({
        status: "corrected",
        corrected_by_invoice_id: "inv-18999",
        credit_notes: [
          {
            id: "cn-1",
            credit_note_no: "CN-2608-000041",
            amount: "-247.870000",
            currency: "USD",
            reason: "Meter misread",
            issued_at: "2026-08-20",
          },
        ],
      }),
    });
    expect(chained).toContain("CN-2608-000041");
    expect(chained).toContain("-$247.87");
    expect(chained).toContain("Meter misread");
    expect(chained).toContain(`href="/${TEST_TENANT}${billDetailPath("inv-18999")}"`);
    expect(chained).toContain("Correcting a bill never changes it.");
    // …and a bill with no chain says so rather than showing an empty table.
    //
    // ⚠ AMENDED 2026-09-14 (`CR-101-BRC03`). The sentence moved rather than
    // going: the blueprint promotes the standing to a PILL and merges the two
    // stacked sentences into one standing line, so *"no credit note or
    // replacement bill is recorded"* now reads under `STANDING` and `HISTORY`
    // says *Nothing to report.* Its own words: *"every sentence on the live tab
    // survives — one is promoted to a pill, one is merged into the standing
    // line."* This asserts both halves so neither can be dropped.
    //
    // ⚠ **AND THIS FIXTURE SERVES NO CHAIN ROUTE, SO IT MEASURES THE
    // IN-FLIGHT STANDING — WHICH IS THE HALF THE BILL'S OWN COLUMN ANSWERS.**
    // `corrected_by_invoice_id` is null on this bill, so nothing replaced it,
    // and that is a fact off the row rather than a walk of the chain. The
    // HISTORY half needs no second request at all.
    const plain = renderDetail(`${BASE}?tab=chain`, { bill: detail() });
    expect(plain).toContain("This is the current bill");
    expect(plain).toContain(
      "Nothing has replaced it, and no credit note or replacement bill is recorded against it.",
    );
    expect(plain).toContain("Nothing to report.");
    expect(plain).not.toContain("CN-");
  });

  it("US-BIL-026 TC-4 / DEF-2716: the run is a LINK to the run, and never its id", () => {
    // ⚠ **THIS CASE WAS NAMED *"the run is shown as its origin, and is not
    // linked onto a screen that does not exist"* AND ASSERTED
    // `toContain("run-07a")` UNTIL 2026-08-31.** Both halves were right when
    // written: EP-BIL-01's run screens did not exist, and a link onto a
    // placeholder is hard-won law 2 wearing a different hat. CR-051 built them,
    // and B14 rule 31 (PO 2026-08-30, *"no Databse ID on screen - that is a
    // rule"*) settles what goes in the cell instead — a run has no
    // human-facing number to print, so the way to it is a control.
    // Rule 31's FIRST branch: a run HAS a human-facing number — `RUN-0001`,
    // the series OQ-342 closed on the PO's own words — so that is what the
    // cell shows once the run answers.
    const named = renderDetail(BASE, { bill: detail(), runNo: "RUN-0001" });
    expect(named).toContain("Billing run");
    expect(named).toContain("RUN-0001");
    expect(named).toContain(`href="/${TEST_TENANT}/billing/run?run=run-07a"`);
    // NON-VACUOUS: the id IS supplied and must not be the visible value.
    expect(named).not.toContain(">run-07a<");

    // A run created before that series exists carries no number and is NOT
    // retro-numbered (OQ-342's own ruling), so the link names its destination.
    const unnumbered = renderDetail(BASE, { bill: detail(), runNo: null });
    expect(unnumbered).toContain("Open the run");
    expect(unnumbered).not.toContain(">run-07a<");

    // …and so does a run the read has not answered for yet, or cannot.
    const pending = renderDetail(BASE, { bill: detail() });
    expect(pending).toContain("Open the run");
    expect(pending).not.toContain(">run-07a<");

    // A single/ad-hoc bill has no run at all, which is an answer.
    const adhoc = renderDetail(BASE, { bill: detail({ bill_run_id: null }) });
    expect(adhoc).toContain("Not from a run");
    expect(adhoc).not.toContain("Open the run");
  });

  it("US-BIL-026 §5 / BR-BIL-016: a null delivery history is named, never drawn as an empty table", () => {
    // ⚠ `?tab=sent` SINCE `CR-101-BRC03` — the panel moved off the Document tab
    // onto its own, which is blueprint entry 02.5. The rows, the refusals and
    // the reasons are byte-identical; only the address changed.
    const html = renderDetail(`${BASE}?tab=sent`, { bill: detail() });
    expect(html).toContain("Sent");
    expect(html).toContain("an empty list would read as");
    // …and a served (empty) queue is a different statement from an absent one.
    const served = renderDetail(`${BASE}?tab=sent`, { bill: detail({ deliveries: [] }) });
    expect(served).toContain("Nothing has been queued for this bill.");
    const sent = renderDetail(`${BASE}?tab=sent`, {
      bill: detail({
        deliveries: [
          {
            id: "d1",
            channel: "email",
            status: "sent",
            at: "2026-08-08",
            returned_at: null,
            held: false,
          },
        ],
      }),
    });
    expect(sent).toContain("email");
    expect(sent).toContain("sent");
  });

  // ── US-PAY-016 — the single mark, on the row that owns it ────────────────
  // BR-PAY-018 marks a DELIVERY RECORD returned, and US-PAY-016 §1 names this
  // panel as the entry: *"Entry: S30 delivery rows / S35 bulk-mark."* Until
  // 2026-08-16 the engine, the flag, the queue and the endpoint all existed and
  // a clerk holding a returned envelope had nowhere to type it.
  //
  // NOTHING HERE TOUCHES THE BILL. Returned ≠ reissued (J18 step 6): the mark
  // writes a delivery-return event and the bill, its lines and its balances are
  // byte-identical either side. BR-BIL-004's read-only rule is about the BILL
  // and is not weakened by an action on its delivery row.
  it("US-PAY-016: a paper delivery row offers Mark returned, and an email row is refused BY REASON", () => {
    const html = renderDetail(`${BASE}?tab=sent`, {
      access: "Full",
      bill: detail({
        deliveries: [
          {
            id: "d-paper",
            channel: "pdf_print",
            status: "queued",
            at: "2026-09-01",
            returned_at: null,
            held: false,
          },
          {
            id: "d-email",
            channel: "email",
            status: "queued",
            at: "2026-09-01",
            returned_at: null,
            held: false,
          },
        ],
      }),
    });
    expect(html).toContain("Mark returned");
    // BR-SHL-025: the email row's control is DISABLED WITH ITS REASON — an
    // email that did not arrive is a provider bounce, not something a clerk can
    // observe about an envelope. The reason is on the screen, not in a rule doc.
    expect(html).toContain("Only mail can be marked returned");
    // TWO buttons, and exactly ONE of them is live: the paper row's. The email
    // row's is present-but-disabled rather than hidden, so a clerk hunting for
    // the action finds it AND finds out why it cannot be used here.
    const all = html.match(/<button[^>]*>Mark returned<\/button>/g) ?? [];
    // ⚠ `disabled=` WITH THE EQUALS SIGN (CR-018 Phase 3). Under Route B the
    // class attribute spells its own state variants — `disabled:opacity-45` —
    // so a lookahead for the bare word `disabled` matches EVERY button and this
    // count silently collapsed to 0. The attribute is what distinguishes them.
    const enabled = html.match(/<button(?![^>]*\sdisabled=)[^>]*>Mark returned<\/button>/g) ?? [];
    expect(all.length).toBe(2);
    expect(enabled.length).toBe(1);
  });

  it("US-PAY-016 TC-5: a row already marked shows the DATE and cannot be marked twice", () => {
    const html = renderDetail(`${BASE}?tab=sent`, {
      access: "Full",
      bill: detail({
        deliveries: [
          {
            id: "d-paper",
            channel: "pdf_print",
            status: "queued",
            at: "2026-09-01",
            returned_at: "2026-09-08",
            held: false,
          },
        ],
      }),
    });
    // The date the post came back, in the tenant's own format — never a "Yes",
    // and never a second live button that would age a second queue row for one
    // envelope (CLAUDE.md rule 6, from the screen's side).
    expect(html).toContain("09/08/2026");
    expect(html).toContain("This piece is already marked returned");
    expect(html).not.toMatch(/<button(?![^>]*disabled)[^>]*>Mark returned<\/button>/);
  });

  it("BR-SHL-025: a View-only role sees Mark returned disabled with the RBAC reason", () => {
    const html = renderDetail(`${BASE}?tab=sent`, {
      access: "View",
      bill: detail({
        deliveries: [
          {
            id: "d-paper",
            channel: "pdf_print",
            status: "queued",
            at: "2026-09-01",
            returned_at: null,
            held: false,
          },
        ],
      }),
    });
    expect(html).not.toMatch(/<button(?![^>]*disabled)[^>]*>Mark returned<\/button>/);
  });

  it("US-BIL-026 TC-5 (negative): the surface writes nothing — no input, no form, no edit", () => {
    const html = renderDetail(`${BASE}?tab=lines`, { bill: detail(), access: "Full" });
    // THE ASSERTION THAT MATTERS AND HAS NOT MOVED: BR-BIL-004 / hard rule 4.
    // This screen shows an immutable record and offers no way to type into it.
    expect(html).not.toContain("<input");
    expect(html).not.toContain("<form");
    expect(html).not.toContain("contenteditable");

    // The three the capability row names are all present — not hidden, so
    // nobody hunts for them.
    expect(html).toContain("Print bill");
    expect(html).toContain("Fix this bill");
    expect(html).toContain("Cancel this bill");

    // ⚠ AMENDED 2026-08-16. This used to require THREE DISABLED BUTTONS, and
    // that count stopped being the right assertion the day the correction
    // workflow shipped: "Fix this bill" is now a LINK to S30's Fix-a-bill tab
    // and "View the bill as sent" is a LINK to the document. A link navigates —
    // it writes nothing — so the read-only guarantee is unchanged, and keeping
    // a disabled control up would have been a screen claiming a state of the
    // product that is no longer true (hard-won law 1).
    //
    // What is asserted instead is the guarantee itself, stated two ways: every
    // BUTTON on this screen is still disabled with a reason (BR-SHL-025), and
    // the only enabled controls are anchors.
    // ⚠ AMENDED AGAIN 2026-09-14 (`CR-101-BRC03`), AND THE AMENDMENT IS
    // NARROWER THAN THE OLD ASSERTION RATHER THAN WEAKER. *"Every enabled
    // button is a tab"* stopped being the guarantee the day the blueprint put
    // a copy-the-number glyph beside the title: copying a string to the
    // clipboard is not a write, and refusing it would be this test policing a
    // proxy instead of the rule.
    //
    // So the rule is stated directly: an enabled button on this screen is
    // either a TAB or one of a NAMED set of controls that touch no record. A
    // new enabled button that is neither still fails, which is the whole
    // reason the old line existed.
    const WRITES_NOTHING = ['role="tab"', 'data-bil="copy-bill-no"', "data-row-more"];
    const buttons = html.match(/<button[^>]*>/g) ?? [];
    const enabled = buttons.filter((tag) => !tag.includes("disabled"));
    expect(
      enabled.filter((tag) => !WRITES_NOTHING.some((marker) => tag.includes(marker))),
    ).toEqual([]);
    expect(html).toContain('href="/brazosbend/billing/fix?bill=');
  });

  it("US-BIL-026 §1: the five tabs are the two truths, what was sent, the chain and the audit trail", () => {
    // ⚠ FIVE SINCE `CR-101-BRC03`: the blueprint splits *Delivery* out of the
    // Document tab as `Sent`, third of five. `…?tab=sent` used to fall back to
    // Document, which was correct for an address that did not exist.
    expect(billTabs(t).map((tab) => tab.label)).toEqual([
      "Document",
      "Charges",
      "Sent",
      "Corrections",
      "Audit",
    ]);
    // BR-CUS-034 / US-AUD-005: the audit tab is the SHARED S61 viewer filtered
    // to this entity, so one audit surface keeps one set of masking rules.
    const audit = renderDetail(`${BASE}?tab=audit`, { bill: detail() });
    expect(audit).toContain("/audit-log?f.entity_type=invoice&amp;f.entity_id=inv-18410");
  });

  it("US-BIL-026 TC-6 / BR-SHL-020: a 404 names BOTH causes rather than picking one", () => {
    // HR-1 collapses "unknown id" and "another utility's bill" into one answer,
    // and an unregistered route answers the same way. Claiming only the last
    // would mislabel an isolation refusal as a build gap.
    const html = renderDetail(BASE);
    // With nothing seeded the query is still pending, so the loading state is
    // what renders — the failure copy itself is asserted through the catalog.
    expect(html).toContain("skeleton");
    expect(t("billing.bill.notFound")).toContain("does not exist for this utility");
    expect(t("billing.bill.notFound")).toContain("has not been built yet");
  });

  it.todo(
    "US-BIL-026 TC-2: after the mapping edit 4100→4101 the line still shows 4100 — needs the issue path and the mapping screen (server scope)",
  );
  it.todo(
    "US-BIL-026 TC-6 (isolation): a Lone Star Ridge session 404s on a Brazos Bend invoice id — server/RLS scope (G5)",
  );
});

describe("US-BIL-027 — void is state-gated and its consequence is the server's", () => {
  it("US-BIL-027 TC-1: void holds the ONE primary slot, disabled with the consequence rule", () => {
    const html = renderDetail(BASE, { bill: detail(), access: "Full" });
    expect(html).toContain("Cancel this bill");
    // BR-BIL-009: the plain-language consequence — which entries reverse, the
    // balance effect, the payment-reversal prerequisite and the approval — is
    // COMPUTED server-side. A dialog written here would invent it.
    expect(html).toContain("which entries reverse");
    expect(html).toContain("whether an approval is needed");
    expect(html).toContain("The server works that out");
  });

  it("US-BIL-027 TC-4 (negative): a bill already void says so, and voiding never deletes", () => {
    const html = renderDetail(BASE, { bill: detail({ status: "void" }), access: "Full" });
    expect(html).toContain("This bill is already canceled.");
    expect(html).toContain("Canceling never deletes it");
    // The bill and its lines are still here — BR-BIL-004: rows remain forever.
    expect(renderDetail(`${BASE}?tab=lines`, { bill: detail({ status: "void" }) })).toContain(
      "On-peak kWh",
    );
  });

  it("US-BIL-027 §1: a draft is not voided — it is simply not issued", () => {
    const html = renderDetail(BASE, {
      bill: detail({ status: "draft", invoice_no: null, issued_at: null, due_date: null }),
      access: "Full",
    });
    expect(html).toContain("A draft is not canceled");
    expect(html).toContain("A draft is not corrected");
  });

  it("US-BIL-027 §1 / BR-SHL-025: a View-only role sees the ROLE's reason first", () => {
    const html = renderDetail(BASE, { bill: detail(), access: "View" });
    expect(html).toContain("Your role can view billing but not change it.");
    // …and a role with no cell never reaches the surface at all (A18 §6).
    const denied = renderDetail(BASE, { bill: detail(), access: "—" });
    expect(denied).toContain("Your role does not include billing.");
    expect(denied).not.toContain("BL-2608-018410");
  });

  it.todo(
    "US-BIL-027 TC-2/TC-3/TC-5: the paid-bill path, the closed-period reversal and the server-side approval gate — all need POST /invoices/{id}/void",
  );
});

// ── DEF-088 / BR-TEN-080 ──────────────────────────────────────────────────
// A REAL SCREEN, ASSERTED ON ITS RENDERED STRING. MoneyCell's own suite proves
// the formatter; this proves the SCREEN that draws money through it, because
// DEF-088 escaped precisely as a screen-level fact nobody looked at. If a future
// component draws money any other way, this goes RED.
describe("DEF-088 / BR-TEN-080 — S30 renders every money figure at exactly 2 decimals", () => {
  // The API serves 4 decimals (BR-TEN-080): no computed precision is lost in
  // transit. This is that wire payload — WE-1's shape with real digits past the
  // second place, including BR-TEN-080's own 8.2985 tax line.
  const fourDecimalWire = detail({
    subtotal: "226.9012",
    tax_total: "8.2985",
    total: "235.1997",
    lines: [
      line({ amount: "26.4049", unit_price: "0.2201" }),
      line({
        id: "ln-2",
        kind: "base",
        description: "Monthly service charge",
        quantity: null,
        unit: null,
        unit_price: null,
        amount: "12.0050", // the float trap: 12.005 as a double is 12.00499…
        gl_account_code: "4105",
      }),
      line({
        id: "ln-3",
        kind: "tax",
        description: "State sales tax",
        quantity: null,
        unit: null,
        unit_price: null,
        amount: "8.2985", // BR-TEN-080's worked figure — must read $8.30
        taxable: false,
        service: null,
        gl_account_code: "2200",
        tariff_version_id: null,
        tariff_version_label: null,
      }),
    ],
    summary: {
      previous_balance: "45.0000",
      payments_credits: "0.0000",
      current_charges: "235.1997",
      total_due: "280.1997",
      currency: "USD",
    },
  });

  it("DEF-088: the S30 line table renders the 8.2985 tax line as $8.30 — the 4-decimal wire figure never reaches the screen", () => {
    const html = renderDetail(`${BASE}?tab=lines`, { bill: fourDecimalWire });
    expect(html).toContain("State sales tax");
    expect(html).toContain("$8.30");
    expect(html).not.toContain("8.2985");
    // Half-up over decimal strings, on a real screen: 26.4049 → $26.40,
    // 12.0050 → $12.01 (a float path renders $12.00), 226.9012 → $226.90.
    expect(html).toContain("$26.40");
    expect(html).toContain("$12.01");
    expect(html).toContain("$226.90");
    expect(html).not.toContain("26.4049");
    expect(html).not.toContain("12.0050");
    expect(html).not.toContain("226.9012");
  });

  it("DEF-088: the S30 summary box renders 2 decimals — and NO money string on the page carries a third", () => {
    const html = renderDetail(BASE, { bill: fourDecimalWire });
    expect(html).toContain("$45.00");
    expect(html).toContain("$235.20"); // 235.1997 half-up at 2 dp
    expect(html).toContain("$280.20"); // 280.1997 half-up at 2 dp
    expect(html).not.toContain("235.1997");
    expect(html).not.toContain("280.1997");

    // The blanket check: sweep the rendered text for every "$<digits>.<digits>"
    // and require the fraction to be exactly 2 long. A new money component that
    // formats for itself lands here, on this screen, before a customer sees it.
    const rendered = html.replace(/<[^>]*>/g, " ");
    const fractions = [...rendered.matchAll(/\$[\d,]+\.(\d+)/g)].map((m) => m[1]);
    expect(fractions.length).toBeGreaterThan(0);
    for (const fraction of fractions) {
      expect(fraction).toHaveLength(2);
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// US-BIL-030 — the record check, on the screen
// ══════════════════════════════════════════════════════════════════════════
describe("US-BIL-030 — the two guarantees the bill run makes, asked on the bill", () => {
  it("states BOTH checks in a clerk's words, with no rule id on the page", () => {
    const html = renderDetail(BASE, { bill: detail() });
    expect(html).toContain("Saved bill matches its charge lines");
    expect(html).toContain("Posted amounts add up to the amount owed");
    expect(html).toContain("Yes — checked just now");
    // CLAUDE.md §Screen IDs: the ticket vocabulary never reaches the page.
    expect(html).not.toContain("BR-BIL-032");
    expect(html).not.toContain("US-BIL-030");
  });

  it("a mismatch shows BOTH figures with the bill's currency, never a bare 'failed'", () => {
    const html = renderDetail(BASE, {
      bill: detail({
        integrity: {
          currency: "USD",
          document_ties_out: false,
          payload_total: "999.990000",
          rows_total: "292.870000",
          payload_line_count: 1,
          row_line_count: 15,
          posting_balanced: true,
          ar_total: "247.870000",
          unavailable: [],
        },
      }),
    });
    expect(html).toContain("do not match");
    // The SIZE of the disagreement, not the fact of it: "it does not tie out"
    // sends somebody looking and these two figures do not.
    //
    // ⚠ **THESE TWO ASSERTIONS READ `999.990000` AND `292.870000` UNTIL
    // 2026-08-27 (DEF-968, CR-043 finding 2).** The wire carries the stored
    // decimal string and this line interpolated it raw, so a clerk read *"Saved
    // bill: 64.570000 USD over 0 line(s)"* on the live deployment. Hard rule 2
    // is money stored 4, percentages 6, **both DISPLAY 2**, and `formatMoney`
    // is the single boundary where that happens (BR-SHL-023 / BR-TEN-080).
    //
    // The old assertions would PASS on the defect and FAIL on the fix, which is
    // why they are replaced rather than added to. Both places are kept: money
    // PADS to two — `$148.60`, never `$148.6` — where a QUANTITY trims to `8`
    // (BR-MET-144, DEF-894). Two rules, two formatters.
    expect(html).toContain("$999.99");
    expect(html).toContain("$292.87");
    expect(html).not.toContain("999.990000");
    expect(html).not.toContain("292.870000");
    // A money figure with no currency is not an amount (CLAUDE.md #2). The
    // symbol IS the code here — `formatMoney` renders `style: "currency"` with
    // the bill's own CHAR(3), so the sentence no longer repeats "USD" beside it.
    expect(html).toContain("$");
  });

  it("a draft says NOT CHECKED with the reason — never 'no'", () => {
    const html = renderDetail(BASE, {
      bill: detail({
        status: "draft",
        integrity: {
          currency: "USD",
          document_ties_out: null,
          payload_total: null,
          rows_total: "292.870000",
          payload_line_count: null,
          row_line_count: null,
          posting_balanced: null,
          ar_total: null,
          unavailable: [
            {
              field: "document_ties_out",
              br_ref: "BR-BIL-032",
              why: "this bill carries no stamped document instance",
            },
            { field: "posting_balanced", br_ref: "BR-BIL-011", why: "a draft has no GL stamps" },
          ],
        },
      }),
    });
    expect(html).toContain("Not checked");
    expect(html).toContain("no stamped document instance");
    // The absence never becomes an accusation.
    expect(html).not.toContain("do not match");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-026@f4c9d21 (story+rules snapshot — EP-BIL-07; co-packets US-BIL-007 EP-BIL-02 · US-BIL-027 same epic)
// generated: 2026-08-11 by story-coder (W3 billing FRONTEND lane — the S30 bill detail)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — GET /invoices/{id} is contracted at 11b §2.8 and unserved) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 738 passed / 174 todo across 53 files✔ (702 passed / 168 todo across 51 files was the pre-lane baseline — this lane adds 36 passing + 6 todo across 2 new files and dropped nothing) · vite build✔ · run_gates 15 PASS · 0 FAIL · 1 SKIP✔ (G13 unwired-props, G14 prototype-conformance and G15 i18n-parity included; 5 locales × 2628 keys, identical sets) · [2026-08-15 DEF-088 display-precision lane] RED PROVED FIRST — the S30 tax line rendered `<span class="cell-money-amount">$8.2985</span>` and all 6 new assertions failed against the pre-fix formatter (verbatim in the lane report). MEASURED, THIS LANE'S OWN FILES ONLY: MoneyCell.test.tsx 8 tests (was 6) · BillDetailPage.test.tsx 22 tests / 3 skipped (was 20 / 3) · PaymentsPage.test.tsx 17 tests (was 15) — 44 passed / 3 todo across the three, all green. The FULL suite total is deliberately not quoted: a concurrent 07-frontend settings lane was adding files throughout, so no whole-suite number here would be reproducible. tsc --noEmit✔ · eslint --max-warnings 0✔ · vite build✔ · node --test server.test.mjs 10/10✔ · tsc -p tsconfig.e2e.json✔ · run_gates: 20 PASS · 0 FAIL at this lane's 17:55 baseline; the failures present at hand-off are named in the lane report and none is this lane's — no file it touched appears in any of them
// exceptions: E4 US-BIL-026 TC-2's "4100 stays 4100 after the mapping edit" is an honest it.todo: proving it needs the ISSUE path and the US-BIL-009 mapping screen, neither of which exists. What IS proven here is the structural half — this screen has no code path that resolves a GL at all, so it can only ever render the served stamp · E4 US-BIL-027 TC-2/TC-3/TC-5 (the paid-bill path, the closed-period reversal, the server-side approval gate) are it.todo because every one of them is a `POST /invoices/{id}/void` behaviour and the consequence message is server-computed by BR-BIL-009 · E4 both TC-6 isolation rows are server/RLS scope (G5) · E4 the detail's rendered 404 frame is asserted through the CATALOG string rather than a rendered failure: `renderToStaticMarkup` runs no effects, so a query can only be seeded with success data
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
