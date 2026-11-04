// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.6` — §03 frame **3·1 Counters**,
//           `05-prototype/06 Payments Page Blueprint.pdf` p051–p052, read as
//           an IMAGE at scale 2.0 (B14 rule 42).
// Screens:  `PAY-04` — the Counter tab of the Payments page
// Rules:    B14 rule 4 (`Verb →` navigates, so `Start counter →` carries the
//           arrow) · rules 12–17 (the toolbar, sorting, the column chooser,
//           the pagination footer, the empty state — p052's own *Table
//           controls* row reads *"All four, on the server, exactly as the
//           payments list already does them"*) · rule 15 (row actions are
//           ICONS, max 2 + overflow) · rule 31 (the COUNTER column shows the
//           till's CODE, never its id) · rule 33 · rule 40 · rule 43 ·
//           rule 21 · `CR-136-BRC07` §3.1 · §3.2
// Tests:    src/features/payments/counterScreens.dom.test.tsx
// ───────────────────────────────────────────────────────
// *"Whose till is open, and whose did not get counted?"* — for a supervisor
// or finance lead checking the day's tills.
//
// ══════════════════════════════════════════════════════════════════════════
// THIS TAB HAD NOTHING BEHIND IT AT ALL UNTIL THIS COMMIT
// ══════════════════════════════════════════════════════════════════════════
// p051, verbatim: *"Nothing in this tab exists. There is no session, no float,
// no owner and no count anywhere in the product."* `counter_sessions` landed
// in phase 0 (`payments/0031`, RLS in `0032`) **written by nothing**, and the
// tab rendered a stated absence over it.
//
// ⚠ **SO THE HOLD COMES OFF IN THE SAME COMMIT AS THE SCREEN.** `counter` is
// removed from `PAYMENTS_TABS_AWAITING_A_SCREEN` here, and
// `sevenTabs.dom.test.tsx` fails BOTH WAYS on that register — a tab listed
// there that has started rendering a real screen is as red as a tab with
// neither. That is hard-won law 2's mirror doing its job: landing a screen and
// releasing the control that pointed at it are two acts, and only the first
// one feels like the work.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ WHAT THE FOUR TILES ARE, AND WHY NONE OF THEM IS COMPUTED HERE
// ══════════════════════════════════════════════════════════════════════════
// `Open now · Taken today · Not counted · Difference this week`, drawn on
// p051. Every one is folded SERVER-SIDE over the same rows the table filters,
// because this list is paginated and a figure folded over one page of fifty is
// a different figure with the same label. B14 rule 37 also applies to the
// numbers the drawing prints — `2`, `$4,101.10`, `3`, `$0.00` are a demo
// tenant's and are illustrations, never facts to build to.
//
// ⚠ **`Not counted` IS NOT COUNTED HERE EITHER**, and that is the point of
// `isNotCounted` living in `counterShared.tsx`: the tile, the filter chip, the
// COUNTED column and `P2.11`'s notice are four readers of ONE expression
// (`CR-136-BRC07` §3.2).
import { useEffect, useMemo, useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getCounters } from "@/api/counterEndpoints";
import type { CounterDetail, CounterRow } from "@/api/counterEndpoints";
import { DataTable } from "@/components/DataTable";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { DEFAULT_PAGE_SIZE, serializeTableParams } from "@/components/tableTypes";
import { DateCell, todayInZone } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import { RowActions, RowActionLink, RowMenuAction, RowActionsMore } from "@/components/RowActions";
import { EyeIcon, PowerIcon, CommitIcon } from "@/components/icons";
import { ROLE_SYSTEM_ADMIN, useRegional, useTenantRole } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  CloseKindMark,
  COUNTER_START_PARAM,
  COUNTER_STATE_FILTER,
  CounterMoney,
  NOT_COUNTED_FILTER_VALUE,
  OPEN_FILTER_VALUE,
  canDeclareCount,
  counterRoute,
  isOpenTill,
  isNotCounted,
} from "./counterShared";
import { countersQueryKey } from "./counterQueries";
import { useCounter } from "./useCounter";
import { StartCounterModal } from "./StartCounterModal";
import { ForceCloseCounterModal } from "./ForceCloseCounterModal";
import { DeclareCountModal } from "./DeclareCountModal";

export interface CountersTabProps extends RegionalProps {
  client?: ApiClient;
  locale?: string;
  /** BR-SHL-025: null = this deployment can write; a string says why not. */
  writeBlockedReason: string | null;
  /** Opening a till lands the clerk on their own counter — 3·2. */
  onOpenCounter: (code: string) => void;
}

const INITIAL_STATE: TableRequestState = {
  q: "",
  // p051 draws the list newest-first with the open tills at the top; `opened`
  // descending is that, and it is the only ordering the drawing evidences.
  sort: "opened",
  dir: "desc",
  page: 1,
  per: DEFAULT_PAGE_SIZE,
  filters: {},
};

/**
 * B14 rule 15 — row actions are ICONS with tooltips, at most two visible then
 * `…`. Lifted out of `CountersTab` rather than nested in it: a component
 * declared inside a render is a NEW component type on every render, which
 * remounts its subtree and drops an open overflow menu the moment the list
 * refetches.
 *
 * ⚠ **THERE IS NO EDIT ACTION AND THAT IS THE DRAWING'S OWN WORD.** p052's
 * *Write surfaces* row reads `Detail → 3·2 · Add → 3·3a · **Edit NOTHING** ·
 * Update → 3·3c, 3·3d`, so the ✎ the wireframe sketches beside the eye is an
 * illustration (B14 rule 37) and is not built.
 */
function CounterRowActions(props: {
  row: CounterRow;
  t: (key: string) => string;
  viewHref: string;
  writeBlockedReason: string | null;
  /** `DEF-PAY-10778` — why THIS role may not force-close, or null. */
  forceCloseBlockedReason: string | null;
  onForceClose: () => void;
  onDeclare: () => void;
}) {
  const { row, t } = props;
  return (
    <RowActions>
      <RowActionLink
        label={t("payments.counter.action.view")}
        icon={<EyeIcon />}
        to={props.viewHref}
      />
      {isOpenTill(row) && (
        <RowMenuAction
          label={t("payments.counter.action.forceClose")}
          icon={<PowerIcon />}
          danger
          reason={props.writeBlockedReason ?? props.forceCloseBlockedReason}
          onClick={props.onForceClose}
        />
      )}
      {canDeclareCount(row) && (
        <RowActionsMore label={t("payments.counter.action.more")}>
          <RowMenuAction
            label={t("payments.counter.action.declare")}
            icon={<CommitIcon />}
            reason={props.writeBlockedReason}
            onClick={props.onDeclare}
          />
        </RowActionsMore>
      )}
    </RowActions>
  );
}

export function CountersTab(props: CountersTabProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  // ⚠ **THE REGIONAL PAIR IS RESOLVED HERE, NOT DEMANDED AS A REQUIRED PROP —
  // AND DEMANDING IT WAS A RED TYPE CHECK, NOT A STYLE POINT.** `PaymentsPage`
  // holds the pair as OPTIONAL `RegionalProps`, so passing `props.timeZone`
  // into a required `string` is `TS2322: 'string | undefined' is not
  // assignable to 'string'`. It was red on this branch from `35f86b374` and
  // nothing saw it, because the lane's own `tsc` runs were being killed by a
  // `timeout` wrapper whose empty output read as a clean pass. `MyCounterPage`
  // and `CounterDoors` already did it this way.
  const { timeZone, dateFormat } = useRegional(props);
  // ⛔ **`DEF-PAY-10778` (PO 2026-10-31 P9 = A).** `POST /counters/{code}/
  // force-close` is `SystemAdminOnly` and the service is
  // `@require_role(SYSTEM_ADMIN)`, so for any other role *Force close* was a
  // live control behind a refusal. It is GREYED with the reason, the same
  // shape as Reverse on the Payments list (`reverseBlockedReason`). A null role
  // (the permissions read has not answered) offers it: the server is the
  // boundary either way.
  const role = useTenantRole(props.client ?? api);
  const forceCloseBlockedReason =
    role !== null && role !== ROLE_SYSTEM_ADMIN ? t("payments.counter.forceCloseAdminOnly") : null;
  const [state, setState] = useState<TableRequestState>(INITIAL_STATE);
  const [searchParams, setSearchParams] = useSearchParams();
  // 3·3c and 3·3d are row acts, so the open dialog is a ROW rather than a flag.
  const [forcing, setForcing] = useState<CounterRow | null>(null);
  const [declaring, setDeclaring] = useState<CounterRow | null>(null);

  // ⚠ **THE START DIALOG IS OPENED BY AN ADDRESS, NOT A HANDLER.** See
  // `COUNTER_START_ROUTE` — a door with no address carries nothing a test can
  // assert, which is how `DEF-CWP-3925` cost the customer portal six of its
  // eight front doors. It is also the only shape `P2.7` can reuse from the six
  // other payments tabs.
  const starting = searchParams.get(COUNTER_START_PARAM) === "1";
  function closeStart(): void {
    const next = new URLSearchParams(searchParams);
    next.delete(COUNTER_START_PARAM);
    setSearchParams(next, { replace: true });
  }

  const config = useMemo<TableConfig<CounterRow>>(
    () => ({
      screenId: "PAY-04",
      getRowId: (row) => row.code,
      // ⚠ A KEY AND NOT A SENTENCE (`DEF-510`): the copy stays in the eleven
      // catalogues. p051 draws it as `Search counter or person…`.
      searchPlaceholder: "payments.counter.list.search",
      searchFields: ["code", "owner"],
      defaultSort: { sort: INITIAL_STATE.sort, dir: INITIAL_STATE.dir },
      filters: [
        {
          // ⚠ **TWO OPTIONS AND NOT FIVE.** The drawing evidences exactly two
          // states a supervisor filters on — the `Not counted ×` chip it draws
          // applied, and the open tills its first tile counts. A third option
          // would be a control the drawing does not show (B14 rule 41).
          name: COUNTER_STATE_FILTER,
          label: t("payments.counter.list.filter.state"),
          options: [
            { value: OPEN_FILTER_VALUE, label: t("payments.counter.list.filter.open") },
            {
              value: NOT_COUNTED_FILTER_VALUE,
              label: t("payments.counter.notCounted"),
            },
          ],
        },
      ],
      columns: [
        {
          key: "code",
          label: t("payments.counter.list.col.counter"),
          sortable: true,
          identity: true,
          // B14 rule 31 — a till's CODE is its human-facing number and its id
          // is never on screen. `CTR-260921-DW` is what a clerk reads out.
          cell: (row) => row.code,
        },
        {
          key: "owner",
          label: t("payments.counter.list.col.person"),
          sortable: true,
          cell: (row) => row.owner_name ?? t("payments.counter.nobody"),
        },
        {
          key: "opened",
          label: t("payments.counter.list.col.opened"),
          sortable: true,
          cell: (row) => (
            <DateCell
              value={row.opened_at}
              timeZone={timeZone}
              dateFormat={dateFormat}
              withTime
            />
          ),
        },
        {
          // ③ — a seal that is not a real close is MARKED so it can never read
          // as one. See `CloseKindMark`, and `CR-136-BRC07` §3.1 for what
          // happened to the drawing's `by the system` auto-close.
          key: "closed",
          label: t("payments.counter.list.col.closed"),
          sortable: true,
          cell: (row) =>
            row.closed_at === null ? (
              <span className="text-neutral-700">{t("payments.counter.stillOpen")}</span>
            ) : (
              <span className="inline-flex items-center gap-2">
                <DateCell
                  value={row.closed_at}
                  timeZone={timeZone}
                  dateFormat={dateFormat}
                  withTime
                />
                <CloseKindMark kind={row.close_kind} t={t} />
              </span>
            ),
        },
        {
          key: "payments",
          label: t("payments.counter.list.col.payments"),
          numeric: true,
          cell: (row) => row.payment_count,
        },
        {
          key: "taken",
          label: t("payments.counter.list.col.taken"),
          sortable: true,
          numeric: true,
          cell: (row) => (
            <CounterMoney
              amount={row.taken_total}
              currency={row.currency}
              locale={props.locale}
              absent="—"
            />
          ),
        },
        {
          // ④ — *"empty is the finding — the payments are safe, the drawer
          // figure is missing"*. An open till has not been counted YET, which
          // is a different statement from nobody counting it, so it draws a
          // dash and a sealed uncounted till says so in words.
          key: "counted",
          label: t("payments.counter.list.col.counted"),
          numeric: true,
          cell: (row) =>
            isNotCounted(row) ? (
              <span className="text-warning-700">{t("payments.counter.notCounted")}</span>
            ) : (
              <CounterMoney
                amount={row.counted_total}
                currency={row.currency}
                locale={props.locale}
                absent="—"
              />
            ),
        },
        {
          key: "actions",
          label: t("payments.counter.list.col.actions"),
          locked: true,
          cell: (row) => (
            <CounterRowActions
              row={row}
              t={t}
              viewHref={tenantPath(counterRoute(row.code))}
              writeBlockedReason={props.writeBlockedReason}
              forceCloseBlockedReason={forceCloseBlockedReason}
              onForceClose={() => setForcing(row)}
              onDeclare={() => setDeclaring(row)}
            />
          ),
        },
      ],
    }),
    // `t` and the regional pair are what the cells read; the row callbacks are
    // stable through the component closure.
    [t, tenantPath, timeZone, dateFormat, props.locale, props.writeBlockedReason, forceCloseBlockedReason],
  );

  // ⚠ **`as_of` IS REQUIRED FOR TWO OF THE FOUR TILES, AND FOUND IN A BROWSER.**
  // `BR-TEN-043` forbids anything under `apps/payments/` reading a wall clock,
  // because a server clock decides a business day in the SERVER's timezone. So
  // `counter_list_totals` answers `taken_today` and `difference_this_week` with
  // **null** and a `totals_unavailable: "as_of_missing"` unless the caller says
  // which day it means — and this screen was not saying. It printed `$0.00`
  // and a blank payment count on a real stack, which is `DEF-127`'s shape:
  // *"a figure nobody filled rendering as a figure somebody counted."*
  //
  // The day is the TENANT's, from `todayInZone`, the same source every other
  // payments tab proposes and the same one `DateCell` renders an instant in —
  // so the day a clerk is offered and the day they read back cannot disagree.
  const params = useMemo(() => {
    const next = serializeTableParams(state, config);
    next.set("as_of", todayInZone(timeZone));
    return next;
  }, [state, config, timeZone]);
  const query = useQuery({
    queryKey: [...countersQueryKey(), params.toString()],
    queryFn: () => getCounters(client, Object.fromEntries(params)),
  });

  const totals = query.data?.totals;
  const currency = totals?.currency ?? query.data?.rows[0]?.currency ?? "USD";

  // A row the clerk has just acted on is re-read from the refreshed list, so a
  // dialog left open over a stale row cannot commit twice.
  useEffect(() => {
    if (query.data === undefined) {
      return;
    }
    setForcing((current) =>
      current === null ? null : (query.data.rows.find((row) => row.code === current.code) ?? null),
    );
    setDeclaring((current) =>
      current === null ? null : (query.data.rows.find((row) => row.code === current.code) ?? null),
    );
  }, [query.data]);

  return (
    <>
      <KPIStrip
        loading={query.isLoading}
        kpis={[
          {
            id: "open-now",
            label: t("payments.counter.kpi.openNow"),
            value: totals?.open_now ?? "—",
            detail: totals?.open_owner_names.join(" · "),
          },
          // ⚠ **A NULL FIGURE IS A STATED ABSENCE, NEVER A ZERO.** See the
          // `as_of` note above: `?? "0"` here is the whole of `DEF-127`.
          totals?.taken_today == null
            ? {
                id: "taken-today",
                label: t("payments.counter.kpi.takenToday"),
                value: <span className="text-neutral-700">—</span>,
                detail: t("payments.counter.kpi.noDay"),
              }
            : {
                id: "taken-today",
                label: t("payments.counter.kpi.takenToday"),
                money: {
                  amount: totals.taken_today,
                  currency,
                  basis: "posting",
                  locale: props.locale,
                },
                detail:
                  totals.taken_today_payment_count == null
                    ? undefined
                    : t("payments.counter.kpi.takenTodayDetail", {
                        count: totals.taken_today_payment_count,
                      }),
              },
          {
            id: "not-counted",
            label: t("payments.counter.notCounted"),
            value: totals?.not_counted ?? "—",
            detail:
              totals?.not_counted_oldest == null ? undefined : (
                <>
                  {t("payments.counter.kpi.oldest")}{" "}
                  <DateCell
                    value={totals.not_counted_oldest}
                    timeZone={timeZone}
                    dateFormat={dateFormat}
                  />
                </>
              ),
          },
          totals?.difference_this_week == null
            ? {
                id: "difference-week",
                label: t("payments.counter.kpi.differenceWeek"),
                value: <span className="text-neutral-700">—</span>,
                detail: t("payments.counter.kpi.noDay"),
              }
            : {
                id: "difference-week",
                label: t("payments.counter.kpi.differenceWeek"),
                money: {
                  amount: totals.difference_this_week,
                  currency,
                  basis: "posting",
                  locale: props.locale,
                },
              },
        ]}
      />
      <DataTable
        config={config}
        state={state}
        onStateChange={setState}
        rows={query.data?.rows ?? []}
        totalRows={query.data?.count ?? null}
        loading={query.isLoading}
        error={
          query.isError
            ? { reason: t("payments.counter.list.failed"), onRetry: () => void query.refetch() }
            : null
        }
        // B14 rule 17 — what is missing, and the action that fills it.
        empty={{
          title: t("payments.counter.list.empty.title"),
          helper: t("payments.counter.list.empty.helper"),
          ctaLabel: t("payments.counter.action.start"),
          ctaReason: props.writeBlockedReason,
          // B14 rule 4: the page head already carries this action, so the
          // empty state's copy of it is the secondary tier.
          ctaVariant: "secondary",
          onCta: () => setSearchParams({ [COUNTER_START_PARAM]: "1" }),
        }}
      />
      {starting && (
        <StartCounterModal
          client={props.client}
          writeBlockedReason={props.writeBlockedReason}
          onClose={closeStart}
          onStarted={(counter: CounterDetail) => {
            closeStart();
            props.onOpenCounter(counter.code);
          }}
        />
      )}
      {forcing !== null && (
        <ForceCloseCounterModal
          client={props.client}
          counter={forcing}
          locale={props.locale}
          timeZone={timeZone}
          dateFormat={dateFormat}
          writeBlockedReason={props.writeBlockedReason}
          onClose={() => setForcing(null)}
          onForceClosed={() => setForcing(null)}
        />
      )}
      {declaring !== null && (
        <DeclareCountModalForRow
          client={props.client}
          row={declaring}
          locale={props.locale}
          timeZone={timeZone}
          dateFormat={dateFormat}
          writeBlockedReason={props.writeBlockedReason}
          onClose={() => setDeclaring(null)}
        />
      )}
    </>
  );
}

/**
 * 3·3d needs the till's per-method split and a LIST ROW does not carry one, so
 * the dialog is opened over a read of `GET /counters/{ref}` rather than over
 * the row the supervisor clicked.
 *
 * ⚠ **THAT IS A DELIBERATE EXTRA READ RATHER THAN A WIDER LIST PAYLOAD.** A
 * per-method split on every row of a paginated supervisor list is fifty splits
 * nobody looks at; the alternative — declaring a count against whatever
 * figures the row happened to carry — is how a screen counts a drawer against
 * a stale total.
 */
function DeclareCountModalForRow(props: {
  row: CounterRow;
  client?: ApiClient;
  locale?: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  writeBlockedReason: string | null;
  onClose: () => void;
}) {
  const detail = useCounter(props.row.code, props.client);
  if (detail.data === undefined) {
    return null;
  }
  return (
    <DeclareCountModal
      client={props.client}
      counter={detail.data}
      locale={props.locale}
      // ⚠ `props.` HERE AND NOT THE BARE NAME — this helper is OUTSIDE
      // `CountersTab` and has its own props; the tab's resolved pair is handed
      // in. A blanket rename of `props.timeZone` → `timeZone` reached this
      // function too and `tsc` answered `TS2304: Cannot find name`.
      timeZone={props.timeZone}
      dateFormat={props.dateFormat}
      writeBlockedReason={props.writeBlockedReason}
      onClose={props.onClose}
      onDeclared={props.onClose}
    />
  );
}

export default CountersTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-136-BRC07 §3.1 · §3.2 · §4 row `P2.6` · blueprint p051–p052 as images at 2.0
// generated: 2026-09-23 by LANE P2-SCREENS
// checklist: A✔ B=n/a(`GET /counters` is `P2.3`, LANE P2-API's) C✔ D=n/a E✔(the tab's hold comes off in this commit) F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/payments/counterScreens.dom.test.tsx · vitest src/features/payments/sevenTabs.dom.test.tsx (the hold-expiry case, flipped in this commit) · G31 · routeBUtilities.test.ts
// exceptions: E3 `GET /counters` is NOT SERVED at this commit — the list renders its failure with a retry rather than an invented row · E3 the drawing's ✎ row action is not built: p052's own *Write surfaces* row reads `Edit NOTHING`
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
