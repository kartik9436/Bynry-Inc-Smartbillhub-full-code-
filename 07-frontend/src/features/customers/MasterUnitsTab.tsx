// ── Trace ──────────────────────────────────────────────
// Change:   `BR-CUS-1094` (PO 2026-09-23) — **the Units tab on a master
//           account's detail screen.** PO verbatim: *"show all units with its
//           status what wil be billed to master account - can we do that?"*
//           Drawing: `05-prototype/Premises & Units Blueprint 2.pdf` pages
//           23–25, read as IMAGES at scale 2.0 through `10-scripts/pdf/
//           pdf_render.py` (B14 rule 42). ⚠ **THAT DRAWING IS THE PROPERTY'S
//           Units tab, not this one** — see the note below.
//           Screens: S21 (the account detail), tab 3 of 14 on a master
// Story:    US-CUS-008 (the S21 tab strip is URL state — BR-SHL-011)
// Rules:    BR-CUS-1094 (THIS TAB's subject — PO 2026-09-23, quoted below) ·
//           BR-CUS-170 (the owner's bill carries every unit nobody else pays
//           for) · BR-CUS-1040 (no per-unit PRICE outside a bill run) ·
//           BR-CUS-1048 (the Accounts tab — this tab is its other half) ·
//           BR-CUS-068 (a master account IS an ordinary `accounts` row) ·
//           BR-CUS-1010 (it hangs off the ADDRESS) · BR-MET-036 (occupancy is
//           DERIVED — `units` has no such column) · BR-MET-101 (a common area
//           is never *occupied*) · BR-SHL-010 (an undeclared capability does
//           not render) · BR-SHL-011 (the one URL/request grammar) ·
//           NFR-3 (server paging) · NFR-5 (no cap anywhere) ·
//           B14 rule 12 (a dimension is a FILTER CHIP) · B14 rule 20 (one
//           table type) · B14 rule 21 (Tailwind utilities — this file adds NO
//           class to any stylesheet and is registered in
//           `styles/route-b-migrated.txt`) · B14 rule 31 (no database id is
//           ever a visible value) · B14 rule 32 (description budget; a stated
//           absence is a `<details>` CLOSED by default) · B14 rule 33
//           (on-screen text capped by what it is FOR — RATIONALE is zero words
//           on screen) · B14 rule 39 (16px between BLOCKS) · B14 rule 43 (a
//           piece of UI is built as a COMPONENT)
// Tests:    src/features/customers/MasterUnitsTab.test.tsx
//           06-backend/tests/test_br_cus_1094_master_units_tab.py
// ───────────────────────────────────────────────────────
//
// ── THE RULING, VERBATIM, BECAUSE ITS SECOND HALF IS A PROHIBITION ─────────
//
// PO 2026-09-23: *"if we have 10 units on premsies, and 5 are vancant and 5 are
// occpied by tenants. then 5 teannt bill will go to them to their regualr
// account, but for 5 vacant units - bill will be generated against master
// account. also every month this is dynamic siaution and hence unit and account
// valid for billing are decied at the time of billing start only"*.
//
// **NOTHING ON THIS SCREEN IS STORED.** `BR-CUS-1094`'s own words: *"No column
// may cache which units a master account pays for, because a cached answer is
// wrong the first time a tenant moves in and nothing would go red."* The server
// derives every answer at read time from the two functions `apps/billing/gather`
// resolves through the seam, so what a clerk sees here is what a bill run
// starting NOW would decide — and the backend's `tc5` moves a tenant in between
// two reads to prove it.
//
// ── WHY THE PO ASKED FOR THIS BEFORE THE BILLING CHANGE ───────────────────
//
// `BR-CUS-1094` is ruled and the vacant→master routing it re-states was already
// built (`BR-CUS-170`, PO 2026-08-27, live in `gather._unbilled_unit_tariffs`).
// **This tab is how that routing gets CHECKED.** Without it the first proof
// that vacant units bill correctly would be a live bill run.
//
// ⚠ **IT IS THE OTHER HALF OF `MasterAccountsTab`.** That tab lists every
// OCCUPYING account at the address, so a vacant unit — which has no account at
// all — appears on no list anywhere in the product. That is the gap.
//
// ── THE DRAWING, AND WHAT IT DOES AND DOES NOT DECIDE ─────────────────────
//
// ⚠ **NO BLUEPRINT PAGE DRAWS THIS TAB.** Nine PDFs were checked with
// `git -c core.quotePath=false ls-tree -r --name-only <ref> | grep -i 'pdf$'`
// — the flag is load-bearing, `DEF-GOV-6236` — and none carries a Units tab on
// an ACCOUNT. What pages 23–25 of the Premises & Units blueprint draw is the
// PROPERTY's Units tab, which asks *what is inside this building, and is any of
// it empty?* — the same building, from the other side.
//
// **So its design language is followed exactly and its subject is not**, and
// four of its own rulings land here unchanged:
//
//   1 · **The label LEADS and the unit number sits beneath it**, quiet, in one
//       cell. The blueprint corrects an earlier draft of itself in writing on
//       this point (p23, p25): `unit_no` is *"the number from the tenant's own
//       series — a printed reference, as legitimate as a property number"*, so
//       B14 rule 31 does not reach it.
//   2 · **A vacant row NEVER draws a dash in the occupant cell** — *"a dash on
//       that row reads as `nothing is billed`, which is the opposite of
//       true"*. `OccupantCell` is that sentence and it is IMPORTED, not copied.
//   3 · **Occupant, not occupancy** — *"a name and its account, not a state
//       word. The state is in the status pill where it belongs."*
//   4 · **The footer count is the size of the job** — *"Filtered to vacant: the
//       footer count is the size of the job."*
//
// ── THE ONE COLUMN THIS SCREEN ADDS, AND WHY IT IS NOT ON THAT DRAWING ────
//
// `Billed to`. On the PROPERTY's tab *"bill to the owner"* names somebody who
// is not on screen; on the OWNER's own screen they are the subject, and the
// question the PO asked is precisely *which of these is mine*. It is a PAYER
// and never a price — `BR-CUS-1040` settles that: *"NO PRICE IS STATED — a
// single what the empty unit will cost figure is the rating engine's and
// nothing publishes a per-unit standing charge outside a bill run."*
//
// ── WHERE THIS DEPARTS FROM THE DRAWING, STATED RATHER THAN ABSORBED ──────
//
//   * **The four KPI tiles drawn above the table are NOT built here.**
//     `AccountMetricColumns` renders once below the tab bar for EVERY tab on
//     this page, so a Units-only tile strip is a change to the account header
//     on all fourteen tabs — a second capability with a second blast radius,
//     already REPORTED as `DEF-CUS-5105`. The counts ride in the footer line
//     instead, which is where the drawing also puts them.
//   * **`+ New unit` is absent.** It is the PROPERTY page's primary action and
//     it asks for a building; an owner's account screen is not where a unit is
//     created, and a button that navigated away to find its own subject would
//     be a door pointing sideways.
//   * **`Owed` is kept**, although it is money on an account screen that does
//     not total anything. The blueprint's reason is the reason here: *"a
//     landlord's question is answered by looking rather than by opening four
//     units"*. There is **no column total**, for `MasterAccountsTab`'s own
//     recorded reason — a figure summing one owner's arrears with three
//     unrelated tenants' invites exactly the wrong conclusion.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getMasterUnits,
  UNIT_BASIS_VACANT,
  UNIT_NOT_CHARGED_NO_CONNECTION,
  UNIT_NOT_CHARGED_NO_PLAN,
  UNIT_PAYER_NOBODY,
  UNIT_PAYER_TENANT,
  UNIT_PAYER_THIS_ACCOUNT,
} from "@/api/endpoints";
import type { AccountDetail, MasterUnitRow, UnitRow } from "@/api/endpoints";
import { DataTable } from "@/components/DataTable";
import { Disclosure } from "@/components/Disclosure";
import { FilterBar } from "@/components/FilterBar";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Note } from "@/components/TextBits";
import { MetersCell, unitDetailPath, unitStatusTone } from "@/features/metering/meteringShared";
import { OccupantCell } from "@/features/metering/PremisesDetailPage";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { Dash } from "./customersShared";

// ── Pure pieces (provable without a browser or a network) ──────────────────

/**
 * The tab's own table state. **LOCAL, not URL-backed**, for the reason
 * `MASTER_ACCOUNTS_STATE` already records one tab across: S21 spends its query
 * string on `?tab=` (IS-4's deep link), and serialising a second table's
 * sort/page/filters into the same URL would make an account deep link carry a
 * page number for somebody else's building.
 *
 * ⚠ **THE SORT IS THE BLUEPRINT'S OWN DEFAULT — the LABEL, ascending.** *"the
 * label leads and the unit number sits under it … what changes is which of the
 * two the eye meets first, and what the table sorts by."*
 */
export const MASTER_UNITS_STATE: TableRequestState = {
  q: "",
  sort: "label",
  dir: "asc",
  page: 1,
  per: DEFAULT_PAGE_SIZE,
  filters: {},
};

/**
 * The query key. **The ACCOUNT is in it**, so two owners can never read one
 * another's building out of the cache, and so is the whole request state,
 * because the paging, the search and the filters are the server's.
 */
export const masterUnitsQueryKey = (accountId: string, state: TableRequestState) =>
  [
    "accounts",
    "units",
    accountId,
    state.q,
    state.sort,
    state.dir,
    state.page,
    state.per,
    state.filters.billed_to ?? "",
    state.filters.occupancy ?? "",
  ] as const;

/**
 * `OccupantCell` takes metering's own `UnitRow`, and this row is customers'.
 * **The four fields it reads are the same four facts under the same four
 * names**, which is why the server publishes `account_no` rather than a second
 * spelling of it — one fact with two names on one row is `DEF-127`'s shape.
 *
 * ⚠ **IT IS A NARROWING AND NOT A CAST OF CONVENIENCE.** Only the fields
 * `OccupantCell` actually branches on are named here, so if it ever starts
 * reading a fifth, this stops compiling instead of rendering something wrong.
 */
type OccupantFacts = Pick<UnitRow, "is_common_area" | "occupancy" | "occupant" | "account_no">;

export function occupantFacts(row: MasterUnitRow): OccupantFacts {
  return {
    is_common_area: row.is_common_area,
    occupancy: row.occupancy,
    occupant: row.occupant ?? null,
    account_no: row.account_no ?? null,
  };
}

/**
 * **WHO GETS THE BILL FOR THIS UNIT — the one thing this tab exists to say.**
 *
 * B14 rule 43: it is a COMPONENT rather than 30 lines inside a column
 * definition, because *standalone code inside a page is not reuse* — and the
 * Bills tab and the pre-billing decision list will each want this sentence.
 *
 * ⚠ **FOUR ANSWERS, AND COLLAPSING ANY TWO WOULD BE A LIE ABOUT MONEY:**
 *
 *   · **a tenant's account number** — the unit is occupied and the bill goes
 *     where it always went (`BR-CUS-1094`: *"The tenant half does not move"*);
 *   · **this account** — the unit is vacant, or it is a common area this
 *     account's own agreement reaches. The row says WHICH, quietly, because a
 *     clerk acts on them differently: an agreement is a thing somebody wrote,
 *     a vacancy stops applying the day a tenant moves in;
 *   · **this account, but nothing is charged** — `gather._unbilled_unit_tariffs`
 *     skips a coverage entry outright when the unit has no plan, and raises no
 *     line for one with no service point. A row saying only *billed here* would
 *     be a promise the run does not keep;
 *   · **nobody** — the unit is vacant and reaches no payer at all. That is
 *     `BR-CUS-1094`'s stated refusal and the one row on this tab a clerk must
 *     act on: *"'no lines because nothing falls to it' and 'no lines although
 *     the premises HAS an unoccupied unit' are different facts and only one of
 *     them is good news."*
 *
 * ⚠ **THERE IS NO DASH IN THIS COLUMN, EVER.** The blueprint's own rule for the
 * cell next door, and the reason transfers exactly: *"a dash on that row reads
 * as `nothing is billed`, which is the opposite of true."*
 *
 * ⚠ **AND NO RATIONALE IS PRINTED.** B14 rule 33 puts *why the product works
 * this way* at zero words on screen. The sentences below are FACTS about this
 * unit — four words each — and the reasoning lives in this docstring and in
 * `BR-CUS-1094`.
 */
export function BilledToCell(props: { row: MasterUnitRow; t: Translator }) {
  const { row, t } = props;
  if (row.payer === UNIT_PAYER_TENANT) {
    return (
      <span className="block" data-billed-to="tenant">
        {row.account_no ?? t("customers.account.units.billed.tenant")}
      </span>
    );
  }
  if (row.payer === UNIT_PAYER_THIS_ACCOUNT) {
    return (
      <span className="block" data-billed-to="this-account">
        <StatusPill tone="info">{t("customers.account.accounts.thisAccount")}</StatusPill>
        <span className="block text-sm italic text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          {row.not_charged === UNIT_NOT_CHARGED_NO_PLAN
            ? t("customers.account.units.notCharged.noPlan")
            : row.not_charged === UNIT_NOT_CHARGED_NO_CONNECTION
              ? t("customers.account.units.notCharged.noConnection")
              : row.payer_basis === UNIT_BASIS_VACANT
                ? t("customers.account.units.basis.vacant")
                : t("customers.account.units.basis.agreement")}
        </span>
      </span>
    );
  }
  // `UNIT_PAYER_NOBODY` — and it is drawn in the DANGER tone rather than as an
  // absence, because it is the one row here somebody has to do something about.
  return (
    <span className="block" data-billed-to="nobody">
      <StatusPill tone="danger">{t("customers.account.units.billed.nobody")}</StatusPill>
    </span>
  );
}

/**
 * The unit cell — **one column, not two**, exactly as the blueprint draws it
 * and exactly as the property's own Units tab already renders it.
 *
 * It is written here rather than imported because the property tab's version is
 * inline in a 2,000-line page and takes metering's row type; extracting THAT is
 * a change under two other lanes' hands this week. ⚠ **The duplication is
 * REPORTED rather than absorbed** — `DEF-SHL-6308`, filed with this change.
 */
export function MasterUnitCell(props: { row: MasterUnitRow; t: Translator; to: string }) {
  const { row, t, to } = props;
  return (
    <span className="block">
      <InlineLinkTo to={to}>
        <span className="font-bold">
          {row.label ?? row.unit_no ?? t("metering.units.noNumber")}
        </span>
      </InlineLinkTo>
      {row.is_common_area && (
        <>
          {" "}
          <StatusPill tone="neutral">{t("metering.units.commonArea")}</StatusPill>
        </>
      )}
      {row.unit_no !== null && row.label !== null && (
        <span
          className="block text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]"
          data-unit-no={row.unit_no}
        >
          {row.unit_no}
        </span>
      )}
    </span>
  );
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface MasterUnitsTabProps {
  detail: AccountDetail;
  client?: ApiClient;
  t: Translator;
}

export function MasterUnitsTab(props: MasterUnitsTabProps) {
  const { detail, t } = props;
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const [state, setState] = useState<TableRequestState>(MASTER_UNITS_STATE);

  const accountId = String(detail.id ?? "");
  const listQuery = useQuery({
    queryKey: masterUnitsQueryKey(accountId, state),
    queryFn: () => getMasterUnits(accountId, state, client),
    enabled: accountId !== "",
    retry: false,
    // ⚠ **NOT CACHED ACROSS A VISIT, AND THAT IS `BR-CUS-1094` RATHER THAN A
    // PREFERENCE.** The server refuses to store which units this account pays
    // for; a client holding the answer while a colleague completes a move-in
    // would re-create exactly the staleness the rule forbids, one layer up.
    staleTime: 0,
  });
  const rows = listQuery.data?.results ?? [];
  const counts = listQuery.data?.counts ?? null;

  const config: TableConfig<MasterUnitRow> = {
    // Its OWN suffix, so this tab's column preferences are not the property
    // tab's (`tableTypes.screenId`: two lists sharing an id share one set).
    screenId: "S21.units",
    getRowId: (row) => row.unit_id,
    // The server matches the label, the unit number and the occupying
    // account's number — every term this placeholder names is answered.
    searchFields: ["label", "unit_no", "account_no"],
    searchPlaceholder: "customers.account.units.searchPlaceholder",
    defaultSort: { sort: MASTER_UNITS_STATE.sort, dir: MASTER_UNITS_STATE.dir },
    // B14 rule 12 — a dimension is a FILTER CHIP, never a segment strip. TWO,
    // because the screen answers two questions: *which are empty* and *which
    // are mine*, and they are not the same question — a common area is billed
    // here and is not a vacancy anybody is trying to fill.
    filters: [
      {
        name: "billed_to",
        label: t("customers.account.units.filter.billedTo"),
        options: [
          {
            value: UNIT_PAYER_THIS_ACCOUNT,
            label: t("customers.account.accounts.thisAccount"),
          },
          { value: UNIT_PAYER_TENANT, label: t("customers.account.units.billed.tenant") },
          { value: UNIT_PAYER_NOBODY, label: t("customers.account.units.billed.nobody") },
        ],
      },
      {
        name: "occupancy",
        label: t("metering.units.col.occupancy"),
        options: [
          { value: "occupied", label: t("customers.account.units.occupancy.occupied") },
          { value: "vacant", label: t("metering.units.status.vacant") },
        ],
      },
    ],
    // ⚠ **SIX OF THESE EIGHT HEADINGS REUSE AN EXISTING CATALOGUE KEY**, which
    // is the PO's standing instruction (*"dont create duplcate code"*) and is
    // what keeps one column from being renamed on one screen only (B14 rule
    // 34's shape). `Unit`, `Type`, `Floor`, `Meters`, `Occupant` and `Owed` are
    // METERING's facts and exist under METERING's keys — the same cross-module
    // reuse `MasterAccountsTab` and `CommonAreasTab` already make. `Billed to`
    // is new because no key holds it, and `Status` reuses the units one.
    columns: [
      {
        key: "label",
        label: t("metering.units.col.label"),
        identity: true, // BR-SHL-013: the identity column can never be hidden
        sortable: true,
        cell: (row) => (
          <MasterUnitCell row={row} t={t} to={tenantPath(unitDetailPath(row.unit_id))} />
        ),
      },
      {
        key: "unit_type",
        label: t("metering.units.col.type"),
        cell: (row) =>
          row.unit_type == null ? (
            <Dash />
          ) : (
            <span>
              {t(`metering.units.type.${row.unit_type}`, { defaultValue: row.unit_type })}
            </span>
          ),
      },
      {
        key: "floor_label",
        label: t("metering.units.col.floor"),
        cell: (row) =>
          row.floor_label == null ? (
            <Dash>{t("metering.units.floorNone")}</Dash>
          ) : (
            <span>{row.floor_label}</span>
          ),
      },
      {
        key: "meters",
        label: t("metering.units.col.meters"),
        cell: (row) => <MetersCell meters={row.meters ?? []} t={t} />,
      },
      {
        // The blueprint's own cell, IMPORTED and not copied — so a vacant row's
        // sentence is one sentence in one place and cannot drift between the
        // owner's screen and the building's.
        key: "occupant",
        label: t("metering.units.col.occupant"),
        cell: (row) => <OccupantCell unit={occupantFacts(row) as UnitRow} t={t} />,
      },
      {
        key: "billed_to",
        label: t("customers.account.units.col.billedTo"),
        cell: (row) => <BilledToCell row={row} t={t} />,
      },
      {
        key: "owed",
        // `numeric` right-aligns it with tabular numerals, so a column of
        // figures reads as a column. ⚠ **AND THERE IS NO FOOT** — see the file
        // header; `DataTable` has no footer total, so the absence costs nothing.
        label: t("metering.units.col.owed"),
        numeric: true,
        // CLAUDE.md hard rule 2: the decimal STRING and its CHAR(3) travel
        // together from the database to the pixel; nothing here parses or
        // rounds one. ⚠ **AND A VACANT UNIT IS NEVER `0.00`** — no occupying
        // account means the books were never asked, which is `DEF-138` exactly.
        // Who pays instead is the two cells to the left.
        cell: (row) => {
          const owed = row.owed ?? null;
          if (owed === null) {
            return (
              <Note as="span" title={t("metering.units.owed.notMeasuredWhy")}>
                {t("metering.units.owed.notMeasured")}
              </Note>
            );
          }
          if (owed.balance === null || owed.balance_unavailable.length > 0) {
            return (
              <Note as="span" title={t("metering.units.owed.unreadableWhy")}>
                {t("metering.units.owed.unreadable")}
              </Note>
            );
          }
          return <MoneyCell amount={owed.balance} currency={owed.balance_currency ?? ""} />;
        },
      },
      {
        key: "status",
        label: t("metering.units.col.status"),
        // ONE status vocabulary for the product: metering's own derived value
        // and metering's own tone map, so this tab and the property's cannot
        // colour one unit two ways.
        cell: (row) =>
          row.status == null ? (
            <Dash />
          ) : (
            <StatusPill tone={unitStatusTone(row.status)}>
              {t(`metering.units.status.${row.status}`, { defaultValue: row.status })}
            </StatusPill>
          ),
      },
    ],
  };

  return (
    <Panel as="section">
      {/* ⚠ **NO `<h3>` AND NO EXPLAINER PARAGRAPH** — the tab strip above
          already says *Units*, the blueprint's own note for this table is
          *"Eight columns, one search, no prose"*, and B14 rule 32 caps the
          description budget one level up. */}
      <DataTable<MasterUnitRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        // ⚠ **`0` AND NOT `null` WHEN THERE IS NO ACCOUNT TO ASK ABOUT**, for
        // `MasterAccountsTab`'s own recorded reason: `DataTable` draws its
        // whole-list empty state on `totalRows === 0`, and `null` means *the
        // total has not arrived yet* — a disabled query never answers, so a
        // null would leave a header over no rows forever.
        totalRows={accountId === "" ? 0 : (listQuery.data?.count ?? null)}
        loading={accountId !== "" && listQuery.isPending}
        error={
          listQuery.isError && listQuery.data === undefined
            ? {
                reason: apiErrorText(listQuery.error, t),
                onRetry: () => void listQuery.refetch(),
              }
            : null
        }
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
        }
        // ⚠ **NO CTA.** A unit is created at its BUILDING, so the only honest
        // action here would navigate away to find its own subject — and a
        // no-op handler would wire a live button to nothing (hard-won law 2).
        empty={{
          title: t("customers.account.units.emptyTitle"),
          helper: t("customers.account.units.emptyHelper"),
        }}
      />

      {/* The blueprint's footer line: *"the footer count is the size of the
          job"*. ⚠ **`billed_nobody` IS PRINTED SEPARATELY AND ONLY WHEN IT IS
          NOT ZERO** — `BR-CUS-1094`: *"'no lines because nothing falls to it'
          and 'no lines although the premises HAS an unoccupied unit' are
          different facts and only one of them is good news."* */}
      {counts !== null && counts.units > 0 && (
        <p className="m-0 mt-4 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          {t("customers.account.units.footerCounts", {
            occupied: counts.occupied,
            vacant: counts.vacant,
            billed: counts.billed_here,
          })}
          {counts.billed_nobody > 0 && (
            <>
              {" "}
              <span data-billed-nobody={counts.billed_nobody}>
                {t("customers.account.units.footerNobody", { count: counts.billed_nobody })}
              </span>
            </>
          )}
        </p>
      )}

      {/* B14 rule 32 — a stated absence is CLOSED by default, and rule 39's
          16px between BLOCKS. Nothing is deleted: both facts a clerk might
          otherwise infer wrongly are said, and cost nothing to skip.

          ⚠ **THE TITLE AND THE SECOND NOTE ARE `MasterAccountsTab`'S OWN
          KEYS, REUSED.** They are the same words in the same role on the same
          screen, and the PO's standing instruction is *"dont create duplcate
          code"* — a second key for *About this list* is how one heading ends
          up renamed on one tab only (B14 rule 34's shape). Only the first
          note is new, because only it is about THIS tab.

          ⚠ **`Disclosure` RENDERS ITS BODY ONLY WHEN OPEN**, so nothing
          below this line reaches a clerk — or a static-markup test — until
          somebody opens it. That is what rule 32 asks for, and it is also a
          blind spot: a raw message key in here is invisible to a check that
          greps the rendered page. The keys are asserted directly instead. */}
      <div className="mt-4">
        <Disclosure title={t("customers.account.accounts.notes")}>
          <Note>{t("customers.account.units.decidedAtRun")}</Note>
          <Note>{t("customers.account.accounts.noTotal")}</Note>
        </Disclosure>
      </div>
    </Panel>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: `BR-CUS-1094` (PO 2026-09-23). Drawing: `05-prototype/Premises &
//         Units Blueprint 2.pdf` pages 23–25, read as IMAGES (B14 rule 42) —
//         the PROPERTY's Units tab, whose design language transfers and whose
//         subject does not. **No blueprint page draws this tab.**
// generated: 2026-09-23 by lane MA-UNITS
// gates: PROVED RED FIRST in the harness that runs it —
//        `npx vitest run src/features/customers/MasterUnitsTab.test.tsx`
//        answered `Error: Failed to load url ./MasterUnitsTab … Does the file
//        exist?` before this file existed, and the tab-strip cases were red
//        against the real page with the component present but unmounted.
// exceptions: E3 the FOUR KPI TILES drawn above the property table are not
//   built — `AccountMetricColumns` renders once for every tab on this page, so
//   a Units-only tile set changes the account header on all fourteen tabs;
//   REPORTED as `DEF-CUS-5105`, which already owns that blast radius · E3 the
//   drawn `+ New unit` primary action is absent: a unit is created at its
//   building and this screen is not one · E3 the two explainer notes are a
//   CLOSED `<details>` rather than prose over the table (B14 rules 32 + 33) ·
//   E4 only `label` is `sortable`: the server's `MASTER_UNIT_SORTS` holds
//   `label` and `unit_no`, and `unit_no` is drawn INSIDE the label cell rather
//   than as its own column, so a sort control for it would head a column that
//   is not there · E4 `MasterUnitCell` duplicates the property tab's inline
//   unit cell rather than importing it, because that one is inline in a
//   2,000-line page under two other lanes this week; REPORTED as
//   `DEF-SHL-6308` rather than extracted under them · E4 `occupancy_statuses`
//   — the five seeded values whose own docstring calls them BILLING BEHAVIOUR
//   — are NOT rendered here and cannot be: **no table in this product carries
//   a foreign key to that list**, so no unit declares one. `DEF-BIL-6296` owns
//   that; this screen states what the RUN will do and does not pretend a
//   reference list drives it
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
