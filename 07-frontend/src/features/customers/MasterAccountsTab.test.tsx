// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 wave F — R7 / `ACC-S17`, the **Accounts** tab
//           on a MASTER account's detail screen. Drawing: `05-prototype/
//           02 Accounts Menu Blueprint.pdf` p189–192 (pinned `033981d4f`,
//           sha256 `c8d596bb505f5020ce4b9474…`), transcribed into
//           `04-docs/05-modules/03-customers/08-screen-layouts.md` §R7.
//           Screens: S21 (the account detail)
// Story:    US-CUS-008 (the S21 tab strip is URL state)
// Rules:    BR-CUS-068 (a master account IS an ordinary `accounts` row with
//           `kind='master'` — no parent id, no child rows, no rolled-up
//           balance) · BR-CUS-1010 (it hangs off the ADDRESS: `premises_id`
//           set, `unit_id` null) · BR-CUS-1048 (this tab, ruled below) ·
//           BR-CUS-1046 (a list opens in CREATION order, newest first) ·
//           B14 rule 12 (the toolbar's grammar — a dimension is a filter chip,
//           never a segment strip) · B14 rule 31 (no database id on screen) ·
//           B14 rule 32 (a stated absence is CLOSED by default)
// ───────────────────────────────────────────────────────
// ⚠ **EVERY CASE HERE WAS PROVED RED BEFORE THE TAB EXISTED** (hard-won law 7),
// through `npx vitest run src/features/customers/MasterAccountsTab.test.tsx` —
// the harness that will run it — and not through a node script. The first run
// could not even resolve `./MasterAccountsTab`:
//
//     Error: Failed to load url ./MasterAccountsTab (resolved id:
//     /home/user/SMARTBillHub/07-frontend/src/features/customers/
//     MasterAccountsTab) in .../MasterAccountsTab.test.tsx. Does the file
//     exist?
//
// **AND THE TWO HALVES OF HARD-WON LAW 2 WERE THEN PROVED SEPARATELY, WHICH
// IS THE POINT OF SPLITTING THEM.** With the component present and the mount
// disabled (`{false && active === …}`) — a tab LABEL over no body, which is
// what a live strip in front of dead UI looks like — the four table cases went
// red and the strip cases stayed GREEN:
//
//     × draws the blueprint's seven columns … → expected [] to deeply equal
//       [ 'Account', 'Unit', 'Occupant', …(5) ]
//     × the master's UNIT cell … → expected '<div class="cus-page">…' to
//       contain 'Common areas ×2'
//     Tests  4 failed | 5 passed (9)
//
// With the mount restored and the strip's `kind` argument dropped
// (`accountTabs(translate)`) — the mirror, a live body no door points at —
// FIVE went red and the strip case named the wrong neighbour:
//
//     × the master's own strip RENDERS thirteen tabs with Accounts second
//       → expected 'Bills' to be 'Accounts'
//     Tests  5 failed | 4 passed (9)
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { AccountDetail, AccountRow, AccountsPage } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import {
  ACCOUNT_TAB_IDS,
  AccountDetailPage,
  accountDetailQueryKey,
  accountTabIds,
  accountTabs,
} from "./AccountDetailPage";
import { MASTER_ACCOUNTS_STATE, masterAccountsQueryKey } from "./MasterAccountsTab";
import { ACCOUNTS_PERMISSION, ACCOUNT_CATEGORIES_QUERY_KEY } from "./customersShared";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** 1408 Elm Street — the blueprint's own building, and BR-MET-101's worked
 *  case. The owner account hangs off the ADDRESS (`BR-CUS-1010`): it names no
 *  unit and carries `premises_id`. */
const PREMISES = "prm-1408-elm";

function detail(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: "acc-10001",
    account_no: "A-10001",
    kind: "master",
    name: "Elm Street Holdings LLC",
    unit_id: null,
    unit_label: null,
    premises_id: PREMISES,
    premise: "1408 Elm Street",
    services: ["electric", "water"],
    balance: "69.600000",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    balance_not_yet_billable: false,
    balance_cached: "0.000000",
    currency: "USD",
    status: "active",
    status_name: "Active",
    status_behavior_class: "billable",
    account_type: "residential",
    account_subtype: null,
    autopay: false,
    opened_at: "2023-03-06",
    closed_at: null,
    last_bill_at: null,
    aging: null,
    deposit_on_file: "0.000000",
    deposit_received_on: null,
    credit_tier: null,
    tax_exempt: false,
    tax_exempt_ref: null,
    tax_exempt_expires: null,
    bad_address: false,
    nsf_count: 0,
    preferred_language: null,
    custom_data: {},
    contacts: [],
    addresses: [],
    service_agreements: [],
    meters: [],
    plan: null,
    plan_snapshot_unavailable: "BR-CUS-029",
    unit_plan: null,
    customer: null,
    // R7's own column: the master's UNIT cell reads `Common areas ×2`, because
    // one master covers several by hanging off the address and reaching each
    // through its OWN open service agreements (`covered_unit_ids`).
    covered_units: 2,
    ...over,
  } as unknown as AccountDetail;
}

function row(over: Partial<AccountRow> = {}): AccountRow {
  return {
    id: "acc-11602",
    account_no: "A-11602",
    customer_no: null,
    name: "Ncube, T.",
    kind: "regular",
    unit_id: "u-e",
    unit_label: "Unit E",
    premises_id: PREMISES,
    premise: "1408 Elm Street · E",
    services: ["electric"],
    balance: "512.800000",
    balance_currency: "USD",
    balance_basis: "posting",
    balance_source: "ledger",
    balance_unavailable: [],
    balance_not_yet_billable: false,
    balance_cached: "0.000000",
    currency: "USD",
    status: "marked_disconnect",
    status_name: "Marked disconnect",
    status_behavior_class: "billable_base_only",
    account_type: "residential",
    account_subtype: null,
    account_subtype_name: null,
    autopay: false,
    opened_at: "2024-07-19",
    closed_at: null,
    last_bill_at: null,
    aging: null,
    ...over,
  } as unknown as AccountRow;
}

/** The master's OWN row, as `GET /accounts?f.premises_id=` returns it — it is
 *  an ordinary account row, which is why leaving it out would be the odd
 *  choice (the blueprint's own words). */
const masterRow = row({
  id: "acc-10001",
  account_no: "A-10001",
  name: "Elm Street Holdings LLC",
  kind: "master",
  unit_id: null,
  unit_label: null,
  balance: "69.600000",
  status: "active",
  status_name: "Active",
  status_behavior_class: "billable",
  opened_at: "2023-03-06",
});

function page(rows: AccountRow[]): AccountsPage {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    rollup: { outstanding: null, currency: null, past_due_60_plus: null },
  } as unknown as AccountsPage;
}

function renderDetail(
  path: string,
  seed: { detail: AccountDetail; rows?: AccountRow[]; access?: string },
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(ACCOUNT_CATEGORIES_QUERY_KEY, {
    selectable: [{ code: "residential", name: "Residential" }],
    legacy: [],
  });
  queryClient.setQueryData(accountDetailQueryKey(seed.detail.id), seed.detail);
  queryClient.setQueryData(queryKeys.myPermissions, {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [
      { code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access: seed.access ?? "write" },
    ],
  });
  if (seed.rows !== undefined && seed.detail.premises_id != null) {
    queryClient.setQueryData(
      masterAccountsQueryKey(seed.detail.premises_id, MASTER_ACCOUNTS_STATE),
      page(seed.rows),
    );
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* Mounted under the REAL path pattern — a bare MemoryRouter leaves
            `useParams().tenant` undefined and every link the page builds comes
            out `//accounts/…`, which reads as a fine string to `toContain`
            (hard-won law 2's fixture clause). */}
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <Routes>
            <Route path="/:tenant/accounts/:accountId" element={<AccountDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The tab strip's labels, in render order. */
function tabOrder(html: string): string[] {
  const strip = html.slice(html.indexOf('role="tablist"'));
  return [...strip.matchAll(/role="tab"[^>]*>([^<]+)</g)].map((m) => m[1]);
}

/** The `<thead>` row of the one table on the tab, as a list of column labels. */
function columnHeadings(html: string): string[] {
  const start = html.indexOf("<thead>");
  const end = html.indexOf("</thead>", start);
  if (start === -1 || end === -1) {
    return [];
  }
  return [...html.slice(start, end).matchAll(/<th[^>]*>(?:<button[^>]*>)?([^<]+)</g)].map(
    (m) => m[1],
  );
}

describe("CR-094 R7 / ACC-S17 — the Accounts tab exists only on a master account", () => {
  it("the tab vocabulary gains `accounts` immediately after `overview`, for a master only", () => {
    // PO, verbatim: *"if the account is of master account, then after the
    // overview tab, it should show the accounts that are connected to that
    // master account"*.
    // ⚠ **AMENDED 2026-09-23 — `BR-CUS-1094` PUT A SECOND CONDITIONAL TAB
    // BESIDE THIS ONE** (`Units`, third), so the master's strip is FOURTEEN.
    // This case is kept asserting the FULL order rather than just `[1]`,
    // because the thing it guards is the PO's *"after the overview tab"* and a
    // looser assertion would stop noticing a third insertion.
    expect(accountTabIds("master")).toEqual([
      "overview",
      "accounts",
      "units",
      ...ACCOUNT_TAB_IDS.slice(1),
    ]);
    // …and an ordinary account's strip is BYTE-FOR-BYTE what it was.
    expect(accountTabIds("regular")).toEqual([...ACCOUNT_TAB_IDS]);
    expect(accountTabs(t, "master").map((tab) => tab.label)[1]).toBe("Accounts");
    expect(accountTabs(t).map((tab) => tab.label)).not.toContain("Accounts");
  });

  it("the master's own strip RENDERS fourteen tabs with Accounts second", () => {
    // Hard-won law 2: the constant above cannot promise the strip.
    // ⚠ **THIS READ `thirteen` AND `+ 1` UNTIL 2026-09-23**, when `BR-CUS-1094`
    // added `Units` as the second conditional tab. Accounts is still SECOND —
    // which is what the 2026-09-12 ruling actually says and what this case is
    // for — and the LENGTH moved by one.
    const html = renderDetail("/accounts/acc-10001", { detail: detail(), rows: [masterRow] });
    const order = tabOrder(html);
    expect(order[0]).toBe("Overview");
    expect(order[1]).toBe("Accounts");
    expect(order[2]).toBe("Units");
    expect(order).toHaveLength(ACCOUNT_TAB_IDS.length + 2);
  });

  it("a REGULAR account's strip is unchanged and `?tab=accounts` falls back to Overview", () => {
    const regular = detail({
      id: "acc-10432",
      account_no: "A-10432",
      kind: "regular",
      unit_id: "u-a",
      unit_label: "A",
      covered_units: null,
    } as Partial<AccountDetail>);
    const html = renderDetail("/accounts/acc-10432?tab=accounts", { detail: regular });
    expect(tabOrder(html)).not.toContain("Accounts");
    expect(tabOrder(html)).toHaveLength(ACCOUNT_TAB_IDS.length);
    // BR-SHL-011's fallback law: an unknown tab id opens the first tab rather
    // than a blank body.
    expect(html).toContain('aria-selected="true"');
  });
});

describe("CR-094 R7 — what the one table draws", () => {
  const html = () =>
    renderDetail("/accounts/acc-10001?tab=accounts", {
      detail: detail(),
      rows: [masterRow, row(), row({ id: "acc-11455", account_no: "A-11455" })],
    });

  it("draws the blueprint's seven columns, in its order, plus the action column", () => {
    // Read off the rendered page 191, left to right.
    expect(columnHeadings(html())).toEqual([
      "Account",
      "Unit",
      "Occupant",
      "Kind",
      "Status",
      "Since",
      "Balance",
      "Actions",
    ]);
  });

  it("the master is IN the list, marked as the one you are on, and has no Open action", () => {
    const out = html();
    expect(out).toContain("This account");
    // ⚠ **THE FIRST DRAFT OF THIS ASSERTION COUNTED HREFS AND EXPECTED 2; IT
    // GOT 4, AND THE TEST WAS WRONG RATHER THAN THE SCREEN.** Each tenant row
    // carries TWO ways out — the account number in the identity cell and the
    // `Open` row action — which is what the drawing shows. So the thing worth
    // pinning is the ROW ACTION count and the master's own absence from every
    // href, not a total that conflates two controls.
    expect([...out.matchAll(/aria-label="Open account"/g)]).toHaveLength(2);
    expect(out).not.toContain('href="/brazosbend/accounts/acc-10001"');
  });

  it("the master's UNIT cell counts the units its own agreements reach", () => {
    // `covered_units: 2` → *Common areas ×2*. It is a real, direct linkage —
    // this account's own open service agreements — and never a unit label,
    // because a master names no unit at all (`BR-CUS-1010`).
    expect(html()).toContain("Common areas ×2");
  });

  it("there is deliberately NO total under the balance column", () => {
    const out = html();
    expect(out).not.toContain("<tfoot");
    // The three rows sum to $769.20 and that figure means nothing: it is the
    // owner's own $69.60 plus $699.60 owed by two unrelated tenants.
    expect(out).not.toContain("769.20");
  });

  it("asks the SERVER for the accounts at this address — no new endpoint", () => {
    // `GET /accounts?f.premises_id=` is `CR-056` W1's own filter. The query key
    // carries the premises so a second building cannot read this one's page.
    expect(masterAccountsQueryKey(PREMISES, MASTER_ACCOUNTS_STATE)[2]).toBe(PREMISES);
  });

  it("states its two absences in a CLOSED disclosure, never as prose over the table", () => {
    const out = html();
    // B14 rule 32. `<details>` with no `open` attribute is closed.
    const details = out.slice(out.indexOf("<details"));
    expect(details.slice(0, details.indexOf(">"))).not.toContain("open");
    expect(out).toContain(t("customers.account.accounts.notes"));
  });
});
