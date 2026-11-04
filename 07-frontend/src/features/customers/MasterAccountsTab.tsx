// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 wave F — remedy `R7` / commitment `ACC-S17`:
//           **the Accounts tab on a master account's detail screen.** Drawing:
//           `05-prototype/02 Accounts Menu Blueprint.pdf` pages 189–192, pinned
//           at commit `033981d4f`, sha256 `c8d596bb505f5020ce4b9474…`, read as
//           IMAGES and transcribed into
//           `04-docs/05-modules/03-customers/08-screen-layouts.md` §R7.
//           Screens: S21 (the account detail), tab 2 of 13 on a master
// Story:    US-CUS-008 (the S21 tab strip is URL state — BR-SHL-011)
// Rules:    BR-CUS-1048 (THIS TAB — PO 2026-09-12, quoted below) ·
//           BR-CUS-068 (a master account IS an ordinary `accounts` row with
//           `kind='master'`: no `parent_account_id`, no child rows, no
//           rolled-up balance) · BR-CUS-1010 (it hangs off the ADDRESS —
//           `premises_id` set, `unit_id` null) · BR-CUS-171 (a master's
//           children are DERIVED from the premises and stored nowhere) ·
//           BR-CUS-1046 (a list opens in CREATION order, newest first) ·
//           BR-CUS-034 (customers keeps no copy of another module's row) ·
//           BR-CUS-055 (a status label is the TENANT's, `status_name`) ·
//           BR-SHL-010 (an undeclared capability does not render) ·
//           BR-SHL-011 (the one URL/request grammar) · B14 rule 12 (the
//           toolbar's grammar — a dimension is a FILTER CHIP) · B14 rule 15
//           (row actions are icons with tooltips) · B14 rule 20 (one table
//           type) · B14 rule 21 (Tailwind utilities — this file adds NO class
//           to any stylesheet and is registered in `styles/route-b-migrated.txt`) ·
//           B14 rule 31 (no database id is ever a visible value) ·
//           B14 rule 32 (one sentence per section; a stated absence is a
//           `<details>` CLOSED by default) · B14 rule 33 (on-screen text is
//           capped by what it is for — RATIONALE is zero words on screen) ·
//           B14 rule 39 (spacing from `--space-N`; 16px between BLOCKS)
// Tests:    src/features/customers/MasterAccountsTab.test.tsx
//           06-backend/tests/test_cr094_r7_master_accounts_tab.py
// ───────────────────────────────────────────────────────
//
// ── THE RULING, VERBATIM, BECAUSE THE SECOND SENTENCE IS THE SHAPE ─────────
//
// PO 2026-09-12: *"if the account is of master account, then after the overview
// tab, it should show the accounts that are connected to that master account"*,
// and, confirming the walk when it was put back to them: *"this is correct -
// you can see the premises -> units -> regular accounts assocaited with it"*.
// The blueprint's own version, from the same ruling: *"change the premises tab
// to accounts tab. And in that, show only one table with all the accounts that
// are associated with this master account and with their account status."*
//
// **ONE TABLE. That is the PO's own word and it is why this file is short.**
//
// ── WHAT "CONNECTED" MEANS, AND WHY THE TAB SAYS SO RATHER THAN IMPLYING IT ─
//
// It is BY ADDRESS. `BR-CUS-068`: a master account is an ordinary account row
// with its kind set to master; the payer is the premises' owner or manager.
// **There is no `parent_account_id`, there are no child accounts, and there is
// no rolled-up balance.** So the accounts on this tab are the accounts at the
// same address — which is what a clerk ringing about a building actually needs
// — and a tenant's account is its own, as is its money.
//
// ⚠ **NOTHING NEW IS DERIVED HERE AND NO NEW ENDPOINT IS ADDED.** The walk the
// PO confirmed (premises → units → the regular accounts on those units) is
// ALREADY the server's: `selectors.sub_accounts_for_master` is `BR-CUS-171`'s
// own read and `selectors.premises_scope_for_account` groups it by unit. What
// this tab asks for is the plainer question that answers the drawing exactly —
// `GET /accounts?f.premises_id=` — because the drawing puts the MASTER in the
// list too, and `sub_accounts_for_master` deliberately excludes it (*"a
// landlord is not their own sub-account"*). `f.premises_id` is `CR-056` W1's
// filter, migration 0037 backfilled the column onto every existing row, and the
// paging, the search and the status filter are therefore all the SERVER's
// (`NFR-3` — no unpaginated list anywhere).
//
// ── THE THREE THINGS THE DRAWING ASKS FOR THAT ARE NOT THE DEFAULT ─────────
//
//   1 · **The master is IN the list, marked as the one you are on.** It is an
//       ordinary account row, so leaving it out would be the odd choice. It
//       carries no `Open` action, because that action would reload this page.
//   2 · **Its UNIT cell reads `Common areas ×2`**, not a unit label — a master
//       names no unit at all. The count is `covered_units`, served on the
//       account detail from `covered_unit_ids(account)`: this account's own
//       OPEN service agreements, which is what billing prices. What those units
//       add up to belongs on the **Bills** tab and is deliberately not here.
//   3 · **There is NO total under the balance column.** The blueprint states
//       the reason and this file states it once: on its own worked building the
//       six rows sum to $810.95, of which $69.60 is the owner's own and $741.35
//       is owed by three unrelated tenants. A figure like that, printed where an
//       owner can see it, invites exactly the wrong conclusion. `DataTable` has
//       no footer total, so the absence costs nothing — it is recorded here so
//       that nobody adds one later thinking it was an oversight.
//
// ── WHERE THIS DEPARTS FROM THE DRAWING, STATED RATHER THAN ABSORBED ───────
//
//   * **The drawn `All | Active | Needing attention | Closed` SEGMENT STRIP is
//     a FILTER CHIP here.** B14 rule 12 fixes the toolbar's grammar for every
//     list in the product, and `AccountsListPage` already took this exact
//     decision for the same drawing's ageing segments. The BEHAVIOUR the
//     drawing asks for is intact — *"the toolbar filters on it, which is the
//     point of the tab"* — and `Needing attention` is not offered because it is
//     not a status: it is two of them, and the server publishes no such filter.
//     Inventing one client-side would break `NFR-3`'s server paging.
//   * **The five KPI tiles drawn above the table are NOT built here**
//     (`BALANCE · ACCOUNTS HERE · ACTIVE · NEEDING ATTENTION · UNITS WITH NO
//     ACCOUNT`). That strip is `AccountMetricColumns`, which this page renders
//     ONCE below the tab bar for EVERY tab — so a master-only tile set is a
//     change to the account header on all thirteen tabs, not a change to this
//     tab. It is a second capability with a second blast radius; REPORTED as
//     `DEF-CUS-5105` rather than half-built inside a tab body.
//   * **The two explainer boxes the drawing prints under the table are a
//     CLOSED disclosure.** B14 rule 33 makes rationale zero words on screen and
//     rule 32 makes a stated absence closed by default. Nothing is deleted: the
//     address relationship and the missing total are both still said, and cost
//     a clerk nothing to skip. The `CommonAreasTab` precedent is identical and
//     is the one the PO has already walked.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { ACCOUNT_KIND_MASTER, getAccounts } from "@/api/endpoints";
import type { AccountDetail, AccountRow } from "@/api/endpoints";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { Disclosure } from "@/components/Disclosure";
import { FilterBar } from "@/components/FilterBar";
import { EyeIcon } from "@/components/icons";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { RowActionLink, RowActions } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { Note } from "@/components/TextBits";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  ACCOUNT_SEED_STATUSES,
  accountDetailPath,
  accountStatusLabel,
  accountStatusTone,
  Dash,
} from "./customersShared";

// ── Pure pieces (provable without a browser or a network) ──────────────────

/**
 * The tab's own table state. **LOCAL, not URL-backed**, and for the reason
 * `PAYMENTS_TAB_STATE` already records one screen up: S21 spends its query
 * string on `?tab=` (IS-4's deep link), and serialising a second table's
 * sort/page/filters into the same URL would make an account deep link carry a
 * page number for somebody else's building.
 *
 * ⚠ **THE SORT IS THE SERVER'S OWN DEFAULT, `created` DESCENDING
 * (`BR-CUS-1046`).** A tab that opened on a different order from the register
 * one click away would be two answers to *which account is newest*. `created`
 * is a declared server sort and deliberately NOT a column here — nothing on
 * the drawing offers to sort by it, and `SINCE` is the account's opening date,
 * which is a different fact from the row's creation order.
 */
export const MASTER_ACCOUNTS_STATE: TableRequestState = {
  q: "",
  sort: "created",
  dir: "desc",
  page: 1,
  per: DEFAULT_PAGE_SIZE,
  filters: {},
};

/**
 * The query key. **The premises is IN it**, so two buildings can never read one
 * another's page out of the cache, and so does the whole request state, because
 * the paging and the search are the server's.
 */
export const masterAccountsQueryKey = (premisesId: string, state: TableRequestState) =>
  [
    "accounts",
    "at-address",
    premisesId,
    state.q,
    state.sort,
    state.dir,
    state.page,
    state.per,
    state.filters.status ?? "",
  ] as const;

/**
 * Is this row the account whose screen we are on?
 *
 * A tiny function on purpose: it is asked by two cells (the identity marker and
 * the row action), and two inline comparisons are two places for one fact to be
 * wrong — the master would then be linkable in one cell and marked in the other.
 */
export function isTheAccountYouAreOn(row: AccountRow, detail: AccountDetail): boolean {
  return String(row.id) === String(detail.id);
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface MasterAccountsTabProps {
  detail: AccountDetail;
  client?: ApiClient;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}

export function MasterAccountsTab(props: MasterAccountsTabProps) {
  const { detail, t, timeZone, dateFormat } = props;
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  const [state, setState] = useState<TableRequestState>(MASTER_ACCOUNTS_STATE);

  // ⚠ **`premises_id` IS NULLABLE AND `null` IS A REAL STATE, NOT AN ERROR.**
  // Migration 0037 backfilled the column onto every row it could resolve; an
  // account whose unit the metering seam cannot answer for has no address, so
  // there is no building to list. The query is DISABLED rather than sent with
  // an empty filter, which the server would read as a filter on the empty
  // string — a different question (BR-SHL-011).
  const premisesId = detail.premises_id ?? "";
  const listQuery = useQuery({
    queryKey: masterAccountsQueryKey(premisesId, state),
    queryFn: () =>
      getAccounts(
        {
          q: state.q,
          sort: state.sort,
          dir: state.dir,
          page: state.page,
          per: state.per,
          filters: { premises_id: premisesId, ...state.filters },
        },
        client,
      ),
    enabled: premisesId !== "",
    retry: false,
  });
  const rows = listQuery.data?.results ?? [];

  const config: TableConfig<AccountRow> = {
    // Its OWN suffix, so this tab's column set is not the S17 register's
    // (`tableTypes.screenId`'s own `SET-05` / `SET-05.cycles` precedent).
    screenId: "S21.accounts",
    getRowId: (row) => row.id,
    // The drawing's own prompt: *"Search by account, occupant or unit"*. The
    // server matches account #, customer #, contact name, service address and
    // meter # (`BR-CUS-053` as amended), so every term named here is answered.
    searchFields: ["account_no", "name", "unit_label"],
    searchPlaceholder: "customers.account.accounts.searchPlaceholder",
    defaultSort: { sort: MASTER_ACCOUNTS_STATE.sort, dir: MASTER_ACCOUNTS_STATE.dir },
    // *"Status is on every row … and the toolbar filters on it — which is the
    // point of the tab: one of these six is in collections and one is on a
    // vacation hold, and neither is visible from anywhere else in the
    // building."* ONE filter, because the drawing offers one dimension.
    filters: [
      {
        name: "status",
        label: t("customers.accounts.filter.status"),
        options: ACCOUNT_SEED_STATUSES.map((code) => ({
          value: code,
          label: t(`customers.accounts.status.${code}`),
        })),
      },
    ],
    // ⚠ **FIVE OF THESE EIGHT HEADINGS REUSE AN EXISTING CATALOGUE KEY RATHER
    // THAN A NEW ONE, AND THAT IS THE PO's STANDING INSTRUCTION** (*"dont
    // create duplcate code"*). Measured before writing them: `Account`,
    // `Status` and `Balance` already exist on this module's own register
    // (`customers.accounts.col.*`) with byte-identical values in all eleven
    // catalogues, and `Unit` and `Occupant` are METERING's facts and exist
    // under its keys — the same cross-module reuse `CommonAreasTab` makes for
    // `metering.units.col.meters`. Minting a second key for one word is also
    // how one column ends up renamed on one screen only (B14 rule 34's shape).
    // `Kind`, `Since` and `Actions` are new because no key holds them for an
    // account row.
    columns: [
      {
        key: "account_no",
        label: t("customers.accounts.col.account"),
        identity: true, // BR-SHL-013: the identity column can never be hidden
        // ⚠ **THE ROW YOU ARE ON IS NOT A LINK.** A link back to this page
        // reads as a way somewhere and goes nowhere — hard-won law 2's mirror,
        // a live-looking control over nothing. It is marked instead, which is
        // what the drawing does.
        cell: (row) =>
          isTheAccountYouAreOn(row, detail) ? (
            <>
              <span className="cus-id">{row.account_no ?? t("customers.account.noNumber")}</span>{" "}
              <StatusPill tone="info">{t("customers.account.accounts.thisAccount")}</StatusPill>
            </>
          ) : (
            <InlineLinkTo className="cus-id" to={tenantPath(accountDetailPath(row.id))}>
              {row.account_no ?? t("customers.account.noNumber")}
            </InlineLinkTo>
          ),
      },
      {
        key: "unit_label",
        label: t("metering.units.col.unit"),
        // Three states, and the middle one is the whole reason this column is
        // interesting: a MASTER names no unit and covers several, so its cell
        // counts what its own open agreements reach. An ordinary account always
        // names one (`BR-CUS-1012`), so the dash is reached only by a master
        // whose coverage could not be read.
        cell: (row) =>
          row.kind === ACCOUNT_KIND_MASTER ? (
            isTheAccountYouAreOn(row, detail) && detail.covered_units != null ? (
              <span>
                {t("customers.account.accounts.commonAreas", { count: detail.covered_units })}
              </span>
            ) : (
              <Dash />
            )
          ) : row.unit_label !== null ? (
            <span>{row.unit_label}</span>
          ) : (
            <Dash />
          ),
      },
      {
        key: "name",
        label: t("metering.units.col.occupant"),
        // BR-CUS-054's entity is served, but this is the primary CONTACT's name
        // — the same value the register's NAME column shows, so one building
        // cannot name a person two ways on two screens.
        cell: (row) =>
          row.name !== null ? (
            <span>{row.name}</span>
          ) : (
            <Dash>{t("customers.accounts.noName")}</Dash>
          ),
      },
      {
        key: "kind",
        label: t("customers.account.accounts.col.kind"),
        // The SERVER's own column, rendered through the same two keys the
        // register and the premises surfaces use — never a word written here
        // (§12 of the UI skill: never hand-type a list).
        cell: (row) => <span>{t(`customers.accounts.kind.${row.kind}`)}</span>,
      },
      {
        key: "status",
        label: t("customers.accounts.col.status"),
        // BR-CUS-055: the label is the TENANT's (`status_name`); the tone keys
        // off the seeded CODE and falls back to the behaviour class, so a
        // tenant-added status still renders.
        cell: (row) => (
          <StatusPill tone={accountStatusTone(row)}>{accountStatusLabel(row, t)}</StatusPill>
        ),
      },
      {
        key: "opened_at",
        label: t("customers.account.accounts.col.since"),
        cell: (row) =>
          row.opened_at !== null ? (
            <DateCell value={row.opened_at} timeZone={timeZone} dateFormat={dateFormat} />
          ) : (
            <Dash />
          ),
      },
      {
        key: "balance",
        label: t("customers.accounts.col.balance"),
        // `numeric` right-aligns it and gives it tabular numerals, so a column
        // of figures reads as a column. ⚠ **AND THERE IS NO FOOT** — see the
        // file header for the reason and the worked figure.
        numeric: true,
        // CLAUDE.md hard rule 2: the decimal STRING and its CHAR(3) travel
        // together from the database to the pixel; nothing here parses or
        // rounds one. A null means the books could not be asked, which is a
        // different claim from $0.00.
        cell: (row) =>
          row.balance === null ? (
            <Dash />
          ) : (
            <MoneyCell amount={row.balance} currency={row.balance_currency ?? row.currency} />
          ),
      },
      {
        key: "actions",
        label: t("customers.account.accounts.col.actions"),
        // B14 rule 15: row actions are ICONS with tooltips, never text links,
        // and the drawing's own `↗ Open` is the one action it draws.
        cell: (row) =>
          isTheAccountYouAreOn(row, detail) ? (
            <Dash />
          ) : (
            <RowActions>
              <RowActionLink
                icon={<EyeIcon />}
                label={t("customers.account.accounts.action.open")}
                to={tenantPath(accountDetailPath(row.id))}
              />
            </RowActions>
          ),
      },
    ],
  };

  return (
    <Panel as="section">
      {/* ⚠ **NO `<h3>` AND NO EXPLAINER PARAGRAPH.** The tab strip above
          already says *Accounts*, and the PO's own instruction for this tab is
          *"show only one table"*. B14 rule 32's description budget says the
          same thing one level up. */}
      <DataTable<AccountRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        // ⚠ **`0` AND NOT `null` WHEN THERE IS NO ADDRESS TO ASK ABOUT**, and
        // that is not cosmetic: `DataTable` draws its whole-list empty state on
        // `totalRows === 0` with no search or filter applied, and `null` means
        // *the total has not arrived yet*. A disabled query never answers, so a
        // null here would leave the tab drawing a header over no rows forever
        // — a screen with no state for its commonest absence.
        totalRows={premisesId === "" ? 0 : (listQuery.data?.count ?? null)}
        loading={premisesId !== "" && listQuery.isPending}
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
        // ⚠ **NO CTA, AND THAT IS `DEF-MET-4764`'s OWN CLAUSE.** A tenant's
        // account is opened through the move-in flow at the UNIT, not from the
        // owner's screen, so there is nothing to offer here and a no-op handler
        // would wire a live button to nothing.
        empty={{
          title:
            premisesId === ""
              ? t("customers.account.accounts.noAddressTitle")
              : t("customers.account.accounts.emptyTitle"),
          helper:
            premisesId === ""
              ? t("customers.account.accounts.noAddressHelper")
              : t("customers.account.accounts.emptyHelper"),
        }}
      />

      {/* B14 rule 32 — a stated absence is CLOSED by default, and rule 39's
          16px between BLOCKS. Nothing the drawing says is deleted: both of its
          explainer boxes are here, cited, and cost a clerk nothing to skip. */}
      <div className="mt-4">
        <Disclosure title={t("customers.account.accounts.notes")}>
          <Note>{t("customers.account.accounts.byAddress")}</Note>
          <Note>{t("customers.account.accounts.noTotal")}</Note>
        </Disclosure>
      </div>
    </Panel>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-094-BRC01 step 2 wave F (R7 / ACC-S17) — the blueprint pages
//         189–192 at commit 033981d4f, read as images
// generated: 2026-09-12 by the CR-094-BRC01 wave F lane
// gates: PROVED RED FIRST in the harness that runs it —
//        `npx vitest run src/features/customers/MasterAccountsTab.test.tsx`
//        answered `Error: Failed to load url ./MasterAccountsTab … Does the
//        file exist?` before this file existed, and the tab-strip cases were
//        red against the real page with the component present but unmounted
// exceptions: E3 the drawn `All | Active | Needing attention | Closed` SEGMENT
//   STRIP renders as ONE filter chip (B14 rule 12 — the toolbar's grammar is
//   ratified for every list in the product, and `AccountsListPage` took the
//   same decision for the same drawing's ageing segments). `Needing attention`
//   is NOT offered: it is two statuses rather than one, the server publishes no
//   such filter, and deriving it client-side would break `NFR-3`'s server
//   paging · E3 the FIVE KPI TILES drawn above the table are not built —
//   `AccountMetricColumns` renders once for every tab, so a master-only tile
//   set changes the account header on all thirteen tabs rather than this tab
//   body; REPORTED as `DEF-CUS-5105` · E3 the drawing's `Columns ▾` and
//   `Export` sit in `DataTable`'s own toolbar and its own absence respectively:
//   `/exports` registers no `accounts` resource, so BR-SHL-010 keeps that one
//   unrendered exactly as the register does · E3 the two explainer boxes are a
//   CLOSED `<details>` rather than prose over the table (B14 rules 32 + 33) ·
//   E4 the SINCE column is `opened_at`, which is the account's opening date;
//   the row's creation order is what the list is SORTED by (`BR-CUS-1046`) and
//   the two are deliberately different facts · E4 no `sortable` column: the
//   server's `ACCOUNT_SORTS` does not include `unit_label`, `kind` or
//   `opened_at`, and a sort control over an ordering the request cannot ask for
//   is the refusal `ageing` and `last_bill` already carry on the register
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
