// ── Trace ──────────────────────────────────────────────
// Change:   CR-138-BRC07 · P4.26 — "A Kind column and filter on 6·1", over
//           `P4.25`'s union read. Blueprint
//           `05-prototype/06 Payments Page Blueprint.pdf` p023 (the task row)
//           and p072–p074 (screen 6·1, read AS IMAGES at scale 2.0 per B14
//           rule 42). The drawing's Table-controls row, verbatim: *"Three tabs
//           today — approval, issued, all. **The toolbar, the Kind filter and
//           paging are the change.**"*
//           Screens: 6·1 Refunds (S58 · PAY-P)
// Rules:    B14 rule 12 (the table toolbar: search · All · filter chips ·
//           + Filter · ▦ Columns) · rule 13 (sortable headers) · rule 14 (the
//           column selector) · rule 16 (the pagination footer on every list) ·
//           rule 17 (an empty state) · rule 15 (row actions are ICONS) · rule
//           19 (this list's own search prompt) · rule 31 (no database id on
//           screen) · rule 32 (a stated absence, CLOSED by default) · rule 33
//           (a LABEL ≤ 3 words, a FACT ≤ 6) · rule 21 (Tailwind utilities, no
//           stylesheet class — this file is on `styles/route-b-migrated.txt`
//           from its first commit) · rule 43 (a piece of UI is a COMPONENT) ·
//           NFR-3 (server pagination) · NFR-5 (no hard caps)
// Tests:    07-frontend/src/features/payments/refundsAndCredits.dom.test.tsx
// Impacts:  features/payments/RefundsPage.tsx (its only mount) ·
//           features/payments/refundsAndCreditsShared.tsx (the cells) ·
//           api/endpoints.getRefundsAndCredits
// ───────────────────────────────────────────────────────
//
// 6·1 — EVERYTHING GIVEN BACK, IN ONE LIST.
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  "A clerk sees everything given back in one place and can still tell a   ║
// ║   cheque from a credit."                                                 ║
// ╚══════════════════════════════════════════════════════════════════════════╝
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT REPLACED THE THREE STATUS TABS, AND WHY IT IS NOT A LOST CAPABILITY
// ══════════════════════════════════════════════════════════════════════════
// The screen carried a segmented control — *awaiting approval · issued · all* —
// over `GET /refunds`, which is the APPROVAL QUEUE and is unpaginated
// **deliberately**: *"a page of an approval queue is a queue that lies about
// what is pending."* This list asks a different question (*what have we given
// back*) of a different read, and that read accepts `f.kind` and nothing else.
//
// So a status filter here could only be applied **to the rows already
// fetched**, which is a filter that tells the truth on page one and lies on
// page two — `NFR-3`'s own defect, at the ICP's real ceiling. It is therefore
// NOT rendered, and **the approval queue is not lost**: `RefundsQueuePanel`
// inside Finance → Revenue & AR has been the approval door since the PO's
// ruling of 2026-09-03 and still is. State is a COLUMN here, which is what the
// drawing shows.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ TWO DRAWN COLUMNS ARE NOT HERE, AND THAT IS REPORTED RATHER THAN FAKED
// ══════════════════════════════════════════════════════════════════════════
// p073 draws **ACCOUNT** (`AC-2026-00019`) and **CUSTOMER** (`Priya Raman`).
// `GET /refunds-and-credits` serves NEITHER, on either side of the module
// boundary: `payments.selectors.refund_row` and `billing.selectors.
// credit_note_row` each carry `account_id` — a uuid, which B14 rule 31 forbids
// on screen by name — and no customer name crosses the seam at all.
//
// **The alternative was to join per row in the browser**, which is an N+1 from
// a list that must work at 40,000 accounts, and it is the thing `NFR-3` exists
// to prevent. So the two columns are ABSENT, the absence is stated once in a
// disclosure CLOSED by default (rule 32), and it is filed as `DEF-PAY-6279`.
// `CR-059` task 18
// recorded the same gap on this screen's first build as `DEF-3119` and it has
// not moved; this list inherits it rather than papering over it.
import { useMemo } from "react";

import { useTranslation } from "react-i18next";

import { DataTable } from "@/components/DataTable";
import { Disclosure } from "@/components/Disclosure";
import { FilterBar } from "@/components/FilterBar";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import type { RefundLifecycle, RefundsAndCreditsRow } from "@/api/endpoints";
import type { StatusTone } from "@/components/StatusPill";
import type { Translator } from "@/features/tenancy/settingsShared";
import {
  KIND_REFUND,
  RefundAmountCell,
  RefundHowCell,
  RefundKindCell,
  RefundReasonCell,
  RefundReferenceCell,
  RefundStateCell,
  kindFilterOptions,
} from "./refundsAndCreditsShared";

export interface RefundsAndCreditsListProps {
  rows: readonly RefundsAndCreditsRow[];
  /** The SERVER's total, never `rows.length` — a page's length is a page's
   *  length, and a footer that read it would count 50 forever. */
  totalRows: number | null;
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  loading: boolean;
  error?: { reason?: string; onRetry: () => void } | null;
  /** Both carried on every response so the screen holds no second copy of a
   *  fact the server owns. `kinds` fills the filter; `lifecycles` tells the
   *  State cell whether a kind HAS a state at all. */
  kinds: readonly string[];
  lifecycles: Record<string, RefundLifecycle> | undefined;
  statusTone: (status: string) => StatusTone;
  /**
   * WHO IS LOOKING — and the column it draws is a DELIBERATE DIVERGENCE FROM
   * THE DRAWING, recorded rather than taken quietly.
   *
   * p073 draws eight columns and *Raised by* is not one of them. It was on the
   * screen this list replaces, and `RefundsPage` states why in its own words:
   * *"the whole point of naming the raiser is that the person about to approve
   * can see whether it is themselves (`BR-PAY-037`)"*. **The four approval acts
   * still live on these rows**, and `RefundsQueuePanel` — the only other
   * refunds surface — carries no such marker either, so dropping it would
   * remove the affordance from the product entirely rather than move it.
   *
   * `BR-PAY-037` is CONFIRMED and permits one user to initiate and approve, so
   * the marker never BLOCKS; it marks. B14 rule 41 sends a drawing that
   * contradicts a signed rule to the PO, and this is one degree softer than
   * that — a drawing that would quietly delete a shipped affordance — so it is
   * a lane judgment recorded with its reasoning (hard-won law 13) instead.
   *
   * Absent (`undefined`) draws no column at all, which is what a surface with
   * no approval act on it should pass.
   */
  currentUserId?: string | null;
  /** The row actions, drawn ONLY on a refund row — *"✂ appears only on a refund
   *  row; a credit has nothing to void"* (p073, annotation ⑥). Absent draws
   *  none, which is what a screen with no act to offer must do. */
  rowActions?: (row: RefundsAndCreditsRow) => React.ReactNode;
  emptyCtaLabel?: string;
  emptyCtaReason?: string | null;
  onEmptyCta?: () => void;
}

/**
 * The capability row for 6·1.
 *
 * ⚠ **`searchFields` AND `filters` DECLARE ONLY WHAT THE SERVER ACCEPTS.**
 * `BR-SHL-010` makes this config the place a screen says what its table can do,
 * and DataTable renders exactly what is declared — so declaring a control the
 * read cannot honour would put a live box on screen that changes nothing. The
 * read takes `page`, `per` and `f.kind`; that is the whole of it today.
 */
export function refundsAndCreditsConfig(
  t: Translator,
  kinds: readonly string[],
  statusTone: (status: string) => StatusTone,
  lifecycles: Record<string, RefundLifecycle> | undefined,
  rowActions?: (row: RefundsAndCreditsRow) => React.ReactNode,
  currentUserId?: string | null,
): TableConfig<RefundsAndCreditsRow> {
  const columns: TableConfig<RefundsAndCreditsRow>["columns"] = [
    {
      key: "reference",
      label: t("payments.refundsAndCredits.col.reference"),
      identity: true,
      cell: (row) => <RefundReferenceCell row={row} t={t} />,
    },
    {
      key: "kind",
      label: t("payments.refundsAndCredits.col.kind"),
      // ⚠ LOCKED. A list of things given back with no Kind column is not a
      // shorter list, it is a different screen — the reasoning `locked` was
      // added for, and the whole point of this task.
      locked: true,
      cell: (row) => <RefundKindCell row={row} t={t} />,
    },
    {
      key: "reason",
      label: t("payments.refundsAndCredits.col.reason"),
      cell: (row) => <RefundReasonCell row={row} t={t} />,
    },
    {
      key: "how",
      label: t("payments.refundsAndCredits.col.how"),
      cell: (row) => <RefundHowCell row={row} t={t} />,
    },
    {
      key: "amount_returned",
      label: t("payments.refundsAndCredits.col.amount"),
      numeric: true,
      cell: (row) => <RefundAmountCell row={row} />,
    },
    {
      key: "state",
      label: t("payments.refundsAndCredits.col.state"),
      // ⚠ THE ⓘ POINTS AT THE DISCLOSURE BELOW, whose summary this string IS —
      // *"pass the DISCLOSURE'S OWN SUMMARY here so the marker and the thing it
      // points at read as one"*. The explanation is in the disclosure; rule 33
      // keeps it out of the header.
      headerNote: t("payments.refundsAndCredits.lifecycles.summary"),
      cell: (row) => (
        <RefundStateCell row={row} t={t} lifecycles={lifecycles} tone={statusTone} />
      ),
    },
  ];
  if (currentUserId !== undefined) {
    columns.push({
      key: "raised_by",
      label: t("payments.refundsAndCredits.col.raisedBy"),
      cell: (row) =>
        row.kind === KIND_REFUND && row.source.requested_by === currentUserId ? (
          <span className="text-neutral-800">{t("payments.refunds.yourRequest")}</span>
        ) : null,
    });
  }
  if (rowActions !== undefined) {
    columns.push({
      key: "actions",
      label: t("payments.refundsAndCredits.col.actions"),
      locked: true,
      cell: (row) => (row.kind === KIND_REFUND ? <>{rowActions(row)}</> : null),
    });
  }
  return {
    screenId: "S58",
    columns,
    getRowId: (row) => `${row.kind}:${row.id}`,
    // ⚠ **NO `searchFields`, SO NO SEARCH BOX — AND THAT IS A DECLARED ABSENCE,
    // NOT AN OVERSIGHT.** p073 draws *"Search account, customer or reference…"*.
    // `GET /refunds-and-credits` accepts `page`, `per` and `f.kind` and **no `q`
    // at all**: `refunds_and_credits.page(offset, limit, kind)` is its whole
    // signature. `BR-SHL-010` makes this config what a screen DECLARES its table
    // can do and `DataTable` renders exactly that, so declaring a search here
    // would put a live box on screen that narrows nothing — worse than its
    // absence, because a clerk would type into it and believe the result.
    //
    // A client-side filter over the fetched page was refused for `NFR-3`'s
    // reason: it tells the truth on page one and lies on page two. The absence
    // rides with the two missing columns in `DEF-PAY-6279`, because it has the
    // same cause — the read does not carry what the drawing searches BY.
    filters: [
      {
        name: "kind",
        label: t("payments.refundsAndCredits.filter.kind"),
        // ⚠ DERIVED FROM THE RESPONSE. See `kindFilterOptions` for why a
        // hand-typed list here is the service-list trap one module over.
        options: kindFilterOptions(kinds, t),
      },
    ],
    // The read orders `-created_at, -id` and accepts no `sort`, so the default
    // is a statement of what the server does rather than a request.
    defaultSort: { sort: "occurred_at", dir: "desc" },
  };
}

export function RefundsAndCreditsList(props: RefundsAndCreditsListProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);

  const config = useMemo(
    () =>
      refundsAndCreditsConfig(
        translate,
        props.kinds,
        props.statusTone,
        props.lifecycles,
        props.rowActions,
        props.currentUserId,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      props.currentUserId,
      props.kinds,
      props.lifecycles,
      props.rowActions,
      props.statusTone,
      t,
    ],
  );

  return (
    <>
      <DataTable<RefundsAndCreditsRow>
        config={config}
        state={props.state}
        onStateChange={props.onStateChange}
        rows={props.rows}
        totalRows={props.totalRows}
        loading={props.loading}
        error={props.error ?? null}
        filterBarSlot={
          <FilterBar
            filters={config.filters ?? []}
            state={props.state}
            onStateChange={props.onStateChange}
          />
        }
        // No `downloadSlot`: `POST /exports` registers no refunds resource, and
        // BR-SHL-010 keeps an undeclared capability unrendered.
        empty={{
          title: t("payments.refundsAndCredits.emptyTitle"),
          helper: t("payments.refundsAndCredits.empty"),
          ctaLabel: props.emptyCtaLabel,
          ctaReason: props.emptyCtaReason,
          ctaVariant: "secondary",
          onCta: props.onEmptyCta,
        }}
      />

      {/* B14 rule 32 — a stated absence is a disclosure CLOSED by default, and
          the two below are the only prose this screen carries. The first
          explains a column that is HERE and reads oddly; the second names two
          that are NOT. Neither is rationale about how we built it (rule 33). */}
      <Disclosure variant="section" title={t("payments.refundsAndCredits.lifecycles.summary")}>
        <p>{t("payments.refundsAndCredits.lifecycles.refund")}</p>
        <p>{t("payments.refundsAndCredits.lifecycles.creditNote")}</p>
      </Disclosure>
      <Disclosure variant="section" title={t("payments.refundsAndCredits.columnsAbsent.summary")}>
        <p>{t("payments.refundsAndCredits.columnsAbsent.body")}</p>
      </Disclosure>
    </>
  );
}

export default RefundsAndCreditsList;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-138-BRC07 P4.26 (payments blueprint phase 4, wave 2) — built from
//         p072–p074 read AS IMAGES at scale 2.0 (B14 rule 42).
// generated: 2026-09-23 by LANE P4-SCREENS-B
// exceptions: (1) **The four KPI tiles the drawing puts above this table are
//         NOT built** — *Waiting 4 · Refunded $6,104.22 · Credited $2,840.00 ·
//         Average wait 2.1 days*. Nothing serves any of them: the union read
//         carries `rows`, `count` and `problems`, and there is no aggregate
//         endpoint for a month's refunded total or a request-to-issue average.
//         They could only be computed from the rows on the CURRENT PAGE, which
//         is a tenant-wide figure derived from fifty rows — the defect
//         `NFR-3` exists to prevent, and a number a clerk would read aloud.
//         Reported rather than approximated. (2) **No status filter** — see the
//         header; the read accepts `f.kind` alone. (3) **No sortable headers
//         yet**: the read takes no `sort`, and a header that reordered one page
//         would be `DEF-PAY-4221`'s own defect (*"it sorts in Python, not
//         SQL"*) moved into the browser. (4) **No search box** — the drawing
//         draws one and the read accepts no `q`; see the note on the config.
//         All four absences have ONE cause: `GET /refunds-and-credits` answers
//         `page`, `per` and `f.kind`, and nothing this screen draws may pretend
//         otherwise.
// ──────────────────────────────────────────────────────────
