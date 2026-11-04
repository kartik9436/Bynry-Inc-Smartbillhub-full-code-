// ── Trace ──────────────────────────────────────────────
// Change:   CR-140-BRC09 · Finance blueprint `P4.11` — 4·1 grows a second
//           panel, **Payments made**. p058 draws it; p059 items 3 and 4 are its
//           specification.
// Task:     `P4.11` the panel · it reads what `P4.4`'s `tax_remittances`
//           records and shows the receipt `P4.3` keeps
// Rules:    B14 rule 12 (the table toolbar, in the product's order) · rule 13
//           (sorting) · rule 16 (the pagination footer) · rule 21 (Tailwind
//           utilities, NO class added to any stylesheet — this file is on
//           `src/styles/route-b-migrated.txt`) · rule 31 (no database id is
//           ever the visible value of a field) · rule 32 (a stated absence is a
//           disclosure CLOSED by default) · rule 43 (a piece of UI is a
//           COMPONENT) · BR-LED-019 (the filing confirmation ref and the
//           receipt are the auditor artefacts) · BR-REP-002 (the books are the
//           number that has to be right)
// Tests:    src/features/ledger/paymentsMade.dom.test.tsx
// Impacts:  features/ledger/RemittancePage.tsx (mounts it under 4·1's own
//           table) · apps/ledger/finance_api.py `_filing_history`
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS CLOSES, IN THE BLUEPRINT'S OWN WORDS
// ══════════════════════════════════════════════════════════════════════════
// p058: *"YOU CAN RECORD A TAX PAYMENT AND NEVER SEE IT AGAIN."*
// `POST /finance/taxes/remittances` existed, there was **no GET and no table**,
// and the screen rendered what you OWE by authority with a Record pop-up over
// it. So an officer asked *"did we pay Bexar County in August?"* left Finance,
// opened the journal and filtered by source — *"which works, because the entry
// is stamped `SOURCE_REMITTANCE`, but only if you know"* — and **owed and paid
// never appeared on the same screen, which is the one comparison this tab
// exists to make.**
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THIS PANEL IS NOT WHERE `REMITTED` COMES FROM
// ══════════════════════════════════════════════════════════════════════════
// The table ABOVE this one reads its REMITTED column out of the BOOKS —
// `reporting.remittance_by_authority` sums remittance-sourced debits per
// 2200-nn account — and goes on doing so. `BR-REP-002` makes the books the
// number that has to be right and a register is a convenience over them. Two
// independent totals of one fact is exactly how the two panels on one screen
// come to disagree, and the one that would be wrong is the one nobody posts to.
//
// So this lists FILINGS. It never sums them into anything the panel above
// states, and it draws no total of its own for the same reason.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE EARLIER FILINGS ARE COUNTED, NOT HIDDEN
// ══════════════════════════════════════════════════════════════════════════
// Every remittance recorded before 2026-09-24 posted a journal entry and
// nothing else, so it has no register row and cannot grow one: its confirmation
// reference survives on the immutable entry memo and in `audit_log`, which is
// pruned. The server counts those entries (`journal_only`) and this states the
// count.
//
// **A declared blind spot with no number beside it is indistinguishable from an
// empty one** — hard-won law 7, and `G32` reporting `0 unresolved` over 21 live
// refusals is this repository's own worked example. A panel that simply listed
// what it had would look complete and be short.
import { useState } from "react";

import { apiHref } from "@/api/apiHref";
import type { RemittancePaidRow, RemittancePaidResponse } from "@/api/endpoints";
import { AbsentFigure } from "@/components/AbsentFigure";
import { clientPage } from "@/components/clientTable";
import type { ClientTableSpec } from "@/components/clientTable";
import { DataTable } from "@/components/DataTable";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { InlineLinkTo } from "@/components/Surfaces";
import type { Translator } from "@/features/tenancy/settingsShared";
import { journalEntryDetailPath } from "./JournalEntryDetail";

/** How the browser narrows and orders the filing history.
 *
 * ⚠ **THE ACCESSORS ARE WRITTEN OUT RATHER THAN INDEXED BY KEY.**
 * `row[state.sort]` returns `undefined` for a key nobody mapped and then
 * "sorts" every row equal — a check that cannot fail, with the header cycling
 * and the list never reordering. `clientTable`'s own header says so. */
export const PAYMENTS_MADE_SPEC: ClientTableSpec<RemittancePaidRow> = {
  // p058 draws the prompt: *"Search authority or confirmation…"*, and those are
  // exactly the two fields it matches (B14 rule 19).
  search: (row) => [row.authority, row.confirmation_ref],
  filter: () => true,
  sortValue: (row, key) => {
    switch (key) {
      case "authority":
        return row.authority;
      case "period":
        return row.period.start;
      case "paid_on":
        return row.paid_on;
      case "amount":
        // Decides an ORDER only; the figure itself stays `MoneyCell`'s.
        return Number(row.amount);
      case "confirmation_ref":
        return row.confirmation_ref;
      case "entry":
        return row.entry_no;
      default:
        return null;
    }
  },
};

export function paymentsMadeConfig(params: {
  t: Translator;
  currency: string | null;
  locale?: string;
  tenantPath: (path: string) => string;
}): TableConfig<RemittancePaidRow> {
  const { t } = params;
  return {
    screenId: "FIN-04.1.paid",
    searchPlaceholder: "finance.taxes.paid.search",
    defaultSort: { sort: "paid_on", dir: "desc" },
    getRowId: (row) => row.id,
    searchFields: ["authority", "confirmation_ref"],
    columns: [
      {
        key: "authority",
        label: t("finance.taxes.col.authority"),
        sortable: true,
        // BR-SHL-013 — a filing history with no authority column is not a
        // shorter list, it is a different screen.
        identity: true,
        cell: (row) => row.authority,
      },
      {
        key: "period",
        label: t("finance.taxes.paid.col.period"),
        sortable: true,
        cell: (row) => t("reports.rollup", { from: row.period.start, to: row.period.end }),
      },
      {
        key: "paid_on",
        label: t("finance.taxes.paid.col.paidOn"),
        sortable: true,
        cell: (row) => row.paid_on,
      },
      {
        key: "amount",
        label: t("finance.taxes.paid.col.amount"),
        sortable: true,
        numeric: true,
        cell: (row) => (
          <MoneyCell
            amount={row.amount}
            currency={row.currency || (params.currency ?? "")}
            locale={params.locale}
          />
        ),
      },
      {
        key: "confirmation_ref",
        label: t("finance.taxes.paid.col.confirmation"),
        sortable: true,
        cell: (row) => row.confirmation_ref,
      },
      {
        key: "entry",
        label: t("finance.taxes.paid.col.entry"),
        sortable: true,
        // ⚠ **B14 RULE 31 — THE ENTRY'S DATABASE ID IS NEVER DRAWN.** The row
        // carries `entry_id` for a link and `entry_no` for a person; where the
        // tenant has not seeded the `journal_entry` series (BR-LED-021) the
        // number is NULL and this says so rather than printing a UUID, which is
        // exactly the substitution rule 31 was ratified to stop.
        cell: (row) =>
          row.entry_no === null ? (
            <AbsentFigure
              label={t("finance.absent")}
              reason={t("finance.taxes.paid.noEntryNumber")}
            />
          ) : (
            // Record links (PO 2026-10-19): the number opens the entry.
            <InlineLinkTo to={params.tenantPath(journalEntryDetailPath(row.entry_id))}>
              {row.entry_no}
            </InlineLinkTo>
          ),
      },
      {
        key: "receipt",
        label: t("finance.taxes.paid.col.receipt"),
        cell: (row) =>
          row.receipts.length === 0 ? (
            // `BR-LED-019` asks for a receipt and a filing may lawfully be
            // recorded without one — it arrives by post a week later. An
            // absence with its reason, never a blank cell (P2.14).
            <AbsentFigure
              label={t("finance.absent")}
              reason={t("finance.taxes.paid.noReceipt")}
            />
          ) : (
            // ⚠ **AN ORDINARY LINK, NOT A FETCH — AND THAT IS WHY THE SERVER
            // REDIRECTS.** `GET /accounts/{id}/documents/{docId}` answers
            // `{url}` in a body and has no caller anywhere in this front end,
            // because a screen that fetches a link and then opens it fights the
            // popup blocker: the window must be opened synchronously in the
            // click and the URL only arrives after an await. The remittance
            // receipt route answers 302 instead, so this is a plain anchor —
            // the session cookie authorises the redirect and the browser saves
            // the file. The href is tenant-scoped, because the filing is.
            <a
              className="font-semibold text-accent-700"
              href={apiHref(params.tenantPath(`/finance/taxes/remittances/${row.id}/receipt`))}
              download
            >
              {t("finance.taxes.paid.openReceipt")}
            </a>
          ),
      },
    ],
  };
}

export interface PaymentsMadePanelProps {
  history: RemittancePaidResponse;
  t: Translator;
  locale?: string;
  tenantPath: (path: string) => string;
  loading?: boolean;
}

export function PaymentsMadePanel(props: PaymentsMadePanelProps) {
  const { history, t } = props;
  const [state, setState] = useState<TableRequestState>(() => ({
    q: "",
    sort: "paid_on",
    dir: "desc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  }));
  const config = paymentsMadeConfig({
    t,
    currency: history.currency,
    locale: props.locale,
    tenantPath: props.tenantPath,
  });
  const paged = clientPage(history.rows, state, PAYMENTS_MADE_SPEC);

  return (
    <Panel>
      <div className="mb-3">
        <h3 className="m-0 text-base font-semibold">{t("finance.taxes.paid.title")}</h3>
      </div>
      <DataTable
        config={config}
        state={state}
        onStateChange={setState}
        rows={paged.page}
        totalRows={paged.total}
        loading={props.loading === true}
        empty={{
          title: t("finance.taxes.paid.empty"),
          helper: t("finance.taxes.paid.emptyHelper"),
        }}
      />
      {/* See the header: counted, never hidden. B14 rule 32 puts a stated
          absence in a disclosure CLOSED by default, which `AbsentFigure` is. */}
      {history.journal_only > 0 && (
        <div className="mt-3">
          <AbsentFigure
            label={t("finance.taxes.paid.earlier", { count: history.journal_only })}
            reason={t("finance.taxes.paid.earlierReason")}
          />
        </div>
      )}
    </Panel>
  );
}

export default PaymentsMadePanel;

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/07 Finance Blueprint.pdf p017 (`P4.11`'s row), p058 (4·1
//         drawn with the second panel), p059 (items 3 and 4, the filter-
//         criteria table and the component table) — rendered at scale 3 and
//         read as IMAGES (B14 rule 42) · 04-docs/02-decisions/14-ui-conventions
//         .md rules 12/13/16/21/31/32/43 · 06-backend/apps/ledger/finance_api
//         .py `_filing_history`
// generated: 2026-09-24 by LANE FIN-P4B
// checklist: A✔ B✔ C✔ D✔ E✔(RemittancePage mounts it) F✔ G✔ H=n/a
// exceptions:
//   E1 **NO TOTAL ROW.** p058 draws none and the header says why one would be
//      dangerous: the REMITTED figure belongs to the panel above, read out of
//      the books, and a second sum of the same fact is how two panels on one
//      screen disagree.
//   E2 **PAGED IN THE BROWSER** (`clientPage`). `GET /finance/taxes/remittances`
//      takes no `q`, `sort`, `page` or `per`, so there is nothing to hand a
//      server-paged `DataTable`. It is `NFR-3`'s shape and it is named here: a
//      filing history is bounded by how often a utility files, which is why
//      this is the least urgent of that family and not why it is absent.
//   E3 **ONE RECEIPT IS LINKED, NOT ALL OF THEM.** The wire carries every
//      document on the filing and the route redirects to the FIRST. A filing
//      with two is possible (the receipt and the return) and rare; drawing a
//      list inside a table cell is a second table, which B14 rule 20 refuses.
//      Reported rather than decided silently.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
