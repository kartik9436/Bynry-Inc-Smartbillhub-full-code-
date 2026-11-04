// ── Trace ──────────────────────────────────────────────
// Story:    §05 entry **25.3 `Asks`** of `05-prototype/04 Billing, As Built.pdf`
//           — **p126 is the head, the tiles, group 1 and the table; p127 is the
//           pager, the warning band and the commentary** — read AS IMAGES at
//           scale 2 (B14 rule 42). p128 is 25.4, the customer side that raises
//           the ask. Screens: S67 (this queue) · S66 (25.4) · 25.1 (`Enrol →`)
// Rules:    B14 rule 41 (the product matches the drawing; only a drawing that
//           contradicts a signed rule reaches the PO) · rule 42 (build from the
//           image) · rule 33 (five caps, and RATIONALE is zero words on screen)
//           · rule 32 (one sentence per section; no rule id in clerk-facing
//           copy) · rule 31 (no database id is a field's visible value) ·
//           rule 37 (a drawn figure is an ILLUSTRATION) · rule 40 (the page-head
//           title is 32px) · rule 21 (Tailwind utilities; this file is on
//           `route-b-migrated.txt`) · rule 36 (r10 gives the VISUAL STYLE; the
//           kit is how you comply) · BR-CWP-066 (a portal ask raises an ORDINARY
//           service request) · BR-CWP-026 (a public form links no account) ·
//           NFR-3 (server pagination) · BR-SHL-020 (a tile states an absence,
//           never a substituted 0) · hard-won law 2 and its 2026-09-05 mirror
// Tests:    src/features/billing/budgetAsksPage.dom.test.tsx
// Impacts:  src/App.tsx (the route) · src/features/billing/billingShared.tsx
//           (`BUDGET_ASKS_ROUTE`) · src/features/billing/BudgetBillsTab.tsx
//           (the door) · src/api/billingOpsEndpoints.ts · eleven catalogues ·
//           07-frontend/src/styles/route-b-migrated.txt
// Open:     OQ-BIL-12359 — a level-pay ask carries no route, no account and no
//           record of the level the customer was shown
// ───────────────────────────────────────────────────────
//
// §05 entry 25.3. The clerk's sentence the drawing opens with: *"Six people
// asked online to level their payments. Which can I do, and what were they
// told?"*
//
// ══════════════════════════════════════════════════════════════════════════
// WHOSE TABLE A CUSTOMER'S ASK LIVES IN — THE WHOLE DESIGN, IN SIX LINES
// ══════════════════════════════════════════════════════════════════════════
// `customers.service_requests`, and billing must never own one. The blueprint
// states the rule the product already holds: *"a portal ask raises an ordinary
// service request, never a request of a new kind"* (`BR-CWP-066`).
//
//   25.4 Join  →  portal calls customers' own door, `create_from_portal`
//   25.3 here  →  billing READS through `apps/billing/customers_seam.py`
//   25.1 Enrol →  billing writes `billing.account_budget_status`
//
// Three modules, two boundaries, zero cross-module writes.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE TABLE IS NOT DRAWN TODAY, AND THAT IS A DECISION RATHER THAN A GAP
// ══════════════════════════════════════════════════════════════════════════
// Three of the drawing's seven columns have no source anywhere in the product:
// **which requests are level-pay asks** (the only marker is prose, and the
// constant that builds it lives in `apps/portal`, which billing may not
// import), **the account it is about** (`BR-CWP-026` — *"it links no account
// and changes none"*), and **the level the customer was shown** (captured by
// nothing, anywhere).
//
// So the table renders ONLY when the server stops withholding its rows —
// `rows_unavailable === null`. Drawing headers, a search box and two filter
// chips over rows that cannot arrive is furniture a clerk would type into, and
// `DEF-CWP-3925`'s whole lesson is that a control over nothing costs more than
// a missing one. The COLUMNS are declared below regardless, so the day
// `customers` publishes the read this screen is WIRING and not a rewrite —
// and `test_hold_expires_when_customers_publishes_the_read` goes red that day
// and says so by name.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ WHAT A CLERK GETS INSTEAD, BECAUSE A DEAD END IS NOT AN ANSWER
// ══════════════════════════════════════════════════════════════════════════
// **The asks are already on a worklist** — the requests queue, channel
// *Customer portal*, with the customer's sentence on the row. They are not
// filterable and not actionable from here, which is what `OQ-BIL-12359` is
// about; they are not invisible. The drawing's own note names what a dead end
// costs: *"A customer who asked online and heard nothing asks again by
// telephone."* So the screen carries the door.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ WHERE THE DRAWING AND B14 DISAGREE — RECORDED, NOT BUILT
// ══════════════════════════════════════════════════════════════════════════
// Every divergence is rule 33, and the conformance record numbers them D1–D7.
//
//   · **Group 1, `WHY AN ASK AND NOT AN ENROLMENT`, is not rendered at all.**
//     Four rows — *"The portal may write / rows of exactly six kinds"*, *"What
//     is at stake"*, *"What the portal cannot see"*, *"So the ask is"* — and
//     every one of them answers *why does the product work this way*. Rule 33
//     gives RATIONALE **zero words on screen**: removed, not shortened. It is
//     here, in `budget_api.py`'s own header, and in the conformance record,
//     which is exactly where rule 33 puts it.
//   · **The warning band under the pager is not rendered either**, for the
//     same clause: *"A month can pass between the ask and the enrolment…"* is
//     the reason the two level columns exist, not a fact a clerk acts on. The
//     COLUMNS carry the meaning, which is the drawing's own argument for them.
//   · **`Asks from the portal` (4 words) → `Portal asks`.** Rule 33 caps a
//     heading at three.
//   · **`LEVEL THEY WERE SHOWN` (4) → `Level shown`.**
//   · **The caption claims no count.** The drawing reads *"6 customers have
//     asked to level their payments"*; six is an illustration (rule 37) of a
//     number this screen cannot read, and printing any number would be the
//     `0.00` defect in words.
//
// ⚠ **AND `GapNotes` IS NOT RENDERED ON THIS SCREEN, THOUGH ITS SIBLING TAB
// SHIPS IT.** The server serves `unavailable[]` and this screen does not print
// it: that list explains *why a control is absent*, which is the exact phrase
// rule 33 gives zero words. It stays on the wire for support and for the tests,
// and the screen says what it cannot do in its own catalogue words — the same
// split `DEF-BIL-5316` forced on the enrol form one screen along.

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getBudgetAsks } from "@/api/billingOpsEndpoints";
import type { BudgetAskRow, BudgetAsksResponse } from "@/api/billingOpsEndpoints";
import { ButtonLink } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { KPIStrip } from "@/components/KPIStrip";
import type { KpiTile } from "@/components/KPIStrip";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { InlineLinkTo } from "@/components/Surfaces";
import { accountDetailPath } from "@/features/customers/customersShared";
import { SERVICE_REQUESTS_ROUTE } from "@/features/customers/serviceRequestShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";
import { useState } from "react";

import {
  BILLING_ROUTE,
  BILLING_TABS,
  BILLING_TAB_ALL,
  BUDGET_ENROL_ROUTE,
  BUDGET_TAB_ROUTE,
} from "./billingShared";

export const budgetAsksKey = (page: number, per: number) =>
  ["budget-billing", "asks", page, per] as const;

/**
 * An absence, in the screen's own words — never the server's sentence.
 *
 * ⚠ **IT IS A `role="note"` AND NOT AN ALERT.** Nothing failed: the product
 * does not hold this fact yet, which is a different thing from a read that
 * broke, and a screen that says the same thing in both cases cannot tell a
 * clerk which happened (`G122`'s defect).
 */
function NotHeld(props: { children: string }) {
  return (
    <p
      className="m-0 max-w-measure font-body text-base leading-prose text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]"
      role="note"
      data-bil="asks-not-held"
    >
      {props.children}
    </p>
  );
}

/**
 * §05 entry 25.3's seven drawn columns.
 *
 * ⚠ **DECLARED EVEN THOUGH NO ROW CAN REACH THEM TODAY**, which is the
 * opposite of dead UI and is deliberate: hard-won law 2 is about a control
 * nothing passes to, and this is a SHAPE the server will fill the day
 * `customers` publishes its read. The alternative — adding the columns then —
 * is how a "wiring" job becomes a rewrite, and how the two level columns get
 * quietly collapsed into one by somebody who never read p127.
 *
 * ⚠ **`REFERENCE` AND `ACCOUNT` ARE BUSINESS NUMBERS, NEVER ROW IDS** (B14
 * rule 31). `SR-26-0087` is what a clerk quotes down the telephone and
 * `ACC-10519-C` is what is printed on the paper bill. `account_id` travels on
 * the row for the `Enrol →` link's address and is rendered by nothing.
 */
export function asksTableConfig(
  t: Translator,
  locale: string | undefined,
  tenantPath: (to: string) => string,
): TableConfig<BudgetAskRow> {
  return {
    screenId: "S67",
    getRowId: (row) => row.reference,
    defaultSort: { sort: "asked_on", dir: "desc" },
    columns: [
      {
        key: "reference",
        label: t("billing.budgetAsks.col.reference"),
        identity: true,
        cell: (row) => row.reference,
      },
      {
        key: "account",
        label: t("billing.budgetAsks.col.account"),
        cell: (row) => (
          <span className="flex flex-col">
            {/* Record links (PO 2026-10-19): the number opens the account. */}
            <span>
              <InlineLinkTo to={tenantPath(accountDetailPath(row.account_id))}>
                {row.account_no}
              </InlineLinkTo>
            </span>
            <span className="text-[color-mix(in_srgb,var(--color-text)_62%,transparent)]">
              {row.customer_name}
            </span>
          </span>
        ),
      },
      {
        key: "asked_on",
        label: t("billing.budgetAsks.col.asked"),
        sortable: true,
        cell: (row) => row.asked_on,
      },
      {
        // ⚠ THE TWO LEVEL COLUMNS ARE NOT A DUPLICATE — p127 says so in
        // capitals, and it is the whole reason this screen exists. A month
        // passes, a bill lands, and the quoted figure stops being correct.
        // Showing only one of them breaks a promise silently or enrols at a
        // stale number.
        key: "level_shown",
        label: t("billing.budgetAsks.col.levelShown"),
        numeric: true,
        // ⚠ **A FIGURE WITHOUT ITS CURRENCY IS NOT A FIGURE** (CLAUDE.md rule
        // 2 — money keeps its `CHAR(3)` partner). `MoneyCell` cannot render one
        // and this screen must not pick a currency on a customer's behalf, so
        // an amount whose currency did not travel reads as absent.
        cell: (row) =>
          row.level_shown === null || row.currency === null ? (
            "—"
          ) : (
            <MoneyCell amount={row.level_shown} currency={row.currency} locale={locale} />
          ),
      },
      {
        key: "level_now",
        label: t("billing.budgetAsks.col.levelNow"),
        numeric: true,
        // ⚠ **A FIGURE WITHOUT ITS CURRENCY IS NOT A FIGURE** (CLAUDE.md rule
        // 2 — money keeps its `CHAR(3)` partner). `MoneyCell` cannot render one
        // and this screen must not pick a currency on a customer's behalf, so
        // an amount whose currency did not travel reads as absent.
        cell: (row) =>
          row.level_now === null || row.currency === null ? (
            "—"
          ) : (
            <MoneyCell amount={row.level_now} currency={row.currency} locale={locale} />
          ),
      },
      {
        key: "eligible",
        label: t("billing.budgetAsks.col.eligible"),
        // *"Not eligible is a row, not a rejection"* (p127). `null` is the
        // third state and is neither: nothing could read the plan's flag.
        cell: (row) =>
          row.eligible === null
            ? "—"
            : row.eligible
              ? t("billing.budgetAsks.eligible.yes")
              : (row.not_eligible_because ?? t("billing.budgetAsks.eligible.no")),
      },
      {
        key: "action",
        label: t("billing.budgetAsks.col.action"),
        cell: (row) =>
          // *"It reuses the enrol screen rather than repeating it"* — `Enrol →`
          // opens 25.1 with the account filled in. A LINK, so the door has an
          // address a test can assert and middle-click works.
          row.eligible === false ? (
            <ButtonLink
              variant="secondary"
              to={tenantPath(`${SERVICE_REQUESTS_ROUTE}?q=${encodeURIComponent(row.reference)}`)}
            >
              {t("billing.budgetAsks.tellThemWhy")}
            </ButtonLink>
          ) : (
            <ButtonLink
              variant="secondary"
              to={tenantPath(`${BUDGET_ENROL_ROUTE}?account=${encodeURIComponent(row.account_id)}`)}
            >
              {t("billing.budgetAsks.enrol")}
            </ButtonLink>
          ),
      },
    ],
  };
}

export interface BudgetAsksPageProps {
  client?: ApiClient; // test seam
  locale?: string;
}

export function BudgetAsksPage(props: BudgetAsksPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();

  const [state, setState] = useState<TableRequestState>({
    q: "",
    sort: "asked_on",
    dir: "desc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  });

  const asksQuery = useQuery({
    queryKey: budgetAsksKey(state.page, state.per),
    queryFn: () => getBudgetAsks({ page: state.page, per: state.per }, client),
    retry: false,
  });
  const data: BudgetAsksResponse | undefined = asksQuery.data;
  const summary = data?.summary;

  // ⚠ **A TILE STATES AN ABSENCE; IT NEVER SHOWS A SUBSTITUTED `0`**
  // (`BR-SHL-020`). `0` on `Waiting` says *nobody asked*; a dash with a line
  // under it says *nobody could ask*, and on a screen about six people waiting
  // for a telephone call those are not the same statement.
  const kpis: KpiTile[] = [
    {
      id: "waiting",
      label: t("billing.budgetAsks.kpi.waiting"),
      value: summary?.waiting ?? "—",
      detail:
        summary?.waiting === null || summary?.waiting === undefined
          ? t("billing.budgetAsks.kpi.notRecorded")
          : undefined,
    },
    {
      id: "eligible",
      label: t("billing.budgetAsks.kpi.eligible"),
      value: summary?.eligible_now ?? "—",
      detail:
        summary?.eligible_now === null || summary?.eligible_now === undefined
          ? t("billing.budgetAsks.kpi.notRecorded")
          : undefined,
    },
    {
      id: "notEligible",
      label: t("billing.budgetAsks.kpi.notEligible"),
      value: summary?.not_eligible ?? "—",
      detail:
        summary?.not_eligible === null || summary?.not_eligible === undefined
          ? t("billing.budgetAsks.kpi.notRecorded")
          : undefined,
    },
    {
      id: "enrolledThisMonth",
      // The one real figure on this screen: billing's own rows, billing's own
      // date. The drawn detail line *"3 from the portal"* is an illustration
      // (rule 37) of a provenance nothing records.
      label: t("billing.budgetAsks.kpi.enrolled"),
      value: summary?.enrolled_this_month ?? "—",
      detail: t("billing.budgetAsks.kpi.originNotHeld"),
    },
  ];

  const rowsWithheld = data?.rows_unavailable !== null && data?.rows_unavailable !== undefined;

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={t("billing.budgetAsks.title")}
        rollup={t("billing.budgetAsks.caption")}
        backTo={{
          to: tenantPath(BUDGET_TAB_ROUTE),
          label: t("billing.budgetAsks.back"),
        }}
        tabs={BILLING_TABS.map((tab) => ({ id: tab.id, label: t(tab.labelKey) }))}
        activeTabId="budget"
        tabsLabel={t("billing.tabsLabel")}
        onTabSelect={(tab) =>
          navigate(
            tenantPath(tab.id === BILLING_TAB_ALL ? BILLING_ROUTE : `${BILLING_ROUTE}/${tab.id}`),
          )
        }
      />

      <KPIStrip kpis={kpis} loading={asksQuery.isPending} />

      <Panel as="section">
        <h3>{t("billing.budgetAsks.queueTitle")}</h3>

        {rowsWithheld ? (
          <div className="flex flex-col items-start gap-3">
            {/* ⚠ ONE SENTENCE, SIX WORDS, AND NOT ONE OF THEM EXPLAINS WHY
                (rule 33: rationale is zero words on screen). What a clerk needs
                from this screen today is WHERE THE ASKS ARE, and that is the
                next line down — a door, not a paragraph. */}
            <NotHeld>{t("billing.budgetAsks.notHeld")}</NotHeld>
            <ButtonLink variant="primary" to={tenantPath(SERVICE_REQUESTS_ROUTE)}>
              {t("billing.budgetAsks.openRequests")}
            </ButtonLink>
          </div>
        ) : (
          <DataTable<BudgetAskRow>
            config={asksTableConfig(translate, props.locale, tenantPath)}
            state={state}
            onStateChange={setState}
            rows={data?.results ?? []}
            totalRows={data?.count ?? null}
            loading={asksQuery.isPending}
            // ⚠ **NO CTA, AND THAT IS `DEF-MET-4764`'s CLAUSE RATHER THAN AN
            // OVERSIGHT.** Nothing a clerk does on this screen CREATES an ask —
            // a customer does, in the portal — so an empty state offering a
            // button would wire a live control onto nothing. The empty state
            // here is a good state: everybody who asked has been answered.
            empty={{
              title: t("billing.budgetAsks.empty"),
              helper: t("billing.budgetAsks.emptyHelper"),
            }}
            error={
              asksQuery.isError
                ? { reason: t("billing.budgetAsks.failed"), onRetry: () => void asksQuery.refetch() }
                : undefined
            }
          />
        )}
      </Panel>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: §05 entry 25.3 of `05-prototype/04 Billing, As Built.pdf` p126–p127
//         (images, B14 rule 42) + BR-CWP-026/066 + NFR-3 + BR-SHL-020 +
//         B14 rules 21/31/32/33/36/37/40/41/42
// generated: 2026-09-15 by the §05 entry 25.3 build lane
// checklist: A✔ B✔ C✔ D✔(GET /budget-billing/asks, mounted) E✔(routed at
//         /:tenant/billing/budget/asks and doored from the Budget Bills tab)
//         F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/billing · G31 (this file is on
//         route-b-migrated.txt) · every assertion driven RED first
// exceptions: (1) the TABLE renders only when the server stops withholding —
//         OQ-BIL-12359 · (2) group 1 and the warning band are RATIONALE and
//         are not rendered (rule 33) · (3) `GapNotes` is not rendered here
//         though the sibling tab ships it, for the same clause
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
