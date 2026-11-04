// ── Trace ──────────────────────────────────────────────
// Change:   CR-140-BRC09 · Finance blueprint `P4.12` — 6·2 **Export**, its own
//           view on Close & export. p069 draws it; p070 items 1–9 and p071's
//           component table are its specification.
// Task:     `P4.12` the view · it CONSUMES `P4.1` (the four groupings are
//           export resources), `P4.13` (`POST /exports` takes ordered
//           `columns`) and `P4.2` (a sent batch has a file)
// Rules:    B14 rule 12 (the table toolbar, in the product's order) · rule 13
//           (sorting) · rule 15 (a row action is an ICON) · rule 16 (the
//           pagination footer) · rule 21 (Tailwind utilities, NO class added
//           to any stylesheet — this file is on
//           `src/styles/route-b-migrated.txt`) · rule 31 (no database id is
//           ever the visible value of a field) · rule 32/33 (one sentence per
//           section; rationale is ZERO words on screen) · rule 43 (a piece of
//           UI is a COMPONENT) · rule 44 (the drawing says WHAT is on the
//           screen; the token scale and the component kit say HOW and win) ·
//           BR-LED-004 (the dimension extracts; a hand-over is idempotent and
//           every figure drills back) · BR-LED-017 (an export requires every
//           month in its range CLOSED) · BR-LED-007 (drift refuses the
//           hand-over) · IS-9 (a download carries the current filters and the
//           VISIBLE COLUMNS) · IS-11 (CSV always; no XLSX) · BR-SHL-025 (a
//           control this deployment cannot honour renders disabled WITH its
//           reason)
// Tests:    src/features/ledger/exportView.dom.test.tsx ·
//           src/features/ledger/exportViewColumns.test.ts
// Impacts:  features/ledger/CloseExportPage.tsx (mounts the view strip and
//           this view) · 10-scripts/gates/g113_export_columns_agree.py
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// ONE FILTER, ONE TABLE, TWO WAYS OUT — RULED, PO 2026-09-24
// ══════════════════════════════════════════════════════════════════════════
// p069's own banner, verbatim: *"this filter should be expanded — I need it by
// period start date and end date; based on the filter, show the table below it
// … then allow to send or download it in different file formats. We need a
// column selector — all selected columns go in the downloaded file."* On the
// three extract buttons: *"why do we need this — can't you merge it with the
// filter itself"*. On the history: *"this is good"*.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ DOWNLOAD AND SEND ARE NOT TWO BUTTONS FOR ONE ACT
// ══════════════════════════════════════════════════════════════════════════
// p069 states the split and the reason: **↓ is the table as shown** — the
// ticked columns, any two dates, and **nothing is recorded**. **↗ Send hands
// the range over ONCE**, in the accounting format, and a batch row is written.
// *"A QuickBooks file taken without a record could be imported twice"* — the
// double booking `BR-LED-004` exists to stop — so the four accounting formats
// leave only through Send, and come back from the hand-over history.
//
// **That is why the ticked columns shape the DOWNLOAD and never the hand-over.**
// An importer needs the layout it needs; a clerk who hid two columns has not
// changed what QuickBooks is owed.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE COLUMN KEYS ARE THE SERVER'S OWN COLUMN NAMES, AND THAT IS LOAD-BEARING
// ══════════════════════════════════════════════════════════════════════════
// `POST /exports` takes `columns` as the resource's declared column NAMES, and
// `apps/tenancy/exports.columns_for()` **drops a name the resource does not
// have** and falls back to the default set when it knows none of them. Both are
// right — `BR-SHL-011`'s *"fall back, never 4xx"* — and both are SILENT. So a
// key renamed on either side of the wire produces a file with the wrong columns
// in it, with `tsc`, every test and every gate green.
//
// `GROUPINGS[k].columns[n].key` below IS the name in
// `apps/ledger/finance_exports.py`, never a display key, and
// `10-scripts/gates/g113_export_columns_agree.py` reads both files and fails
// when they disagree. The LABELS are catalogue keys and are free to move; the
// KEYS are a contract with Python.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ NO PDF, AND IT IS THE DRAWING THIS DIVERGES FROM RATHER THAN THE RULE
// ══════════════════════════════════════════════════════════════════════════
// p070 row 6 draws *Download CSV* **or** *Download PDF*. **This deployment has
// no PDF renderer of any kind** — `apps/ledger/finance_exports.py`'s own
// exception (1) records it, and `apps/reports/exports.py` records the same
// absence. IS-11 reads *"CSV always, PDF where layout matters"*, and one of
// those two is true here. A second menu item that produced nothing would be a
// broken promise wearing a download glyph (`DEF-007`'s shape), so `pdf` is not
// passed and the control renders as the plain CSV button. **Reported, never
// silently followed** — §16 of the UI skill, and rule 44's own clause.
import { useMemo, useState } from "react";

import { useMutation, useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import {
  EXPORT_TARGETS,
  getExportExtract,
  getExportPreview,
  requestListExport,
} from "@/api/endpoints";
import type {
  ExportExtractAuthorityRow,
  ExportExtractKind,
  ExportExtractPremisesRow,
  ExportExtractServiceRow,
  ExportPreviewResponse,
  ExportResource,
  ExportSummaryRow,
  ExportTarget,
} from "@/api/endpoints";
import { AbsentFigure } from "@/components/AbsentFigure";
import { Button } from "@/components/Button";
import { Chip } from "@/components/Chip";
import { clientPage } from "@/components/clientTable";
import type { ClientTableSpec } from "@/components/clientTable";
import { DataTable } from "@/components/DataTable";
import { DownloadButton } from "@/components/DownloadButton";
import { FilterRow } from "@/components/FilterRow";
import { DatePickerField, SelectField } from "@/components/FormModal";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { InlineLink } from "@/components/Surfaces";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { ExportNotice, exportOutcome } from "@/features/exports/ListExportButton";
import type { ExportOutcome } from "@/features/exports/ListExportButton";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { Translator } from "@/features/tenancy/settingsShared";

import { ExportCostSection } from "./financeShared";

/* ══════════════════════════════════════════════════════════════════════════
   THE FOUR GROUPINGS — p070 row 3
   ══════════════════════════════════════════════════════════════════════════
   *"Group by Account · Service · Premises · Tax authority — replaces the three
   extract buttons. Only Account is handed over; the other three are the
   extracts."* The order is the drawing's. */
export const EXPORT_GROUPINGS = ["account", "service", "premises", "authority"] as const;
export type ExportGrouping = (typeof EXPORT_GROUPINGS)[number];

/** The ACCOUNT grouping is the one the send gate reads, so it is the landing
 *  grouping and an unrecognised value falls back to it rather than 404ing
 *  (BR-SHL-011). */
export function exportGroupingFrom(raw: string | null | undefined): ExportGrouping {
  return (EXPORT_GROUPINGS as readonly string[]).includes(raw ?? "")
    ? (raw as ExportGrouping)
    : "account";
}

/** One column of one grouping's table AND of its file.
 *
 *  `key` is the export resource's own column name — see the header. `field` is
 *  where the value sits on the row the READ answers with, which is a different
 *  name on most of them (`Column("gl_account", "code")`). */
interface GroupingColumn {
  key: string;
  field: string;
  labelKey: string;
  money?: boolean;
  /** Off until a clerk ticks it. Absent = shown. */
  offByDefault?: boolean;
}

interface GroupingSpec {
  /** Which `POST /exports` resource writes this grouping's file (`P4.1`). */
  resource: ExportResource;
  /** `null` for Account, which reads `/finance/export/preview` instead. */
  extract: ExportExtractKind | null;
  labelKey: string;
  columns: readonly GroupingColumn[];
}

/**
 * ⚠ **EVERY `key` BELOW IS A `Column(...)` NAME IN
 * `06-backend/apps/ledger/finance_exports.py`.** `g113_export_columns_agree.py`
 * reads both files and fails on a disagreement — see the header for what a
 * silent disagreement costs.
 */
export const GROUPINGS: Record<ExportGrouping, GroupingSpec> = {
  account: {
    resource: "export_preview",
    extract: null,
    labelKey: "finance.export.groupBy.account",
    columns: [
      { key: "gl_account", field: "code", labelKey: "finance.export.col.account" },
      { key: "name", field: "name", labelKey: "finance.export.col.what" },
      { key: "target_ref", field: "target_ref", labelKey: "finance.export.col.ref" },
      { key: "debit", field: "debit", labelKey: "finance.export.col.debit", money: true },
      { key: "credit", field: "credit", labelKey: "finance.export.col.credit", money: true },
      // p070's ▦ panel is drawn OPEN with two unticked rows under the five.
      // These are that pair: a weekly hand-over splits one account across
      // several windows (`EXPORT_GRANULARITIES`), and the window is the only
      // thing telling those rows apart.
      {
        key: "window_start",
        field: "window_start",
        labelKey: "finance.export.col.windowStart",
        offByDefault: true,
      },
      {
        key: "window_end",
        field: "window_end",
        labelKey: "finance.export.col.windowEnd",
        offByDefault: true,
      },
    ],
  },
  service: {
    resource: "revenue_by_service",
    extract: "service",
    labelKey: "finance.export.groupBy.service",
    columns: [
      { key: "service", field: "service_code", labelKey: "finance.export.col.service" },
      { key: "usage_revenue", field: "usage", labelKey: "finance.export.col.usage", money: true },
      {
        key: "base_and_fees",
        field: "base_and_fees",
        labelKey: "finance.export.col.baseAndFees",
        money: true,
      },
      {
        key: "total_billed",
        field: "total_billed",
        labelKey: "finance.export.col.totalBilled",
        money: true,
      },
    ],
  },
  premises: {
    resource: "by_premises",
    extract: "premises",
    labelKey: "finance.export.groupBy.premises",
    columns: [
      { key: "premises", field: "premises_name", labelKey: "finance.export.col.premises" },
      { key: "billed", field: "billed", labelKey: "finance.export.col.billed", money: true },
      { key: "collected", field: "collected", labelKey: "finance.export.col.collected", money: true },
      { key: "owed", field: "owed", labelKey: "finance.export.col.owed", money: true },
    ],
  },
  authority: {
    resource: "remittance",
    extract: "authority",
    labelKey: "finance.export.groupBy.authority",
    columns: [
      { key: "authority_code", field: "code", labelKey: "finance.export.col.authorityCode" },
      { key: "authority", field: "name", labelKey: "finance.export.col.authority" },
      {
        key: "remitting_basis",
        field: "remitting_basis",
        labelKey: "finance.export.col.basis",
      },
      { key: "billed", field: "billed", labelKey: "finance.export.col.billed", money: true },
      { key: "collected", field: "collected", labelKey: "finance.export.col.collected", money: true },
      { key: "remitted", field: "remitted", labelKey: "finance.export.col.remitted", money: true },
      {
        key: "outstanding_billed",
        field: "outstanding_billed",
        labelKey: "finance.export.col.owedBilled",
        money: true,
      },
      {
        key: "outstanding_collected",
        field: "outstanding_collected",
        labelKey: "finance.export.col.owedCollected",
        money: true,
      },
    ],
  },
};

/** `BR-LED-017`'s two detail levels. Account only — an extract has no window
 *  to split. Served as `EXPORT_GRANULARITIES` and mirrored here as the TYPE and
 *  as what the picker offers before a response arrives, exactly as
 *  `EXPORT_TARGETS` is. */
export const EXPORT_GRANULARITIES = ["summary", "weekly"] as const;
export type ExportGranularity = (typeof EXPORT_GRANULARITIES)[number];

/** The row every grouping's table is rendered from: whatever the read answered
 *  with, read by FIELD name. Deliberately not a union — the four reads answer
 *  four shapes and this view's job is to lay any of them out, which is one
 *  behaviour rather than four. */
type AnyRow =
  | ExportSummaryRow
  | ExportExtractServiceRow
  | ExportExtractPremisesRow
  | ExportExtractAuthorityRow;

/** ⚠ **`null` IS NOT `"0.00"` AND MUST NOT BECOME IT.** `collected` and
 *  `outstanding_collected` are served `null` where payments publishes no
 *  allocation for the window, and `apps/ledger/reporting` is blunt about the
 *  cost: a zero there reads as *"nothing was collected"* about money that was.
 *  The cell renders the absence; the file writes an empty cell. */
export function cellValue(row: AnyRow, field: string): string | null {
  const value = (row as unknown as Record<string, unknown>)[field];
  if (value === null || value === undefined || value === "") {
    return null;
  }
  return String(value);
}

/** The visible keys of a grouping, in the order the chooser would start in. */
export function defaultVisibleColumns(grouping: ExportGrouping): string[] {
  return GROUPINGS[grouping].columns
    .filter((column) => column.offByDefault !== true)
    .map((column) => column.key);
}

/**
 * What the file is asked for — `POST /exports`'s body, from what is on screen.
 *
 * ⚠ **`columns` IS `visible`, NOT THE CONFIG'S ORDER.** IS-9's second half and
 * `P4.13`'s ruling — PO, verbatim: *"all selected columns will go in downloaded
 * file"* — are about the ORDER the clerk left them in, which is what
 * `DataTable` reports back through `onVisibleColumnsChange`. Re-deriving it
 * from `GROUPINGS` would send the drawn order over a reordered table and the
 * file would not match the screen it came from.
 */
export function downloadBody(params: {
  grouping: ExportGrouping;
  from: string;
  to: string;
  target: ExportTarget;
  granularity: ExportGranularity;
  visible: readonly string[];
  q: string;
}): {
  resource: ExportResource;
  filters: Record<string, string>;
  q: string;
  columns: readonly string[];
} {
  const spec = GROUPINGS[params.grouping];
  const filters: Record<string, string> = { from: params.from, to: params.to };
  if (params.grouping === "account") {
    // Only `export_preview` declares these two (`filters=("from","to","target",
    // "granularity")`). An undeclared filter is IGNORED by the kernel, so
    // sending them everywhere would be harmless and dishonest — the request
    // would claim a shape the resource does not have.
    filters.target = params.target;
    filters.granularity = params.granularity;
  }
  return {
    resource: spec.resource,
    filters,
    q: params.q,
    columns: params.visible,
  };
}

/* ══════════════════════════════════════════════════════════════════════════
   THE PREVIEW TABLE
   ══════════════════════════════════════════════════════════════════════════ */

function previewSpec(grouping: ExportGrouping): ClientTableSpec<AnyRow> {
  const columns = GROUPINGS[grouping].columns;
  const text = columns.filter((column) => column.money !== true);
  const byKey = new Map(columns.map((column) => [column.key, column]));
  return {
    // p069 draws *"Search account…"*. It matches the grouping's TEXT columns —
    // the ones a person reads a name out of — and never the money, because a
    // search box that matched `1,250.00` would narrow on a figure nobody typed.
    search: (row) =>
      text.map((column) => cellValue(row, column.field) ?? "").filter((one) => one !== ""),
    filter: () => true,
    sortValue: (row, key) => {
      const column = byKey.get(key);
      if (column === undefined) {
        return null;
      }
      const raw = cellValue(row, column.field);
      if (raw === null) {
        return null;
      }
      // A money column sorts as a NUMBER; everything else sorts as written.
      // `"9.00"` before `"10.00"` is the lexicographic answer and it is wrong
      // on every money column in this product.
      return column.money === true ? Number(raw) : raw;
    },
  };
}

/** Why THIS column is empty, as a catalogue key.
 *
 *  `target_ref` — the account has no code in the accounting package, which is
 *  what blocks the whole hand-over (BR-LED-014). The two collected columns —
 *  payments publishes no allocation for the window, and `apps/ledger/reporting`
 *  is blunt about the cost of writing `0.00` there instead. Everything else
 *  simply has no value on this row. */
export function absentReasonKey(columnKey: string): string {
  if (columnKey === "target_ref") {
    return "finance.export.refMissing";
  }
  if (columnKey === "collected" || columnKey === "outstanding_collected") {
    return "finance.export.collectedAbsent";
  }
  return "finance.export.valueAbsent";
}

export function previewConfig(params: {
  grouping: ExportGrouping;
  t: Translator;
  currency: string | null;
  locale?: string;
  /** BR-LED-004 — *"every figure drills back"*. The ACCOUNT grouping's code is
   *  a link into the lines behind it, which is US-LED-016 TC-3's auditor asking
   *  *"what is the 506.31?"*. The three extracts have no batch to drill into,
   *  so they render their first column as text rather than as a link that
   *  cannot open. */
  onDrill?: (code: string) => void;
}): TableConfig<AnyRow> {
  const spec = GROUPINGS[params.grouping];
  return {
    // Each grouping keeps its OWN saved column set: five account columns and
    // eight authority columns are not one preference wearing two names.
    screenId: `FIN-06.2.${params.grouping}`,
    searchPlaceholder: `finance.export.searchPreview.${params.grouping}`,
    defaultSort: { sort: spec.columns[0].key, dir: "asc" },
    getRowId: (row) =>
      spec.columns.map((column) => cellValue(row, column.field) ?? "").join("|"),
    searchFields: spec.columns
      .filter((column) => column.money !== true)
      .map((column) => column.key),
    columns: spec.columns.map((column, index) => ({
      key: column.key,
      label: params.t(column.labelKey),
      sortable: true,
      // BR-SHL-013 — the identity column can never be hidden. It is the FIRST
      // column of each grouping: a preview with no account code, no service and
      // no premises name is a table of figures about nothing.
      identity: index === 0,
      numeric: column.money === true,
      cell: (row: AnyRow) => {
        const raw = cellValue(row, column.field);
        if (raw === null) {
          // ⚠ **THREE DIFFERENT ABSENCES, THREE DIFFERENT SENTENCES.** B14
          // rule 32 makes a stated absence a disclosure with its REASON, and a
          // single sentence over all three would be a reason that is true of
          // one of them. The keys are written out rather than composed from
          // `column.key`: a key built at runtime is a key `G15` cannot see.
          return (
            <AbsentFigure
              label={params.t("finance.absent")}
              reason={params.t(absentReasonKey(column.key))}
            />
          );
        }
        if (column.money === true) {
          return (
            <MoneyCell amount={raw} currency={params.currency ?? ""} locale={params.locale} />
          );
        }
        const drill = params.onDrill;
        if (column.key === "gl_account" && drill !== undefined) {
          return (
            <InlineLink type="button" onClick={() => drill(raw)}>
              {raw}
            </InlineLink>
          );
        }
        return raw;
      },
    })),
  };
}

/* ══════════════════════════════════════════════════════════════════════════
   THE FOUR CHECKS — p069, drawn above ↗ Send
   ══════════════════════════════════════════════════════════════════════════ */

export interface SendCheck {
  id: string;
  passed: boolean;
}

/**
 * ⚠ **THESE ARE THE SERVER'S FOUR GATES RENDERED, AND `sendable` IS STILL THE
 * SERVER'S ANSWER.** `CloseExportPage`'s own header has said so since the
 * screen was built: a client-side fifth opinion drifts the first time a gate
 * changes and would enable a button the server then refuses. These four exist
 * so a ✗ can say WHICH one — they never decide.
 */
export function sendChecks(preview: ExportPreviewResponse): SendCheck[] {
  return [
    { id: "closed", passed: preview.period_closed },
    { id: "notSent", passed: preview.already_exported === null },
    { id: "balances", passed: preview.balanced },
    { id: "codes", passed: preview.missing_refs.length === 0 },
  ];
}

/* ══════════════════════════════════════════════════════════════════════════
   THE VIEW
   ══════════════════════════════════════════════════════════════════════════ */

export interface ExportViewProps {
  client: ApiClient;
  t: Translator;
  dateFormat: RegionalDateFormat;
  locale?: string;
  /** The open period, as the params band's opening dates. `null` until
   *  `GET /shell/display` answers. */
  period: { start: string; end: string } | null;
  target: ExportTarget;
  onTargetChange: (next: ExportTarget) => void;
  /** The targets `GET /finance/export/batches` served, or undefined before the
   *  first response (`P1.6` — the list is the SERVER's, never typed out here). */
  servedTargets?: string[];
  /** Opens 6·2a. The confirm dialog, the mutation and the toast stay on the
   *  page that owns the send, exactly as the close dialog does. The PREVIEW
   *  rides along, because the dialog's consequence names that window's figures
   *  and a second read of one window is how two panels come to disagree. */
  onSend: (handover: {
    from: string;
    to: string;
    granularity: ExportGranularity;
    preview: ExportPreviewResponse;
  }) => void;
  /** BR-LED-004 — a figure opens to its lines. Owned by the page, which holds
   *  the batch the drill-back reads. */
  onDrill: (code: string) => void;
  /** `CR-069` wave J — the adapter's own `describe()` sentence for the saved
   *  accounting connection, or `null`. Never composed here. */
  savedDestination?: string | null;
  /** `P4.9` — the *Keep files for* setting, in months, or `null` when the
   *  tenant has not set one. **`null` is not *forever* dressed up**: it is the
   *  absence of a policy, which is what every tenant has had until now, and the
   *  screen says nothing rather than promising a window nobody chose. */
  retentionMonths?: number | null;
  /** Opens Settings → Integrations, where both of the above are set. */
  onOpenDestinationSettings?: () => void;
  /** The server's refusal from the LAST send attempt, in its own words
   *  (BR-SHL-020). `null` when there has been none. */
  sendRefusal?: string | null;
  /** The server's four-gate answer for the CURRENT window, plus the preview
   *  itself. Passed in rather than read here so one window is read once. */
  children?: never;
}

export function ExportView(props: ExportViewProps) {
  const { t, client } = props;

  // The drawn params band is STAGED: p069 draws an `Apply` button, so a clerk
  // types two dates and a grouping and the table moves once, rather than
  // re-reading the books on every keystroke of a year.
  const [draftFrom, setDraftFrom] = useState(props.period?.start ?? "");
  const [draftTo, setDraftTo] = useState(props.period?.end ?? "");
  const [draftGrouping, setDraftGrouping] = useState<ExportGrouping>("account");
  const [draftGranularity, setDraftGranularity] = useState<ExportGranularity>("summary");
  const [applied, setApplied] = useState<{
    from: string;
    to: string;
    grouping: ExportGrouping;
    granularity: ExportGranularity;
  } | null>(null);

  // Before the first Apply the view shows the OPEN period — which is what the
  // screen showed before this view existed, so nobody loses a table by
  // arriving.
  const window = applied ?? {
    from: props.period?.start ?? "",
    to: props.period?.end ?? "",
    grouping: "account" as ExportGrouping,
    granularity: "summary" as ExportGranularity,
  };
  const spec = GROUPINGS[window.grouping];

  const [tableState, setTableState] = useState<TableRequestState>(() => ({
    q: "",
    sort: "gl_account",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  }));
  const [visible, setVisible] = useState<string[]>(() => defaultVisibleColumns("account"));
  const [notice, setNotice] = useState<ExportOutcome | null>(null);

  const ready = window.from !== "" && window.to !== "";

  // The ACCOUNT read. It runs for EVERY grouping, because it is the send
  // gate's read as well as the account table's — the four checks and `sendable`
  // are on it, and p069 draws them under every grouping.
  const previewQuery = useQuery({
    queryKey: ["finance", "export", "view-preview", window.from, window.to, props.target,
      window.granularity],
    queryFn: () =>
      getExportPreview(
        {
          from: window.from,
          to: window.to,
          target: props.target,
          granularity: window.granularity,
        },
        client,
      ),
    retry: false,
    enabled: ready,
  });
  const extractQuery = useQuery({
    queryKey: ["finance", "export", "view-extract", spec.extract ?? "", window.from, window.to],
    queryFn: () =>
      getExportExtract(
        { kind: spec.extract as ExportExtractKind, from: window.from, to: window.to },
        client,
      ),
    retry: false,
    enabled: ready && spec.extract !== null,
  });

  const preview = previewQuery.data;
  const rows: AnyRow[] = useMemo(() => {
    if (spec.extract === null) {
      return preview?.rows ?? [];
    }
    return (extractQuery.data?.rows ?? []) as AnyRow[];
  }, [spec.extract, preview, extractQuery.data]);
  const currency =
    spec.extract === null ? (preview?.currency ?? null) : (extractQuery.data?.currency ?? null);
  const loading = spec.extract === null ? previewQuery.isLoading : extractQuery.isLoading;

  const config = previewConfig({
    grouping: window.grouping,
    t,
    currency,
    locale: props.locale,
    onDrill: window.grouping === "account" ? props.onDrill : undefined,
  });
  const paged = clientPage(rows, tableState, previewSpec(window.grouping));

  const download = useMutation({
    mutationFn: async () => {
      const accepted = await requestListExport(
        downloadBody({
          grouping: window.grouping,
          from: window.from,
          to: window.to,
          target: props.target,
          granularity: window.granularity,
          visible,
          q: tableState.q,
        }),
        client,
      );
      // ONE job poller (11b §2.17). This file starts no interval of its own.
      return client.pollJob(accepted.job_id);
    },
    onSuccess: (job) => setNotice(exportOutcome(job, t)),
    onError: () => setNotice({ message: t("exports.failed"), ok: false, href: null }),
  });

  function apply(): void {
    const next = {
      from: draftFrom,
      to: draftTo,
      grouping: draftGrouping,
      granularity: draftGranularity,
    };
    setApplied(next);
    setVisible(defaultVisibleColumns(next.grouping));
    setTableState((current) => ({
      ...current,
      page: 1,
      q: "",
      sort: GROUPINGS[next.grouping].columns[0].key,
      dir: "asc",
    }));
    // A file asked for under the OLD grouping has nothing to say about the new
    // one, and a stale *"your download is ready"* over a different table is a
    // link to the wrong figures.
    setNotice(null);
    download.reset();
  }

  // p070 item 7 — *"a ✗ disables Send and says why, and so does another
  // grouping"*. Only Account is handed over; the other three are extracts.
  const groupingBlocksSend = window.grouping !== "account";
  const sendable = preview?.sendable === true && !groupingBlocksSend;

  return (
    <div className="flex flex-col gap-4">
      {/* ── 2 · the params band ─────────────────────────────────────────
          A `<form>` so Enter applies, which is what a clerk who typed two
          dates expects. The kit's fields, side by side, which is rule 38: a
          drawing decides what a form CONTAINS and the UI rules decide how it
          is built. */}
      <Panel>
        {/* ⚠ **ONE ROW ON THREE BASELINES UNTIL `DEF-LED-6728`.** This band was
            `flex flex-wrap items-end`, which aligns the BOTTOM of each field's
            box — so the two date fields, which carry the IS-8 regional echo
            under their inputs, had their labels and controls pushed 23px ABOVE
            the three selects, and `Apply` sat on a third height on a
            hand-written `pb-1`. The Product Owner reported it as *"filter is
            not align - it is not in 1 line"*.

            It is `FilterRow` now, which is a COMPONENT because B14 rule 43 says
            a piece of UI is one and because twenty screens in this product
            hand-roll this same band — an alignment fixed here alone would be
            fixed nowhere else. Read that file for why aligning from the TOP is
            the rhythm and a margin is the symptom.

            ⚠ **NOTHING IN THIS REPO COULD SEE IT.** `brazosbend`'s date format
            is `MM/DD/YYYY`, which is what headless Chromium draws inside a
            native date input, so `regionalDateEcho` returns `null` and the bar
            measures perfectly aligned on our own fixture. The defect exists for
            the six formats that differ — which is most tenants. */}
        <FilterRow
          data-filter-row="export-params"
          onSubmit={apply}
          action={
            <Button variant="primary" type="submit">
              {t("finance.export.apply")}
            </Button>
          }
        >
          <div className="min-w-[160px]">
            <DatePickerField
              id="export_period_start"
              label={t("finance.export.periodStart")}
              value={draftFrom}
              onChange={setDraftFrom}
              dateFormat={props.dateFormat}
              required
            />
          </div>
          <div className="min-w-[160px]">
            <DatePickerField
              id="export_period_end"
              label={t("finance.export.periodEnd")}
              value={draftTo}
              onChange={setDraftTo}
              dateFormat={props.dateFormat}
              // The end cannot precede the start, and the server says the same
              // (`ledger.export.window_invalid`). A bound the field enforces is
              // a refusal a clerk never has to meet.
              min={draftFrom === "" ? undefined : draftFrom}
              required
            />
          </div>
          <div className="min-w-[180px]">
            <SelectField
              id="export_group_by"
              label={t("finance.export.groupBy")}
              value={draftGrouping}
              onChange={(next) => setDraftGrouping(exportGroupingFrom(next))}
              options={EXPORT_GROUPINGS.map((one) => ({
                value: one,
                label: t(GROUPINGS[one].labelKey),
              }))}
            />
          </div>
          <div className="min-w-[200px]">
            <SelectField
              id="export_target"
              label={t("finance.export.target")}
              value={props.target}
              onChange={(next) => props.onTargetChange(next as ExportTarget)}
              options={(props.servedTargets ?? EXPORT_TARGETS).map((value) => ({
                value,
                label: t(`finance.export.target.${value}`, { defaultValue: value }),
              }))}
            />
          </div>
          <div className="min-w-[160px]">
            <SelectField
              id="export_detail"
              label={t("finance.export.detail")}
              value={draftGranularity}
              onChange={(next) => setDraftGranularity(next as ExportGranularity)}
              options={EXPORT_GRANULARITIES.map((one) => ({
                value: one,
                label: t(`finance.export.detail.${one}`),
              }))}
              // BR-LED-017 — weekly is an ACCOUNT split. An extract has no
              // window to divide, so the control says so rather than offering a
              // detail level the read cannot honour (BR-SHL-025).
              disabled={draftGrouping !== "account"}
              help={
                draftGrouping === "account" ? undefined : t("finance.export.detail.accountOnly")
              }
            />
          </div>
        </FilterRow>
        {/* `CR-069` wave J, kept through the restructure — *Going to Month-end
            journal · QuickBooks · downloaded here*, the adapter's own sentence
            rather than a second one composed here. `null` — no saved
            connection, a refused read, a server without wave J — renders
            nothing and leaves the band exactly as it was. */}
        {(props.savedDestination ?? null) !== null && (
          <div className="mt-3 flex flex-wrap items-baseline gap-3">
            <p className="m-0 text-sm" role="note">
              {t("finance.export.savedTarget", { destination: props.savedDestination })}
              {/* `P4.9` — the retention BESIDE the destination, because they
                  are one setting on one connection and a clerk asking *where
                  does this go* is the same clerk asking *and for how long*.
                  Silent when nobody has set one: an unset policy is not
                  *forever* and must not read as a promise. */}
              {props.retentionMonths != null && (
                <> {t("finance.export.retention", { months: props.retentionMonths })}</>
              )}
            </p>
            {/* The DOOR. p076 puts both settings on Settings → Integrations,
                and a screen that states a setting without a way to change it
                sends a clerk hunting through a settings tree for it. */}
            {props.onOpenDestinationSettings !== undefined && (
              <Button variant="ghost" onClick={props.onOpenDestinationSettings}>
                {t("finance.export.destinationSettings")}
              </Button>
            )}
          </div>
        )}
      </Panel>

      {/* ── 4 · the preview ─────────────────────────────────────────────── */}
      <Panel>
        <div className="mb-3 flex items-baseline justify-between gap-4">
          <h3 className="m-0 text-base font-semibold">{t("finance.export.previewTitle")}</h3>
          {notice !== null && <ExportNotice outcome={notice} t={t} />}
        </div>
        <DataTable
          config={config}
          state={tableState}
          onStateChange={setTableState}
          rows={paged.page}
          totalRows={paged.total}
          loading={loading}
          visibleColumns={visible}
          onVisibleColumnsChange={setVisible}
          // ── 6 · ↓ — the table AS SHOWN. See the header for why no PDF. ──
          downloadSlot={
            <DownloadButton
              onDownload={() => {
                setNotice(null);
                download.mutate();
              }}
              disabled={!ready || download.isPending || rows.length === 0}
            />
          }
          empty={{
            title: t("finance.export.emptyTitle"),
            helper: t("finance.export.emptyPeriod"),
          }}
        />
        {/* The foot the drawing puts under the table: *Balanced* and both
            totals. It is the ACCOUNT grouping's fact — an extract has no
            debit/credit pair to foot — so it renders there and nowhere else,
            rather than as a green tick nobody derived. */}
        {window.grouping === "account" && preview !== undefined && (
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3" data-foot="">
            <StatusPill tone={preview.balanced ? "success" : "danger"}>
              {preview.balanced ? t("finance.gl.balanced") : t("finance.export.doesNotFoot")}
            </StatusPill>
            <div className="flex items-center gap-6 text-sm">
              <span className="flex items-center gap-2">
                {t("finance.export.col.debit")}
                <MoneyCell
                  amount={preview.total_debits}
                  currency={preview.currency}
                  locale={props.locale}
                />
              </span>
              <span className="flex items-center gap-2">
                {t("finance.export.col.credit")}
                <MoneyCell
                  amount={preview.total_credits}
                  currency={preview.currency}
                  locale={props.locale}
                />
              </span>
            </div>
          </div>
        )}
        {/* BR-LED-039's payable side. NOT inside the footer above, and the
            label says so — a reader cannot add it to a balance it is not part
            of. p070 draws no cost row; this is here because dropping a figure
            off a live screen on a drawing's SILENCE is not a lane's decision. */}
        {window.grouping === "account" && preview !== undefined && (
          <ExportCostSection
            section={preview.cost_section}
            t={t}
            locale={props.locale}
          />
        )}
        {/* ── 7 · the four checks, then ↗ Send ────────────────────────────
            The checks are FACTS and the Send is the only thing a person can
            press — B14 keeps a control row to things that act, so the chips sit
            on their own line above it. */}
        {preview !== undefined && (
          <>
            <div className="mt-4 flex flex-wrap gap-2">
              {sendChecks(preview).map((check) => (
                <Chip
                  key={check.id}
                  data-check={check.id}
                  data-passed={check.passed ? "yes" : "no"}
                >
                  {check.passed ? "✓" : "✗"} {t(`finance.export.check.${check.id}`)}
                </Chip>
              ))}
            </div>
            {/* A ✗ chip says WHICH gate failed; this says what to do about it,
                and only for the gates that actually failed. Each is stated
                SEPARATELY because each has a different next action for the
                human reading it — which is the reasoning the panel this
                replaced carried, kept. */}
            {!preview.period_closed && (
              <p className="mt-2 mb-0 text-sm" role="note">
                {t("finance.export.blockedOpen")}
              </p>
            )}
            {preview.already_exported !== null && (
              <p className="mt-2 mb-0 text-sm" role="note">
                {t("finance.export.blockedAlready", {
                  from: preview.already_exported.period.start,
                  to: preview.already_exported.period.end,
                })}
              </p>
            )}
            {!preview.balanced && (
              <p className="mt-2 mb-0 text-sm" role="alert">
                {t("finance.export.blockedDrift")}
              </p>
            )}
            {preview.missing_refs.length > 0 && (
              <p className="mt-2 mb-0 text-sm" role="note">
                {t("finance.export.blockedRefs", { accounts: preview.missing_refs.join(", ") })}
              </p>
            )}
            {props.sendRefusal !== null && props.sendRefusal !== undefined && (
              <p className="mt-2 mb-0 text-sm" role="alert">
                {props.sendRefusal}
              </p>
            )}
            <div className="mt-3 flex items-center justify-end gap-3">
              {groupingBlocksSend && (
                <span className="text-sm" data-send-blocked="grouping">
                  {t("finance.export.sendAccountsOnly")}
                </span>
              )}
              <Button
                variant="primary"
                disabled={!sendable}
                onClick={() =>
                  props.onSend({
                    from: window.from,
                    to: window.to,
                    granularity: window.granularity,
                    preview,
                  })
                }
              >
                {t("finance.export.send")}
              </Button>
            </div>
          </>
        )}
      </Panel>
    </div>
  );
}

export default ExportView;

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/07 Finance Blueprint.pdf p017 (`P4.12`'s row), p069
//         (6·2 drawn), p070 (items 1–9 + the filter-criteria table), p071 (the
//         component table, DOORS, FIELDS, TABLE CONTROLS, RULES) — rendered at
//         scale 3 and read as IMAGES (B14 rule 42) ·
//         04-docs/02-decisions/14-ui-conventions.md rules 12/13/15/16/21/31/
//         32/33/43/44 · 06-backend/apps/ledger/finance_exports.py (the four
//         resources and their column names) · 06-backend/apps/tenancy/
//         exports.py `columns_for` (`P4.13`)
// generated: 2026-09-24 by LANE FIN-P4B
// checklist: A✔ B✔ C✔ D=n/a(no new endpoint) E✔(CloseExportPage mounts it) F✔ G✔ H=n/a
// exceptions:
//   E1 **NO `Download PDF`** — the drawing offers it and this deployment has no
//      PDF renderer. Set out in full in the header; reported, not silently
//      followed.
//   E2 **THE PREVIEW IS PAGED IN THE BROWSER** (`clientPage`). None of the four
//      reads takes `q`, `sort`, `page` or `per`, so there is nothing to hand a
//      server-paged `DataTable`. It is `NFR-3`'s shape and it is named here:
//      the four reads owe a backend task, and `P1.8` is the one p070 already
//      files for by-premises.
//   E3 **`EXPORT_GRANULARITIES` IS A HAND-COPY OF THE SERVER'S TUPLE**, which
//      is the shape `P1.6` removed from `EXPORT_TARGETS`. No response carries
//      the granularity vocabulary today; `GET /finance/export/batches` serves
//      `targets` and nothing serves this. Written down rather than left
//      implicit — it is two values and it has not moved since BR-LED-017 was
//      signed.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
