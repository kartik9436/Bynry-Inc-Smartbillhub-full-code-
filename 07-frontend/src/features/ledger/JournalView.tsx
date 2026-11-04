// ── Trace ──────────────────────────────────────────────
// Task:     Finance blueprint `P1.1` (the journal list onto the shared
//           `DataTable`) · `P1.9` (filter state into the URL) · `P1.15` (the
//           strip splits into four views and this one becomes the landing
//           view) · `P1.17` (two visible row actions plus the overflow)
// Drawing:  05-prototype/07 Finance Blueprint.pdf — **p020** is the wireframe
//           and its eight numbered notes; **p021** is the binding filter-criteria
//           table and the "Components to use" table; **p022** carries FOR /
//           DOORS / PRIMARY ACTION / FIELDS / TABLE CONTROLS / RULES.
//           Built from the RENDERED IMAGES (B14 rule 42), never from the text
//           layer — which for this document is scrambled.
// Rules:    B14 rule 2 (one page header — the page owns it, not this panel) ·
//           rule 4 (button grammar) · rule 12 (search + filter chips) ·
//           rule 13 (sortable headers) · rule 14 (the shared ColumnChooser) ·
//           rule 15 (row actions are icons, **two visible then `…`**) ·
//           rule 16 (a pagination footer) · rule 20 (ONE table type) ·
//           rule 21 (Tailwind utilities, no new stylesheet class — this file is
//           on `07-frontend/src/styles/route-b-migrated.txt`) · rule 31 (no
//           database id is ever a visible value) · rule 33 (the text caps, and
//           RATIONALE is zero words on screen) · rule 43 (a piece of UI is a
//           COMPONENT — this file exists because of that rule) · rule 44 (our
//           spacing, sizes, type scale and tokens decide HOW it is built) ·
//           BR-LED-012 · BR-LED-003 · BR-SHL-011 · BR-SHL-023 · BR-SHL-025
// ───────────────────────────────────────────────────────
//
// 1·1 JOURNAL — the Finance tab's landing view.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS REPLACES, AND WHY IT IS A FILE AND NOT A FUNCTION IN THE PAGE
// ══════════════════════════════════════════════════════════════════════════
// Until now the journal was a `PlainTable` rendered *inside* `?view=balance`,
// as a panel below the trial balance — no search, no chips, no column chooser,
// no pager and no sortable headers, on a list that grows with transaction
// volume. p022's own TABLE CONTROLS row says so: *"All six, none of which
// exists today."*
//
// **B14 rule 43** — ratified after *"use it"* turned out to mean 120 lines
// inline in a 4,186-line page — is why this is a component: a view that is a
// function body inside `GeneralLedgerPage.tsx` is importable by nothing and
// testable only through the whole screen.
//
// ══════════════════════════════════════════════════════════════════════════
// THE SERVER WAS ALREADY READY. THIS SCREEN IS WHERE THE PARAMS COME FROM
// ══════════════════════════════════════════════════════════════════════════
// p021's filter table ends with a box headed **SIX CRITERIA, ZERO NEW
// ENDPOINTS**: *"Every one of these is already accepted by the handler … and
// nothing has ever sent it a filter."* That is exactly what was true — the
// handler has taken `q`, `f.type`, `f.status`, `f.source_type`, `f.premises`
// and `f.ledger_account` for weeks, and the front end sent none of them.
//
// What `P1.8` added underneath, the same day: the page is now taken in SQL, so
// `page`, `per`, `sort` and `dir` mean something to the database rather than to
// a slice of a built list.
//
// ══════════════════════════════════════════════════════════════════════════
// THE ENTRY NUMBER SORTS BY DATE (p021's GAP box · `P1.18`)
// ══════════════════════════════════════════════════════════════════════════
// The drawing puts a `⇅` on ENTRY NO. and on DATE. `JE-{MM}{DD}{YY}-{0000}`
// does not sort chronologically as text — `JE-011526-0001` precedes
// `JE-020325-0001` and is ELEVEN MONTHS OLDER — and the PO ruled that format
// knowing so. The server maps both sort names onto `entry_date`; this file just
// declares the two columns sortable and never sorts anything itself.

import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { DataTable } from "@/components/DataTable";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { JOURNAL_PERIOD_CHOICES } from "@/components/periodWindow";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { FilterBar } from "@/components/FilterBar";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { RowAction, RowActions, RowActionsMore, RowMenuAction } from "@/components/RowActions";
import { StatusPill } from "@/components/StatusPill";
import { EyeIcon, RollBackIcon, TrashIcon } from "@/components/icons";
import { Dash } from "@/features/metering/meteringShared";
import { InlineLinkTo } from "@/components/Surfaces";
import { tenantPathFrom, useTenant } from "@/routing/tenantPath";
import { journalEntryDetailPath, journalSourcePath } from "./JournalEntryDetail";
import type { JournalEntriesResponse, JournalEntryListRow } from "@/api/endpoints";

type Translator = (key: string, params?: Record<string, unknown>) => string;

/** p021 row 2 — Standard · Accrual · Reversal, CHECK-constrained server-side. */
export const JOURNAL_TYPES = ["standard", "accrual", "reversing"] as const;

/** p021 row 3 — Draft · Posted, **and not `reversed`**.
 *
 *  ⚠ The drawing's own warning: *"⚠ **not** reversed — that is a link, never a
 *  status"*. `journal_entries.status` holds exactly two values, so offering a
 *  third would put a value in a filter no column can ever equal. Both reversal
 *  LINKS ride on every row and the State cell renders them. */
export const JOURNAL_STATUSES = ["draft", "posted"] as const;

/** p021 row 4 — *"Invoice · Payment · Opening balance · Credit note · Counter
 *  receipt · Refund (the six live on the fixture)"*.
 *
 *  ⚠ **A SOURCE THE VOCABULARY HAS NO WORD FOR STILL SHOWS, AS ITSELF.**
 *  `BR-REP-008`: nothing invisible. The filter offers the six the fixture
 *  holds; the COLUMN renders whatever arrives. */
export const JOURNAL_SOURCES = [
  "invoice",
  "payment",
  "opening_balance",
  "credit_note",
  "counter_receipt",
  "refund",
] as const;

/** `DEF-LED-10071` J3 — the three `f.` params the Period filter owns. */
export const JOURNAL_PERIOD_PARAMS = {
  choice: "period",
  from: "period_from",
  to: "period_to",
} as const;

/**
 * What the journal needs to know about the UTILITY to draw a date and count a
 * period — its zone, its date format and its business date. REQUIRED, never
 * defaulted: a date column that silently fell back to ISO is `DEF-LED-10075`,
 * and *Last 30 days* counted from the browser's clock is BR-TEN-043 broken.
 */
export interface JournalRegional {
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** The utility's business date, `YYYY-MM-DD`. */
  today: string;
  /**
   * `DEF-LED-10074` — the screen's word for a raw `source_type` the server's
   * BR-REP-008 vocabulary has no word for (`finance.journal.sourceCode.*`), or
   * `null` when the catalogue has none either and the raw code must show.
   */
  sourceWord: (sourceType: string) => string | null;
}

/** The screen id the shared `ColumnChooser` keys its per-user preference on. */
export const JOURNAL_SCREEN_ID = "S56.journal";

/**
 * The capability-matrix row, as a `TableConfig` — p022's FIELDS line in its
 * drawn order: *Entry no. · Date · Type · Memo · Source · Debit · Credit ·
 * State · Actions*.
 *
 * `response` is NULLABLE for the reason `trialBalanceConfig` already records
 * one screen over: parsing `?sort=` out of the URL needs the COLUMNS and
 * happens before any row has arrived, and a second columns-only config would be
 * two lists that can drift.
 */
export function journalConfig(
  response: JournalEntriesResponse | null,
  t: Translator,
  locale: string | undefined,
  regional: JournalRegional,
  actions?: {
    onReverse: (row: JournalEntryListRow) => void;
    onDeleteDraft: (row: JournalEntryListRow) => void;
    /** `DEF-LED-6723` — the eye's destination. */
    onOpen: (row: JournalEntryListRow) => void;
  },
  /** Record links (PO 2026-10-19). Absent — a bare config, as a test builds
   *  it — the number and the source stay text. `JournalView` always passes it. */
  tenantPath?: (path: string) => string,
): TableConfig<JournalEntryListRow> {
  return {
    screenId: JOURNAL_SCREEN_ID,
    // B14 rule 31 — `entry_id` keys React and the preference store and reaches
    // no cell. The identity column is the ENTRY NUMBER, which is the string a
    // bookkeeper says out loud, and a draft's is a dash by ruling.
    getRowId: (row) => row.entry_id,
    searchFields: ["je_number", "memo"],
    // B14 rule 19 — this list's own prompt, naming what the box matches.
    // p020 note 2: *"Searches the memo — and the entry number once P0.3 lands"*.
    // P0.3 landed on 2026-09-24.
    // `DEF-LED-10071` J2 — the box now also matches what an entry's LINES
    // belong to (J1), so the prompt names those too.
    searchPlaceholder: "finance.journal.searchPrompt",
    // p021's GAP box. `number` is offered because the drawing draws a `⇅` on
    // that header; the SERVER orders it by `entry_date`.
    defaultSort: { sort: "entry_date", dir: "desc" },
    filters: [
      {
        name: "type",
        label: t("finance.journal.col.type"),
        options: JOURNAL_TYPES.map((value) => ({
          value,
          label: t(`finance.journal.type.${value}`, { defaultValue: value }),
        })),
      },
      {
        name: "status",
        label: t("finance.journal.col.status"),
        options: JOURNAL_STATUSES.map((value) => ({
          value,
          label: t(`finance.journal.status.${value}`, { defaultValue: value }),
        })),
      },
      {
        name: "source_type",
        label: t("finance.journal.col.source"),
        options: JOURNAL_SOURCES.map((value) => ({
          value,
          // DEF-LED-10076 — the filter offers SOURCE TYPES, so it is labelled
          // from the per-type words (`sourceCode.*`), never the raw code.
          label: t(`finance.journal.sourceCode.${value}`, { defaultValue: value }),
        })),
      },
      // `DEF-LED-10071` J3 · J4 — Last 30 / 60 / 90 days or Custom, counted
      // from the UTILITY's business date. Absent from the URL means NO period
      // — every entry — which is the PO's ruled default (J4). It sends the
      // server's existing `from`/`to`; see `journalWindow`.
      {
        name: "period",
        label: t("finance.gl.period"),
        options: [],
        period: {
          ...JOURNAL_PERIOD_PARAMS,
          choices: JOURNAL_PERIOD_CHOICES,
          today: regional.today,
          dateFormat: regional.dateFormat,
        },
      },
    ],
    columns: [
      {
        key: "je_number",
        label: t("finance.journal.col.number"),
        sortable: true,
        identity: true,
        // A DRAFT HAS NO NUMBER (PO 2026-08-12). The dash is the ruling
        // rendered, never a missing value.
        //
        // Record links (PO 2026-10-19): the number opens the entry — the same
        // page the 👁 row action opens, which stays.
        cell: (row: JournalEntryListRow) =>
          row.je_number === null ? (
            <Dash />
          ) : tenantPath === undefined ? (
            row.je_number
          ) : (
            <InlineLinkTo to={tenantPath(journalEntryDetailPath(row.entry_id))}>
              {row.je_number}
            </InlineLinkTo>
          ),
      },
      {
        key: "entry_date",
        label: t("finance.journal.col.date"),
        sortable: true,
        // `DEF-LED-10075` (P9) — the utility's date format, `10/01/2026`, never
        // the ISO `2026-10-01` the wire carries. DateCell is the ONE path.
        cell: (row: JournalEntryListRow) =>
          row.entry_date === null ? (
            <Dash />
          ) : (
            <DateCell
              value={row.entry_date}
              timeZone={regional.timeZone}
              dateFormat={regional.dateFormat}
            />
          ),
      },
      {
        key: "type",
        label: t("finance.journal.col.type"),
        cell: (row: JournalEntryListRow) => t(`finance.journal.type.${row.type}`, { defaultValue: row.type }),
      },
      { key: "memo", label: t("finance.journal.col.memo"), cell: (row: JournalEntryListRow) => row.memo ?? "" },
      {
        key: "source",
        label: t("finance.journal.col.source"),
        cell: (row: JournalEntryListRow) => {
          // `DEF-LED-10074` — a source BR-REP-008 has no word for, but the PO
          // has named (*Counter session*), reads that word. The GROUPING
          // vocabulary is untouched; only the label on this cell changes.
          const word =
            row.source_label !== null && !row.source_mapped && row.source_type !== null
              ? regional.sourceWord(row.source_type)
              : null;
          // Record links (PO 2026-10-19): a bill, payment or refund source
          // opens that record; every other source stays a word.
          const sourcePath =
            tenantPath === undefined ? null : journalSourcePath(row.source_type, row.source_id);
          return row.source_label === null ? (
            <Dash />
          ) : row.source_mapped ? (
            sourcePath !== null && tenantPath !== undefined ? (
              <InlineLinkTo to={tenantPath(sourcePath)}>
                {t(`finance.journal.source.${row.source_label}`, { defaultValue: row.source_label })}
              </InlineLinkTo>
            ) : (
              t(`finance.journal.source.${row.source_label}`, { defaultValue: row.source_label })
            )
          ) : word !== null ? (
            word
          ) : (
            // `source_mapped=false` means BR-REP-008's vocabulary has no word
            // for this entry's source and the RAW value is showing through — a
            // visible gap by design, never bucketed under a familiar word.
            <span className="text-neutral-700">
              {t("finance.journal.sourceUnmapped", { source: row.source_type ?? "" })}
            </span>
          );
        },
      },
      {
        key: "debit",
        label: t("finance.journal.col.debit"),
        numeric: true,
        cell: (row: JournalEntryListRow) => <MoneyCell amount={row.debit} currency={row.currency} locale={locale} />,
      },
      {
        key: "credit",
        label: t("finance.journal.col.credit"),
        numeric: true,
        cell: (row: JournalEntryListRow) => <MoneyCell amount={row.credit} currency={row.currency} locale={locale} />,
      },
      {
        key: "status",
        label: t("finance.journal.col.status"),
        cell: (row: JournalEntryListRow) => (
          <span className="inline-flex items-center gap-2">
            <StatusPill tone={row.status === "posted" ? "success" : "warning"}>
              {t(`finance.journal.status.${row.status}`, { defaultValue: row.status })}
            </StatusPill>
            {/* r13 #2 — the reversal pair has TWO links and both are shown, in
                both directions: one column cannot answer "was this reversed?"
                and "is this the reversal?". */}
            {row.reversed_by_entry_id !== null && (
              <span className="text-neutral-700">{t("finance.journal.reversed")}</span>
            )}
            {row.reversal_of_entry_id !== null && (
              <span className="text-neutral-700">{t("finance.journal.isReversal")}</span>
            )}
            {!row.balanced && (
              <span className="text-danger-700" role="alert">
                {t("finance.journal.unbalancedDraft")}
              </span>
            )}
          </span>
        ),
      },
      {
        key: "actions",
        label: t("finance.journal.col.actions"),
        locked: true,
        cell: (row: JournalEntryListRow) =>
          actions === undefined ? null : (
            // p020 note 7, CHANGED: *"👁 view · ↺ reverse, then `…`. **Two
            // visible plus overflow** — the cap `RowActions` does not
            // enforce"*. B14 rule 15's last clause, honoured by the CALLER,
            // which is where the cap has always lived.
            //
            // ⚠ **HARD RULE 4 — THERE IS NO EDIT CONTROL HERE AND THERE NEVER
            // CAN BE.** A posted entry is immutable for ever and the only
            // correction is reverse + repost, which writes two NEW entries
            // through the posting service. A draft is not in the books, so
            // deleting one is lawful (`BR-LED-003`) and lives in the overflow.
            <RowActions>
              {/* ⚠ **THE HOLD IS RELEASED AND THE HANDLER ARRIVED WITH IT
                  (`DEF-LED-6723`, 2026-09-25).** This control was DISABLED WITH
                  ITS REASON under `BR-SHL-025`, correctly, because p022's WRITE
                  SURFACES line read *"Detail NOTHING — `GET /ledger/journal-
                  entries/{id}` is mounted DELETE-only"* and there was nothing
                  to open. The Product Owner clicked it anyway on v2.351.84:
                  *"we cannot click on eye."*

                  ⚠ **RELEASING A HOLD AND LANDING THE SCREEN ARE TWO ACTS AND
                  ONLY THE FIRST FEELS LIKE THE WORK** — that is hard-won law
                  2's mirror, and on 2026-09-05 it left the customer portal with
                  two working doors out of eight. So the destination is asserted
                  BY ADDRESS **and by the screen id it opens** in
                  `journalEntryDoor.dom.test.tsx`, in this commit. A test that
                  asserts only a path passes when the router mounts something
                  else there and both render *"not built yet"*.

                  ⚠ **THE KEY `finance.journal.noEntryDetail` IS RETIRED, NOT
                  REWORDED.** A refusal sentence that outlives its refusal is
                  the rot this file exists to stop repeating. */}
              <RowAction
                label={t("finance.journal.viewAction")}
                icon={<EyeIcon />}
                onClick={() => actions.onOpen(row)}
              />
              <RowAction
                label={t("finance.journal.reverseAction")}
                icon={<RollBackIcon />}
                reason={
                  row.status !== "posted"
                    ? t("finance.journal.draftNoReverse")
                    : row.reversed_by_entry_id !== null
                      ? t("finance.journal.alreadyReversed")
                      : null
                }
                onClick={() => actions.onReverse(row)}
              />
              <RowActionsMore label={t("finance.journal.moreActions")}>
                <RowMenuAction
                  label={t("finance.journal.deleteDraftAction")}
                  icon={<TrashIcon />}
                  danger
                  reason={
                    row.status === "posted" ? t("finance.journal.postedNoDelete") : null
                  }
                  onClick={() => actions.onDeleteDraft(row)}
                />
              </RowActionsMore>
            </RowActions>
          ),
      },
    ],
  };
}

export interface JournalViewProps {
  response: JournalEntriesResponse | null;
  loading: boolean;
  error?: { reason?: string; onRetry: () => void } | null;
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  locale?: string;
  /** The utility's zone, date format and business date — see `JournalRegional`. */
  regional: Omit<JournalRegional, "sourceWord">;
  onReverse: (row: JournalEntryListRow) => void;
  onDeleteDraft: (row: JournalEntryListRow) => void;
  /** `DEF-LED-6723` — what the eye opens. REQUIRED and not optional: an
   *  optional prop nothing passes is hard-won law 2's dead UI, and this
   *  control has already spent five weeks pointing at nothing. */
  onOpen: (row: JournalEntryListRow) => void;
}

/**
 * The whole of 1·1 — the panel, the toolbar, the table and the footer.
 *
 * ⚠ **THE ROWS ARE THE SERVER'S PAGE AND NOTHING HERE SLICES, SORTS OR FILTERS
 * THEM.** `totalRows` is the server's `count` over the FILTERED SET, which
 * `P1.8` made a `COUNT(*)`. A screen that re-sorted the page it was handed
 * would silently disagree with the pager beside it.
 */
/**
 * `DEF-LED-10074` — the regional block plus the catalogue lookup for a raw
 * source word. `i18n.exists` and not a sentinel `defaultValue`: a missing key
 * must read as MISSING, and the raw code must then show (BR-REP-008).
 */
export function journalRegional(
  regional: Omit<JournalRegional, "sourceWord">,
  t: (key: string) => string,
  i18n: { exists: (key: string) => boolean },
): JournalRegional {
  return {
    ...regional,
    sourceWord: (sourceType) => {
      const key = `finance.journal.sourceCode.${sourceType}`;
      return i18n.exists(key) ? t(key) : null;
    },
  };
}

/**
 * `DEF-LED-10071` J3 · J4 — the `from`/`to` the server is asked for, from the
 * journal's own filter state, or nothing at all when no period is chosen.
 * The state only ever holds a window `restorePeriod`/`setPeriod` accepted, so
 * a refused or half-typed period cannot reach the request.
 */
export function journalWindow(filters: Record<string, string>): { from?: string; to?: string } {
  const from = filters[JOURNAL_PERIOD_PARAMS.from];
  const to = filters[JOURNAL_PERIOD_PARAMS.to];
  if (filters[JOURNAL_PERIOD_PARAMS.choice] === undefined || from === undefined || to === undefined) {
    return {};
  }
  return { from, to };
}

export function JournalView(props: JournalViewProps) {
  const { t, i18n } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const { timeZone, dateFormat, today } = props.regional;
  const tenant = useTenant();
  const config = useMemo(
    () =>
      journalConfig(
        props.response,
        translate,
        props.locale,
        journalRegional(props.regional, t, i18n),
        {
          onReverse: props.onReverse,
          onDeleteDraft: props.onDeleteDraft,
          onOpen: props.onOpen,
        },
        (path) => tenantPathFrom(tenant, path),
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [props.response, props.locale, t, timeZone, dateFormat, today, tenant],
  );

  return (
    <Panel>
      {/* B14 rule 44 — the gap is `--space-4` from the scale, and the heading
          is the panel heading the kit already draws. The page head's 32px title
          (rule 40) belongs to the PAGE and is not repeated here (rule 2). */}
      <div className="mb-4 flex items-center justify-between gap-4">
        <h3 className="m-0 font-heading text-h5 leading-heading">
          {t("finance.journal.title")}
        </h3>
      </div>
      <DataTable<JournalEntryListRow>
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
          title: t("finance.journal.noMatchTitle"),
          helper: t("finance.journal.noMatchHelper"),
          ctaLabel: t("finance.journal.clearSearch"),
          ctaVariant: "secondary",
          onCta: () => props.onStateChange({ ...props.state, q: "", filters: {}, page: 1 }),
        }}
      />
    </Panel>
  );
}
