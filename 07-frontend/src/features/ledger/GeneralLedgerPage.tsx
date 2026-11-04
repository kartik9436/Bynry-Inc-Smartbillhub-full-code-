// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-008 (S56 trial balance — the GL table and its BALANCED
//           footer) · US-LED-013 (the S56 journal list — drafts, posted
//           entries, reversals and their links, all first-class visible)
//           Screens: S56 (AppShell sidebar → Finance → General ledger)
// Rules:    BR-LED-009 (trial balance: period filter, dimension expansion,
//           export) · BR-LED-007 (ANY drift is a red flag, never a silent fix) ·
//           BR-LED-012 (the journal list carries the IS-5 capability row) ·
//           BR-LED-003 (a posted entry is immutable — this screen offers no
//           edit) · BR-REP-001 (every money group labels its date basis) ·
//           BR-REP-002 (read-models over journal-line dimensions, never a
//           side-maintained number and never a client-side one) · BR-REP-006
//           (filters enumerate the LIVE vocabulary) · BR-SHL-011 (the URL
//           grammar) · BR-SHL-020 (plain-language failure) · BR-SHL-023 (one
//           money formatting path) · BR-SHL-025 (a control this deployment
//           cannot honour renders disabled WITH its reason) · BR-SHL-044 (one
//           page header)
// ───────────────────────────────────────────────────────
// S56 — General ledger: the trial balance an auditor asks for first.
//
// `GET /ledger/trial-balance` has been SERVED since 2026-08-11 and had no
// caller until now. `apps/ledger/reporting.trial_balance` foots LE-1 at
// **598.69 = 598.69** over the whole book and **553.69 = 553.69** over the July
// window, and until this file no human being could read either.
//
// ══════════════════════════════════════════════════════════════════════════
// THE FOOTER IS THE SCREEN. IT IS NEVER COMPUTED HERE.
// ══════════════════════════════════════════════════════════════════════════
// `total_debit`, `total_credit`, `difference` and `balanced` are all SERVED.
// This file sums nothing, compares nothing and rounds nothing — there is not one
// arithmetic operator on a money value anywhere in it (CLAUDE.md rule 2,
// BR-SHL-023). US-LED-008 TC-5 is explicit that *"no client-side 'rebalancing'
// exists"*, and a screen that added its own column totals would be a second
// derivation that agrees with the server right up until the day it matters.
//
// **An unbalanced period renders UNBALANCED**, with the difference beside it.
// BR-LED-007 makes drift a release blocker with no dismiss path: drift can only
// come from a posting-service bypass, so the one thing this screen must never do
// is make broken books look tidy.
//
// ══════════════════════════════════════════════════════════════════════════
// WHERE THIS SCREEN DIVERGES FROM `05-prototype/UtilityBilling.html`
// ══════════════════════════════════════════════════════════════════════════
// Law 6 — diff against the prototype and report BOTH directions.
//
//   · **No premises filter.** ⚠ **CORRECTED 2026-09-03 — DEF-2347.** This
//     paragraph read *"`journal_lines.premises_id` is NULL on every row in the
//     product (US-LED-002 unbuilt)"* and that was the reason the screen gave a
//     clerk in eleven languages. **US-LED-002 LANDED 2026-08-16**:
//     `apps/ledger/posting.py` resolves account → unit → premises at posting
//     time and REFUSES a line that names a customer account and cannot resolve
//     one, and `reporting.by_premises_summary` has grouped on that stamp ever
//     since. The data was never the blocker after that date.
//     **What is true now is smaller and it is a MISSING READ:**
//     `GET /ledger/trial-balance` accepts `from` and `to` and nothing else, and
//     `GET /ledger/journal-entries` accepts `f.type`, `f.status`,
//     `f.source_type`, `q`, `from` and `to` — neither takes a premises. So a
//     dropdown here would still make the report LOOK filtered, which is why it
//     is still not drawn; the REASON on screen changed and the control did not.
//     CR-060 C24 closes when the two reads take the param.
//   · **No "Expand → dimension breakdown" on a GL row.** BR-LED-009 asks for it
//     and there is no read model: `reporting.py` publishes the account totals and
//     `GET /ledger/journal-entries/{id}` is named by 11b §2.10 and NOT SERVED —
//     the ledger API lane reported the exact read that would close it
//     (`reporting.journal_entry_detail(entry_id)`). The row expands to nothing,
//     so no chevron is drawn.
//     ⚠ **RE-VERIFIED 2026-09-03 for CR-060 C23 and it still holds** — recorded
//     because the paragraph ABOVE it did not, and a sentence that has been
//     checked is worth more than one that has merely survived. `journal_api.py`
//     mounts `ledger/journal-entries/<uuid:entry_id>` as **DELETE only**;
//     `reporting.journal_entry_list` filters on type, status, source_type,
//     search and the date window and **has no ledger-account filter**; and
//     `reporting.account_ledger` is the CUSTOMER account's AR movements, not a
//     chart row's. So nothing served answers *"which entries make up this
//     account's figure for this period"*. C23 needs ONE of two reads and
//     either closes it: `reporting.journal_entry_detail(entry_id)` (11b §2.10's
//     own name, one entry's lines with their dimensions), or a
//     `f.ledger_account` filter on `journal_entry_list` — which is the cheaper
//     of the two here, because the row a clerk clicks is an ACCOUNT and the
//     list this screen already draws is the surface that would answer it.
//   · **No "+ Record refund" or "+ Journal entry" buttons.** Both are S57
//     (EP-LED-04) and neither has an endpoint; `apps/ledger/api.py` records that
//     every §2.10 WRITE is unserved. A button onto nothing is DEF-007's family.
//   · **No "↓ Export trial balance".** `POST /reports/{key}/export` is contracted
//     and served by no deployment (the job runner is TD-17), so the control
//     renders DISABLED WITH ITS REASON per BR-SHL-025 rather than vanishing.
//   · ⚠ **THE ACCOUNT-MAPPING PANEL IS GONE — DEF-LED-6701, PO on build
//     2.351.84: *"at bottom why are you asking for account mapping?"*.** This
//     clause read *"it is a LINK, not a table … the live mapping lives on
//     Settings → Configure and `GET /ledger/gl-mappings` is not served"*, and
//     was amended once already, on 2026-08-16, when that route WAS served. It
//     went stale a second time and nobody amended it: the mapping is now a VIEW
//     of this same tab (blueprint p025 note 1, *"Chart · was 'Chart of accounts
//     & mapping'"*), so the panel was a second door to a place the view strip at
//     the top of this screen already opens. Removed, not reworded — B14 rule 33.
//   · ⚠ **THE JOURNAL LIST IS GONE FROM THIS VIEW — DEF-LED-6700, PO on build
//     2.351.84: *"on balance screen you are still showing journal entries table
//     at bottom - it should be removed - it is already in journal entries -
//     separate tab"*.** This clause read *"the journal list is ADDED below the
//     trial balance … it is the only place a draft entry is visible at all"*,
//     which was true until `P1.15` split the tab into four views. Finance
//     blueprint p023 note 1: *"Balance · was 'Trial balance & journal'; the
//     journal moved out to 1·1"*. `JournalView` offers `draft` in its status
//     facet, so the draft argument moved with the list rather than dying with
//     it, and Balance is the trial balance alone.
import { useState } from "react";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  deleteManualJournalDraft,
  getChartOfAccounts,
  getCloseChecklist,
  getJournalEntries,
  getTrialBalance,
  requestListExport,
  reverseJournalEntry,
} from "@/api/endpoints";
import type {
  JournalEntryListRow,
  LedgerChartRow,
  ManualJournalLine,
  TrialBalanceResponse,
  TrialBalanceRow,
} from "@/api/endpoints";
import { journalEntryDetailPath } from "./JournalEntryDetail";
import { JournalView, journalConfig, journalRegional, journalWindow } from "./JournalView";
import { AbsentFigure } from "@/components/AbsentFigure";
import { Button } from "@/components/Button";
// CR-060 C14 — the shared list toolkit. BOTH files are on
// `src/styles/route-b-migrated.txt`, so their Tailwind utilities live in THEIR
// files and a legacy `fin-*` page may import and render them safely (B14 rule
// 21's migration clause; CR-060 §8d states the same in terms).
import { DataTable } from "@/components/DataTable";
import { todayInZone } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { PeriodPicker } from "@/components/PeriodPicker";
import {
  BALANCE_PERIOD_CHOICES,
  choiceFor,
  isPeriodChoice,
  periodRefusal,
  periodWindow,
} from "@/components/periodWindow";
import type { PeriodMonth, PeriodValue } from "@/components/periodWindow";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { DownloadButton } from "@/components/DownloadButton";
import { MoneyCell } from "@/components/MoneyCell";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { Panel } from "@/components/Panel";
import {
  Dash,
  isDenied,
  useRegional,
  useAccessCell,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { AccrualsPanel } from "./AccrualsPanel";
import { AccrualsWorkbench } from "./AccrualsWorkbench";
import { ChartOfAccountsPanel } from "./ChartOfAccountsPanel";
import { JournalEntryModal } from "./JournalEntryModal";
import { FinanceBody, FinanceHeader, useFinancePeriod } from "./financeChrome";
import {
  CloseReadinessStrip,
  FINANCE_PERMISSION,
  FINANCE_TAB_GL,
  FactRow,
  PremisesFilterField,
  financeTabFrom,
  gapSentence,
  usePremisesSearch,
} from "./financeShared";
import { ViewStrip, withView } from "./financeViewStrip";

import "./finance.css";

/** ⚠ **THE PROPERTY IS PART OF THE KEY (`P2.3`).** A cache key that names the
 *  period but not the filter answers a filtered request from the unfiltered
 *  cache — the control moves, the table does not, and every test still passes.
 *  `""` is "every property" and is the unfiltered report. */
/**
 * The query-string name of the Balance view's property filter (`DEF-LED-6654`).
 *
 * It is **the same string `getTrialBalance` puts on the wire**, so what a clerk
 * pastes and what the server is asked can be read against each other without a
 * translation table in between.
 */
export const PREMISES_PARAM = "f.premises";

/**
 * `DEF-LED-10072` P7 — the Balance view's period, in the page URL under the
 * SAME names the server takes (`from`, `to`), plus the quick choice that
 * produced them (`range`). One name end to end, like `f.premises`.
 */
export const BALANCE_PERIOD_PARAMS = { choice: "range", from: "from", to: "to" } as const;

/**
 * `DEF-LED-10072` P1 · P2 · P4 · P7 — the window the Trial balance shows.
 *
 * * A quick choice in the URL is RE-COUNTED from the business date, so a link
 *   saying *Last 30 days* means the last thirty days on the day it is opened.
 * * Custom keeps its two dates, when they are real and neither cross nor end
 *   after today (P4); otherwise the link falls back rather than erroring
 *   (BR-SHL-011).
 * * With nothing in the URL it is **This month** — the finance month being
 *   worked in, which is what this view always showed (P1) — up to today, since
 *   a period cannot end after today (P4).
 *
 * `null` only while no finance month is served and the URL names none, which
 * is exactly when the old screen also had no period to ask for.
 */
export function balancePeriodFrom(
  params: URLSearchParams,
  today: string,
  month: PeriodMonth | null,
): PeriodValue | null {
  const raw = params.get(BALANCE_PERIOD_PARAMS.choice);
  const from = params.get(BALANCE_PERIOD_PARAMS.from) ?? "";
  const to = params.get(BALANCE_PERIOD_PARAMS.to) ?? "";
  const lawful = (window: { from: string; to: string }) =>
    periodRefusal(window.from, window.to, today) === null;
  if (isPeriodChoice(raw) && BALANCE_PERIOD_CHOICES.includes(raw)) {
    const window = periodWindow(raw, today, month) ?? { from, to };
    if (lawful(window)) return { choice: raw, ...window };
  } else if (raw === null && lawful({ from, to })) {
    return { choice: choiceFor(from, to, today, BALANCE_PERIOD_CHOICES, month), from, to };
  }
  if (month === null) return null;
  const window = periodWindow("this_month", today, month);
  return window === null || !lawful(window)
    ? { choice: "custom", from: month.start, to: month.end }
    : { choice: "this_month", ...window };
}

export const trialBalanceQueryKey = (period: string, premisesId = "") =>
  ["ledger", "trial-balance", period, premisesId] as const;
export const journalQueryKey = (period: string, filters: string) =>
  ["ledger", "journal-entries", period, filters] as const;

/** A route that answers 404 does not exist on this deployment. DERIVED from the
 *  response, never declared — a constant would be a comment claiming a fact
 *  about another file (hard-won law 1). */
export function ledgerRouteAbsent(error: unknown): boolean {
  return isApiError(error) && error.status === 404;
}

// ── The trial balance (US-LED-008 · A14 r2's five columns) ────────────────

/**
 * The seven columns of the trial balance as **CR-060 C14's list toolkit**, and
 * the reason the toolkit is the whole of that task.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHY `DataTable` AND NOT THE HAND-ROLLED `PlainTable` THAT WAS HERE
 * ══════════════════════════════════════════════════════════════════════════
 * C14's headline is *"and NONE of it needs building"*: `components/DataTable`
 * already ships search, sort, paging, column show/hide and column reorder, and
 * `FilterBar` ships the filters — and `PaymentsPage` was the ONE file in the
 * product using them, while every ledger page drew its own `<table>`. So this
 * is a DELETION of bespoke markup, not an addition of features.
 *
 * ⚠ **AND IT IS LAWFUL IN A FILE THAT IS NOT ON THE TAILWIND LIST, WHICH IS THE
 * ONLY REASON IT CAN BE DONE INSIDE A FEATURE CHANGE (B14 rule 21).**
 * `07-frontend/src/features/ledger/` has ZERO of its files on
 * `src/styles/route-b-migrated.txt`, so a Tailwind utility written HERE emits
 * no CSS and renders as nothing at all while `tsc`, eslint and every
 * `toHaveClass` assertion pass. `DataTable` and `FilterBar` ARE migrated, so
 * their utilities live in THEIR files and a legacy page may import and render
 * them safely — CR-060 §8d says so in terms. Not one utility is typed into this
 * file; the classes below are `fin-*` names `finance.css` already declares.
 * The migration of this area is its own piece of work by PO ruling of
 * 2026-09-01 and is deliberately NOT folded in here.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * THE TABLE PAGES; THE FOOTER DOES NOT. THAT IS THE WHOLE DESIGN.
 * ══════════════════════════════════════════════════════════════════════════
 * `GET /ledger/trial-balance` is NOT paginated and must never be: US-LED-008
 * TC-1 requires the table to foot over ALL rows, so a page would make
 * `total_debit` a page total and the word *Balanced* a claim about a page. The
 * response is bounded by the tenant's CHART OF ACCOUNTS, not by transaction
 * volume, so the whole of it arrives in one read.
 *
 * So the toolkit's search, sort and paging run over the served rows HERE, and
 * the footer is rendered BELOW the table off the SERVER's own totals. Filter
 * the table to liabilities and the footer still says whether THE BOOKS balance,
 * because that is the only thing it can honestly say — and the sentence under
 * it says so, once, in the rule-32 budget.
 *
 * ⚠ **NOTHING IN HERE ADDS UP MONEY.** The sort compares served decimal STRINGS
 * through `Number()` for ORDER ONLY, never to produce a figure — `MoneyCell`
 * renders every amount and the totals are the server's (CLAUDE.md rule 2,
 * BR-SHL-023). A sort key is not a money value.
 */
export const TRIAL_BALANCE_SCREEN_ID = "S56.trialBalance";

/** Order only. A decimal STRING compared as a number decides which row is
 *  above which; it never becomes a figure anybody reads. */
function byAmount(a: string, b: string): number {
  return Number(a) - Number(b);
}

export function trialBalanceConfig(
  /** ⚠ **NULLABLE ON PURPOSE, AND IT IS THE ONLY WAY THIS STAYS ONE CONFIG.**
   *  Parsing `?sort=` out of the URL needs the COLUMNS and never renders a
   *  cell, and it happens before the report has arrived. A second
   *  columns-only config would be two lists that can drift, so the report is
   *  optional and every money cell asks for it — a cell that somehow rendered
   *  without one draws a dash rather than an amount with no CHAR(3) beside it
   *  (CLAUDE.md rule 2: the code rides WITH the figure, never assumed). */
  report: TrialBalanceResponse | null,
  t: Translator,
  locale: string | undefined,
): TableConfig<TrialBalanceRow> {
  const money = (amount: string) =>
    report === null ? (
      <Dash />
    ) : (
      <MoneyCell amount={amount} currency={report.currency} locale={locale} />
    );
  return {
    screenId: TRIAL_BALANCE_SCREEN_ID,
    // B14 rule 31 / G69 — `account_id` is the row id for React and for the
    // preference store and reaches no cell. The IDENTITY column is the GL
    // CODE, which is the number a bookkeeper actually says out loud.
    getRowId: (row) => row.account_id,
    searchFields: ["code", "name"],
    searchPlaceholder: "finance.gl.searchPrompt",
    defaultSort: { sort: "code", dir: "asc" },
    filters: [
      {
        name: "type",
        label: t("finance.gl.col.type"),
        options: TRIAL_BALANCE_TYPES.map((type) => ({
          value: type,
          label: t(`finance.gl.type.${type}`, { defaultValue: type }),
        })),
      },
    ],
    columns: [
      {
        key: "code",
        label: t("finance.gl.col.account"),
        sortable: true,
        identity: true,
        // CR-196-BRC10 Q1 A (PO 2026-10-29) — every period shows the NEW code,
        // with the old one beside it: *"0117-080-1000-0000-7110 (formerly
        // 4150)"*. `fin-absent-reason` is the quiet second-line class this
        // module already declares (B14 rule 21 — no stylesheet grows).
        cell: (row) =>
          row.former_code ? (
            <>
              {row.code}{" "}
              <span className="fin-absent-reason">
                {t("finance.coa.formerly", { code: row.former_code })}
              </span>
            </>
          ) : (
            row.code
          ),
      },
      { key: "name", label: t("finance.gl.col.name"), sortable: true },
      {
        key: "type",
        label: t("finance.gl.col.type"),
        sortable: true,
        cell: (row) => t(`finance.gl.type.${row.type}`, { defaultValue: row.type }),
      },
      // CR-060 C4 — position · movement · position, in that reading order.
      {
        key: "opening",
        label: t("finance.gl.col.opening"),
        sortable: true,
        numeric: true,
        cell: (row) => money(row.opening),
      },
      {
        key: "debit",
        label: t("finance.gl.col.debit"),
        sortable: true,
        numeric: true,
        // A trial balance prints the account's NET on ONE side and a dash on
        // the other — LE-1's own shape ("1200 AR | 152.32"). A real 0.00 is a
        // fact LE-1 states and is NOT blanked.
        cell: (row) => money(row.debit),
      },
      {
        key: "credit",
        label: t("finance.gl.col.credit"),
        sortable: true,
        numeric: true,
        cell: (row) => money(row.credit),
      },
      {
        key: "closing",
        label: t("finance.gl.col.closing"),
        sortable: true,
        numeric: true,
        cell: (row) => money(row.closing),
      },
    ],
  };
}

/** The five `type` values the chart can hold, for the toolkit's own filter.
 *  BR-REP-006 — a filter enumerates the LIVE vocabulary, and this one is the
 *  `ledger_accounts.type` CHECK constraint's own set rather than a guess. */
export const TRIAL_BALANCE_TYPES = [
  "asset",
  "liability",
  "equity",
  "revenue",
  "expense",
  "contra_revenue",
] as const;

/**
 * Search · filter · sort · page, over rows the server sent whole.
 *
 * Exported so a test can assert the arithmetic-free ordering directly rather
 * than by reading pixels — and because it is the one piece of logic in this
 * file, so it must be reachable without mounting a screen.
 */
export function trialBalanceView(
  rows: readonly TrialBalanceRow[],
  state: TableRequestState,
): { page: TrialBalanceRow[]; total: number } {
  const needle = state.q.trim().toLowerCase();
  let working = rows.filter((row) => {
    if (needle !== "" && !`${row.code} ${row.name}`.toLowerCase().includes(needle)) {
      return false;
    }
    const type = state.filters.type;
    return type === undefined || type === "" || row.type === type;
  });
  const direction = state.dir === "desc" ? -1 : 1;
  working = [...working].sort((a, b) => {
    switch (state.sort) {
      case "opening":
        return direction * byAmount(a.opening, b.opening);
      case "debit":
        return direction * byAmount(a.debit, b.debit);
      case "credit":
        return direction * byAmount(a.credit, b.credit);
      case "closing":
        return direction * byAmount(a.closing, b.closing);
      case "name":
        return direction * a.name.localeCompare(b.name);
      case "type":
        return direction * a.type.localeCompare(b.type);
      default:
        return direction * a.code.localeCompare(b.code);
    }
  });
  const from = (state.page - 1) * state.per;
  return { page: working.slice(from, from + state.per), total: working.length };
}

export function TrialBalanceTable(props: {
  report: TrialBalanceResponse;
  t: Translator;
  locale?: string;
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
}) {
  const { report, t } = props;
  const config = trialBalanceConfig(report, t, props.locale);
  const view = trialBalanceView(report.rows, props.state);
  return (
    <Panel>
      <div className="fin-panel-head">
        <h3>{t("finance.gl.tableTitle")}</h3>
      </div>
      {report.rows.length === 0 ? (
        // An empty book is rendered as EMPTY, in words. DEF-110's warning is
        // exactly this: a month-close journey over a fixture with no July
        // entries would foot 0 = 0 at every step and PASS. A table with no rows
        // and a green "Balanced" badge is the dangerous direction.
        <p className="fin-absent-reason" role="note">
          {t("finance.gl.empty")}
        </p>
      ) : (
        <DataTable<TrialBalanceRow>
          config={config}
          state={props.state}
          onStateChange={props.onStateChange}
          rows={view.page}
          totalRows={view.total}
          loading={false}
          filterBarSlot={
            <FilterBar
              filters={config.filters ?? []}
              state={props.state}
              onStateChange={props.onStateChange}
            />
          }
          empty={{
            title: t("finance.gl.noMatchTitle"),
            helper: t("finance.gl.noMatchHelper"),
            ctaLabel: t("finance.gl.clearSearch"),
            onCta: () => props.onStateChange({ ...props.state, q: "", filters: {}, page: 1 }),
          }}
        />
      )}
      {report.rows.length === 0 ? null : (
        <div className="fin-total-row" data-testid="trial-balance-footer">
          {/* The word "Balanced" is the SERVER's answer. There is no comparison
              of the two totals anywhere in this file.

              ⚠ **THREE VALUES, NOT TWO (`DEF-LED-6524`).** `balanced` is
              `true`, `false` or **`null`**, and this read `report.balanced ?
              "success" : "danger"` — which renders `null` as **danger, with
              the difference beside it**. `apps/ledger/wire.py` names that exact
              failure in its own docstring: *"coercing it to `false` would
              report a posting-service bypass on a screen that is working
              perfectly"*.

              `null` means **the question does not apply**: a table narrowed to
              one property cannot foot, because balance is a property of an
              ENTRY and the filter takes a subset of each entry's lines. So no
              verdict is drawn at all — not "Balanced", not "Unbalanced", and
              not a neutral pill saying nothing. The footer's totals still show;
              only the claim about them is withheld. */}
          {report.balanced === null ? null : (
            <FactRow
              label={t("finance.gl.footerLabel")}
              value={
                <StatusPill tone={report.balanced ? "success" : "danger"}>
                  {report.balanced
                    ? t("finance.gl.balanced")
                    : t("finance.gl.unbalanced", { difference: report.difference })}
                </StatusPill>
              }
              strong
            />
          )}
          {/* CR-060 C4's own proof, rendered: opening + movement = closing, and
              on a book that closed square both positions foot to nothing. */}
          <FactRow
            label={t("finance.gl.col.opening")}
            value={
              <MoneyCell
                amount={report.total_opening}
                currency={report.currency}
                basis={report.basis}
                locale={props.locale}
              />
            }
          />
          <FactRow
            label={t("finance.gl.col.debit")}
            value={
              <MoneyCell
                amount={report.total_debit}
                currency={report?.currency ?? null}
                basis={report.basis}
                locale={props.locale}
              />
            }
          />
          <FactRow
            label={t("finance.gl.col.credit")}
            value={
              <MoneyCell
                amount={report.total_credit}
                currency={report?.currency ?? null}
                basis={report.basis}
                locale={props.locale}
              />
            }
          />
          <FactRow
            label={t("finance.gl.col.closing")}
            value={
              <MoneyCell
                amount={report.total_closing}
                currency={report.currency}
                basis={report.basis}
                locale={props.locale}
              />
            }
          />
          {/* B14 rule 32 — ONE sentence, and it is load-bearing rather than
              decorative: the table above pages and filters, the footer never
              does, and a reader who assumed otherwise would read a page total
              as the month's. */}
          <p className="fin-params-note" role="note">
            {t("finance.gl.footerScope")}
          </p>
        </div>
      )}
      {report.balanced === false ? (
        // BR-LED-007: drift is a RELEASE BLOCKER with no dismiss path. It is
        // stated as an alert, with the served difference, and there is no
        // control on this screen that makes it go away.
        //
        // ⚠ **`=== false`, NOT FALSY (`DEF-LED-6524`).** This read
        // `report.balanced ? null : <alert>`, so a filtered table — where the
        // server sends `null` precisely to avoid a verdict — printed *"The
        // books do not add up. Debits and credits can only differ if something
        // wrote a journal line outside the posting service."* on a perfectly
        // healthy set of books, the moment a clerk picked a property. A
        // release-blocking accusation that fires when nothing is wrong is the
        // one everybody learns to ignore, which is the argument the tie-out's
        // own decision row already makes about a different false alarm.
        <p className="fin-absent-reason" role="alert">
          {t("finance.gl.driftWarning")}
        </p>
      ) : null}
    </Panel>
  );
}

// ⛔ `JournalEntryTable` IS GONE (`DEF-LED-6723`, 2026-09-25).
//
// It was the S56 journal list before `P1.15` split the strip into four views
// and `JournalView` took the screen over. It stayed EXPORTED with **zero
// production callers**, exercised only by two cases in `financeSurface.test.tsx`
// — which is hard-won law 2's dead-UI shape wearing a green suite: a component
// nothing mounts, with tests that keep it looking alive. A sibling lane found
// it, judged deleting it the riskier act with the container restarting, and
// said so rather than doing it quietly; this lane is the one that had to decide,
// because the entry DETAIL was the last thing that might have given it a caller
// and it does not — the detail draws its own two-sided table.
//
// ⚠ **ITS TWO CASES ASSERTED REAL RULES AND THOSE MOVED RATHER THAN DIED** —
// a draft's dash (`BR-LED-021`, PO 2026-08-12, *"a draft has NO number"*) and
// an unrecognised source showing as ITSELF (`BR-REP-008`, *nothing invisible*).
// They now run against `journalConfig`'s own cell renderers in
// `journalView.test.tsx`, which is the table a clerk actually sees. Deleting
// an assertion about a live rule would have been the worse half of this trade.
// ── The screen ────────────────────────────────────────────────────────────

/** The S56 body has three sections and only one fits on a screen at a time.
 *  Carried in `?view=` URL STATE rather than component state so a section is
 *  linkable into a ticket and a browser Back leaves it — the same posture the
 *  S29 read drawer takes (BR-SHL-011). */
/** `P1.15` — **FOUR views, one word each, and `journal` is the landing view.**
 *
 *  Finance blueprint p020/p023/p025/p027. The strip used to read *"Trial
 *  balance & journal"* over a screen that was two lists stacked, and p023's own
 *  note records the split: *"Balance · was 'Trial balance & journal'; the
 *  journal moved out to 1·1"*.
 *
 *  ⚠ **`balance` KEEPS ITS URL VALUE, DELIBERATELY.** It is the value every
 *  existing bookmark, ticket link and test carries, and renaming it would break
 *  each of them to no purpose — the WORD on screen changed, the value did not.
 *  `journal` is the new one and it is FIRST, because p020 marks it *"the
 *  landing view"* and p022's DOORS line reads *"It is the landing view, so
 *  every door to `/finance` is a door to this screen"*. */
export const GL_VIEWS = ["journal", "balance", "chart", "accruals"] as const;
export type GlView = (typeof GL_VIEWS)[number];

/** An unknown `?view=` falls back to the LANDING view and never 404s.
 *
 *  ⚠ **THE FALLBACK MOVED FROM `balance` TO `journal` (`P1.15`)**, which is what
 *  makes the journal the landing view: `/finance` with no `?view=` is the
 *  commonest way in by far. `?view=balance` still resolves to the trial
 *  balance, so nothing bookmarked moved. */
export function glViewFrom(raw: string | null): GlView {
  return (GL_VIEWS as readonly string[]).includes(raw ?? "") ? (raw as GlView) : "journal";
}

export interface GeneralLedgerPageProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
  locale?: string;
  /** BR-TEN-043 — the instant this screen stamps on a post, a retirement or a
   *  reversal. A SEAM, not a convenience: nothing in a money path may read a
   *  clock the caller did not state, and a test must be able to name it. */
  now?: () => string;
}

export function GeneralLedgerPage(props: GeneralLedgerPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const routeParams = useParams();
  const { timeZone, dateFormat } = useRegional(props);
  const cell = useAccessCell(FINANCE_PERMISSION, client);
  const { period, loading } = useFinancePeriod(client);
  // `DEF-LED-10071` J3 · `DEF-LED-10072` P2 — every quick choice is counted
  // from the UTILITY's business date: today in the tenant's own zone, read
  // through the page's `now` seam (BR-TEN-043), never the browser's calendar.
  const businessToday = todayInZone(
    timeZone,
    new Date((props.now ?? (() => new Date().toISOString()))()),
  );
  const { i18n } = useTranslation();
  const regional = { timeZone, dateFormat, today: businessToday };
  const financeMonth: PeriodMonth | null =
    period === null ? null : { start: period.start, end: period.end };

  // ⚠ `const [status, setStatus]` STOOD HERE AND IS DELETED WITH THE SELECT IT
  // drove (`DEF-LED-6700`). BR-REP-006's rule that the status filter enumerates
  // the vocabulary the SERVER accepts — and that `reversed` is deliberately
  // absent, being a LINK rather than a value `journal_entries.status` can hold —
  // did not go with it: it now lives on `JournalView`'s `JOURNAL_STATUSES`,
  // which is the one status filter this tab has.
  const [searchParams, setSearchParams] = useSearchParams();
  const view = glViewFrom(searchParams.get("view"));
  // CR-060 C14 — *"so a filtered journal view becomes a shareable URL"*, and
  // the CR's own proof is the round trip: search, sort, filter and the column
  // set survive a reload. `?view=` rides in the SAME query string, so a link
  // to a filtered trial balance keeps the section it was filtered on.
  // The currency only reaches the CELL renderers, and parsing the URL never
  // renders one — so `null` here is the honest argument rather than a stand-in
  // report, and there is exactly one config shape (the columns a `?sort=` may
  // name cannot drift from the columns the table draws).
  const tableConfigForParams = trialBalanceConfig(null, translate, props.locale);
  // `DEF-LED-10072` — the picked window. The close strip and the Accruals view
  // do NOT read it: they stay on `period`, the month being CLOSED (P5).
  const balancePeriod = balancePeriodFrom(searchParams, businessToday, financeMonth);
  function setBalancePeriod(next: PeriodValue): void {
    const params = new URLSearchParams(searchParams);
    params.set(BALANCE_PERIOD_PARAMS.choice, next.choice);
    params.set(BALANCE_PERIOD_PARAMS.from, next.from);
    params.set(BALANCE_PERIOD_PARAMS.to, next.to);
    params.set("view", view);
    setSearchParams(params, { replace: true });
  }
  const tableState = parseTableParams(searchParams, tableConfigForParams);
  function setTableState(next: TableRequestState): void {
    const params = serializeTableParams(next, tableConfigForParams);
    params.set("view", view);
    // ⚠ **THE PROPERTY FILTER SURVIVES A SORT (`DEF-LED-6654`).**
    // `serializeTableParams` writes the table's OWN declared params and nothing
    // else, so a filter living beside them is dropped by any sort, page or page
    // -size change unless it is carried across here. A filter that silently
    // clears itself when a clerk clicks a column heading is worse than one that
    // never travelled at all.
    carryPremises(params);
    setSearchParams(params, { replace: true });
  }
  // `P1.1` · `P1.9` — the journal's own request state, in the SAME query string.
  //
  // ⚠ **PARSED WITH THE JOURNAL'S CONFIG AND NOT THE TRIAL BALANCE'S.**
  // `parseTableParams` validates `sort` against the columns it is given, so
  // reading `?sort=entry_date` through `trialBalanceConfig` would silently fall
  // back to `code` — a shared URL that opens on a different order than the one
  // that was copied. One view is on screen at a time, so the two states never
  // both drive a table.
  const journalConfigForParams = journalConfig(
    null,
    translate,
    props.locale,
    journalRegional(regional, t, i18n),
  );
  const journalState = parseTableParams(searchParams, journalConfigForParams);
  function setJournalState(next: TableRequestState): void {
    const params = serializeTableParams(next, journalConfigForParams);
    params.set("view", view);
    // The journal does not READ the property filter — it is the Balance view's
    // control (p023 note 2) — but the two views share ONE query string, so
    // paging the journal must not throw away the Balance view's filter that a
    // clerk switches back to.
    carryPremises(params);
    setSearchParams(params, { replace: true });
  }
  /** Carry the Balance view's own params — `f.premises` and, since
   *  `DEF-LED-10072`, its period — across a rebuild of the query string. A
   *  sort or a page on either table must not throw away a window a clerk
   *  picked and is about to switch back to. */
  function carryPremises(params: URLSearchParams): void {
    for (const name of [
      PREMISES_PARAM,
      BALANCE_PERIOD_PARAMS.choice,
      BALANCE_PERIOD_PARAMS.from,
      BALANCE_PERIOD_PARAMS.to,
    ]) {
      const current = searchParams.get(name);
      if (current !== null && current !== "") params.set(name, current);
    }
  }
  const [modalOpen, setModalOpen] = useState(false);
  const [prefill, setPrefill] = useState<{ lines: ManualJournalLine[]; memo: string } | null>(null);
  const [reverseTarget, setReverseTarget] = useState<JournalEntryListRow | null>(null);
  const [reverseReason, setReverseReason] = useState("");
  const [reverseFailure, setReverseFailure] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const toast = useToast();
  const stamp = props.now ?? (() => new Date().toISOString());

  // The GL account picker S57 fills its rows from. `f.status=active` is not
  // tidiness: a deactivated account is refused by the posting service (IS-1),
  // so an unfiltered picker would offer rows every submit would bounce — the
  // DEF-114 shape.
  const chart = useQuery({
    queryKey: ["ledger", "chart", "picker"],
    queryFn: () => getChartOfAccounts({ status: "active" }, client),
    retry: false,
  });
  const pickerAccounts: LedgerChartRow[] = chart.data?.rows ?? [];

  // ── The property filter (Finance blueprint `P2.3`, `DEF-LED-6499`) ───────
  // `premisesId` is what the SERVER is asked for; `premisesTerm` is what the
  // clerk has typed. Two pieces of state because they answer different
  // questions — a term with no choice made yet must not filter the table, and
  // a choice already made must survive the clerk clearing the box.
  // `""` means EVERY property, which is the unfiltered report and the default.
  //
  // ⚠ **`premisesId` LIVES IN THE URL AND NOT IN `useState` (`DEF-LED-6654`).**
  // It was component state, so a clerk who filtered the trial balance to one
  // property and pasted the link sent a colleague EVERY property — silently,
  // because the link looks complete to both of them. Phase 1's own DONE WHEN
  // (p012) is *"every list … carries its filters in the URL"*, and the journal
  // beside it on this same screen had carried its six since `P1.9`.
  //
  // ⚠ **`f.premises` IS THE SAME SPELLING THE WIRE USES**, which
  // `getTrialBalance` already sends. One name for the filter end to end means
  // a pasted link and the request it produces can be read against each other
  // by a person, and `journalUrlShareability.dom.test.tsx` asserts exactly that
  // string on the outgoing call.
  //
  // ⚠ **IT IS READ BACK THROUGH `searchParams`, SO A PASTED LINK IS THE ONLY
  // SOURCE OF TRUTH.** A `useState` seeded from the URL would round-trip
  // correctly in one mount and diverge the moment anything else wrote the query
  // string — the sort, the page or `?view=` — which is the shape that made this
  // a defect rather than a missing feature.
  const premisesId = searchParams.get(PREMISES_PARAM) ?? "";
  function setPremisesId(next: string): void {
    const params = new URLSearchParams(searchParams);
    // Deleted rather than set empty: an empty `f.premises` on the wire reads
    // like a filter that matched nothing, and in the address bar it reads like
    // a filter somebody set and meant.
    if (next === "") params.delete(PREMISES_PARAM);
    else params.set(PREMISES_PARAM, next);
    params.set("view", view);
    setSearchParams(params, { replace: true });
  }
  const [premisesTerm, setPremisesTerm] = useState("");
  const premisesSearch = usePremisesSearch(premisesTerm, client, "gl");

  const windowKey = period === null ? "" : `${period.start}|${period.end}`;
  const balanceWindowKey =
    balancePeriod === null ? "" : `${balancePeriod.from}|${balancePeriod.to}`;
  const trialBalance = useQuery({
    // ⚠ **`premisesId` IS IN THE KEY, AND LEAVING IT OUT IS THE WHOLE DEFECT
    // THIS TASK EXISTS TO AVOID.** react-query caches by key: a filter the key
    // does not mention changes the request and not the cached answer, so the
    // control would move, the network would carry `f.premises`, and the table
    // would go on showing every property — a filter that looks applied and
    // is not, which is worse than the panel that said it did not exist.
    // `DEF-LED-10072` — the PICKED window, in the key for the same reason the
    // property is: a window the key does not name is answered from the cache.
    queryKey: trialBalanceQueryKey(balanceWindowKey, premisesId),
    queryFn: () =>
      getTrialBalance(
        {
          ...(balancePeriod === null ? {} : { from: balancePeriod.from, to: balancePeriod.to }),
          // Omitted rather than sent empty: `_premises_filter` reads None for
          // both, but an empty `f.premises` on the wire reads like a filter
          // that matched nothing.
          ...(premisesId === "" ? {} : { premises: premisesId }),
        },
        client,
      ),
    retry: false,
    enabled: balancePeriod !== null,
    // `DEF-LED-10072` — the last table stays on screen while the next window
    // loads. Without it a new window empties `report`, the page swaps the
    // params band for a skeleton, and the Period picker UNMOUNTS under the
    // clerk's typing — `10/05/20` is already a valid day, so the year they
    // were finishing went to 2020.
    placeholderData: keepPreviousData,
  });
  // CR-060 C12 — the SAME payload S42 reads, so the strip and the Close screen
  // cannot disagree about what is outstanding. Both bounds are REQUIRED here
  // (unlike the trial balance), so the query waits for the served period.
  const closeChecklist = useQuery({
    queryKey: ["finance", "close-checklist", windowKey],
    queryFn: () =>
      getCloseChecklist({ from: period?.start ?? "", to: period?.end ?? "" }, client),
    retry: false,
    enabled: period !== null,
  });
  // `P1.1` — every criterion p021's filter table lists now actually travels.
  // The server has accepted all six since `api.py:478-485` and the front end
  // sent none of them; `P1.8` then put the page itself in SQL, so `page`,
  // `per`, `sort` and `dir` reach the database rather than a slice of a built
  // list.
  // `DEF-LED-10071` J4 — NO period unless one is chosen: every entry. Until
  // this change the journal was silently narrowed to the finance month, which
  // the PO's ruling replaces (*"J4 stands as written: no default period"*).
  const journalRequest = {
    ...journalWindow(journalState.filters),
    status: journalState.filters.status ?? "",
    type: journalState.filters.type ?? "",
    sourceType: journalState.filters.source_type ?? "",
    q: journalState.q,
    page: journalState.page,
    per: journalState.per,
    sort: journalState.sort,
    dir: journalState.dir,
  };
  const journal = useQuery({
    queryKey: journalQueryKey("", JSON.stringify(journalRequest)),
    queryFn: () => getJournalEntries(journalRequest, client),
    retry: false,
  });

  // P4.5 — the trial-balance download. `apps/ledger/finance_exports.py`
  // registers `trial_balance`; the server answers 202 and a job writes the
  // file, so the toast says it was ASKED FOR rather than that it has arrived.
  const exportRequest = useMutation({
    mutationFn: () =>
      requestListExport(
        {
          resource: "trial_balance",
          // The file is the window ON SCREEN (`DEF-LED-10072`), so the table
          // and the download cannot describe two different periods.
          filters:
            balancePeriod === null ? {} : { from: balancePeriod.from, to: balancePeriod.to },
        },
        // ⚠ THE PAGE'S CLIENT. `requestListExport` defaults to the module-level
        // `api`, so omitting this reaches the real network from inside a test
        // and from any screen mounted against a seam.
        client,
      ),
    onSuccess: () => toast(t("reports.export.queued")),
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("finance.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }
  if (trialBalance.isError && isPermissionDenied(trialBalance.error)) {
    return (
      <PermissionDenied
        helper={t("finance.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }

  const report = trialBalance.data;
  const failed = trialBalance.isError && report === undefined;
  const routeAbsent = failed && ledgerRouteAbsent(trialBalance.error);

  /** `BR-LED-003` — a draft is not in the books, so deleting one is lawful and
   *  is the only removal this screen has. A POSTED entry can never be deleted
   *  (hard rule 4) and the control says so rather than being hidden. */
  async function deleteDraft(row: JournalEntryListRow) {
    try {
      await deleteManualJournalDraft(row.entry_id, client);
      await queryClient.invalidateQueries({ queryKey: ["ledger"] });
      toast(t("finance.journal.draftDeleted"));
    } catch (problem) {
      toast(apiErrorText(problem, translate));
    }
  }

  async function confirmReverse() {
    if (reverseTarget === null) {
      return;
    }
    setReverseFailure(null);
    try {
      const result = await reverseJournalEntry(
        reverseTarget.entry_id,
        {
          reason: reverseReason,
          // The MIRROR is dated to the original's own book date; the close
          // forwards it if that period is locked (BR-TEN-038) and says so.
          entry_date: reverseTarget.entry_date ?? (period?.end ?? ""),
          posted_at: stamp(),
        },
        client,
      );
      toast(
        result.mirror_created
          ? t("finance.journal.reversedToast")
          : t("finance.journal.alreadyReversedToast"),
      );
      // LE-8's second half: the prefilled correction is DATA, not a row. It is
      // loaded into S57 so the clerk fixes the figure and *Save draft* is what
      // makes it exist — which keeps the draft lifecycle in exactly one place.
      setPrefill({
        lines: result.repost_draft,
        memo: t("finance.journal.repostMemo", { reason: reverseReason }),
      });
      setReverseTarget(null);
      setReverseReason("");
      setModalOpen(true);
      void queryClient.invalidateQueries({ queryKey: ["ledger"] });
    } catch (error) {
      setReverseFailure(
        isApiError(error) ? apiErrorText(error, translate) : t("finance.journal.reverseFailed"),
      );
    }
  }

  return (
    <div className="fin-page">
      <FinanceHeader
        activeTab={financeTabFrom(routeParams.tab ?? FINANCE_TAB_GL)}
        explainer={t("finance.explainer.gl")}
        period={period}
        t={translate}
        timeZone={timeZone}
        dateFormat={dateFormat}
        actions={
          <>
            {/* THE PROTOTYPE'S "+ Journal entry", WIRED. It was absent from
                this screen until 2026-08-16 with the note *"both are S57 and
                neither has an endpoint"*; S57 and its four routes exist now, so
                the button opens the modal instead of the comment explaining
                why it could not. "+ Record refund" stays absent — that is S58,
                payments' (US-PAY-011), and still unserved.

                ⚠ **IT NOW OPENS THE BATCH SCREEN, NOT THE MODAL
                (`DEF-LED-6664`).** `P1.21` built `1·5a` at
                `/finance/journal-entries/new`, routed it, tested it with 191
                cases — and changed no control, so for a day the only way into
                it was to TYPE the address. A grep of the whole of `src` for
                `journal-entries/new` returned `App.tsx` and nothing else.
                Finance blueprint **p030**'s DOORS row names this control as one
                of the screen's two doors, and its TODAY row says the modal is
                what the screen REPLACES: *"A `FormModal` over 1·1 that composes
                ONE entry with a free-form line list. No address, no batch, no
                draft to return to."*

                ⚠ **THE MODAL IS NOT RETIRED, AND THAT IS DELIBERATE.** It is
                still the REPOST half of reverse-and-repost below — that path
                hands it a prefilled set of lines and the batch composer takes
                no prefill — so retiring it here would have taken a working
                correction path down with a door fix. p030's SECOND door, the
                `✎` row action on a draft, is NOT wired either: the `/edit`
                route renders `JournalBatchPage` with nothing that reads the
                draft, so a `✎` would open an empty composer headed *"Edit draft
                entries"* — law 2 in its original form, a door onto nothing.
                Filed as `DEF-LED-6698` rather than built.

                ⚠ **THIS CITATION READ `DEF-LED-6677` IN `6aaac29b6` AND THAT
                IS A REAL DEFECT BELONGING TO SOMEBODY ELSE** — lane FIN-COPY's
                cost-category codes on Finance → Costs. The row this comment
                means was destroyed before it was ever committed, by a
                sibling's law-11 re-derivation of the shared register
                (`DEF-GOV-6697`), and the number had already been taken. A
                dangling id is caught by every id-existence check in this repo;
                a VALID id naming the WRONG defect is caught by none of them,
                which is `DEF-2804`'s shape and is why this is spelled out
                rather than quietly corrected. */}
            <Button
              variant="secondary"
              data-testid="open-journal-entry"
              onClick={() => navigate(tenantPath("/finance/journal-entries/new"))}
            >
              {t("finance.je.open")}
            </Button>
            {/* THE PROTOTYPE'S "↓ Export trial balance", WORKING (`P4.5`).

                ⚠ **THIS CONTROL WAS DISABLED WITH A REASON FOR SIX WEEKS, AND
                THE REASON MOVED TWICE BEFORE THE CONTROL DID.** It first said
                the download *"needs the report export service, which is not
                running on this deployment"* — false, the kernel had been
                writing files since August. `P2.5` corrected it on the MORNING
                of 2026-09-24 to name the real gap: a missing REGISTRATION.
                `P4.1` registered it that afternoon (`apps/ledger/
                finance_exports.py`), so the corrected sentence became false in
                turn and is now DELETED rather than shortened — B14 rule 33
                puts rationale at zero words on screen, and a working download
                needs nothing beside it.

                The filters are the screen's OWN window, so the file and the
                table cannot show different months. `disabled` is still
                reachable and still true when it fires: before the report has
                loaded there is nothing to export. */}
            <DownloadButton
              disabled={balancePeriod === null || report === undefined}
              onDownload={() => exportRequest.mutate()}
            />
          </>
        }
      />
      <FinanceBody period={period} loading={loading} t={translate}>
        {routeAbsent ? (
          <ArrivesWith
            title={t("finance.awaits.endpointTitle")}
            message={t("finance.awaits.endpoint")}
          />
        ) : failed ? (
          <Panel role="alert">
            <h3>{t("finance.error.title")}</h3>
            <p className="fin-absent-reason">{apiErrorText(trialBalance.error, translate)}</p>
          </Panel>
        ) : report === undefined ? (
          <LoadingSkeleton variant="table" />
        ) : (
          <>
            {/* The S56 body has three sections and only one fits on a screen.
                `?view=` is URL state, so a section is linkable into a ticket
                and a browser Back leaves it (BR-SHL-011).

                ⚠ **THIS WAS ~25 LINES OF JSX HERE UNTIL 2026-09-24 (`P2.18`).**
                Revenue & AR needs the same strip, and writing it a second time
                in a second page is what B14 rule 43 exists to stop. It moved to
                `financeViewStrip.tsx` UNCHANGED — same `<nav>`, same class,
                same `Button` variants, same `aria-current` — so this screen
                renders byte-for-byte what it rendered before. `P1.9`'s fix (only
                `view` moves; the rest of the query string survives) travelled
                with it as `withView` and is now in one place instead of two. */}
            <ViewStrip
              label={t("finance.gl.viewsLabel")}
              active={view}
              items={GL_VIEWS.map((candidate) => ({
                id: candidate,
                label: t(`finance.gl.view.${candidate}`),
              }))}
              onSelect={(candidate) => setSearchParams(withView(searchParams, candidate))}
            />
            {view === "journal" ? (
              // `P1.1` · `P1.15` — 1·1, the landing view. A COMPONENT and not a
              // function body in this page (B14 rule 43).
              <>
                <JournalView
                  response={journal.data ?? null}
                  loading={journal.isPending}
                  error={
                    journal.isError
                      ? {
                          reason: apiErrorText(journal.error, translate),
                          onRetry: () => void journal.refetch(),
                        }
                      : null
                  }
                  state={journalState}
                  onStateChange={setJournalState}
                  locale={props.locale}
                  regional={regional}
                  onReverse={(row) => {
                    setReverseTarget(row);
                    setReverseReason("");
                    setReverseFailure(null);
                  }}
                  onDeleteDraft={(row) => void deleteDraft(row)}
                  // `DEF-LED-6723` — the eye. `navigate` and not an `<a>`,
                  // because this is a row ACTION and the row is already a
                  // clickable surface; `journalEntryDetailPath` is the one
                  // definition of the address, imported by the route, by this
                  // caller and by the door test so the three cannot drift.
                  onOpen={(row) =>
                    navigate(tenantPath(journalEntryDetailPath(row.entry_id)))
                  }
                />
                {(journal.data?.unavailable ?? []).map((gap) => (
                  <p key={gap.code} className="fin-absent-reason" role="note">
                    {gapSentence(gap, translate)}
                  </p>
                ))}
              </>
            ) : view === "chart" ? (
              <ChartOfAccountsPanel client={client} now={stamp} t={translate} />
            ) : view === "accruals" ? (
              // ⚠ **`P3.1` — THE VIEW WAS THE SWEEP CARD ALONE UNTIL THIS
              //    COMMIT, AND THE FOUR ENGINES THAT FILL IT HAD NO CALLER.**
              //    Finance blueprint p026 draws 1·4 as TWO cards: *Period-end
              //    entries* — the four engines, previewed then posted — above
              //    *Waiting to reverse*, which is what the view already did and
              //    which its own note 5 marks `EXISTS · Kept`.
              //
              //    Both are components and neither is a function body in this
              //    page (B14 rule 43).
              <>
                <AccrualsWorkbench
                  period={period === null ? null : { start: period.start, end: period.end }}
                  now={stamp}
                  t={translate}
                  client={client}
                  locale={props.locale}
                />
                <AccrualsPanel
                  asOf={period?.end ?? ""}
                  now={stamp}
                  t={translate}
                  client={client}
                  locale={props.locale}
                />
              </>
            ) : (
              <>
            {/* The blueprint's params band for this screen (p023 note 2):
                *"from · to · property. Stays here and not on Journal — it
                describes the period's state, not an entry list"*.

                The period and the basis are FACTS and stay `FactRow`s; the
                property is the one thing here a clerk can CHANGE, so it is a
                control. B14's rule about a row of controls holding only
                pressable things runs the other way too — a filter is not a
                fact and must not be drawn as one. */}
            <div className="fin-params">
              {/* `DEF-LED-10072` P1 · P2 · P8 — the period is a CONTROL now,
                  the shared kit picker the Journal's filter uses too. PO: *"user
                  want filter to and from date you have given but it is plan
                  text"*. It starts on the finance month (P1). */}
              <PeriodPicker
                id="gl.period"
                label={t("finance.gl.period")}
                value={balancePeriod}
                choices={BALANCE_PERIOD_CHOICES}
                today={businessToday}
                month={financeMonth}
                dateFormat={dateFormat}
                layout="row"
                onChange={setBalancePeriod}
              />
              {/* P6 — the date basis stays a FACT. */}
              <FactRow label={t("finance.gl.datedBy")} value={t(`cells.basis.${report.basis}`)} />
              <div className="fin-params-field">
                <PremisesFilterField
                  term={premisesTerm}
                  onTermChange={setPremisesTerm}
                  search={premisesSearch}
                  value={premisesId}
                  onChange={setPremisesId}
                  t={translate}
                />
              </div>
            </div>
            {/* CR-060 C12 — what is still outstanding, on the tab a clerk
                lands on. A failed or absent read draws NOTHING rather than an
                empty strip: this is a convenience beside the trial balance, and
                "0 of 6 done" over an unread checklist is a claim. */}
            {closeChecklist.data === undefined ? null : (
              <CloseReadinessStrip checklist={closeChecklist.data} t={translate} />
            )}
            <TrialBalanceTable
              report={report}
              t={translate}
              locale={props.locale}
              state={tableState}
              onStateChange={setTableState}
            />
            {/* ⚠ **THE PROPERTY-FILTER ABSENCE PANEL WAS HERE AND IS DELETED,
                NOT REWORDED (`DEF-LED-6499`, Finance blueprint `P2.4`).** It
                told a clerk *"the ledger lines carry the dimension; the filter
                itself has not been built"* over a filter `CR-060` C24 served on
                2026-09-03 — `api.py` takes `f.premises` on the trial balance
                AND on the journal, `reporting.py:730` filters on it in SQL, and
                `getTrialBalance` has been sending it ever since. The blueprint's
                own criteria table for this screen marks that row **SERVED**.

                **Removed rather than shortened, because B14 rule 33 puts
                RATIONALE at ZERO words on screen** — why a control is absent is
                the rule's own example, and a control that is no longer absent
                has nothing left to explain. The honest build is the working
                control, which is now in the params band above.

                ⚠ **WHY IT SURVIVED THREE WEEKS, and it is worth more than the
                fix:** its test asserted the sentence was PRESENT and never that
                it was TRUE, so nothing could go red when the filter shipped.
                That is `DEF-2346`'s shape, recorded in the decision log of
                2026-09-03 about this very screen — and it happened again on the
                panel one line below the one that ruling fixed.

                The row-expansion panel that follows is UNTOUCHED: it is still
                true, and `P2.4` is about the false one only. */}
            <Panel className="fin-absent-panel">
              <div className="fin-panel-head">
                <h3>{t("finance.gl.expandTitle")}</h3>
              </div>
              {/* ⚠ RE-VERIFIED 2026-09-03 and this one is TRUE, which is why
                  only its shape moved. `GET /ledger/journal-entries/{id}` is
                  mounted in `apps/ledger/journal_api.py` as DELETE ONLY, no
                  read model returns the entries that hit ONE ledger account,
                  and `reporting.journal_entry_list` has no account filter. The
                  brief for C23 said to find out before building; this is what
                  finding out returned. */}
              <AbsentFigure
                label={t("finance.absent")}
                reason={t("finance.gl.expandUnavailable")}
              />
            </Panel>
            {/* ⚠ **THE JOURNAL LIST AND THE ACCOUNT-MAPPING PANEL WERE HERE
                AND ARE DELETED, NOT MOVED (`DEF-LED-6700`, `DEF-LED-6701`,
                reported by the PO on build 2.351.84).**

                **The journal list.** `P1.15` split this screen in two —
                Finance blueprint p023 note 1, verbatim: *"Balance · was 'Trial
                balance & journal'; the journal moved out to 1·1 · CHANGED ·
                P1.15"*, and the same page's TODAY line names exactly this
                leftover: *"Renders the trial balance and the journal on one
                page. The journal half moves to 1·1"*. The journal branch above
                was ADDED and this copy was never REMOVED, so the split landed
                half-done and a clerk read the same entries twice on one screen.
                `JournalView` is a strict superset of what stood here — the same
                nine columns, the same draft/posted filter as a facet, plus type,
                source and premises filters and the delete-a-draft action — so
                nothing a clerk could see or do is lost.

                ⚠ The page docstring's old exception (6) said this list was *"the
                only place a DRAFT entry is visible at all"*. It was true before
                `P1.15` and is not true now: `JournalView`'s status facet offers
                `draft`, and `JOURNAL_STATUSES` holds both values. The docstring
                is amended in this commit rather than left to be inferred.

                **The account-mapping panel.** Its whole content was one link to
                `?view=chart` — a second door to a view the strip at the TOP of
                this screen already opens. It began as the stand-in for the
                prototype's five hardcoded S56 mapping rows, became a link when
                `GET /ledger/gl-mappings` was served on 2026-08-16, and was never
                removed when the mapping became a VIEW of this same tab (p025
                note 1: *"Chart · was 'Chart of accounts & mapping'"*). p023 gives
                Balance five sections — title, params band, totals, toolbar,
                close checklist — and this is not one of them.

                **Both are removed rather than reworded**, per B14 rule 33: a
                section whose only job was to point somewhere the frame now
                reaches has nothing left to say, and rationale is zero words on
                screen. Why they went is here, in the code, and in the two
                register rows. */}
              </>
            )}
          </>
        )}
      </FinanceBody>
      {modalOpen && (
        <JournalEntryModal
          accounts={pickerAccounts}
          // The tenant's own accounting day (BR-TEN-022), never the browser's:
          // a modal defaulting to `new Date()` would book a Texas clerk's
          // Monday entry into Sunday from a laptop set to UTC (DEF-094).
          defaultEntryDate={period?.end ?? ""}
          now={stamp}
          prefill={prefill}
          client={client}
          locale={props.locale}
          currency={report?.currency ?? null}
          onClose={() => {
            setModalOpen(false);
            setPrefill(null);
          }}
          onPosted={() => {
            setModalOpen(false);
            setPrefill(null);
            void queryClient.invalidateQueries({ queryKey: ["ledger"] });
          }}
        />
      )}
      {reverseTarget !== null && (
        <Panel role="dialog" aria-label={t("finance.journal.reverseTitle")}>
          <div className="fin-panel-head">
            <h3>{t("finance.journal.reverseTitle")}</h3>
          </div>
          {/* BR-LED-003 — reason + audit. A correction with no reason is a
              correction nobody can ever explain to an auditor, so the confirm
              is disabled until one is typed and the server refuses it anyway. */}
          <p className="fin-absent-reason" role="note">
            {t("finance.journal.reverseHelp")}
          </p>
          <label className="fin-params-field">
            {t("finance.journal.reverseReason")}
            <input
              className="input"
              value={reverseReason}
              onChange={(event) => setReverseReason(event.target.value)}
            />
          </label>
          <div className="fin-params-actions">
            <Button
              variant="primary"
              data-testid="confirm-reverse"
              disabled={reverseReason.trim() === ""}
              onClick={() => void confirmReverse()}
            >
              {t("finance.journal.reverseConfirm")}
            </Button>
            <Button variant="ghost"  onClick={() => setReverseTarget(null)}>
              {t("finance.journal.reverseCancel")}
            </Button>
          </div>
          {reverseFailure !== null && (
            <p className="fin-absent-reason" role="alert">
              {reverseFailure}
            </p>
          )}
        </Panel>
      )}
    </div>
  );
}

export default GeneralLedgerPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-008@7e1e359 (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-03-trial-balance-reports.md US-LED-008 §1-§8 · EP-LED-04 US-LED-013 · 09-ledger/02-business-rules.md BR-LED-003/007/009/012 · 12-reports/02-business-rules.md BR-REP-001/002/006/008 · 04-docs/01-spec/11b-api-audit.md §2.10 · 05-prototype/UtilityBilling.html lines 3691-3725 · 12-governance/10-defect-log.csv DEF-112)
// generated: 2026-08-15 by story-coder (DEF-112 lane — `GET /ledger/trial-balance` was SERVED on 2026-08-11 and had no caller)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — `src/features/ledger/generalLedger.test.tsx` failed to resolve `./GeneralLedgerPage` before this file existed; verbatim in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: (1) NO premises filter — ⚠ AMENDED 2026-09-03 (DEF-2347): this clause read "`journal_lines.premises_id` is NULL on every row (US-LED-002 unbuilt)" and US-LED-002 landed 2026-08-16, so every line has carried the stamp for six weeks. The endpoint still does not accept the param — `GET /ledger/trial-balance` takes `from`/`to` only and `GET /ledger/journal-entries` takes `f.type`/`f.status`/`f.source_type`/`q`/`from`/`to` — so the control is still not drawn and a filter that changed nothing would still make the report look filtered. The reason on screen moved from MISSING DATA to a MISSING READ, which is the only part that was wrong. Stated on screen · (2) NO dimension expansion on a GL row: BR-LED-009 asks for it and `GET /ledger/journal-entries/{id}` is named by 11b §2.10 and NOT SERVED — the read that closes it is `apps.ledger.reporting.journal_entry_detail(entry_id)` · (3) NO "+ Record refund" / "+ Journal entry" buttons: both are S57 (EP-LED-04) and every §2.10 WRITE on the journal is unserved · (4) "↓ Export trial balance" renders DISABLED with its reason (BR-SHL-025) — `POST /reports/{key}/export` is served by no deployment (TD-17, no job runner) · (5) ⚠ **AMENDED 2026-09-25 (`DEF-LED-6701`) — THIS READ "the account-mapping panel is a LINK to Settings → Configure" AND THE PANEL IS DELETED.** The mapping is a VIEW of this tab (blueprint p025) and the view strip is its door; a panel whose only content was a second link to it is not one of the five sections p023 gives this screen · (6) ⚠ **AMENDED 2026-09-25 (`DEF-LED-6700`) — THIS READ "the journal list is ADDED to this tab … it is the only place a DRAFT entry is visible at all" AND THE LIST IS DELETED FROM THIS VIEW.** `P1.15` moved the journal to its own view (blueprint p023 note 1) and the branch above renders `JournalView`, whose status facet offers `draft`; this copy was the half of the split that was never removed · (7) `f.status=reversed` is not offered though EP-LED-04's matrix lists it: "reversed" is a LINK, not a status value
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
