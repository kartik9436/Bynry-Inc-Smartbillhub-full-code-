// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-006 · US-SHL-007 · US-SHL-008 (EP-SHL-02 §Stories)  Screens: every list screen (S14, S15, S17, S25, S30, S33, S34, S37, S45, S49, S108, …)
// Rules:    BR-SHL-010 (one framework) · BR-SHL-011 (URL grammar) · BR-SHL-012 (state composition) · BR-SHL-013 (column visibility)
// ───────────────────────────────────────────────────────
// FE-02 DataTable (B13 §1): THE one table. Config-driven from the consuming
// screen's capability-matrix row (BR-SHL-010 — an undeclared capability never
// renders); server-side pagination/sort/search expressed as the BR-SHL-011
// request-state object the consumer serializes; TanStack Table headless
// underneath; A18 states composed from the EXISTING StateFrame components
// (BR-SHL-012 — never reimplemented here). Row actions, bulk selection and the
// real export control are later packets (FE-04 ConfirmDialog, FE-14
// DownloadButton, US-SHL-014 gating) — this file carries only the IS-9 hook
// point: a capability-row slot the consumer fills (`downloadSlot`).
import { Fragment, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import type { ColumnDef } from "@tanstack/react-table";

import { ColumnChooser } from "./ColumnChooser";
import { EmptyList, FailedWithRetry, LoadingSkeleton, ZeroResults } from "./StateFrame";
import {
  PAGE_SIZES,
  clampPage,
  columnPreferenceKey,
  columnsFromPreference,
  defaultVisibleColumns,
  pageCount,
} from "./tableTypes";
import type { PageSize, TableConfig, TableRequestState } from "./tableTypes";

import "./DataTable.css";
import { getUserPreference, putUserPreference } from "@/api/endpoints";
import { useListAnalytics } from "@/analytics";
import { InfoIcon } from "@/components/icons";
import { createSearchDebouncer } from "./searchDebounce";
import type { SearchDebouncer } from "./searchDebounce";

// ⚠ **IS-3's TWO CONSTANTS AND THE DEBOUNCER ITSELF MOVED TO
// `./searchDebounce` ON 2026-09-19 (`DEF-CWP-5747`) AND ARE RE-EXPORTED HERE
// UNCHANGED.** No importer moves: `ShellWithSession`, `FindTheAddress` and this
// file's own suite go on reading them from `@/components/DataTable`. They left
// because the PORTAL needed the debouncer and may not import this module —
// `BR-CWP-011`, and `portal/components/listTable.tsx` records the whole reason:
// this file's module scope calls `@/api/endpoints`, which is the staff edge and
// answers 403 to every portal session.
export { createSearchDebouncer, SEARCH_DEBOUNCE_MS, SEARCH_MIN_CHARS } from "./searchDebounce";
export type { SearchDebouncer } from "./searchDebounce";

// ── Request-state transitions (pure, testable without a browser) ───────────
// Derived least-surprise law: any change to q, filters, sort, or page size
// returns to page 1 — the result set changed, so the old page number is
// meaningless. Only explicit paging keeps the page.

export function withSearch(state: TableRequestState, q: string): TableRequestState {
  return { ...state, q, page: 1 };
}

// IS-2: click-header single-column sort with direction toggle. Ties are broken
// by a stable secondary sort by id ON THE SERVER — the request never carries a
// second column.
export function nextSortState(state: TableRequestState, columnKey: string): TableRequestState {
  if (state.sort === columnKey) {
    return { ...state, dir: state.dir === "asc" ? "desc" : "asc", page: 1 };
  }
  return { ...state, sort: columnKey, dir: "asc", page: 1 };
}

export function withPage(state: TableRequestState, page: number): TableRequestState {
  return { ...state, page };
}

export function withPageSize(state: TableRequestState, per: PageSize): TableRequestState {
  return { ...state, per, page: 1 };
}

// A18 §2 clear-filters action: drops the search AND every filter in one step.
export function clearQueryAndFilters(state: TableRequestState): TableRequestState {
  return { ...state, q: "", filters: {}, page: 1 };
}

// ── Column-visibility transitions (BR-SHL-013, pure) ───────────────────────
// The visible set is an ORDERED array of column keys, and it is what gets
// STORED: `useColumnPreference` below writes exactly what these three functions
// return to `user_preferences` key `table.<screen>.columns`, and reads it back
// on mount (BR-SHL-013 / BR-SHL-027 / BR-SHL-024).
//
// ⚠ **THIS COMMENT USED TO SAY "the consumer persists to …" AND NO CONSUMER DID
// (DEF-647).** The PO found it by using the product: *"when I make changes to
// colume selector and save it; it save temaprarily … it reset to deault"*. The
// transitions below were built, unit-tested and green; there was no endpoint and
// no caller, so the ordered array they return went nowhere. Hard-won law 1 — a
// comment claiming a guarantee is not the guarantee — in the file whose comment
// made the claim. The transitions themselves are UNCHANGED by the fix: what was
// missing was never the value, only its round trip.

export function toggleColumnVisible<Row>(
  visible: string[],
  key: string,
  config: TableConfig<Row>,
): string[] {
  const column = config.columns.find((c) => c.key === key);
  if (column === undefined || column.identity === true || column.locked === true) {
    // BR-SHL-013: the identity column cannot be hidden — the toggle is a no-op
    // (its checkbox also renders disabled).
    //
    // ⚠ `locked` IS ENFORCED HERE AND NOT ONLY ON THE CHECKBOX. The disabled
    // checkbox is what a MOUSE meets; this is what a keyboard and a stored
    // column set from before the flag existed go through. A lock enforced in
    // one of the two is a lock a saved preference walks straight past.
    return visible;
  }
  if (visible.includes(key)) {
    return visible.filter((k) => k !== key);
  }
  // A re-shown column appends at the end of the visible order — boring and
  // predictable; the user moves it from there (IS-5 reorder).
  return [...visible, key];
}

export function moveColumnUp(visible: string[], key: string): string[] {
  const index = visible.indexOf(key);
  if (index <= 0) {
    return visible;
  }
  const next = [...visible];
  next[index] = next[index - 1];
  next[index - 1] = key;
  return next;
}

export function moveColumnDown(visible: string[], key: string): string[] {
  // IS-5 says "show/hide + reorder" and r10 draws BOTH arrows on every row.
  // Only ↑ existed, so a column could be moved up and never back down — the
  // reorder was one-directional and a user who overshot had to Reset table.
  const index = visible.indexOf(key);
  if (index < 0 || index >= visible.length - 1) {
    return visible;
  }
  const next = [...visible];
  next[index] = next[index + 1];
  next[index + 1] = key;
  return next;
}

// ── Expanded-row transitions (CR-029 RC-W3-T0, pure) ───────────────────────
// The open set is an ORDERED array of row ids, the same shape and the same
// reasons as `visibleColumns` above: trivially comparable in a test, trivially
// serializable the day a screen wants to keep a row open across a refresh.
//
// ⚠ SCOPED TO THE CURRENT PAGE, DELIBERATELY. Pagination is server-side (IS-2),
// so "all rows" can only ever mean the rows this page was served — expanding
// something the client has never seen is not a state the component can be in.
// A row id left over from the previous page is inert rather than an error
// (BR-SHL-024's shape: an unknown stored value reads as absent, never as a
// crash), which is why `areAllRowsExpanded` asks about THESE rows.

export function toggleExpandedRow(expanded: readonly string[], rowId: string): string[] {
  if (expanded.includes(rowId)) {
    return expanded.filter((id) => id !== rowId);
  }
  return [...expanded, rowId];
}

export function expandAllRows(rowIds: readonly string[]): string[] {
  return [...rowIds];
}

export function collapseAllRows(): string[] {
  return [];
}

// The bulk control's own predicate — it names the action it will PERFORM, so
// it has to know whether anything is left to open. An empty page is never
// "all expanded": a control offering to collapse nothing is a lie.
export function areAllRowsExpanded(
  expanded: readonly string[],
  rowIds: readonly string[],
): boolean {
  return rowIds.length > 0 && rowIds.every((id) => expanded.includes(id));
}

// ── The column preference: read on mount, write on change (DEF-647) ────────
//
// THE LAST QUARTER OF A MECHANISM THAT WAS THREE-QUARTERS BUILT. `UserPreference`
// (tenancy migration 0002), its RLS policy (0003), BR-SHL-013's key name,
// `TableConfig.screenId` and the pure transitions above all existed; a read and
// a write did not, so every list in the product — accounts, premises, assets,
// reads, invoices, payments — forgot the user's columns the moment the
// component remounted.
//
// WHY IT LIVES IN THE KIT AND NOT IN THE 25 CONSUMERS. Every consuming screen
// already declares `screenId`, which is the whole input this needs. Putting the
// round trip here fixes the chooser on every list at once; putting it in the
// consumers would fix it on the ones a lane remembered, which is the shape of
// the defect being fixed. `components/CustomFields.tsx` sets the precedent for a
// kit component reading through FI-01.
//
// WHAT IT DELIBERATELY DOES NOT DO:
//  · It does not run when the consumer CONTROLS `visibleColumns`. A screen that
//    passes the pair owns the storage; two writers on one key is a race, not a
//    feature. (Nothing passes it today — see G13's allow entry.)
//  · It never surfaces a failure. A preference is a convenience: if the read
//    fails the list renders its declared defaults, and if the write fails the
//    choice still applies for this session. A toast per failed column toggle
//    would be worse than the defect.
//  · It does not block the first paint. The list renders defaults and switches
//    to the stored set when the read lands — which is invisible in practice,
//    because a list is showing `LoadingSkeleton` for its own rows at that
//    moment anyway.
//  · It never clobbers a choice the user has ALREADY made: if the read resolves
//    after the first toggle (a slow network, a fast finger), `touched` discards
//    it. Restoring a preference over a live edit is the same bug in the mirror.

interface ColumnPreference {
  visible: string[];
  /** Called with exactly what the pure transitions returned — see above. */
  update: (next: string[]) => void;
}

function useColumnPreference<Row>(config: TableConfig<Row>, controlled: boolean): ColumnPreference {
  const [visible, setVisible] = useState<string[]>(() => defaultVisibleColumns(config));
  // ⚠ **A LIST WHOSE COLUMNS ARRIVE FROM THE SERVER WAS INVISIBLE, AND NOTHING
  // ANYWHERE WENT RED (`DEF-REP-6838`, found by walking 2·1 in a browser).**
  // The state above is seeded ONCE, at mount. Every list in the product until
  // 2026-09-26 declared its columns as a literal, so "once" was always
  // "forever" and the seed was right. Screen 2·1 declares them from the
  // report's OWN response — 46 reports cannot have 46 hand-typed column lists —
  // so at mount `config.columns` is EMPTY, the seed is `[]`, and the table then
  // renders thirty rows of nothing: a `<tbody>` with thirty `<tr>`s in it and
  // not one cell. `tsc`, every gate and a DOM test counting `tbody tr` all pass.
  //
  // So the seed is re-taken WHILE UNTOUCHED, whenever the declared set changes.
  // For every existing list that is a no-op: a static `columns` yields the same
  // signature on every render, so `setVisible` is never called and the markup is
  // byte-for-byte what it was (asserted against `__fixtures__/DataTable.baseline.html`).
  //
  // ⚠ It stops the moment the USER touches the chooser, and it never overrides
  // a STORED preference — `touchedRef` is set by both, which is the same guard
  // the restore below already leans on. Re-seeding over a clerk's own choice
  // would be this defect in the mirror, and worse.
  // `config` is an object literal in nearly every consumer, so it is a NEW
  // reference on every render and cannot be an effect dependency without
  // re-fetching forever. The ref is the same idiom `fireRef` uses above.
  const configRef = useRef(config);
  configRef.current = config;
  const touchedRef = useRef(false);
  // `DEF-RAT-9112`: the DEFAULT set is part of the signature too, so a list
  // whose defaults follow the viewport (rate schedules and charge codes below
  // 1440) re-seeds when the window crosses it — while untouched, exactly as
  // above. A static config yields the same string every render, so nothing
  // else re-seeds.
  const declared = config.columns
    .map((column) => `${column.key}${column.defaultVisible === false ? "-" : ""}`)
    .join("|");
  const seeded = useRef(declared);
  useEffect(() => {
    if (controlled || touchedRef.current || seeded.current === declared) {
      return;
    }
    seeded.current = declared;
    setVisible(defaultVisibleColumns(configRef.current));
  }, [declared, controlled]);
  const preferenceKey = columnPreferenceKey(config);

  useEffect(() => {
    if (controlled || preferenceKey === null) {
      return;
    }
    let cancelled = false;
    void getUserPreference<unknown>(preferenceKey)
      .then((stored) => {
        // Unmounted, already edited, or nothing stored (BR-SHL-024: an unknown
        // key reads as absent and the caller keeps its defaults).
        if (cancelled || touchedRef.current || stored === null) {
          return;
        }
        setVisible(columnsFromPreference(stored, configRef.current));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [preferenceKey, controlled]);

  return {
    visible,
    update: (next: string[]) => {
      touchedRef.current = true;
      setVisible(next);
      if (controlled || preferenceKey === null) {
        return;
      }
      // Fire and forget, last-write-wins (BR-SHL-024). Not debounced: a column
      // toggle is a deliberate click, not a keystroke, and a debounce would let
      // a user close the tab between the choice and the write.
      void putUserPreference(preferenceKey, next).catch(() => undefined);
    },
  };
}

// ── Width: a list never overflows its column (DEF-SHL-5378) ────────────────
// Measured in Chromium on 2026-10-01 against a real tenant: at 1440 the Rate
// schedules list was 1,188px in a 1,120px column, Charge codes 1,176px and
// Assets 1,246px; at 1280 Plans, Units and Meter reads joined them. Every
// ancestor computed `overflow-x: visible` up to `main.view`, which is
// `overflow-x: hidden` — so the page did not scroll, the overhang was simply
// CUT, and the last thing on each row (the Retire icon) was half off screen.
//
// Two causes, two fixes, both here because every list shares them:
//   1. **The header refused to wrap.** `.data-table th` carried
//      `white-space: nowrap`, so eleven uppercase, letter-spaced headers set a
//      floor the table could not go under: "CUSTOMER CLASS" alone held 159px.
//      The declaration is DELETED from DataTable.css (rule 21: existing CSS
//      only shrinks). A header now breaks between words only when the column
//      is short of room — a table with room lays out exactly as before. That
//      alone brings Rate schedules and Charge codes to 1,120px at 1440.
//   2. **A table that still cannot fit had nowhere to go.** It now scrolls
//      sideways inside its own box (the UI skill's rule: a table scrolls in its
//      container, the page never does), and its row-actions column is pinned
//      to the right edge while it does, so the icons are never the part that
//      is out of sight.
//
// ⚠ jsdom performs no layout, so in a unit test `overflows` is always false and
// the markup is the fitting table's. The proof that a list fits is a browser
// measurement: `10-scripts/render-checks/table-width-fit.mjs`.

/** The column key every list in the product gives its row-action icons. */
export const ACTIONS_COLUMN_KEY = "actions";

/**
 * The pinned actions column, Tailwind only (B14 rule 21). It needs an opaque
 * background or the scrolled cells show through it; every list measured sits
 * on the page background (`--color-bg`). The row hover in DataTable.css is a
 * translucent tint and an unlayered rule, so it would win over a plain utility
 * and turn the pinned cell see-through on hover — hence `!` and the same 4%
 * tint mixed over the page background for the hovered row.
 *
 * ⛔ **`DEF-SHL-10777` — THIS SAID *"NO `z-index`, deliberately"* AND WAS WRONG
 * THE DAY IT WAS WRITTEN.** It reasoned that a z-index would make each pinned
 * cell its own stacking context and paint the `…` menu (`RowActionsMore`,
 * `z-40`) under the next row's cell. **`position: sticky` already makes every
 * pinned cell a stacking context**, so that is exactly what happened: on the
 * Payments list the menu opened under the row below and a pointer click on
 * *Reverse* landed on that row's cell. So the cell holding an OPEN menu is
 * lifted above its neighbours, and only while it is open.
 */
export const PINNED_ACTIONS_CELL =
  "sticky right-0 !bg-bg [.data-table-row:hover>&]:!bg-[color-mix(in_srgb,var(--color-text)_4%,var(--color-bg))] [&:has(details[open])]:z-10";
export const PINNED_ACTIONS_HEADER = "sticky right-0 !bg-bg";

/**
 * Is the table wider than the box it sits in? Re-measured whenever either one
 * changes size — a column shown from ▦, a page of longer rows, a window
 * resized. One pixel of slack, because Chromium reports fractional widths.
 */
export function useTableOverflowsX(
  boxRef: { current: HTMLElement | null },
  tableRef: { current: HTMLElement | null },
): boolean {
  const [overflows, setOverflows] = useState(false);
  useEffect(() => {
    const box = boxRef.current;
    const table = tableRef.current;
    if (box === null || table === null || typeof ResizeObserver === "undefined") {
      return undefined;
    }
    const measure = () => {
      setOverflows(table.getBoundingClientRect().width > box.clientWidth + 1);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(box);
    observer.observe(table);
    return () => observer.disconnect();
  });
  return overflows;
}

// ── The component ──────────────────────────────────────────────────────────

/**
 * What a table does when its rows could not be fetched — `null` for *"this read
 * cannot fail here"*, an object for *"it failed, and this is how to ask again"*.
 *
 * ⚠ **EXPORTED SO A SCREEN CAN THREAD IT DOWN TO A TAB THAT OWNS THE TABLE
 * (`DEF-SHL-6915`).** Four of `RouteReadsPage`'s tabs, `TrialBalanceTable` and
 * `RuleMatrix` all take their rows from a parent that holds the query, so the
 * only honest thing they can say about a failure is what the parent hands them.
 * Before this type each of them simply said nothing, and `DataTable` then read
 * *"no rows"* as *"no matches"* and told the clerk to clear their filters.
 */
export type DataTableError = { reason?: string; onRetry: () => void } | null;


export interface DataTableProps<Row> {
  config: TableConfig<Row>;
  state: TableRequestState;
  onStateChange: (next: TableRequestState) => void;
  rows: readonly Row[]; // the CURRENT PAGE only — pagination is server-side (IS-2)
  totalRows: number | null; // server-provided total; null until the first response
  loading: boolean;
  // US-SHL-006 TC-6: Retry re-issues the identical query — the request state is
  // untouched by a failure. `reason` is plain language (BR-SHL-020); a catalog
  // default renders when the consumer has none.
  error?: DataTableError;
  // BR-SHL-012: the consuming screen supplies ONLY the empty-list copy + CTA.
  // `ctaReason` (optional) renders that CTA disabled WITH its reason — for a
  // screen whose create flow is a later story, so the empty state never offers
  // a live button onto nothing (BR-SHL-025's shape; added with S17).
  empty: {
    title: string;
    helper: string;
    /** The one way in. **OPTIONAL since 2026-09-10 (`DEF-MET-4764`)**: a list
     *  nobody can fill — a record's audit history — offers nothing rather than
     *  passing a no-op handler to satisfy a required prop, which `EmptyList`
     *  then wires to a live button that does nothing. Absent draws no button;
     *  every existing caller is byte-for-byte unchanged. */
    ctaLabel?: string;
    ctaReason?: string | null;
    /** B14 rule 4 — `secondary` when the page header already carries this
     *  action, so the screen has one primary. Absent = `primary`, unchanged. */
    ctaVariant?: "primary" | "secondary";
    /** Absent WITH `ctaLabel` absent = no button is drawn. */
    onCta?: () => void;
    /** A SECOND way to fill the list, in the ghost tier under the first.
     *  Optional and absent by default, so every existing empty block is
     *  byte-for-byte unchanged — see `EmptyList` for why it exists. */
    secondaryCtaLabel?: string;
    onSecondaryCta?: () => void;
  };
  // Controlled column visibility (ordered visible keys). The consumer wires
  // persistence through US-SHL-013's preference service; uncontrolled falls
  // back to the config default set.
  visibleColumns?: string[];
  onVisibleColumnsChange?: (keys: string[]) => void;
  filterBarSlot?: ReactNode; // FE-03 FilterBar, composed by the consumer (IS-4)
  downloadSlot?: ReactNode; // IS-9 hook point — FE-14 DownloadButton lands here later
  /**
   * **THE TOTALS ROW** — `CR-142-BRC07` `P2.5`, for 2·1's report table.
   *
   * Given the VISIBLE column keys, in their current order, returns a `<tr>`.
   * Absent draws no `<tfoot>` at all, so every existing list renders exactly
   * what it rendered before.
   *
   * ⚠ **IT TAKES THE VISIBLE KEYS BECAUSE THE COLUMN CHOOSER MOVES THEM.** A
   * footer built from the DECLARED columns puts its figures under the wrong
   * headings the moment a clerk hides one, and nothing on screen says so.
   */
  renderFooterRow?: (visibleColumnKeys: readonly string[]) => ReactNode;
  // ⛔ **THERE IS NO `dimensionsSlot`, AND ITS ABSENCE IS A RULING, NOT AN
  //    OMISSION (DEF-1700, PO 2026-08-27).**
  //
  //    DEF-1085 added one: a designed second row, right-aligned, for a screen's
  //    dimension controls. It was built because Premises, Units and Reads had
  //    each put a `SegmentedFilter` into `downloadSlot` and the Reads row
  //    finally overflowed. The slot was the right answer to the question that
  //    was asked — *where do these controls go* — and the Product Owner then
  //    answered a different one, looking at the result: *"on premsies screen -
  //    why we are having - apartment complex, comemrcial building etc in
  //    toolkit as per our stadard first raw of tookkit is more than suficient ;
  //    how many places such isue is there - I can see it in unit also"*.
  //
  //    **Nowhere. The controls go away.** All four chip rows duplicated a
  //    dimension the same screen already declared in `TableConfig.filters`, so
  //    the `+ Filter` panel offered every one of them, from the same option
  //    source, writing the same `f.<name>` param. Row one is B14 rule 12's set
  //    plus the IS-9 export, it is bounded, and it is the whole toolbar.
  //
  //    ⚠ **A SCREEN THAT WANTS A NEW DIMENSION DECLARES IT IN
  //    `TableConfig.filters`** and passes `filterBarSlot`. It does not grow a
  //    row. Re-adding this prop would re-open DEF-1700, and `G43` clause (c)
  //    still fails a dimension control placed in `downloadSlot` — the hole the
  //    three screens originally stepped in.
}

export function DataTable<Row>(props: DataTableProps<Row>) {
  const { config, state, onStateChange } = props;
  const { t } = useTranslation();

  // CR-169-BRC10 — `list_searched` / `list_filtered`: whether there was a
  // search, which filter by NAME, and how many rows came back. Never the text
  // and never a filter's value; one call here covers every list.
  useListAnalytics({
    list: config.screenId,
    q: state.q,
    filters: state.filters,
    settled: !props.loading && props.error == null,
    total: props.totalRows,
  });

  // Search input is local while typing; the debouncer commits it to request
  // state. Initial value restores a pasted URL's q (BR-SHL-011).
  const [input, setInput] = useState(state.q);
  const fireRef = useRef<(q: string) => void>(() => undefined);
  fireRef.current = (q) => onStateChange(withSearch(state, q));
  const debouncerRef = useRef<SearchDebouncer | null>(null);
  if (debouncerRef.current === null) {
    debouncerRef.current = createSearchDebouncer((q) => fireRef.current(q), state.q);
  }
  const debouncer = debouncerRef.current;
  useEffect(() => {
    const active = debouncerRef.current;
    return () => active?.clear(); // cancel a pending fire on unmount
  }, []);

  // Column visibility: controlled when the consumer passes the pair, otherwise
  // held here and PERSISTED per user under `table.<screen>.columns` (DEF-647 —
  // see `useColumnPreference` above; before it, this state died with the mount).
  // Unknown stored keys are dropped defensively (BR-SHL-024: an unknown
  // preference reads as absent → fall back, never error).
  const preference = useColumnPreference(config, props.visibleColumns !== undefined);
  const requestedVisible = props.visibleColumns ?? preference.visible;
  let visibleKeys = requestedVisible.filter((key) => config.columns.some((c) => c.key === key));
  const identityKey = config.columns.find((c) => c.identity === true)?.key;
  if (identityKey !== undefined && !visibleKeys.includes(identityKey)) {
    // BR-SHL-013: the identity column is ALWAYS visible, whatever was stored.
    // This is why `columnsFromPreference` does not re-insert it: one owner.
    visibleKeys = [identityKey, ...visibleKeys];
  }
  function updateVisible(next: string[]): void {
    preference.update(next);
    props.onVisibleColumnsChange?.(next);
  }

  // CR-029 RC-W3-T0: which rows are open. Internal state — a screen that needs
  // the open set in its URL gets a controlled pair the day it exists, and not
  // before (two more optional props nothing passes is the DEF-007..010 shape).
  const [expandedRowIds, setExpandedRowIds] = useState<string[]>([]);

  // DEF-SHL-5378 / DEF-RAT-8842 — does the table need more room than its
  // column has? Measured, never guessed: see `useTableOverflowsX`.
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const tableRef = useRef<HTMLTableElement | null>(null);
  const overflows = useTableOverflowsX(scrollRef, tableRef);

  // TanStack Table (headless) — all paging/sorting/filtering is manual because
  // the server owns it (IS-2); TanStack contributes the column/row model.
  const columnDefs: ColumnDef<Row>[] = config.columns.map((col) => ({
    id: col.key,
    // A column may draw a control in its head (`DEF-WRK-9689`: the select
    // column's *Select all* box); the LABEL still names it in the `▦` panel.
    header: col.header !== undefined ? () => col.header?.() : col.label,
    accessorFn: (row: Row) => (row as Record<string, unknown>)[col.key],
    cell: (ctx) =>
      col.cell !== undefined ? col.cell(ctx.row.original) : String(ctx.getValue() ?? ""),
  }));
  const table = useReactTable({
    data: props.rows as Row[],
    columns: columnDefs,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => config.getRowId(row),
    manualPagination: true,
    manualSorting: true,
    manualFiltering: true,
    state: {
      columnOrder: visibleKeys,
      columnVisibility: Object.fromEntries(
        config.columns.map((c) => [c.key, visibleKeys.includes(c.key)]),
      ),
      sorting: [{ id: state.sort, desc: state.dir === "desc" }],
    },
  });

  // BR-SHL-012 / A18 §1: nothing created yet → the consumer's empty-list block
  // replaces the WHOLE table region — no toolbar, and never an empty header.
  // (Placed after every hook call — hooks must run unconditionally.)
  const hasQueryState = state.q !== "" || Object.keys(state.filters).length > 0;
  if (!props.loading && props.error == null && props.totalRows === 0 && !hasQueryState) {
    // Passed field by field rather than spread: `ctaReason` is optional, and a
    // spread hides which props actually reach the component — the shape G13
    // was written to catch (a prop declared, rendered behind, and never given).
    return (
      <EmptyList
        title={props.empty.title}
        helper={props.empty.helper}
        ctaLabel={props.empty.ctaLabel}
        ctaReason={props.empty.ctaReason}
        ctaVariant={props.empty.ctaVariant}
        onCta={props.empty.onCta}
        secondaryCtaLabel={props.empty.secondaryCtaLabel}
        onSecondaryCta={props.empty.onSecondaryCta}
      />
    );
  }

  const total = props.totalRows ?? 0;
  const lastPage = pageCount(total, state.per);
  const numericKeys = new Set(config.columns.filter((c) => c.numeric === true).map((c) => c.key));
  const columnByKey = new Map(config.columns.map((c) => [c.key, c]));
  // ⋮ menu order: visible columns in display order, then hidden ones
  // (interim IS-5 spec — CONFIRMED for v1 by OQ-013's closure → BR-SHL-027).
  const menuColumns = [
    ...visibleKeys.map((key) => columnByKey.get(key)),
    ...config.columns.filter((c) => !visibleKeys.includes(c.key)),
  ].filter((c): c is NonNullable<typeof c> => c !== undefined);

  // ── CR-029 RC-W3-T0 · the expandable-row capability ──────────────────────
  // Declared on the config or absent entirely (BR-SHL-010). `expandable` gates
  // EVERY piece of markup below, which is what makes an undeclared list render
  // byte-for-byte what it rendered before this landed.
  const renderExpanded = config.renderExpanded;
  const expandable = renderExpanded !== undefined;
  // ── THE WHOLE ROW AS A TARGET (config.rowHref; absent = unchanged) ───────
  //
  // ⚠ **THIS DOES NOT NAVIGATE. IT ACTIVATES THE ROW'S OWN IDENTITY LINK**,
  // and the first draft did navigate — with `useNavigate()` at the top of this
  // component — which made **every list in the product require a `<Router>`**.
  // 40 cases in `src/components` went red instantly on
  // *"useNavigate() may be used only in the context of a <Router>"*, because
  // the kit's own suites mount `DataTable` bare and always have.
  //
  // **The failure was the useful part, so the fix is the better design:** a row
  // click finds the `<a>` the identity cell already renders and clicks it. Three
  // things fall out of that and each is worth more than the line it saves —
  // the row and the identity cell can never disagree about where they go, the
  // kit keeps no second navigation implementation (hard-won law 5), and
  // `DataTable` needs no router context at all, so BR-SHL-010's *"byte-identical
  // to a list that never heard of the feature"* holds for the DEPENDENCIES too
  // and not only for the markup.
  //
  // A declared `rowHref` with no identity link therefore does nothing, which is
  // the honest outcome: there was never a keyboard-reachable target to widen.
  const rowHref = config.rowHref;
  /**
   * A click inside anything that already does something is NOT a row click.
   * Without this the select checkbox would navigate, the identity link would
   * fire twice, and every row action would open the detail as a side effect.
   * `closest` walks up from the real target, so a `<span>` inside a button is
   * covered too.
   */
  function rowClickIsOwn(target: EventTarget | null): boolean {
    return (
      target instanceof Element &&
      target.closest("a,button,input,select,textarea,label,[role]") === null
    );
  }
  const pageRowIds = props.rows.map((row) => config.getRowId(row));
  const openRows = new Set(expandedRowIds);
  const allExpanded = areAllRowsExpanded(expandedRowIds, pageRowIds);
  const bulkKey = allExpanded ? "table.expand.allCollapse" : "table.expand.all";

  // The row-actions column is pinned to the right edge ONLY while the table is
  // scrolling sideways, and only when it is the last visible column — a pinned
  // column in the middle of a row would sit on top of its neighbours.
  const lastVisibleKey = visibleKeys[visibleKeys.length - 1];
  const pinActions = overflows && lastVisibleKey === ACTIONS_COLUMN_KEY;
  function cellClass(key: string, base: string | undefined, header: boolean): string | undefined {
    if (!pinActions || key !== ACTIONS_COLUMN_KEY) {
      return base;
    }
    return [base, header ? PINNED_ACTIONS_HEADER : PINNED_ACTIONS_CELL].filter(Boolean).join(" ");
  }

  /** The row's own name, for the control's accessible name.
   *
   * ⚠ TWELVE BUTTONS ALL CALLED "EXPAND" ARE UNUSABLE WITHOUT A MOUSE, which
   * is the same failure B14's note on rule 15 describes for a nameless icon:
   * it renders beautifully, passes every text assertion, and a screen-reader
   * user cannot tell which row they are opening. The identity column is the
   * one column BR-SHL-013 guarantees is present and is what a person calls the
   * row ("PRM-001"), so it is the name; the row id is the fallback for a
   * config with no identity column. */
  function rowLabel(row: Row): string {
    if (identityKey !== undefined) {
      const value = (row as Record<string, unknown>)[identityKey];
      if (value !== undefined && value !== null && String(value) !== "") {
        return String(value);
      }
    }
    return config.getRowId(row);
  }

  function handleClearSearch(): void {
    setInput("");
    debouncer.clear();
    onStateChange(withSearch(state, "")); // IS-3: ✕ clears immediately, no debounce
  }

  function handleClearAll(): void {
    setInput("");
    debouncer.clear();
    onStateChange(clearQueryAndFilters(state));
  }

  return (
    <div className="data-table-frame">
      {/* IS-5 capability row: search + filters + download slot + column chooser.
          BR-SHL-010: each piece renders only if the matrix row declares it. */}
      <div className="table-toolbar">
        {config.searchFields !== undefined && (
          // ⚠ **THE BOX'S WIDTH AND ITS LOOK BOTH LIVE HERE NOW (DEF-1150).**
          //    `DataTable.css` declared `.table-search input { … min-width:
          //    220px }` and NOTHING RENDERED `.table-search` after the Route B
          //    migration — the class left the markup and the rule stayed in the
          //    stylesheet. With Tailwind's preflight and no bare `input` rule
          //    anywhere in `src/**/*.css`, the search box on all 27 lists had NO
          //    styling at all: it fell back to the browser's ~170px default and
          //    cut 20 of the 27 prompts mid-word. The PO read
          //    "Search asset #, serial, r" on the Assets page and reported it.
          //
          //    THE SIZING, ratified as CR-045 R2: WANTS 320px (`flex` basis),
          //    grows to fill whatever the toolbar leaves, SHRINKS to a 240px
          //    floor before anything wraps, and never exceeds 512px.
          //
          //    ⚠ **THE FLOOR IS 240px AND NOT 320px, AND THE DIFFERENCE IS THE
          //    WHOLE POINT.** A hard 320px floor would ADD width to a toolbar
          //    this file already records as over budget — ~1,360px of controls
          //    in ~1,150px of room on the reads list (DEF-1085) — and would push
          //    the filters and the ▦ onto a second row on a narrow viewport.
          //    The three CR-045 wave A changes only work as a SET: search takes
          //    +150px, the ↓ glyph gives back ~95px, and R7's five-term cap on
          //    prompts is what lets the box shrink to 240px without cutting
          //    text. **Filters wrap; the search never does.**
          //
          //    It rides on the WRAPPER and not on the input, because the wrapper
          //    is the flex item `.table-toolbar` lays out — sizing the input
          //    instead leaves the wrapper content-sized and the grow leg dead,
          //    which looks identical in source and is wrong on screen.
          //    `.table-toolbar` is already `flex-wrap: wrap`, so growing is safe.
          //
          //    THE LOOK is `.input`, the field kit `FormModal.css` already
          //    declares. B14 rule 21 asks for no NEW stylesheet class, and
          //    reusing a declared one adds none — which is what the rule is
          //    actually after (DEF-974). The orphaned `.table-search*` rules are
          //    deleted in this same commit rather than left beside the fix
          //    (hard-won law 1), and G31's ceiling comes down with them.
          //
          //    ⚠ THE ✕ FOLLOWS THE WIDTH because it is `absolute right-2` inside
          //    THIS wrapper. A wider box with the ✕ stranded where 170px used to
          //    end is the obvious way this regresses, so it is asserted rather
          //    than assumed — see `DataTableSearchWidth.dom.test.tsx`.
          <div className="relative flex min-w-[15rem] max-w-[32rem] flex-[1_1_20rem] items-center">
            <input
              // `DEF-SHL-5345` — the ✕ below is the kit's; Chromium's own
              // search-cancel button is hidden so the box shows ONE cross.
              className="input [&::-webkit-search-cancel-button]:appearance-none"
              type="search"
              value={input}
              // B14 rule 19 (DEF-510): the list's OWN prompt when its config
              // declares one, and "Search this list" when it does not — so the
              // field could land without moving a single screen. The accessible
              // name is the SAME sentence: a screen reader reading "Search this
              // list" over a box the sighted user is told matches premises,
              // units and meters is the split B14 rule 19 exists to close.
              placeholder={t(config.searchPlaceholder ?? "table.search.placeholder")}
              aria-label={t(config.searchPlaceholder ?? "table.search.placeholder")}
              onChange={(e) => {
                setInput(e.target.value);
                debouncer.type(e.target.value);
              }}
            />
            {input !== "" && (
              <button
                type="button"
                className="absolute right-2 cursor-pointer border-none bg-transparent text-btn-sm text-accent-text"
                aria-label={t("table.search.clear")}
                onClick={handleClearSearch}
              >
                ✕
              </button>
            )}
          </div>
        )}
        {props.filterBarSlot}
        <div className="table-toolbar-spacer" />
        {/* IS-9 hook point (US-SHL-008): the consumer's Download control renders
            here — FE-14 DownloadButton once it exists. Absent slot = no export
            capability (BR-SHL-010). */}
        {props.downloadSlot}
        {/* ⚠ **THE `▦` PANEL MOVED TO `components/ColumnChooser.tsx` ON
            2026-09-16 (`DEF-INT-5498`), AND IT IS A MOVE RATHER THAN A
            REWRITE.** The Integration Blueprint asks the connector CARD GRID
            for the same control and says why it must be this one: *"Naming it
            ▦ Columns keeps the kit's own control rather than minting a second
            one — B14 rule 36."* A card grid cannot mount `DataTable`, so the
            only way to honour that was to lift the panel out of here. Every
            byte of its markup is unchanged and `DataTableColumnPrefs.dom.test.tsx`
            and `DataTableColumnAnchor.dom.test.tsx` are what proves it.
            ⚠ **THE THREE DECISIONS STAYED HERE.** `toggleColumnVisible`
            re-inserts a re-shown column at its CONFIG position and refuses
            BR-SHL-013's identity column; the reset is this table's default
            set. Handing the chooser arrays instead of callbacks would have
            dropped all three quietly. */}
        <ColumnChooser
          items={menuColumns.map((col) => ({
            key: col.key,
            label: col.label,
            locked: col.identity === true || col.locked === true,
          }))}
          visible={visibleKeys}
          onToggle={(key) => updateVisible(toggleColumnVisible(visibleKeys, key, config))}
          onMoveUp={(key) => updateVisible(moveColumnUp(visibleKeys, key))}
          onMoveDown={(key) => updateVisible(moveColumnDown(visibleKeys, key))}
          onReset={() => updateVisible(defaultVisibleColumns(config))}
        />
      </div>

      {props.loading ? (
        // BR-SHL-012 / A18 §3: skeleton rows while fetching — never a bare spinner.
        <LoadingSkeleton variant="table" />
      ) : props.error != null ? (
        // BR-SHL-012 / A18 §4 via the ONE FailedWithRetry (BR-SHL-020). Its
        // Download-report/Cancel actions have no list-load meaning — no-ops
        // unless the consumer wires them (API friction flagged to EP-SHL-04).
        <FailedWithRetry
          title={t("table.failed.title")}
          reason={props.error.reason ?? t("table.failed.reason")}
          onRetry={props.error.onRetry}
          onDownloadReport={() => undefined}
        />
      ) : total === 0 ? (
        // A18 §2: toolbar/filters stay; the rows region (header included —
        // BR-SHL-012's empty-header ban) is replaced.
        <ZeroResults query={state.q} onClearFilters={handleClearAll} />
      ) : (
        <>
          {/* ⚠ **THE TABLE SCROLLS SIDEWAYS INSIDE ITS OWN BOX, AND ONLY THE
              TABLE DOES (DEF-SHL-5378, DEF-RAT-8842).** The toolbar is OUTSIDE
              this wrapper on purpose: `overflow-x: auto` also clips the y axis,
              so a wrapper around the whole frame would cut off the `+ Filter`
              and `▦ Columns` panels that drop down from the toolbar — which is
              why the rate-schedules lane could not fix this on one screen. The
              wrapper only SCROLLS when the table is measured wider than it
              (`useTableOverflowsX`); a table that fits keeps no clipping box at
              all, so a row's `…` menu opening below the last row is never cut. */}
          <div
            ref={scrollRef}
            data-table-scroll=""
            className={overflows ? "max-w-full overflow-x-auto" : "max-w-full"}
          >
          <table className="data-table" ref={tableRef}>
            <thead>
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {/* RC-W3-T0 · EXPAND ALL lives in the expander column's own
                      header cell, NOT in the toolbar. B14 rule 12 fixes the
                      toolbar's grammar exactly — `[Search…] [All | chips ×]
                      [+ Filter ▾] … [▦ Columns]` — so a control appended there
                      breaks a ratified rule on every list in the product to
                      serve one; above the column it governs is where a reader
                      looks for it anyway. B14 rule 21: Tailwind utilities, no
                      stylesheet class. */}
                  {expandable && (
                    <th scope="col" className="w-10">
                      <button
                        type="button"
                        className="inline-flex h-6 w-6 cursor-pointer items-center justify-center border-none bg-transparent text-btn-sm text-accent-text"
                        aria-label={t(bulkKey)}
                        title={t(bulkKey)}
                        onClick={() =>
                          setExpandedRowIds(
                            allExpanded ? collapseAllRows() : expandAllRows(pageRowIds),
                          )
                        }
                      >
                        {/* The glyph is a TEXT disclosure marker, aria-hidden,
                            like this table's own ▲▼ sort arrows — not an SVG
                            from `icons.tsx`. B14 rule 15's glyph vocabulary is
                            for ROW ACTIONS ("this only for table actions ; not
                            for buttons", PO 2026-08-20) and G37 refuses one
                            inside a plain <button>; a disclosure triangle is
                            not in that vocabulary and inventing an entry for it
                            would widen a ruled list without a ruling. */}
                        <span aria-hidden="true">{allExpanded ? "▾" : "▸"}</span>
                      </button>
                    </th>
                  )}
                  {headerGroup.headers.map((header) => {
                    const col = columnByKey.get(header.column.id);
                    // `DEF-MET-10164` — a column may send another column's sort
                    // (`sortKey`), so "is this header sorted" compares the SORT
                    // NAME it sends, not its key.
                    const sortName = col?.sortKey ?? header.column.id;
                    const sorted = state.sort === sortName;
                    const headerContent = flexRender(
                      header.column.columnDef.header,
                      header.getContext(),
                    );
                    return (
                      <th
                        key={header.id}
                        // IS-2: the sorted column is indicated visually.
                        className={cellClass(
                          header.column.id,
                          [col?.numeric === true ? "cell-num" : "", sorted ? "th-sorted" : ""]
                            .filter(Boolean)
                            .join(" ") || undefined,
                          true,
                        )}
                        aria-sort={
                          sorted ? (state.dir === "asc" ? "ascending" : "descending") : undefined
                        }
                      >
                        {col?.sortable === true ? (
                          <button
                            type="button"
                            className="table-sort"
                            onClick={() => onStateChange(nextSortState(state, sortName))}
                          >
                            {headerContent}
                            {sorted && (
                              <span className="table-sort-arrow" aria-hidden="true">
                                {state.dir === "asc" ? "▲" : "▼"}
                              </span>
                            )}
                          </button>
                        ) : (
                          headerContent
                        )}
                        {/* The ⓘ sits OUTSIDE the sort button on purpose: it is
                            not part of the sort control, and a marker inside a
                            button would be announced as part of the button's
                            name and re-sort the table when someone clicked the
                            footnote. `title` carries the accessible name for a
                            pointer; `aria-label` carries it for a reader. */}
                        {col?.headerNote !== undefined && col.headerNote !== "" && (
                          <span
                            className="ml-1 inline-flex items-center align-middle"
                            data-header-note=""
                            role="img"
                            aria-label={col.headerNote}
                            title={col.headerNote}
                          >
                            <InfoIcon />
                          </span>
                        )}
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => {
                const isOpen = openRows.has(row.id);
                const regionId = `${config.screenId}-expanded-${row.id}`;
                return (
                  <Fragment key={row.id}>
                    <tr
                      // The cursor is the only VISIBLE difference a declared
                      // `rowHref` makes; the row hover was always there.
                      className={
                        rowHref === undefined
                          ? "data-table-row"
                          : "data-table-row cursor-pointer"
                      }
                      // BR-SHL-010 — every one of these is UNDEFINED on a list
                      // that declares no `rowHref`, so its markup is unchanged.
                      data-row-href={rowHref?.(row.original) ?? undefined}
                      onClick={
                        rowHref === undefined
                          ? undefined
                          : (event) => {
                              // Let a text selection be a text selection.
                              if (
                                rowHref(row.original) === null ||
                                !rowClickIsOwn(event.target) ||
                                (window.getSelection()?.toString() ?? "") !== ""
                              ) {
                                return;
                              }
                              event.currentTarget
                                .querySelector<HTMLAnchorElement>("a[href]")
                                ?.click();
                            }
                      }
                    >
                      {expandable && (
                        <td className="w-10">
                          <button
                            type="button"
                            className="inline-flex h-6 w-6 cursor-pointer items-center justify-center border-none bg-transparent text-btn-sm text-accent-text"
                            // The three a11y facts a disclosure owes: it is a
                            // real button (Tab reaches it, Enter and Space
                            // work, focus stays put across the toggle), its
                            // state is aria-expanded, and it points at the
                            // region it opened. `aria-controls` is written only
                            // while the region EXISTS — a collapsed row renders
                            // nothing to point at, and a dangling reference is
                            // worse than none.
                            aria-expanded={isOpen}
                            aria-controls={isOpen ? regionId : undefined}
                            aria-label={t(
                              isOpen ? "table.expand.rowCollapse" : "table.expand.row",
                              { row: rowLabel(row.original) },
                            )}
                            title={t(isOpen ? "table.expand.rowCollapse" : "table.expand.row", {
                              row: rowLabel(row.original),
                            })}
                            onClick={() =>
                              setExpandedRowIds(toggleExpandedRow(expandedRowIds, row.id))
                            }
                          >
                            <span aria-hidden="true">{isOpen ? "▾" : "▸"}</span>
                          </button>
                        </td>
                      )}
                      {row.getVisibleCells().map((cell) => (
                        <td
                          key={cell.id}
                          className={cellClass(
                            cell.column.id,
                            numericKeys.has(cell.column.id) ? "cell-num" : undefined,
                            false,
                          )}
                        >
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                    {/* The open row's content, in ONE cell spanning the whole
                        table so the sub-table is not squeezed into a column.
                        It is REMOVED when collapsed rather than hidden: a
                        display:none sub-table is still in the accessibility
                        tree's document order and still costs its render on
                        every page of 1,000 rows.
                        ⚠ NO `data-table-row` CLASS. That class is this table's
                        row hover AND the string the shipped suite counts to
                        assert a page holds 50 rows — an expanded row wearing it
                        would silently make every one of those counts wrong. */}
                    {expandable && isOpen && (
                      <tr>
                        <td
                          id={regionId}
                          colSpan={visibleKeys.length + 1}
                          className="bg-neutral-100"
                        >
                          {renderExpanded(row.original)}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
            {props.renderFooterRow === undefined ? null : (
              // ⚠ **A TOTALS ROW IS PART OF THE TABLE, NOT A STRIP UNDER IT**
              // (`CR-142-BRC07` `P2.5`, drawn on 2·1a/2·1b). It must share the
              // column widths, or the figure under *Amount* stops being under
              // *Amount* the moment a column is hidden — and the column chooser
              // makes that a thing a clerk does. Putting it outside the
              // `<table>` and lining it up with CSS is the version of this that
              // looks right until somebody uses the product.
              //
              // ⚠ **OPT-IN (B14 rule 36).** Absent renders nothing at all, so
              // every one of the 25 lists in the product is byte-for-byte
              // unchanged — asserted against `__fixtures__/DataTable.baseline.html`.
              //
              // The consumer is handed the VISIBLE column keys in their current
              // order and returns the cells; the kit owns neither what a total
              // means nor how money is formatted. This screen computes nothing
              // (BR-REP-002) — every figure it puts here is the server's.
              <tfoot>{props.renderFooterRow(visibleKeys)}</tfoot>
            )}
          </table>
          </div>
          <div className="table-pager">
            <span className="table-pager-range">
              {t("table.pager.range", {
                from: (state.page - 1) * state.per + 1,
                to: Math.min(state.page * state.per, total),
                total,
              })}
            </span>
            <label className="table-pager-size">
              {t("table.pager.pageSize")}
              <select
                value={state.per}
                onChange={(e) =>
                  onStateChange(withPageSize(state, Number(e.target.value) as PageSize))
                }
              >
                {PAGE_SIZES.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="table-page-btn"
              disabled={state.page <= 1}
              aria-label={t("table.pager.prev")}
              onClick={() =>
                onStateChange(withPage(state, clampPage(state.page - 1, total, state.per)))
              }
            >
              ‹
            </button>
            <button
              type="button"
              className="table-page-btn"
              disabled={state.page >= lastPage}
              aria-label={t("table.pager.next")}
              onClick={() =>
                onStateChange(withPage(state, clampPage(state.page + 1, total, state.per)))
              }
            >
              ›
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-006@e879338 (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-08-10 by story-coder (W2 customers lane — the `empty` block carries an optional `ctaReason` through to the shared EmptyList, for a screen whose create flow is a later story)
//            · AMENDED 2026-08-23 by the CR-029 RC-W3-T0 kit lane (B17 §7) — `config.renderExpanded` adds EXPANDABLE ROWS: an expander column, a per-row disclosure button and Expand-all/Collapse-all. Built one wave ahead of SET-06.3, its consumer, so `DataTable.dom.test.tsx` drives the real states rather than asserting a type exists (hard-won law 2)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ tsc✔ eslint✔ vitest 31/31✔ (5 TC todo this packet — browser/journey/backend scope) · [W2 customers lane 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 622 passed / 148 todo across 47 files✔ · vite build✔ · run_gates 14 PASS · 0 FAIL · 1 SKIP✔
//        · [CR-029 RC-W3-T0 2026-08-23] tsc✔ eslint --max-warnings 0 on src/components✔ vitest 2100 passed / 184 todo across 122 files✔ · g13✔ g37✔ g34✔ g02✔ g40✔ · g31 n/a (this file is Route B — its utilities are compiled by src/styles/routeBUtilities.test.ts, green) · every other run_gates failure names another lane's files, checked one by one
// exceptions: E4 [2026-08-10] the empty block is handed to EmptyList field by field instead of spread — a spread hides which props actually reach the component, which is the shape G13 exists to catch
//        · E3 [2026-08-23] `renderExpanded` lives on the CONFIG, not on `DataTableProps` — BR-SHL-010 puts capability declarations on the capability-matrix row, and it is a per-row render function of `Row`, which is `cell`'s shape. A consequence worth stating plainly: G13 reads `props.X` idioms and therefore does NOT see a config-level slot, so it is this file's tests and not that gate which prove the capability is exercised
//        · E3 [2026-08-23] the disclosure glyph is a TEXT marker (▸/▾) like this table's own ▲▼ sort arrows, not an `icons.tsx` SVG — B14 rule 15's vocabulary is for row actions (PO 2026-08-20: "this only for table actions ; not for buttons") and G37 refuses one inside a plain <button>
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
