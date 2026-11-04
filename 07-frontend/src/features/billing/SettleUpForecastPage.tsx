// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-019 (the budget bill: variance on every bill, the annual
//           settle-up) — the FORECAST, which had no endpoint and no screen.
//           Screens: §05 entry **25.2 `Settle-up forecast`** of
//           `05-prototype/04 Billing, As Built.pdf` — p124(low)–p126(top), read
//           AS IMAGES at scale 2 (B14 rule 42). p125 carries the drawn frame;
//           p125–p126 are its commentary. Entry 25 (p121–p122) is the tab this
//           screen is reached from and entry 25.1 (p122–p124) is its sibling.
// Rules:    B14 rule 41 (the product matches the drawing; only a drawing that
//           contradicts a signed rule reaches the PO) · rule 42 (build from the
//           image) · rule 37 (every figure drawn in a wireframe is an
//           ILLUSTRATION, never a fact to build to) · rule 33 (five caps, and
//           RATIONALE is zero words on screen) · rule 32 (one sentence per
//           section; no rule id in clerk-facing copy) · rule 31 (no database id
//           is a field's visible value) · rule 40 (the page-head title is 32px)
//           · rule 21 (Tailwind utilities; this file is on
//           `route-b-migrated.txt`) · rule 36 (r10 gives the VISUAL STYLE; the
//           kit is how you comply) · rule 19 (this list's own search prompt) ·
//           rule 16 (the pagination footer) · BR-BIL-017 (the annual settle-up
//           month, COPIED onto the account at enrolment) · BR-BIL-011 (the
//           monthly posting is the ACTUALS posting) · CLAUDE.md rule 2 (money
//           4dp, display 2, never a float) · NFR-3 (the page is cut in SQL) ·
//           hard-won law 2 and its 2026-09-05 mirror
// Tests:    src/features/billing/settleUpForecastPage.dom.test.tsx
// Impacts:  src/App.tsx (the route) · src/features/billing/BudgetBillsTab.tsx
//           (the door) · src/api/billingOpsEndpoints.ts (the read) ·
//           07-frontend/src/styles/route-b-migrated.txt · eleven catalogues
// ───────────────────────────────────────────────────────
//
// §05 entry 25.2. The clerk's sentence the drawing opens with: *"Who is going
// to be trued up, when, and for how much — so I can answer them before they
// ring?"*
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THERE IS NO BUTTON HERE ON PURPOSE — AND THAT IS THE DRAWING'S OWN RULING
// ══════════════════════════════════════════════════════════════════════════
// An earlier version of this drawing offered a bulk **"Settle these 2"**. The
// blueprint withdrew it and recorded why, *"corrected here rather than quietly
// removed, because the reasoning is the thing worth keeping"*: the cycle run
// already posts the settle-up, on the account's own bill, inside the same write
// that creates it, **idempotently per invoice**. A bulk button would have been
// **a second writer for the same money**.
//
// So this screen reads and nothing else. There is no mutation in this file, no
// `useMutation`, and `GET /budget-billing/settle-up-forecast` has no sibling
// POST to call. Its test asserts the absence, because a comment claiming a
// guarantee is not the guarantee (hard-won law 1).
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE SIGN HERE IS THE OPPOSITE OF THE SIBLING'S, AND NEITHER IS A FLIP
// ══════════════════════════════════════════════════════════════════════════
// `BudgetBillsTab` says, correctly, *"the variance sign is the engine's and not
// the drawing's… nothing here flips a sign"* — and it shows `variance_balance`,
// where ❄️ WE-8's **−50.87** is the month the customer under-paid.
//
// **This screen shows a different fact.** Screen 25 draws the POSITION an
// account is in; 25.2 draws the TRANSACTION that is coming — *"will we collect
// or credit, and how much"*. The engine publishes that as `budget.SettleUp`,
// whose `amount` is always positive, whose `direction` carries the sign, and
// whose `signed` property reads, in its own docstring, *"+ collects, −
// credits"* — **exactly the drawn column**. So `balance_signed` comes off the
// ❄️ frozen dataclass and **nothing here negates anything either**. Two screens,
// two facts, one engine, no flip.
//
// ══════════════════════════════════════════════════════════════════════════
// NO ARITHMETIC IN THIS FILE, AND THE THREE COLUMNS PROVE IT
// ══════════════════════════════════════════════════════════════════════════
// `PAID ON THE LEVEL`, `ACTUAL SO FAR` and `BALANCE` are three decimal strings
// the server computed, and they tie out there (a billed event's movement IS
// `level − actual`, so over one settle-up period `Σlevel − Σactual` is the
// balance). The browser adds nothing — which is the rule entry 25.1's lane
// applied when it refused to sum twelve monthly figures client-side, and it
// matters more here because a clerk reads all three out loud on one telephone
// call.
//
// ══════════════════════════════════════════════════════════════════════════
// WHERE THIS DIVERGES FROM THE DRAWING, AND WHY — every one is rule 33
// ══════════════════════════════════════════════════════════════════════════
// Rule 41 makes the drawing the specification and rule 33 is a signed rule the
// drawn PROSE exceeds, so the structure is built exactly and the words are cut
// to the caps. Nothing drawn is dropped except what rule 33 gives zero words:
//
//   · **"There is no button here on purpose. A second way to settle the same
//     money is a second answer to it."** — RATIONALE, *why a control is
//     absent*, which rule 33 puts at **zero words on screen**. It lives in this
//     docstring, in `budget_api.budget_settle_up_forecast` and in the
//     conformance record. ⚠ Rule 33's own note: rationale is REMOVED, not
//     shortened — cutting it to six words would keep the breach and make it
//     terser.
//   · **"What this screen is for / Seeing it coming, and answering the customer
//     who rings to ask"** — the same thing, so the `WHERE IT HAPPENS` table is
//     the three FACTUAL rows and not four.
//   · **Headings trimmed to three words**: `NOTHING ON THIS SCREEN WRITES
//     ANYTHING` → `Where it posts`; `LATER IN THE YEAR` → `Later this year`;
//     `PAID ON THE LEVEL` → `Paid on level`.
//   · **"Accounts do not all settle together. Each one carries the settle-up
//     month it was enrolled with, so this list spans nine months."** — the
//     second sentence is rationale; the first is a FACT a clerk needs, kept as
//     `Accounts settle in different months` (5 words).
//
// ⚠ **AND `Export` IS DRAWN, RENDERED AND REFUSED WITH ITS REASON —
// `DEF-BIL-5328`.** `EXPORT_RESOURCES` is a closed list of eleven and none of
// them is a budget list: BR-SHL-010 makes the SERVER's capability row the
// config, so `ListExportButton` has nothing to point at, and a working-looking
// button over that gap is the dead control hard-won law 2's mirror is about.
// Greyed-with-a-reason is the blueprint's own doctrine one page earlier (p121).
// **The hold carries the test that fires when it expires** — the day a
// settle-up export resource is registered, `settleUpForecastPage.dom.test.tsx`
// goes red and names this button.
import { useMemo, useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getSettleUpForecast } from "@/api/billingOpsEndpoints";
import type {
  SettleUpForecastRow,
  SettleUpForecastSummary,
} from "@/api/billingOpsEndpoints";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { formatMonthYear } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { InlineLinkTo } from "@/components/Surfaces";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useRegional } from "@/features/metering/meteringShared";
import { accountDetailPath } from "@/features/customers/customersShared";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { GapNotes } from "./billingOpsShared";
import {
  BILLING_ROUTE,
  BILLING_TAB_ALL,
  BILLING_TABS,
  BUDGET_TAB_ROUTE,
} from "./billingShared";

export const settleUpForecastKey = (scope: string) =>
  ["budget-billing", "settle-up-forecast", scope] as const;

/** The two directions the engine publishes. Never hand-typed as strings in a
 *  cell: CLAUDE.md's *"never hand-type a list"* is why an eleventh utility
 *  service still does not appear on the sign-up screen. */
const DIRECTION_COLLECT = "collect";
const DIRECTION_CREDIT = "credit";

const MUTED = "text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]";

/**
 * A money cell, or the absence in words.
 *
 * ⚠ **NULL IS AN ABSENCE AND NEVER `0.00`.** An account with no bill inside its
 * current settle-up period has had nothing asked of it and its meter has said
 * nothing; `$0.00` says both of those happened and came to zero.
 */
function MoneyOrAbsent(props: {
  amount: string | null;
  currency: string;
  locale?: string;
  absent: string;
}) {
  if (props.amount === null) {
    return <span className={MUTED}>{props.absent}</span>;
  }
  return <MoneyCell amount={props.amount} currency={props.currency} locale={props.locale} />;
}

interface ForecastView {
  t: Translator;
  locale: string | undefined;
  timeZone: string;
  accountHref: (row: SettleUpForecastRow) => string;
}

/**
 * The drawn table: ACCOUNT · SETTLES IN · PAID ON THE LEVEL · ACTUAL SO FAR ·
 * BALANCE · WILL. Six columns, in that order.
 *
 * ⚠ **THE DRAWN FIGURES ARE ILLUSTRATIONS (B14 rule 37)** — `100412 / Navarro,
 * P.`, `+$212.80`, `Showing 1–37 of 37`. Not one of them is asserted anywhere;
 * what is built is the SHAPE they illustrate.
 */
function forecastTableConfig(view: ForecastView): TableConfig<SettleUpForecastRow> {
  const { t, locale, timeZone } = view;
  return {
    screenId: "S30.budget.settleUp",
    // The drawn placeholder is the contract (B14 rule 19) and these are the
    // SAME three legs the server searches — `selectors.budget_apply_search`,
    // shared with the Budget Bills tab, so one term means one thing on both.
    searchFields: ["account_no", "customer_name", "address"],
    searchPlaceholder: "billing.budget.search",
    filters: [
      {
        name: "month",
        label: t("billing.settleUp.filter.monthLabel"),
        // Twelve months, DERIVED from `Intl` through the product's one
        // month-year formatter — never a hand-typed list of month names, which
        // would be a twelfth catalogue nobody translates.
        options: Array.from({ length: 12 }, (_unused, index) => ({
          value: String(index + 1),
          label: formatMonthYear(
            `2026-${String(index + 1).padStart(2, "0")}-01`,
            timeZone,
            locale,
          ).split(" ")[0],
        })),
      },
      {
        name: "direction",
        label: t("billing.settleUp.filter.directionLabel"),
        options: [
          { value: DIRECTION_COLLECT, label: t("billing.settleUp.will.collect") },
          { value: DIRECTION_CREDIT, label: t("billing.settleUp.will.credit") },
        ],
      },
    ],
    // Nearest first — the drawing lists Nov 2026 above Jan 2027 above Mar 2027.
    // The ORDER is the server's (`months_away`, cut in SQL), so the sort the
    // screen declares and the rows it receives cannot disagree.
    defaultSort: { sort: "months_away", dir: "asc" },
    getRowId: (row) => row.account_id,
    columns: [
      {
        key: "account",
        label: t("billing.settleUp.col.account"),
        identity: true,
        cell: (row) => (
          <>
            {/* B14 rule 31 — the HUMAN-FACING number is the visible value and
                the id rides the `href`, where it is not visible and the rule is
                not engaged. The drawing paints the number in the accent, which
                is how this document draws every door (`DEF-BIL-5325` is the
                sibling column that was drawn as a door and rendered as text). */}
            <InlineLinkTo to={view.accountHref(row)}>
              {row.account_no ?? t("billing.budget.noAccountNo")}
            </InlineLinkTo>
            <span className="block text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
              {row.customer_name ?? t("billing.budget.noCustomerName")}
            </span>
          </>
        ),
      },
      {
        key: "settles_in",
        label: t("billing.settleUp.col.settlesIn"),
        // `Nov 2026`, through the product's ONE month-year formatter
        // (BR-SHL-023). `DEF-BIL-5324` is the sibling cell that printed
        // `2027-01` by building the string itself.
        cell: (row) => (
          <strong>
            {formatMonthYear(
              `${row.settles_in_year}-${String(row.settles_in_month).padStart(2, "0")}-01`,
              timeZone,
              locale,
            )}
          </strong>
        ),
      },
      {
        key: "paid_on_level",
        label: t("billing.settleUp.col.paidOnLevel"),
        numeric: true,
        cell: (row) => (
          <MoneyOrAbsent
            amount={row.paid_on_level}
            currency={row.currency}
            locale={locale}
            absent={t("billing.settleUp.absent.noBills")}
          />
        ),
      },
      {
        key: "actual_so_far",
        label: t("billing.settleUp.col.actualSoFar"),
        numeric: true,
        cell: (row) => (
          <MoneyOrAbsent
            amount={row.actual_so_far}
            currency={row.currency}
            locale={locale}
            absent={t("billing.settleUp.absent.noBills")}
          />
        ),
      },
      {
        key: "balance",
        label: t("billing.settleUp.col.balance"),
        numeric: true,
        // The drawing puts a COLLECTION in the accent and leaves a credit
        // plain: money the utility is about to ask a customer for is the half
        // that starts a telephone call.
        cell: (row) =>
          row.balance_signed === null ? (
            <span className={MUTED}>{t("billing.settleUp.absent.nothingDue")}</span>
          ) : row.settle_up_direction === DIRECTION_COLLECT ? (
            <strong className="text-accent-700">
              <MoneyCell
                amount={row.balance_signed}
                currency={row.currency}
                locale={locale}
              />
            </strong>
          ) : (
            <MoneyCell amount={row.balance_signed} currency={row.currency} locale={locale} />
          ),
      },
      {
        key: "will",
        label: t("billing.settleUp.col.will"),
        cell: (row) =>
          row.settle_up_direction === DIRECTION_COLLECT ? (
            <>{t("billing.settleUp.will.collect")}</>
          ) : row.settle_up_direction === DIRECTION_CREDIT ? (
            <>{t("billing.settleUp.will.credit")}</>
          ) : (
            // Exactly zero to true up. `budget.settle_up` returns no line at
            // all for that, and the drawing has no third word — so the cell
            // states it rather than picking one of the two.
            <span className={MUTED}>{t("billing.settleUp.will.nothing")}</span>
          ),
      },
    ],
  };
}

/** The drawn four tiles: SETTLING THIS MONTH · TO COLLECT · TO CREDIT · LATER. */
function forecastTiles(
  summary: SettleUpForecastSummary | undefined,
  t: Translator,
  locale: string | undefined,
  timeZone: string,
): KpiTile[] {
  const dash = "—";
  const monthName =
    summary === undefined
      ? undefined
      : formatMonthYear(
          `${summary.settling_year}-${String(summary.settling_month).padStart(2, "0")}-01`,
          timeZone,
          locale,
        ).split(" ")[0];
  // ⚠ The two money tiles are `value`, not `money`. A `KpiMoney` requires a
  // BR-REP-001 date basis and the three the kit offers — posting, clearing,
  // priced — are all statements about something that has HAPPENED. A forecast
  // has not; declaring one would put a false label under a real figure.
  const collectTotal =
    summary === undefined || summary.to_collect_amount === null || summary.currency === null
      ? null
      : summary.to_collect_amount;
  const creditTotal =
    summary === undefined || summary.to_credit_amount === null || summary.currency === null
      ? null
      : summary.to_credit_amount;
  const mixed = summary !== undefined && summary.currencies.length > 1;
  return [
    {
      id: "settling",
      label: t("billing.settleUp.kpi.settling"),
      value: summary === undefined ? dash : summary.settling_this_month,
      detail: monthName,
    },
    {
      id: "collect",
      label: t("billing.settleUp.kpi.toCollect"),
      value:
        collectTotal === null || summary === undefined || summary.currency === null ? (
          // CLAUDE.md rule 2 — two currencies do not add. The COUNT below is
          // still true and the total is withheld rather than invented.
          <span className={MUTED}>{dash}</span>
        ) : (
          <MoneyCell amount={collectTotal} currency={summary.currency} locale={locale} />
        ),
      detail:
        summary === undefined ? undefined : mixed ? (
          <span className={MUTED}>{t("billing.settleUp.kpi.mixed")}</span>
        ) : (
          t("billing.settleUp.kpi.accounts", { count: summary.to_collect_accounts })
        ),
    },
    {
      id: "credit",
      label: t("billing.settleUp.kpi.toCredit"),
      value:
        creditTotal === null || summary === undefined || summary.currency === null ? (
          <span className={MUTED}>{dash}</span>
        ) : (
          <MoneyCell amount={creditTotal} currency={summary.currency} locale={locale} />
        ),
      detail:
        summary === undefined ? undefined : mixed ? (
          <span className={MUTED}>{t("billing.settleUp.kpi.mixed")}</span>
        ) : (
          t("billing.settleUp.kpi.accounts", { count: summary.to_credit_accounts })
        ),
    },
    {
      id: "later",
      label: t("billing.settleUp.kpi.later"),
      value: summary === undefined ? dash : summary.later_accounts,
      detail:
        summary === undefined
          ? undefined
          : t("billing.settleUp.kpi.otherMonths", { count: summary.later_months }),
    },
  ];
}

/**
 * Group 1 — `WHERE IT HAPPENS`. Three facts, each ≤ 6 words (B14 rule 33).
 *
 * The drawing's fourth row (*"What this screen is for / Seeing it coming…"*)
 * is RATIONALE and rule 33 gives rationale zero words on screen; it is in this
 * file's header, where the rule says to put it.
 */
function WhereItPosts(props: { t: Translator }) {
  const { t } = props;
  const rows: Array<[string, string]> = [
    [t("billing.settleUp.posts.line"), t("billing.settleUp.posts.lineValue")],
    [t("billing.settleUp.posts.who"), t("billing.settleUp.posts.whoValue")],
    [t("billing.settleUp.posts.redraft"), t("billing.settleUp.posts.redraftValue")],
  ];
  return (
    <Panel as="section">
      <h3>{t("billing.settleUp.posts.heading")}</h3>
      <table className="w-full border-collapse">
        <tbody>
          {rows.map(([label, value]) => (
            <tr key={label} className="border-b border-divider last:border-b-0">
              <th
                scope="row"
                className="w-[240px] py-2 pr-4 text-left font-heading text-base font-normal text-[color-mix(in_srgb,var(--color-text)_70%,transparent)] max-sm:w-auto"
              >
                {label}
              </th>
              <td className="py-2 font-body text-base leading-normal">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

export interface SettleUpForecastPageProps {
  client?: ApiClient;
  locale?: string;
}

export function SettleUpForecastPage(props: SettleUpForecastPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  // The shell's publication, never `GET /settings/regional` — that route is
  // Admin-only and a billing clerk meets a refusal on it (`DEF-SHL-4283`).
  // DEF-SHL-3964: `useRegional` and no hand-written fallback (DEF-SHL-9122).
  const { timeZone } = useRegional({});

  const [state, setState] = useState<TableRequestState>({
    q: "",
    sort: "months_away",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  });

  const listQuery = useQuery({
    queryKey: settleUpForecastKey(
      `${state.filters.month ?? ""}|${state.filters.direction ?? ""}|${state.q}|${state.page}|${state.per}`,
    ),
    queryFn: () =>
      getSettleUpForecast(
        {
          month: state.filters.month,
          direction: state.filters.direction,
          q: state.q,
          page: state.page,
          per: state.per,
          // ⚠ NO `asOf`. The horizon is the SERVER's today: a browser clock and
          // a server clock disagree across a timezone, and which month counts
          // as "this month" decides a whole tile.
        },
        client,
      ),
    retry: false,
  });
  const data = listQuery.data;

  const view = useMemo<ForecastView>(
    () => ({
      t: translate,
      locale: props.locale,
      timeZone,
      accountHref: (row) => tenantPath(accountDetailPath(row.account_id)),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [props.locale, timeZone, tenantPath, t],
  );
  const tableConfig = useMemo(() => forecastTableConfig(view), [view]);
  const tiles = forecastTiles(data?.summary, translate, props.locale, timeZone);

  const neverSettle = data?.summary.no_settle_month ?? 0;

  return (
    <div className="px-4 pt-6 pb-8">
      {/* B14 rule 2 — ONE page header; rule 40 puts its title at 32px. The tab
          strip stays under it with `Budget Bills` active, exactly as the
          drawing keeps it, so a clerk can see where they are. */}
      <PageHeader
        title={t("billing.settleUp.title")}
        rollup={t("billing.settleUp.caption")}
        secondaryActions={
          <>
            {/* DRAWN, RENDERED AND REFUSED WITH ITS REASON — `DEF-BIL-5328`.
                No export resource exists for this list, and BR-SHL-010 makes
                the server's capability row the config. `title` carries the
                reason without spending a word of the screen's budget on it. */}
            <Button variant="secondary" disabled title={t("billing.settleUp.exportWhy")}>
              {t("billing.settleUp.export")}
            </Button>
            <Button variant="secondary" onClick={() => navigate(tenantPath(BUDGET_TAB_ROUTE))}>
              {t("billing.settleUp.back")}
            </Button>
          </>
        }
        tabs={BILLING_TABS.map((tab) => ({ id: tab.id, label: t(tab.labelKey) }))}
        activeTabId="budget"
        tabsLabel={t("billing.tabsLabel")}
        onTabSelect={(tab) =>
          navigate(
            tenantPath(tab.id === BILLING_TAB_ALL ? BILLING_ROUTE : `${BILLING_ROUTE}/${tab.id}`),
          )
        }
      />

      <KPIStrip kpis={tiles} loading={listQuery.isPending} />

      {/* ── 1 · WHERE IT POSTS ───────────────────────────────────────────── */}
      <WhereItPosts t={translate} />

      {/* ── THE TABLE ────────────────────────────────────────────────────── */}
      <Panel as="section">
        <DataTable<SettleUpForecastRow>
          config={tableConfig}
          state={state}
          onStateChange={setState}
          rows={data?.results ?? []}
          totalRows={data?.count ?? null}
          loading={listQuery.isPending}
          error={
            listQuery.isError
              ? {
                  reason: apiErrorText(listQuery.error, translate),
                  onRetry: () => void listQuery.refetch(),
                }
              : null
          }
          empty={{
            title: t("billing.settleUp.empty"),
            helper: t("billing.settleUp.emptyHelper"),
          }}
          filterBarSlot={
            <FilterBar
              filters={tableConfig.filters ?? []}
              state={state}
              onStateChange={setState}
            />
          }
        />
        {/* The drawing's caption under the table. Its second sentence is
            rationale and rule 33 removes it; this half is the fact. */}
        <p className={`m-0 mt-3 font-body text-base leading-normal ${MUTED}`}>
          {t("billing.settleUp.spansMonths")}
        </p>
        {/* ⚠ A STATED ABSENCE, NOT A QUIETLY SHORTER LIST. An enrolled account
            whose tenant published no settle-up month never trues up, so it is
            not a row here — and a forecast that silently covered fewer people
            than are enrolled is worse than one that says so. */}
        {neverSettle > 0 && (
          <p className={`m-0 mt-2 font-body text-base leading-normal ${MUTED}`} role="note">
            {t("billing.settleUp.neverSettle", { count: neverSettle })}
          </p>
        )}
      </Panel>

      <GapNotes gaps={data?.unavailable ?? []} t={translate} />
    </div>
  );
}

export default SettleUpForecastPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: §05 entry 25.2 of 05-prototype/04 Billing, As Built.pdf (p124-p126,
//         read as images at scale 2) · 04-docs/05-modules/07-billing/
//         02-business-rules.md BR-BIL-011/017/021 · 08-worked-examples.md WE-8 ·
//         04-docs/02-decisions/14-ui-conventions.md B14 · 06-backend/apps/
//         billing/budget.py + budget_api.py
// generated: 2026-09-15 by the S80 settle-up forecast lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E3 the bulk "Settle these 2" is NOT built — the blueprint
//         withdrew it and the cycle run is the only writer (see the header) ·
//         E3 `Export` is drawn, rendered and DISABLED with its reason:
//         EXPORT_RESOURCES holds no budget list and BR-SHL-010 makes the
//         server's capability row the config (DEF-BIL-5328), and the hold
//         carries the test that fires when it expires · E3 the four drawn
//         commentary sentences are RATIONALE and B14 rule 33 gives rationale
//         ZERO words on screen — removed, not shortened · E3 every money
//         figure is a decimal STRING rendered through MoneyCell; nothing in
//         this file adds, subtracts or negates money · E3 a null money column
//         renders as a stated absence and NEVER as 0.00 · E3 the month filter's
//         twelve options are DERIVED through `Intl`, never hand-typed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
