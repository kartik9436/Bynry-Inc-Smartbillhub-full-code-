// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-015 (which tier has already gone, so a manual send never
//           doubles one) · US-PAY-018 (the plan-notice and missed-instalment
//           position) · US-PAY-019 (the dunning + disconnect pause, and why
//           collections is or is not running for an account) · US-PAY-014 (the
//           ladder this previews without stepping it)
//           Screens: S34 (the collections board) · S21 (the account position)
// Rules:    BR-PAY-016 (dunning resumes the day AFTER a missed instalment; the
//           plan stays ACTIVE and nobody is dropped — PO 2026-08-12, OQ-170) ·
//           BR-PAY-017 (the four rungs and the five stop conditions) ·
//           BR-CUS-043 (the pause covers the ARREARS THE PLAN SPREADS, never
//           this month's bill) · BR-PAY-029 (collections lists read balance
//           high → low) · B14 rule 31 (nothing internal is ever visible to a
//           utility user — the ACCOUNT column shows the NUMBER) · B14 rule 33
//           (a FACT is at most six words) · BR-SHL-020 · BR-SHL-023 ·
//           BR-SHL-025 · BR-SHL-044
// ───────────────────────────────────────────────────────
// The collections board — WHO IS AT WHICH TIER, AND WHAT GOES NEXT.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS SCREEN EXISTS
// ══════════════════════════════════════════════════════════════════════════
// `POST /collections/run` has existed since the ladder shipped, and it SENDS:
// it writes the notice, advances the tier and records a `notice_history` row on
// every path, skips included. **There was no way to look first.** A clerk
// selected accounts on S34 and drove a five-stop-condition engine over them
// without being able to see which tier each account had already had, what would
// go next, or which of them the rules would silently pass over. Every one of
// those skips is a customer nobody contacted.
//
// This screen is the look. It calls a READ that steps nothing, and the guarantee
// is asserted by a backend test rather than promised in a comment: opening this
// page must not advance anybody's tier.
//
// ══════════════════════════════════════════════════════════════════════════
// THE THREE-VALUED "RUNS" COLUMN — AND WHY IT IS NOT A BOOLEAN
// ══════════════════════════════════════════════════════════════════════════
//   `true`   the ladder steps this account today
//   `false`  a rule stopped it, and `skip_reason` names which
//   `null`   **this deployment cannot say**, because no balance floor could be
//            read (BR-PAY-017 · OQ-137 · OQ-157)
//
// A boolean would collapse the third into the second, and "we did not chase
// them" and "we cannot tell you whether we will" are different sentences to say
// to a utility. When the third state is live the board still shows every
// account, every balance and every tier already sent — an honest partial answer
// rather than a blank screen or a plausible next step.
import { useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getCollectionsLadder } from "@/api/bankRecEndpoints";
import type { LadderBoardRow } from "@/api/bankRecEndpoints";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { clientPage } from "@/components/clientTable";
import type { ClientTableSpec } from "@/components/clientTable";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { KPIStrip } from "@/components/KPIStrip";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { Kicker } from "@/components/TextBits";
import { Panel } from "@/components/Panel";
import { InlineLinkTo } from "@/components/Surfaces";
import { isDenied, useAccessCell } from "@/features/metering/meteringShared";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

// `CR-136-BRC07` `P2.7` — the counter door, one component for every payments
// page head (B14 rule 43).
import { CounterHeadSlot } from "./CounterDoors";
import { GapNotes, bankRecRouteAbsent } from "./depositsShared";
// ONE pill vocabulary for both ladder surfaces — 7·1's LADDER column and
// this board must not colour the same rung differently (B14 rule 36).
import { debtorDetailPath, ladderTone } from "./debtorsTable";
import {
  COLLECTIONS_LADDER_ROUTE,
  PAYMENTS_PERMISSION,
  PAYMENTS_TABS,
  PAYMENTS_TAB_COLLECTIONS,
  PAYMENTS_TAB_OUTSTANDINGS,
  collectionTierLabel,
  ladderSkipLabel,
  paymentsStripSelection,
  paymentsTabPath,
} from "./paymentsShared";

import "./payments.css";

/** ⚠ **RE-EXPORT, NOT A SECOND DEFINITION (`P0.8`).** The address moved to
 *  `paymentsShared` when the Debtors tab had to name it — see that file. This
 *  name stays because App.tsx and four tests import it. */
export const COLLECTIONS_ROUTE = COLLECTIONS_LADDER_ROUTE;
export const collectionsQueryKey = (asOf: string) => ["payments", "collections", asOf] as const;

/** Today, as an ISO date, from the BROWSER — which is the legitimate reading of
 *  BR-TEN-043: the caller states the business day and the SERVER never reads a
 *  clock. It is also editable on the screen, because a clerk previewing
 *  tomorrow's run needs tomorrow's board. */
export function todayIso(now: Date = new Date()): string {
  return now.toISOString().slice(0, 10);
}

// ── The board ─────────────────────────────────────────────────────────────

export /**
 * ⚠ **THE LADDER BOARD IS THE KIT'S TABLE NOW — `CR-138-BRC07` `P4.9`.**
 *
 * The blueprint's 7·3a Table-controls row is four words: ***"All four absent
 * today."*** One filter chip and a date field, on a plain table. So this
 * gains, from `DataTable` and therefore identically to every other list in the
 * product: **the toolbar** (rule 12), **⇅ headers** (rule 13), **the ▦
 * chooser** (rule 14) and **a pagination footer** (rule 16).
 *
 * ⚠ **NOT ONE CELL'S BEHAVIOUR MOVES.** Every three-valued branch below is the
 * one that was here before, word for word: `runs === null` still means *this
 * deployment cannot say*, a skip still renders its reason, and `days_late`
 * null still refuses to read as zero. A migration that promises to move no
 * pixel has no business rewriting a judgment about what a null means.
 *
 * ⚠ **AND THE PAGING RUNS IN THE BROWSER, WHICH IS `P4.2`'s SEAM AND NOT AN
 * ANSWER TO IT.** `GET /collections/ladder` runs **one query per debtor** —
 * the `NFR-3` breach `CLAUDE.md` does not name — and takes no page parameter.
 * `clientPage` is what `P4.2` deletes.
 */
function ladderBoardConfig(
  t: Translator,
  locale: string | undefined,
  tenantPath: (path: string) => string = (path) => path,
): TableConfig<LadderBoardRow> {
  return {
    screenId: "PAY-B.ladder",
    columns: [
      {
        key: "account_no",
        label: t("payments.col.account"),
        sortable: true,
        identity: true,
        // ⚠ B14 rule 31 — this cell printed `account_id` until 2026-09-01 and a
        // clerk read `01a046dd-…` where the tab one click away read
        // `AC-2026-00048`. An account nobody has numbered says so IN WORDS and
        // never falls back to the id — not in the cell and not on `title`,
        // because a tooltip is clerk-facing too (DEF-2883).
        //
        // Record links (PO 2026-10-19): the number opens the DEBTOR page, the
        // same door the Outstandings list's account cell opens.
        cell: (row) => {
          const href = debtorDetailPath(row.account_no);
          return href === null ? (
            <span className="pay-absent">{t("payments.row.noAccountNo")}</span>
          ) : (
            <InlineLinkTo to={tenantPath(href)}>{row.account_no}</InlineLinkTo>
          );
        },
      },
      {
        key: "balance",
        label: t("payments.collections.col.balance"),
        sortable: true,
        numeric: true,
        cell: (row) => <MoneyCell amount={row.balance} currency={row.currency} locale={locale} />,
      },
      {
        key: "days_late",
        label: t("payments.collections.col.daysLate"),
        sortable: true,
        numeric: true,
        // null is NOT zero. A bill nobody can place in time cannot be chased on
        // a schedule anchored to time, and "0 days late" reads as "due today".
        cell: (row) =>
          row.days_late === null ? (
            <span className="pay-absent">{t("payments.collections.noDueDate")}</span>
          ) : (
            row.days_late
          ),
      },
      {
        // ③ *"Rung now · as a pill, not a sentence"* (B14 rule 33).
        key: "current_tier",
        label: t("payments.collections.col.currentTier"),
        sortable: true,
        cell: (row) =>
          row.current_tier === null ? (
            // NOT an em dash: "we have not written to this customer yet" is a
            // state a clerk acts on, and a blank cell reads as missing data.
            <span className="pay-absent">{t("payments.collections.noTierYet")}</span>
          ) : (
            <>
              <StatusPill tone={ladderTone(row.current_tier)}>
                {collectionTierLabel(row.current_tier, t)}
              </StatusPill>
              {row.tier_sent_on !== null && (
                <span className="pay-sub">
                  {t("payments.collections.tierSentOn", { date: row.tier_sent_on })}
                </span>
              )}
            </>
          ),
      },
      {
        // ④ *"Goes out next · and when — the question the board exists to
        //    answer."* THE THREE-VALUED CELL: `runs === null` means the balance
        //    floor could not be read and this deployment CANNOT SAY — never a
        //    plausible rung, which would send letters.
        key: "next_rung",
        label: t("payments.collections.col.nextStep"),
        cell: (row) =>
          row.runs === null ? (
            <span className="pay-absent">{t("payments.collections.cannotSay")}</span>
          ) : row.next_rung === null ? (
            <span className="pay-absent">{t("payments.collections.ladderDone")}</span>
          ) : (
            collectionTierLabel(row.next_rung, t)
          ),
      },
      {
        key: "next_step_on",
        label: t("payments.collections.col.due"),
        sortable: true,
        cell: (row) =>
          row.next_step_on === null ? (
            <span className="pay-absent">{t("payments.collections.noStepDate")}</span>
          ) : (
            row.next_step_on
          ),
      },
      {
        key: "state",
        label: t("payments.collections.col.state"),
        cell: (row) =>
          row.plan_paused ? (
            <StatusPill tone="neutral">{t("payments.collections.paused")}</StatusPill>
          ) : row.runs === true ? (
            <StatusPill tone="warning">{t("payments.collections.dueNow")}</StatusPill>
          ) : row.runs === false && row.skip_reason !== null ? (
            // EVERY SKIP IS A DECISION, never an absence. J4 step 2 requires
            // each one on the trail and this is where a clerk reads it: *"why
            // did this customer never hear from us?"* has an answer on the row.
            <StatusPill tone="neutral">{ladderSkipLabel(row.skip_reason, t)}</StatusPill>
          ) : (
            <span className="pay-absent">{t("payments.collections.cannotSay")}</span>
          ),
      },
    ],
    getRowId: (row) => row.account_id,
    searchFields: ["account_no"],
    searchPlaceholder: "payments.collections.searchPlaceholder",
    filters: [
      {
        // The drawing's `Due now ×` chip, as a declared filter rather than a
        // hand-rolled control — so it appears in `+ Filter` and removes as a
        // chip like every other filter in the product (B14 rule 12).
        name: "due",
        label: t("payments.collections.col.state"),
        options: [
          { value: "now", label: t("payments.collections.dueNow") },
          { value: "paused", label: t("payments.collections.paused") },
        ],
      },
    ],
    defaultSort: { sort: "balance", dir: "desc" },
  };
}

/** How the browser narrows and orders this board until `P4.2` lands. */
const LADDER_SPEC: ClientTableSpec<LadderBoardRow> = {
  search: (row) => [row.account_no ?? ""],
  filter: (row, name, value) => {
    if (name !== "due") {
      return true;
    }
    return value === "paused" ? row.plan_paused : row.runs === true && !row.plan_paused;
  },
  sortValue: (row, key) => {
    switch (key) {
      case "account_no":
        return row.account_no;
      // A decimal string compares wrongly as text; this decides an ORDER and
      // never reaches a rendered figure, which stays `MoneyCell`'s.
      case "balance":
        return Number(row.balance);
      case "days_late":
        return row.days_late;
      case "current_tier":
        return row.current_tier;
      case "next_step_on":
        return row.next_step_on;
      default:
        return null;
    }
  },
};

// ── The screen ────────────────────────────────────────────────────────────

export interface CollectionsPageProps {
  client?: ApiClient; // test seam
  locale?: string;
  /**
   * The board's opening "as at" date. DEF-216, and BR-TEN-043's own rule: a
   * business date is an INPUT, never the wall clock.
   *
   * ⚠ THIS PROP EXISTS BECAUSE ITS ABSENCE MADE FOUR TESTS ROT OVERNIGHT.
   * `asOf` defaulted straight from `todayIso()`, so the page asked for a query
   * key containing TODAY'S REAL DATE while the tests primed one containing
   * 2026-08-16. They passed on the day they were written and failed every day
   * after: the keys no longer matched, the page rendered its loading skeleton
   * for ever, and the failures read as ordinary "expected 'Friendly reminder'"
   * content mismatches rather than as a clock problem.
   *
   * Same seam and same shape as `SettingsNumberingTab`'s `today` prop, which
   * is how the rest of this codebase already keeps a date out of a render.
   */
  today?: string;
}

export function CollectionsPage(props: CollectionsPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const cell = useAccessCell(PAYMENTS_PERMISSION, client);

  // DEF-216: the caller's date when it gives one, the clock only as a fallback.
  const [asOf, setAsOf] = useState(props.today ?? todayIso());
  // BR-SHL-011's vocabulary. `P4.2` is where it moves onto the request; until
  // then `clientPage` is the server's half, run here.
  const [tableState, setTableState] = useState<TableRequestState>(() => ({
    q: "",
    sort: "balance",
    dir: "desc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  }));

  const boardQuery = useQuery({
    queryKey: collectionsQueryKey(asOf),
    queryFn: () => getCollectionsLadder({ as_of: asOf }, client),
    retry: false,
  });

  if (isDenied(cell)) {
    return (
      <PermissionDenied
        helper={t("payments.collections.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }
  if (boardQuery.isError && isPermissionDenied(boardQuery.error)) {
    return (
      <PermissionDenied
        helper={t("payments.collections.denied")}
        onBack={() => navigate(tenantPath("/dashboard"))}
      />
    );
  }

  const board = boardQuery.data;
  // ⚠ **THE SEAM `P4.2` DELETES.** `GET /collections/ladder` runs one query
  // per debtor and takes no page parameter — the `NFR-3` breach `CLAUDE.md`
  // does not name. Narrowing and paging in the browser closes the four UI
  // rules today and closes none of that; both halves are on the CR board.
  const ladder = clientPage(board?.rows ?? [], tableState, LADDER_SPEC);
  const failed = boardQuery.isError && board === undefined;
  const routeAbsent = failed && bankRecRouteAbsent(boardQuery.error);

  return (
    <div className="fin-page">
      <PageHeader
        title={t("shell.nav.payments")}
        rollup={t("payments.collections.rollup", { asOf })}
        // ⛔ **`DEF-PAY-6237` — `P2.7` SAYS *EVERY PAYMENTS SCREEN* AND THIS
        // SCREEN WAS THE ONE IT MISSED.** §03 3·1's note ① is *"the missing
        // control, ON EVERY PAYMENTS SCREEN"*, and 3·3a's Doors row is *"1 door
        // — and it did not exist."* The ladder (7·3a) IS a payments screen: it
        // draws the same seven-tab strip with **Debtors** selected, and it is
        // where a clerk working overdue accounts stands when somebody walks up
        // with cash. Without this they have to navigate away to find the door,
        // which is what "every payments screen" exists to prevent.
        //
        // It is `CounterHeadSlot`, the component `P2.7` built — not a second
        // copy of it (B14 rule 43), so both states and the address come from
        // the one place.
        secondaryActions={<CounterHeadSlot client={props.client} />}
        // ⚠ **`P0.8` — THE STRIP IS THE DRAWING'S SEVEN AND THIS SCREEN IS NOT
        // ONE OF THEM.** The blueprint folds the ladder under **Debtors** as
        // screen 7·3a and draws that tab selected while the ladder is open, so
        // the selection is computed rather than hardcoded. Hardcoding the
        // ladder's own id would leave the whole strip looking unselected, which
        // is exactly what `RefundsPage` records going wrong one screen over.
        tabs={PAYMENTS_TABS.map((tab) => ({
          id: tab.id,
          label: t(tab.labelKey),
          explainer:
            tab.id === PAYMENTS_TAB_OUTSTANDINGS
              ? t("payments.collections.explainer")
              : undefined,
        }))}
        activeTabId={paymentsStripSelection(PAYMENTS_TAB_COLLECTIONS)}
        tabsLabel={t("payments.tabsLabel")}
        onTabSelect={(tab) => navigate(tenantPath(paymentsTabPath(tab.id)))}
      />

      {routeAbsent ? (
        <ArrivesWith
          title={t("payments.collections.awaitsTitle")}
          message={t("payments.collections.awaits")}
        />
      ) : failed ? (
        <Panel role="alert">
          <h3>{t("payments.collections.errorTitle")}</h3>
          <p className="pay-absent">{apiErrorText(boardQuery.error, translate)}</p>
        </Panel>
      ) : board === undefined ? (
        <LoadingSkeleton variant="table" />
      ) : (
        <>
          <KPIStrip
            kpis={[
              {
                id: "accounts",
                label: t("payments.collections.kpi.accounts"),
                value: board.tiles.accounts,
              },
              {
                id: "due",
                label: t("payments.collections.kpi.dueToday"),
                value: board.next_step_available ? (
                  board.tiles.due_today
                ) : (
                  // The honest absence, in the tile that would otherwise be the
                  // most confident thing on the screen.
                  <span className="pay-absent">{t("payments.collections.cannotSay")}</span>
                ),
                detail: t("payments.collections.kpi.dueTodayDetail"),
              },
              {
                id: "paused",
                label: t("payments.collections.kpi.paused"),
                value: board.tiles.paused,
                detail: t("payments.collections.kpi.pausedDetail"),
              },
              {
                id: "notStarted",
                label: t("payments.collections.kpi.notStarted"),
                value: board.tiles.not_started,
                detail: t("payments.collections.kpi.notStartedDetail"),
              },
            ]}
          />

          <div className="pay-toolbar">
            <label className="pay-inline-field" htmlFor="as_of">
              {t("payments.collections.asOf")}
              <input
                id="as_of"
                type="date"
                className="input"
                value={asOf}
                onChange={(event) => setAsOf(event.target.value)}
              />
            </label>
            {/* Said out loud, because a board that looks like a worklist and
                sends nothing would be read as one that had already sent. */}
            <span className="pay-absent" role="note">
              {t("payments.collections.previewOnly")}
            </span>
          </div>

          {!board.next_step_available && (
            <div className="pay-attention" role="note">
              <Kicker>{t("payments.collections.thresholdKicker")}</Kicker>
              <p>{t("payments.collections.thresholdMissing")}</p>
            </div>
          )}

          {/* ⚠ **THE FOUR CONTROLS THE BLUEPRINT CALLS *"ALL FOUR ABSENT
              TODAY"*.** Search, the filter chips, the ▦ chooser and the
              pagination footer are `DataTable`'s, on this list exactly as on
              every other. The date field above stays where it is: `as_of` is
              the question the whole BOARD asks, not a dimension of the list,
              and `DEF-1700` deleted the second toolbar row a screen grew for
              controls like it. */}
          <DataTable
            config={ladderBoardConfig(translate, props.locale, tenantPath)}
            state={tableState}
            onStateChange={setTableState}
            rows={ladder.page}
            totalRows={ladder.total}
            loading={false}
            // The drawing's `Due now ×` chip. `DataTable` takes the chips as
            // a COMPOSED slot, so a declared filter with no `filterBarSlot`
            // renders nothing at all — see `OutstandingsTab`'s note.
            filterBarSlot={
              <FilterBar
                filters={ladderBoardConfig(translate, props.locale).filters ?? []}
                state={tableState}
                onStateChange={setTableState}
              />
            }
            empty={{
              title: t("payments.collections.empty"),
              helper: t("payments.collections.emptyHelper"),
            }}
          />
          <GapNotes gaps={board.problems} t={translate} />
        </>
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-019@9d41b60 (sources: 04-docs/05-modules/08-payments/06-epics/EP-PAY-05-payment-plans.md US-PAY-018/019 §1/§3/§5 · EP-PAY-04 US-PAY-014/015 · 08-payments/02-business-rules.md BR-PAY-016/017/029 + BR-CUS-043 · 08-qa/01-e2e/journeys/J4-collections.md · 05-prototype/UtilityBilling.html lines 3656-3671; co-packets US-PAY-015, US-PAY-018)
// generated: 2026-08-16 by story-coder (payments SURFACE lane — the look-before-you-send a ladder that could only STEP had never had)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — the collections test file failed to resolve this module before it existed; verbatim in the lane report. tsc✔ · eslint --max-warnings 0✔ · vitest✔ · vite build✔ · run_gates✔
// exceptions: (1) `runs` is rendered THREE-VALUED — true / false-with-a-reason / "cannot say" — because a boolean would collapse "we did not chase them" into "we cannot tell you whether we will" · (2) `days_late` null renders as its own sentence, never 0: a bill nobody can place in time cannot be chased on a schedule anchored to time, and "0 days late" reads as "due today" · (3) THE BOARD SENDS NOTHING and says so on the screen — the notice-sending path is `POST /collections/run`, which is the S34 bulk action and is not duplicated here · (4) FIXED 2026-09-01, CR-059 — the account column shows the ACCOUNT NUMBER. It showed the ACCOUNT ID until B14 rule 31 was ratified (2026-08-30) and turned this note's own reported limitation into a live defect: a clerk read a raw uuid where the sibling Outstandings tab read `AC-2026-00048`. The honest fix this note named was the one taken — `ladder_board` now serves `account_no`, read through customers' OWN published `account_queryset()` resolved by name, which is the seam `outstandings.py`, `reporting.py`, `autopay.py` and `writeoffs.py` already use and is neither a join nor a cross-module table read. An account with no number says so in four words and NEVER falls back to the id; blank is normalised to null in the read model, because `account_no` is a `TextField()` and `""` would draw an empty cell · (5) this is a FOURTH tab on the Payments page where the prototype draws three; the ladder position belongs with the outstandings a clerk works from, and the divergence is REPORTED rather than taken quietly (the Finance page's fifth tab is the same precedent)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
