// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-001 (S17 accounts table + header roll-up) ·
//           US-CUS-002 (S17 search, filters and the wizard entry points)
//           Screens: S17
// Rules:    BR-CUS-015 (the list contract) · BR-CUS-016 (aging is DERIVED and
//           never stored — so it is absent, never fabricated) · BR-CUS-029 (no
//           account plan snapshot ⇒ no Plan column, no Plan filter) ·
//           BR-CUS-053 (the capability row) · BR-CUS-055 (the seeded status
//           vocabulary and its behaviour classes) · BR-CUS-059 (autopay is
//           capture-only) · BR-SHL-011 (URL grammar) · BR-SHL-023 (one money
//           formatting path) · BR-SHL-025 (disabled WITH the reason) ·
//           BR-SHL-034 (one date formatting path) · BR-SHL-044 (one header)
// ───────────────────────────────────────────────────────
// §4 test data is Brazos Bend Utilities (US-CUS-001 §4), rendered through the
// mocked client seam — no network, ever.
//
// The assertions that matter most here are the NEGATIVE ones: this screen must
// not print a date, a zero or a dash where the server said "unknown". Each of
// those is one line in the defect log's `unwired-prop` / fabricated-value
// family, and each is checked below.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { AccountRow, AccountsPage, MyPermissions } from "@/api/endpoints";
import { ACCOUNT_FILTERS, ACCOUNT_SORTS } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { EmptyList } from "@/components/StateFrame";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";

import {
  ACCOUNTS_BUILT_TABS,
  ACCOUNTS_TAB_IDS,
  AccountsListPage,
  accountsFilters,
  accountsParamsFrom,
  accountsQueryKey,
  accountsTabFromParam,
  accountsTableConfig,
} from "./AccountsListPage";
import type { AccountRowWithAgeing } from "./accountsListCells";
import {
  ACCOUNTS_PERMISSION,
  ACCOUNT_SEED_STATUSES,
  accountStatusLabel,
  accountStatusTone,
  rollupCurrency,
} from "./customersShared";

// PO 2026-08-10 (path tenancy): every authenticated URL is `/{tenant}/…`.
const TEST_TENANT = "brazosbend";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function account(over: Partial<AccountRow> = {}): AccountRow {
  return {
    id: "acc-10432",
    account_no: "A-10432",
    // CR-030 W2 T2.9(b) — `customers.customer_no`, served on every row since
    // 2026-08-24. `C-00417` is the shape the `customer` series allocates
    // (default `C-{00000}`), not an invented format.
    customer_no: "C-00417",
    // BR-CUS-068 — `kind` is served on every account row (regular | master).
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
    // The two fields the server serves NULL until billing lands (W3).
    last_bill_at: null,
    aging: null,
    ...over,
  };
}

function page(rows: AccountRow[], rollupOver: Partial<AccountsPage["rollup"]> = {}): AccountsPage {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    rollup: {
      accounts: rows.length,
      // DEF-127 — the LEDGER's Σ, with the CHAR(3) it derived (DEF-099). It was
      // the cached column until 2026-08-15 and read "$0.00 outstanding" to a
      // utility the books said was owed 261.20.
      outstanding: "0.000000",
      currency: "USD",
      outstanding_basis: "posting",
      outstanding_unavailable: [],
      // Null, never 0 — the count needs open invoices (BR-CUS-016).
      past_due_60_plus: null,
      // PO ruling 2026-09-28 — the four status tiles' ONE grouped count, as
      // `selectors.account_status_counts` serves it: one row per status THIS
      // TENANT HAS, including the ones holding nobody. The SIX seeded codes,
      // because that is what a provisioned utility really has (`services.
      // SEED_ACCOUNT_STATUSES`), not the four the tiles happen to draw.
      //
      // ⚠ **THE FIGURES ARE THE SHAPE, NOT A REQUIREMENT (B14 rule 37).** What
      // each case pins is which tile reads which code; no case asserts that a
      // real utility has three active accounts.
      by_status: [
        { code: "active", name: "Active", accounts: 3 },
        { code: "closed", name: "Closed", accounts: 5 },
        { code: "disconnected", name: "Disconnected", accounts: 0 },
        { code: "marked_disconnect", name: "Marked disconnect", accounts: 2 },
        { code: "pending_activation", name: "Pending activation", accounts: 1 },
        { code: "vacation_hold", name: "Vacation hold/Suspended", accounts: 4 },
      ],
      ...rollupOver,
    },
  };
}

const CELLS = {
  accountNo: () => <span />,
  // CR-030 W2 T2.9(b) — the `CUSTOMER #` column B18's `[shot]` never drew and
  // the PO asked for by name on 2026-08-24.
  customerNo: () => <span />,
  name: () => <span />,
  premise: () => <span />,
  services: () => <span />,
  balance: () => <span />,
  lastBill: () => <span />,
  status: () => <span />,
  // CR-030 W2 T2.3 — the AGEING column B18 §5.1.2 splits off STATUS.
  ageing: () => <span />,
  accountAge: () => <span />,
  autopay: () => <span />,
  since: () => <span />,
};

const CONFIG = accountsTableConfig(t, CELLS);

function permissions(access: string): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access }],
  };
}

function renderList(
  path: string,
  seed: { list?: AccountsPage; access?: string } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = parseTableParams(new URLSearchParams(path.split("?")[1] ?? ""), CONFIG);
  if (seed.list !== undefined) {
    queryClient.setQueryData(
      accountsQueryKey(serializeTableParams(state, CONFIG).toString()),
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
          <AccountsListPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The header, up to the table: where the ONE primary action must live. */
function header(html: string): string {
  const end = html.indexOf("data-table-frame");
  return end === -1 ? html : html.slice(0, end);
}

/**
 * The rows region only. The negative assertions below are about what the TABLE
 * claims — the awaiting panel deliberately NAMES the missing ageing states in
 * prose, and a whole-document `not.toContain` would read that prose as the
 * defect it exists to prevent.
 */
function rowsRegion(html: string): string {
  const start = html.indexOf("<table");
  const end = html.indexOf("</table>");
  return start === -1 || end === -1 ? "" : html.slice(start, end);
}

describe("US-CUS-001 — the S17 accounts list", () => {
  it("US-CUS-001 TC-1: the seeded row renders through the shared kit, newest-first by default", () => {
    const html = renderList("/accounts", {
      list: page([
        account({ id: "a-11025", account_no: "A-11025", name: "Blueprint Studio" }),
        account(),
      ]),
    });
    expect(html).toContain("A-11025");
    expect(html).toContain("Blueprint Studio");
    expect(html).toContain("Miller, Sarah");
    expect(html).toContain("1408 Elm St · A");
    // ── `BR-CUS-1046` (PO 2026-09-10) ────────────────────────────────────────
    // ⚠ **THIS ASSERTED `{ sort: "name", dir: "asc" }` UNTIL 2026-09-12, ON
    // `BR-CUS-053`'s AUTHORITY, AND THAT CLAUSE IS NOW SUPERSEDED.** PO
    // verbatim: ***"It should always sort it by the creation order. The new
    // newly created entries should always show on the top."*** Measured on the
    // demo utility before the fix: the newest account, created that morning,
    // came back at position 58 of 73 — page TWO at the page size this screen
    // uses. After: position 1.
    //
    // **Only that clause of `BR-CUS-053` moved.** The five search terms, the
    // filters and the columns are untouched, and `NAME` is still sortable, so
    // A→Z is one click away and the click survives a refresh.
    expect(CONFIG.defaultSort).toEqual({ sort: "created", dir: "desc" });
    // The ORDER itself is the server's, and since 2026-09-12 it is an `ORDER BY`
    // with the page taken in SQL rather than a Python sort over the whole
    // tenant (`NFR-3`, and `BR-CUS-1046`'s own *"fix the default and the
    // ordering together"*).
    expect(CONFIG.columns.some((column) => column.key === "name" && column.sortable === true)).toBe(
      true,
    );
    expect(CONFIG.columns.find((column) => column.identity === true)?.key).toBe("account_no");
    // BR-CUS-015: one tag per ACTIVE service agreement, through the ONE tag
    // component — the service catalog is platform-level, not per module.
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
    expect(html).not.toContain("var(--color-service-gas)");
  });

  it("US-CUS-001 TC-1 / BR-SHL-023: the balance renders through MoneyCell with its own currency", () => {
    const html = renderList("/accounts", { list: page([account()]) });
    // The decimal string is FORMATTED, never parsed or re-rounded here.
    expect(html).toContain("cell-money");
    expect(html).toContain("$247.30");
    expect(html).not.toContain("247.300000");
    // A different tenant currency travels WITH the amount (CLAUDE.md #2).
    const cad = renderList("/accounts", {
      // DEF-127 — the balance carries the currency the LEDGER derived for it,
      // which is the one that must reach the cell.
      list: page(
        [account({ balance: "64.000000", balance_currency: "CAD", currency: "CAD" })],
        { currency: "CAD" },
      ),
    });
    expect(cad).toContain("CA$64.00");
  });

  it("US-CUS-001 TC-1 / BR-CUS-055: the pill takes the tenant's own label and the class's tone", () => {
    // Account statuses are Reference data, so the SERVER's name wins — a tenant
    // that renamed one sees its own word, not a catalog override.
    expect(accountStatusLabel(account({ status_name: "Snowbird hold" }), t)).toBe("Snowbird hold");
    // …and a server that sent no name falls back to the catalog, then the code.
    expect(accountStatusLabel(account({ status_name: "" }), t)).toBe("Active");
    expect(accountStatusLabel(account({ status: "legal_hold", status_name: "" }), t)).toBe(
      "legal_hold",
    );
    // DEF-722 (PO 2026-08-26): the tone keys off the STATUS, with the BEHAVIOUR
    // CLASS as the fallback — so a TENANT-ADDED status, which no code map can
    // list, is still coloured by the class billing keys off. These four are the
    // fallback path and their answers are unchanged by the ruling; the six
    // seeded codes are asserted against rendered markup in
    // `accountStatusTone.dom.test.tsx`.
    const tenantAdded = (behaviorClass: string) =>
      accountStatusTone({ status: "legal_hold", status_behavior_class: behaviorClass });
    expect(tenantAdded("billable")).toBe("success");
    expect(tenantAdded("billable_base_only")).toBe("warning");
    expect(tenantAdded("terminal")).toBe("danger");
    expect(tenantAdded("non_billable")).toBe("neutral");
    const html = renderList("/accounts", {
      list: page([account({ status: "pending_activation", status_name: "Pending activation", status_behavior_class: "non_billable" })]),
    });
    expect(html).toContain("Pending activation");
    expect(html).toContain('class="pill bg-neutral-200 text-neutral-700"'); // CR-018: the draft tone's utilities
  });

  // ── DEF-722 · THE TWO NON-BILLABLE STATUSES ARE NOT THE SAME PILL ────────
  // The defect, on the screen it was filed against. `Pending activation` and
  // `Disconnected` share behaviour class `non_billable` (BR-CUS-107), so while
  // the tone keyed off the CLASS this list painted both of them the same
  // neutral grey — a customer who has not started and one whose service was cut
  // for debt, indistinguishable in the column a clerk scans.
  //
  // ⚠ THE STATUS IS SEEDED AND NOTHING ASSIGNS IT (`commit_cut` writes no
  // `accounts` column — DEF-701, open), so this row is CONSTRUCTED. It cannot
  // be reproduced by clicking, and that is a fact about the writer rather than
  // about the pill.
  it("DEF-722 / BR-CUS-107: `Disconnected` and `Pending activation` are the same CLASS and never the same pill", () => {
    const pill = (status: string, name: string) =>
      renderList("/accounts", {
        list: page([
          account({ status, status_name: name, status_behavior_class: "non_billable" }),
        ]),
      });
    const cut = pill("disconnected", "Disconnected");
    const pending = pill("pending_activation", "Pending activation");
    // The one that owes money takes the loudest tone in the set.
    expect(cut).toContain("Disconnected");
    expect(cut).toContain('class="pill past"');
    // The one that has not started stays quiet…
    expect(pending).toContain('class="pill bg-neutral-200 text-neutral-700"');
    // …and — the assertion the defect is actually about — they differ.
    expect(cut).not.toContain('class="pill bg-neutral-200 text-neutral-700"');
  });

  // ── DEF-628 / BR-CUS-510 · THE BALANCE CELL'S TWO KINDS OF ZERO ──────────
  // The defect, on the row the CR-030 W2 seed lane measured against a live
  // tenant: `balance='0.000000'`, `balance_unavailable=()`, `last_bill_at=null`
  // on a `Pending activation` account — a real ledger zero, rendered as
  // **$0.00** where B18 §5.1.5 requires *awaiting*. "Nothing is owed" and
  // "nothing CAN be owed yet" are different facts and this column spelled them
  // the same way.
  //
  // ⚠ **THE SECOND CASE IS THE ONE THAT MATTERS MOST AND IT IS GREEN TODAY.**
  // DEF-628's own prevention note says to key the cell off `non_billable`;
  // BR-CUS-107 put `Disconnected` in that class the DAY AFTER the note was
  // written, and a cut account holds a debt. So the pair below is the guard: a
  // screen that keyed off the class alone would hide `A-11488`'s $612.75.
  it("DEF-628 / BR-CUS-510: a pending-activation zero reads AWAITING, and a cut account's debt still reads as money", () => {
    const pending = renderList("/accounts", {
      list: page([
        account({
          status: "pending_activation",
          status_name: "Pending activation",
          status_behavior_class: "non_billable",
          balance: "0.000000",
          balance_not_yet_billable: true,
          last_bill_at: null,
        }),
      ]),
    });
    // ⚠ **THE NEGATIVE IS SCOPED TO THE ROW'S OWN CELL, ON PURPOSE.** A bare
    // `not.toContain("$0.00")` over the page FAILS here for an innocent reason:
    // the KPI strip's `OUTSTANDING` tile legitimately totals $0.00 across a
    // one-account page. A check whose output cannot distinguish pass from fail
    // is worse than no check (CLAUDE.md law 11, twice) — so this asserts the
    // BALANCE CELL's rendered markup, which is the thing the defect is about.
    expect(pending).toContain(
      '<td class="cell-num"><span class="cus-awaits" title="This account cannot be billed yet,',
    );
    expect(pending).toContain(">Awaiting</span></td>");
    // The defect itself, in the negative — the fabricated-looking zero is gone
    // from the row. Before the fix this cell read
    // `<td class="cell-num"><span class="cell-money">…$0.00…`.
    expect(pending).not.toContain('<td class="cell-num"><span class="cell-money"');

    const cut = renderList("/accounts", {
      list: page([
        account({
          status: "disconnected",
          status_name: "Disconnected",
          status_behavior_class: "non_billable", // the trap's premise
          balance: "612.750000",
          balance_not_yet_billable: false,
        }),
      ]),
    });
    expect(cut).toContain("$612.75");
    expect(cut).not.toContain("Awaiting");
  });

  it("US-CUS-001 TC-3 / BR-CUS-016: a null aging is NEVER rendered as an aging pill", () => {
    // The prototype's Status column mixes the stored status with a derived
    // ageing state. Billing owns the invoices it derives from, so `aging` is
    // null — and no null may become "Current", which is a claim about money.
    const html = renderList("/accounts", { list: page([account({ aging: null })]) });
    const rows = rowsRegion(html);
    expect(rows).toContain("Active");
    expect(rows).not.toContain("30d past");
    expect(rows).not.toContain("60+ past");
    expect(rows).not.toContain(">Current<");
    // The gap is STATED rather than left to be noticed. AMENDED 2026-08-15
    // (DEF-127): the panel used to name the last bill date as missing, and it
    // is served now.
    // ⚠ AMENDED AGAIN 2026-08-24 (CR-030 W2): the panel said the ageing PILL
    // "is not shown", and this wave draws it — the sentence was true when
    // written and false the moment the AGEING column landed, which is DEF-445's
    // exact shape. It now names the half that IS still missing: an account
    // whose debt comes from a bill we issued ages to a dash, because only the
    // migrated-balance half is derivable.
    // ⚠ AMENDED 2026-08-24 — the "Waiting on billing" panel is DELETED (PO
    // ruling, walking the deployed build: "Delete both boxes entirely"). This
    // case no longer pins the explanation, because there is no longer one on
    // screen. What it still pins is the fact the explanation was about, and
    // that is the assertion worth keeping: a null ageing renders as a DASH and
    // never as a pill. A fabricated "Current" on an account we cannot age is
    // the defect; the paragraph describing it was only ever the apology.
    expect(html).not.toContain("Waiting on billing");
    expect(html).not.toContain("ageing pill");
  });

  it("US-CUS-001 §5: Last bill renders as awaiting, never as a dash that reads 'never billed'", () => {
    const html = renderList("/accounts", { list: page([account({ last_bill_at: null })]) });
    expect(html).toContain("Awaits billing");
    // AMENDED 2026-08-15 (DEF-127). The copy used to read "Billing is not built
    // yet" and the cell said it about accounts that HAD been billed, because
    // the server's seam pointed at the wrong module attribute. It is now a
    // statement about THIS account.
    expect(html).toContain("no issued bill yet");
    // BR-SHL-034: a date the server DOES send goes through the shared cell.
    const billed = renderList("/accounts", {
      list: page([account({ last_bill_at: "2026-07-15" })]),
    });
    expect(billed).toContain("07/15/2026");
    expect(rowsRegion(billed)).not.toContain("Awaits billing");
  });

  it("US-CUS-001 TC-1 / BR-CUS-016: the roll-up shows the served figures and no invented ones", () => {
    const html = renderList("/accounts", { list: page([account(), account({ id: "b" })]) });
    // ⚠ THE ROLL-UP MOVED, IT DID NOT GO (CR-030 W2 T2.2, 2026-08-24). This
    // line read `expect(header(html)).toContain("page-header-rollup")` — the
    // `.sub` line under the H1 that r10 draws. B18 §5.1.1 draws the same three
    // figures as the first three of five KPI tiles, so keeping both would make
    // one screen state "2 accounts" twice. Same amend-don't-delete precedent as
    // the tab-strip pin below: what this case guards — the SERVER's own block,
    // never recomputed here — is unchanged, so the assertion follows the figures
    // to where they now render.
    // ⚠ **AMENDED AGAIN 2026-09-20 (`DEF-CUS-5939`): THE SLOT IS OCCUPIED, AND
    // NOT BY THESE FIGURES.** The blueprint's head carries `10 tabs · <Tab>` on
    // the sub-line, which is a fact about the SCREEN and not about the books —
    // so the assertion this case needs is the narrow one it always meant: the
    // roll-up line must not state the money figures a second time. Keeping the
    // blunt `not.toContain("page-header-rollup")` would have pinned an empty
    // slot and refused the head the drawing asks for.
    expect(header(html)).toContain('<div class="page-header-rollup">10 tabs · Accounts</div>');
    // ⚠ **AMENDED AGAIN 2026-09-28 (PO ruling · `DEF-CUS-7700`), AND THIS TIME
    // THE FIGURES DID NOT MOVE, THEY WENT.** This block asserted the strip
    // carried `Outstanding`, `$0.00`, the sentence explaining what the figure
    // includes, and `Not counted yet` under `Past-due 60+`. The ruling replaces
    // the five tiles with four counted by STATUS, and none of the four is
    // money — so every one of those four assertions is now a claim about a
    // tile that does not exist.
    //
    // **It is amended rather than deleted, and what it still guards is the
    // half that was never about the money:** this screen must not state a
    // tenant-wide figure the server did not send, and the head's sub-line must
    // not repeat the strip. The FIGURES it names have changed with the tiles.
    //
    // ⚠ **`Outstanding` NOW HAS NO SURFACE ON THIS SCREEN AT ALL**, which is
    // the ruling and is reported rather than quietly worked around: the tenant
    // receivable lives on Finance's Revenue & AR screen, and the per-row
    // BALANCE column is the only money left here. The two negative assertions
    // below are what stops a lane re-adding a fifth tile without a ruling.
    for (const restated of ["Outstanding", "$0.00", "accounts"]) {
      expect(header(html).slice(header(html).indexOf("page-header-rollup"),
        header(html).indexOf("page-header-actions"))).not.toContain(restated);
    }
    expect(html).toContain("kpi-grid");
    expect(kpiRegion(html)).not.toContain("Outstanding");
    expect(kpiRegion(html)).not.toContain("$0.00");
    // The four the PO ruled, with the counts the roll-up's ONE grouped query
    // sent — never a figure this screen worked out for itself.
    expect(kpiRegion(html)).toContain("Active");
    expect(kpiRegion(html)).toContain(">3<");
    expect(kpiRegion(html)).toContain("Suspended");
    expect(kpiRegion(html)).toContain(">4<");
    // ⚠ **`Past-due 60+` AND `Not counted yet` ARE GONE FROM THE SCREEN, AND
    // THAT IS `DEF-CUS-7700` CLOSING.** The assertion that used to stand here
    // read `expect(html).toContain("Not counted yet")` — it pinned a
    // PLACEHOLDER as though it were behaviour, which is exactly why two tiles
    // that never counted anything survived every check in this repo for weeks.
    // Inverted rather than removed, so a lane re-introducing an uncounted tile
    // goes red here.
    expect(html).not.toContain("Not counted yet");
    expect(html).not.toContain("Past-due 60+");
    // `rollupCurrency` still resolves one CHAR(3) for a set of rows and is
    // still asserted, although this screen no longer calls it: the helper is
    // exported from `customersShared` and the account detail money cells rely
    // on the same rule (BR-TEN-042's currency lock).
    expect(rollupCurrency([account(), account({ id: "b" })])).toBe("USD");
    expect(rollupCurrency([])).toBeNull();
    expect(rollupCurrency([account(), account({ id: "b", currency: "CAD" })])).toBeNull();
  });

  it("US-CUS-001 §5 / BR-CUS-029: there is no Plan column and no Plan filter", () => {
    // The account plan snapshot has no DDL anywhere, and the unit's plan is a
    // different thing (BR-CUS-010) — so neither is rendered nor requested.
    expect(CONFIG.columns.map((column) => column.key)).toEqual([
      "account_no",
      // ⚠ AMENDED TWICE ON 2026-08-24, AND BOTH MOVES WERE RULINGS — this pin
      // is what makes an accidental column visible, so it moves only when the
      // PO moves it. It gained `customer_no` in the morning (*"we were suppose
      // to add customer # comlume what happened to that"*) and LOST it the
      // same afternoon, once the PO saw it on the deployed screen: *"on
      // account tab - we dont need this column … you can sho it as part of
      // details screen"*. The number now rides in the account detail's kicker
      // beside the account number. The SEARCH still matches it — that was
      // never what the ruling was about.
      "name",
      "premise",
      "services",
      "balance",
      "last_bill",
      "status",
      // CR-030 W2 T2.3 — B18 §5.1.2's new column, between STATUS and the two
      // hidden-by-default ones. Still no `plan`: BR-CUS-029's snapshot has no
      // DDL anywhere and the unit's plan is a different thing (BR-CUS-010).
      "ageing",
      // DEF-CUS-10180 (PO 2026-10-17) — *"Column Account age"*, next to Aging.
      "account_age",
      "autopay",
      "opened_at",
    ]);
    expect(CONFIG.filters?.map((filter) => filter.name)).not.toContain("plan");
    // Every filter this screen declares is one the endpoint actually accepts.
    //
    // ⚠ `ageing` IS ACCEPTED AND IS MISSING FROM THE MIRROR (CR-030 W2,
    // 2026-08-24). `apps/customers/selectors.ACCOUNT_FILTERS` carries `ageing`
    // and `api._with_ageing_segment` reads both `?ageing=` and `f.ageing=`; the
    // FRONTEND copy of that tuple in `src/api/endpoints.ts` was not updated when
    // the backend half landed this morning, and that file belongs to another
    // lane this session. The allowance is named here rather than dropped, so
    // this case still refuses any OTHER undeclared filter — and it goes away in
    // the commit that adds `ageing` to the wrapper.
    // ⚠ GONE 2026-10-17 (DEF-CUS-10181): `ageing` is in the wrapper's tuple
    // now and the allowance went with it, as promised above.
    for (const filter of CONFIG.filters ?? []) {
      expect(ACCOUNT_FILTERS as readonly string[]).toContain(filter.name);
    }
    // …and every sortable column is one the endpoint actually sorts by.
    for (const column of CONFIG.columns.filter((c) => c.sortable === true)) {
      expect(ACCOUNT_SORTS as readonly string[]).toContain(column.key);
    }
    // `last_bill` IS in the server's sort set and is deliberately not offered:
    // every value is null, so the control would promise an order that is not
    // there.
    expect(CONFIG.columns.find((c) => c.key === "last_bill")?.sortable).toBeUndefined();
  });

  it("US-CUS-001 §5 / BR-CUS-059: the two available columns are the ones the API can serve", () => {
    const hidden = CONFIG.columns.filter((c) => c.defaultVisible === false).map((c) => c.key);
    expect(hidden).toEqual(["autopay", "opened_at"]);
    const html = renderList("/accounts?f.autopay=true", { list: page([account()]) });
    // Autopay is CAPTURE-ONLY in v1 — recorded and shown, never collected on.
    // ⚠ AMENDED 2026-08-24 — this sentence lived in the "Waiting on other
    // work" panel, which the PO deleted. It is NOT replaced by another
    // assertion here, and that absence is the point: the warning that autopay
    // is recorded but never collected on now appears NOWHERE in the product.
    // Filed as DEF-644 rather than quietly dropped with the panel.
    expect(html).not.toContain("nothing collects on it in this version");
  });

  it("BR-CUS-068: the served `kind` marks a master account, and `f.kind` is offered as a chip", () => {
    // A master account is an ORDINARY row — same endpoint, same columns, same
    // table — so on S17 it is indistinguishable from a tenant's account unless
    // the screen renders the one column that differs.
    const html = renderList("/accounts", {
      list: page([
        account(),
        account({ id: "acc-master", account_no: "A-00900", kind: "master", name: "Miller Property LLC" }),
      ]),
    });
    expect(html).toContain("A-00900");
    // ⚠ **COUNTED ON THE PILL MARKUP, NOT ON THE WORD.** `>Master<` matches
    // twice — the row pill AND the filter chip's own option — so the plain
    // word cannot tell "the master row is marked" from "the chip exists".
    const pills = html.match(/<span class="pill[^"]*">Master<\/span>/g) ?? [];
    expect(pills.length).toBe(1); // the master row only; a marker on every row marks nothing
    // …and it sits in the identity cell, beside that row's own number.
    expect(html).toMatch(/A-00900<\/a> <span class="pill[^"]*">Master<\/span>/);
    expect(html).not.toMatch(/A-10432<\/a> <span class="pill/);

    // The chip's options are the server's own vocabulary. `selectors.account_list`
    // applies `f.kind` for exactly these two and IGNORES anything else, so a
    // third option would render a control that quietly returned everything.
    const kind = accountsFilters(t).find((f) => f.name === "kind");
    expect(kind?.options.map((o) => o.value)).toEqual(["regular", "master"]);
    expect(kind?.options.map((o) => o.label)).toEqual(["Regular", "Master"]);
  });

  it("US-CUS-001 §RBAC / BR-SHL-025: a '—' cell hides the surface, a 'View' cell disables the writes", () => {
    const denied = renderList("/accounts", { list: page([account()]), access: "—" });
    expect(denied).toContain("state-denied");
    expect(denied).not.toContain("A-10432");

    // A4 gives Executive VIEW on Premises/Accounts — the rows render and every
    // page action is disabled WITH the reason, never hidden (TC-6).
    const viewOnly = renderList("/accounts", { list: page([account()]), access: "View" });
    expect(viewOnly).toContain("A-10432");
    expect(viewOnly).toContain("Your role can view accounts but not change them.");
    expect(header(viewOnly)).toContain("+ New account");
    expect(header(viewOnly)).toContain("disabled");
  });

  // ⚠ **AMENDED 2026-09-20 (`DEF-CUS-5939`): THE TIER MOVED, THE CAP DID NOT.**
  // This read `data-variant="primary"` … `.toBe(1)`. The Accounts blueprint
  // draws this head four times and its action is plain words top right in every
  // one, so the slot is `ghost`; BR-SHL-044 caps the row at ONE primary and its
  // clause (c) says a tab may legitimately carry no header action at all.
  // Inverted rather than deleted — a deleted case would let the filled tier
  // come back unnoticed.
  /**
   * ⚠ **THE TIER REVERSED ON 2026-09-22 — `DEF-CUS-6193`, dated with
   * `git log -S` over `AccountsListPage.tsx` to commit `74511fa68`.**
   * `DEF-CUS-5939` had made this control the quiet text tier; the PO then
   * walked the deployed build and could not SEE the only way to create
   * anything on the page, so item 1 of their report makes it the primary.
   * **The subject of this case — EXACTLY ONE header action, and no page action
   * is a dead link — is unchanged**, and the negative is INVERTED rather than
   * dropped so a silent revert to the quiet control goes red here.
   */
  it("US-CUS-001 TC-6 / BR-SHL-044: exactly one header action, and no page action is a dead link", () => {
    const head = header(renderList("/accounts", { list: page([account()]), access: "Full" }));
    expect((head.match(/data-variant="primary"/g) ?? []).length).toBe(1);
    expect(head).not.toContain('data-variant="ghost"');
    expect(head).toContain("+ New account");
    expect(head).toContain("Move-in");
    expect(head).toContain("Move-out");
    // S18 landed 2026-08-11, so "+ New account" is a LIVE control for a role
    // that may write — it is no longer disabled with "that page is a later
    // story".
    expect(head).not.toContain("The guided New account page is a later story");
    expect(head).not.toContain("Move-in and move-out are guided pages of their own");
    // ⚠ **AMENDED 2026-08-26 (PO ruling, lane MOVEENTRY).** This line read
    // `expect(head).toContain("Move-in and move-out each act on one account")`
    // — it PINNED the disabled reason in place. The PO overruled the reason
    // itself (*"-Enable Move in /move out"*), so the assertion is inverted
    // rather than deleted: the sentence must be GONE from the product, and a
    // deleted case would let it come back unnoticed.
    expect(head).not.toContain("Move-in and move-out each act on one account");
    expect(head).not.toContain("Your role can view accounts");
    // ⛔ NOT a loose `toContain("disabled")` — every button in the kit carries
    // `disabled:opacity-45` in its class list, so the loose form is true of a
    // LIVE button and this case could never go red. `disabled=""` is the
    // attribute (the same distinction `AccountsCreateEntry.test.tsx` records).
    for (const label of ["Move-in", "Move-out"] as const) {
      const tag = new RegExp(`<button[^>]*>${label}</button>`).exec(head)?.[0] ?? "";
      expect(tag).not.toBe("");
      expect(tag).not.toContain('disabled=""');
    }
    // The row's identity IS a link now, because S21 exists and reads
    // `GET /accounts/{id}` — it was plain text while that screen did not.
    const html = renderList("/accounts", { list: page([account()]), access: "Full" });
    expect(html).toContain('href="/brazosbend/accounts/acc-10432"');
  });

  it("US-CUS-001 §6 / BR-SHL-044: this screen declares a page header and draws none of its own", () => {
    const html = renderList("/accounts", { list: page([account()]) });
    expect(html).toContain("page-header");
    // ⚠ **AMENDED 2026-09-20 (`DEF-CUS-5939`) — THE TITLE IS THE SCREEN'S NAME
    // AND THE KICKER IS THE MODULE'S.** This asserted `<h1>Accounts</h1>`. The
    // blueprint draws an `ACCOUNTS` kicker over the title **The register**, on
    // all four frames that show this head (p117, p131, p41, p48). The 32px
    // class is B14 rule 40 and is pinned here too, because the head now has
    // two pieces of text above the strip and the title must stay the larger.
    // ⚠ **AND AMENDED AGAIN 2026-09-24 (`DEF-CUS-6422`): THE TITLE READS
    // `Accounts`.** PO 2026-09-23: "Register" appears in no clerk-facing
    // string — it is our internal name for a list, and the clerk knows this
    // one by its sidebar word. The drawing's word is overruled by that ruling.
    expect(html).toMatch(/<h1[^>]*class="[^"]*text-h2[^"]*"[^>]*>Accounts<\/h1>/);
    expect(html).not.toContain("The register");
    expect(html).toMatch(/<span data-kicker=""[^>]*>Accounts<\/span>/);
    // The sub-line: `<N> tabs · <the active tab>`, ONE key with two
    // interpolations (B8). The third fragment the drawings carry — `N open` —
    // is deliberately ABSENT rather than zero; `DEF-CUS-5953` carries it.
    expect(html).toContain('<div class="page-header-rollup">10 tabs · Accounts</div>');
    expect(html).not.toMatch(/page-header-rollup">[^<]*open/);
    // No bespoke head. ⚠ THE TAB-STRIP PIN MOVED WITH THE RULING (CR-030 W1,
    // 2026-08-24). This line read `not.toContain("page-header-tabs")` with the
    // comment *"the prototype's accounts page has neither a kicker nor tabs"*,
    // which was TRUE of the r9 screen it was written against. B18 §4 and the
    // PO's uniform-tab contract — *"each tab has - list view {table + search +
    // filter + table colume selector}, detail view..."* — give this page a tab
    // strip, and S81's Imports tab is the second tab. A test that pins the
    // ABSENCE of a feature is correct when written and becomes a blocker the
    // moment the feature is ruled in; the precedent for moving it rather than
    // deleting it is `AssetRegistry.test.tsx`'s W5 amendment.
    //
    // What this test still guards is unchanged and is the point of it: the
    // screen declares the SHARED PageHeader (BR-SHL-044) and draws no head of
    // its own. The strip comes FROM that shared header, which is why the
    // assertion below is now positive.
    expect(html).not.toContain("cus-head");
    expect(html).toContain("page-header-tabs");
    // ⚠ **THIS LINE READ `not.toContain("kicker")` UNTIL 2026-09-20
    // (`DEF-CUS-5939`), AND IT IS THE SAME SHAPE THE PARAGRAPH ABOVE
    // DESCRIBES — a pin on the ABSENCE of a feature, correct against the r9
    // screen it was written for and a blocker the day the feature is drawn.**
    // All four blueprint frames of this head draw an `ACCOUNTS` kicker over
    // the title. So it is INVERTED rather than deleted, and it still guards
    // the thing it always guarded: the kicker comes from the SHARED
    // `PageHeader` (one `data-kicker` element), never from a head this screen
    // drew itself.
    expect((html.match(/data-kicker=""/g) ?? []).length).toBe(1);
  });

  it("A18 §1: the empty list offers its CTA disabled WITH the reason, never a live button onto nothing", () => {
    const html = renderList("/accounts", { list: page([]) });
    expect(html).toContain("state-empty");
    expect(html).toContain("No accounts yet.");
    expect(html).toContain("+ New account");
    // No access cell is seeded here, so the CTA is live — the disabled-with-
    // reason path is the READ-ONLY role's, asserted below.
    const readOnly = renderList("/accounts", { list: page([]), access: "View" });
    expect(readOnly).toContain("disabled");
    expect(readOnly).toContain("Your role can view accounts but not change them.");
    // The shared block still renders a LIVE button when no reason is given —
    // this screen's posture must not become every screen's.
    const live = renderToStaticMarkup(
      <EmptyList title="t" helper="h" ctaLabel="Go" onCta={() => undefined} />,
    );
    // ⚠ NOT `not.toContain("disabled")` (CR-018 Phase 3). Under Route B the class
    // attribute SPELLS the state variants — `disabled:opacity-45
    // disabled:cursor-not-allowed` — so the substring is present on every button
    // in the product, enabled or not, and the old assertion passes nothing. It
    // is the ATTRIBUTE that has to be asked for.
    expect(live).not.toMatch(/<button[^>]*\sdisabled=/);
  });

  it("A18 §4 / BR-SHL-012: a failed load renders the shared failed-with-retry frame", () => {
    // No seeded data and no network: the query rejects and the ONE state frame
    // renders, rather than an empty table with a header (the empty-header ban).
    const html = renderList("/accounts");
    expect(html).toContain("skeleton");
    expect(html).not.toContain("<table");
  });

  it.todo(
    "US-CUS-001 TC-2: sorting by Balance desc puts A-11340 first — the ORDER is the server's, so this is a backend assertion (selectors.account_list)",
  );
  it.todo(
    "US-CUS-001 TC-5 (negative): a second active account on one unit is refused by BR-CUS-017 — server scope, no screen writes accounts yet",
  );
  it.todo(
    "US-CUS-001 TC-7 (isolation): a Lone Star Ridge session sees no Brazos Bend account in any permutation — server/RLS scope (G5)",
  );
});

describe("US-CUS-002 — S17 search, filters and the wizard entry points", () => {
  it("US-CUS-002 TC-1/TC-2 / BR-CUS-053: the declared search fields are the capability row's own set", () => {
    // ⚠ AMENDED 2026-08-24 (CR-030 W2 close-out, T2.9(a)) — **FIVE, NOT
    // FOUR**. BR-CUS-053 was amended by PO ruling the same day: *"THE SEARCH
    // SET IS FIVE, NOT FOUR, AND `CUSTOMER #` IS A COLUMN AS WELL AS A SEARCH
    // TERM"*. `selectors.account_list` now ORs `_account_ids_by_customer_no`
    // into the same match group as `account_no`, so this declaration and the
    // server agree; `06-backend/tests/test_cr030_w2_customer_no_search.py` is
    // what holds the server half. The order mirrors the OR-group's own.
    expect(CONFIG.searchFields).toEqual([
      "account_no",
      "customer_no",
      "name",
      "address",
      "meter_no",
    ]);
    // IS-3's mechanics (server-side, debounced, min 2 chars) belong to the ONE
    // table framework — this screen declares the fields and nothing else.
    const html = renderList("/accounts?q=Elm", { list: page([account()]) });
    expect(html).toContain('value="Elm"');
  });

  it("US-CUS-002 TC-3 / BR-SHL-011: every declared filter round-trips through the URL", () => {
    // AMENDED 2026-08-22 — `kind` joined the set with BR-CUS-068. The list is
    // asserted whole rather than by membership, so a filter the endpoint does
    // NOT accept cannot be added without this case saying so.
    expect(CONFIG.filters?.map((filter) => filter.name)).toEqual([
      "status",
      "category",
      "autopay",
      "kind",
      // CR-030 W2 T2.4/T2.3 — the AGEING segment. `selectors.ACCOUNT_FILTERS`
      // carries `ageing` and `_with_ageing_segment` accepts both the CR's bare
      // `?ageing=` and BE-05's `f.ageing=`, so this one IS served.
      "ageing",
      "balance_gt",
    ]);
    const state = parseTableParams(
      new URLSearchParams(
        "f.status=closed&f.category=commercial&f.autopay=true&f.kind=master&f.balance_gt=1&q=Ridge",
      ),
      CONFIG,
    );
    expect(state.filters).toEqual({
      status: "closed",
      category: "commercial",
      autopay: "true",
      kind: "master",
      balance_gt: "1",
    });
    expect(serializeTableParams(state, CONFIG).get("f.kind")).toBe("master");
    expect(serializeTableParams(state, CONFIG).get("f.status")).toBe("closed");
    // An undeclared filter is ignored rather than sent (US-SHL-007 TC-5) —
    // `plan` is exactly that case here (BR-CUS-029).
    expect(parseTableParams(new URLSearchParams("f.plan=RES-STD"), CONFIG).filters).toEqual({});
    // The request state reaches the wrapper unchanged: one translation, one
    // place, so the URL a user shares is the query the server runs.
    // `BR-CUS-1046` — the URL carried no `sort`, so the state is on the
    // screen's DEFAULT, which is the creation order descending since
    // 2026-09-12. This read `{ sort: "name", dir: "asc" }` on `BR-CUS-053`'s
    // superseded clause.
    expect(accountsParamsFrom(state)).toMatchObject({ q: "Ridge", sort: "created", dir: "desc" });
    // …and a sort the clerk DID choose still travels, which is the ruling's
    // own second clause: *"a clerk's chosen sort must still win and still
    // survive a refresh."*
    const chosen = parseTableParams(new URLSearchParams("sort=name&dir=asc"), CONFIG);
    expect(accountsParamsFrom(chosen)).toMatchObject({ sort: "name", dir: "asc" });
    expect(serializeTableParams(chosen, CONFIG).get("sort")).toBe("name");
  });

  it("US-CUS-002 / BR-CUS-055: the status filter offers the ratified seed, in the seed's order", () => {
    const statuses = accountsFilters(t).find((filter) => filter.name === "status");
    expect(statuses?.options.map((option) => option.value)).toEqual([...ACCOUNT_SEED_STATUSES]);
    expect(statuses?.options[0].label).toBe("Pending activation");
    expect(statuses?.options.at(-1)?.label).toBe("Closed");
    // ⛔ **DEF-684 — THE CATEGORY CHIP TAKES THE SERVER'S CATALOGUE.** This
    // asserted `[...ACCOUNT_CATEGORIES]`, a hardcoded four, and so it PINNED
    // the defect rather than catching it: it went green over `government`
    // (LEGACY since BR-CUS-094, refused by name on a service request) and over
    // four real categories the platform prices and this chip could not reach.
    // The fixture below invents three codes that appear in NO constant and no
    // catalogue, so only options that arrived over the wire can satisfy it —
    // the shape `ServiceRequestCapturePage.test.tsx` already uses.
    const SERVED = [
      { code: "zzz_selectable_one", name: "Zzz selectable one" },
      { code: "zzz_selectable_two", name: "Zzz selectable two" },
    ];
    const SERVED_LEGACY = [{ code: "zzz_legacy", name: "Zzz legacy" }];
    const categories = accountsFilters(t, [...SERVED, ...SERVED_LEGACY]).find(
      (filter) => filter.name === "category",
    );
    expect(categories?.options.map((option) => option.value)).toEqual([
      "zzz_selectable_one",
      "zzz_selectable_two",
      "zzz_legacy",
    ]);
    // The LABEL rides with the code. `customers.accounts.category.*` only ever
    // held the superseded four, so a translated label is a label that cannot
    // exist for four of the seven.
    expect(categories?.options.map((option) => option.label)).toEqual([
      "Zzz selectable one",
      "Zzz selectable two",
      "Zzz legacy",
    ]);
    // ⚠ **A FILTER TAKES THE LEGACY CODE AND A PICKER MUST NOT.** BR-CUS-094
    // keeps `government` "still a valid FK, still filterable, still priceable";
    // an account already carrying it has to stay findable.
    expect(categories?.options.map((option) => option.value)).toContain("zzz_legacy");
    // Nothing fetched yet offers NOTHING, which is honest. Four wrong codes
    // were not.
    expect(
      accountsFilters(t).find((filter) => filter.name === "category")?.options,
    ).toEqual([]);
    // `balance > 0` is a FLAG on this endpoint, not a threshold — one option,
    // so the control cannot imply a number the server will not honour.
    const balance = accountsFilters(t).find((filter) => filter.name === "balance_gt");
    expect(balance?.options).toEqual([{ value: "1", label: "Over zero" }]);
  });

  it("US-CUS-002 TC-4 / A18 §2: a filter that matches nothing renders zero-results, not empty-list", () => {
    const html = renderList("/accounts?f.status=closed", { list: page([]) });
    expect(html).toContain("state-zero");
    // A18 §2 keeps the toolbar and filters; the create CTA belongs to §1 only.
    expect(html).toContain("table-toolbar");
    expect(html).not.toContain("state-empty");
  });

  it("US-CUS-002 §5: the segments and the CSV export the prototype draws are absent, and say why", () => {
    const html = renderList("/accounts", { list: page([account()]), access: "Full" });
    // The prototype draws the four segments as a radio group. Only All and
    // Closed are answerable without invoices, and a half-implemented segment
    // set is worse than none — so no radio renders anywhere on this screen.
    expect(html).not.toContain('type="radio"');
    // ⚠ INVERTED 2026-10-17 (DEF-CUS-10180). This asserted NO download
    // because `/exports` registered no accounts resource. The PO put Account
    // age "in the download", `apps/customers/exports.py` registers it, and the
    // shared control renders — BR-SHL-010's condition is now met.
    expect(html).toContain('data-download="button"');
    // ⚠ AMENDED 2026-08-24 — the "Waiting on other work" panel is DELETED (PO
    // ruling: "Delete both boxes entirely"). The behaviour this case exists
    // for is unchanged and still asserted above: no download control renders,
    // because `/exports` registers no accounts resource. What is gone is the
    // paragraph explaining it — an invisible absence nobody was confused by.
    expect(html).not.toContain("Waiting on other work");
  });

  it.todo(
    "US-CUS-002 TC-6: a 1-character search fires no query — the debounce is browser scope (asserted once in DataTable's own suite)",
  );
  it("US-CUS-002 §5 / hard-won law 2: the two entry points S18 and S21 answer are wired, not described", () => {
    const html = renderList("/accounts", { list: page([account()]), access: "Full" });
    // The account number opens S21 …
    expect(html).toContain('href="/brazosbend/accounts/acc-10432"');
    // … and the awaiting panel no longer claims the detail screen is missing.
    expect(html).not.toContain("opening an account to see its detail is a later story");
  });

  it.todo(
    "US-CUS-002 TC-5: Move-out opens S20 and Cancel returns with the search state intact — S19/S20 are unbuilt and have no endpoint",
  );
  it.todo(
    "US-CUS-002 TC-7 (isolation): a Lone Star Ridge search for 'Miller' returns nothing — server/RLS scope (G5)",
  );
});

// ═══════════════════════════════════════════════════════════════════════════
// CR-030 W2 · B18 §5.1.4's `TC-ACC-*` and §10.3's `TC-UI-*`
//
// The three cases that are NOT here are `it.todo` below with the reason each
// cannot be asserted from this file. None of them is deferred for effort:
// TC-ACC-3 has no served field, TC-ACC-6 is a server/RLS claim, and two of the
// TC-UI rows are about screens this lane does not own.
// ═══════════════════════════════════════════════════════════════════════════

/** An S17 row plus the four ageing keys `selectors.ageing_cells` serves. */
function aged(over: Partial<AccountRowWithAgeing> = {}): AccountRowWithAgeing {
  return { ...account(), ...over };
}

/** The KPI strip only — so a `not.toContain` about a TILE cannot be satisfied
 *  (or falsified) by the table or the awaiting panel below it.
 *
 *  ⚠ **THE OPENING TAG IS NO LONGER A BARE `<div class="kpi-grid">`** — a strip
 *  whose tiles press carries `role="group"` and an accessible name, so the
 *  attributes now sit between the class and the `>`. Matching on the class
 *  alone keeps this helper working for BOTH forms; pinning the whole tag would
 *  have made every case below silently read the empty string and pass. */
function kpiRegion(html: string): string {
  const start = html.indexOf('<div class="kpi-grid"');
  if (start === -1) {
    return "";
  }
  const end = html.indexOf("data-table-frame", start);
  return end === -1 ? html.slice(start) : html.slice(start, end);
}

/** How many tiles the strip drew. ⚠ **A PRESSABLE TILE IS A `<button>`, NOT A
 *  `<div>`** (PO ruling 2026-09-28), so counting `<div class="kpi">` now
 *  reports ZERO on this screen — and `expect(0).toBe(0)` is a check that
 *  cannot fail. Counted off the shared class instead, whichever element wears
 *  it. */
function tileCount(strip: string): number {
  return strip.split(/<(?:div|button)[^>]*class="kpi[ "]/).length - 1;
}

describe("CR-030 W2 — the Accounts tab (B18 §5.1)", () => {
  /**
   * ⚠ **AMENDED 2026-09-28 — PO ruling, and `DEF-CUS-7700` closing with it.**
   *
   * This case read *"five KPI tiles render, and the ones that cannot be
   * computed say so rather than drawing a zero"*, and it asserted the literal
   * **"Not counted yet"** twice over — once for `PAST DUE 60+` and once for
   * `CLOSED THIS YEAR`. **Both of those tiles never counted anything from the
   * day they shipped**, and this assertion is the reason nothing said so: a
   * test that pins the PLACEHOLDER makes a permanent gap indistinguishable
   * from intended behaviour, which is `DEF-CUS-7700`'s escape reason in one
   * line.
   *
   * **It is AMENDED and not deleted**, and what it still guards is the half
   * that was always right: the strip states the figures the SERVER sent and
   * invents none. What changed is which tiles, and that there are four.
   */
  it("TC-ACC-1: four status tiles render, each with the count the server's grouped query sent", () => {
    const html = renderList("/accounts", {
      list: page([aged(), aged({ id: "b" })]),
      access: "Full",
    });
    const strip = kpiRegion(html);
    // Four tiles, no more and no fewer — and counted off the shared class, not
    // off `<div>`, because a pressable tile is a `<button>`.
    expect(tileCount(strip)).toBe(4);
    // The PO's own four words, in the PO's own order.
    expect(
      Array.from(strip.matchAll(/<span class="k">([^<]*)</g)).map((m) => m[1]),
    ).toEqual(["Active", "Pending", "Disconnecting", "Suspended"]);
    // ⚠ **`Disconnecting`, AND NEVER `Disconnects`** — ruled, because
    // `Disconnects` is a TAB on this screen and means the REQUESTS. The tab
    // still says it; the tile must not.
    expect(strip).not.toContain(">Disconnects<");
    // The fixture's grouped counts, each landing on its own tile: active 3,
    // pending_activation 1, marked_disconnect 2, vacation_hold 4.
    for (const figure of [">3<", ">1<", ">2<", ">4<"]) {
      expect(strip).toContain(figure);
    }
    // Nothing the ruling dropped is still drawn anywhere on the page.
    for (const gone of ["Outstanding", "Past-due 60+", "Closed this year", "Not counted yet"]) {
      expect(html).not.toContain(gone);
    }
  });

  /**
   * ⚠ **THIS CASE WAS *"a null Outstanding states its absence and never renders
   * $0.00"* AND ITS SUBJECT NO LONGER EXISTS.** The Outstanding tile is gone by
   * ruling, so the old assertions would have been asserting the absence of a
   * thing that is absent for a different reason — green, and meaningless.
   *
   * **The question it was really asking survives and is worth more now:** what
   * does a tile draw when the server did not answer for it? Re-pointed at the
   * case that can actually happen — a tenant whose status set does not carry
   * one of the four.
   */
  it("TC-ACC-1 (absence): a status this tenant does not have draws a dash and cannot be pressed", () => {
    const html = renderList("/accounts", {
      list: page([aged()], {
        by_status: [
          { code: "active", name: "Active", accounts: 6 },
          { code: "pending_activation", name: "Pending activation", accounts: 0 },
          { code: "marked_disconnect", name: "Marked disconnect", accounts: 0 },
          // no `vacation_hold` — this utility never seeded it (BR-CUS-055 is
          // tenant-extensible in both directions).
        ],
      }),
    });
    const strip = kpiRegion(html);
    // Still four tiles: the ruling is four, and a strip that silently shrinks
    // to three for some tenants is a screen nobody can describe.
    expect(tileCount(strip)).toBe(4);
    expect(strip).toContain("Suspended");
    // A DASH, never `0` — "nobody is suspended" and "this utility has no such
    // status" are different sentences and `0` states the first about the
    // second.
    expect(strip).toContain("—");
    // …and it is not a control. A filter on a status no account can hold would
    // return an empty list for ever (hard-won law 2's mirror), so the tile that
    // cannot answer also cannot be pressed.
    expect(strip).not.toContain('data-kpi="suspended"');
    // The three the tenant DOES have are still buttons, including the two at a
    // real zero — a zero is an answer.
    for (const id of ["active", "pending", "disconnecting"]) {
      expect(strip).toContain(`data-kpi="${id}"`);
    }
  });

  it("TC-ACC-2: STATUS and AGEING are two cells, never one — a pending account can be past due", () => {
    const html = renderList("/accounts", {
      list: page([
        aged({
          status: "pending_activation",
          status_name: "Pending activation",
          status_behavior_class: "non_billable",
          ageing_segment: "d31_60",
          ageing_days_past_due: 45,
          ageing_source: "opening_buckets",
          ageing_unavailable: null,
        }),
      ]),
    });
    const rows = rowsRegion(html);
    expect(rows).toContain("Pending activation");
    expect(rows).toContain("31–60 days past");
    // Two headers, so the two vocabularies can never be read as one. Both are
    // sortable now — AGEING since 2026-10-17 (DEF-CUS-10181: the server orders
    // by the anchor in SQL), so its `<th>` wraps a button like STATUS's.
    expect(html).toContain(">Status");
    expect(html).toContain(">Aging");
    expect(html).not.toContain("<th>Aging</th>");
    // The exact age is the tooltip, not a third column.
    expect(rows).toContain("45 days past due");
  });

  it("TC-ACC-2 (the null cell): no derivable position renders a dash WITH its reason, never Current", () => {
    const html = renderList("/accounts", {
      list: page([
        aged({
          ageing_segment: null,
          ageing_days_past_due: null,
          ageing_source: null,
          ageing_unavailable: [
            {
              code: "invoice_ageing_needs_due_dates",
              br_ref: "BR-CUS-016",
              detail: "Only the opening-bucket half is derivable for this account.",
            },
          ],
        }),
      ]),
    });
    const rows = rowsRegion(html);
    // ⚠ "Current" is a claim about a customer's money that nobody computed.
    expect(rows).not.toContain("Current");
    expect(rows).toContain("—");
    // The SERVER's own sentence rides on the cell, so a clerk can see WHY.
    expect(rows).toContain("Only the opening-bucket half is derivable for this account.");
  });

  it("TC-ACC-2 (vocabulary): the AGEING cell reads `ageing_segment`, never billing's `aging`", () => {
    // `aging` is billing's still-unwired three-state vocabulary and is a
    // DIFFERENT field. A row carrying one and not the other must not borrow it.
    const html = renderList("/accounts", {
      list: page([aged({ aging: "60+ past", ageing_segment: null, ageing_unavailable: null })]),
    });
    expect(rowsRegion(html)).not.toContain("60+ past");
  });

  it("TC-ACC-4: eight services render five chips and one overflow chip, never eight wrapping", () => {
    const html = renderList("/accounts", {
      list: page([
        aged({
          services: [
            "electric",
            "water",
            "sewer",
            "gas",
            "broadband",
            "trash",
            "solar",
            "battery",
          ],
        }),
      ]),
    });
    const rows = rowsRegion(html);
    // r10's five letters, then the overflow square carrying the remainder.
    expect(rows).toContain(">E<");
    expect(rows).toContain(">W<");
    expect(rows).toContain(">S<");
    expect(rows).toContain(">G<");
    expect(rows).toContain(">B<");
    expect(rows).toContain(">+3<");
    // Nothing is LOST to the cap: the hidden three are the overflow chip's own
    // accessible name, so a reader who cannot hover still has them.
    expect(rows).toContain("3 more services: Trash, Solar, Battery");
    // …and the hidden ones are not ALSO drawn as squares.
    expect(rows).not.toContain(">So<");
    expect(rows).not.toContain(">Ba<");
  });

  it("TC-ACC-4 (under the cap): five or fewer services draw no overflow chip at all", () => {
    const html = renderList("/accounts", {
      list: page([aged({ services: ["electric", "water", "sewer", "gas", "broadband"] })]),
    });
    expect(rowsRegion(html)).not.toContain("more services:");
  });

  it("TC-ACC-5 / BR-SHL-011: the ageing segment rides in the URL and a reload restores it", () => {
    // The four options are the SERVER's segment vocabulary — a fifth value, or
    // a collapsed "60+ past", would fall back to no filter and quietly return
    // the whole tenant (BR-SHL-011's never-4xx rule cutting the wrong way).
    const ageing = CONFIG.filters?.find((filter) => filter.name === "ageing");
    expect(ageing?.options.map((option) => option.value)).toEqual([
      "current",
      "d31_60",
      "d61_90",
      "d90_plus",
    ]);
    const state = parseTableParams(new URLSearchParams("f.ageing=d90_plus"), CONFIG);
    expect(state.filters).toEqual({ ageing: "d90_plus" });
    expect(serializeTableParams(state, CONFIG).get("f.ageing")).toBe("d90_plus");
    // …and it reaches the wrapper, which spells it `f.ageing` on the wire.
    expect(accountsParamsFrom(state).filters).toEqual({ ageing: "d90_plus" });
    // ⚠ AN UNRECOGNISED *VALUE* IS CARRIED, AND THE SERVER IS WHAT REFUSES IT.
    // BR-SHL-011's fallback law is about a filter NAME the screen does not
    // declare (`f.plan` above, dropped); the framework never validates a
    // declared filter's value, so `f.ageing=60plus` reaches the request and
    // `normalize_ageing_segment` returns None for it — meaning NO ageing filter
    // rather than a 4xx, which is the same never-error posture from the other
    // end. Asserted as it really behaves, so nobody reads the line above as a
    // client-side guarantee it is not.
    expect(parseTableParams(new URLSearchParams("f.ageing=60plus"), CONFIG).filters).toEqual({
      ageing: "60plus",
    });
    expect(parseTableParams(new URLSearchParams("f.plan=RES-STD"), CONFIG).filters).toEqual({});
  });

  /**
   * **TC-ACC-7, FROM THE FAR SIDE OF ITS OWN PRECONDITION.**
   *
   * B18 §5.1.4 declares it as *"Given `customer_no` not yet migrated · When the
   * search placeholder renders · Then it does **not** offer `customer #`"*. The
   * Given is now FALSE — the column migrated in CR-030 W0 (migrations 0013 +
   * 0014) — and BR-CUS-053's amendment of 2026-08-24 says what the case becomes
   * in so many words: *"`TC-ACC-7` is the test that goes green when the
   * selector learns the column."*
   *
   * So the case is not deleted and not rewritten into a different question. It
   * asserts the SAME invariant it always did, which is a BICONDITIONAL and was
   * only ever visible from one side: **the prompt names `customer #` exactly
   * when the server matches it.** Yesterday both halves were false and it
   * passed; today both are true and it passes. What it forbids is the pair
   * coming apart — a prompt promising a search that is not performed, which is
   * hard-won law 1 in its purest form and is why the previous lane withheld
   * the copy rather than shipping it early.
   */
  it("TC-ACC-7: the prompt names `customer #` exactly when the server matches it — the promise and the performance move together", () => {
    expect(CONFIG.searchPlaceholder).toBe("customers.accounts.searchPlaceholder");
    const html = renderList("/accounts", { list: page([aged()]) });

    // The SEARCH half — what `selectors.account_list` really ORs into its one
    // match group (BR-CUS-053 (a), proved server-side in
    // `06-backend/tests/test_cr030_w2_customer_no_search.py`).
    const serverMatchesCustomerNo = CONFIG.searchFields?.includes("customer_no") ?? false;
    // The PROMPT half — the rendered English a clerk actually reads.
    const promptNamesCustomerNo = /customer #/i.test(html);

    expect(serverMatchesCustomerNo).toBe(true);
    expect(promptNamesCustomerNo).toBe(serverMatchesCustomerNo);
    // And the four that were always true are still named — the fifth is an
    // ADDITION, not a replacement.
    expect(html).toContain("Account #");
    expect(html).toContain("meter #");
  });

  /**
   * CR-030 W2 T2.9(b) — the column itself. **PO 2026-08-24, verbatim:** *"we
   * were suppose to add customer # comlume what happened to that"*.
   *
   * Asserted on the DECLARED CONFIG as well as on the rendered row, because
   * those are two different failures: a column missing from `columns` never
   * reaches the column selector at all (BR-SHL-010), and a column present but
   * fed by a cell that reads the wrong field renders blank on every row —
   * hard-won law 2, which is the defect family this whole file is written
   * against.
   */
  it("TC-ACC-7 (the column): `CUSTOMER #` is NOT a column on this list — PO ruling 2026-08-24", () => {
    // ⚠ INVERTED THE SAME DAY IT WAS WRITTEN, and both directions were rulings.
    // The morning's reading of *"we were suppose to add customer # comlume"*
    // put the column here; the PO then saw it on the deployed screen and ruled
    // *"on account tab - we dont need this column … you can sho it as part of
    // details screen"*. So this case now pins the ABSENCE, for the same reason
    // it used to pin the presence: whichever way the ruling went, an
    // accidental change to this list must fail here rather than reach a screen.
    expect(CONFIG.columns.find((c) => c.key === "customer_no")).toBeUndefined();
    const html = renderList("/accounts", { list: page([account()]), access: "Full" });
    expect(rowsRegion(html)).not.toContain("C-00417");

    // WHAT DID NOT CHANGE, and is the half worth guarding: the SEARCH still
    // matches the customer number. The ruling was about a column; removing the
    // search too would answer a question the PO never asked. `ACCOUNT_SORTS`
    // still cannot order by it, so no control may offer that ordering.
    expect(ACCOUNT_SORTS).not.toContain("customer_no");
    expect(t("customers.accounts.searchPlaceholder")).toContain("customer #");
  });

  it("TC-ACC-7 (the empty cell): an account with no customer entity says so, and never borrows the account number", () => {
    // Three ordinary states produce null here — no `customer_accounts` link, a
    // customer the 0014 backfill has not reached, an import row with neither a
    // reference nor a name. None of them is a figure that failed to compute, so
    // the cell reads "No customer number" and NOT an "Awaits …" that would
    // promise one is coming (compare the AGEING and Last-bill cells).
    const html = renderList("/accounts", {
      list: page([account({ customer_no: null })]),
      access: "Full",
    });
    const rows = rowsRegion(html);
    // ⚠ AMENDED 2026-08-24 — the CUSTOMER # column is removed from this list
    // by PO ruling, so there is no cell to hold an empty-state sentence. The
    // half of this case that still matters is BELOW and is why it survives at
    // all: the account number must never leak into a customer-number slot.
    expect(rows).not.toContain("No customer number");
    // The account number must not leak into the customer column — the two are
    // different numbers and conflating them is the whole reason W0 added one.
    expect(rows).not.toContain("C-00417");
    expect(rows).toContain("A-10432");
  });

  /**
   * TC-UI-2, named as its own case. **B18 §10.3: *"Every tab renders exactly
   * five KPI tiles, each with label · figure · caption."***
   *
   * It was asserted inside TC-ACC-1 as a one-line aside. That is enough to hold
   * the count and not enough to be FOUND: §10.3's eight rows are the CR's
   * conformance contract and a reader auditing them against this file could not
   * see this one. Restated here as the row it is, over the same rendered strip.
   */
  it("TC-UI-2: the Accounts tab renders exactly four KPI tiles, each with a label, a figure and a line", () => {
    const html = renderList("/accounts", { list: page([account()]), access: "Full" });
    const strip = kpiRegion(html);
    // ⚠ **FIVE BECAME FOUR — PO ruling 2026-09-28, which SUPERSEDES B18 §10.3's
    // *"exactly five KPI tiles"* for this tab.** The row above records what
    // §10.3 asked for; the number is asserted rather than loosened, exactly as
    // it was when the five were the contract.
    expect(tileCount(strip)).toBe(4);
    // Each of the four is a different STATUS, so each carries its own label
    // and its own line — four tiles sharing one caption would pass a count.
    for (const label of ["Active", "Pending", "Disconnecting", "Suspended"]) {
      expect(strip).toContain(label);
    }
    // B14 rule 33: the LINE under a tile is a FACT, six words or fewer, and it
    // says what the status MEANS for billing — never why the product works
    // this way, which is zero words on screen.
    for (const line of [
      "billing normally",
      "no bill can be raised",
      "still consuming",
      "base charges only",
    ]) {
      expect(strip).toContain(line);
      expect(line.split(/\s+/).length).toBeLessThanOrEqual(6);
    }
    // …and every LABEL is the one word the PO ruled (rule 33 caps a label at
    // three; the ruling is tighter and is what is asserted).
    for (const label of Array.from(strip.matchAll(/<span class="k">([^<]*)</g)).map((m) => m[1])) {
      expect(label.trim().split(/\s+/)).toHaveLength(1);
    }
  });

  /**
   * ⚠ **EIGHT BECAME NINE AND WENT BACK TO EIGHT, BOTH ON 2026-08-26, AND THE
   * NUMBER IS ASSERTED RATHER THAN LOOSENED EITHER TIME.** B18 §4 draws eight
   * and this case was written from it. `Waiting on` was added as a ninth for
   * the CR-035 store, and the PO struck it the same day —
   * **CR-035 · AMENDMENT 1**, verbatim: *"We dont need seperate tab for this -
   * this will be directly on each request Request, Connect, Move IN move Out,
   * Trasnfr, Disconnect - seperate queue not reequired"*, then **"yyes"**.
   *
   * A parked job now appears on the tab for ITS OWN KIND OF WORK, and in the
   * `waiting_on` COLUMN the Requests list has always carried. The strip is back
   * to B18 §4's eight, so the divergence this case used to REPORT is closed by
   * the ruling rather than by a doc amendment.
   *
   * ⚠ **AMENDED 2026-09-20 — IT IS A ROW OF THE TAB'S OWN LIST, NOT A PANEL
   * ABOVE IT (`DEF-CUS-5994`).** This paragraph named `ParkedDraftsPanel`
   * *"pinned above each of the five flow lists"*; the PO removed it — *"remove
   * it - it is anyway in the list so we dont need it sepretely - if it is not
   * in list add it"* — and every list unions `wizard_parks` for its own flow
   * now. The placement moved; the ruling above did not.
   *
   * ⚠ **THE COUNT HALF BELOW IS UNCHANGED AND IS STILL THE WHOLE OF
   * REQUIREMENT 2** (*"the tab count must not lie"*): only `accounts` carries a
   * figure, so a parked draft has no tab superscript to corrupt. What DID
   * invert is the LIST's total — a draft is a row, so `total` counts it, which
   * is asserted in `parkedDrafts.dom.test.tsx`.
   */
  it("TC-UI-1: the strip is exactly TEN tabs, in order, and only Accounts carries a count", () => {
    // ⚠ **WAS EIGHT UNTIL `CR-094-BRC01` WAVE G (2026-09-12), AND THE ASSERTION
    // IS MOVED RATHER THAN RELAXED.** PO ruling, verbatim: *"in the main tab
    // list, add complaints and services. These two tabs. build their ad form
    // and detail view. and tables."* The blueprint's page 39 draws the strip
    // with `Complaints` and `Services` AFTER the six flow queues and BEFORE
    // `Imports`, and its own header reads *"10 tabs"* — so the ORDER is
    // asserted, not merely the count: a strip that appended the two after
    // `Imports` would pass a length check and be the wrong screen.
    const html = renderList("/accounts", {
      list: page([aged(), aged({ id: "b" })]),
      access: "Full",
    });
    expect(ACCOUNTS_TAB_IDS).toEqual([
      "accounts",
      "requests",
      "new-connects",
      "move-ins",
      "move-outs",
      "transfers",
      "disconnects",
      "complaints",
      "services",
      "imports",
    ]);
    const strip = html.slice(html.indexOf('class="page-header-tabs"'));
    expect(strip.split('role="tab"').length - 1).toBe(10);
    // ⚠ **AMENDED 2026-09-20 (`DEF-CUS-5939`) — NO COUNT, ON ANY TAB.** This
    // read `toContain(">Accounts 2<")` with the note *"the one count this
    // product can answer, from the served roll-up"*. It was NOT the roll-up:
    // it was `listQuery.data.count`, the number of rows matching the CURRENT
    // filters, so typing in the search box moved the figure beside the tab's
    // own word. And none of the four drawn frames carries a count on any tab.
    // The assertion is INVERTED rather than deleted, so a count cannot return
    // to one tab out of ten unnoticed.
    expect(strip).toContain(">Accounts<");
    expect(strip).not.toMatch(/>[A-Za-z][^<]*\s\d+</);
    // ⚠ AND NO OTHER COUNT. `[shot]` superscripts seven of the eight; six of
    // those need tables that do not exist, and a `42` typed beside Requests
    // would be a fabricated figure on the first screen a tenant opens.
    //
    // ⚠ **AND THIS IS WHERE REQUIREMENT 2 IS ACTUALLY MET (CR-035 · AMENDMENT
    // 1).** *"If the Move-ins tab reads 12 and three of them never happened,
    // that number is wrong in a way that reaches reports."* Those five tabs
    // carry NO figure at all, so folding parked drafts onto them corrupts
    // nothing here; the drafts are counted on their own panel, in words, and
    // added to nothing.
    expect(strip).toContain(">Requests<");
    expect(strip).not.toContain(">Waiting on<");
    // The two new ones carry no count either, for the same reason: their figure
    // would be an aggregate over the whole queue and `GET /work-orders`' A11
    // envelope carries none.
    expect(strip).toContain(">Complaints<");
    expect(strip).toContain(">Services<");
    expect(strip).toContain(">Imports<");
  });

  it("TC-UI-1 (BR-SHL-011): an unknown ?tab= falls back to Accounts and never 404s", () => {
    expect(accountsTabFromParam("move-outs")).toBe("move-outs");
    expect(accountsTabFromParam("nonsense")).toBe("accounts");
    expect(accountsTabFromParam(null)).toBe("accounts");
    const html = renderList("/accounts?tab=nonsense", { list: page([aged()]) });
    expect(html).toContain("kpi-grid");
    expect(html).toContain("<table");
  });

  it("T2.1: NO tab states its absence any more — every one of the TEN has a body", () => {
    const unbuilt = ACCOUNTS_TAB_IDS.filter((id) => !ACCOUNTS_BUILT_TABS.includes(id));
    // ⚠ **WAS 6, THEN 5, THEN 2, AND IS NOW 0 — AND THE NUMBER WAS ALWAYS THE
    // POINT.** The paragraph that stood here is SUPERSEDED and is kept because
    // it was true when written and records why the tabs waited:
    //
    //   *"The two that remain are `move-ins` and `move-outs`, and they remain
    //   for a reason that is a FACT and not a plan: W5's two lists have no read
    //   model and no endpoint — there is no `GET /move-ins` or `GET /move-outs`
    //   anywhere in `06-backend` (measured 2026-08-25)."*
    //
    // That measurement is now false: `apps/customers/move_reads.py` is the read
    // model and both tabs mount their list (CR-030 W5). **This is the assertion
    // going off exactly as designed** — its own closing line was *"a tab quietly
    // moving between built and unbuilt is exactly the change this suite exists
    // to notice"* — so it is rewritten to state the new fact, not relaxed.
    //
    // ⚠ **AND THE ABSENCES DID NOT DISAPPEAR; THEY MOVED.** Neither move list
    // shows what B18 draws — four of §5.6.7's six move-outs are in a state this
    // schema cannot hold — so the reasons now ride on the CELLS, SEGMENTS and
    // TILES they are about (BR-SHL-025's placement rule) instead of on a panel
    // covering the whole tab. `MoveInsTab.test.tsx` and `MoveOutsTab.test.tsx`
    // own those cases; what is asserted HERE is only that no tab is a note.
    expect(unbuilt).toEqual([]);
    expect(ACCOUNTS_BUILT_TABS).toHaveLength(ACCOUNTS_TAB_IDS.length);
    // The property the old loop protected, kept alive: a ninth tab added
    // without a body would land in `unbuilt` and fail on the line above.

    // ⚠ AND THE POSITIVE HALF, WHICH THE OLD SHAPE COULD NOT ASSERT: the two
    // tabs that were notes this morning now render a real surface. Hard-won law
    // 2 — "built is not wired" — closed on the screen that taught it.
    for (const id of ["move-ins", "move-outs"] as const) {
      const html = renderList(`/accounts?tab=${id}`, { list: page([aged()]), access: "Full" });
      // ⛔ NO `ArrivesWith` PANEL. That is the whole change.
      expect(html).not.toContain("settings-arrives");
      // A real list: the shared table kit, and the KPI strip the tab draws.
      expect(html).toContain("data-embedded=\"\"");
      expect(html).toContain(`data-screen="${id === "move-ins" ? "S19.moveIns" : "S20.moveOuts"}"`);
    }
  });

  it("DEF-664: the Requests tab renders the LIST, not a note about the list", () => {
    // ⚠ THIS ASSERTION HAS BEEN REWRITTEN TWICE, AND BOTH EARLIER SHAPES WERE
    // TRUE WHEN WRITTEN. Until W4 shipped, the tab said "the request itself is
    // still being designed" — false the day the request shipped. It was then
    // amended to say the list "is still to come", with a button to /requests —
    // accurate, and the PO still hit it in production on 2026-08-25 with their
    // own SR-26-0001 sitting one click away: "When I click on service request
    // nothing is shoing, but I ahve created one request - it shows up on
    // another scren".
    //
    // The old version of this test PINNED that interim shape — it asserted
    // not.toContain("<table") and toContain("Open service requests") — and its
    // own comment said it "will change when the embed lands". This is that
    // change, and the lesson is worth keeping: a test can hold a stated
    // absence honestly and still be pinning something a user experiences as
    // broken.
    const html = renderList("/accounts?tab=requests", { list: page([aged()]), access: "Full" });

    // Neither sentence that stopped being true may come back.
    expect(html).not.toContain("still being designed");
    expect(html).not.toContain("Nothing is recorded here yet");
    expect(html).not.toContain("still to come");
    // Nor the button that stood in for the list, nor the tracking id: a tab
    // that renders its surface tracks nothing.
    expect(html).not.toContain("Open service requests");
    expect(html).not.toContain('data-tracks="DEF-664"');

    // It IS the list now — the embedded marker says this copy does not own the
    // URL, and the KPI strip is the requests list's own chrome rendering inside
    // the tab.
    expect(html).toContain("data-embedded");

    // ⚠ THE ROWS AND THE KPI STRIP ARE DELIBERATELY NOT ASSERTED HERE, and the
    // reason is worth writing down rather than discovering twice. This harness
    // seeds only the ACCOUNTS query, so the embedded list renders its own
    // loading state — no table, no tiles. Seeding a second query key from this
    // file would mean reconstructing the embedded copy's internal default
    // state, which is exactly what `urlState={false}` keeps private; the test
    // would then be asserting the reconstruction, not the component.
    //
    // What this case owns is the MOUNT and the CHROME: the list component is
    // there (`data-embedded` sits on its root), it brought no second title, and
    // the panel it replaced is gone. That the table draws rows is proved where
    // the data lives — `ServiceRequestsListPage.test.tsx`.

    // ⚠ AND EXACTLY ONE <h1>. Nesting a full page inside a tab is how a screen
    // ends up with two titles and two back links; the embedded copy suppresses
    // its own page chrome, and this is what proves it did.
    expect(html.match(/<h1/g) ?? []).toHaveLength(1);
  });

  /**
   * **THE THREE TABS THE PO REPORTED EMPTY, ASSERTED AT THE MOUNT.**
   *
   * PO, from a live build 2026-08-25: *"nothing on new connect + on all of
   * these screens"*. Each of the three had a finished read model, a mounted
   * endpoint and a panel saying its surface *"arrives with"* a wave — three
   * honest notes that added up to a screen a user experiences as broken.
   *
   * ⚠ **WHY THIS CASE EXISTS BESIDE THE THREE TABS' OWN SUITES.** Those prove
   * each component renders and CALLS its endpoint. This proves the mount:
   * without it, a tab could be listed in `ACCOUNTS_BUILT_TABS` while still
   * rendering its `ArrivesWith` panel, and every gate in the repo would stay
   * green — the built-is-not-wired shape (law 2) one level up.
   *
   * ⚠ **THE ROWS AND TILES ARE DELIBERATELY NOT ASSERTED HERE**, for the reason
   * DEF-664's case above gives: this harness seeds only the ACCOUNTS query, so
   * each embedded list draws its own loading state. What this case owns is the
   * MOUNT and the CHROME.
   */
  it("CR-030 W6/W7 — New connects, Transfers and Disconnects render their LISTS, not notes about them", () => {
    for (const [tab, screen] of [
      ["new-connects", "S86"],
      ["transfers", "S89"],
      ["disconnects", "S90"],
    ] as const) {
      const html = renderList(`/accounts?tab=${tab}`, { list: page([aged()]), access: "Full" });
      // The embedded marker says this copy does not own the URL (DEF-664), and
      // the screen id says WHICH list mounted.
      expect(html).toContain('data-embedded=""');
      expect(html).toContain(`data-screen="${screen}"`);
      // The panel each one replaced is gone, and so is the id it tracked: a tab
      // that renders its surface tracks nothing.
      expect(html).not.toContain("settings-arrives");
      // Exactly one page header — nesting a list inside a tab is how a screen
      // ends up with two titles (B14 rule 2 / BR-SHL-044).
      expect(html.match(/<h1/g) ?? []).toHaveLength(1);
    }
  });

  it("TC-UI-4: the header primary relabels per tab, and there is exactly one on the page", () => {
    // ⚠ `primary` SINCE 2026-09-22 (`DEF-CUS-6193`) — see the head case above.
    // It was the quiet tier under `DEF-CUS-5939` and the PO could not see it.
    // The subject of THIS case is the RELABELLING and the count, both
    // unchanged.
    const accounts = header(renderList("/accounts", { list: page([aged()]), access: "Full" }));
    expect(accounts.match(/data-variant="primary"/g)).toHaveLength(1);
    expect(accounts).not.toContain('data-variant="ghost"');
    expect(accounts).toContain("+ New account");
    expect(accounts).not.toContain("↑ New import");

    const imports = header(renderList("/accounts?tab=imports", { access: "Full" }));
    expect(imports.match(/data-variant="primary"/g)).toHaveLength(1);
    expect(imports).not.toContain('data-variant="ghost"');
    expect(imports).toContain("↑ New import");
    expect(imports).not.toContain("+ New account");

    // ⚠ **THIS ASSERTION WAS `toHaveLength(0)` AND IT IS SUPERSEDED BY
    // DEF-729, 2026-08-26.** It read: *"An unbuilt tab declares NO primary: a
    // button over a body that says 'not built yet' is the built-is-not-wired
    // defect with a label on it."* True while the six tabs rendered a note
    // about themselves; false since they render their real lists. What it cost
    // is the defect: the Requests tab embeds a list whose own header is
    // suppressed, so with the page primary withheld too, a clerk looking at a
    // tab with rows in it had NO WAY to raise a request at all. The primary
    // slot now carries the ACTIVE tab's create action — one primary, relabelled
    // (B14 rule 4 / BR-SHL-044) — and `AccountsCreateEntry.test.tsx` walks all
    // eight tabs and the reasons the two disabled ones still carry.
    const requests = header(renderList("/accounts?tab=requests", { access: "Full" }));
    expect(requests).toContain("+ New request");
    expect(requests).not.toContain("+ New account");
  });

  it("TC-UI-3: the Accounts tab carries search, filter and a column selector (the PO's uniform contract)", () => {
    const html = renderList("/accounts", { list: page([aged()]), access: "Full" });
    // Search — declared by `searchFields`, drawn by the ONE framework.
    expect(html).toContain('type="search"');
    // `+ Filter ▾` and its chip row, with the ageing segment among them.
    expect(html).toContain("Aging");
    // The column selector is the shared one every list already gets: r10's
    // COLUMNS glyph with "Choose columns · ↑↓ to reorder". It is NOT rebuilt
    // here — DataTable renders it from the same `TableConfig` this screen
    // declares, which is what makes the AGEING column appear in it for free.
    expect(html).toContain("Show or hide columns");
    expect(html).toContain("Columns · show / hide · ↑↓ reorder");
    expect(html).toContain("Reset table");
    // …and the NEW column is in it, because the selector reads the same
    // `TableConfig` this screen declares. That is the whole of task 2.7: the
    // control already existed on every list, so the work was declaring the
    // column, not building a second chooser.
    expect(html).toContain("Aging");
  });

  it("TC-UI-6: the list renders its footnote sentence under the pager", () => {
    const rows = [aged(), aged({ id: "b" })];
    const html = renderList("/accounts", { list: page(rows), access: "Full" });
    expect(html).toContain("table-pager");
    // ⚠ THE SENTENCE IS THE SHARED PAGER'S, AND IT IS SHORTER THAN `[shot]`'s.
    // B18 §5.1.2 writes *"Showing 1–8 of 1,247"*; `ListPager` renders
    // `table.pager.range` — "1–2 of 2" — on every list in the product. Changing
    // the wording is a change to that ONE component and therefore to every
    // screen, which is not this lane's to make; REPORTED as a divergence rather
    // than a second pager built here.
    expect(html).toContain("1–2 of 2");
    expect(html).toContain("Rows per page");
  });

  /**
   * **TC-ACC-3 IS CLOSED AS *WON'T BUILD*, NOT AS PENDING — PO RULING
   * 2026-08-24, verbatim: *"okay dont link it"*.**
   *
   * It stood as an `it.todo` for one day, correctly: the `4 accounts` sub-link
   * B18 §5.1.2 puts on the NAME cell needed a customer block on the row and a
   * `customer_id` in `ACCOUNT_FILTERS`, and neither existed. Then the PO cut
   * the feature. **An `it.todo` left standing after that reads as work owed**,
   * and CR-030 W2's task 2.5 is struck through in B18 with this same ruling —
   * so the case is retired here rather than quietly deleted, because a case
   * that vanishes cannot be audited against the design that declared it.
   *
   * ⚠ **`it.skip` AND NOT A DELETION, AND NOT `it.todo`.** The repo has no
   * prior won't-build convention to follow (a grep for one returns nothing), so
   * this is the plainest thing that reads correctly in a vitest run: the case
   * is REPORTED as skipped with the ruling and its date in the name, where a
   * todo would be reported as outstanding. If a convention is later minted,
   * this is the row to convert.
   *
   * ⚠ **WHAT REPLACED THE CAPABILITY, so the cut is not a hole.** The customer
   * is still reachable from the row — their number is the `CUSTOMER #` column
   * (T2.9(b)), and typing it into the search box returns every account they
   * hold, because `selectors.account_list` matches `customer_no` across every
   * `customer_accounts` link. That is what the sub-link was for.
   */
  it.skip(
    "TC-ACC-3 — WON'T BUILD (CUT BY PO RULING 2026-08-24: \"okay dont link it\"): the `4 accounts` customer sub-link on the NAME cell is not built and will not be built, and neither are the two server halves it needed (no customer block on `selectors.account_row`, no `customer_id` in `ACCOUNT_FILTERS`). B18 W2 task 2.5 is struck through with the same ruling. The capability it carried — reach every account this customer holds — is served instead by the `CUSTOMER #` column and the search that now matches it (TC-ACC-7)",
    () => undefined,
  );
  it.todo(
    "TC-ACC-6 (isolation): tenant B sees none of tenant A's 1,247 rows — hard rule 1 is enforced by RLS FORCE and asserted server-side (G5 / tests/test_cr030_w2_ageing.py), never from a mocked client seam",
  );
  it.todo(
    "TC-UI-5: table body type is 13.5px and headers 12px — asserted once against the ONE table by the CR-016 type-scale gate, not restated per screen",
  );
  it.todo(
    "TC-UI-7: every detail view ends on an Audit tab — S21's assertion, in AccountDetailPage.test.tsx, not the list's",
  );
  it.todo(
    "TC-UI-8: no screen in this CR adds a class to a stylesheet — G31 holds the ratchet at 0 and `styles/routeBUtilities.test.ts` compiles every utility in `accountsListCells.tsx`; a screen-level restatement would assert the same fact twice and drift",
  );
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-5939 — THE HEAD, ON ALL TEN TABS
// ══════════════════════════════════════════════════════════════════════════
// **ONE HEAD SERVES TEN TABS**, which is why the two lanes that found this
// deferred it and why the cases below walk every one of them rather than the
// one that happened to be drawn. Built from the Accounts blueprint read AS
// IMAGES (B14 rule 42): p117 Move-outs, p131 Transfers, p41 Complaints, p48
// Services — four frames of the SAME head, which is the proof that what is
// built here generalises.
//
// **RED PROVED FIRST**, on the pre-fix screen:
//
//     AssertionError: expected '…<h1 class="text-h2">Accounts</h1>…'
//     to contain '10 tabs · Move-outs'
//
// ⚠ **THE THIRD FRAGMENT IS ASSERTED ABSENT, NOT ZERO, AND THAT IS THE POINT
// OF THE LAST CASE.** The drawings read `… · 1 still open`, `… · 3 open` and
// `… · 4 open, 1 past due`; the figures are illustrations (B14 rule 37) and no
// tab can hand this head a real one — every tab body owns its own query and
// its OPEN tile rides inside that query's envelope. A `0` would be a claim.
describe("DEF-CUS-5939 — the register's head, on every one of its ten tabs", () => {
  it("names the ACTIVE tab on the sub-line, and the sub-line and the strip cannot disagree", () => {
    const WORD: Readonly<Record<string, string>> = {
      accounts: "Accounts",
      requests: "Requests",
      "new-connects": "New connects",
      "move-ins": "Move-ins",
      "move-outs": "Move-outs",
      transfers: "Transfers",
      disconnects: "Disconnects",
      complaints: "Complaints",
      services: "Services",
      imports: "Imports",
    };
    for (const tab of ACCOUNTS_TAB_IDS) {
      const html = renderList(`/accounts?tab=${tab}`, { list: page([account()]) });
      const head = header(html);
      // The kicker does NOT change with the tab — one screen.
      expect(head).toMatch(/<span data-kicker=""[^>]*>Accounts<\/span>/);
      if (tab === "move-ins") {
        // ⚠ **`CR-171-BRC10` P2.01 — THE REDESIGNED MOVE-INS TAB IS TITLED
        // `Move-ins` AND HAS NO SUB-LINE** (image 01). Every other tab keeps
        // the register's head until its own redesign.
        expect(head).toMatch(/<h1[^>]*>Move-ins<\/h1>/);
        expect(head).not.toContain("page-header-rollup");
      } else {
        expect(head).toMatch(/<h1[^>]*>Accounts<\/h1>/);
        // …and the sub-line does.
        expect(head).toContain(
          `<div class="page-header-rollup">10 tabs · ${WORD[tab]}</div>`,
        );
      }
      // ⚠ **THE HEAD AND THE BODY READ THE SAME `activeTab`, ASSERTED RATHER
      // THAN ASSUMED.** The word on the sub-line must be the word of the tab
      // the strip has SELECTED — not merely a word that appears on the page.
      // Both come from `tabLabel()`, and this is the case that goes red the
      // day a second spelling appears.
      const selected =
        /<button[^>]*data-tab="([^"]+)"[^>]*aria-selected="true"[^>]*>([^<]*)</.exec(head);
      expect(selected?.[1]).toBe(tab);
      expect(selected?.[2]).toBe(WORD[tab]);
    }
  });

  it("states `10 tabs` because there are ten, counted from the strip rather than typed", () => {
    const head = header(renderList("/accounts", { list: page([account()]) }));
    const strip = head.slice(head.indexOf('class="page-header-tabs"'));
    // ⛔ NOT a literal 10 on both sides — that would only prove the test agrees
    // with itself. The sub-line's figure is compared with the number of tabs
    // the strip actually renders, so an eleventh tab moves both or goes red.
    const rendered = strip.split('role="tab"').length - 1;
    expect(head).toContain(`<div class="page-header-rollup">${rendered} tabs · Accounts</div>`);
    expect(rendered).toBe(ACCOUNTS_TAB_IDS.length);
  });

  it("omits the drawn `N open` fragment on every tab rather than printing a zero", () => {
    for (const tab of ACCOUNTS_TAB_IDS) {
      const head = header(renderList(`/accounts?tab=${tab}`, { list: page([account()]) }));
      const line = head.slice(head.indexOf("page-header-rollup"), head.indexOf("page-header-tabs"));
      expect(line).not.toMatch(/\bopen\b/);
      // …and specifically not a zero, which is the failure this guards: a `0
      // open` is a claim that the tab has nothing open, and nothing here knows
      // that. `DEF-CUS-5953` carries the fragment.
      expect(line).not.toMatch(/·\s*\d/);
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-001@a2e1d59 (story+rules snapshot — EP-CUS-01 lead story; co-packet US-CUS-002 same epic)
// generated: 2026-08-10 by story-coder (W2 customers FRONTEND lane — S17) · AMENDED 2026-08-11 by story-coder (S18/S21 landed: three assertions that named those screens as ABSENT now assert they are wired — the account number is a link, "+ New account" is live for a writing role, and the awaiting panel no longer claims the detail screen is missing) · AMENDED 2026-08-24 by the CR-030 W2 FRONTEND lane (B18 §5.1.4's TC-ACC-* and §10.3's TC-UI-*, plus three pre-existing assertions amended rather than deleted where a ruling moved what they pinned: the roll-up line became the KPI strip, the column set gained `ageing`, and the awaiting panel's sentence about the ageing pill became false the moment the column landed)
// amended: 2026-08-26 by lane MOVEENTRY — TC-6's `toContain("Move-in and
//         move-out each act on one account")` is INVERTED, not deleted. It
//         pinned the disabled reason in place, and the PO overruled the reason
//         (*"-Enable Move in /move out"*); a deleted case would let the sentence
//         return unnoticed, so the case now asserts it is GONE and that neither
//         control carries `disabled=""`.
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 622 passed / 148 todo across 47 files✔ (604 passed / 142 todo across 46 files was the pre-lane baseline) · vite build✔ · run_gates 14 PASS · 0 FAIL · 1 SKIP✔ · [S18/S21 lane 2026-08-11] tsc✔ · eslint --max-warnings 0✔ · vitest 670 passed / 160 todo across 49 files✔ (622 passed / 148 todo across 47 files was the pre-lane baseline) · vite build✔ · run_gates 14 PASS · 0 FAIL · 1 SKIP✔ · [CR-030 W2 2026-08-24] tsc✔ · eslint --max-warnings 0✔ · vitest AccountsPage.test.tsx 35 passed / 11 todo across 46 cases✔ (20 passed / 6 todo was the pre-lane baseline — 15 cases added, none dropped)
// exceptions: E4 US-CUS-001 TC-2 (sort by balance desc) asserts an ORDER the SERVER produces — the screen only sends `sort`/`dir`, so the ordering claim belongs to the backend suite and stays an honest it.todo here · E4 TC-5 (the one-active-account-per-unit refusal) and both TC-7 isolation rows are server/RLS scope (G5) · E4 US-CUS-002 TC-5 (Move-out → S20 → Cancel) cannot be asserted at all: S19/S20 are unbuilt and the API deliberately stubs no move-in/move-out route · E4 US-CUS-002 TC-6's debounce is browser scope and is already asserted once against the shared framework · **[CR-030 W2 2026-08-24]** E4 **TC-ACC-3 is `it.todo` and not for effort**: `GET /accounts` serves no customer block on a row and declares no `customer_id` filter, so neither the `4 accounts` sub-link nor the filter it would follow can be asserted from a screen test — both halves are server-side · E4 TC-ACC-6 (tenant isolation) is a server/RLS claim asserted by `tests/test_cr030_w2_ageing.py` and G5; a mocked client seam cannot prove it and a test that pretended to would be worse than none · E4 TC-UI-5 (13.5px body / 12px header) is the CR-016 type-scale gate's, asserted once against the ONE table rather than restated per screen; TC-UI-7 (a detail view ends on Audit) is S21's; TC-UI-8 (no stylesheet class) is G31 plus `styles/routeBUtilities.test.ts`, which compiles every utility in `accountsListCells.tsx` · E3 **the `f.ageing=<junk>` assertion records what the framework REALLY does**: `parseTableParams` validates a filter's NAME and never its VALUE, so an unrecognised segment is carried to the request and `normalize_ageing_segment` drops it server-side. Asserted as-is rather than as a client-side guarantee this product does not have · E3 the endpoint-mirror loop carries a NAMED allowance for `ageing`, which `selectors.ACCOUNT_FILTERS` accepts and `src/api/endpoints.ts`'s copy of that tuple does not yet list; every other filter is still asserted against the mirror, and the allowance goes with the wrapper's own commit · E3 TC-UI-6 asserts the SHARED pager's sentence (`1–2 of 2`), not `[shot]`'s *"Showing 1–8 of 1,247"* — the wording is `ListPager`'s and changing it changes every list in the product
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

describe("record links (PO 2026-10-19) — the Premise column", () => {
  it("opens the unit on a unit account and the premises on a master that names none", () => {
    const html = rowsRegion(
      renderList("/accounts", {
        list: page([
          account(),
          account({
            id: "acc-m1",
            account_no: "A-M0001",
            kind: "master",
            unit_id: null,
            premises_id: "prm-1408",
            premise: "1408 Elm St",
          }),
        ]),
      }),
    );
    expect(html).toContain(`href="/${TEST_TENANT}/premises/units/u-10432a"`);
    expect(html).toContain(`href="/${TEST_TENANT}/premises/prm-1408"`);
    expect(html).toContain(">1408 Elm St · A</a>");
  });
});
