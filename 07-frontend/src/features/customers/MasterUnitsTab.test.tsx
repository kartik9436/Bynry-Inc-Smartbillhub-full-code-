// ── Trace ──────────────────────────────────────────────
// Change:   `BR-CUS-1094` (PO 2026-09-23) — the **Units** tab on a MASTER
//           account's detail screen. PO verbatim: *"show all units with its
//           status what wil be billed to master account - can we do that?"*
//           Drawing: `05-prototype/Premises & Units Blueprint 2.pdf` p23–25,
//           read as IMAGES (B14 rule 42) — the PROPERTY's Units tab, whose
//           design language transfers and whose subject does not.
//           Screens: S21 (the account detail)
// Story:    US-CUS-008 (the S21 tab strip is URL state)
// Rules:    BR-CUS-1094 (this tab's subject) · BR-CUS-170 (the owner's bill
//           carries every unit nobody else pays for) · BR-CUS-1040 (no
//           per-unit PRICE outside a bill run) · BR-CUS-068 · BR-CUS-1010 ·
//           BR-MET-036 (occupancy DERIVED) · BR-MET-101 (a common area is
//           never *occupied*) · B14 rule 12 (a dimension is a filter chip) ·
//           B14 rule 31 (no database id on screen) · B14 rule 32 (a stated
//           absence is CLOSED by default) · B14 rule 33 (rationale is ZERO
//           words on screen)
// ───────────────────────────────────────────────────────
// ⚠ **EVERY CASE HERE WAS PROVED RED BEFORE THE TAB EXISTED** (hard-won law 7),
// through `npx vitest run src/features/customers/MasterUnitsTab.test.tsx` — the
// harness that will run it — and not through a node script. The failures are
// quoted at the foot of this file.
//
// ⚠ **THE COMPONENT IS MOUNTED UNDER THE REAL PATH PATTERN `App.tsx` USES.**
// A bare `MemoryRouter` with no `/:tenant/accounts/:accountId` route leaves
// `useParams().tenant` undefined and every link the page builds comes out
// `//accounts/…` — a protocol-relative URL to another host, which reads as a
// perfectly good string to `toContain` (hard-won law 2's fixture clause, and
// it has already gone wrong twice on this feature).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { AccountDetail, MasterUnitRow, MasterUnitsPage } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import {
  ACCOUNT_TAB_IDS,
  AccountDetailPage,
  accountDetailQueryKey,
  accountTabIds,
  accountTabs,
} from "./AccountDetailPage";
import { MASTER_UNITS_STATE, masterUnitsQueryKey } from "./MasterUnitsTab";
import { ACCOUNTS_PERMISSION, ACCOUNT_CATEGORIES_QUERY_KEY } from "./customersShared";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** 1408 Elm Street — `BR-MET-101`'s worked building and `BR-CUS-068`'s signed
 *  `$69.60`. The owner account hangs off the ADDRESS (`BR-CUS-1010`). */
const PREMISES = "prm-1408-elm";
const ACCOUNT = "acc-10001";

function detail(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: ACCOUNT,
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
    account_type: "commercial",
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
    covered_units: 1,
    ...over,
  } as unknown as AccountDetail;
}

function unit(over: Partial<MasterUnitRow> = {}): MasterUnitRow {
  return {
    unit_id: "u-a",
    label: "Unit A",
    unit_no: "U-01144",
    is_common_area: false,
    occupancy: "occupied",
    metering_occupancy: "occupied",
    payer: "tenant",
    payer_basis: "occupying_account",
    account_no: "A-10517",
    not_charged: null,
    unit_type: "residential",
    floor_label: "Ground",
    meters: [],
    metered_services: ["electric"],
    occupant: "Alvarez, M.",
    owed: {
      balance: "61.400000",
      balance_currency: "USD",
      balance_unavailable: [],
      balance_not_yet_billable: false,
    },
    status: "active",
    ...over,
  } as unknown as MasterUnitRow;
}

/** The blueprint's own building: three occupied, one vacant, plus a hallway. */
const OCCUPIED = unit();
const VACANT = unit({
  unit_id: "u-d",
  label: "Unit D",
  unit_no: "U-01147",
  occupancy: "vacant",
  metering_occupancy: "vacant",
  payer: "this_account",
  payer_basis: "vacant_base_only",
  account_no: null,
  occupant: null,
  owed: null,
  status: "vacant",
});
const HALLWAY = unit({
  unit_id: "u-h",
  label: "Hallway lighting",
  unit_no: "U-01148",
  is_common_area: true,
  occupancy: "vacant",
  metering_occupancy: "vacant",
  payer: "this_account",
  payer_basis: "service_agreement",
  account_no: null,
  unit_type: "common_area",
  occupant: null,
  owed: null,
  status: "active",
});
/** Vacant, no plan — `gather._unbilled_unit_tariffs` raises NO line for it. */
const UNPLANNED = unit({
  unit_id: "u-z",
  label: "Unit Z",
  unit_no: "U-01149",
  occupancy: "vacant",
  metering_occupancy: "vacant",
  payer: "this_account",
  payer_basis: "vacant_base_only",
  account_no: null,
  not_charged: "no_plan",
  occupant: null,
  owed: null,
  status: "vacant",
});
/** Vacant and reaching NOBODY — `BR-CUS-1094`'s stated refusal. */
const ORPHAN = unit({
  unit_id: "u-o",
  label: "Unit O",
  unit_no: "U-01150",
  occupancy: "vacant",
  metering_occupancy: "vacant",
  payer: "nobody",
  payer_basis: null,
  account_no: null,
  occupant: null,
  owed: null,
  status: "vacant",
});

function page(rows: MasterUnitRow[]): MasterUnitsPage {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    counts: {
      units: rows.length,
      occupied: rows.filter((r) => r.occupancy === "occupied").length,
      vacant: rows.filter((r) => r.occupancy === "vacant").length,
      billed_here: rows.filter((r) => r.payer === "this_account").length,
      billed_nobody: rows.filter((r) => r.payer === "nobody").length,
    },
  } as unknown as MasterUnitsPage;
}

function renderDetail(
  path: string,
  seed: { detail: AccountDetail; rows?: MasterUnitRow[] },
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(ACCOUNT_CATEGORIES_QUERY_KEY, {
    selectable: [{ code: "commercial", name: "Commercial" }],
    legacy: [],
  });
  queryClient.setQueryData(accountDetailQueryKey(seed.detail.id), seed.detail);
  queryClient.setQueryData(queryKeys.myPermissions, {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access: "write" }],
  });
  if (seed.rows !== undefined) {
    queryClient.setQueryData(
      masterUnitsQueryKey(String(seed.detail.id), MASTER_UNITS_STATE),
      page(seed.rows),
    );
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

const UNITS_PATH = `/accounts/${ACCOUNT}?tab=units`;
const FULL_BUILDING = [OCCUPIED, VACANT, HALLWAY, UNPLANNED, ORPHAN];

describe("BR-CUS-1094 — the Units tab exists only on a master account", () => {
  it("the tab vocabulary gains `units` straight after `accounts`, for a master only", () => {
    expect(accountTabIds("master")).toEqual([
      "overview",
      "accounts",
      "units",
      ...ACCOUNT_TAB_IDS.slice(1),
    ]);
    // …and an ordinary account's strip is BYTE-FOR-BYTE what it was.
    expect(accountTabIds("regular")).toEqual([...ACCOUNT_TAB_IDS]);
    expect(accountTabs(t).map((tab) => tab.label)).not.toContain("Units");
  });

  it("the master's own strip RENDERS Units third, and an ordinary one does not", () => {
    // Hard-won law 2: the constant above cannot promise the strip. This reads
    // the rendered tablist of the REAL page.
    const master = tabOrder(renderDetail(UNITS_PATH, { detail: detail(), rows: FULL_BUILDING }));
    expect(master[0]).toBe("Overview");
    expect(master[1]).toBe("Accounts");
    expect(master[2]).toBe("Units");

    const ordinary = tabOrder(
      renderDetail(`/accounts/${ACCOUNT}?tab=overview`, {
        detail: detail({ kind: "regular", unit_label: "Unit A", covered_units: null }),
      }),
    );
    expect(ordinary).not.toContain("Units");
  });
});

describe("BR-CUS-1094 — every unit is listed, with who its bill goes to", () => {
  it("draws the eight columns, with `Billed to` among them", () => {
    const html = renderDetail(UNITS_PATH, { detail: detail(), rows: FULL_BUILDING });
    expect(columnHeadings(html)).toEqual([
      "Unit",
      "Type",
      "Floor",
      "Meters",
      "Occupant",
      "Billed to",
      "Owed",
      "Status",
    ]);
  });

  it("lists the vacant units, which appear on no accounts list anywhere", () => {
    // The gap this tab exists to close: a vacant unit has no account, so
    // `MasterAccountsTab` cannot show it and neither can the register.
    const html = renderDetail(UNITS_PATH, { detail: detail(), rows: FULL_BUILDING });
    expect(html).toContain("Unit D");
    expect(html).toContain("Unit Z");
    expect(html).toContain("Hallway lighting");
  });

  it("an occupied unit names its tenant's account, and a vacant one names this account", () => {
    const html = renderDetail(UNITS_PATH, { detail: detail(), rows: [OCCUPIED, VACANT] });
    expect(html).toContain('data-billed-to="tenant"');
    expect(html).toContain("A-10517");
    expect(html).toContain('data-billed-to="this-account"');
    expect(html).toContain(t("customers.account.accounts.thisAccount"));
    // …and the vacant row says WHY it is billed here, which is not the same
    // reason the hallway is.
    expect(html).toContain(t("customers.account.units.basis.vacant"));
  });

  it("a common area says `Its own agreement`, never the vacancy sentence", () => {
    // `BR-MET-101` — a hallway is never *occupied* and must never read like a
    // vacant flat; and `BR-CUS-068` is a written agreement, not a rule that
    // lapses the day a tenant moves in.
    const html = renderDetail(UNITS_PATH, { detail: detail(), rows: [HALLWAY] });
    expect(html).toContain(t("customers.account.units.basis.agreement"));
    expect(html).not.toContain(t("customers.account.units.basis.vacant"));
  });

  it("a vacant unit with no plan says nothing is billed, rather than promising a charge", () => {
    // `gather._unbilled_unit_tariffs` skips a coverage entry outright on
    // `not has_plan`, so *billed to this account* alone would be false.
    const html = renderDetail(UNITS_PATH, { detail: detail(), rows: [UNPLANNED] });
    expect(html).toContain(t("customers.account.units.notCharged.noPlan"));
    expect(html).not.toContain(t("customers.account.units.basis.vacant"));
  });

  it("a unit reaching NOBODY is a stated refusal and is counted separately", () => {
    // `BR-CUS-1094`: *"'no lines because nothing falls to it' and 'no lines
    // although the premises HAS an unoccupied unit' are different facts and
    // only one of them is good news."*
    const html = renderDetail(UNITS_PATH, { detail: detail(), rows: FULL_BUILDING });
    expect(html).toContain('data-billed-to="nobody"');
    expect(html).toContain(t("customers.account.units.billed.nobody"));
    expect(html).toContain('data-billed-nobody="1"');

    // …and with nobody orphaned, that sentence is ABSENT rather than zero.
    const clean = renderDetail(UNITS_PATH, { detail: detail(), rows: [OCCUPIED, VACANT] });
    expect(clean).not.toContain("data-billed-nobody");
  });

  it("a vacant row never draws a dash where the money is, and is never `0.00`", () => {
    // The blueprint's own rule, and `DEF-138`: *"a dash on that row reads as
    // `nothing is billed`, which is the opposite of true"*, and a vacant unit
    // was never MEASURED — no occupying account means the books were not asked.
    const html = renderDetail(UNITS_PATH, { detail: detail(), rows: [VACANT] });
    expect(html).toContain(t("metering.units.owed.notMeasured"));
    // ⚠ **SCOPED TO THE TABLE BODY, AND THE FIRST DRAFT WAS NOT.** Asserting
    // `not.toContain("0.00")` over the whole page failed on the account
    // HEADER's own `$0.00` deposit — a true figure about a different subject.
    // A check that fails on somebody else's correct number is a check that
    // gets weakened rather than read.
    const body = html.slice(html.indexOf("<tbody>"), html.indexOf("</tbody>"));
    expect(body).not.toContain("0.00");
    // The Occupant cell carries the vacancy sentence, imported from the
    // property tab rather than re-written here.
    expect(html).toContain('data-occupant-state="vacant"');
  });

  it("the footer counts are the size of the job", () => {
    const html = renderDetail(UNITS_PATH, { detail: detail(), rows: FULL_BUILDING });
    expect(html).toContain(
      t("customers.account.units.footerCounts", { occupied: 1, vacant: 4, billed: 3 }),
    );
  });
});

describe("BR-CUS-1094 — what the tab must NOT say", () => {
  it("prints no database id anywhere (B14 rule 31)", () => {
    // The unit NUMBER is shown and is not an id: the blueprint corrects an
    // earlier draft of its own on exactly this point (p23, p25).
    const html = renderDetail(UNITS_PATH, { detail: detail(), rows: FULL_BUILDING });
    expect(html).toContain("U-01147");
    for (const row of FULL_BUILDING) {
      expect(html).not.toContain(`>${row.unit_id}<`);
    }
    expect(html).not.toContain(">acc-10001<");
  });

  it("states no PRICE for any unit (BR-CUS-1040)", () => {
    // *"NO PRICE IS STATED — a single what the empty unit will cost figure is
    // the rating engine's."* `Owed` is what a unit owes TODAY, not a forecast.
    const html = renderDetail(UNITS_PATH, { detail: detail(), rows: FULL_BUILDING });
    for (const word of ["will cost", "estimated", "forecast", "next bill"]) {
      expect(html.toLowerCase()).not.toContain(word);
    }
  });

  it("prints no rationale and offers no `+ New unit` (B14 rules 32 + 33)", () => {
    const html = renderDetail(UNITS_PATH, { detail: detail(), rows: FULL_BUILDING });
    // ⚠ **TWO THINGS THIS CASE GOT WRONG FIRST TIME, BOTH WORTH KEEPING.**
    //
    // (a) It asserted the notes' TEXT was in the markup. `Disclosure` renders
    //     its children **only when open**, so the text is genuinely absent —
    //     which is rule 32 working, not a bug. The heading is what is on
    //     screen closed, so that is what is asserted.
    // (b) It asserted `not.toMatch(/<details[^>]*\sopen/)`. `Disclosure` is a
    //     `<button>` and a region, not a `<details>` — **so that assertion
    //     could never fail, on any input, ever.** It is law 7's *structurally
    //     incapable of failing* shape in one line of a test. The real closed
    //     state is `aria-expanded="false"` on the toggle.
    expect(html).toContain(t("customers.account.accounts.notes"));
    expect(html).not.toContain(t("customers.account.units.decidedAtRun"));
    expect(html).toContain('aria-expanded="false"');
    // A unit is created at its BUILDING; a CTA here would navigate away to
    // find its own subject.
    expect(html).not.toContain(t("metering.units.action.new"));
  });

  it("renders no raw message key — every value resolves in the catalogue", () => {
    // ⚠ **A KEY THE ELEVEN CATALOGUES DO NOT HOLD RENDERS AS ITSELF AND EVERY
    // ASSERTION ABOVE STILL PASSES.** Four landed that way in one day. This is
    // the assertion that refuses it.
    const html = renderDetail(UNITS_PATH, { detail: detail(), rows: FULL_BUILDING });
    const leaked = [...html.matchAll(/>(customers\.account\.units\.[A-Za-z.]+)</g)].map(
      (m) => m[1],
    );
    expect(leaked).toEqual([]);
    // ⚠ **THIS GREP HAS A BLIND SPOT AND IT IS NAMED RATHER THAN LEFT AS A
    // ZERO.** `Disclosure` renders its children only when OPEN, so a raw key
    // inside the notes panel is invisible here — which is exactly how
    // `customers.account.units.notes` reached a screen in this lane's first
    // draft and was caught by the positive half below, not by this grep. A
    // check reporting zero over a scope it silently excludes is law 7's
    // hardest shape (`G32`'s own lesson), so the positive list is the real
    // assertion and this one is the cheap first pass.
    // …and positively: every key this tab renders IS in the catalogue.
    for (const key of [
      "customers.account.tab.units",
      "customers.account.units.col.billedTo",
      "customers.account.units.filter.billedTo",
      "customers.account.units.billed.tenant",
      "customers.account.units.billed.nobody",
      "customers.account.units.basis.vacant",
      "customers.account.units.basis.agreement",
      "customers.account.units.notCharged.noPlan",
      "customers.account.units.notCharged.noConnection",
      "customers.account.units.occupancy.occupied",
      "customers.account.units.searchPlaceholder",
      "customers.account.units.emptyTitle",
      "customers.account.units.emptyHelper",
      "customers.account.units.footerCounts",
      "customers.account.units.footerNobody",
      "customers.account.units.decidedAtRun",
      // Reused rather than minted — the disclosure's heading and its second
      // note are `MasterAccountsTab`'s own, and this asserts they still exist.
      "customers.account.accounts.notes",
      "customers.account.accounts.noTotal",
    ]) {
      expect(t(key)).not.toBe(key);
    }
  });

  it("offers both filter chips and no segment strip (B14 rule 12)", () => {
    const html = renderDetail(UNITS_PATH, { detail: detail(), rows: FULL_BUILDING });
    expect(html).toContain(t("customers.account.units.filter.billedTo"));
    expect(html).toContain(t("metering.units.col.occupancy"));
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: `BR-CUS-1094` (PO 2026-09-23)
// generated: 2026-09-23 by lane MA-UNITS
// gates: PROVED RED FIRST in the harness that runs it, in a detached worktree
//        at the branch tip so no other lane's tree was touched (law 11's
//        mechanism two), and **BOTH HALVES OF HARD-WON LAW 2 SEPARATELY**,
//        because a single red cannot tell them apart:
//
//        (2) THE COMPONENT PRESENT AND THE MOUNT DISABLED — a tab LABEL over
//            no body, which is exactly what a live strip in front of dead UI
//            looks like:
//              Tests  11 failed | 4 passed (15)
//            The four that held are the tab-strip cases, correctly: the door
//            IS there. Every table case named the missing thing by name, e.g.
//              → expected [] to deeply equal [ 'Unit', 'Type', 'Floor', …(5) ]
//              → expected '<div…' to contain 'data-billed-to="tenant"'
//
//        (3) THE MOUNT RESTORED AND `ACCOUNT_MASTER_UNITS_TAB_ID` LEFT OUT OF
//            `accountTabIds` — the mirror, a live body no door points at:
//              Tests  13 failed | 2 passed (15)
//              → expected [ 'overview', 'accounts', …(11) ] to deeply equal
//                [ 'overview', 'accounts', …(12) ]
//              → expected 'Bills' to be 'Units'
//
//        ⚠ **STAGE 3 TOOK 13 AND NOT 2, AND THAT IS WORTH SAYING RATHER THAN
//        ROUNDING.** Without the tab id, `?tab=units` resolves to no tab at
//        all, so the BODY does not render either — the two halves are not
//        fully independent from this direction. Stage 2 is the clean one and
//        is what proves the table cases read the body; stage 3 proves the
//        strip cases read the door. Claiming a tidy 2-and-11 split would have
//        been a nicer sentence and a false one.
//
//        The GREEN run, in the same harness: Tests 15 passed (15).
// exceptions: E4 the fixture seeds the query cache rather than the network, as
//   every S21 tab test in this module does — what is being asserted is the
//   RENDER, and a fetch would make these cases a test of `msw` · E4 `Owed` is
//   asserted only for its vacant sentence and its absence of `0.00`; the money
//   FORMAT is `MoneyCell`'s own suite and is not re-tested here
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
