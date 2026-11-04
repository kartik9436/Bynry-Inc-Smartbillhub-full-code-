// ── Trace ──────────────────────────────────────────────
// Task:     Finance blueprint `P1.2` (the deposits list onto the shared
//           `DataTable`, status and method chips) · `P1.4` (the chips come from
//           the server) · `P1.7` (the search reaches the server) · `P1.9`'s
//           shape (the filter state lives in the URL, so a filtered list can be
//           sent as a link)
// Defect:   `DEF-PAY-6554` (the list served every batch and cited the retired
//           3,000-connection ceiling) · `DEF-PAY-6556` (the chips were a
//           hand-typed array and `f.method` had no control at all)
// Drawing:  05-prototype/07 Finance Blueprint.pdf — **p048** is screen 3·1's
//           wireframe (FIN-03) with its six numbered notes and the binding
//           filter-criteria table; **p049** carries "Components to use" and the
//           FOR / DOORS / FIELDS / TABLE CONTROLS / RULES rows. Built from the
//           RENDERED IMAGES (B14 rule 42) at scale 2.2, never from the text
//           layer — which for this document is scrambled.
// Rules:    B14 rule 2 (one page header — the page owns it, not this panel) ·
//           rule 12 (search + filter chips) · rule 13 (sortable headers) ·
//           rule 14 (the shared ColumnChooser) · rule 16 (a pagination footer) ·
//           rule 20 (ONE table type) · rule 21 (Tailwind utilities, no new
//           stylesheet class — this file is on
//           `07-frontend/src/styles/route-b-migrated.txt`) · rule 31 (no
//           database id is ever a visible value) · rule 33 (the text caps) ·
//           rule 43 (a piece of UI is a COMPONENT — this file exists because of
//           that rule) · rule 44 (our tokens and spacing decide HOW) ·
//           BR-PAY-004 (a reconciled batch LOCKS) · BR-SHL-011 · BR-SHL-023
// ───────────────────────────────────────────────────────
//
// 3·1 DEPOSITS — the list, its toolbar, its chooser and its footer.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS REPLACES, AND WHY IT IS A FILE AND NOT A FUNCTION IN THE PAGE
// ══════════════════════════════════════════════════════════════════════════
// Until now the batches were a `PlainTable` inside `DepositsPage.tsx` with a
// row of segmented buttons above it — no search, no `+ Filter`, no column
// chooser and no pager, on a list that grows with every day a utility banks.
// p049's own TABLE CONTROLS row says exactly that: *"Search none · status wired
// but local · method unwired · chooser none · sort SQL `-deposited_on` (passes
// R14) · pagination none"*, and its RULES row records *"Breaks ✗ UI-RULES
// 12·13·14·15·16 · ✗ NFR-3"*.
//
// **B14 rule 43** — ratified after *"use it"* turned out to mean 120 lines
// inline in a 4,186-line page — is why this is a component: a table that is a
// function body inside the page is importable by nothing and testable only
// through the whole screen.
//
// ══════════════════════════════════════════════════════════════════════════
// FOUR THINGS THIS FILE DELIBERATELY DOES NOT DO
// ══════════════════════════════════════════════════════════════════════════
//   · **`⇅` ON DATE, AND ON NOTHING THE SERVER CANNOT ORDER.** p048 draws the
//     glyph on DATE alone. `bankrec_read.BATCH_SORTS` accepts three names and
//     this config offers the ones the drawing draws; declaring a column
//     sortable that the server ignores would put a control on screen that
//     changes nothing (`BR-SHL-010`).
//   · **ROW ACTIONS ARE STILL A LINK, NOT ICONS.** p048 note 4 marks that
//     CHANGED and hands it to `P1.17`, which rebuilds `RowActions` with a real
//     overflow *"once, not four times"*. Rewriting a shipped control set inside
//     a task whose subject is the pager is the silent fix CLAUDE.md forbids, so
//     the behaviour below is byte-for-byte what shipped and the breach stays in
//     the register.
//   · **THE `Difference` AND `Bank shows` SENTENCES ARE UNCHANGED.** They read
//     *"Pending — the bank has not shown this yet"*, which is eight words
//     against B14 rule 33's six-word cap for a FACT. It is the one thing this
//     screen must not get wrong (p049: *"In transit reads pending, never
//     $0.00"*), so the sentence is carried over exactly and the length is
//     filed rather than shortened by a lane whose subject is paging.
//   · **IT HOLDS NO VOCABULARY.** The status and method chips are the server's
//     (`P1.4`). A screen that typed them out is `DEF-PAY-6556`, and the shape
//     `SignupWizard.tsx`'s tick-list taught this repo: the row exists, the API
//     serves it, `tsc` and every test pass, and no chip appears.
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { DataTable } from "@/components/DataTable";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { FilterBar } from "@/components/FilterBar";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import type {
  DepositBatchRow,
  DepositBatchesResponse,
  ServedChip,
} from "@/api/bankRecEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

import {
  BankFigure,
  bankAbsenceReason,
  batchStatusLabel,
  batchStatusTone,
  depositOwnerLabel,
  isZeroAmount,
} from "./depositsShared";

/** The screen id the shared `ColumnChooser` keys its per-user preference on. */
export const DEPOSITS_SCREEN_ID = "S37.deposits";

/**
 * A served chip → a `TableFilterConfig` option.
 *
 * ⚠ **TWO SHAPES, ONE READER, AND THE FALLBACK IS THE VALUE ITSELF.** A status
 * arrives as `label_key` because the vocabulary is this product's and the words
 * are the catalogue's; a tender arrives as `label` because the words are the
 * tenant's own. A chip carrying neither renders as its VALUE rather than as a
 * blank chip — `BR-REP-008`'s *nothing invisible*, and the difference between a
 * clerk seeing an unfamiliar word and seeing an empty control.
 */
export function chipOptions(chips: readonly ServedChip[], t: Translator) {
  return chips.map((chip) => ({
    value: chip.value,
    label:
      chip.label ??
      (chip.label_key === undefined
        ? chip.value
        : t(chip.label_key, { defaultValue: chip.value })),
  }));
}

/**
 * The capability-matrix row as a `TableConfig` — p049's FIELDS line in its drawn
 * order: *Batch · Date · Method · Payments · Our total · Bank shows ·
 * Difference · Status*, then the row's one act.
 *
 * `statuses` / `methods` are NULLABLE for the reason `journalConfig`'s response
 * is: parsing `?sort=` and `?f.status=` out of the URL needs the COLUMNS and the
 * FILTER NAMES, and it happens before any row has arrived. A second
 * columns-only config would be two lists free to drift.
 */
export function depositsConfig(
  t: Translator,
  locale: string | undefined,
  chips: { statuses: readonly ServedChip[]; methods: readonly ServedChip[] },
  batchPath?: (batchId: string) => string,
): TableConfig<DepositBatchRow> {
  return {
    screenId: DEPOSITS_SCREEN_ID,
    // B14 rule 31 — `id` keys React and the preference store and reaches no
    // cell. The identity column is the BATCH CODE, which is the string a clerk
    // reads off a deposit slip.
    getRowId: (row) => row.id,
    // `P1.7` — declared so the box renders; the SERVER does the matching over
    // batch code, bank reference and payment confirmation.
    searchFields: ["code"],
    // B14 rule 19 — this list's own prompt, naming what the box matches.
    // p048 draws it verbatim: *"Search batch, bank reference, cheque…"*.
    searchPlaceholder: "payments.deposits.searchPrompt",
    defaultSort: { sort: "deposited_on", dir: "desc" },
    filters: [
      {
        name: "status",
        label: t("payments.col.status"),
        options: chipOptions(chips.statuses, t),
      },
      {
        name: "method",
        label: t("payments.col.method"),
        options: chipOptions(chips.methods, t),
      },
    ],
    columns: [
      {
        key: "code",
        label: t("payments.deposits.col.batch"),
        sortable: true,
        identity: true,
        cell: (row: DepositBatchRow) =>
          batchPath === undefined ? (
            row.code
          ) : (
            // The CODE is a label; the banking DATE is its own column, because
            // the PO's ruling of 2026-08-12 says a code is a label and never a
            // data store. Nothing here parses a date out of the string.
            <InlineLinkTo to={batchPath(row.id)}>{row.code}</InlineLinkTo>
          ),
      },
      {
        key: "deposited_on",
        label: t("payments.deposits.col.date"),
        sortable: true,
        cell: (row: DepositBatchRow) => row.deposited_on ?? t("payments.deposits.noDate"),
      },
      {
        key: "method",
        label: t("payments.col.method"),
        cell: (row: DepositBatchRow) =>
          row.all_tenders === true
            ? depositOwnerLabel(row.channel ?? null, t)
            : (row.method_name ?? row.method_code ?? t("payments.deposits.noMethod")),
      },
      {
        key: "payment_count",
        label: t("payments.deposits.col.payments"),
        numeric: true,
        cell: (row: DepositBatchRow) => row.payment_count ?? "—",
      },
      {
        key: "recorded_total",
        label: t("payments.deposits.col.ourTotal"),
        numeric: true,
        sortable: true,
        cell: (row: DepositBatchRow) => (
          <BankFigure
            amount={row.recorded_total}
            currency={row.currency}
            reason={t("payments.deposits.noRecordedTotal")}
            locale={locale}
          />
        ),
      },
      // ⚠ THE TWO CELLS THIS SCREEN EXISTS TO GET RIGHT. A batch the bank has
      // not shown carries NO bank figure and NO difference, and both say so in
      // words. Rendering either as 0.00 would draw a deposit that reconciles
      // perfectly over money nobody has confirmed (DEF-127's shape).
      {
        key: "bank_total",
        label: t("payments.deposits.col.bankShows"),
        numeric: true,
        cell: (row: DepositBatchRow) => (
          <BankFigure
            amount={row.bank_total}
            currency={row.currency}
            reason={bankAbsenceReason(row.status, t)}
            locale={locale}
          />
        ),
      },
      {
        key: "difference",
        label: t("payments.deposits.col.difference"),
        numeric: true,
        cell: (row: DepositBatchRow) => (
          <BankFigure
            amount={row.difference}
            currency={row.currency}
            reason={bankAbsenceReason(row.status, t)}
            locale={locale}
          />
        ),
      },
      {
        key: "status",
        label: t("payments.col.status"),
        cell: (row: DepositBatchRow) => (
          <StatusPill tone={batchStatusTone(row.status)}>
            {batchStatusLabel(row.status, t, {
              difference: row.difference,
              currency: row.currency,
              locale,
            })}
          </StatusPill>
        ),
      },
      {
        key: "actions",
        label: t("payments.deposits.col.action"),
        locked: true,
        cell: (row: DepositBatchRow) =>
          batchPath === undefined ? null : (
            // ONE act per row, and BR-PAY-004 decides which. A reconciled batch
            // is LOCKED: it gets "View", never "Resolve", because the service
            // refuses a second reconcile and a control that fails on click is
            // worse than no control (BR-SHL-025).
            <InlineLinkTo to={batchPath(row.id)}>
              {/* `LBX-01` (`DEF-PAY-10700`) — a MATCHED batch whose
                  difference is exactly $0.00 has nothing to resolve; the act
                  waiting on it is the reconcile itself. An unknown difference
                  (`null`) is not zero and keeps "Resolve". */}
              {row.locked
                ? t("payments.deposits.view")
                : row.status === "matched" && isZeroAmount(row.difference)
                  ? t("payments.deposits.reconcile")
                  : row.status === "unmatched" || row.status === "matched"
                    ? t("payments.deposits.resolve")
                    : t("payments.deposits.view")}
            </InlineLinkTo>
          ),
      },
    ],
  };
}

export interface DepositsListProps {
  response: DepositBatchesResponse | null;
  loading: boolean;
  error?: { reason?: string; onRetry: () => void } | null;
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  locale?: string;
  batchPath: (batchId: string) => string;
}

/**
 * The whole of 3·1's list — toolbar, table and footer.
 *
 * ⚠ **THE ROWS ARE THE SERVER'S PAGE AND NOTHING HERE SLICES, SORTS OR FILTERS
 * THEM.** `totalRows` is the server's `count` over the FILTERED SET, from a
 * `COUNT(*)`. A screen that re-sorted the page it was handed would silently
 * disagree with the pager beside it.
 *
 * ⚠ **AND IT DRAWS NO PANEL AND NO HEADING.** p048 puts the table straight
 * under the tiles with no box around it, and the page head is the page's
 * (B14 rule 2).
 */
export function DepositsList(props: DepositsListProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const config = useMemo(
    () =>
      depositsConfig(
        translate,
        props.locale,
        {
          statuses: props.response?.statuses ?? [],
          methods: props.response?.methods ?? [],
        },
        props.batchPath,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [props.response, props.locale, props.batchPath, t],
  );

  return (
    <DataTable<DepositBatchRow>
      config={config}
      state={props.state}
      onStateChange={props.onStateChange}
      rows={props.response?.results ?? []}
      totalRows={props.response?.count ?? null}
      loading={props.loading}
      error={props.error}
      filterBarSlot={
        <FilterBar
          filters={config.filters ?? []}
          state={props.state}
          onStateChange={props.onStateChange}
        />
      }
      empty={{
        title: t("payments.deposits.emptyTitle"),
        helper: t("payments.deposits.empty"),
        ctaLabel: t("payments.deposits.clearSearch"),
        ctaVariant: "secondary",
        onCta: () => props.onStateChange({ ...props.state, q: "", filters: {}, page: 1 }),
      }}
    />
  );
}
