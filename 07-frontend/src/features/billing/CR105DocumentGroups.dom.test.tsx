// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-105-BRC03 — the bill detail's Document tab, RESTRUCTURED into
//           the seven groups the Billing blueprint draws (02.1, p015–p017 of
//           `05-prototype/04 Billing, As Built.pdf`, sha256 137a2a48…0971,
//           read AS IMAGES per B14 rule 42).
//           Screens: S30 · BIL-05 · `/:tenant/billing/bills/:invoiceId`
// Defects:  DEF-BIL-5244 (the header's two controls were built inverted, and a
//           comment naming six pages defended it) — CLOSED not-a-defect here.
// Rules:    B14 rule 37 (a drawn figure is an ILLUSTRATION — the annotation is
//           the specification) · B14 rule 32 (a stated absence is CLOSED by
//           default; one sentence per section) · B14 rule 33 (two sentences of
//           six beat one of twelve) · B14 rule 31 (no internal code on screen)
//           · BR-SHL-044 (one page header, exactly one primary) ·
//           BR-SHL-025 (a forbidden control is disabled WITH its reason) ·
//           BR-BIL-030 (the bill is locked at issue) · hard rule 3 (a quantity
//           always with its explicit unit) · hard-won law 7 (RED first)
// ───────────────────────────────────────────────────────
/**
 * THE ONE THING THIS SUITE EXISTS FOR:
 *
 *   **p011–p012's carry-over map is the acceptance test, and it is titled
 *   "Nothing on the bill detail is lost."**
 *
 * It does the arithmetic itself — 43 as-built elements become 51, as
 * 27 unchanged + 11 moved + 4 relabelled + 1 removed + 9 new — so an element it
 * marks MOVED that goes missing is a failed conversion, and the ONE it marks
 * REMOVED surviving is the same failure wearing the other face. Both directions
 * are asserted below, because a restructure proved in one direction only is how
 * a fact ends up in two places.
 *
 * ⚠ **WHAT THESE CASES CANNOT PROVE.** jsdom lays nothing out: group ORDER here
 * is DOM order, and DOM order is not what a person sees if something is
 * absolutely positioned or its container wraps. The widths, the rhythm and the
 * emphasis were walked in Chromium at 1440 and 1280 by
 * `10-scripts/cr105_bill_detail_walkthrough.mjs` (hard-won law 6). A green run
 * of this file is not evidence that the screen looks right.
 *
 * EVERY CASE HERE WAS PROVED RED IN A WORKTREE PINNED AT THE PRE-CHANGE TIP
 * BEFORE IT WAS TRUSTED GREEN. The verbatim failures are in the lane report.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  InvoiceDetail,
  InvoiceLineRow,
  MyPermissions,
  OpenBillPosition,
} from "@/api/endpoints";
import type { RenderedBillDocument } from "@/api/billingOpsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { entityAuditQueryKey } from "@/features/metering/PremisesDetailPage";
import { accountUsageKey } from "@/features/customers/AccountUsageTab";
import type { UsagePayload } from "@/features/customers/AccountUsageTab";

import { BillDetailPage, billDetailQueryKey } from "./BillDetailPage";
import { DEFAULT_BILL_LAYOUT, billDocumentKey } from "./BillDocumentPage";

const TENANT = "brazosbend";
const INVOICE = "inv-51050";
const ACCOUNT = "acc-51050";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

// Each case renders into the same jsdom document, so without this the previous
// case's screen is still mounted and `screen` finds both.
afterEach(cleanup);

function line(over: Partial<InvoiceLineRow> = {}): InvoiceLineRow {
  return {
    id: "ln-1",
    kind: "usage",
    description: "water usage tier 1 (0-5 kgal)",
    quantity: "5.000000",
    unit: "kgal",
    unit_price: "4.240000",
    amount: "21.200000",
    taxable: true,
    gl_account_id: "gl-1",
    gl_account_code: "4110",
    gl_account_name: "Water usage",
    tariff_version_id: "tv-1",
    tariff_version_label: "Residential water, from 2026-08-01",
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

function detail(over: Partial<InvoiceDetail> = {}): InvoiceDetail {
  return {
    id: INVOICE,
    invoice_no: "BL-2608-000043",
    bill_type: "cycle",
    status: "issued",
    past_due: false,
    account_id: ACCOUNT,
    account_no: "AC-2026-00003",
    customer_name: "Castillo, Clara",
    // The CODE. Rule 31's human-facing branch, and legend 4 keeps it on Origin.
    cycle_label: "CY-007",
    // The NAME. New on the payload with this change, and what the header says.
    cycle_name: "Silver Creek — monthly",
    bill_run_id: "run-2",
    service_date: "2026-07-31",
    period_start: "2026-07-01",
    period_end: "2026-07-31",
    issued_at: "2026-08-02",
    due_date: "2026-08-22",
    subtotal: "246.520000",
    tax_total: "4.930000",
    total: "251.450000",
    currency: "USD",
    template_version: 1,
    payload_version: 1,
    has_payload: true,
    document_url: `/invoices/${INVOICE}/document`,
    lines: [
      line(),
      line({ id: "ln-2", description: "water usage tier 2", quantity: "14.000000" }),
      line({
        id: "ln-3",
        kind: "base",
        description: "water base charge",
        quantity: null,
        unit: null,
        unit_price: null,
        amount: "8.000000",
      }),
    ],
    summary: {
      currency: "USD",
      previous_balance: "0.000000",
      payments_credits: "0.000000",
      current_charges: "251.450000",
      total_due: "251.450000",
    },
    charges_by_service: {
      currency: "USD",
      services: [
        {
          service: "water",
          service_name: "Water",
          line_count: 3,
          subtotal: "246.520000",
          subtotal_display: "246.52",
        },
      ],
      bill_level: {
        line_count: 1,
        kinds: ["tax"],
        subtotal: "4.930000",
        subtotal_display: "4.93",
      },
      tie_out: {
        ties_out: true,
        lines_total: "251.450000",
        invoice_total: "251.450000",
        delta: "0.000000",
      },
    },
    taxes_by_authority: null,
    credit_notes: [],
    rebill_of_invoice_id: null,
    corrected_by_invoice_id: null,
    adjustments: [],
    deliveries: null,
    integrity: {
      currency: "USD",
      document_ties_out: true,
      payload_total: "251.450000",
      rows_total: "251.450000",
      payload_line_count: 4,
      row_line_count: 4,
      posting_balanced: true,
      ar_total: "251.450000",
      unavailable: [],
    },
    ...over,
  };
}

function rendered(over: Partial<RenderedBillDocument> = {}): RenderedBillDocument {
  return {
    invoice_id: INVOICE,
    invoice_no: "BL-2608-000043",
    template_id: "tpl-1",
    template_version: 1,
    payload_version: 1,
    layout_source: "platform-layout-classic-letter-v1",
    layout: DEFAULT_BILL_LAYOUT,
    currency: "USD",
    content_type: "text/html; charset=utf-8",
    body: "<article>bill</article>",
    pdf_content_type: "application/pdf",
    pdf_page_count: 2,
    pdf_url: `/invoices/${INVOICE}/document.pdf`,
    masthead: [],
    meta: [],
    services: [],
    groups: [],
    summary: [],
    remarks: [],
    usage: [],
    footer: [],
    stub: [],
    // The SERVER's own words for why the Usage table's READ column cannot be
    // filled. Copied verbatim from a live `GET /invoices/{id}/document`.
    absent: [
      {
        field: "meter_no · prior_read · current_read",
        why: "stage 6 keeps only whether the service was measured",
        br_ref: "A19 §1.4",
      },
    ] as RenderedBillDocument["absent"],
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

function usage(over: Partial<UsagePayload> = {}): UsagePayload {
  const water = {
    id: "svc-w",
    code: "water",
    name: "Water",
  };
  return {
    account_id: ACCOUNT,
    window: { months: 12, from: "2025-10", to: "2026-09", options: [12, 24] },
    services: [water],
    series: [
      {
        service: water,
        unit: "kgal",
        unit_absence: null,
        points: [],
        months_present: 3,
        months_absent: 9,
        metrics: {
          avg_per_month: {
            value: "17.400000",
            display: "17.4",
            unit: "kgal",
            absent_reason: null,
            description: "last_12_months",
            months_counted: 3,
            months_absent: 9,
          },
          peak: { value: null, display: null, unit: null, absent_reason: null },
          low: { value: null, display: null, unit: null, absent_reason: null },
          yoy: { value: null, display: null, unit: null, absent_reason: null },
        },
      },
    ],
    water_avg: { value: "17.400000", display: "17.4", unit: "kgal", absent_reason: null },
    rule_ref: "BR-MET-106",
    ...over,
  };
}

function openBills(over: Partial<OpenBillPosition> = {}): OpenBillPosition {
  return {
    account_id: ACCOUNT,
    account_no: "AC-2026-00003",
    currency: "USD",
    bills: [],
    total_open: "300.400000",
    bill_count: 1,
    problems: [],
    ...over,
  };
}

function permissions(): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: "reads_billing_runs", label: "Reads & Billing runs", access: "Full" }],
  };
}

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN.** A bare `MemoryRouter` with no
 * `/:tenant/...` route leaves `useParams().tenant` undefined, so every address
 * the page builds comes out `//billing/...` — a protocol-relative URL to
 * another host that reads as a perfectly good string to `toContain`. That is
 * hard-won law 2's fixture clause and it is why the route is declared here.
 */
function mount(
  seed: {
    bill?: InvoiceDetail;
    document?: RenderedBillDocument | null;
    usage?: UsagePayload | null;
    open?: OpenBillPosition | null;
    tab?: string;
  } = {},
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const bill = seed.bill ?? detail();
  queryClient.setQueryData(billDetailQueryKey(bill.id), bill);
  queryClient.setQueryData(queryKeys.myPermissions, permissions());
  queryClient.setQueryData(entityAuditQueryKey("invoice", bill.id), {
    page: { count: 0, next: null, previous: null, results: [] },
    window: { window: "hot", from: null },
  });
  if (seed.document !== null) {
    queryClient.setQueryData(billDocumentKey(bill.id), seed.document ?? rendered());
  }
  if (seed.usage !== null) {
    queryClient.setQueryData(accountUsageKey(bill.account_id, 12), seed.usage ?? usage());
  }
  if (seed.open !== null) {
    queryClient.setQueryData(["accounts", "open-bills", bill.account_id], seed.open ?? openBills());
  }
  const suffix = seed.tab === undefined ? "" : `?tab=${seed.tab}`;
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/billing/bills/${bill.id}${suffix}`]}>
          <Routes>
            <Route path="/:tenant/billing/bills/:invoiceId" element={<BillDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  ).container;
}

// ══════════════════════════════════════════════════════════════════════════
// THE ONE REMOVED ELEMENT, AND ITS RULING
// ══════════════════════════════════════════════════════════════════════════

describe("CR-105 · the embedded viewer is the only thing removed, and it is removed", () => {
  it("no frame is rendered on a bill that HAS a printable page", () => {
    const container = mount();
    // Positive anchor first: the tab really rendered. Without it every
    // `not.toContain` below passes on a blank page — law 7's false-pass shape.
    expect(screen.getByText(t("billing.bill.panel.theBill"))).toBeTruthy();
    expect(container.querySelectorAll("iframe")).toHaveLength(0);
    expect(container.querySelector('[data-bil="printable-page"]')).toBeNull();
  });

  it("a download control and an open-in-a-new-tab control replace it, at the same URL", () => {
    const container = mount();
    const actions = container.querySelector('[data-bil="the-bill-actions"]');
    expect(actions).not.toBeNull();
    const anchors = [...(actions?.querySelectorAll("a") ?? [])];
    expect(anchors).toHaveLength(2);
    const href = `/api/${TENANT}/invoices/${INVOICE}/document.pdf`;
    expect(anchors[0].getAttribute("href")).toBe(href);
    expect(anchors[0].hasAttribute("download")).toBe(true);
    expect(anchors[1].getAttribute("href")).toBe(href);
    expect(anchors[1].getAttribute("target")).toBe("_blank");
    // B14 rule 4 — `↓` downloads, `↗` leaves the product, and the drawing
    // carries both glyphs.
    expect(anchors[0].textContent).toContain("↓");
    expect(anchors[1].textContent).toContain("↗");
  });

  it("the two facts about the saved copy are STATED, not inferred from a rendered page", () => {
    mount();
    // The page count comes off the SERVER's render; two pages is the fixture's.
    expect(screen.getByText(t("billing.bill.savedCopyPages", { count: 2 }))).toBeTruthy();
    expect(screen.getByText(t("billing.bill.field.savedCopy"))).toBeTruthy();
    expect(screen.getByText(t("billing.bill.field.template"))).toBeTruthy();
  });

  it("a bill with no saved copy refuses BOTH controls with the same reason", () => {
    const container = mount({ bill: detail({ has_payload: false, document_url: null }), document: null });
    const actions = container.querySelector('[data-bil="the-bill-actions"]');
    expect(actions?.querySelectorAll("a")).toHaveLength(0);
    const buttons = [...(actions?.querySelectorAll("button") ?? [])];
    expect(buttons).toHaveLength(2);
    for (const button of buttons) {
      expect(button.hasAttribute("disabled")).toBe(true);
      expect(button.getAttribute("title")).toBe(t("billing.bill.action.reprintNoDocument"));
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-BIL-5244 — THE ANNOTATION DECIDES EMPHASIS, NOT THE BOX
// ══════════════════════════════════════════════════════════════════════════

describe("CR-105 · the header's emphasis is legend 6's, and it was built inverted", () => {
  it("`View the bill as sent` is the FILLED primary and sits leftmost", () => {
    const container = mount();
    const row = container.querySelector(".page-header-actions");
    expect(row).not.toBeNull();
    const controls = [...(row?.querySelectorAll("a,button") ?? [])];
    // ⚠ Read the RENDERED variant attribute, never the prop: a prop assertion
    // would have been green on the inverted day (B14's own amendment records
    // exactly that trap for the danger tier).
    expect(controls[0].textContent).toContain(t("billing.bill.action.viewDocument"));
    expect(controls[0].getAttribute("data-variant")).toBe("primary");
  });

  it("`Fix this bill` is the SECONDARY, and it is still a live link", () => {
    const container = mount();
    const row = container.querySelector(".page-header-actions");
    const controls = [...(row?.querySelectorAll("a,button") ?? [])];
    const fix = controls.find((el) => el.textContent?.includes(t("billing.bill.action.correct")));
    expect(fix).toBeTruthy();
    expect(fix?.getAttribute("data-variant")).toBe("secondary");
    expect(fix?.getAttribute("href")).toBe(`/${TENANT}/billing/fix?bill=${INVOICE}`);
  });

  it("exactly ONE primary on the header, which is BR-SHL-044", () => {
    const container = mount();
    const row = container.querySelector(".page-header-actions");
    const primaries = [...(row?.querySelectorAll('[data-variant="primary"]') ?? [])];
    expect(primaries).toHaveLength(1);
  });

  it("and the primary does not VANISH on a bill with no saved copy — it refuses", () => {
    // p014's own finding: *"Print disables with a reason; View vanishes. A
    // clerk cannot learn one rule from the pair."* Both refuse now.
    const container = mount({ bill: detail({ has_payload: false, document_url: null }), document: null });
    const row = container.querySelector(".page-header-actions");
    const primaries = [...(row?.querySelectorAll('[data-variant="primary"]') ?? [])];
    expect(primaries).toHaveLength(1);
    expect(primaries[0].textContent).toContain(t("billing.bill.action.viewDocument"));
    expect(primaries[0].hasAttribute("disabled")).toBe(true);
  });

  it("Print bill and Cancel this bill are in the `…` overflow, and Cancel keeps its reason", () => {
    const container = mount();
    expect(container.querySelector('[data-testid="bil-print-bill"]')).not.toBeNull();
    const cancel = container.querySelector('[data-testid="bil-cancel-bill"]');
    expect(cancel).not.toBeNull();
    expect(cancel?.getAttribute("title")).toBeTruthy();
  });

  // DEF-BIL-10067 (after-walk 2026-10-12, item c) — a ONE-TIME DRAFT decides
  // with its own Cancel draft button (DEF-BIL-10068), so the old disabled
  // "Cancel this bill" with *"A draft is not canceled — it is simply not
  // issued."* beside it contradicted the button next to it.
  it("a one-time draft has Cancel draft and NOT the old disabled Cancel this bill", () => {
    const container = mount({
      bill: detail({ status: "draft", one_time: true, issued_at: null, document_url: null }),
    });
    expect(screen.getAllByText(t("billing.bill.action.cancelDraft")).length).toBeGreaterThan(0);
    expect(container.querySelector('[data-testid="bil-print-bill"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="bil-cancel-bill"]')).toBeNull();
  });

  it("a cycle draft keeps the old item and its reason", () => {
    const container = mount({ bill: detail({ status: "draft", issued_at: null, document_url: null }) });
    expect(container.querySelector('[data-testid="bil-cancel-bill"]')?.getAttribute("title")).toBe(
      t("billing.bill.action.voidDraft"),
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE SEVEN GROUPS, IN THE DRAWN ORDER
// ══════════════════════════════════════════════════════════════════════════

describe("CR-105 · seven groups, one word each, in the order a clerk asks them", () => {
  it("Amount → Breakdown → Usage → Dates → The bill → Origin → Record", () => {
    const container = mount();
    const text = container.textContent ?? "";
    const at = [
      t("billing.bill.panel.summary"),
      t("billing.bill.panel.breakdown"),
      t("billing.bill.panel.usage"),
      t("billing.bill.panel.dates"),
      t("billing.bill.panel.theBill"),
      t("billing.bill.panel.originShort"),
      t("billing.bill.panel.record"),
    ].map((heading) => text.indexOf(heading));
    expect(at.every((i) => i >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
  });

  it("Origin and Record are `<details>` CLOSED by default — B14 rule 32", () => {
    const container = mount();
    for (const id of ["origin", "record"]) {
      const group = container.querySelector(`details[data-bil="group-${id}"]`);
      expect(group).not.toBeNull();
      expect((group as HTMLDetailsElement).open).toBe(false);
    }
  });

  it("the cycle's ID stays under Origin while the header says its NAME — legend 4", () => {
    const container = mount();
    const origin = container.querySelector('details[data-bil="group-origin"]');
    expect(origin?.textContent).toContain("CY-007");
    const header = container.querySelector('[data-bil="money-line"]');
    expect(header?.textContent).toContain("Silver Creek — monthly");
    expect(header?.textContent).not.toContain("CY-007");
  });

  it("a server that sends no cycle_name falls back to the code, never to nothing", () => {
    const container = mount({ bill: detail({ cycle_name: undefined }) });
    const header = container.querySelector('[data-bil="money-line"]');
    expect(header?.textContent).toContain("CY-007");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE NINE NEW ELEMENTS
// ══════════════════════════════════════════════════════════════════════════

describe("CR-105 · the nine new elements the map counts", () => {
  it("1 · the customer's NAME and the service ADDRESS are both LINKS — legend 1", () => {
    const container = mount();
    const who = container.querySelector('[data-bil="who-line"]');
    const links = [...(who?.querySelectorAll("a") ?? [])];
    // Name, address (absent without the account read) and account number all
    // point at the account. With no account fixture the address is correctly
    // omitted — an address is a real place or it is nothing — so the NAME
    // being a link is the thing this case owns.
    expect(links.length).toBeGreaterThanOrEqual(2);
    expect(links[0].textContent).toBe("Castillo, Clara");
    expect(links[0].getAttribute("href")).toBe(`/${TENANT}/accounts/${ACCOUNT}`);
  });

  it("3 · the BILLED date is on the header line and in Dates — legend 3", () => {
    const container = mount();
    expect(container.querySelector('[data-bil="money-line"]')?.textContent).toContain("08/02/2026");
    const dates = screen.getByText(t("billing.bill.field.billed"));
    expect(dates).toBeTruthy();
  });

  it("9 · Owed today is the LIVE balance, linked, and it is not one of the four", () => {
    const container = mount();
    const cells = [...container.querySelectorAll('[data-bil="owed-today"]')];
    expect(cells).toHaveLength(2);
    expect(cells[0].querySelector("a")?.getAttribute("href")).toBe(
      `/${TENANT}/accounts/${ACCOUNT}`,
    );
    expect(cells[1].textContent).toContain("$300.40");
    // …and the bill's own frozen total is a DIFFERENT figure on the same panel.
    expect(container.textContent).toContain("$251.45");
  });

  it("9 · an unanswered open position is a stated absence, never a zero", () => {
    const container = mount({ open: null });
    const cells = [...container.querySelectorAll('[data-bil="owed-today"]')];
    expect(cells).toHaveLength(2);
    expect(cells[1].textContent).not.toContain("$0.00");
    expect(cells[1].textContent).toContain(t("billing.bill.summary.awaiting"));
  });

  it("9 · Owed today does NOT render on Charges — p018 ends at Total due", () => {
    const container = mount({ tab: "lines" });
    expect(container.textContent).toContain(t("billing.bill.panel.summary"));
    expect(container.querySelectorAll('[data-bil="owed-today"]')).toHaveLength(0);
    // …and neither does the caveat, which was the same 17 words on both tabs.
    expect(container.textContent).not.toContain("These four are as at issue");
  });

  it("10 · Breakdown is ONE LINE off charges_by_service, with a link to the table", () => {
    const container = mount();
    const line = container.querySelector('[data-bil="breakdown"]');
    expect(line).not.toBeNull();
    expect(line?.textContent).toContain("Water");
    expect(line?.textContent).toContain("$246.52");
    // The bill-level bucket holds only tax here, so it is named `Tax` — the
    // drawing's own word, and true of this bucket.
    expect(line?.textContent).toContain(t("billing.bill.breakdownTax"));
    expect(line?.textContent).toContain("$4.93");
    expect(line?.querySelector("a")?.getAttribute("href")).toBe(
      `/${TENANT}/billing/bills/${INVOICE}?tab=lines`,
    );
  });

  it("10 · a bucket holding more than tax is NOT called Tax — DEF-2429's shape", () => {
    const bill = detail();
    const container = mount({
      bill: detail({
        charges_by_service: {
          ...bill.charges_by_service!,
          bill_level: {
            line_count: 2,
            kinds: ["tax", "minimum_adjustment"],
            subtotal: "10.330000",
            subtotal_display: "10.33",
          },
        },
      }),
    });
    const line = container.querySelector('[data-bil="breakdown"]');
    expect(line?.textContent).toContain(t("billing.bill.breakdownBillLevel"));
  });

  it("DEF-BIL-9346 · a bill's discounts read DISCOUNTS in the breakdown, never 'Charged to the bill'", () => {
    // Ruth's December bill (CR-166 walk step 8): Senior −$9.00 + Autopay −$0.26,
    // no tax. Both figures are the server's split of the bucket.
    const bill = detail();
    const container = mount({
      bill: detail({
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
    });
    const line = container.querySelector('[data-bil="breakdown"]');
    expect(line?.textContent).toContain(t("billing.bill.group.discounts"));
    expect(line?.textContent).not.toContain(t("billing.bill.breakdownBillLevel"));
    expect(container.textContent).not.toContain(t("billing.bill.breakdownBillLevel"));
  });

  it("DEF-BIL-9346 · discounts AND a tax: Discounts and Tax, each with its own figure", () => {
    const bill = detail();
    const container = mount({
      bill: detail({
        charges_by_service: {
          ...bill.charges_by_service!,
          bill_level: {
            line_count: 3,
            kinds: ["discount", "tax"],
            subtotal: "-6.260000",
            subtotal_display: "-6.26",
            discounts: { line_count: 2, subtotal: "-9.260000", subtotal_display: "-9.26" },
            others: { line_count: 1, kinds: ["tax"], subtotal: "3.000000", subtotal_display: "3.00" },
          },
        },
      }),
    });
    const line = container.querySelector('[data-bil="breakdown"]');
    expect(line?.textContent).toContain(t("billing.bill.group.discounts"));
    expect(line?.textContent).toContain(t("billing.bill.breakdownTax"));
    expect(line?.textContent).toContain("$3.00");
  });

  it("11 · Usage sums THIS PERIOD off the bill and reads AVERAGE off the account", () => {
    const container = mount();
    const table = container.querySelector('[data-bil="bill-usage"]');
    expect(table).not.toBeNull();
    const cells = [...(table?.querySelectorAll("tbody td") ?? [])].map((td) => td.textContent ?? "");
    expect(cells[0]).toBe("Water");
    // 5 + 14 = 19 kgal, and hard rule 3 says it never renders without the unit.
    expect(cells[1]).toBe("19 kgal");
    expect(cells[2]).toBe("17.4 kgal");
  });

  it("11 · the READ column carries the SERVER's own sentence, never an invented meter", () => {
    const container = mount();
    const table = container.querySelector('[data-bil="bill-usage"]');
    const cells = [...(table?.querySelectorAll("tbody td") ?? [])];
    expect(cells[3].textContent).toContain(t("billing.bill.usage.readAbsent"));
    expect(cells[3].textContent).not.toMatch(/M-\d/);
  });

  it("11 · two units inside one service is an absence, not a sum — hard rule 3", () => {
    const container = mount({
      bill: detail({
        lines: [line(), line({ id: "ln-x", quantity: "3.000000", unit: "gal" })],
      }),
    });
    const table = container.querySelector('[data-bil="bill-usage"]');
    const cells = [...(table?.querySelectorAll("tbody td") ?? [])];
    expect(cells[1].textContent).toContain(t("billing.bill.usage.mixedUnits"));
    expect(cells[1].textContent).not.toContain("8");
  });

  it("11 · a bill with no metered line says so rather than drawing an empty table", () => {
    const container = mount({
      bill: detail({
        lines: [line({ id: "ln-b", kind: "base", quantity: null, unit: null })],
      }),
    });
    expect(container.querySelector('[data-bil="bill-usage"]')).toBeNull();
    expect(screen.getByText(t("billing.bill.usageNone"))).toBeTruthy();
  });

  it("11 · an account with no usage history awaits it — never averages zero", () => {
    const container = mount({ usage: null });
    const table = container.querySelector('[data-bil="bill-usage"]');
    const cells = [...(table?.querySelectorAll("tbody td") ?? [])];
    expect(cells[2].textContent).toContain(t("billing.bill.usage.averageAwaiting"));
    expect(cells[2].textContent).not.toContain("0 kgal");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// THE MOVES — asserted on the side they ARRIVED at
// ══════════════════════════════════════════════════════════════════════════

describe("CR-105 · Dates absorbs When-this-is-due and the second pill", () => {
  it("all five drawn rows are in Dates, in the drawn order", () => {
    const container = mount();
    const text = container.textContent ?? "";
    const at = [
      t("billing.bill.field.billed"),
      t("billing.bill.field.servicePeriod"),
      t("billing.bill.field.due"),
      t("billing.bill.field.pastDue"),
      t("billing.bill.field.feesOnBill"),
    ].map((label) => text.indexOf(label));
    expect(at.every((i) => i >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
  });

  it("the service period carries its day count — 07/01 to 07/31 is 31 days", () => {
    const container = mount();
    expect(container.textContent).toContain(t("billing.bill.periodDays", { count: 31 }));
  });

  it("the late-terms sentence moved with it, and still composes nothing", () => {
    const container = mount();
    const terms = container.querySelector('[data-bil="late-terms"]');
    expect(terms).not.toBeNull();
    expect(container.textContent).not.toContain("1.5%");
    expect(container.textContent).not.toContain("$5.00 or");
  });

  it("`Past-due unknown` lives ONCE, under Dates — never as a second pill", () => {
    const container = mount({ bill: detail({ past_due: null }) });
    const pills = [...container.querySelectorAll(".page-header-identity, header")]
      .map((el) => el.textContent ?? "")
      .join(" ");
    expect(pills).not.toContain(t("billing.bill.pastDueUnknown"));
    expect(screen.getByText(t("billing.bill.pastDueUnknown"))).toBeTruthy();
  });
});

describe("CR-105 · Record is the two version axes merged with the record check", () => {
  it("both version axes and both integrity verdicts are in one closed group", () => {
    const container = mount();
    const record = container.querySelector('details[data-bil="group-record"]');
    expect(record).not.toBeNull();
    const text = record?.textContent ?? "";
    expect(text).toContain(t("billing.bill.field.templateVersion"));
    expect(text).toContain(t("billing.bill.field.payloadVersion"));
    expect(text).toContain(t("billing.bill.field.documentTiesOut"));
    expect(text).toContain(t("billing.bill.field.postingBalanced"));
  });
});
