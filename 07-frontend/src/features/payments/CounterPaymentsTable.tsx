// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.6` — the list under §03 frame **3·2 My
//           counter**, `05-prototype/06 Payments Page Blueprint.pdf` p053,
//           read as an IMAGE at scale 2.0 (B14 rule 42).
// Screens:  `PAY-07`
// Rules:    B14 rules 12–17 (the toolbar, sorting, the column chooser, the
//           pagination footer, the empty state) · rule 31 (the PAYMENT #
//           column shows the payment's NUMBER, never its id) · rule 33 ·
//           rule 43 · rule 21 · BR-SHL-011 (the URL grammar) · BR-SHL-023
// Tests:    src/features/payments/counterScreens.dom.test.tsx
// ───────────────────────────────────────────────────────
// What this till has taken, payment by payment.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ WHY THIS IS A NEW COMPONENT AND NOT `PaymentsPage`'s LIST — REPORTED
// ══════════════════════════════════════════════════════════════════════════
// p053's *To build* row reads: *"`GET /counters/{id}` and its running totals.
// **The payments list underneath is the existing one, filtered by batch.**"*
// That is the right instruction and this lane could not follow it literally:
// **`PaymentsPage`'s list is not a component.** It is a `TableConfig` built
// inside a 3,342-line page body, wired to that page's own filters, bulk bar,
// record modal, detail drawer and eight catalogue families. There is nothing
// exported to mount.
//
// Extracting it is real work with a real blast radius — it is the list behind
// four tabs — and doing it inside a screen wave is how a wave grows while it
// is being built. So this draws p053's OWN eight columns over the same
// endpoint (`GET /payments`, narrowed by batch), and **the gap is FILED rather
// than quietly absorbed**: the extraction is named in `P2.6`'s row on the CR.
//
// It composes the shared `DataTable`, so rules 12–17 come from the kit and
// this file declares no second table (B14 rule 20).
import { useMemo, useState } from "react";

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getPayments } from "@/api/endpoints";
import type { PaymentRow } from "@/api/endpoints";
import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";

import { counterPaymentsQueryKey } from "./counterQueries";
import { Money, appliedBills } from "./paymentsShared";

/**
 * ⚠ **THE FILTER IS THE COUNTER'S CODE, SENT AS A DECLARED `f.<name>`
 * PARAM** — BR-SHL-011's grammar, and the same shape every other list on this
 * page already uses. It is not a second endpoint and not a path segment: the
 * payments list is one list, narrowed.
 */
export const COUNTER_BATCH_FILTER = "counter";

export interface CounterPaymentsTableProps {
  counterCode: string;
  client?: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  locale?: string;
}

export function CounterPaymentsTable(props: CounterPaymentsTableProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const [state, setState] = useState<TableRequestState>({
    q: "",
    // p053 draws the newest payment first — 11:42 above 10:15 above 09:31.
    // ⚠ **`posted_at` AND NOT `taken`**: `PAYMENT_SORTS` is the server's own
    // sortable set and a column key it does not know is a sort that silently
    // does nothing. The COLUMN is headed *Taken*, which is the drawing's word.
    sort: "posted_at",
    dir: "desc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  });

  const config = useMemo<TableConfig<PaymentRow>>(
    () => ({
      // Its own suffix so the clerk's column choice here does not overwrite
      // the one they made on the main payments list (BR-SHL-013).
      screenId: "PAY-07.payments",
      getRowId: (row) => row.id,
      // p053: `Search account #, customer or reference…`.
      searchPlaceholder: "payments.counter.detail.searchPayments",
      searchFields: ["account_no", "customer_name", "reference"],
      defaultSort: { sort: "posted_at", dir: "desc" },
      columns: [
        {
          key: "payment_no",
          label: t("payments.counter.detail.col.paymentNo"),
          sortable: true,
          identity: true,
          // B14 rule 31 — the payment's human-facing NUMBER. `PMT-2609-000418`
          // is what a clerk reads out; `row.id` never reaches the screen.
          cell: (row) => row.payment_no ?? t("payments.counter.detail.noNumber"),
        },
        {
          key: "posted_at",
          label: t("payments.counter.detail.col.taken"),
          sortable: true,
          cell: (row) => (
            <DateCell
              value={row.posted_at}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
              withTime
            />
          ),
        },
        {
          key: "account",
          label: t("payments.counter.detail.col.account"),
          sortable: true,
          cell: (row) => row.account_no ?? "—",
        },
        {
          key: "customer",
          label: t("payments.counter.detail.col.customer"),
          cell: (row) => row.customer_name ?? "—",
        },
        {
          key: "method",
          label: t("payments.col.method"),
          cell: (row) => row.method_name ?? row.method ?? "—",
        },
        {
          key: "reference",
          label: t("payments.counter.detail.col.reference"),
          cell: (row) => row.confirmation ?? "—",
        },
        {
          key: "applied_to",
          label: t("payments.counter.detail.col.appliedTo"),
          // p053 draws ONE bill number per row. A payment can be split across
          // several, so the cell names the first and says how many more — a
          // FACT of at most six words (B14 rule 33), never a wrapped list that
          // sets the height of the whole row.
          cell: (row) => {
            const bills = appliedBills(row);
            if (bills.length === 0) {
              return <span className="text-neutral-700">{t("payments.counter.detail.unapplied")}</span>;
            }
            if (bills.length === 1) {
              return bills[0].invoiceNumber ?? t("payments.counter.detail.unapplied");
            }
            return t("payments.counter.detail.appliedPlus", {
              first: bills[0].invoiceNumber ?? "",
              more: bills.length - 1,
            });
          },
        },
        {
          key: "amount",
          label: t("payments.counter.detail.col.amount"),
          sortable: true,
          numeric: true,
          cell: (row) => <Money amount={row.amount} currency={row.currency} />,
        },
      ],
    }),
    [t, props.timeZone, props.dateFormat],
  );

  // ⚠ **A `ListRequest`, NOT A `URLSearchParams`.** `getPayments` owns the
  // `f.<name>` spelling through `listQuery`, and BR-SHL-011 says only SET
  // values travel — building the query string here would be a second
  // serialiser free to disagree with the one every other payments list uses.
  const request = useMemo(
    () => ({
      q: state.q === "" ? undefined : state.q,
      sort: state.sort,
      dir: state.dir,
      page: state.page,
      per: state.per,
      filters: { ...state.filters, [COUNTER_BATCH_FILTER]: props.counterCode },
    }),
    [state, props.counterCode],
  );

  const query = useQuery({
    queryKey: [...counterPaymentsQueryKey(props.counterCode), JSON.stringify(request)],
    queryFn: () => getPayments(request, client),
  });

  return (
    <DataTable
      config={config}
      state={state}
      onStateChange={setState}
      rows={query.data?.results ?? []}
      totalRows={query.data?.count ?? null}
      loading={query.isLoading}
      error={
        query.isError
          ? {
              reason: t("payments.counter.detail.paymentsFailed"),
              onRetry: () => void query.refetch(),
            }
          : null
      }
      // B14 rule 17. ⚠ **NO CTA**, and the absence is deliberate rather than
      // forgotten: `DataTable`'s `ctaLabel` has been optional since
      // `DEF-MET-4764` precisely so a list whose one way in lives in the page
      // head does not draw a second button onto the same form.
      empty={{
        title: t("payments.counter.detail.empty.title"),
        helper: t("payments.counter.detail.empty.helper"),
      }}
    />
  );
}

export default CounterPaymentsTable;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-136-BRC07 §4 row `P2.6` · blueprint p053 as an image at 2.0
// generated: 2026-09-23 by LANE P2-SCREENS
// checklist: A✔ B=n/a(the `f.counter` filter is `P2.3`/`P2.8`'s to serve) C✔ D=n/a E✔ F✔ G✔ H=n/a
// exceptions: E3 p053 says *"the existing list, filtered by batch"* and `PaymentsPage`'s list is not an extractable component — this draws p053's own columns over the same endpoint and the extraction is FILED on the CR · E3 the `f.counter` filter is not served at this commit · E3 no ACTIONS column: the drawing sketches 👁 ✎ … and p053's *Write surfaces* row gives this screen `Detail → 2·2 · Add → 2·3a · Update → 3·3b` — none of which is a row act on a payment from here
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
