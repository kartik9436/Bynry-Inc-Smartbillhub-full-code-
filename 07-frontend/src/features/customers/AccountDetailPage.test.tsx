// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-008 (S21 header, pills & action rails) ·
//           US-CUS-009 (Overview tab panels) ·
//           US-CUS-010 (Bills · Payments · Adjustments) ·
//           US-CUS-011 (Usage · Meters · Documents · Notes · Audit)
//           Screens: S21
// Rules:    BR-CUS-016 (aging is DERIVED and never stored — so it is absent) ·
//           BR-CUS-018 (a draft is the only thing that activates) ·
//           BR-CUS-029 (no account plan snapshot ⇒ `plan` is null with its
//           rule id. ⚠ THIS READ "⇒ no plan block" UNTIL 2026-09-01 and
//           that inference was DEF-2419: the account is BILLED on a plan
//           and the box now shows it, read through the unit FK) ·
//           BR-CUS-030 (closing is the move-out flow, refused here) ·
//           BR-CUS-045 (the government id is the last four only) ·
//           BR-CUS-054 (no customer entity ⇒ no "all accounts" chip) ·
//           BR-CUS-055 (the seeded statuses and their behaviour classes) ·
//           BR-CUS-057 / BR-CUS-058 (deposit interest · computed credit tier) ·
//           BR-CUS-059 (autopay is capture-only) · BR-SHL-023 (one money path) ·
//           BR-SHL-025 (disabled WITH the reason) · BR-SHL-034 (one date path) ·
//           BR-SHL-044 (one header, exactly one primary)
// ───────────────────────────────────────────────────────
// §4 test data is A-10432 (EP-CUS-03 §4), rendered through the seeded query
// cache — no network, ever.
//
// The assertions that matter most are the NEGATIVE ones. This screen must not
// print a due date, a deposit-interest figure or a credit tier where the server
// said "there is no table for that". Each is one line in the defect log's
// fabricated-value family, and each is checked below.
//
// ⚠ **"A PLAN" WAS THE FIRST ITEM IN THAT LIST UNTIL 2026-09-01, AND IT DID NOT
// BELONG THERE (DEF-2419).** The other three have no source anywhere in the
// product. The plan HAS one — the unit the account stands on — and the account
// is demonstrably billed on it. What has no table is the account's own SNAPSHOT
// of it, which is a different fact and is still absent. A negative assertion
// over a fact the product can answer is not caution; it is a screen refusing to
// show a clerk something they can see one page away.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type {
  AccountDetail,
  AccountNote,
  AssetDetail,
  AssetReadRow,
  CustomFieldRegistryEntry,
  InvoiceRow,
  MyPermissions,
} from "@/api/endpoints";
import { formatMoney } from "@/components/MoneyCell";
import { queryKeys } from "@/api/queryClient";
import { entityAuditQueryKey } from "@/features/metering/PremisesDetailPage";
import { ToastProvider } from "@/components/Toast";

import { accountNotesKey, UNAVAILABLE_ACTIONS } from "./AccountActions";
import { accountUsageKey } from "./AccountUsageTab";
import type { UsagePayload, UsagePoint } from "./AccountUsageTab";
import { ACCOUNT_RAIL_ACTIONS } from "./AccountIconRail";
import {
  ACCOUNT_TAB_IDS,
  AccountDetailPage,
  accountDetailQueryKey,
  accountRollupLine,
  accountTabs,
  addressLine,
} from "./AccountDetailPage";
import {
  accountMeterAssetKey,
  accountMeterReadsKey,
  accountRecentBillsKey,
} from "./accountDetailTabs";
import {
  ACCOUNTS_PERMISSION,
  accountDetailPath,
  accountHeadline,
  isClosedAccount,
  isDraftAccount,
  maskedGovId,
  primaryContact,
  warningText,
  ACCOUNT_CATEGORIES_QUERY_KEY,
} from "./customersShared";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…`.
const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function detail(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: "acc-10432",
    account_no: "A-10432",
    // BR-CUS-068: the server serves `kind` on EVERY account payload, so the
    // fixture states it too — an ordinary account is `regular`; `master` is
    // the owner's account over a premises' common areas.
    kind: "regular",
    name: "Miller, Sarah",
    unit_id: "u-10432a",
    unit_label: "A",
    premise: "1408 Elm St · A",
    services: ["electric", "water"],
    balance: "247.300000",
    // DEF-127 — the LEDGER's figure and the CHAR(3) it derived for it.
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    // BR-CUS-510 / DEF-628 — the DEFAULT is `false`: this fixture's zero,
    // wherever it has one, is a real answer about money owed.
    balance_not_yet_billable: false,
    balance_cached: "0.000000",
    currency: "USD",
    status: "active",
    status_name: "Active",
    status_behavior_class: "billable",
    account_type: "residential",
    account_subtype: null,
    autopay: true,
    opened_at: "2024-02-14",
    closed_at: null,
    // Billing owns both, and billing is not built (W3).
    last_bill_at: null,
    aging: null,
    deposit_on_file: "0.000000",
    deposit_received_on: null,
    credit_tier: null, // COMPUTED cache with no computer yet (BR-CUS-058)
    tax_exempt: false,
    tax_exempt_ref: null,
    tax_exempt_expires: null,
    bad_address: false,
    nsf_count: 0,
    preferred_language: null,
    custom_data: {},
    contacts: [
      {
        id: "c-1",
        full_name: "Miller, Sarah",
        email: "sarah.miller@example.com",
        phone: "+1 (512) 555-0184",
        dob: "1987-04-12",
        gov_id_last4: "4218",
        is_primary: true,
      },
    ],
    addresses: [],
    service_agreements: [
      {
        id: "sa-1",
        service_point_id: "sp-1",
        service: "electric",
        started_on: "2024-02-14",
        ended_on: null,
      },
    ],
    meters: [{ id: "ast-4021", asset_no: "M-4021", qualifier: null }],
    // The server sends BOTH: the null, and the rule that says why. UNCHANGED
    // by DEF-2419 — this is the ACCOUNT's own snapshot (BR-CUS-029, still no
    // table), and `unit_plan` below is the different question.
    plan: null,
    plan_snapshot_unavailable: "BR-CUS-029",
    // DEF-2419 — the plan the account is BILLED on, read through
    // `accounts.unit_id` -> `units.rate_plan_id`. These are the PO's own
    // figures from the unit screen they put beside this one: the same unit
    // shows `Sample — Residential v1` and `ON PLAN SINCE 06/01/2026`.
    unit_plan: {
      name: "Sample — Residential",
      code: "RES-STD",
      version: 1,
      since: "2026-06-01",
    },
    // BR-CUS-054's entity landed 2026-08-11 (US-CUS-019). An account created
    // before it — which is every account in these fixtures — carries no link,
    // and null is the honest value rather than a customer nobody created.
    customer: null,
    ...over,
  };
}

/**
 * CR-030 W3 — the three lists this screen reads from OTHER modules, as their
 * own endpoints answer them. They are fixtures of the SERVED shape, not of a
 * customers read model: `GET /invoices?f.account_id=`, `GET /assets/{id}` and
 * `GET /assets/{id}/reads` (BR-CUS-034).
 */
function bill(over: Partial<InvoiceRow> = {}): InvoiceRow {
  return {
    id: "inv-1",
    invoice_no: "BL-2607-018204",
    bill_type: "cyclic",
    status: "paid",
    past_due: null,
    account_id: "acc-10432",
    account_no: "A-10432",
    customer_name: "Miller, Sarah",
    cycle_label: "07-A",
    bill_run_id: "run-1",
    service_date: "2026-07-15",
    period_start: "2026-06-15",
    period_end: "2026-07-14",
    issued_at: "2026-07-15T08:42:01Z",
    due_date: "2026-08-01",
    subtotal: "228.350000",
    tax_total: "18.950000",
    total: "247.300000",
    currency: "USD",
    template_version: "v1",
    ...over,
  } as InvoiceRow;
}

/** r10's `M-4021`: `AMI · Itron OpenWay CENTRON`, installed Feb 12 2024. */
function asset(over: Record<string, unknown> = {}): AssetDetail {
  return {
    id: "ast-4021",
    asset_no: "M-4021",
    type: "electric_meter",
    type_name: "Electric meter",
    status: "in_service",
    status_name: "Healthy",
    behavior_class: "in_service",
    read_method_name: "AMI",
    manufacturer: "Itron",
    model: "OpenWay CENTRON",
    multiplier: "1",
    install_date: "2024-02-12",
    service: "electric",
    ...over,
  } as unknown as AssetDetail;
}

function read(over: Partial<AssetReadRow> = {}): AssetReadRow {
  return {
    read_id: "r-1",
    date: "2026-08-03T06:12:00Z",
    channel: "total",
    read_type: "consumption",
    reading: "43148",
    consumption: "284",
    unit: "kWh",
    export: null,
    export_unit: null,
    export_read_id: null,
    source: "ami",
    status: "ok",
    ...over,
  };
}

function permissions(access: string): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access }],
  };
}

function renderDetail(
  path: string,
  seed: {
    detail?: AccountDetail;
    access?: string;
    /** `GET /invoices?f.account_id=` — the recent-bills panel (CR-030 3.4). */
    bills?: InvoiceRow[];
    /** `GET /assets/{id}` per meter — the Meters table (CR-030 3.9). */
    assets?: Record<string, AssetDetail>;
    /** `GET /assets/{id}/reads` per meter — the nested read log. */
    reads?: Record<string, AssetReadRow[]>;
    /** `GET /accounts/{id}/notes` — the Notes CARDS (CR-030 3.10). */
    notes?: AccountNote[];
    /**
     * `GET /accounts/{id}/usage` over the OVERVIEW's TWELVE-month window — the
     * `USAGE TREND` group. Without it that group renders its pending state, and
     * a case about the TABLE would be reading a spinner: law 7's *looking at
     * the wrong thing*, which passes and fails for reasons it is not about.
     */
    usage?: UsagePayload;
    /** `GET /custom-fields?entity=accounts&screen=S21&mode=view` — the
     *  utility's own fields on the Overview (`DEF-CUS-9121`). */
    customFields?: CustomFieldRegistryEntry[];
  } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (seed.customFields !== undefined) {
    queryClient.setQueryData(queryKeys.customFieldRegistry("accounts", "S21", "view"), seed.customFields);
  }
  // ⛔ **DEF-684 — THE CONSUMER CATEGORY ARRIVES OVER THE WIRE.** The Account
  // panel used to print `t("customers.accounts.category." + code)`, and only
  // BR-CUS-094's superseded FOUR have a catalogue key — so an account in one of
  // the four categories the ruling added (`builder_developer` most visibly)
  // printed its raw slug on S21. The seed below is the platform catalogue as
  // `GET /service-requests/categories` serves it.
  queryClient.setQueryData(ACCOUNT_CATEGORIES_QUERY_KEY, {
    selectable: [
      { code: "residential", name: "Residential" },
      { code: "builder_developer", name: "Builder or developer" },
    ],
    legacy: [],
  });
  if (seed.detail !== undefined) {
    queryClient.setQueryData(accountDetailQueryKey(seed.detail.id), seed.detail);
  }
  if (seed.access !== undefined) {
    queryClient.setQueryData(queryKeys.myPermissions, permissions(seed.access));
  }
  // DEF-579: the Audit tab now READS this account's own rows (BR-AUD-010's
  // first half, which the shipped tab never did). Seeded EMPTY by default so
  // every case here measures the tab and not A18's loading skeleton; the rows
  // themselves are pinned on PRM-02/PRM-03, where the PO reported the defect.
  if (seed.detail !== undefined) {
    queryClient.setQueryData(entityAuditQueryKey("account", seed.detail.id), {
      page: { count: 0, next: null, previous: null, results: [] },
      window: { window: "hot", from: null },
    });
  }
  if (seed.detail !== undefined && seed.bills !== undefined) {
    queryClient.setQueryData(accountRecentBillsKey(seed.detail.id), {
      count: seed.bills.length,
      next: null,
      previous: null,
      results: seed.bills,
      rollup: { total: null, currency: null },
    });
  }
  for (const [assetId, row] of Object.entries(seed.assets ?? {})) {
    queryClient.setQueryData(accountMeterAssetKey(assetId), row);
  }
  for (const [assetId, rows] of Object.entries(seed.reads ?? {})) {
    queryClient.setQueryData(accountMeterReadsKey(assetId), rows);
  }
  if (seed.detail !== undefined && seed.notes !== undefined) {
    queryClient.setQueryData(accountNotesKey(seed.detail.id), seed.notes);
  }
  // 12 and not 24: the Overview's group opens on r10's *"last 12 months"*
  // while the Usage TAB opens on 24, so the key must be the one this group
  // actually asks for.
  if (seed.detail !== undefined && seed.usage !== undefined) {
    queryClient.setQueryData(accountUsageKey(seed.detail.id, 12), seed.usage);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <Routes>
            <Route path="/:tenant/accounts/:accountId" element={<AccountDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * The header, up to the first thing below it: where the ONE primary must live.
 *
 * ⚠ **THIS SLICED ON `class="met-panel"` AND HAD STOPPED SLICING ANYTHING.**
 * CR-018 Phase 4b-2 migrated `Panel` to Tailwind utilities, so no element on
 * this page carries that class any more, `indexOf` returned −1, and every
 * assertion written against "the header" was silently reading the WHOLE
 * document — including its own button count. Found by CR-030 W3 when the count
 * came back 24 for a header holding 12. The slice is now the metric block's
 * own `data-account-metrics` marker, which is the first element after the
 * header by construction and is a data attribute rather than a style hook, so
 * a future migration cannot quietly break it again.
 */
/**
 * A two-service usage payload — the shape `GET /accounts/{id}/usage` serves.
 *
 * Three months per service, newest last in the payload (the server's order) so
 * the case can prove the TABLE reverses them, which the drawing requires:
 * *"the six most recent months, newest first"*.
 */
function usagePayload(): UsagePayload {
  const point = (month: string, q: string, unit: string): UsagePoint => ({
    month,
    quantity: `${q}.000000`,
    quantity_display: q,
    unit,
    absent: false,
    read_count: 1,
    estimated_read_count: 0,
    estimated: false,
    computed_at: "2026-09-01T00:00:00Z",
  });
  const metric = (display: string | null, unit: string | null, month?: string) => ({
    value: display === null ? null : `${display}.000000`,
    display,
    unit,
    month: month ?? null,
    absent_reason: display === null ? "unavailable" : null,
  });
  const series = (id: string, code: string, name: string, unit: string, qs: string[]) => ({
    service: { id, code, name },
    unit,
    unit_absence: null,
    points: [point("2026-06", qs[0]!, unit), point("2026-07", qs[1]!, unit), point("2026-08", qs[2]!, unit)],
    months_present: 3,
    months_absent: 0,
    metrics: {
      avg_per_month: metric(qs[1]!, unit),
      peak: metric(qs[2]!, unit, "2026-08"),
      low: metric(qs[0]!, unit, "2026-06"),
      yoy: metric(null, null),
    },
  });
  return {
    account_id: "acc-10432",
    window: { months: 12, from: "2025-09", to: "2026-08", options: [12, 24] },
    services: [
      { id: "svc-e", code: "electric", name: "Electric" },
      { id: "svc-w", code: "water", name: "Water" },
    ],
    series: [
      series("svc-e", "electric", "Electric", "kWh", ["1000", "1100", "1200"]),
      series("svc-w", "water", "Water", "kgal", ["9", "10", "11"]),
    ],
    water_avg: metric("10", "kgal"),
    rule_ref: "BR-MET-106",
  } as UsagePayload;
}

function header(html: string): string {
  const end = html.indexOf("data-account-metrics");
  return end === -1 ? html : html.slice(0, end);
}

/**
 * The METRIC STRIP alone — `data-account-metrics` up to the icon rail that
 * always follows it.
 *
 * ⚠ **BOUNDED AT BOTH ENDS, AND THE SECOND BOUND IS THE WHOLE POINT.** A slice
 * that only cuts at the start runs to the end of the document, so it contains
 * the Overview tab's "Deposit & credit" card — and a case asserting the strip
 * carries a deposit tile passed with no tile there at all. It was found by
 * red-proving the case (hard-won law 7), which is the only reason it is not
 * still passing.
 */
function metrics(html: string): string {
  const start = html.indexOf("data-account-metrics");
  if (start === -1) {
    return "";
  }
  const end = html.indexOf("data-account-icon-rail", start);
  return end === -1 ? html.slice(start) : html.slice(start, end);
}

/**
 * The document with every `title=` attribute removed. The negative assertions
 * below are about what the screen SHOWS: the reasons deliberately NAME the
 * missing ageing states in prose ("Current, 30 days past and 60+ past are
 * worked out from open invoices"), and a whole-document `not.toContain` would
 * read that explanation as the defect it exists to prevent.
 */
function visible(html: string): string {
  return html.replace(/ title="[^"]*"/g, "");
}

/**
 * The ICON RAIL's own markup (CR-030 W3 · 3.2 · BR-SHL-045).
 *
 * Sliced on `data-account-icon-rail` for the reason `header()` above learned the
 * hard way: a slice taken on a style class stops slicing anything the day the
 * style migrates, and every assertion written against it silently starts reading
 * the whole document. The rail's children are `<button><svg…></button>` and
 * nothing else, so the first `</div>` after the marker is the rail's own close.
 */
function rail(html: string): string {
  const start = html.indexOf("data-account-icon-rail");
  if (start === -1) return "";
  const end = html.indexOf("</div>", start);
  return end === -1 ? html.slice(start) : html.slice(start, end);
}

/** Every opening `<button …>` tag inside the rail, in document order. */
/**
 * The header's COMMAND buttons — its worded actions, and never its tabs.
 *
 * ⚠ **THE `role="tab"` EXCLUSION IS THE WHOLE POINT** (`DEF-CUS-4631`,
 * 2026-09-07). `PageHeader` renders the tab strip as `<button role="tab">`
 * inside the header, so "every button in the header" and "every action in the
 * header" are different sets — and the two cases that use this ask about the
 * second. They used to ask `header(html).not.toContain(">Payment plan<")`,
 * which was a true assertion about a screen with a tab called "Plan" and became
 * a false alarm the day that tab was correctly renamed **Payment plan**. A tab
 * that SHOWS the payment plan and a glyph that STARTS one are not a duplicated
 * control; the raw-text form could not tell them apart and this can.
 */
function headerCommandLabels(html: string): string[] {
  return [...header(html).matchAll(/<button\b([^>]*)>([^<]*)</g)]
    .filter((match) => !/ role="tab"/.test(match[1]))
    .map((match) => match[2].trim());
}

function railButtons(html: string): string[] {
  return [...rail(html).matchAll(/<button\b[^>]*>/g)].map((m) => m[0]);
}

/** One attribute off a tag — `""` when the attribute is absent entirely. */
function attr(tag: string, name: string): string {
  return new RegExp(` ${name}="([^"]*)"`).exec(tag)?.[1] ?? "";
}

/**
 * Is this control actually disabled?
 *
 * ⚠ IT IS NOT `tag.includes("disabled")`, AND THE FIRST DRAFT OF THIS FILE WROTE
 * IT THAT WAY AND WENT RED ON THREE HEALTHY CONTROLS. Every button in the
 * product now carries the Tailwind utilities `disabled:opacity-45
 * disabled:cursor-not-allowed` in its class string, so the SUBSTRING is present
 * on every button whether it is disabled or not. A `not.toContain("disabled")`
 * can therefore never pass, and — the direction that actually matters — a
 * `toContain("disabled")` passes on a control that is fully enabled. That is
 * the DEF-182 shape: a check whose output cannot distinguish pass from fail.
 * Read the ATTRIBUTE.
 */
function isDisabled(tag: string): boolean {
  return / disabled=""/.test(tag);
}

describe("DEF-CUS-9776 / DEF-CUS-9774 — a company's name, and its certificate", () => {
  // M5's church: the customer is the company, the contact a person, and the
  // only exemption a per-tax CERTIFICATE (ruling (A): the blanket flag stays false).
  const church = (): AccountDetail =>
    detail({
      name: "Grace Fellowship of Cedar Ford",
      contacts: [
        { id: "c-9", full_name: "Ruth Okafor", email: null, phone: null, dob: null, gov_id_last4: null, is_primary: true },
      ] as AccountDetail["contacts"],
      customer: {
        id: "cu-54",
        kind: "company",
        display_name: "Grace Fellowship of Cedar Ford",
        external_ref: null,
        accounts: [{ id: "acc-10432", account_no: "A-10432" }],
      },
      tax_exempt: false,
      tax_exempt_ref: null,
      tax_exempt_expires: null,
      tax_exemptions: [
        {
          id: "cert-1",
          certificate_ref: "CF-REL-2026-0412",
          issued_on: "2026-01-15",
          expires_on: "2028-12-31",
          state: "live",
          tax_id: "tax-city",
          tax_name: "City of Cedar Ford utility tax",
          category_name: "Religious",
        },
        {
          id: "cert-0",
          certificate_ref: "OLD-1",
          issued_on: "2020-01-01",
          expires_on: "2021-01-01",
          state: "expired",
          tax_id: "tax-old",
          tax_name: "Expired county tax",
          category_name: "Religious",
        },
      ],
    });

  it("titles the account by the company, not its contact person", () => {
    expect(accountHeadline(church(), t)).toBe("Grace Fellowship of Cedar Ford");
    const html = renderDetail("/accounts/acc-10432", { detail: church() });
    expect(html).toMatch(/<h1[^>]*>Grace Fellowship of Cedar Ford<\/h1>/);
    expect(html).toMatch(/<dt>Full name<\/dt><dd>Grace Fellowship of Cedar Ford<\/dd>/);
  });

  it("states the live certificate on the drawn three rows, and not the expired one", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: church() });
    expect(html).toContain("Exempt from City of Cedar Ford utility tax");
    expect(html).toContain("CF-REL-2026-0412");
    expect(html).toContain("12/31/2028");
    expect(html).not.toContain("Expired county tax");
    expect(html).not.toMatch(/<dt>Tax exempt<\/dt><dd>No<\/dd>/);
  });

  it("an account with neither a blanket flag nor a certificate still reads No", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail({ tax_exempt: false, tax_exemptions: [] }) });
    expect(html).toMatch(/<dt>Tax exempt<\/dt><dd>No<\/dd>/);
  });
});

describe("US-CUS-008 — the S21 header, its pills and its action rails", () => {
  it("US-CUS-008 TC-1: the billing chain, both pills and the service tags render from the served row", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    // The kicker is the account number; the H1 is the person the bills go to.
    expect(html).toContain("Account A-10432");
    expect(html).toMatch(/<h1[^>]*>Miller, Sarah<\/h1>/);
    expect(html).toContain("1408 Elm St · A");
    // BR-SHL-034: the "since" date through the ONE formatter, never re-cut.
    // ⚠ AMENDED (CR-030 W3 · 3.1): r10 writes `Since Feb 2024`, and the shared
    // DateCell has had a `monthYear` mode since CR-028 — so the chain asks for
    // that mode instead of the full date. Still one formatter, still no string
    // cut by this screen.
    expect(html).toContain("Feb 2024");
    expect(html).toContain("Since");
    // BR-CUS-015: one tag per ACTIVE service agreement, through the ONE tag
    // component — the service catalog is platform-level.
    // ⚠ AMENDED 2026-08-21 (CR-023 P1). This asked for `met-tag-electric` — the
    // full-name chip metering's `ServiceTags` used to draw. That component now
    // renders r10's coloured LETTER SQUARES from the ONE badge implementation
    // the product shares (`features/rating/ratingShared`), so this screen got
    // the fix for free and this assertion had to follow it. Same rule, same
    // component, same source of truth: BR-CUS-015's one tag per ACTIVE service
    // agreement, through the shared component rather than a per-module copy.
    expect(html).toContain("var(--color-service-electric)");
    expect(html).toContain("var(--color-service-water)");
    expect(html).toContain('aria-label="Electric"');
    // BR-CUS-055 / BR-CUS-059: the stored status and the enrolment pill.
    expect(html).toContain("Active");
    expect(html).toContain("Autopay on");
    // BR-SHL-023: the balance is FORMATTED, never parsed or re-rounded here.
    expect(html).toContain("$247.30");
    expect(html).not.toContain("247.300000");
    // AMENDED 2026-08-16 (DEF-127). The qualifier used to read "cached figure —
    // the ledger is the source of truth, and nothing writes this column yet",
    // which described the column the header was actually serving: a cache that
    // read $0.00 for an account holding an issued, unpaid 108.88. The figure is
    // now the ledger's own and the sentence says where it came from.
    expect(html).toContain("worked out from the ledger");
  });

  it("US-CUS-008 TC-1 / DEF-2419: the plan block shows the plan the UNIT holds, name + version + since", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    // ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-09-01, AND THE ASSERTION
    // WAS THE DEFECT (DEF-2419).** It required the box to state an absence —
    // *"Plan not shown here"* — on the ground that the unit's plan and the
    // account's diverge at the first override. There is no override and there
    // cannot be one: nothing in the schema can hold a plan for one account
    // differing from its unit, so the divergence had nowhere to be stored.
    // PO ruling 2026-09-01: *"It should be foreign key - it should take it
    // from Unit and display it there - that is important"*, confirming their
    // ruling of 2026-08-11, *"from unit you will derive the plan"*.
    expect(html).toContain("Sample — Residential");
    // BR-CUS-013's SNAPSHOT integer, and the date the unit took the plan —
    // the two facts the unit screen already prints beside the name.
    expect(html).toContain("v1");
    expect(html).toContain("since");
    // The caption names the UNIT as the source, because what priced an OLD
    // bill is that bill's Charges tab and not this box.
    expect(html).toContain("Plan from unit");
    // ⚠ THE OLD SENTENCES ARE GONE FROM THE SCREEN, BOTH OF THEM.
    expect(html).not.toContain("Plan not shown here");
    // The shared wizard key is untouched and must not surface here either.
    expect(html).not.toContain("No plan recorded");
    // B14 rule 33 — RATIONALE is ZERO words on screen. The 68-word paragraph
    // that explained why the box was empty now lives in the code comment.
    expect(html).not.toContain("match only until the first override");
    expect(html).not.toContain("kept as a snapshot taken when the account");
  });

  it("DEF-2419 / BR-CUS-029: `plan` is STILL null and its rule is STILL served — showing is not storing", () => {
    // The whole change rests on this distinction, so it is asserted rather
    // than assumed. The account's OWN snapshot has no table and none was
    // invented; what the screen gained is a READ through the unit FK.
    const served = detail();
    expect(served.plan).toBeNull();
    expect(served.plan_snapshot_unavailable).toBe("BR-CUS-029");
    const html = renderDetail("/accounts/acc-10432", { detail: served });
    // r10 prints `Residential Standard` / `$30.50/mo base` in this column from
    // the account snapshot. Neither is invented: the base charge is still
    // absent and still says where the figure lives.
    expect(html).not.toContain("Residential Standard");
    expect(html).not.toContain("$30.50");
    expect(html).toContain("Base charge not shown here");
  });

  it("DEF-2419: a unit with NO plan states the absence — an empty box is not an answer", () => {
    // `units.rate_plan_id` is nullable and a unit standing on no plan is an
    // ORDINARY state, not a gap in the utility's data. Two other absences
    // arrive as the same null — an account naming no unit, and a plan no
    // longer published — and one sentence covers all three truthfully.
    const html = renderDetail("/accounts/acc-10432", {
      detail: detail({ unit_plan: null }),
    });
    expect(html).toContain("No plan on this account");
    expect(html).not.toContain("Sample — Residential");
    // And NOT the shared wizard key, which claims the utility recorded nothing.
    expect(html).not.toContain("No plan recorded");
  });

  it("DEF-2419 / B14 rule 31: no database id reaches the plan box", () => {
    // Rule 31: nothing internal is ever visible to a utility user — not a
    // primary key, not a rule number. The payload deliberately carries NO
    // plan id at all, so there is nothing to leak; the unit screen reaches
    // its plan by id and this one does not.
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    const plan = html.slice(html.indexOf("Plan from unit"));
    const box = plan.slice(0, plan.indexOf("Base charge not shown here"));
    expect(box).not.toContain("u-10432a"); // the unit id
    expect(box).not.toContain("acc-10432"); // the account id
    expect(box).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/i); // any uuid
    // A rule id in the SENTENCE is the DEF-332 shape. `data-rule-ref` is the
    // sanctioned carrier and is not what a clerk reads.
    expect(box.replace(/data-rule-ref="[^"]*"/g, "")).not.toContain("BR-CUS-");
  });

  it("US-CUS-008 §5 / BR-CUS-016: no due date and no ageing state are invented", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    // ⚠ **BOTH SENTENCES CHANGED ON 2026-08-27 (CR-043 finding 11) AND THE
    // RULE DID NOT.** Nothing here invents a due date or an ageing state, which
    // is what the negatives below still check.
    //
    // "Not known yet" sat under the BALANCE and named no subject, so the PO
    // read **$64.57 / "Not known yet"** as a doubt about the balance. It names
    // the due date now.
    //
    // "Nothing read yet" used the word READ on a utility screen, which is
    // understood as a METER READING — on an account whose bill prices 5 kgal +
    // 3 kgal. The column was never about reads; its own `why` says it is the
    // newest event of any kind and that only payments can be read for it today.
    expect(html).toContain("Due date not known yet");
    expect(html).not.toContain("Nothing read yet");
    // ⚠ **`"Not shown yet"` IS NO LONGER ASSERTED, BECAUSE THE TILE IT BELONGED
    //    TO IS GONE (PO 2026-09-13).** It was the Last activity tile's awaiting
    //    label. That tile is not in the PO's row — *"Balance, Ageing, Last bill,
    //    Plan from unit, Deposit"* — and before it was removed every `.ts`/`.tsx`
    //    file under `src/` was searched for a caller of its `lastActivity` prop:
    //    **nothing in the product ever passed it.** The prop was optional, so
    //    the tile rendered this awaiting branch on every account that has ever
    //    opened this screen and could not have rendered anything else. The
    //    assertion was pinning dead UI in place.
    //
    // ⚠ **AND THE PARAGRAPH BELOW USED TO SAY AGEING HAS NO PLACE ON THIS
    //    SCREEN. THAT IS SUPERSEDED AND THE REASONING IS WORTH KEEPING.**
    //    It read: *"r10's header card draws THREE metric columns and no ageing
    //    at all, and B18 §5.1.2 puts ageing on the S17 row where a clerk scans
    //    for it — so the fact is gone from this screen"*. Correct in August,
    //    and the cost showed up in September: the LIST drew an Ageing column,
    //    the DETAIL drew nothing, and a clerk drilling in from that list lost
    //    the single fact saying how overdue the account is. The blueprint draws
    //    Ageing as the SECOND tile and the PO confirmed it under B14 rule 41.
    //
    //    **WHAT SURVIVES INTACT IS THE RULE THIS CASE IS NAMED FOR: nothing may
    //    FABRICATE an ageing state.** This fixture serves no ageing keys at
    //    all, so no band may appear — which is exactly what the negatives below
    //    still check, and they are now checking something harder than they were,
    //    because the screen has a tile that COULD show a band and must not.
    expect(html).not.toContain("Not worked out yet");
    // A fabricated "Current" would be a claim about a customer's money. The
    // reasons name those states in prose on purpose, so this looks at what is
    // rendered rather than at what is explained.
    const shown = visible(html);
    expect(shown).not.toContain(">Current<");
    expect(shown).not.toContain("30d past");
    expect(shown).not.toContain("60+ past");
    expect(shown).not.toContain("30 days past");
  });

  it("US-CUS-008 TC-4 / BR-SHL-025: an Executive sees every action disabled WITH its reason, never hidden", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail(), access: "View" });
    const head = header(html);
    expect(head).toContain("Record payment");
    expect(head).toContain("Adjust");
    expect(head).toContain("Move-out");
    expect(head).toContain("Activate account");
    expect(head).toContain("Your role can view accounts but not change them.");
    expect(head).toContain("disabled");
  });

  it("US-CUS-008 TC-6 / A18 §6: a '—' cell hides the whole surface", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail(), access: "—" });
    expect(html).toContain("state-denied");
    expect(html).not.toContain("A-10432");
  });

  it("US-CUS-008 TC-5 / BR-CUS-030: Move-out OPENS S20 for an occupant, and never flips a status", () => {
    const head = header(renderDetail("/accounts/acc-10432", { detail: detail(), access: "Full" }));
    expect(head).toContain("Move-out");
    // S20 landed 2026-08-11 (US-CUS-005), so an OCCUPANT's Move-out is a live
    // control — it no longer claims the page is missing. Hard-won law 1: the
    // string had to change with the fact.
    expect(head).not.toContain("Move-out is a guided page of its own and is not built.");
    expect(head).not.toContain("The server refuses to close an account");
    // BR-CUS-030: a draft never took the unit, so ITS Move-out stays disabled
    // with the state as the reason.
    const draftHead = header(
      renderDetail("/accounts/acc-10432", {
        detail: detail({
          status: "pending_activation",
          status_name: "Pending activation",
          status_behavior_class: "non_billable",
        }),
        access: "Full",
      }),
    );
    expect(draftHead).toContain("Only an account that currently holds its unit can be moved out.");
    // BR-CUS-017: Move-in hands the unit on, so it is live only once CLOSED.
    expect(head).toContain("Move-in");
    expect(head).toContain("Move-in hands this account&#x27;s unit to the next occupant");
    const closedHead = header(
      renderDetail("/accounts/acc-10432", {
        detail: detail({
          status: "closed",
          status_name: "Closed",
          status_behavior_class: "terminal",
          closed_at: "2026-08-14",
        }),
        access: "Full",
      }),
    );
    expect(closedHead).not.toContain(
      "Move-in hands this account&#x27;s unit to the next occupant",
    );
    // AMENDED 2026-08-11 (W4/W8 ACTION lane) — the third rewrite of this one
    // assertion, and each rewrite is hard-won law 1 doing its job. It first
    // said the payments MODULE was not built; then that the button had not been
    // WIRED. Both were true when written and neither is true now: Record
    // payment opens the S22 modal on this page and posts to
    // `POST /accounts/{id}/payments`. So it is LIVE — no title, no disabled —
    // and BR-PAY-036 is why it is gated on the role and on nothing else: a
    // payment is accepted in any account state.
    expect(head).toContain("Record payment");
    expect(head).not.toContain("has not been wired to it yet");
    expect(head).not.toContain("payments module, which is not built");
    // ⚠ **AND `Adjust` IS LIVE TOO, AS OF 2026-09-13 (`DEF-CUS-5126`).** This
    // line asserted the header still carried *"Adjustments are billing rows"*.
    // It was the fourth false refusal on this screen: `POST
    // /accounts/{id}/payments` takes `type: "adjustment"` and has since
    // `CR-059` CS-35. The assertion is INVERTED rather than deleted, so the
    // sentence cannot come back.
    expect(head).toContain("Adjust");
    expect(head).not.toContain("Adjustments are billing rows");
    expect(head).not.toContain("There is no endpoint to post one to");
  });

  it("US-CUS-008 / BR-CUS-018: only a draft offers a live Activate; an active account is disabled with the state", () => {
    expect(isDraftAccount(detail({ status_behavior_class: "non_billable" }))).toBe(true);
    expect(isDraftAccount(detail())).toBe(false);
    expect(isClosedAccount(detail({ status_behavior_class: "terminal" }))).toBe(true);

    const active = header(renderDetail("/accounts/acc-10432", { detail: detail(), access: "Full" }));
    expect(active).toContain("Only a draft account can be activated.");

    const draft = header(
      renderDetail("/accounts/acc-10432", {
        detail: detail({
          status: "pending_activation",
          status_name: "Pending activation",
          status_behavior_class: "non_billable",
        }),
        access: "Full",
      }),
    );
    expect(draft).toContain("Activate account");
    expect(draft).not.toContain("Only a draft account can be activated.");
  });

  it("BR-CUS-107: a CUT account is `non_billable` and is NOT a draft — Activate stays refused", () => {
    // ⚠ THE ONE THING THE SIXTH STATUS COULD HAVE BROKEN ON THIS PAGE.
    // BR-CUS-107 (PO 2026-08-25, closing DEF-701) adds `disconnected` in class
    // `non_billable`, so `pending_activation` is no longer the only status in
    // that class. `isDraftAccount` used to test the CLASS alone, which would
    // have made the ONE primary action on a CUT customer's page a live
    // "Activate account" — one click to put a customer with the service off and
    // the debt unpaid back to Active, around the reconnect flow BR-PAY-036 and
    // B18 §5.8.4 require ("payment confirmed → visit scheduled → restored").
    const cut = detail({
      status: "disconnected",
      status_name: "Disconnected",
      status_behavior_class: "non_billable",
    });
    expect(isDraftAccount(cut)).toBe(false);

    const head = header(renderDetail("/accounts/acc-10432", { detail: cut, access: "Full" }));
    expect(head).toContain("Only a draft account can be activated.");

    // ⚠ AND THE OTHER HALF OF BR-CUS-107, WHICH IS THE CLAUSE THE RULING ITSELF
    // FLAGS: a `non_billable` account MUST still be able to pay, because paying
    // is how a cut customer gets reconnected (BR-CUS-104). Record payment is
    // gated on the ROLE and on nothing else (BR-PAY-036).
    expect(head).toContain("Record payment");
  });

  it("DEF-CUS-5000 / B14 rule 31: the Sub-type shows the tenant's label, never the raw code", () => {
    // Measured on the running product: the Account panel printed
    // **`small_commercial`** at a clerk while the Category cell one line up
    // read `Residential`, because the code was the only thing on the wire and
    // this `Fact` had nothing else to render. B14 rule 31/32 — no database id
    // and no internal code is the visible value of a field.
    const labelled = renderDetail("/accounts/acc-10432", {
      detail: detail({
        account_type: "residential",
        account_subtype: "small_commercial",
        account_subtype_name: "Small commercial",
      }),
      access: "Full",
    });
    expect(labelled).toContain("Small commercial");
    expect(labelled).not.toContain("small_commercial");

    // ⚠ **AND THE FALLBACK IS THE CODE, NEVER A GUESS.** `account_subtypes` is
    // TENANT-DEFINED (BR-CUS-067), so a row may carry a label this deployment
    // has not seeded — and inventing one is how `government` quietly starts
    // reading as "Municipal", the substitution BR-CUS-094 forbids by name and
    // the reason `accountCategoryName` falls back the same way. A code on
    // screen is a fact about the DATA; a wrong word is a lie about it.
    const unlabelled = renderDetail("/accounts/acc-10432", {
      detail: detail({ account_subtype: "legacy_code", account_subtype_name: null }),
      access: "Full",
    });
    expect(unlabelled).toContain("legacy_code");
  });

  it("DEF-CUS-5005 / BR-CUS-430: Close out opens on a CUT account and on no other status", () => {
    // **THE BLUEPRINT'S OWN SIX-ROW TRUTH TABLE (`ACC-A05`, p27), ASSERTED AS A
    // TABLE.** Its caption is the defect: *"the only status that opens this
    // button is the one it was not written for"* — `Close out` was LIVE on
    // `pending_activation` and refused on the five that reach a clerk today,
    // because the gate named the two states that refuse
    // (`isOccupyingAccount || isClosedAccount` = `billable`,
    // `billable_base_only`, `terminal`) and let every other class through.
    // `pending_activation` is `non_billable` and fell out of both.
    //
    // ⚠ **BOTH DIRECTIONS, AND THE ALLOW ROW IS THE HALF THAT MATTERS.** A gate
    // that refuses everything passes every "is it disabled here" assertion ever
    // written — hard-won law 7's *incapable of passing*. The `disconnected` row
    // is the one that fails if a later lane tightens this to a refusal list
    // again. It cannot be proved in a browser on this fixture: the tenant seeds
    // **no** disconnected account, and a cut cannot be committed on it either
    // (see `10-scripts/cr094_wave_b_seed_cut_account.py`, which drives the real
    // services as far as a `cut` case and records the three product blockers it
    // then meets).
    const REFUSAL = "Only an account whose service has been cut is closed out.";
    const TRUTH_TABLE: ReadonlyArray<readonly [string, string, boolean]> = [
      ["active", "billable", false],
      ["marked_disconnect", "billable", false],
      ["vacation_hold", "billable_base_only", false],
      ["closed", "terminal", false],
      ["pending_activation", "non_billable", false],
      // BR-CUS-107's sixth status — the one status a close-out is for.
      ["disconnected", "non_billable", true],
    ];
    for (const [status, behaviour, opens] of TRUTH_TABLE) {
      const head = header(
        renderDetail("/accounts/acc-10432", {
          detail: detail({
            status,
            status_name: status,
            status_behavior_class: behaviour,
            closed_at: status === "closed" ? "2026-08-14" : null,
          }),
          access: "Full",
        }),
      );
      // BR-SHL-025: the control stays ON the screen either way, carrying its
      // reason — never hidden.
      expect(head, `${status}: the control must stay on screen`).toContain("Close out");
      if (opens) {
        expect(head, `${status}: Close out must be LIVE`).not.toContain(REFUSAL);
      } else {
        expect(head, `${status}: Close out must be refused`).toContain(REFUSAL);
      }
    }
  });

  it("US-CUS-008 §6 / BR-SHL-044: one page header, exactly one primary, and no head of its own", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail(), access: "Full" });
    expect(html).toContain("page-header");
    expect(html).toContain("page-header-tabs");
    expect((header(html).match(/data-variant="primary"/g) ?? []).length).toBe(1);
    expect(html).not.toContain("cus-head");
  });

  it("US-CUS-008 TC-3 / BR-SHL-011: every one of the twelve tabs is URL state", () => {
    // ⚠ **AMENDED 2026-09-02 (`CR-059` CS-37 · task 28): NINE TABS BECAME TEN.**
    // S21 gains **Credits** — every credit note on the account, with the bill
    // each came from — immediately after Payments. Before it, the only way to
    // answer *"show me every credit note on this account"* was to open the
    // customer's bills one at a time. It sits beside Payments because that is
    // where the question is asked: what they paid and what they were let off,
    // in one conversation. r10 draws nine; this is a divergence from r10 and is
    // stamped as one rather than quietly absorbed.
    expect([...ACCOUNT_TAB_IDS]).toEqual([
      "overview",
      "bills",
      "payments",
      "credits",
      // ⚠ **AMENDED 2026-09-02 (`CR-059` CS-23 · task 6): TEN TABS BECAME
      // ELEVEN.** S21 gains **Plan** — every instalment of the account's live
      // payment plan, paid or outstanding, with the day it was met. It sits
      // after Credits because the three money tabs answer one conversation:
      // what they paid, what they were let off, and what they agreed to pay in
      // instalments. It could not have existed before 2026-09-01: nothing
      // marked an instalment paid, so a customer paying perfectly on time
      // would have read as behind on every row.
      "plan",
      "usage",
      "meters",
      // ⚠ **AMENDED 2026-09-04 (`CR-070` wave O): ELEVEN TABS BECAME TWELVE.**
      // S21 gains **Work** — the jobs on this account and at the address it
      // shares, each row saying which. It sits after Meters and before the
      // money because a job is about the thing AT the address (a meter to
      // exchange, a final read to take) rather than about what is owed. It
      // exists because the PO ruled the connection detail one screen too many:
      // *"you cannot have two differnt screen - this is an integration
      // problem"*, so the build's work is reached from the account and from
      // the premises instead of from a parallel destination.
      "work",
      "adjustments",
      "documents",
      "notes",
      "audit",
    ]);
    expect(accountTabs(t).map((tab) => tab.label)).toEqual([
      "Overview",
      "Bills",
      "Payments",
      // Rendered from `defaultValue` until the catalogue entry lands — the key
      // itself on a clerk's screen would be B14 rule 32 (no internal code in
      // clerk-facing copy), which is the failure this fallback prevents.
      "Credits",
      // ⚠ RENAMED 2026-09-07 (`DEF-CUS-4631`) — it read "Plan", and on this
      // very screen the header card says **"Plan from unit — Sample —
      // Residential v1"**, which is the RATE plan. Two different things under
      // one word: the PO read the tab and asked *"above it says there is plan
      // and in plan section - it says it dont have any plan - why?"*. Both
      // statements were true and together they were nonsense. The tab holds the
      // PAYMENT plan — an instalment arrangement — and now says so.
      //
      // ⚠ AND FOUR CATALOGUES HAD ALREADY FIXED IT WITHOUT ENGLISH NOTICING:
      // de "Ratenplan", fr-FR "Échéancier", ja-JP "分割払い", ko-KR "분납" —
      // every one of them the local word for an INSTALMENT plan. B14 rule 35
      // asks for a catalogue written in its own language, and those four
      // translators had done exactly that and landed on the right meaning
      // while the English they were translating stayed ambiguous.
      "Payment plan",
      "Usage",
      "Meters",
      // ⚠ CR-070 wave O — and its sentence is in all ELEVEN catalogues in the
      // commit that added the tab, so unlike Credits above it needs no
      // `defaultValue` at all. `TAB_LABEL_FALLBACK` gained no entry for it.
      "Work",
      "Adjustments",
      "Documents",
      "Notes",
      "Audit",
    ]);
    // A deep link opens ON that tab; an unknown one falls back to the first
    // rather than erroring (BR-SHL-011's spirit).
    // AMENDED 2026-08-11 (W3 billing lane): the Bills tab is LIVE and renders
    // billing's own S30 list scoped to this account, so the marker on it is
    // that list's exit link rather than the old arrives-with panel.
    expect(renderDetail("/accounts/acc-10432?tab=bills", { detail: detail() })).toContain(
      "All bills",
    );
    // ⚠ `Recent bills` → `History`: B14 rule 41 (PO 2026-09-13) — the blueprint
    // heads this group `HISTORY`. The same panel, renamed by the drawing.
    expect(renderDetail("/accounts/acc-10432?tab=nonsense", { detail: detail() })).toContain(
      "History",
    );
  });

  it("US-CUS-008 TC-2 / BR-CUS-054: an account with NO customer link renders no chip and invents none", () => {
    // AMENDED 2026-08-11 (US-CUS-019 lane). This used to assert the chip could
    // not exist because the entity had no tables. It has them now — so what is
    // asserted is the honest half that survives: an account carrying no link
    // (every account created before the entity, and every imported row that
    // named neither a reference nor a name) shows NOTHING rather than a
    // customer conjured from its contact.
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    expect(html).not.toContain("cus-customer-chip");
    expect(html).not.toContain("All accounts for this customer");
    // ⚠ AMENDED 2026-08-24 — the panel is DELETED (PO ruling, walking the
    // deployed build: *"on account details screen - we dont want -"*, quoting
    // it back in full). It was TRUE: the BR-CUS-019 duplicate check at S18
    // step 1 is genuinely unbuilt. What the ruling settles is that a build
    // backlog does not belong in a grey box on an operator's screen.
    //
    // The gap itself is not lost with the box — it is a real product gap and
    // belongs in the defect register, which is where a backlog goes. This case
    // keeps the assertions above, which are the ones about THIS SCREEN: no
    // chip, and no invented customer name, when the account has no link.
    expect(html).not.toContain("The customer record, and what it still cannot do");
  });

  it("US-CUS-008 TC-2 / BR-CUS-054: a LINKED account lists every account of that customer", () => {
    // The EP-CUS-07 §4 landlord: Bluebonnet Property Group LLC, three suites,
    // ONE customer. This is the capability the rule names, and until the entity
    // landed it could not be rendered at all.
    const html = renderDetail("/accounts/acc-10432", {
      detail: detail({
        customer: {
          id: "cus-118",
          kind: "company",
          display_name: "Bluebonnet Property Group LLC",
          external_ref: "CUST-118",
          accounts: [
            { id: "acc-10432", account_no: "A-10432" },
            { id: "acc-10433", account_no: "A-10433" },
            { id: "acc-10434", account_no: "A-10434" },
          ],
        },
      }),
    });
    expect(html).toContain("All accounts for this customer");
    expect(html).toContain("Bluebonnet Property Group LLC");
    // The OTHER two are links; this account is not a link to itself.
    expect(html).toContain('href="/brazosbend/accounts/acc-10433"');
    expect(html).toContain('href="/brazosbend/accounts/acc-10434"');
    expect(html).not.toContain('href="/brazosbend/accounts/acc-10432"');
  });

  it("US-CUS-008 §1: every rail action is a control now — live, or disabled with the reason", () => {
    // AMENDED 2026-08-11 (W4/W8 ACTION lane). This test used to assert the
    // OPPOSITE — that seven actions were named in one prose panel rather than
    // drawn as seven dead buttons — and that was the right call while none of
    // them had a service to call. Four do now (Record payment, Add note,
    // Change plan, and the move pair), so the panel is gone and the five that
    // still cannot be honoured carry their OWN reason on their OWN control,
    // which is where BR-SHL-025 wants it. The panel's strings are deleted from
    // all eleven catalogues rather than left behind.
    const html = renderDetail("/accounts/acc-10432", { detail: detail(), access: "Full" });
    expect(html).not.toContain("Account actions that arrive later");

    // LIVE: no `disabled`, no `title` — the control does what it says.
    // ⚠ AMENDED (CR-030 W3 · 3.3): Record payment is the ONE PRIMARY now, as
    // r10 draws it. It could not be while payments did not exist; the endpoint
    // and the S22 modal are both live, so the reason expired and the button
    // moved. Activate — the old primary — is a secondary, because a control
    // only a pending-activation account can press is not the page's primary
    // action on the other four statuses.
    expect(header(html)).toMatch(/data-variant="primary"[^>]*>Record payment<\/button>/);
    // r10's action stack is `Record payment` · `Adjust` · `Move-out`, in that
    // order: the two that follow the primary lead the secondary rail.
    expect(header(html)).toContain("Adjust");
    expect(header(html)).toContain("Move-out");
    expect(header(html)).toContain("Activate account");
    // ⚠ AMENDED (CR-030 W3 · 3.2 · BR-SHL-045, 2026-08-24). `Add note` and
    // `Change plan` were asserted HERE, as worded secondaries, until the PO
    // ruled the icon rail. They are still live and still on the screen — as two
    // of the rail's seven glyphs, below the metric block — so what changes is
    // WHERE the assertion lives, not whether the feature exists. The rail's own
    // describe block below owns them now, and the header must NOT still draw a
    // second worded copy of either.
    // ⚠ ASSERTED ON THE HEADER'S BUTTONS AND NOT ON ITS RAW TEXT
    // (`DEF-CUS-4631`, 2026-09-07). These read `not.toContain(">Payment plan<")`
    // until the Plan tab was renamed **Payment plan** — at which point the tab
    // strip, which is inside the header slice, made the string appear and the
    // assertion failed over a screen that was perfectly correct. A tab and a
    // button are different controls; what this case is actually about is that
    // no WORDED BUTTON duplicates a rail glyph, so it asks that question.
    const headerButtonLabels = headerCommandLabels(html);
    for (const moved of ["Add note", "Change plan", "Payment plan"]) {
      expect(headerButtonLabels).not.toContain(moved);
    }

    // DISABLED WITH THE REASON, and the reason names the blocker rather than
    // saying "soon".
    // ⚠ AMENDED (CR-016, 2026-08-19): the reason still names the blocker rather
    // than saying "soon", and it now does so without our open-question numbers.
    // ⚠ AMENDED AGAIN (DEF-CUS-4631, 2026-09-07) — **AND THIS BLOCK IS WHY THE
    // DEFECT SURVIVED THREE WEEKS.** It used to assert, word for word, the three
    // sentences the PO found false on the screen: *"Which account a goodwill
    // credit should be charged to has not been decided"*, *"Reprinting a bill is
    // not available yet"* and *"The notice history has no table"*. Every one of
    // them had been answered — `OQ-105`/`OQ-168`, `OQ-103`/`OQ-169`, and
    // `OQ-133`/`OQ-136`/`OQ-137`, all CLOSED on 2026-08-12 — so this test was
    // not checking the product against the rules, it was PINNING the product to
    // a set of expired rules and going green over the mistake. A test that
    // asserts a refusal's exact words holds that refusal in place; the assertion
    // that survives is the one that says the control REFUSES and lets the reason
    // be derived. `accountRailHoldExpiry.test.ts` now carries the other half —
    // the check that fails when a hold comes true.
    expect(html).not.toContain("OQ-1");
    // The ONE refusal on this rail that is still true: nothing renders a
    // statement. Asserted by the SHAPE (a disabled ✉ with some reason), not by
    // the sentence, so re-wording it is not a test change.
    // ⚠ `DEF-CUS-9107` — REWORDED `e14d22004` (2026-09-13): *"Statements are
    // not built yet"* stopped being true when the statement read and its server
    // half landed; the glyph is still held for ONE missing hunk, and its reason
    // says only that. Still asserted ON the glyph, not anywhere on the page.
    expect(html).toMatch(/aria-label="Send statement" title="This icon is not ready yet\."/);
    expect(html).not.toContain("Statements are not built yet.");
    // The three that were false are no longer refused ON THESE GROUNDS. Asserted
    // NEGATIVELY and by the expired words, because the failure being guarded
    // against is the sentences coming back.
    expect(html).not.toContain("has not been decided");
    expect(html).not.toContain("The notice history has no table");
    expect(html).not.toContain("Reprinting a bill is not available yet");

    // ⚠ AMENDED (CR-030 W3 · 3.2, 2026-08-24): FIVE header controls, not twelve.
    // Seven of the twelve became the icon rail (BR-SHL-045) and NONE of them
    // was dropped — the arithmetic is asserted rather than described, because
    // "nothing was lost" is exactly the claim a rail replacement can get wrong.
    // What stays worded: the ONE primary (Record payment) plus Adjust and
    // Move-out (r10's action stack) plus Activate and Move-in, this
    // deployment's two extra live writes, for which r10 draws no glyph.
    // ⚠ AMENDED AGAIN (DEF-724, 2026-08-27): SIX worded controls, not five.
    // **Close out is the SIXTH and it is NEW, not one of the twelve moved
    // around.** The PO ruled a separate terminal act on 2026-08-27 — *"A
    // disconnected customer can never be closed - Add a separate close-out
    // act"* — and r10 draws no glyph for it, exactly as it draws none for
    // Activate or Move-in, so it stays worded rather than inventing an eighth
    // rail icon (BR-SHL-045's seven are r10's seven exactly).
    //
    // The `12` below is UNCHANGED on purpose: it is the arithmetic that proves
    // the rail replacement lost nothing from r10's original twelve. A control
    // that never existed in r10 must not be added to it, or the claim that
    // sum is making stops being checkable.
    // ⚠ AMENDED (CR-183-BRC10, 2026-10-14): SEVEN worded controls. **Temporary
    // stop is the SEVENTH and it is NEW** (PO rulings B1–B4 — a clerk starts,
    // moves or ends a hold for a customer on the phone), worded for Close
    // out's reason: r10 draws no glyph for it.
    expect((header(html).match(/<button/g) ?? []).length).toBe(7 + ACCOUNT_TAB_IDS.length);
    expect(html).toContain("Temporary stop");
    expect(railButtons(html)).toHaveLength(ACCOUNT_RAIL_ACTIONS.length);
    // ⚠ **r10's TWELVE, PLUS `ACC-S16`'s ONE, IS THIRTEEN (2026-09-12).** The
    // sum this line protects is *"the rail replacement lost nothing from r10's
    // original twelve"*, and it still holds: five stay worded and r10's seven
    // are all still glyphs. What is +1 is a control r10 never drew, because
    // nothing in r10 could write to a customer at all — which is finding F11.
    expect(5 + ACCOUNT_RAIL_ACTIONS.length).toBe(13);
    expect(html).toContain("Close out");
  });

  it("A18 §3/§4: a pending read is the shared skeleton and a failed one the shared retry card", () => {
    const html = renderDetail("/accounts/acc-10432");
    expect(html).toContain("skeleton");
    expect(html).not.toMatch(/<h1[\s>]/);
  });

  it("US-CUS-008 §5: the pure header helpers answer without a browser", () => {
    expect(accountRollupLine(detail())).toBe("1408 Elm St · A");
    expect(accountRollupLine(detail({ premise: null }))).toBe("A");
    expect(accountRollupLine(detail({ premise: null, unit_label: null }))).toBeNull();
    expect(accountHeadline(detail(), t)).toBe("Miller, Sarah");
    // No contact at all still names the account rather than rendering blank.
    expect(accountHeadline(detail({ contacts: [], name: null }), t)).toBe("A-10432");
    expect(accountDetailPath("acc-10432")).toBe("/accounts/acc-10432");
  });

  it.todo(
    "US-CUS-008 TC-6 (isolation): a Lone Star Ridge session never resolves a Brazos Bend account id — server/RLS scope (G5)",
  );
  it.todo(
    "US-CUS-008: clicking Activate posts and re-renders the active header — the click path needs a browser (the mutation is asserted through the endpoint wrapper's own suite)",
  );
  it("BR-CUS-068: S21 says a master account IS one, and an ordinary account stays silent", () => {
    // A master account is served by the SAME `GET /accounts/{id}` with the same
    // shape — so without this pill the one fact that changes who pays the bill
    // is invisible on the screen that shows the bill.
    const master = renderDetail("/accounts/acc-10432", {
      detail: detail({ kind: "master", name: "Miller Property LLC" }),
    });
    // ⚠ **`Master` → `Master account`, AND THE REGULAR ACCOUNT NOW SAYS SO TOO
    //    (PO 2026-09-13).** The blueprint draws a KIND chip on every account —
    //    `Regular account` on the drawn one — so the positive-only pill became
    //    one chip from one vocabulary. `BR-CUS-068`'s reason is unchanged and is
    //    what this case still guards: the fact that changes who pays the bill
    //    must be on the screen that shows the bill.
    expect(header(master)).toMatch(/<span class="pill[^"]*">Master account<\/span>/);
    const regular = renderDetail("/accounts/acc-10432", { detail: detail() });
    expect(header(regular)).not.toContain(">Master account<");
    expect(header(regular)).toContain(">Regular account<");
  });
});

describe("US-CUS-009 — the Overview tab's panels", () => {
  it("DEF-CUS-9121: the utility's own fields are on the Overview, label and value", () => {
    // ⚠ Dropped by the 2026-09-13 regrouping with its imports left behind, so
    // a value recorded in the New Account wizard was shown nowhere on the
    // account. Every other case here seeds NO field, which is exactly why
    // nothing noticed: the view renders nothing for a utility with none.
    const html = renderDetail("/accounts/acc-10432", {
      detail: detail({ custom_data: { meter_room: "Basement B" } }),
      customFields: [
        {
          id: "cf-1",
          key: "meter_room",
          label: "Meter Room",
          help_text: "",
          data_type: "text",
          options: [],
          is_required: false,
          display_order: 0,
          placement: { S21: "view" },
        },
      ],
    });
    const group = html.slice(html.indexOf('data-overview-group="account-setup"'));
    expect(group).toContain("Meter Room");
    expect(group).toContain("Basement B");
  });

  it("US-CUS-009 TC-2 / BR-CUS-045: the customer panel renders the contact, with the id masked to its last four", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    expect(html).toContain("sarah.miller@example.com");
    expect(html).toContain("+1 (512) 555-0184");
    expect(html).toContain("04/12/1987"); // BR-SHL-034, one date path
    // The server stores four digits and nothing more — so four is all there is
    // to show, and the panel says that rather than implying a hidden fuller id.
    expect(html).toContain("••••4218");
    expect(html).toContain("last four digits");
    expect(maskedGovId("4218")).toBe("••••4218");
    expect(maskedGovId(null)).toBeNull();
    expect(primaryContact(detail().contacts)?.full_name).toBe("Miller, Sarah");
  });

  it("US-CUS-009 TC-3 / BR-CUS-057 / BR-CUS-058: interest accrued and the credit tier are absent WITH their rules, never 0 or 'A'", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    // ⚠ **THIS PINNED "No column for it" AND THAT CLAIM HAD GONE FALSE
    // (DEF-3486).** BR-CUS-057's accrual landed on 2026-09-03 —
    // `apps/customers/deposit_interest.py` plus the published selector
    // `deposit_interest_accrued` — so there IS a figure; what is missing is
    // that `account_detail_dict` does not put it in the payload. The property
    // this case is really about is unchanged and still asserted: an absence
    // WITH its rule, and never an invented `$3.20`.
    expect(html).toContain("Not accrued");
    expect(html).toContain("BR-CUS-057");
    expect(html).toContain("Not computed");
    expect(html).toContain("BR-CUS-058");
    expect(html).not.toContain("$3.20");
    // The deposit figure IS served, and the qualifier says where it comes from.
    // It said "no deposit path writes this column yet" until 2026-09-03 and
    // DEF-177 closed that gap: a cleared deposit payment moves the register
    // through customers' own published writer.
    expect(html).toContain("a deposit shows here once its payment clears");
  });

  it("DEF-CUS-4625 / BR-CUS-028: the portal panel READS the state, and invents none of it", () => {
    // ⚠ **THIS CASE USED TO ASSERT THE DEFECT.** It required the sentence
    // *"out of scope for this version"* — true when it was written, false
    // from the day CR-068 shipped the portal and CR-082 seeded it, and the
    // Product Owner found it on an account that HAS a login: *"I have login
    // portal for this account - portal access says…"*. A test that pins a
    // typed sentence keeps that sentence alive; this one reads the payload.
    const html = renderDetail("/accounts/acc-10432", {
      detail: detail({
        paperless: true,
        sms_reminders: false,
        portal_access: {
          logins: 1,
          locked: 0,
          last_sign_in: "2026-09-05",
          unreadable: [],
        },
      }),
    });
    expect(html).toContain("Portal access");
    expect(html).toContain("1 can sign in");
    expect(html).toContain("Last sign-in");
    // NEGATIVE — the three claims the old sentence made, all of them false.
    expect(html).not.toContain("out of scope for this version");
    expect(html).not.toContain("never built");
    // ⚠ **THIS ASSERTED THE PRINT-FLOOR SENTENCE AND IT HAS LEFT THE SCREEN
    //    (PO 2026-09-13, B14 rule 33).** It was rationale, and it had been
    //    ORPHANED since the eleven-group rework moved `Paperless` and `Text
    //    reminders` into BILLING PREFERENCES — it explained two rows that were
    //    no longer beside it. `BR-BIL-036` is unchanged and is recorded at the
    //    panel; what this case guards is the DERIVED state, which is the whole
    //    of `DEF-CUS-4625`, so the negative assertions below still bite.
    expect(html).not.toContain("Bills are always printed as well.");
  });

  it("DEF-CUS-4625: never signed in and could-not-be-read are DIFFERENT sentences", () => {
    // The distinction the old sentence flattened. `null` means nobody has
    // ever signed in — a fact about this customer. `unreadable` means the
    // walk could not answer — a fact about us. A screen that printed one for
    // the other is how *"no login date exists"* survived the portal landing.
    const never = renderDetail("/accounts/acc-10432", {
      detail: detail({
        portal_access: { logins: 0, locked: 0, last_sign_in: null, unreadable: [] },
      }),
    });
    expect(never).toContain("Nobody has signed up");
    expect(never).toContain("Never signed in");
    expect(never).not.toContain("Could not be read");

    const blind = renderDetail("/accounts/acc-10432", {
      detail: detail({
        portal_access: {
          logins: null,
          locked: null,
          last_sign_in: null,
          unreadable: ["logins", "last_sign_in"],
        },
      }),
    });
    expect(blind).toContain("Could not be read");
    expect(blind).not.toContain("Never signed in");
  });

  it("US-CUS-009 TC-1/TC-6 / BR-CUS-034: the recent-bills panel READS billing's list; the usage trend is still a frame", () => {
    // ⚠ AMENDED (CR-030 W3 · 3.4). Recent bills was an arrives-with citing
    // DEF-474 — the row whose whole complaint is that the panel said bills had
    // no read endpoint while this page's own Bills tab was reading one. It is
    // a real panel now, over billing's `GET /invoices?f.account_id=`
    // (BR-CUS-034: billing's list, not a customers copy of it).
    const html = renderDetail("/accounts/acc-10432", {
      detail: detail(),
      bills: [bill(), bill({ id: "inv-2", invoice_no: "BL-2606-018091", total: "228.100000" })],
    });
    // ⚠ `Recent bills` → `History` (B14 rule 41, PO 2026-09-13).
    expect(html).toContain("History");
    expect(html).toContain("All bills →");
    expect(html).toContain("BL-2607-018204");
    expect(html).toContain("$247.30");
    expect(html).not.toContain("247.300000");
    // r10 draws a USAGE column here and an invoice ROW carries no quantity —
    // the cell states that rather than opening every bill on an overview.
    // ⚠ **REWRITTEN 2026-09-13 BY B14 RULE 33's SWEEP.** Twenty words cut to
    // six; what the cell states is where the usage IS, not why it is not here.
    expect(html).toContain("Usage sits on the bill&#x27;s lines.");

    // ⚠ **THE USAGE TREND IS NO LONGER A FRAME (DEF-3487).** This case pinned
    // the sentence *"no endpoint publishes that"* and the `DEF-747` tracking
    // id, and both had stopped being true: CR-030 W3 task 3.8 landed
    // `GET /accounts/{id}/usage` and `AccountUsageTab`, which the Usage tab on
    // this very screen has drawn ever since. The panel is now that component,
    // over a twelve-month window, so what is asserted is the REAL thing:
    // the heading, the link to the tab, and the chart component's own frame
    // rather than a stated absence.
    //
    // The static first paint is the query's PENDING state — react-query starts
    // a server render optimistically — which is exactly what the Usage tab's
    // own suite asserts one file over, and it is why this reads for the
    // loading sentence rather than for bars.
    expect(html).not.toContain("no endpoint publishes that");
    expect(html).not.toContain('data-tracks="DEF-747"');
    expect(html).toContain("Usage trend");
    expect(html).toContain("Details →");
    expect(html).toContain("Loading usage");
    // The payment method keeps its sentence AND gains r10's control, disabled
    // with its reason (BR-SHL-025) rather than absent.
    expect(html).toContain("Payment method");
    expect(html).toContain("Update method");
    // ⚠ **REWRITTEN 2026-09-13 BY B14 RULE 33's SWEEP.** Twenty-six words
    // naming which module keeps the method and why, cut to the five-word fact.
    expect(html).toContain("No stored method to update.");
    expect(html).not.toContain("which keeps none for an account in this version");
  });

  it("US-CUS-009 TC-1 (negative): a bill list that has not arrived draws no table and no zero", () => {
    // Nothing seeded: SSR renders the pending state. A panel that drew an empty
    // table here would assert "this account has never been billed".
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    expect(html).toContain("Loading bills…");
    expect(html).not.toContain("BL-2607-018204");
    expect(html).not.toContain("07-A");
  });

  it("US-CUS-009 §5: the account panel shows the attributes the endpoint DOES serve, with their caveat", () => {
    const html = renderDetail("/accounts/acc-10432", {
      detail: detail({ tax_exempt: true, tax_exempt_ref: "TX-4491", preferred_language: "es" }),
    });
    // ⛔ **DEF-684 — THE SERVED NAME, NOT A CATALOGUE KEY.** This passed over the
    // defect: `Residential` had an i18n key and the four categories BR-CUS-094
    // added did not, so the panel printed `builder_developer` for them and no
    // assertion could see it. The second case below is the one that bites.
    expect(html).toContain("Residential");
    expect(html).not.toContain("<dd>residential</dd>");
    expect(html).toContain("TX-4491");
    expect(html).toContain("Returned payments");
    // ⚠ **REWRITTEN 2026-09-13, B14 rule 33's sweep — NOT DELETED.** This used
    // to assert *"written by the returned-mail workflow"*, the ACCOUNT SETUP
    // hint. That sentence was RATIONALE (why the two fields read as their
    // column default) and rule 33 makes rationale zero words on screen; the
    // Overview drawing carries no hint under this heading either. The hint and
    // its key are gone, so the assertion now holds the hint to its ABSENCE —
    // which is the half that cannot rot back into a tautology.
    expect(html).not.toContain("written by the returned-mail workflow");
    expect(html).not.toContain("customers.account.panel.accountHint");

    // A category BR-CUS-094 ADDED. It has no `customers.accounts.category.*`
    // key and never will — the name rides with the code.
    const added = renderDetail("/accounts/acc-10432", {
      detail: detail({ account_type: "builder_developer" }),
    });
    expect(added).toContain("Builder or developer");
    expect(added).not.toContain("builder_developer");
  });

  it("US-CUS-009 §5: an account with no mailing row says 'same as service', which is not the same as 'no address'", () => {
    const same = renderDetail("/accounts/acc-10432", { detail: detail({ addresses: [] }) });
    expect(same).toContain("Same as the service address.");
    const mailed = renderDetail("/accounts/acc-10432", {
      detail: detail({
        addresses: [
          {
            id: "ad-1",
            kind: "mailing",
            line1: "PO Box 88",
            city: "Katy",
            state: "TX",
            postal_code: "77494",
          },
        ],
      }),
    });
    expect(mailed).toContain("PO Box 88, Katy, TX, 77494");
    expect(
      addressLine({
        id: "ad-2",
        kind: "mailing",
        line1: "PO Box 88",
        city: null,
        state: null,
        postal_code: null,
      }),
    ).toBe("PO Box 88");
  });

  it("US-CUS-009 TC-5 (negative): no contact on file is stated, never rendered as blank fields", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail({ contacts: [] }) });
    expect(html).toContain("No contact has been recorded on this account yet.");
    expect(html).not.toContain("sarah.miller@example.com");
  });

  it.todo(
    "US-CUS-009 TC-2: editing the phone propagates to every linked account — the customer entity has no table, so there is nothing to propagate through",
  );
  it.todo(
    "US-CUS-009 TC-7 (isolation): the Overview read is tenant-scoped — server/RLS scope (G5)",
  );
});

describe("US-CUS-010 — the financial tabs render their boundary, not an empty table", () => {
  it("US-CUS-010 TC-1/TC-2/TC-3: Bills reads billing's own list; Payments and Adjustments name what they wait for", () => {
    // AMENDED 2026-08-11 (W3 billing lane). The Bills tab is no longer an
    // arrives-with panel: it is billing's S30 list scoped by `f.account_id`
    // (11b §2.6), which is why it draws a table where the other two do not.
    // BR-CUS-034 still holds — customers owns no copy of these rows, it embeds
    // the owning module's own list. The bills-list assertions themselves live
    // with that list, in features/billing/BillsPage.test.tsx.
    const bills = renderDetail("/accounts/acc-10432?tab=bills", { detail: detail() });
    expect(bills).toContain("All bills");
    expect(bills).toContain("/brazosbend/billing?sort=issue_date&amp;dir=desc&amp;f.account_id=");
    // ⚠ **REWRITTEN 2026-09-13, B14 rule 33's sweep.** The Bills tab's awaits
    // block used to be titled *"Columns this tab cannot show"* over 31 words
    // explaining why the usage behind a bill is not summed — the PO pasted
    // both back as copy they do not want on screen. The TITLE is now the fact
    // at three words and the body is one six-word sentence. The key is
    // unchanged, so the render site on the Bills tab is another lane's to
    // decide on; what is asserted here is the COPY.
    expect(bills).toContain("Usage not shown");
    expect(bills).not.toContain("Columns this tab cannot show");

    // AMENDED 2026-08-11 (W4/W8 ACTION lane): the Payments tab CALLS the ledger
    // now. It is not a customers read model — BR-CUS-034 forbids one — it is
    // the payments module's own S33 table scoped by `f.account_id`, the same
    // shape the Bills tab takes above. The old panel said "this tab does not
    // read that ledger yet"; it does, so the string is deleted from all eleven
    // catalogues rather than left contradicting the table beside it.
    const payments = renderDetail("/accounts/acc-10432?tab=payments", { detail: detail() });
    expect(payments).not.toContain("This tab does not read that ledger yet");
    expect(payments).toContain("Applied to"); // the S33 column set, embedded
    expect(payments).not.toContain("DEPO-4218");

    const adjustments = renderDetail("/accounts/acc-10432?tab=adjustments", { detail: detail() });
    // The tab is still a FRAME and its sentence now says WHY — two of r10's six
    // columns have no store anywhere (`DEF-CUS-5136`: the reason lives only in
    // the pruned audit log, `OQ-BIL-12354`, and nothing records an approver,
    // `OQ-RBS-1739`). What it no longer says is that no endpoint exists.
    // ⚠ `DEF-CUS-9107` — SINCE `32f17b2d2` (2026-09-13) THE TAB LISTS REAL
    // ADJUSTMENTS in its six drawn columns, with *New adjustment* above them;
    // the sentence sending the clerk to the Payments tab was deleted with the
    // reason for it. Its rows are `AccountAdjustmentsTab.test.tsx`'s subject.
    expect(adjustments).toContain("New adjustment");
    for (const heading of ["Adjustment #", "Reason", "Applied to", "Approved by"]) {
      expect(adjustments).toContain(heading);
    }
    expect(adjustments).not.toContain("Adjustments show on the Payments tab");
    expect(adjustments).not.toContain("No endpoint lists or posts one");
    expect(adjustments).not.toContain("ADJ-142");
  });

  it("US-CUS-010 TC-5 (negative): no tab offers an edit or a create on a financial row", () => {
    for (const tab of ["bills", "payments", "adjustments"]) {
      const html = renderDetail(`/accounts/acc-10432?tab=${tab}`, {
        detail: detail(),
        access: "Full",
      });
      // Only the header's four controls exist on these tabs — no "+ Record
      // payment" or "+ New adjustment" toolbar button is drawn onto nothing.
      expect(html).not.toContain("+ New adjustment");
      expect(html).not.toContain("+ Record payment");
    }
  });

  it.todo(
    "US-CUS-010 TC-4: the Open filter on a fully paid account renders zero-results — the tab has no table until billing lands",
  );
  it.todo(
    "US-CUS-010 TC-6 (isolation): the read models re-check the tenant — server/RLS scope (G5)",
  );
});

describe("US-CUS-011 — the operational tabs", () => {
  it("US-CUS-011 TC-2 / CR-030 3.9: the Meters tab draws r10's eight columns from the ASSETS module", () => {
    // ⚠ AMENDED (CR-030 W3 · 3.9). This was a bullet list of meter numbers
    // under the hint "meter type, install date, multiplier and the last read
    // live in the asset registry — open a meter to see them". CR-028 serves
    // `GET /assets/{id}` and `GET /assets/{id}/reads`, so the tab reads them:
    // one request per meter, through the owning module (BR-CUS-034), never a
    // customers-side copy of an assets row.
    const html = renderDetail("/accounts/acc-10432?tab=meters", {
      detail: detail(),
      assets: { "ast-4021": asset() },
      reads: { "ast-4021": [read(), read({ read_id: "r-2", date: "2026-07-03T06:12:00Z" })] },
    });
    // ⚠ `DEF-CUS-9107` — **THE TAB IS ITS DRAWING SINCE `97e4edb8d`
    // (2026-09-13, B14 rule 41, `ACC-T07`)** and has its own test file,
    // `AccountMetersTab.test.tsx`, which asserts the ten drawn columns cell by
    // cell, the read formatting and the read log (a ROW ACTION now, `?meter=`,
    // not a table beneath). What THIS page case owns is that `?tab=meters`
    // mounts that tab with the asset the registry answered with.
    expect(html).toContain("M-4021");
    expect(html).toContain('href="/brazosbend/assets/ast-4021"');
    for (const heading of [
      "Meter #",
      "Service",
      "Meter type",
      "Read method",
      "Installed",
      "Multiplier",
      "Last read",
      "Read on",
      "Status",
    ]) {
      expect(html).toContain(heading);
    }
    // …filled from the asset, not from this screen.
    expect(html).toContain("Healthy");
    // The superseded hint stays deleted.
    expect(html).not.toContain("Meter type, install date, multiplier and the last read");
  });

  it("US-CUS-011 TC-2 (negative): a registry that did not answer states the absence, never a value", () => {
    // Nothing seeded for the asset: every registry column is a dash carrying
    // its reason, and no plausible type or multiplier is drawn.
    const html = renderDetail("/accounts/acc-10432?tab=meters", { detail: detail() });
    // ⚠ `DEF-CUS-9107` — the drawn tab (`97e4edb8d`) builds its rows FROM the
    // registry's answer, so a static render — where the registry never
    // answers — draws the table and no row. What must hold is the negative:
    // no plausible value is invented for a meter nobody has described. The
    // FAILED registry's own statement is `AccountMetersTab.test.tsx`'s *"a
    // meter whose registry did not answer STATES it rather than drawing
    // blanks"*, over a view the hook marks `assetFailed`.
    expect(html).toContain("Meters on this unit");
    expect(html).not.toContain("Electric meter");
    expect(html).not.toContain("Itron OpenWay CENTRON");
    expect(html).not.toContain("43,148");
    expect(html).not.toContain("so its service, type, install date and multiplier");
  });

  it("US-CUS-011 §5: the service agreements table renders started/ended through the shared date cell", () => {
    // ⚠ `DEF-CUS-9107` — ON OVERVIEW since `97e4edb8d` (2026-09-13, B14 rule
    // 41): *"The services this account holds are a separate fact and live in
    // the Service group on Overview."* One table, two hosts became one host.
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    const group = html.slice(html.indexOf('data-overview-group="service"'));
    expect(group).toContain("02/14/2024");
    expect(group).toContain("Still open");
    const meters = renderDetail("/accounts/acc-10432?tab=meters", { detail: detail() });
    expect(meters).not.toContain("Services on this account");
  });

  it("US-CUS-011 TC-1: the Usage tab draws no chart and no average from nothing", () => {
    const html = renderDetail("/accounts/acc-10432?tab=usage", { detail: detail() });
    // AMENDED 2026-08-24 (CR-030 W3 · 3.8, BR-MET-106). This case used to pin
    // the ARRIVES-WITH sentence — "The reads list cannot be narrowed to this
    // account yet" — which was stale twice over: it blamed a reads filter
    // CR-028 shipped, and it cited DEF-475, which is closed. The tab is now
    // AccountUsageTab and that sentence is gone, so pinning it would be
    // asserting the absence of a feature that exists (hard-won law 1).
    //
    // WHAT THIS CASE IS FOR, unchanged and still worth having: this page must
    // not fabricate a figure when nothing has been calculated. The assertions
    // are deliberately NEGATIVE — they hold before and after the locale fan-in,
    // where an assertion on the empty-state COPY would flip twice. The positive
    // rendering contract lives in AccountUsageTab.test.tsx, which owns it.
    expect(html).not.toContain("The reads list cannot be narrowed to this account yet");
    expect(html).not.toContain("628 kWh");
    expect(html).not.toContain("+8.2%");
    expect(html).not.toContain("0 kWh"); // absent is not zero — BR-MET-106
  });

  it("US-CUS-011 TC-3/TC-4: Notes is LIVE and writes; Documents still offers no control that saves nowhere", () => {
    // AMENDED 2026-08-11 (W4/W8 ACTION lane). `account_notes` exists now
    // (migration 0007, BR-CUS-035) and the tab is one of exactly two things on
    // S21 that customers owns outright — so the claim "Account notes have no
    // table and no endpoint" is deleted from all eleven catalogues rather than
    // left beside the Add-note button.
    const notes = renderDetail("/accounts/acc-10432?tab=notes", { detail: detail(), access: "Full" });
    expect(notes).not.toContain("Account notes have no table and no endpoint.");
    expect(notes).toContain("Add note");
    // AMENDED 2026-08-16 (unreachable-screens lane). This used to assert
    // "A note is pinned when it is written." — the tab's honest statement while
    // the shared client had no PATCH verb, so the pin could only be set at
    // creation. The verb landed and pin/unpin are live, so the assertion moves
    // with the fact rather than the string being left to rot (hard-won law 1);
    // the superseded key is deleted from all eleven catalogues.
    //
    // What the tab now says is the REMAINING absence, which is a different one:
    // the pin is editable and audited, and correcting a note's TEXT is not
    // offered because no rule says whether the original wording stays visible
    // to the next reader (OQ-225).
    expect(notes).not.toContain("A note is pinned when it is written.");
    // ⚠ **REWRITTEN 2026-09-13 BY B14 RULE 33's SWEEP — NOT DELETED.** The tab
    // carried 35 words: *"Pinning is recorded in the audit log. Correcting the
    // text of a note is not offered: there is no rule yet on whether the
    // original wording stays visible to the next person who reads it."* The
    // last clause is RATIONALE, which rule 33 makes zero words on screen, and
    // the first sentence is a different fact about a different control. What
    // remains is the absence itself, at five words. `OQ-225` is still why, and
    // it lives in the register and in the component's own comment.
    expect(notes).toContain("A note cannot be corrected.");
    expect(notes).not.toContain("there is no rule yet on whether the original wording");

    // ⚠ **AMENDED 2026-09-12 (`CR-094-BRC01` wave I, `ACC-S8`) — THE SENTENCE
    //    THIS ASSERTED IS DELETED FROM ALL ELEVEN CATALOGUES.** It read
    //    *"Account documents have no table and no upload endpoint."* and was
    //    TRUE from 2026-08-08, when `BR-CUS-036` was CONFIRMED, until the table
    //    and the two endpoints landed. Hard-won law 1 again, in the same shape
    //    the Notes half of this case records three lines up: the assertion
    //    moves with the fact rather than the string being left to rot.
    //
    //    The tab is now `AccountDocumentsTab.tsx` with its own suite; what this
    //    case still owns is that the DOOR opens it — `?tab=documents` draws the
    //    real tab and not the frame.
    const documents = renderDetail("/accounts/acc-10432?tab=documents", {
      detail: detail(),
      access: "Full",
    });
    expect(documents).not.toContain("Account documents have no table and no upload endpoint.");
    expect(documents).toContain("Upload document");
  });

  // AMENDED 2026-08-22 (DEF-579). The tab is still ONE audit surface — the
  // rows come from the same `GET /audit-log` with the same entity filters — but
  // BR-AUD-010 says a per-entity tab RENDERS the entity's rows *and* links to
  // S61, and this asserted only the link. Seeded empty here, so no table is a
  // statement about the DATA rather than about the tab.
  it("US-CUS-011 TC-5 / DEF-579: the Audit tab reads this account's own rows and links to the one viewer", () => {
    const html = renderDetail("/accounts/acc-10432?tab=audit", { detail: detail() });
    expect(html).toContain("f.entity_type=account");
    expect(html).toContain("f.entity_id=acc-10432");
    // Nothing recorded in the window: the tab SAYS so; it does not draw an
    // empty table and it does not claim "never".
    expect(html).toContain("in the window the log covers");
    expect(html).not.toContain("<table");
  });

  it("US-CUS-011 §5: an empty meter list is stated, not left blank", () => {
    const html = renderDetail("/accounts/acc-10432?tab=meters", { detail: detail({ meters: [] }) });
    // Reworded `2f894a21f` (2026-09-19, the premises and units copy sweep): a
    // title with no full stop, and its one fact beneath. `DEF-CUS-9107`.
    expect(html).toContain("No meters on this unit");
    expect(html).toContain("No meters are assigned to this unit.");
  });

  it("BR-CUS-029 / BR-CUS-023: the server's own create warnings render through the catalog", () => {
    expect(warningText({ code: "plan_snapshot_not_recorded", br_ref: "BR-CUS-029" }, t)).toContain(
      "No plan snapshot was recorded",
    );
    expect(warningText({ code: "deposit_not_applied", br_ref: "BR-CUS-023" }, t)).toContain(
      "No deposit was applied",
    );
    // An unknown code still renders — the codes are the server's, and this
    // catalog must not decide which of them a user is allowed to see.
    expect(warningText({ code: "something_new" }, t)).toBe("something_new");
  });

  it.todo(
    "US-CUS-011 TC-6 (negative): deleting a contract document is audit-locked — no document endpoint exists to attempt it against",
  );
  it.todo(
    "US-CUS-011 TC-8 (isolation): the audit read is tenant-scoped — server/RLS scope (G5)",
  );
});

// ── CR-030 W3 · B18 §5.2.3 — the seven TC-ACD cases ───────────────────────
//
// ⚠ **WHAT THESE ARE MEASURED AGAINST.** B18 §5.2 marks its rows
// `[shot: ACC-01 detail ×10]` and those screenshots are NOT in this repo
// (DEF-631 / B18 D5). `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html` DOES
// draw the account detail — header card, its tabs and every table in them —
// so r10's own markup is the reference here, and each case below quotes what
// it draws rather than what a picture is reported to show.
describe("CR-030 W3 — the ACC-01 conformance cases (B18 §5.2.3)", () => {
  it("TC-ACD-1: twelve tabs, in the ACC-01 order plus Credits, Plan and Work, with Audit last", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    // ⚠ **AMENDED 2026-09-02 (`CR-059` CS-37 · task 28): NINE TABS BECAME TEN.**
    // S21 gains **Credits** — every credit note on the account, with the bill
    // each came from — immediately after Payments. Before it, the only way to
    // answer *"show me every credit note on this account"* was to open the
    // customer's bills one at a time. It sits beside Payments because that is
    // where the question is asked: what they paid and what they were let off,
    // in one conversation. r10 draws nine; this is a divergence from r10 and is
    // stamped as one rather than quietly absorbed.
    expect(ACCOUNT_TAB_IDS).toEqual([
      "overview",
      "bills",
      "payments",
      "credits",
      // CR-059 CS-23 · task 6 — the eleventh; see the note on the same list above.
      "plan",
      "usage",
      "meters",
      // CR-070 wave O — the twelfth; see the note on the same list above.
      "work",
      "adjustments",
      "documents",
      "notes",
      "audit",
    ]);
    expect(ACCOUNT_TAB_IDS[ACCOUNT_TAB_IDS.length - 1]).toBe("audit");
    // …and the strip RENDERS them in that order, which the constant alone
    // cannot promise (hard-won law 2: built is not wired).
    const strip = html.slice(html.indexOf('role="tablist"'));
    const order = [...strip.matchAll(/role="tab"[^>]*>([^<]+)</g)].map((m) => m[1]);
    expect(order).toEqual(accountTabs(t).map((tab) => tab.label));
    expect(order[order.length - 1]).toBe("Audit");
  });

  it("TC-ACD-2: the PLAN column draws the unit's plan, and the base charge is still the one absence", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    // ⚠ **AMENDED 2026-09-01 (DEF-2419).** This case required the column to
    // state an absence and carry `data-rule-ref="BR-CUS-029"`. The absence was
    // built on a divergence that has nowhere to be stored — see US-CUS-008
    // TC-1 above — and the PO ruled the plan is taken from the unit and shown.
    // What r10 draws in this column is `Residential Standard / $30.50/mo base`:
    // the NAME half is now filled from the unit, and the BASE CHARGE half is
    // still the account snapshot's and is still absent.
    expect(html).toContain("Sample — Residential");
    expect(html).not.toContain("Plan not shown here");
    // The base charge comes from the account's plan SNAPSHOT, which still has
    // no table. Unchanged from CR-043 finding 11, including the reason it was
    // worded this way: "No base charge recorded" claimed the utility had
    // recorded none, on an account whose bill charges $8.00 of water base.
    expect(html).not.toContain("$30.50");
    expect(html).toContain("Base charge not shown here");
    expect(html).not.toContain("No base charge recorded");
  });

  it("TC-ACD-3: deposit interest is *not recorded* with BR-CUS-057 — never $0.00", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    const interest = html.slice(html.indexOf("Interest accrued"));
    // DEF-3486 — the wording moved because the fact behind it moved; the
    // PROPERTY this case pins has not: no `$` between here and the credit
    // tier, the rule id on the element, and no invented `$3.20` anywhere.
    expect(interest).toContain("Not accrued");
    expect(interest.slice(0, interest.indexOf("Credit tier"))).not.toContain("$");
    expect(html).toContain('data-rule-ref="BR-CUS-057"');
    expect(html).not.toContain("$3.20");
  });

  // ── The 2026-09-03 Product-Owner walk of this screen ──────────────────────

  it("DEF-3483: the services table names each service, the way the meters table already does", () => {
    // The PO, pointing at the Meters table lower down the same tab: *"Services
    // on this account - I will show name of the service inform of similar to
    // this - E Electric"*. The panel drew the bare coloured square, so an
    // account selling six services was six coloured letters and a clerk had to
    // know that `St` is storm water and `So` is solar to read its own list.
    //
    // Proved RED first: with the cell back at `ServiceTags` the panel's own
    // slice fails on `toContain("Electric")` — the letter `E` is there and the
    // word is not.
    // ⚠ `DEF-CUS-9107` — the table moved to Overview's SERVICE group on
    // 2026-09-13 (`97e4edb8d`), so the slice is that group's.
    const overview = renderDetail("/accounts/acc-10432", { detail: detail() });
    const start = overview.indexOf('data-overview-group="service"');
    const panel = overview.slice(start, overview.indexOf("data-overview-group=", start + 10));
    // ⚠ **`toContain("Electric")` IS NOT THE ASSERTION AND THIS CASE WAS
    // WRITTEN WRONG ONCE.** The old cell put the service NAME in `title=` and
    // `aria-label=`, so a plain substring search found "Electric" in a panel
    // that drew nothing but a coloured `E` — the guard passed over the exact
    // defect it was written for. The discriminator is a TEXT NODE: `>Electric<`
    // exists only when the word is drawn beside the square.
    expect(panel).toContain(">Electric<");
    // The SQUARE stays — the PO asked for "E Electric", both halves — and it
    // is still the one shared badge map, so the letter and the colour cannot
    // disagree with any other service square in the product.
    expect(panel).toContain("--color-service-electric");
    expect(panel).toContain(">E<");
  });

  it("DEF-3484: the plan tile carries ONE sentence, and the base-charge absence is closed", () => {
    // The PO on this tile: *"too much content here - Sample — Commercial v1 ·
    // since 06/01/2026 / Base charge not shown here — see any bill's Charges
    // tab"*. B14 rule 32 gives a section one sentence and puts a stated
    // absence behind something closed by default.
    //
    // Proved RED first: with the sub-line back as plain text the second
    // assertion fails, because the sentence is then in the document body
    // rather than only on the element.
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    const strip = metrics(html);
    // Nothing is lost: the whole sentence is still there, in all eleven
    // catalogues, one hover away.
    expect(strip).toContain("Base charge not shown here");
    // …and it is no longer PRINTED. `visible()` strips every title attribute,
    // which is exactly the difference between "on screen" and "available".
    expect(visible(strip)).not.toContain("Base charge not shown here");
    expect(visible(strip)).toContain("Base charge");
  });

  it("DEF-3485: the deposit is the LAST tile — the row is five now, and this case says why", () => {
    // ⚠ **THIS CASE PINNED A RULING THAT HAS BEEN SUPERSEDED, AND IT IS
    //    REWRITTEN RATHER THAN DELETED — the chain is the point.**
    //
    // `DEF-3485`, PO 2026-09-03: *"Can we show deposite data as 4th item on
    // this line - Balance / Plan from unit / Last activity - you can adjust the
    // deposite details and show all information that can i=fit on that line"*.
    // That set the row to FOUR and put the deposit last.
    //
    // SUPERSEDED by the PO on 2026-09-13, confirming the Accounts blueprint's
    // own drawing under B14 rule 41: *"Balance, Ageing, Last bill, Plan from
    // unit, Deposit - this is correct"*. Five tiles; **Last activity** is
    // dropped for **Ageing** and **Last bill**.
    //
    // **WHAT SURVIVES `DEF-3485` IS WHAT THIS CASE STILL ASSERTS:** the deposit
    // is LAST, and its sub-line is the received date. Only the COUNT and the
    // middle of the row moved. Order lives in its own describe block above; the
    // deposit's own two rules are here, where the ruling that set them is.
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    const strip = metrics(html);
    expect(strip).toContain("Deposit on file");
    // The PO's order, 2026-09-13 — the deposit still fourth-and-last becomes
    // fifth-and-last, which is the same rule with one more tile in front of it.
    const order = ["Balance", "Aging", "Last bill", "Plan from unit", "Deposit on file"];
    let cursor = -1;
    for (const label of order) {
      const at = strip.indexOf(label);
      expect(at, `${label} present in order`).toBeGreaterThan(cursor);
      cursor = at;
    }
    // The RECEIVED DATE is the sub-line, because this component's rule is that
    // a sub-line is a fact about the figure above it. With no date the tile
    // says which fact is missing and why, rather than printing a bare dash.
    const received = renderDetail("/accounts/acc-10432", {
      detail: detail({ deposit_on_file: "150.000000", deposit_received_on: "2026-06-01" }),
    });
    const withDate = received.slice(received.indexOf("data-account-metrics"));
    expect(withDate).toContain("$150.00");
    expect(withDate).toContain("06/01/2026");
    expect(strip).toContain("Deposit received");
  });

  it("TC-ACD-4: an account with autopay OFF draws no pill — an absence is not a grey pill", () => {
    const on = renderDetail("/accounts/acc-10432", { detail: detail({ autopay: true }) });
    expect(header(on)).toContain("Autopay on");
    const off = renderDetail("/accounts/acc-10432", { detail: detail({ autopay: false }) });
    expect(off).not.toContain("Autopay on");
    expect(off).not.toContain("Autopay off");
    // The STATUS pill is untouched: this case is about the autopay pill alone.
    expect(header(off)).toContain("Active");
  });

  it("DEF-644: the autopay pill carries the warning that nothing collects on it", () => {
    // ⚠ THIS CASE EXISTS BECAUSE THE WARNING ALREADY VANISHED ONCE. It lived in
    // the Accounts tab's "Waiting on other work" panel until the PO deleted
    // that panel on 2026-08-24 — their call, made with this consequence stated
    // — and it left with the box, because nothing pinned it to anything.
    //
    // `Autopay on` is TRUE and, alone, MISLEADING: autopay in this version is
    // "a promise recorded, never a charge" (apps/payments/models.py:623), so a
    // clerk can switch it on and reasonably expect the next bill to be taken.
    // It will not be. That is a money expectation, not a cosmetic gap, and the
    // failure surfaces at the next arrears review rather than at the mistake.
    const on = renderDetail("/accounts/acc-10432", { detail: detail({ autopay: true }) });
    // ⚠ **REWRITTEN 2026-09-13 BY B14 RULE 33's SWEEP.** Twenty-two words cut
    // to five — *Autopay is recorded, not collected.* The money expectation
    // this case exists to protect is the whole of that sentence; the second
    // sentence explaining what will happen at the next bill was rationale.
    expect(header(on)).toContain("Autopay is recorded, not collected.");
    // And it must travel WITH the pill, not sit somewhere else on the page —
    // the whole point of re-homing it is that it is read where autopay is read.
    expect(header(on)).toMatch(/title="[^"]*recorded, not collected[^"]*"[^>]*>\s*Autopay on/);
  });

  it("TC-ACD-5: `?tab=meters` opens on Meters, and an unknown tab falls back to Overview without erroring", () => {
    const meters = renderDetail("/accounts/acc-10432?tab=meters", { detail: detail() });
    // The drawn tab's own heading (`97e4edb8d`), not the services panel that
    // moved to Overview. `DEF-CUS-9107`.
    expect(meters).toContain("Meters on this unit");
    expect(meters).toContain("Meter #");
    const unknown = renderDetail("/accounts/acc-10432?tab=zzz-not-a-tab", { detail: detail() });
    expect(unknown).toMatch(/<h1[^>]*>Miller, Sarah<\/h1>/);
    // The Overview's own panels, so the fallback is the OVERVIEW rather than a
    // blank body under a header that still renders.
    // ⚠ `Recent bills` → `History` (B14 rule 41, PO 2026-09-13).
    expect(unknown).toContain("History");
    // ⚠ **THIS ASSERTED `Deposit &amp; credit` AND HAD BEEN RED SINCE THE
    //    ELEVEN-GROUP REWORK** (`1660d1722`), which folded that card's rows into
    //    MONEY where the drawing puts them. The case is about the FALLBACK
    //    landing on the Overview, so it names a group the drawing actually has;
    //    the old string named a card the screen no longer draws.
    expect(unknown).toContain("Account setup");
    expect(unknown).not.toContain("Meter #");
  });

  it("TC-ACD-6: a note renders as a CARD — title, `date · author`, body — not a table row", () => {
    const html = renderDetail("/accounts/acc-10432?tab=notes", {
      detail: detail(),
      access: "Full",
      notes: [
        {
          id: "n-1",
          account_id: "acc-10432",
          title: "Leak credit request approved",
          body: "Customer submitted the plumber's invoice showing the repair was completed.",
          author_id: "u-1",
          author_name: "Alex Reed",
          pinned: true,
          customer_visible: false,
          created_at: "2026-06-22T14:03:41Z",
        } as AccountNote,
      ],
    });
    // The card, with r10's own three parts.
    // ⚠ `data-note-card=""` WITH ITS `=`, not the bare name: `toContain
    // ("data-note-card")` also matches the LIST's `data-note-cards`, so it
    // passed with the card marker deleted — proved by deleting it. A check
    // whose output cannot tell pass from fail is worse than no check.
    expect(html).toContain('data-note-card=""');
    expect(html).toContain("<h3>Leak credit request approved</h3>");
    expect(html).toContain("Alex Reed");
    expect(html).toContain("06/22/2026");
    expect(html).toContain("Customer submitted the plumber&#x27;s invoice");
    // NOT a table: the whole point of the drift B18 §5.2.2 records.
    const tab = html.slice(html.indexOf("data-note-cards"));
    expect(tab).not.toContain("<tr");
    expect(tab).not.toContain("<td");
    // …and the pinned card takes r10's accent rule rather than only a pill.
    expect(html).toContain('data-pinned="true"');
  });

  it("TC-ACD-7: a −$42.50 adjustment keeps its minus — the formatter never re-signs a figure", () => {
    // ⚠ **THIS IS ASSERTED ON THE FORMATTER, NOT ON THE TAB, AND THAT IS THE
    // HONEST FORM OF IT TODAY.** The Adjustments tab has no endpoint: it draws
    // r10's headings over a stated absence, so there is no −$42.50 on the
    // screen to measure. What the case is really about is the money path
    // (BR-SHL-023) — a negative amount rendering as a negative, at two
    // decimals, from the ONE formatter every cell on this screen uses.
    expect(formatMoney("-42.500000", "USD")).toBe("-$42.50");
    expect(formatMoney("-42.500000", "USD")).toContain("-");
    expect(formatMoney("-5.000000", "USD")).toBe("-$5.00");
    // And the tab it belongs to draws the columns it will need, over the
    // absence — never an empty table, which would read as "never adjusted".
    const html = renderDetail("/accounts/acc-10432?tab=adjustments", { detail: detail() });
    for (const heading of ["Adjustment #", "Reason", "Applied to", "Approved by"]) {
      expect(html).toContain(heading);
    }
    // ⚠ **THE SENTENCE CHANGED ON 2026-09-13 AND SO DID THE ABSENCE BEHIND IT
    // (`DEF-CUS-5126` / `DEF-CUS-5136`).** It read *"No endpoint lists or posts
    // one"*. Posting one has been possible since `CR-059` CS-35 and is now a
    // live control; what the tab still cannot do is LIST, and for a different
    // reason — two of the six headings above, Reason and Approved by, have no
    // store anywhere in this product (`OQ-BIL-12354`, `OQ-RBS-1739`).
    // `DEF-CUS-9107` — the tab LISTS since `32f17b2d2` (2026-09-13); with no
    // adjustment on this account there is no −$42.50 drawn, and no sentence.
    expect(html).toContain("New adjustment");
    expect(html).not.toContain("Adjustments show on the Payments tab");
    expect(html).not.toContain("No endpoint lists or posts one");
    expect(html).not.toContain("ADJ-142");
    expect(html).not.toContain("42.50");
  });

  // ⚠ **THE SENTENCE CHANGED ON 2026-09-13 AND THIS CASE WAS ASSERTING THE OLD
  //    ONE.** It read *"The deposit on file is not listed as a payment"* over 39
  //    words of why; B14 rule 33 keeps the FACT and deletes the REASON, so the
  //    pair is now *Deposits are not listed here.* and *The deposit shows on
  //    Overview.* — the second being the one thing a clerk can act on. The
  //    absence itself and its `DEF-177` trail are unchanged, which is what this
  //    case has always been for.
  it("CR-030 3.5: the Payments tab says the deposit on file is not one of these rows", () => {
    const html = renderDetail("/accounts/acc-10432?tab=payments", { detail: detail() });
    expect(html).toContain("Deposits are not listed here.");
    expect(html).toContain("The deposit shows on Overview.");
    expect(html).toContain('data-tracks="DEF-177"');
    // r10's own fixture row, which nothing serves — so nothing draws it.
    expect(html).not.toContain("DEPO-4218");
  });

  // ⚠ **RENAMED AND AMENDED 2026-09-12 (`CR-094-BRC01` wave I, `ACC-S8`).** It
  //    read *"draws r10's five headings over the absence"* and asserted
  //    `"no upload endpoint"`. `BR-CUS-036` was CONFIRMED on 2026-08-08 and the
  //    table it names did not exist, so the tab was a FRAME — the five drawn
  //    heads over one spanning cell saying so. It is a list now.
  //
  //    **The five headings are still asserted here, in r10's drawn order**,
  //    because that is what this case has always been for; the sentence under
  //    them is what changed, and the check that it is GONE is the half that
  //    would have rotted silently.
  it("CR-030 3.7: the Documents tab draws r10's five headings, and no longer over an absence", () => {
    const html = renderDetail("/accounts/acc-10432?tab=documents", { detail: detail() });
    for (const heading of ["Document", "Type", "Date", "Uploaded by", "Size"]) {
      expect(html).toContain(heading);
    }
    expect(html).toContain("Upload document");
    expect(html).not.toContain("no upload endpoint");
    // r10's own fixture row, which nothing serves — so nothing draws it
    // (B14 rule 37: a figure drawn in a wireframe is an illustration).
    expect(html).not.toContain("Welcome_Pack");
  });

  it("CR-030 3.11: the Audit tab names the three kinds of actor, with BR-CUS-028 on the element", () => {
    const html = renderDetail("/accounts/acc-10432?tab=audit", { detail: detail() });
    // ⚠ THIS SENTENCE READ "made by a member of staff or by the system" UNTIL
    //   2026-09-06 (`DEF-CUS-4298`), AND `US-AUD-010` MADE IT FALSE THE DAY IT
    //   LANDED. There is now a third kind of actor — an automation that names
    //   itself, drawn on this very table as "Returned payments, version 4" —
    //   and it is neither a member of staff nor the anonymous system.
    //
    //   The failure is worth naming because this assertion did not catch it:
    //   it asks whether the sentence is PRESENT, which is a different question
    //   from whether it is TRUE, and no check in this repository asks the
    //   second one. It was found by a person looking at a screenshot from the
    //   browser walkthrough (`10-scripts/render-checks/us-aud-010-the-audit-actor.mjs`),
    //   which is hard-won law 6 charging its rent again.
    // ⚠ **REWRITTEN 2026-09-13 BY B14 RULE 33's SWEEP — NOT DELETED.** The
    // line used to name all three kinds of actor in seventeen words. Rule 33
    // caps a FACT at six, and the WHO column beside it already says which of
    // the three any given row was. What the case is for is unchanged: the
    // element states that an actor is recorded, and carries BR-CUS-028.
    expect(html).toContain("Every entry names who acted.");
    expect(html).not.toContain("a member of staff, an automation, or the system");
    expect(html).not.toContain("made by a member of staff or by the system");
    expect(html).toContain('data-rule-ref="BR-CUS-028"');
    // r10 writes `Sarah Miller (portal)` in its USER column. There is no portal
    // in this version and `audit_log` records no channel, so nothing invents one.
    expect(html).not.toContain("(portal)");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// CR-030 W3 · task 3.2 — THE ICON RAIL (BR-SHL-045, PO 2026-08-24, closing D2)
// ══════════════════════════════════════════════════════════════════════════
//
// The ruling, in the PO's chosen option: *"Seven icons, label appears on
// hover"*. The seven, in r10's own order: ✉ Send statement · 🖨 Print bill ·
// $ Issue credit · ⇄ Change plan · ⚡ Disconnect notice · 🗓 Payment plan ·
// ✎ Add note.
//
// ⚠ THE ASSERTIONS THAT MATTER MOST HERE ARE THE ACCESSIBLE-NAME ONES, and the
// ruling says why in as many words: *"HOVER IS A MOUSE, AND HALF OUR USERS ARE
// NOT ON ONE."* A rail of seven perfectly-drawn glyphs with no `aria-label`
// renders beautifully, passes every text-absence assertion in this file, and is
// unusable without a mouse — and one of its glyphs SENDS A DISCONNECT NOTICE.
// So `railName()` below is asserted glyph by glyph rather than in the aggregate.
describe("CR-030 W3 · 3.2 / BR-SHL-045 — the S21 icon rail", () => {
  // ⚠ SEEDS A BILL SINCE `DEF-CUS-4631` (2026-09-07). Two of the rail's glyphs
  // are now DERIVED from "has this account an issued bill", so a fixture with
  // no bills is not the ordinary account — it is the empty-account edge case,
  // and pinning the rail's behaviour to it would test the exception and call it
  // the rule. The no-bill case has its own named test below.
  const railFull = (): string =>
    renderDetail("/accounts/acc-10432", { detail: detail(), access: "Full", bills: [bill()] });

  // ⚠ **SEVEN BECAME EIGHT ON 2026-09-12 — `CR-094-BRC01` wave K, `ACC-S16`.**
  // This case was named *"and no eighth"* and it did exactly what it was
  // written to do: the eighth glyph could not reach the screen without a lane
  // amending it here and saying why.
  //
  // **WHY THE EIGHTH IS LAWFUL AND NOT A QUIET ADDITION.** `BR-SHL-045` ruled
  // SEVEN against a proposal to REDUCE them to two-plus-a-menu; it ruled on the
  // presentation of the actions that existed, not that no action could ever
  // join them. What adds this one is a commitment card in the blueprint's own
  // §12 — `ACC-S16`, *"A clerk can write to the customer from the account"* —
  // over step 1's finding F11: *"Seven icons and six buttons and not one sends
  // a word."* `R6` draws it FIRST on the rail, which is where it is.
  it("ACC-S16: eight glyphs now, the new one first, in r10's order after it", () => {
    const buttons = railButtons(railFull());
    expect(buttons).toHaveLength(8);
    expect(buttons.map((tag) => attr(tag, "aria-label"))).toEqual([
      "Write to customer",
      "Send statement",
      "Print bill",
      "Issue credit",
      "Change plan",
      "Disconnect notice",
      "Payment plan",
      "Add note",
    ]);
    // The table the component draws from is the same seven, so a glyph added
    // there without a test amendment fails the length check above rather than
    // sliding onto the screen unasserted.
    expect(ACCOUNT_RAIL_ACTIONS.map((glyph) => glyph.id)).toEqual([
      "communication",
      "sendStatement",
      "printBill",
      "issueCredit",
      "changePlan",
      "disconnectNotice",
      "paymentPlan",
      "addNote",
    ]);
  });

  it("BR-SHL-045: the label is the ACCESSIBLE NAME, not only a hover tooltip", () => {
    for (const tag of railButtons(railFull())) {
      // A real `aria-label`, on every one, live or disabled. This is the half
      // that survives a touch screen and a screen reader.
      expect(attr(tag, "aria-label").length).toBeGreaterThan(0);
      // AND a `title`, which is what makes the hover the PO chose actually
      // happen. Both, never one — the ruling is explicit that hover ALONE
      // "would leave a touch user guessing between two glyphs".
      expect(attr(tag, "title").length).toBeGreaterThan(0);
    }
    // The group itself is named, so a screen reader announces seven controls as
    // one thing rather than as loose buttons after the metric columns.
    expect(rail(railFull())).toContain('role="group"');
  });

  // ⚠ **THIS BLOCK WAS REWRITTEN ON 2026-09-07 (`DEF-CUS-4631`) AND THE REASON
  // IS WORTH MORE THAN THE TEST.** It used to assert the exact words of four
  // refusals. Three of those four sentences were FALSE — the questions they
  // named had been closed on 2026-08-12 and the endpoints they said were
  // missing were mounted — so the test was green precisely because the screen
  // and the test agreed with each other and neither agreed with the product.
  // **Pinning a refusal's copy makes the refusal permanent.** What is asserted
  // now is the STATE (live, or refused) and the FACT that decides it.
  it("BR-SHL-025 / DEF-CUS-4631: SIX of the seven are live on an occupied account with a bill", () => {
    const html = renderDetail("/accounts/acc-10432", {
      detail: detail(),
      access: "Full",
      bills: [bill()],
    });
    const byName = new Map(
      railButtons(html).map((tag) => [attr(tag, "aria-label"), tag]),
    );

    // Print bill and Issue credit are DERIVED from "has this account an issued
    // bill", and this account has one — so both are live. Before this change
    // they were dead on every account in the product.
    for (const name of [
      "Print bill",
      "Issue credit",
      "Disconnect notice",
      "Change plan",
      "Payment plan",
      "Add note",
    ]) {
      const tag = byName.get(name) ?? "";
      expect(isDisabled(tag)).toBe(false);
      // A live control's tooltip is its own name, never an excuse.
      expect(attr(tag, "title")).toBe(name);
    }

    // ── THE ONE THAT STILL REFUSES, AND IT IS THE ONE THAT WAS ALWAYS TRUE ──
    // Nothing in this product renders a statement. It is a CAPABILITY absence,
    // so no per-account fact can derive it and it keeps a typed sentence —
    // guarded instead by `accountRailHoldExpiry.test.ts`, which fails the day a
    // statement renderer lands.
    const statement = byName.get("Send statement") ?? "";
    expect(isDisabled(statement)).toBe(true);
    expect(attr(statement, "title")).toBe(t("customers.account.action.sendStatementBlocked"));

    // ⚠ AND THE ONE REMAINING SENTENCE IS NOT A SECOND COPY (hard-won law 5):
    // it is `UNAVAILABLE_ACTIONS`', the one place the worded buttons read it
    // from before this rail existed.
    // ⚠ **THE `adjust` SKIP IS GONE WITH THE ENTRY IT SKIPPED (2026-09-13,
    // `DEF-CUS-5126`).** This loop carried `if (action.id === "adjust")
    // continue` because `adjust` stayed a WORDED button while the rail took the
    // other glyphs. It is no longer in the list at all: its refusal was false —
    // `POST /accounts/{id}/payments` with `type: "adjustment"` has existed
    // since `CR-059` CS-35 — and the button now opens `AdjustModal`. The skip
    // is removed rather than left harmlessly in place, because a `continue` on
    // an id nothing holds is a line that reads as a live exemption.
    for (const action of UNAVAILABLE_ACTIONS) {
      expect(attr(byName.get(t(action.labelKey)) ?? "", "title")).toBe(t(action.reasonKey));
    }
  });

  it("DEF-CUS-4631: with NO issued bill the two bill-backed glyphs refuse, and say why", () => {
    // The same account, same role — only the FACT differs. That is the whole
    // point of a derived refusal: nothing was re-worded, the answer changed.
    const html = renderDetail("/accounts/acc-10432", {
      detail: detail(),
      access: "Full",
      bills: [],
    });
    const byName = new Map(
      railButtons(html).map((tag) => [attr(tag, "aria-label"), tag]),
    );
    for (const [name, reason] of [
      ["Print bill", "No bill has been issued yet."],
      ["Issue credit", "A credit needs an issued bill."],
    ] as Array<[string, string]>) {
      const tag = byName.get(name) ?? "";
      expect(isDisabled(tag)).toBe(true);
      expect(attr(tag, "title")).toBe(reason);
    }
    // Disconnect is gated on OCCUPANCY, not on bills, so it is unaffected.
    expect(isDisabled(byName.get("Disconnect notice") ?? "")).toBe(false);
  });

  it("DEF-CUS-4631: a DRAFT account cannot be disconnected — it never took the unit", () => {
    const html = renderDetail("/accounts/acc-10432", {
      // A draft: `status_behavior_class` is what decides occupancy, never the
      // tenant's own label (`OCCUPYING_BEHAVIOR_CLASSES`).
      detail: detail({ status: "draft", status_name: "Draft", status_behavior_class: "pending" }),
      access: "Full",
      bills: [bill()],
    });
    const byName = new Map(
      railButtons(html).map((tag) => [attr(tag, "aria-label"), tag]),
    );
    const cut = byName.get("Disconnect notice") ?? "";
    expect(isDisabled(cut)).toBe(true);
    expect(attr(cut, "title")).toBe("This account does not hold service.");
  });

  it("B14 rule 6 / BR-SHL-045: the disconnect notice is the ONE glyph in the danger tier", () => {
    const buttons = railButtons(railFull());
    const danger = buttons.filter((tag) => attr(tag, "data-variant").includes("danger"));
    expect(danger).toHaveLength(1);
    expect(attr(danger[0], "aria-label")).toBe("Disconnect notice");
    // "distinguishable by colour, and not only by shape" — the tier is asserted
    // by its INTENT attribute rather than by a colour utility, because the day
    // the danger hue changes this assertion should still mean the same thing.
    expect(attr(danger[0], "data-variant")).toBe("ghost-danger");
    for (const tag of buttons.filter((b) => attr(b, "aria-label") !== "Disconnect notice")) {
      expect(attr(tag, "data-variant")).toBe("ghost");
    }
  });

  it("BR-SHL-045: the keyboard reaches every live glyph — real buttons, no tabindex override", () => {
    const buttons = railButtons(railFull());
    // Seven real `<button>` elements: tab reaches an enabled one and Enter or
    // Space activates it, with no `tabindex` anywhere overriding that. A `<div
    // onClick>` would satisfy every other assertion in this file and none of
    // this one.
    expect(buttons).toHaveLength(8); // ACC-S16 — the eighth glyph, 2026-09-12
    for (const tag of buttons) {
      expect(attr(tag, "tabindex")).toBe("");
      expect(attr(tag, "aria-hidden")).toBe("");
    }
    // ⚠ REPORTED, NOT SILENTLY ACCEPTED: an HTML `disabled` button is not
    // tab-reachable, so a blocked glyph announces its reason on hover and on
    // focus-of-a-neighbour but cannot itself be focused. That is BR-SHL-025's
    // shipped shape everywhere in this product (`GuardedButton` and `RowAction`
    // both), not something this rail invents, so it is stated here rather than
    // diverged from in one screen. The LIVE glyphs — the ones a keyboard user
    // can actually act on — are enabled and reachable.
    //
    // ⚠ **THIS LIST WAS THREE UNTIL 2026-09-07 AND IS NOW SIX**
    // (`DEF-CUS-4631`). Print bill, Issue credit and Disconnect notice were
    // each refusing on a question the PO had already closed on 2026-08-12, so
    // for three weeks a keyboard user could reach three of the seven controls
    // on this screen. The count is asserted, not described, because "we
    // activated them" is exactly the claim this change could get wrong.
    // ⚠ **AND SIX BECAME SEVEN ON 2026-09-12 (`ACC-S16`).** The new glyph is
    // LIVE from its first commit — the endpoint is mounted and the write is
    // served — so a keyboard user can reach it. A glyph shipped disabled over a
    // working endpoint is the dead control hard-won law 2's mirror is about.
    const live = buttons.filter((tag) => !isDisabled(tag));
    expect(live.map((tag) => attr(tag, "aria-label"))).toEqual([
      "Write to customer",
      "Print bill",
      "Issue credit",
      "Change plan",
      "Disconnect notice",
      "Payment plan",
      "Add note",
    ]);
  });

  it("BR-SHL-045: nothing was lost — every glyph is an action the header used to word", () => {
    const html = railFull();
    // The seven names on the rail, and the five that stay worded in the header,
    // are the TEN r10 draws and the ten this page's docstring counted. The
    // "seven versus ten" was never a missing three.
    const railNames = railButtons(html).map((tag) => attr(tag, "aria-label"));
    const worded = ["Record payment", "Adjust", "Move-out", "Activate account", "Move-in"];
    // ⚠ EIGHT since `ACC-S16` (2026-09-12): r10's seven, plus the one r10 has
    // no equivalent for. The five worded ones did not move, which is what this
    // case is actually protecting.
    expect(railNames).toHaveLength(8);
    for (const name of worded) expect(header(html)).toContain(name);
    // …and not one of the seven is drawn twice, as a glyph AND as a WORDED
    // BUTTON. ⚠ Asked of the header's buttons rather than of its text
    // (`DEF-CUS-4631`): the Plan tab is now labelled **Payment plan**, so the
    // tab strip legitimately carries that string inside the header slice. A
    // TAB that shows the plan and a GLYPH that starts one are not a duplicate
    // control, and the raw-text form could not tell them apart.
    const headerButtonLabels = headerCommandLabels(html);
    for (const name of railNames) expect(headerButtonLabels).not.toContain(name);
  });

  it("BR-SHL-025 / TC-ACD-4: an Executive sees all eight disabled with the ROLE's reason", () => {
    const buttons = railButtons(
      renderDetail("/accounts/acc-10432", { detail: detail(), access: "View" }),
    );
    // ⚠ EIGHT since `ACC-S16`. The new glyph takes the SAME role gate as the
    // three live ones — an Executive may read an account and may not write to
    // its customer — so it is disabled with the ROLE's sentence, not its own.
    expect(buttons).toHaveLength(8);
    for (const tag of buttons) {
      expect(isDisabled(tag)).toBe(true);
      // The ROLE comes first, ahead of the module's own reason: it is the one
      // the user can do something about.
      expect(attr(tag, "title")).toBe("Your role can view accounts but not change them.");
      // Still named, still announced. A hidden control teaches nothing.
      expect(attr(tag, "aria-label").length).toBeGreaterThan(0);
    }
  });

  it("US-CUS-008 TC-5 / BR-CUS-043: a CLOSED account's plan glyphs carry the occupancy rule", () => {
    const buttons = railButtons(
      renderDetail("/accounts/acc-10432", {
        detail: detail({
          status: "closed",
          status_name: "Closed",
          status_behavior_class: "terminal",
          closed_at: "2026-08-14",
        }),
        access: "Full",
      }),
    );
    const byName = new Map(buttons.map((tag) => [attr(tag, "aria-label"), tag]));
    expect(attr(byName.get("Change plan") ?? "", "title")).toContain(
      "Only an account that currently holds its unit can change plan.",
    );
    expect(attr(byName.get("Payment plan") ?? "", "title")).toContain(
      "A payment plan spreads the arrears of a live tenancy",
    );
    // Add note is gated on the ROLE alone — a closed account still takes a note.
    expect(isDisabled(byName.get("Add note") ?? "")).toBe(false);
  });

  it("A18 §6: the rail is not drawn at all for a role that cannot see the screen", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail(), access: "—" });
    expect(railButtons(html)).toHaveLength(0);
  });
});

/**
 * ⚠ **THE ELEVEN SERVED FIELDS THAT REACHED NO SCREEN — PO ruling 2026-09-10,
 * verbatim: *"we should have all these details captured on screen"*, with
 * *"when we do information architecture, we have to logically group the
 * information, give group a heading so that it is easy for user to
 * understand"* beside it.**
 *
 * The Accounts blueprint counted the cost on the running product: the account
 * endpoint serves 69 fields and ELEVEN were drawn nowhere, each confirmed
 * absent by searching the RENDERED TEXT for its served value. `DEF-GOV-5006`
 * is the row that says those rulings were in the blueprint and in no file of
 * this repository; nothing was ever scoped to them.
 *
 * **AGEING IS THE ONE THAT COST SOMEBODY SOMETHING.** The accounts LIST draws
 * an Ageing column. The DETAIL drew nothing — on `A-11812` the server answers
 * `d61_90`, 61 days, source `opening_buckets`, and the words *past due*
 * appeared NOWHERE on that account's page. A clerk drilled in from the list
 * and lost the single fact that says how overdue the account is.
 *
 * ⚠ **PROVED RED FIRST, IN THIS HARNESS, AT THE TIP THIS LANE STARTED FROM
 * (`aa628eff2`), in a throwaway `git worktree` rather than by reasoning about
 * it** — hard-won law 7's second half, which is the clause a red proof through
 * the wrong entry point fails. Every case below failed there and passes here.
 *
 * ⚠ **AND THE ASSERTION IS ON THE RENDERED TEXT, NOT ON A PROP.** `G13` asks
 * whether a prop is passed; it cannot ask whether a field reaches a reader,
 * which is exactly how eleven served fields stayed invisible while every check
 * in the repository was green.
 */
/**
 * ⚠ **THE FIVE-TILE ROW — PO ruling 2026-09-13, verbatim: *"Balance, Ageing,
 * Last bill, Plan from unit, Deposit - this is correct"*.**
 *
 * It **supersedes the COUNT in `DEF-3485`** (PO, 2026-09-03: *"Can we show
 * deposite data as 4th item on this line - Balance / Plan from unit / Last
 * activity"*), which set this row to four. The blueprint draws five and drops
 * **Last activity** for **Ageing** and **Last bill**; put to the PO as a
 * drawing contradicting a signed ruling — the one question B14 rule 41 allows
 * — and ruled for the drawing. The deposit tile stays last, where `DEF-3485`
 * put it.
 *
 * ⚠ **THE TILE THAT WAS REMOVED WAS DEAD BEFORE IT WAS DROPPED.** `lastActivity`
 * was an OPTIONAL prop and every `.ts`/`.tsx` file under `src/` was searched
 * for a caller before it went: **nothing in the product ever passed it.** So
 * the tile rendered its awaiting branch on every account that has ever opened
 * this screen and could not have rendered anything else — hard-won law 2's dead
 * UI, in the header of the most-opened screen we have. `ORDER` below is
 * asserted as a SEQUENCE and not as a set, because a row whose tiles are all
 * present in the wrong order is the defect this ruling is about.
 */
describe("ACC-02 — the five-tile row, in the order the blueprint draws it", () => {
  const AGEING = {
    ageing_segment: "d61_90",
    ageing_days_past_due: 61,
    ageing_source: "opening_buckets",
    ageing_unavailable: null,
  } as unknown as Partial<AccountDetail>;

  /** The row as drawn. A SEQUENCE — order is the ruling, not a detail. */
  const ORDER = ["Balance", "Aging", "Last bill", "Plan from unit", "Deposit on file"];

  function tileOrder(html: string): string[] {
    const at = ORDER.map((label) => ({ label, i: html.indexOf(`>${label}<`) }));
    return at
      .filter((x) => x.i >= 0)
      .sort((a, b) => a.i - b.i)
      .map((x) => x.label);
  }

  it("all five tiles are present, in the drawn order", () => {
    const html = metrics(renderDetail("/accounts/acc-10432", { detail: detail(AGEING) }));
    expect(tileOrder(html)).toEqual(ORDER);
  });

  it("Last activity is gone — it was an optional prop nothing ever passed", () => {
    const html = metrics(renderDetail("/accounts/acc-10432", { detail: detail(AGEING) }));
    expect(html).not.toContain("Last activity");
  });

  it("the ageing tile carries the band and its day count, not a dash", () => {
    const html = metrics(renderDetail("/accounts/acc-10432", { detail: detail(AGEING) }));
    expect(html).toContain("61 days past due");
    // The list's VOCABULARY, not the list's pill — a tile draws its value at
    // tile size. The band's own words must still be the list's words.
    expect(html).toContain("Opening balance");
  });

  it("an account with no band says so and never invents one", () => {
    const html = metrics(renderDetail("/accounts/acc-10432", { detail: detail() }));
    expect(html).toContain("Aging");
    expect(html).not.toContain("61 days past due");
  });

  it("a never-billed account states it, and does not promise a figure is coming", () => {
    const html = metrics(renderDetail("/accounts/acc-10432", { detail: detail(AGEING) }));
    expect(html).toContain("Never billed");
    // `AwaitsCell` would promise one is on the way. Never billed is an ordinary
    // and permanent state for a new connection or a migrated opening balance.
    expect(html).toContain("No bill has been raised yet.");
  });
});

describe("ACC-02 — every fact the server serves sits under a named group", () => {
  /** The four keys `selectors.ageing_cells` spreads into every account row. */
  const AGEING = {
    ageing_segment: "d61_90",
    ageing_days_past_due: 61,
    ageing_source: "opening_buckets",
    ageing_unavailable: null,
  } as unknown as Partial<AccountDetail>;

  it("MONEY: the ageing band, its day count and where the claim comes from", () => {
    const html = visible(renderDetail("/accounts/acc-10432", { detail: detail(AGEING) }));
    expect(html).toContain("Money");
    expect(html).toContain("Aging source");
    expect(html).toContain("Opening balance");
    expect(html).toContain("Days past due");
    expect(html).toContain("61");
  });

  it("MONEY: the basis and the source resolve to words, never to the wire's code", () => {
    const html = visible(renderDetail("/accounts/acc-10432", { detail: detail(AGEING) }));
    expect(html).toContain("Posting date");
    expect(html).toContain("The ledger");
    // B14 rule 31 — the served value is `"ledger"` and a clerk never sees it.
    expect(html).not.toContain(">ledger<");
    expect(html).not.toContain(">opening_buckets<");
  });

  it("ACCOUNT SETUP: kind, behaviour class and the two dates, all in words", () => {
    const html = visible(renderDetail("/accounts/acc-10432", { detail: detail(AGEING) }));
    expect(html).toContain("Account kind");
    expect(html).toContain("Regular");
    expect(html).toContain("Behavior class");
    expect(html).toContain("Billable");
    expect(html).toContain("Opened");
    expect(html).toContain("Closed");
    // `status_behavior_class` is `"billable"` on the wire — rule 31 again.
    expect(html).not.toContain(">billable<");
  });

  it("ACCOUNT SETUP: a standalone account says it is not in a group, not that it has no master", () => {
    const html = visible(renderDetail("/accounts/acc-10432", { detail: detail(AGEING) }));
    expect(html).toContain("Master account");
    // `_master_ref` answers null for THREE different reasons — standalone, a
    // master itself, and the ambiguous two-masters case it refuses to break —
    // so the screen may never assert which one this is.
    expect(html).not.toContain("no master");
  });

  it("PLAN: the unit's plan, its code, its version and the date it took effect", () => {
    const html = visible(
      renderDetail("/accounts/acc-10432", {
        detail: detail({
          ...AGEING,
          unit_plan: {
            name: "Sample — Residential",
            code: "SCW-RES",
            version: 1,
            since: "2026-06-01",
          },
        } as unknown as Partial<AccountDetail>),
      }),
    );
    expect(html).toContain("SCW-RES");
    expect(html).toContain("In force since");
    expect(html).toContain("Version");
  });

  it("a served field that is absent renders a dash and never a fabricated value", () => {
    // No ageing keys at all — an older server, or an account with no band.
    const html = visible(renderDetail("/accounts/acc-10432", { detail: detail() }));
    expect(html).toContain("Aging source");
    expect(html).not.toContain("Opening balance");
    // The day count must not appear with no band behind it to mean anything.
    expect(html).not.toContain("undefined");
  });
});

/* ══════════════════════════════════════════════════════════════════════════
 * B14 RULE 41 (PO 2026-09-13) — THE OVERVIEW MATCHES ITS BLUEPRINT DRAWING
 * ══════════════════════════════════════════════════════════════════════════
 * The drawing is `04-docs/05-modules/03-customers/blueprint/02-account-detail
 * .md`, the ACC-02 frame: ELEVEN named groups and FORTY-ONE label/value rows.
 * The screen rendered SEVEN groups and THIRTY-SIX rows.
 *
 * ⚠ **THESE CASES ASSERT PRESENCE, ORDER AND WORDS — NOT THAT THE SCREEN LOOKS
 * LIKE THE DRAWING, WHICH THEY CANNOT.** These suites are `renderToStaticMarkup`
 * in the `node` environment: there is no layout engine here, so a group in the
 * wrong column, a rule of the wrong width or a gap off the scale is invisible to
 * every line below. B14 rule 41's own status cell says the same thing about the
 * whole repository — *"nothing in this repository reads a rendered screen"* —
 * and names the browser census as the instrument. The `data-account-overview`
 * and `data-overview-group` hooks these cases read are what that census selects
 * on; asserting them here is what stops one being renamed away from under it.
 *
 * ⚠ **AND NO CASE BELOW ASSERTS A FIGURE THE DRAWING INKED** (B14 rule 37). The
 * drawing says *"two service agreements"* against `A-11812`; the count under
 * METERS is read off `service_agreements.length`, and the case proves that by
 * feeding it THREE and expecting three.
 * ══════════════════════════════════════════════════════════════════════════ */
describe("B14 rule 41 — the Overview is the eleven drawn groups, in the drawn order", () => {
  /** Every `data-overview-group` slug, in document order. */
  function groups(html: string): string[] {
    return (html.match(/data-overview-group="([a-z-]+)"/g) ?? []).map((one) =>
      one.replace(/^data-overview-group="/, "").replace(/"$/, ""),
    );
  }

  /** The Overview region only — from its root hook to the end of the document. */
  function overview(html: string): string {
    const start = html.indexOf("data-account-overview");
    return start === -1 ? "" : html.slice(start);
  }

  it("FIFTEEN groups — the drawn eleven, the two sample-data ones, UNIT and the co-applicant", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    // ⚠ **`usage-trend` AND `payment-method` GAINED HOOKS ON 2026-09-13.** The
    // blueprint draws this tab TWICE — an empty-account frame (the eleven
    // below) and a SAMPLE-DATA frame that also draws USAGE TREND and PAYMENT
    // METHOD. Both were on the screen already and neither was hooked, so the
    // browser census reported a clean zero over two groups it was not looking
    // at — law 7's *reporting zero over a scope it silently excludes*.
    // `10-scripts/render-checks/drawn/acc02-overview.json` carries them now,
    // with the frame each came from written on the row.
    expect(groups(html)).toEqual([
      // LEFT column, top to bottom
      "money",
      "service",
      "meters",
      "plan",
      "history",
      "usage-trend",
      // RIGHT column, top to bottom
      "customer",
      // ⊕ **CO-APPLICANT, 2026-09-23 — NOT DRAWN, PO-RULED (`DEF-CUS-6391`).**
      // *"Store a second person on the account (name, email, phone), shown on
      // the account page"*. No frame draws it, so it sits beside the other
      // person on the account and nothing else moves.
      "co-applicant",
      "mailing-address",
      "customer-record",
      "billing-preferences",
      "account-setup",
      // ⚠ **UNIT LANDED 2026-09-13 (`DEF-CUS-5163`).** The blueprint's R5 frame
      // heads it `UNIT — WHAT THIS ACCOUNT IS ATTACHED TO` with `✎Change unit`
      // and the screen rendered no unit group at all. Its POSITION is the one
      // thing the two frames agree on — R5 draws it straight after the ACCOUNT
      // group, and the ACC-02 frame this list otherwise follows puts ACCOUNT
      // SETUP fifth — so it goes here and nothing else moves.
      "unit",
      "portal-access",
      "payment-method",
    ]);
  });

  it("FORTY-SIX label/value rows — forty-one, plus the UNIT group's five", () => {
    const html = overview(renderDetail("/accounts/acc-10432", { detail: detail() }));
    // ⚠ **THE ARITHMETIC, BECAUSE THIS NUMBER HAS BEEN RIGHT FOR THE WRONG
    // REASON AND WAS RED.** The drawing's eleven groups hold 41 rows and the
    // screen renders FORTY of them — `Balance` is the header tile (PO
    // 2026-09-03; the browser census records it as a declared remainder rather
    // than a miss). The forty-first here is PAYMENT METHOD's own `On file` row,
    // from the blueprint's sample-data frame. 40 + 1.
    //
    // ⚠ **AND FIVE MORE FROM 2026-09-13**: the UNIT group's Unit · Premises ·
    // Service address · Unit type · Unit plan (`DEF-CUS-5163`). 41 + 5.
    expect((html.match(/<dt>/g) ?? []).length).toBe(46);
  });

  /* ════════════════════════════════════════════════════════════════════════
   * THE SIX FAULTS THE PRODUCT OWNER READ OFF THE LIVE SCREEN, 2026-09-13
   * ════════════════════════════════════════════════════════════════════════
   * ⚠ **NOT ONE OF THESE COULD HAVE BEEN A REGRESSION CAUGHT BY A SUITE, AND
   * THAT IS THE POINT.** Every one was TRUE in the DOM before it was fixed — a
   * second `<h3>` is a real heading, `· sub` is a real string, a missing chip is
   * a component that was never mounted, and a chart is a chart. The cases below
   * pin the FIXES so they cannot rot back; what FOUND them was a person looking
   * at the screen (hard-won law 6), and the geometry half is still only
   * measurable by `10-scripts/render-checks/acc02-tab-conformance.mjs`.
   * ════════════════════════════════════════════════════════════════════════ */

  it("FAULT 1 · PAYMENT METHOD carries ONE heading, no rationale, and a refusing control", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    const group = html.slice(html.indexOf('data-overview-group="payment-method"'));
    const panel = group.slice(0, group.indexOf('data-overview-group="', 1) + 1 || undefined);
    // It printed its heading TWICE — once as the panel's `<h3>` and again as
    // `ArrivesWith`'s own `<h3>` from its `title` prop.
    expect((panel.match(/>Payment method</g) ?? []).length).toBe(1);
    // 27 words of rationale, which B14 rule 33 puts at ZERO on screen.
    expect(visible(html)).not.toContain("belong to the payments module");
    expect(visible(html)).not.toContain("nothing collects on it in this version.");
    // BR-SHL-025 / B14 rule 25 — the control STAYS and refuses, with a reason
    // at rule 33's six-word cap. It is not hidden.
    expect(panel).toContain("Update method");
    expect(panel).toContain("disabled");
    expect(html).toContain("No stored method to update.");
  });

  it("FAULT 2 · METERS resolves `qualifier`, and falls back to the asset number ALONE", () => {
    const html = visible(
      renderDetail("/accounts/acc-10432", {
        detail: detail({
          meters: [
            { id: "m-1", asset_no: "SM-7045", qualifier: "sub" },
            { id: "m-2", asset_no: "W-5045", qualifier: "master" },
            // A value this product does not mint. B14 rule 31 says the CODE may
            // not reach the screen, so the row is the asset number and nothing.
            { id: "m-3", asset_no: "X-0001", qualifier: "wat" as unknown as string },
          ],
        }),
      }),
    );
    expect(html).toContain("SM-7045");
    expect(html).toContain("Sub-meter");
    expect(html).toContain("W-5045");
    expect(html).toContain("Master meter");
    // The raw wire values, which the screen printed at a clerk until today.
    expect(html).not.toContain("· sub");
    expect(html).not.toContain("· master");
    // …and `(sub)` / `(master)`, which exist in the catalogue and are the same
    // code in brackets rather than a clerk's words.
    expect(html).not.toContain("(sub)");
    // Scoped to the group: `wat` is a substring of `water`, which this account's
    // SERVICE table legitimately carries. A negative assertion over the whole
    // document is a check that fails for a reason it was never about.
    const group = html.slice(html.indexOf('data-overview-group="meters"'));
    const list = group.slice(0, group.indexOf("</ul>"));
    expect(list).toContain("X-0001");
    expect(list).not.toContain("wat");
  });

  it("FAULT 3 · the header draws the drawn chips, each resolved through its catalogue", () => {
    const head = header(renderDetail("/accounts/acc-10432", { detail: detail() }));
    expect(head).toContain(">Active<");
    expect(head).toContain(">Billable<");
    expect(head).toContain(">Residential<");
    expect(head).toContain(">Regular account<");
    // B14 rule 31 — not one of the three RAW values reaches the header.
    expect(head).not.toContain("billable<");
    expect(head).not.toContain("residential<");
    expect(head).not.toContain("regular<");
  });

  it("FAULT 3 · the sub-type rides on the category chip and never alone", () => {
    const head = header(
      renderDetail("/accounts/acc-10432", {
        detail: detail({ account_subtype: "small_commercial", account_subtype_name: "Small commercial" }),
      }),
    );
    expect(head).toContain("Residential · Small commercial");
    expect(head).not.toContain("small_commercial");
  });

  it("FAULT 3 · a chip whose catalogue does not resolve does NOT render its code", () => {
    // A tenant-added behaviour class and a category the platform catalogue in
    // this fixture does not hold. Absence beats a raw enum (B14 rule 31): a
    // chip has a third option a table cell does not.
    const head = header(
      renderDetail("/accounts/acc-10432", {
        detail: detail({
          account_type: "not_in_the_catalogue",
          status_behavior_class: "some_tenant_class" as unknown as AccountDetail["status_behavior_class"],
        }),
      }),
    );
    expect(head).not.toContain("not_in_the_catalogue");
    expect(head).not.toContain("some_tenant_class");
    // The status and the kind are unaffected — one chip failing to resolve does
    // not take the row with it.
    expect(head).toContain(">Active<");
    expect(head).toContain(">Regular account<");
  });

  it("FAULT 4 · BILLING PREFERENCES carries a LIVE control, not a refusal", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail(), access: "Full" });
    const group = html.slice(html.indexOf('data-overview-group="billing-preferences"'));
    const head = group.slice(0, group.indexOf("</div>") + 6);
    expect(head).toContain("Edit billing preferences");
    // ⚠ `disabled=""` AND NOT `"disabled"`: the kit's button carries
    // `disabled:opacity-45` in its CLASS STRING whatever its state, so the bare
    // word is in the markup of every button on the screen and a `not.toContain`
    // on it can never fail. Law 7 — a check you cannot describe a false pass
    // for is a check you do not understand.
    expect(head).not.toContain('disabled=""');
    // …and a clerk who may not write still sees it, refusing with its reason
    // (`BR-SHL-025`), rather than not seeing it at all.
    const readOnly = renderDetail("/accounts/acc-10432", { detail: detail(), access: "View" });
    const ro = readOnly.slice(readOnly.indexOf('data-overview-group="billing-preferences"'));
    expect(ro.slice(0, ro.indexOf("</div>") + 6)).toContain('disabled=""');
  });

  it("FAULT 4 · CUSTOMER and MAILING ADDRESS are LIVE, and PORTAL ACCESS still refuses", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail(), access: "Full" });
    const head = (slug: string) => {
      const group = html.slice(html.indexOf(`data-overview-group="${slug}"`));
      return group.slice(0, group.indexOf("</div>") + 6);
    };
    // ⚠ **THE `customer` REFUSAL WAS STALE ABOUT THE WRONG TABLE.** It pointed
    // at `BR-CUS-1054`, which shipped `PATCH /customers/{id}` — the `customers`
    // row, on the CUSTOMER's own screen. This group renders `contacts`, keyed
    // to the ACCOUNT, and nothing wrote those; `PATCH /accounts/{id}/contact`
    // is the door built with this fix.
    expect(head("customer")).toContain("Edit customer");
    expect(head("customer")).not.toContain('disabled=""');
    // Hard rule 8's first named exception had a CREATE path and no correction
    // path at all.
    expect(head("mailing-address")).toContain("Edit mailing address");
    expect(head("mailing-address")).not.toContain('disabled=""');
    // ⚠ **AND PORTAL ACCESS STAYS REFUSED, WHICH IS A CORRECT REFUSAL RATHER
    // THAN THE FOURTH GAP.** Its three rows are DERIVED from portal
    // credentials and sessions; a customer enrols themselves (`CR-068`) and no
    // staff door creates a sign-in. A refusal that is true is not a defect, and
    // this case is what stops a later sweep "finishing the set".
    expect(head("portal-access")).toContain('disabled=""');
    expect(html).toContain("The customer signs up themselves.");
  });

  it("FAULT 5 · USAGE TREND is a TABLE with a Month column, and draws no chart", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail(), usage: usagePayload() });
    // ⚠ **THE SLICE IS TAKEN ON THE HOOK, SO IT MUST EXIST FIRST.** Without
    // this the group slice is the empty string and every assertion below fails
    // for the wrong reason — law 7's *looking at the wrong thing*.
    expect(html).toContain('data-overview-group="usage-trend"');
    const group = html.slice(html.indexOf('data-overview-group="usage-trend"'));
    const head = group.slice(0, group.indexOf("</div>") + 6);
    expect(head).toContain("Usage trend");
    expect(head).toContain("Details →");
    // The window control the drawing draws on this group, kept.
    expect(group).toContain("12 months");
    expect(group).toContain("24 months");
    // A TABLE, the drawing's own `MONTH` column, and the months newest first.
    expect(group).toContain("<table");
    expect(group).toContain("Month");
    expect(group.indexOf("2026-08")).toBeLessThan(group.indexOf("2026-07"));
    // …and NO chart. `UsageChart` draws its bar row as `role="img"`; that is
    // the thing the Product Owner asked to be replaced here.
    expect(group).not.toContain('role="img"');
    // ⚠ **THE READ-OUT ROW STAYS — the PO said so in the same breath — AND IT
    // IS ASSERTED BY ITS IDS, NOT BY ITS LABELS.** The labels belong to the
    // Usage TAB's component, which this group composes rather than copies, and
    // that lane renamed them on the same day (`Average month` → `Average`,
    // and the year-on-year figure became `Vs last month`). Pinning another
    // lane's wording here would make their next copy fix fail in a case about
    // the Overview's table.
    expect(group).toContain('data-testid="usage-readouts"');
    expect(group).toContain('data-readout="avg"');
    expect(group).toContain('data-readout="peak"');
    expect(group).toContain('data-readout="low"');
  });

  it("FAULT 6 · no rationale sentence is left on this tab", () => {
    const html = visible(renderDetail("/accounts/acc-10432", { detail: detail() }));
    // ACCOUNT SETUP's 23 words.
    expect(html).not.toContain("written by the returned-mail workflow");
    // PORTAL ACCESS's orphaned print-floor sentence.
    expect(html).not.toContain("Bills are always printed as well.");
    // CUSTOMER's 24 words about the data model.
    expect(html).not.toContain("This is one contact on one account.");
  });

  it("SERVICE draws the three drawn columns on the Overview, where the drawing puts them", () => {
    const html = overview(renderDetail("/accounts/acc-10432", { detail: detail() }));
    const group = html.slice(html.indexOf('data-overview-group="service"'));
    const table = group.slice(0, group.indexOf("</table>"));
    expect(table).toContain("Started");
    expect(table).toContain("Ended");
    // The drawn ENDED cell for an open agreement, which is not a dash.
    expect(table).toContain("Still open");
  });

  it("METERS states the absence and DERIVES the count — three agreements read as three", () => {
    const three = detail({
      meters: [],
      service_agreements: [
        { id: "sa-1", service_point_id: "sp-1", service: "electric", started_on: "2024-02-14", ended_on: null },
        { id: "sa-2", service_point_id: "sp-2", service: "water", started_on: "2024-02-14", ended_on: null },
        { id: "sa-3", service_point_id: "sp-3", service: "gas", started_on: "2024-02-14", ended_on: null },
      ],
    });
    const html = visible(renderDetail("/accounts/acc-10432", { detail: three }));
    expect(html).toContain("No meter is assigned");
    expect(html).toContain("This account holds 3 service agreements and no measuring asset.");
    // ⚠ The drawing's own figure. Asserting it would be B14 rule 37's defect.
    expect(html).not.toContain("holds two service agreements");
  });

  it("METERS lists the meters when the unit carries them, and states nothing", () => {
    const html = visible(renderDetail("/accounts/acc-10432", { detail: detail() }));
    expect(html).toContain("M-4021");
    expect(html).not.toContain("No meter is assigned");
  });

  it("HISTORY is a headed group with `All bills →`, and its empty state is the drawn one", () => {
    const html = visible(renderDetail("/accounts/acc-10432", { detail: detail(), bills: [] }));
    const group = html.slice(html.indexOf('data-overview-group="history"'));
    // ⚠ **THE WINDOW WAS 400 AND WENT RED ON `56fd6d47f`**, which lengthened
    // `GROUP_HEAD` by ~130 characters of utility classes to take a group's edit
    // control out of the flow. Nothing about the heading row changed; the slice
    // simply stopped reaching the control. A window tuned to a class string is
    // a window the next class string breaks, so it is sized to the head now.
    const head = group.slice(0, group.indexOf("</div>") + 6);
    expect(head).toContain("History");
    expect(head).toContain("All bills →");
    expect(html).toContain("No bill has been issued");
    // ⚠ **REWRITTEN 2026-09-13, B14 rule 33's sweep.** The drawn HISTORY block
    // carried 35 words ending *"…which is why the ageing is counted from that
    // rather than from a bill's due date"*. That clause is RATIONALE and is
    // zero words on screen; the six-word FACT stays, and it is the sentence
    // `ACC-02`'s own drawing opens with. The reason lives in the register.
    expect(html).toContain("No bill has been raised yet.");
    expect(html).not.toContain("carried in as an opening figure");
  });

  it("CUSTOMER RECORD shows `customer_no` and NEVER the customer's database id (B14 rule 31)", () => {
    const linked = detail({
      customer_no: "C-00417",
      customer: {
        id: "cst-9e21f4c6-0000-4aaa-9bbb-cccccccccccc",
        kind: "person",
        display_name: "Miller, Sarah",
        external_ref: null,
        accounts: [
          { id: "acc-10432", account_no: "A-10432" },
          { id: "acc-10433", account_no: "A-10433" },
        ],
      },
    });
    const html = visible(renderDetail("/accounts/acc-10432", { detail: linked }));
    const group = html.slice(html.indexOf('data-overview-group="customer-record"'));
    const block = group.slice(0, group.indexOf("</section>"));
    expect(block).toContain("Customer ID");
    expect(block).toContain("C-00417");
    expect(block).toContain("Linked accounts");
    expect(block).not.toContain("cst-9e21f4c6");
  });

  // ⚠ AMENDED 2026-10-20 (record links, PO 2026-10-19): `Linked accounts` is a
  // LIST of account links and no longer a count, so nothing linked draws the
  // dash — still never a blank. This case read `counts zero` until then.
  it("CUSTOMER RECORD says so when nothing is linked, and draws a dash rather than blanking", () => {
    const html = visible(renderDetail("/accounts/acc-10432", { detail: detail() }));
    const group = html.slice(html.indexOf('data-overview-group="customer-record"'));
    const block = group.slice(0, group.indexOf("</section>"));
    expect(block).toContain("Not linked to a customer record.");
    expect(block).toContain(">—<");
    expect(block).not.toContain("data-linked-accounts");
  });

  it("record links — unit, premises, meter and every OTHER linked account open their own pages", () => {
    const html = renderDetail("/accounts/acc-10432", {
      detail: detail({
        premise_address: "1408 Elm St",
        service_premises_id: "prm-1408",
        customer: {
          id: "cus-1",
          customer_no: "C-00001",
          kind: "person",
          display_name: "Rosa Alvarez",
          accounts: [
            { id: "acc-10432", account_no: "A-10432" },
            { id: "acc-10433", account_no: "A-10433" },
          ],
        } as unknown as AccountDetail["customer"],
        customer_no: "C-00001",
      }),
    });
    const unitGroup = html.slice(html.indexOf('data-overview-group="unit"'));
    const unitBlock = unitGroup.slice(0, unitGroup.indexOf("</section>"));
    expect(unitBlock).toContain(`href="/${TEST_TENANT}/premises/units/u-10432a"`);
    expect(unitBlock).toContain(`href="/${TEST_TENANT}/premises/prm-1408"`);
    expect(html).toContain(`href="/${TEST_TENANT}/assets/ast-4021"`);
    const group = html.slice(html.indexOf('data-overview-group="customer-record"'));
    const block = group.slice(0, group.indexOf("</section>"));
    // The other account is a link; the open one is plain and marked current.
    expect(block).toContain(`href="/${TEST_TENANT}/accounts/acc-10433"`);
    expect(block).not.toContain(`href="/${TEST_TENANT}/accounts/acc-10432"`);
    expect(block).toContain('aria-current="page">A-10432<');
    // Customer ID stays TEXT — there is no customer page (PO 2026-10-19).
    expect(block).toContain("C-00001");
    expect(block).not.toContain("/customers/");
  });

  it("BILLING PREFERENCES carries the five drawn rows", () => {
    const html = visible(renderDetail("/accounts/acc-10432", { detail: detail() }));
    const group = html.slice(html.indexOf('data-overview-group="billing-preferences"'));
    const block = group.slice(0, group.indexOf("</section>"));
    for (const label of [
      "Autopay",
      "Paperless",
      "Text reminders",
      "Preferred language",
      "Notification template",
    ]) {
      expect(block).toContain(label);
    }
    expect((block.match(/<dt>/g) ?? []).length).toBe(5);
  });

  it("the notification template is a STATED ABSENCE — never a fabricated `Tenant default`", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    expect(visible(html)).toContain("Not shown yet");
    // The drawing's value. `account_detail_dict` serves no resolved template
    // name at all, so printing it would be a value this screen never received.
    expect(html).not.toContain("Tenant default");
  });

  it("three facts MOVED and none is duplicated — a fact belongs to exactly one group", () => {
    const html = overview(visible(renderDetail("/accounts/acc-10432", { detail: detail() })));
    // `Preferred language` left ACCOUNT SETUP; `Paperless` and `Text reminders`
    // left PORTAL ACCESS. One occurrence each, on the whole tab.
    for (const label of ["Preferred language", "Paperless", "Text reminders"]) {
      expect(html.split(`<dt>${label}</dt>`).length - 1).toBe(1);
    }
  });

  it("PORTAL ACCESS is the drawn three rows, with `Locked` a row of its own", () => {
    const html = visible(renderDetail("/accounts/acc-10432", {
      detail: detail({
        portal_access: { logins: 2, locked: 0, last_sign_in: null, unreadable: [] },
      }),
    }));
    const group = html.slice(html.indexOf('data-overview-group="portal-access"'));
    const block = group.slice(0, group.indexOf("</section>"));
    expect((block.match(/<dt>/g) ?? []).length).toBe(3);
    expect(block).toContain("Sign-in");
    expect(block).toContain("Locked");
    expect(block).toContain("Last sign-in");
  });

  it("MAILING ADDRESS is its own group now, not a sub-head inside Customer", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    const customer = html.slice(
      html.indexOf('data-overview-group="customer"'),
    );
    // The Customer group closes BEFORE the mailing group opens.
    expect(customer.indexOf("</section>")).toBeLessThan(
      customer.indexOf('data-overview-group="mailing-address"'),
    );
    expect(html).toContain("Same as the service address.");
  });

  it("ACCOUNT SETUP carries the drawn heading and has lost `Preferred language`", () => {
    const html = visible(renderDetail("/accounts/acc-10432", { detail: detail() }));
    const group = html.slice(html.indexOf('data-overview-group="account-setup"'));
    const block = group.slice(0, group.indexOf("</section>"));
    expect(block).toContain("Account setup");
    expect(block).not.toContain("Preferred language");
    expect(block).toContain("Category");
  });

  /**
   * ⚠ **ROW ORDER IS PART OF THE DRAWING, NOT A DETAIL.** The same sequences the
   * browser census carries in its own `DRAWN` table
   * (`10-scripts/render-checks/acc02-overview-conformance.mjs`) — kept here too
   * because this is the check that runs on every commit, and a row that drifts
   * out of sequence is invisible to `tsc`, to eslint and to every other case in
   * this file.
   */
  it("each group's rows are in the DRAWN sequence, not the order lanes added them", () => {
    const html = visible(renderDetail("/accounts/acc-10432", {
      detail: detail({
        portal_access: { logins: 0, locked: 0, last_sign_in: null, unreadable: [] },
      }),
    }));
    const drawn: Record<string, string[]> = {
      money: ["Basis", "Source", "Aging", "Days past due", "Aging source"],
      plan: ["Plan", "Code", "Version", "In force since"],
      customer: ["Full name", "Email", "Phone", "Date of birth", "Government ID"],
      "customer-record": ["Customer ID", "Linked accounts"],
      "billing-preferences": [
        "Autopay", "Paperless", "Text reminders", "Preferred language",
        "Notification template",
      ],
      "account-setup": [
        "Category", "Sub-category", "Account kind", "Master account", "Behavior class",
        "Tax exempt", "Exemption reference", "Exemption expires", "Bad address",
        "Opened", "Closed",
      ],
      "portal-access": ["Sign-in", "Locked", "Last sign-in"],
    };
    for (const [slug, labels] of Object.entries(drawn)) {
      const from = html.indexOf(`data-overview-group="${slug}"`);
      expect(from, `${slug} is on the screen`).toBeGreaterThan(-1);
      const block = html.slice(from, html.indexOf("</section>", from));
      const seen = labels.map((label) => block.indexOf(`<dt>${label}</dt>`));
      expect(seen.filter((at) => at === -1), `${slug}: every drawn row present`).toEqual([]);
      expect(
        [...seen].sort((a, b) => a - b),
        `${slug}: the drawn rows in the drawn sequence`,
      ).toEqual(seen);
    }
  });

  it("DEF-CUS-9788: Billing preferences shows the PO on bills, last, only when there is one", () => {
    const withPo = visible(renderDetail("/accounts/acc-10432", { detail: detail({ po_number: "PO-2026-118" }) }));
    const from = withPo.indexOf('data-overview-group="billing-preferences"');
    const block = withPo.slice(from, withPo.indexOf("</section>", from));
    expect(block).toContain("<dt>PO on bills</dt>");
    expect(block).toContain("PO-2026-118");
    expect(block.indexOf("<dt>Notification template</dt>")).toBeLessThan(block.indexOf("<dt>PO on bills</dt>"));
    const without = visible(renderDetail("/accounts/acc-10432", { detail: detail({ po_number: null }) }));
    expect(without).not.toContain("PO on bills");
  });

  it("the census hooks a browser check selects on are actually in the markup", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail() });
    expect(html).toContain("data-account-overview");
    // ⚠ 11 → 13 on 2026-09-13: `usage-trend` and `payment-method` were on the
    // screen and unhooked. → 14 the same day, when the drawn UNIT group was
    // built (`DEF-CUS-5163`). → 15 on 2026-09-23, the PO-ruled CO-APPLICANT
    // (`DEF-CUS-6391`). See the group-list case at the top of this suite.
    expect(groups(html)).toHaveLength(15);
  });
});



/* ══════════════════════════════════════════════════════════════════════════
 * B14 RULE 41 (PO 2026-09-13) — DOCUMENTS · NOTES · AUDIT ARE THEIR DRAWINGS
 * ══════════════════════════════════════════════════════════════════════════
 * `ACC-T10`, `ACC-T11` and `ACC-T12` in
 * `04-docs/05-modules/03-customers/blueprint/02-account-detail.md`, transcribed
 * into `10-scripts/render-checks/drawn/acc02-{documents,notes,audit}.json`.
 *
 * ⚠ **THESE CASES ASSERT PRESENCE, ORDER AND WORDS — NOT THAT THE SCREEN LOOKS
 * LIKE THE DRAWING, WHICH THEY CANNOT.** `renderToStaticMarkup` in the `node`
 * environment computes no layout, so a group in the wrong column, a rule of the
 * wrong width or a gap off the scale is invisible to every line below. The
 * instrument for those is the browser census, and the `data-account-overview` /
 * `data-overview-group` hooks these cases read are what it selects on — which
 * is the whole reason to pin them here: a renamed hook makes the census measure
 * nothing and report a clean zero (hard-won law 7).
 * ══════════════════════════════════════════════════════════════════════════ */
describe("B14 rule 41 — Documents, Notes and Audit are the drawn tabs", () => {
  /** The one pinned note the drawing puts above the table, and one below it. */
  const pinned = {
    id: "n-1",
    account_id: "acc-10432",
    title: "Disputes the opening balance",
    body: "Owner rang about the ten-day notice.",
    author_id: "u-1",
    author_name: "Sam Ortiz",
    pinned: true,
    customer_visible: false,
    created_at: "2026-09-11T11:24:00Z",
  } as AccountNote;
  const plain = {
    ...pinned,
    id: "n-2",
    title: "Reminder sent",
    body: "No reply to the voicemail.",
    author_name: "Dana Whitfield",
    pinned: false,
    created_at: "2026-08-27T09:02:00Z",
  } as AccountNote;

  it("ACC-T10: Documents is ONE named group, hooked for the census, with its one control", () => {
    const html = renderDetail("/accounts/acc-10432?tab=documents", {
      detail: detail(),
      access: "Full",
    });
    expect(html).toContain("data-account-overview");
    expect(html).toContain('data-overview-group="documents"');
    // The drawn heading, and the drawn control beside it rather than above it.
    expect(html).toContain(">Documents</h3>");
    expect(html).toContain("Upload document");
    // Exactly one group on this tab — the drawing gives it one column.
    expect(html.match(/data-overview-group="documents"/g)).toHaveLength(1);
  });

  it("ACC-T11: Notes draws the pinned note as a CARD and the rest as the drawn table", () => {
    const html = renderDetail("/accounts/acc-10432?tab=notes", {
      detail: detail(),
      access: "Full",
      notes: [pinned, plain],
    });
    expect(html).toContain('data-overview-group="notes"');
    expect(html).toContain(">Notes</h3>");
    expect(html).toContain("Add note");
    // The pinned note, in r10's card, above everything.
    expect(html).toContain('data-note-card=""');
    expect(html).toContain('data-pinned="true"');
    expect(html).toContain("Disputes the opening balance");
    // …and the drawn columns, in the drawn order, below it.
    const heads = ["When", "Who", "Kind", "Note", "Actions"];
    let at = 0;
    for (const head of heads) {
      const next = html.indexOf(`>${head}<`, at);
      expect(next, `${head} is drawn, in the drawn order`).toBeGreaterThan(-1);
      at = next + 1;
    }
    // The UNPINNED note is the row; the pinned one is the card and not both.
    const table = html.slice(html.indexOf("<table"));
    expect(table).toContain("Reminder sent");
    expect(table).not.toContain("Disputes the opening balance");
  });

  it("ACC-T11: KIND is drawn and says so, because account_notes has no kind (DEF-CUS-5145)", () => {
    const html = renderDetail("/accounts/acc-10432?tab=notes", {
      detail: detail(),
      access: "Full",
      notes: [plain],
    });
    // Never blank — a blank cell reads as "nobody knows" — and never an
    // invented `Collections`, which is what the drawing inks.
    expect(html).toContain("Not recorded");
    expect(html).not.toContain(">Collections<");
    // And the five-word fact rule 33 leaves on screen where 35 words stood.
    expect(visible(html)).toContain("A note cannot be corrected.");
  });

  it("ACC-T12: Audit is a named group carrying the ONE shared audit surface", () => {
    const html = renderDetail("/accounts/acc-10432?tab=audit", { detail: detail() });
    expect(html).toContain('data-overview-group="audit"');
    expect(html).toContain(">Audit</h3>");
    // BR-CUS-028's element is inside the group, not loose beneath the tab.
    const group = html.slice(html.indexOf('data-overview-group="audit"'));
    expect(group).toContain('data-rule-ref="BR-CUS-028"');
  });

  it("every one of the three tabs carries the hook the browser census selects on", () => {
    for (const tab of ["documents", "notes", "audit"]) {
      const html = renderDetail(`/accounts/acc-10432?tab=${tab}`, { detail: detail() });
      expect(html, `${tab} has the census root`).toContain("data-account-overview");
      expect(html, `${tab} has its group`).toContain(`data-overview-group="${tab}"`);
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-008@a2e1d59 (story+rules snapshot — EP-CUS-03 lead story; co-packets US-CUS-009/010/011 same epic)
// generated: 2026-08-11 by story-coder (W2 customers FRONTEND lane 2 — S21)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 670 passed / 160 todo across 49 files✔ (622 passed / 148 todo across 47 files was the pre-lane baseline) · vite build✔ · run_gates 14 PASS · 0 FAIL · 1 SKIP✔
// exceptions: E4 every isolation TC (US-CUS-008 TC-6, US-CUS-009 TC-7, US-CUS-010 TC-6, US-CUS-011 TC-8) is server/RLS scope and stays an honest it.todo — G5 covers them · E4 the Activate CLICK path needs a browser: the button and its four reasons are asserted statically here, and the mutation itself is the endpoint wrapper's · E4 US-CUS-009 TC-2's propagation-to-every-linked-account cannot be asserted at all — the customer entity has no table, which is the assertion this file makes instead · E4 US-CUS-010 TC-4's zero-results-after-filter needs a Bills table, which billing owns and has not built · E4 US-CUS-011 TC-6's audit-locked document delete has no endpoint to attempt
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

/* ⊕ `DEF-CUS-9837` — the Co-applicant group lists the account's CO-OWNERS
 * (move-in's record, and New Connect's co-applicant since `DEF-CUS-9830`). It
 * read only the second contact, so an account with Maria Mark as co-owner said
 * *No co-applicant*. What would pass wrongly: asserting the group exists — it
 * always did; this reads her name and the absence of the empty sentence. */
describe("DEF-CUS-9837 — the Co-applicant group shows the account's co-owners", () => {
  function group(html: string): string {
    const start = html.indexOf('data-overview-group="co-applicant"');
    const end = html.indexOf('data-overview-group="mailing-address"');
    return start === -1 ? "" : html.slice(start, end === -1 ? undefined : end);
  }

  it("Maria Mark, saved as a co-owner, is named with her contact facts", () => {
    const html = renderDetail("/accounts/acc-10432", {
      detail: detail({
        co_owners: [{ kind: "co_owner", full_name: "Maria Mark", email: null, phone: "(512) 555-0130" }],
      }),
    });
    const body = group(html);
    expect(body).toContain("Maria Mark");
    expect(body).toContain("(512) 555-0130");
    expect(body).not.toContain(t("customers.account.noCoApplicant"));
  });

  it("an account with neither a second contact nor a co-owner still says so", () => {
    const html = renderDetail("/accounts/acc-10432", { detail: detail({ co_owners: [] }) });
    expect(group(html)).toContain(t("customers.account.noCoApplicant"));
  });
});
