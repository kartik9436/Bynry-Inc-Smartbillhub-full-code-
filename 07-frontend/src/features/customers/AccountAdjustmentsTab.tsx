// ── Trace ──────────────────────────────────────────────
// Change:   B14 rule 41 (PO 2026-09-13) — the product UI matches the blueprint
//           EXACTLY. `ACC-T09`, the Adjustments tab of `02-account-detail.md`.
// Story:    US-CUS-011 · screen S21, tab `?tab=adjustments`.
// Rules:    B14 rule 16 (every list table carries the pagination footer) ·
//           rule 19 (the search prompt names what it matches) · rule 20 (one
//           table type) · rule 21 (Tailwind utilities; this file adds NO class
//           to a stylesheet and IS registered in `styles/route-b-migrated.txt`)
//           · rule 31 (no database id on screen) · rule 33 (on-screen text is
//           capped by what it is for — and RATIONALE is ZERO words on screen)
//           · rule 36 (compose the kit) · rule 41 (the drawing is the scope) ·
//           BR-CUS-034 (customers keeps no copy of another module's row) ·
//           BR-SHL-034 (one date formatter) · CLAUDE.md hard rule 2 (money
//           stored to 4 decimals, DISPLAYED at 2).
// ───────────────────────────────────────────────────────
//
// ── THE DRAWING, QUOTED RATHER THAN LINKED ─────────────────────────────────
// `04-docs/05-modules/03-customers/blueprint/02-account-detail.md`, `ACC-T09`:
//
//   toolbar  `All`  `Filter ▾`  `⚲ Search`  `Columns ▾`  `⇩ Export`
//            and the tab's own `New adjustment`
//   columns  `DATE` · `ADJUSTMENT #` · `REASON` · `APPLIED TO` · `AMOUNT` ·
//            `APPROVED BY`
//   footer   `1–3 of 3  ·  Rows per page 50  ‹ ›`
//
// **ALL SIX COLUMNS ARE BUILT, IN THAT ORDER.**
//
// ── WHAT CHANGED HERE, AND WHY IT IS A DEFECT FIX RATHER THAN A FEATURE ────
//
// This tab drew the six column heads over ONE spanning cell and listed nothing.
// The blueprint's own annotation says why it was written that way — *"no
// endpoint lists an adjustment and none posts one"* — and **both halves of that
// sentence are now false**:
//
//   · `POST /accounts/{id}/payments` with `type: "adjustment"` has existed
//     since `CR-059` CS-35, and `AdjustModal` is its door. The tab's own
//     `+ New adjustment` was released for it on 2026-09-13.
//   · `GET /payments` accepts `f.account_id` AND `f.type` (`PAYMENT_FILTERS`,
//     server-side `payments/selectors.PAYMENT_FILTERS`), pages in the database
//     and serves `posted_at`, `payment_no`, `amount`, `currency` and the
//     `applied_to` allocations. **Nothing called it with `f.type=adjustment`.**
//
// An endpoint that exists and has no caller is a defect, not a gap, so it is
// wired. Four of the six drawn columns come straight off that row.
//
// ── THE OTHER TWO COLUMNS, AND WHY THEY ARE STILL DRAWN ────────────────────
//
// **`REASON` and `APPROVED BY` have no column anywhere in this product.**
//
//   · The reason a clerk types travels to `record_payment` as `reason_code`
//     and is written into the `audit_log` row and nowhere else —
//     `payments/services.py` says so in terms: *"The reason has no column on
//     `payments` … and this row is where it is kept."* `audit_log` is pruned
//     on a retention schedule, so it is not a store this table may read as
//     though it were permanent (CLAUDE.md hard rule 4's own warning about
//     `OQ-1340`).
//   · Nothing records who APPROVED an adjustment, at either end: the same
//     question is open from Runbook 9's side.
//
// So each cell states its own absence in two words rather than going blank,
// showing `$0.00`, or dropping the column — all three of which are claims about
// a customer that nobody made. `NotRecorded` is the house device for *the
// server refuses to hold this*, as distinct from `AwaitsCell`, which promises a
// figure is coming. **Nothing is coming; no column exists to fill.**
//
// ⚠ **THE EXPLANATION ABOVE IS ZERO WORDS ON SCREEN (B14 rule 33).** The tab
// used to carry it as a sentence — *"Adjustments show on the Payments tab,
// marked Adjustment. This table needs two facts nothing keeps yet — the reason
// and who approved it."* — which is RATIONALE, and rule 33 puts rationale in
// the code and in the register. This comment IS where it went.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getPayments } from "@/api/endpoints";
import type { PaymentRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { InlineLinkTo } from "@/components/Surfaces";
import { paymentDetailRoute } from "@/features/payments/paymentDetailShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { tenantPathFrom, useTenant } from "@/routing/tenantPath";

import { Dash, NotRecorded } from "./customersShared";

/** The screen id `TableConfig` keys its column preference on — S21's own tab,
 *  so a clerk's chosen columns survive leaving the account and coming back. */
const ADJUSTMENTS_TABLE_SCREEN = "S21.adjustments";

/** `payments.type`, the one value this tab lists. Declared once so the query
 *  key and the request cannot come to disagree. */
const ADJUSTMENT_TYPE = "adjustment";

export function accountAdjustmentsKey(accountId: string, state: TableRequestState) {
  return ["account-adjustments", accountId, state.q, state.sort, state.dir, state.page, state.per] as const;
}

/**
 * The request this tab makes, as data.
 *
 * ⚠ **IT IS A FUNCTION SO THAT A TEST CAN ASSERT THE THING THE TAB ACTUALLY
 * SENDS, AND THAT IS NOT TIDINESS — IT IS LAW 7.** The first version of the
 * law-2 case read the URL out of a stubbed `fetch`, and `renderToStaticMarkup`
 * fires no queries: every URL it saw was the HARNESS'S OWN prefetch, so
 * deleting `f.type=adjustment` from the component left the case green. A check
 * that cannot fail is worse than none, because it is trusted. The component
 * and the case now read the SAME builder, so the filters cannot differ.
 *
 * ⚠ **BOTH FILTERS, AND THE SECOND IS THE WHOLE TAB.** `f.account_id` alone
 * lists every payment on the account; `f.type=adjustment` is what makes this
 * the Adjustments tab rather than a second Payments tab.
 */
export function accountAdjustmentsRequest(accountId: string, state: TableRequestState) {
  return {
    q: state.q,
    sort: state.sort,
    dir: state.dir,
    page: state.page,
    per: state.per,
    filters: { account_id: accountId, type: ADJUSTMENT_TYPE },
  };
}

/**
 * What this adjustment was taken off — the bills its allocations met.
 *
 * ⚠ **B14 rule 31 — `invoice_id` IS NEVER THE VISIBLE VALUE.** The row carries
 * both the id and billing's own number; the number is what a customer is
 * holding and what a clerk says on the phone. An allocation whose number
 * billing could not resolve contributes nothing to the sentence rather than a
 * uuid, and an adjustment that met no bill draws a dash — it is carried as
 * credit, which is a real state and not a missing value.
 */
export function appliedToLabel(row: PaymentRow): string | null {
  const numbers = row.applied_to
    .map((entry) => entry.invoice_number)
    .filter((number): number is string => number !== null && number !== "");
  return numbers.length === 0 ? null : numbers.join(" · ");
}

export function adjustmentsTableConfig(
  t: Translator,
  cells: {
    date: (row: PaymentRow) => JSX.Element;
    amount: (row: PaymentRow) => JSX.Element;
    /** Record links (PO 2026-10-19): the adjustment's number. Absent, it is
     *  plain text — a bare config, as a test builds it. */
    number?: (row: PaymentRow & { payment_no: string }) => JSX.Element;
  },
): TableConfig<PaymentRow> {
  /** The two facts nothing in this product keeps. One element, two columns —
   *  written once so the two cells cannot drift into two different sentences. */
  const notKept = (
    <NotRecorded
      label={t("customers.account.adjustments.notKept")}
      why={t("customers.account.adjustments.notKeptWhy")}
    />
  );
  return {
    screenId: ADJUSTMENTS_TABLE_SCREEN,
    getRowId: (row) => row.id,
    // IS-3 — what the server's own `q` matches on a payments list.
    searchFields: ["adjustmentNo", "appliedTo"],
    // B14 rule 19 — the prompt names WHAT the box matches, never "Search this
    // list".
    searchPlaceholder: "customers.account.adjustments.search",
    // The drawing's toolbar carries `Filter ▾` over a single `All` chip, which
    // is a filter control with nothing to choose. The only dimension this list
    // HAS is already spent — every row is `f.type=adjustment` — so no filter is
    // declared, and BR-SHL-010 keeps an undeclared capability unrendered rather
    // than drawing an empty menu.
    defaultSort: { sort: "posted_at", dir: "desc" },
    columns: [
      {
        key: "date",
        label: t("customers.account.adjustments.col.date"),
        sortable: true,
        cell: cells.date,
      },
      {
        key: "adjustmentNo",
        label: t("customers.account.adjustments.col.adjustmentNo"),
        // B14 rule 31 + BR-SHL-013 — the number is the identity and can never
        // be hidden. A row minted before the series existed has none and draws
        // a dash rather than its id.
        identity: true,
        cell: (row) =>
          row.payment_no === null ? (
            <Dash />
          ) : cells.number !== undefined ? (
            cells.number({ ...row, payment_no: row.payment_no })
          ) : (
            <span className="tabular-nums">{row.payment_no}</span>
          ),
      },
      {
        key: "reason",
        label: t("customers.account.adjustments.col.reason"),
        cell: () => notKept,
      },
      {
        key: "appliedTo",
        label: t("customers.account.adjustments.col.appliedTo"),
        cell: (row) => {
          const label = appliedToLabel(row);
          return label === null ? <Dash /> : <span>{label}</span>;
        },
      },
      {
        key: "amount",
        label: t("customers.account.adjustments.col.amount"),
        numeric: true,
        sortable: true,
        cell: cells.amount,
      },
      {
        key: "approvedBy",
        label: t("customers.account.adjustments.col.approvedBy"),
        cell: () => notKept,
      },
    ],
  };
}

/**
 * S21's **Adjustments** tab — every adjustment on this account.
 *
 * `onNew` opens the same modal the page header's `Adjust` opens: one action,
 * one door. ⚠ **IT IS PASSED BY `AccountDetailPage` AND MUST STAY PASSED** —
 * an optional prop nothing passes is dead UI, which is hard-won law 2 and four
 * defects in one day.
 */
export function AccountAdjustmentsTab(props: {
  accountId: string;
  client?: ApiClient;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onNew?: () => void;
}) {
  const { t } = props;
  const { i18n } = useTranslation();
  const client = props.client ?? api;
  const tenant = useTenant();
  const tenantPath = (path: string) => tenantPathFrom(tenant, path);

  const config = useMemo(
    () =>
      adjustmentsTableConfig(t, {
        // BR-SHL-034 — ONE date formatter in this product. `posted_at` is NOT
        // NULL on the column; the dash is here because the wire type says it
        // can be absent, never because the product expects it.
        date: (row) => (
          <DateCell value={row.posted_at} timeZone={props.timeZone} dateFormat={props.dateFormat} />
        ),
        // CLAUDE.md hard rule 2 — stored to four decimals, DISPLAYED at two,
        // beside the CHAR(3) the server sent. The sign is the server's and is
        // never flipped here: a correction that ADDS a charge is a positive
        // adjustment and reads as one.
        amount: (row) => (
          <MoneyCell amount={row.amount} currency={row.currency} locale={i18n.language} />
        ),
        // Record links (PO 2026-10-19): an adjustment IS a payments row
        // (`f.type=adjustment`), and the payment page resolves its `PMT-`
        // number like any other — so the number opens it.
        number: (row) => (
          <InlineLinkTo className="tabular-nums" to={tenantPath(paymentDetailRoute(row.payment_no))}>
            {row.payment_no}
          </InlineLinkTo>
        ),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t, i18n.language, props.timeZone, props.dateFormat, tenant],
  );

  const [state, setState] = useState<TableRequestState>(() => defaultRequestState(config));

  const listQuery = useQuery({
    queryKey: accountAdjustmentsKey(props.accountId, state),
    queryFn: () => getPayments(accountAdjustmentsRequest(props.accountId, state), client),
    retry: false,
    enabled: props.accountId !== "",
  });

  return (
    /* `data-account-overview` and the per-group `data-overview-group` hook are
       what the BROWSER census selects on (`10-scripts/render-checks/
       acc02-tab-conformance.mjs`): jsdom computes no layout, so no vitest case
       in this repo can say the screen LOOKS like the drawing. One column on
       this tab, because the drawing gives it one. */
    <div data-account-overview="">
      <div className="flex min-w-0 flex-col">
        <Panel
          as="section"
          tone="group"
          data-overview-group="adjustments"
          data-screen={ADJUSTMENTS_TABLE_SCREEN}
          title={t("customers.account.tab.adjustments")}
          /* The drawing makes `New adjustment` the tab's PRIMARY. It is a
             secondary here: the page header already carries this screen's one
             primary (`Record payment`, BR-SHL-044 / B14 rule 4), which is the
             same choice the Documents tab beside it makes. */
          trailing={
            <Button variant="secondary" onClick={() => props.onNew?.()}>
              {t("customers.account.adjustments.new")}
            </Button>
          }
        >
          <DataTable<PaymentRow>
            config={config}
            state={state}
            onStateChange={setState}
            rows={listQuery.data?.results ?? []}
            totalRows={listQuery.data?.count ?? null}
            loading={listQuery.isPending}
            error={
              listQuery.isError
                ? {
                    reason: t("customers.account.adjustments.loadFailed"),
                    onRetry: () => void listQuery.refetch(),
                  }
                : null
            }
            empty={{
              title: t("customers.account.adjustments.empty"),
              helper: t("customers.account.adjustments.emptyHelper"),
              ctaLabel: t("customers.account.adjustments.new"),
              ctaVariant: "secondary",
              onCta: () => props.onNew?.(),
            }}
          />
        </Panel>
      </div>
    </div>
  );
}

export default AccountAdjustmentsTab;

// ── Lifecycle ─────────────────────────────────────────────
// generated: 2026-09-13 by the ACC-02 conformance lane (tabs Usage · Meters ·
//            Work · Adjustments)
// exceptions: E3 no `Filter ▾` menu is declared — the list's only dimension is
//             already spent on `f.type=adjustment`, and BR-SHL-010 keeps an
//             undeclared capability unrendered rather than drawing an empty
//             one · E3 no `⇩ Export`: `POST /exports` resolves only the
//             resources a module REGISTERS and nothing registers an adjustments
//             list, so a download button here would be wired to a 404 (the
//             same sentence `AccountDocumentsTab` already makes)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
