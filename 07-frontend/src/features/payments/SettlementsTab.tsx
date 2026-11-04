// ── Trace ──────────────────────────────────────────────
// Change:   `CR-139-BRC07` `P5.7` — §03 frame **5·1 Settlements**,
//           `05-prototype/06 Payments Page Blueprint.pdf` **p069** (the head,
//           the question, the tab strip) and **p070** (the four tiles, the
//           toolbar, the eight columns, the annotations and the For/Doors/
//           Primary action/Today/Task rows), read AS IMAGES at 2.0 (B14 rule 42).
// Screens:  5·1 Settlements (`S-NEW · PAY-P`) — the Settlements tab
// Rules:    B14 rules 12–17 (the toolbar, sorting, the column chooser, the
//           pagination footer, the empty state — p070's own Rules row reads
//           `B14 12–17 · 31 · 33 · 40`) · rule 15 (row actions are ICONS) ·
//           rule 19 (the search placeholder names what it matches) · rule 31
//           (the SETTLEMENT column is the provider's reference, never an id) ·
//           rule 32 · rule 33 · rule 37 (every figure drawn is an
//           illustration) · rule 41 · rule 43 · rule 21 · BR-SHL-011 ·
//           BR-TEN-043 (the caller names the day) · NFR-3
// Tests:    src/features/payments/settlementScreens.dom.test.tsx ·
//           src/features/payments/sevenTabs.dom.test.tsx (the hold, flipped)
// ───────────────────────────────────────────────────────
/**
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║  "The bank shows one credit from the processor. Which payments is it?"   ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 * p069's question for 5·1, and p070's TODAY line is four words: **"Nothing.
 * Provider payments arrive and are recorded; nothing models being paid for
 * them. No settlement table, no feed, no screen."**
 *
 * ⚠ **THE HOLD COMES OFF IN THE SAME COMMIT AS THE SCREEN.** `settlements` is
 * removed from `PAYMENTS_TABS_AWAITING_A_SCREEN` here, and
 * `sevenTabs.dom.test.tsx` fails BOTH WAYS on that register — a tab listed
 * there that has started rendering is as red as a tab with neither. That is
 * hard-won law 2's mirror doing its job: landing a screen and releasing the
 * control that pointed at it are two acts, and only the first feels like the
 * work. Its two catalogue keys go in the same commit, so the panel cannot come
 * back quietly.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHY THIS TAB EXISTS AT ALL — p070's own GAP box
 * ══════════════════════════════════════════════════════════════════════════
 * *"Your rule is that **every payment carries a batch number**. A counter
 * payment gets one when the till opens; an imported one gets its file's. **A
 * card payment has nothing to belong to until the provider pays out** — and
 * the payout is the thing the bank statement shows as a single line. So the
 * settlement IS the card payment's batch, and without it the rule cannot hold
 * for a third of the money."*
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ⚠ THERE IS NO PRIMARY ACTION, AND THAT IS THE DRAWING'S OWN WORD
 * ══════════════════════════════════════════════════════════════════════════
 * p070's *Primary action* row reads **"None — this is a read."**, and p072's
 * step 3 is titled *"What you can do to it — Nothing, and that is the
 * design."* So this tab draws no header button, no bulk bar and no row action
 * but the eye: every act a clerk might want here belongs to the PAYMENT inside
 * the payout (tab 2) or to the BANK MATCH (Finance).
 *
 * **The empty state therefore has no CTA either.** B14 rule 17 asks for *what
 * is missing and the action that fills it* — and the action that fills this
 * list is a provider feed delivering a payout, which is not something a clerk
 * presses. It says so in words instead of offering a button that does nothing.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ⚠ THE FOUR TILES ARE FOLDED ON THE SERVER, AND TWO OF THEM CAN ANSWER null
 * ══════════════════════════════════════════════════════════════════════════
 * **PAID OUT TODAY · AWAITING SETTLEMENT · FEES THIS MONTH · UNMATCHED.** Every
 * one is folded over the same rows the table filters, because this list is
 * paginated and a figure folded over one page of fifty is a different figure
 * with the same label.
 *
 * *Paid out today* and *Fees this month* are claims about a DAY, and nothing
 * under `apps/payments/` may read a wall clock (`BR-TEN-043`) — so the day is
 * the TENANT's, from `todayInZone`, exactly as the Counter tab sends it, and a
 * missing one renders a stated absence rather than `$0.00` (`DEF-127`).
 *
 * ⚠ **p070's FIGURES ARE ILLUSTRATIONS** (B14 rule 37): `$12,841.03`,
 * `$1,204.80`, `$418.22` and `0` are a demo tenant's and nothing here is built
 * to reach them.
 */
import { useCallback, useMemo, useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getSettlements } from "@/api/settlementEndpoints";
import type { SettlementRow } from "@/api/settlementEndpoints";
import { DataTable } from "@/components/DataTable";
import { DateCell, todayInZone } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import { RowActions, RowActionLink } from "@/components/RowActions";
import { EyeIcon } from "@/components/icons";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { DEFAULT_PAGE_SIZE, serializeTableParams } from "@/components/tableTypes";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  BankMark,
  Percent,
  SETTLEMENT_MATCHED,
  SETTLEMENT_PROVIDER_FILTER,
  SETTLEMENT_RECEIVED,
  SETTLEMENT_STATE_FILTER,
  SettlementMoney,
  settlementRoute,
  settlementsQueryKey,
} from "./settlementsShared";
import type { Translator } from "./settlementsShared";

export interface SettlementsTabProps extends RegionalProps {
  client?: ApiClient;
  locale?: string;
}

const INITIAL_STATE: TableRequestState = {
  q: "",
  // p070 draws the list newest payout first, and the table's own index
  // `ix_settlements_paid_out` is `(tenant, -paid_out_at)` for exactly this.
  sort: "paid_out_at",
  dir: "desc",
  page: 1,
  per: DEFAULT_PAGE_SIZE,
  filters: {},
};

/**
 * ⚠ **THE REQUEST IS BUILT FROM A STABLE SHAPE, NOT FROM THE RENDER CONFIG.**
 * `serializeTableParams` reads only `config.filters`, and this screen's render
 * config depends on the RESPONSE — the PROVIDER filter's options arrive beside
 * the tiles. Serializing from it would make the query key depend on its own
 * answer, which refetches once on every load and reads as a flicker nobody can
 * explain. The two filter NAMES are the whole of what the request needs.
 */
const REQUEST_SHAPE: TableConfig<SettlementRow> = {
  screenId: "PAY-P",
  getRowId: (row) => row.code,
  defaultSort: { sort: INITIAL_STATE.sort, dir: INITIAL_STATE.dir },
  columns: [],
  filters: [
    { name: SETTLEMENT_STATE_FILTER, label: "", options: [] },
    { name: SETTLEMENT_PROVIDER_FILTER, label: "", options: [] },
  ],
};

/**
 * B14 rule 15 — row actions are ICONS with tooltips, at most two then `…`.
 * Lifted out of the tab rather than nested in it: a component declared inside
 * a render is a NEW component type on every render, which remounts its subtree.
 *
 * ⚠ **THERE IS EXACTLY ONE, AND THE DRAWING SAYS SO.** p070's row draws an eye
 * and an overflow glyph; p072's step 3 says a settlement has no actions at
 * all, so the `…` is an illustration (B14 rule 37) and is not built. The eye is
 * 5·2's only door — p071's *Doors* row reads *"A row on 5·1. 1 door."*
 */
function SettlementRowActions(props: { t: (key: string) => string; viewHref: string }) {
  return (
    <RowActions>
      <RowActionLink
        label={props.t("payments.settlement.action.view")}
        icon={<EyeIcon />}
        to={props.viewHref}
      />
    </RowActions>
  );
}

export function SettlementsTab(props: SettlementsTabProps) {
  const { t } = useTranslation();
  // The shared `BankMark` takes a plain `Translator` rather than i18next's own
  // `TFunction`, so the binding is made once here (B14 rule 43: the component
  // is the reusable thing, and a reusable thing does not depend on a hook).
  const translate: Translator = useCallback(
    (key, params) => (params === undefined ? t(key) : t(key, params)),
    [t],
  );
  const client = props.client ?? api;
  const tenantPath = useTenantPath();
  // ⚠ RESOLVED HERE RATHER THAN DEMANDED AS A REQUIRED PROP. `PaymentsPageProps
  // extends RegionalProps`, where both are OPTIONAL, so a required `string`
  // prop is `TS2322` at the mount site — the type error `DEF-PAY-6226` cost the
  // Counter tab and every lane's `tsc` run with it.
  const { timeZone, dateFormat } = useRegional(props);
  const [state, setState] = useState<TableRequestState>(INITIAL_STATE);

  const params = useMemo(() => {
    const next = serializeTableParams(state, REQUEST_SHAPE);
    // ⚠ **THE BUSINESS DAY TRAVELS, BECAUSE THE SERVER MAY NOT READ A CLOCK.**
    // `BR-TEN-043` / gate `G6`: a server clock decides a business day in the
    // SERVER's timezone, so *Paid out today* would be somebody else's Tuesday
    // for a Texas utility. It is the tenant's day, from the same source
    // `DateCell` renders an instant in, so the day offered and the day read
    // back cannot disagree.
    next.set("as_of", todayInZone(timeZone));
    return next;
  }, [state, timeZone]);

  const query = useQuery({
    queryKey: [...settlementsQueryKey(), params.toString()],
    queryFn: () => getSettlements(client, Object.fromEntries(params)),
  });

  const totals = query.data?.totals;
  const currency = totals?.currency ?? query.data?.rows[0]?.currency ?? "USD";

  const config = useMemo<TableConfig<SettlementRow>>(
    () => ({
      screenId: "PAY-P",
      // ⚠ THE ROW'S IDENTITY IS ITS REFERENCE AND NOT ITS KEY — the payload
      // carries no `id` at all, which is B14 rule 31 made structural rather
      // than remembered.
      getRowId: (row) => row.code,
      // B14 rule 19 — a KEY and not a sentence (`DEF-510`). p070 draws the
      // placeholder as `Search payout or reference…`, and the server's `q`
      // matches exactly those two things.
      searchPlaceholder: "payments.settlement.list.search",
      searchFields: ["code", "provider"],
      defaultSort: { sort: INITIAL_STATE.sort, dir: INITIAL_STATE.dir },
      filters: [
        {
          // ⚠ **TWO OPTIONS, BECAUSE THE TABLE HAS TWO STATES.** They are the
          // `settlements.status` domain in full — the database refuses a third
          // — and the fourth tile (UNMATCHED) is the same question asked as a
          // figure. A filter the drawing does not evidence would be a control
          // B14 rule 41 did not ask for.
          name: SETTLEMENT_STATE_FILTER,
          label: t("payments.settlement.list.filter.state"),
          options: [
            {
              value: SETTLEMENT_MATCHED,
              label: t("payments.settlement.state.matched"),
            },
            {
              value: SETTLEMENT_RECEIVED,
              label: t("payments.settlement.state.unmatched"),
            },
          ],
        },
        {
          // p070's ② — *"Provider · one, two or three per utility"*. The
          // options are the ones actually on file, served beside the tiles, so
          // a two-item dropdown costs no second request and cannot offer a
          // processor this utility has never been paid by.
          name: SETTLEMENT_PROVIDER_FILTER,
          label: t("payments.settlement.list.filter.provider"),
          options: (totals?.providers ?? []).map((provider) => ({
            value: provider,
            label: provider,
          })),
        },
      ],
      columns: [
        {
          key: "code",
          label: t("payments.settlement.list.col.settlement"),
          sortable: true,
          identity: true,
          // B14 rule 31 — the PROVIDER'S own reference, which is what the
          // clerk is reading off the processor's statement and what the
          // address bar carries. There is no id to show and none is sent.
          cell: (row) => row.code,
        },
        {
          key: "provider",
          label: t("payments.settlement.list.col.provider"),
          sortable: true,
          // ⚠ A `provider_key` FROM THE TENANT'S OWN CONNECTION, RENDERED AS
          // DATA. `BR-INT-037` and `G77` forbid a vendor name written into our
          // code; this cell writes none — it prints what the row carries.
          cell: (row) => row.provider,
        },
        {
          key: "paid_out_at",
          label: t("payments.settlement.list.col.paidOut"),
          sortable: true,
          cell: (row) => (
            <DateCell
              value={row.paid_out_at}
              timeZone={timeZone}
              dateFormat={dateFormat}
              withTime
            />
          ),
        },
        {
          key: "payments",
          label: t("payments.settlement.list.col.payments"),
          sortable: true,
          numeric: true,
          cell: (row) => row.payments,
        },
        {
          key: "gross",
          label: t("payments.settlement.list.col.gross"),
          sortable: true,
          numeric: true,
          cell: (row) => (
            <SettlementMoney amount={row.gross} currency={row.currency} locale={props.locale} />
          ),
        },
        {
          key: "fees",
          label: t("payments.settlement.list.col.fees"),
          numeric: true,
          // ⚠ NOT SORTABLE, AND THAT IS THE DRAWING. p070 puts a ⇅ on
          // SETTLEMENT, PROVIDER, PAID OUT, GROSS, NET and BANK and none on
          // FEES or PAYMENTS-as-money. A control the drawing does not draw is
          // one B14 rule 41 did not ask for.
          cell: (row) => (
            <SettlementMoney amount={row.fees} currency={row.currency} locale={props.locale} />
          ),
        },
        {
          key: "net",
          label: t("payments.settlement.list.col.net"),
          sortable: true,
          numeric: true,
          cell: (row) => (
            <SettlementMoney amount={row.net} currency={row.currency} locale={props.locale} />
          ),
        },
        {
          // ③ — *"Bank · a payout is one bank line, which is why the batch
          // exists"*. The pill and the credit's reference are ONE fact the
          // database keeps agreeing (`ck_settlements_matched_has_line`).
          key: "status",
          label: t("payments.settlement.list.col.bank"),
          sortable: true,
          cell: (row) => <BankMark status={row.status} reference={row.bank_reference} t={translate} />,
        },
        {
          key: "actions",
          label: t("payments.settlement.list.col.actions"),
          locked: true,
          cell: (row) => (
            <SettlementRowActions t={t} viewHref={tenantPath(settlementRoute(row.code))} />
          ),
        },
      ],
    }),
    [t, translate, tenantPath, timeZone, dateFormat, props.locale, totals?.providers],
  );

  return (
    <>
      <KPIStrip
        loading={query.isLoading}
        kpis={[
          totals?.paid_out_today == null
            ? {
                id: "paid-out-today",
                label: t("payments.settlement.kpi.paidOutToday"),
                value: <span className="text-neutral-700">—</span>,
                detail: t("payments.settlement.kpi.noDay"),
              }
            : {
                id: "paid-out-today",
                label: t("payments.settlement.kpi.paidOutToday"),
                money: {
                  amount: totals.paid_out_today,
                  currency,
                  basis: "clearing",
                  locale: props.locale,
                },
                detail:
                  totals.paid_out_today_providers == null
                    ? undefined
                    : t("payments.settlement.kpi.paidOutTodayDetail", {
                        count: totals.paid_out_today_providers,
                      }),
              },
          // ① — *"Awaiting settlement · the third state no requirement names ·
          // taken, not yet paid out"*. It is NOT day-shaped, so it always
          // answers: it is a question about MEMBERSHIP and TENDER, never about
          // a clock. See `settlements_read.PROVIDER_SETTLED_TENDERS` for why
          // the till's cash is *never settled* rather than *awaiting*.
          totals === undefined
            ? {
                id: "awaiting-settlement",
                label: t("payments.settlement.kpi.awaiting"),
                value: <span className="text-neutral-700">—</span>,
              }
            : {
                id: "awaiting-settlement",
                label: t("payments.settlement.kpi.awaiting"),
                money: {
                  amount: totals.awaiting_settlement,
                  currency,
                  basis: "posting",
                  locale: props.locale,
                },
                detail: t("payments.settlement.kpi.awaitingDetail", {
                  count: totals.awaiting_settlement_payments,
                }),
              },
          totals?.fees_this_month == null
            ? {
                id: "fees-this-month",
                label: t("payments.settlement.kpi.fees"),
                value: <span className="text-neutral-700">—</span>,
                detail: t("payments.settlement.kpi.noDay"),
              }
            : {
                id: "fees-this-month",
                label: t("payments.settlement.kpi.fees"),
                money: {
                  amount: totals.fees_this_month,
                  currency,
                  basis: "posting",
                  locale: props.locale,
                },
                // ⚠ **THE DRAWING'S SUB-LINE READS *"1.9% of card takings"* AND
                // THIS ONE SAYS *provider takings*.** The same drawing's own
                // table lists an ACH payout, so two halves of ONE drawing
                // describe one denominator two ways — B14 rule 37's exact
                // case. The SHAPE they agree on is a percentage under FEES,
                // and the word is the true one: a share that included ACH and
                // called itself *card* would be a false sentence on a money
                // tile. Recorded on `CR-139-BRC07`'s `P5.7` row.
                detail:
                  totals.fees_share_of_takings == null ? undefined : (
                    <>
                      <Percent value={totals.fees_share_of_takings} />{" "}
                      {t("payments.settlement.kpi.feesDetail")}
                    </>
                  ),
              },
          {
            // ④ — the drawing's own fourth tile. Not day-shaped either: a
            // payout is matched or it is not.
            id: "unmatched",
            label: t("payments.settlement.kpi.unmatched"),
            value: totals?.unmatched ?? "—",
            detail: t("payments.settlement.kpi.unmatchedDetail"),
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
            ? {
                reason: t("payments.settlement.list.failed"),
                onRetry: () => void query.refetch(),
              }
            : null
        }
        // B14 rule 17 — what is missing, and what fills it. ⚠ **NO CTA**: the
        // thing that fills this list is a provider feed delivering a payout,
        // which is not a button a clerk can press. An empty state offering one
        // would be a live control over a door nobody opens.
        empty={{
          title: t("payments.settlement.list.empty.title"),
          helper: t("payments.settlement.list.empty.helper"),
        }}
      />
    </>
  );
}

export default SettlementsTab;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-139-BRC07 §4 row `P5.7` · blueprint p069–p072 as images at 2.0 · DEF-PAY-6286 (the read no task row owned, built in this commit)
// generated: 2026-09-23 by LANE P5-SCREENS
// checklist: A✔ B✔ C✔ D=n/a(no write exists — p072 step 3) E✔(the tab's hold comes off in this commit) F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/payments/settlementScreens.dom.test.tsx · vitest src/features/payments/sevenTabs.dom.test.tsx · G31 · routeBUtilities.test.ts
// exceptions: (1) the FEES tile's sub-line says *provider takings* where the drawing says *card takings* — the same drawing lists an ACH payout, so B14 rule 37 settles it on the shape both halves agree on · (2) the row's `…` overflow glyph is not built: p072's step 3 says a settlement has no actions
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
