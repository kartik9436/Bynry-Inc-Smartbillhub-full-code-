// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 2 task `P2.18`
//          (*"Drill through to the facts"*, p12, read as an image per B14
//          rule 42). Outcome, verbatim: *"A $48,221.14 subtotal opens the 412
//          rows that make it"*.
// Defect:  DEF-REP-6869 (the group row's `path` is not a filter set) ·
//          DEF-REP-6871 (44 of 71 dimensions offer a subtotal that cannot be
//          opened — which is why the control is ABSENT rather than dead)
// Rules:   B14 rule 43 (a piece of UI is built as a COMPONENT) · rule 33
//          (a LABEL ≤ 3 words · a FACT ≤ 6 words · RATIONALE is ZERO words on
//          screen) · rule 31 (no database id is ever visible) · rule 21
//          (Tailwind utilities only) · rule 15 (icons live in
//          `components/icons.tsx`; nothing here hand-draws an `<svg>`) ·
//          CLAUDE.md hard-won law 2's mirror (a live screen behind a dead
//          control)
//          AMENDED 2026-09-27 (lane REP-P2-REST) for `P2.24` — *"Drill down in
//          place. A group row expands to the next level WITHOUT LEAVING THE
//          REPORT — Area opens its routes, a route its premises. Collapse
//          restores it."* p013, and p028's 2·1E note ②: *"A group row · ▾ open
//          · ▸ closed, expands in place, no page load"*, both read as images.
// Tests:   07-frontend/src/features/reports/reportGroupRow.dom.test.tsx ·
//          07-frontend/src/features/reports/reportDrillDownInPlace.dom.test.tsx
// Impacts: ReportViewerPage.tsx (renders these inside the table body)
// ───────────────────────────────────────────────────────
import { Link } from "react-router-dom";

import type { ReportGroupRow, ReportRow, ReportTotal } from "@/api/reportsEndpoints";
import { isRefusedTotal, isReportGroupRow } from "@/api/reportsEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

import { RefusedTotalCell } from "./RefusedTotalCell";

/**
 * THE SUBTOTAL ROW'S TWO CELLS, AND THE DOOR OUT OF ONE OF THEM.
 *
 * ⚠ **A GROUP ROW IS AN ORDINARY TABLE ROW HERE, NOT A ROW SPANNING EVERY
 * COLUMN, AND THAT IS A DELIBERATE READING OF `P2.18` RATHER THAN A
 * SHORTCUT.** The task's whole argument is that *"a subtotal is a number you
 * cannot check"*; a figure that sits UNDER ITS OWN COLUMN HEADING is a figure
 * a clerk can check against the rows below it, and a spanning band puts it
 * somewhere else on the screen from the numbers it totals. It also needs no
 * change to the shared `DataTable`, whose rendered output is pinned by
 * `__fixtures__/DataTable.baseline.html` for all 25 lists in the product.
 *
 * ⚠ **THE DRILL-THROUGH IS ABSENT WHERE THE SERVER OFFERS NO FILTERS, AND
 * THAT IS THE LOAD-BEARING HALF.** `runner.bind` discards a parameter the
 * dataset does not declare, silently — so a control built on a guessed filter
 * opens the WHOLE report under a chip naming one group. Measured on real
 * PostgreSQL 16: replaying a group's `path` verbatim returns 30 rows for a
 * group of 11 and for a group of 19 alike. **44 of the registry's 71
 * dataset/dimension pairs cannot be drilled today** (`DEF-REP-6871`), so this
 * is the common case and not an edge one.
 */

// ═══════════════════════════════════════════════════════════════════════════
// `P2.24` — DRILL DOWN IN PLACE
// ═══════════════════════════════════════════════════════════════════════════
//
// ⚠ **`P2.24` IS NOT `P2.18` WITH A TRIANGLE, AND THE DIFFERENCE IS A NETWORK
// REQUEST.** A drill-THROUGH navigates: it leaves this report, applies the
// group's filters and asks the server for the facts. A drill-DOWN opens the
// next level of a payload ALREADY IN HAND — *"without leaving the report … no
// page load"*. The server sends every level of a grouping in one flat, ordered
// list precisely so this can be true (`slicers.group_rows`'s own docstring:
// *"Flat rather than nested because the table renders rows and `P2.24` opens
// and closes a level IN PLACE"*), so this file adds no fetch of any kind.
//
// ⚠ **EXPANDABILITY IS DERIVED FROM THE PAYLOAD, NEVER FROM BEING A GROUP.**
// Measured on real PostgreSQL 16 against the seeded `brazosbend` tenant,
// 2026-09-27 (`10-scripts/rep_p2_24_grouping_depth.py`): of the **46** live
// report definitions, **one** groups to three levels (`trend_pack`), **two** to
// exactly one (`ar_aging` by consumer class, `journal_export` by service) and
// **43** cannot group at all. On the SQL path the answer is `collapsed: true` —
// group rows and NO facts — so the deepest group row opens NOTHING.
//
// A disclosure drawn on it would be hard-won law 2's mirror exactly: a control
// that runs, changes nothing, and tells a clerk there is more to see. So
// `openableGroups` asks whether the NEXT row is deeper, which is a question
// about the data in hand and cannot be wrong about it.

/** A row of a report as the table renders it — a fact, or a subtotal. */
export type ReportViewerRow = ReportRow | ReportGroupRow;

/**
 * How a group row is remembered across renders.
 *
 * ⚠ **THE VIEWER'S `getRowId` CALLS THIS RATHER THAN REPEATING IT.** The React
 * key and the open/closed set must be the SAME string or a row opens and the
 * wrong one redraws; two places composing it from the same four fields is the
 * shape that drifts (hard-won law 5, one source).
 *
 * B14 rule 31 is untouched: this feeds keys and state and is never drawn.
 */
export function groupDisclosureKey(row: ReportGroupRow): string {
  return `group:${row.level}:${row.dimension}:${String(row.value)}`;
}

/** A fact row sits beneath every group above it, so it is deeper than all of
 *  them. Expressed as a number so one comparison covers both kinds. */
const DEEPER_THAN_ANY_GROUP = Number.MAX_SAFE_INTEGER;

function depthOf(row: ReportViewerRow): number {
  return isReportGroupRow(row) ? row.level : DEEPER_THAN_ANY_GROUP;
}

/**
 * The group rows that have something beneath them — and ONLY those.
 *
 * The list is flat and in tree order, so *"has children"* is *"is the next row
 * deeper than this one"*. A level-2 group followed by another level-2 group has
 * nothing of its own; a group followed by a fact has its facts.
 */
export function openableGroups(rows: readonly ReportViewerRow[]): ReadonlySet<string> {
  const open = new Set<string>();
  rows.forEach((row, index) => {
    if (!isReportGroupRow(row)) return;
    const next = rows[index + 1];
    if (next !== undefined && depthOf(next) > row.level) {
      open.add(groupDisclosureKey(row));
    }
  });
  return open;
}

/**
 * The rows to draw: every row whose ANCESTORS ARE ALL OPEN.
 *
 * ⚠ **EVERY ancestor, not the immediate parent** — and that is the case a
 * naive implementation passes an open/close pair on and still gets wrong.
 * Closing the year while the month is still in the open set must hide the month
 * AND the service under it; re-opening the year then restores the month
 * expanded, which is *"collapse restores it"* read exactly.
 *
 * ⚠ **AN UNGROUPED REPORT COMES BACK BYTE-FOR-BYTE.** 43 of the 46 definitions
 * cannot group at all, so the common path through this function must be the
 * identity — the chain is empty, `every` is vacuously true, and every row is
 * emitted in order.
 *
 * Pure and exported, so the states can be asserted as arithmetic without
 * mounting anything — and then asserted AGAIN on the real screen, because a
 * perfect function nothing calls is law 2's *built is not wired*.
 */
export function visibleRows(
  rows: readonly ReportViewerRow[],
  open: ReadonlySet<string>,
): ReportViewerRow[] {
  const ancestors: { key: string; level: number }[] = [];
  const shown: ReportViewerRow[] = [];
  for (const row of rows) {
    if (isReportGroupRow(row)) {
      while (ancestors.length > 0 && ancestors[ancestors.length - 1].level >= row.level) {
        ancestors.pop();
      }
      if (ancestors.every((a) => open.has(a.key))) shown.push(row);
      ancestors.push({ key: groupDisclosureKey(row), level: row.level });
    } else if (ancestors.every((a) => open.has(a.key))) {
      shown.push(row);
    }
  }
  return shown;
}

/** Open a closed group, close an open one. A new set, so React sees the change. */
export function toggleGroup(open: ReadonlySet<string>, key: string): ReadonlySet<string> {
  const next = new Set(open);
  if (!next.delete(key)) next.add(key);
  return next;
}

/**
 * The ▸ / ▾ control, exactly as 2·1E note ② draws it.
 *
 * ⚠ **THE TWO GLYPHS ARE THE KIT'S OWN AND SO ARE THE TWO STRINGS.**
 * `DataTable.tsx:718` already draws `▾` open and `▸` closed for its Expand-all,
 * and `table.expand.row` / `table.expand.rowCollapse` are already translated in
 * all eleven catalogues. Minting `reports.group.expand` would have been a
 * twelfth and thirteenth string saying what two shipped strings already say, in
 * eleven languages (hard-won law 5).
 *
 * ⚠ **B14 RULE 15 IS NOT BREACHED BY A TEXT GLYPH.** Rule 15 puts SVG icons in
 * `components/icons.tsx` and forbids hand-drawing one here; this is the
 * character the kit itself uses for this exact control, and reaching for
 * `ChevronDownIcon` would have made the disclosure look unlike the identical
 * control one component away.
 *
 * ⚠ **NAMED BY ITS ROW, NEVER BY ITS FUNCTION.** Twelve buttons all called
 * *Expand* are unusable without a mouse — `DataTable`'s own note. The group's
 * label is the name, so a screen-reader user hears *"Expand 2026-09-01"*.
 * `aria-expanded` carries the STATE, so the name does not have to.
 */
export function GroupDisclosure(props: {
  open: boolean;
  /** The group's own label — what a person calls this row. */
  label: string;
  onToggle: () => void;
  t: Translator;
}) {
  const key = props.open ? "table.expand.rowCollapse" : "table.expand.row";
  const name = props.t(key, { row: props.label });
  return (
    <button
      type="button"
      onClick={props.onToggle}
      aria-expanded={props.open}
      aria-label={name}
      title={name}
      data-group-disclosure={props.open ? "open" : "closed"}
      className="inline-flex h-4 w-4 shrink-0 items-center justify-center text-neutral-600 hover:text-text"
    >
      <span aria-hidden="true">{props.open ? "▾" : "▸"}</span>
    </button>
  );
}

/** A group row's label cell — what the group IS, and how many rows it covers. */
export function GroupLabelCell(props: {
  row: ReportGroupRow;
  /** The tenant-relative viewer address this report is already at. */
  reportHref: string;
  /** The screen's current URL search, which the drill-through amends. */
  search: URLSearchParams;
  /**
   * `P2.24`. REQUIRED rather than optional, and that is deliberate: an
   * optional prop nothing passes is dead UI and is the defect hard-won law 2
   * is named for. `expandable` false draws a SPACER, never a disabled control.
   */
  expandable: boolean;
  open: boolean;
  onToggle: () => void;
  t: Translator;
}) {
  const label = String(props.row.value ?? props.t("reports.subtotal.blank"));
  // ⚠ **B14 RULE 33.** The count is a FACT in three words — *"19 rows"* — and
  // WHY a subtotal can or cannot be opened is RATIONALE, which is zero words
  // on screen. It lives in this docstring and in `DEF-REP-6871`.
  const count = props.t("reports.subtotal.rows", { count: props.row.rows });
  const indent = { paddingLeft: `${props.row.level * 16}px` };
  // ⚠ **A SPACER, NOT A DISABLED CONTROL** (`P2.24`). A group with nothing
  // beneath it gets no button at all — hard-won law 2's mirror — but the label
  // column still has to line up with its siblings, so the gap keeps its width.
  // `aria-hidden` so the count of controls a screen-reader reports is the count
  // of controls there are.
  const disclosure = props.expandable ? (
    <GroupDisclosure open={props.open} label={label} onToggle={props.onToggle} t={props.t} />
  ) : (
    <span aria-hidden="true" className="inline-block h-4 w-4 shrink-0" />
  );
  if (props.row.filters === null) {
    return (
      <span className="inline-flex items-baseline gap-2 font-semibold" style={indent}>
        {disclosure}
        <span>{label}</span>
        <span className="text-xs font-normal text-neutral-600">{count}</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-baseline gap-2 font-semibold" style={indent}>
      {disclosure}
      <Link
        to={`${props.reportHref}?${drillSearch(props.row.filters, props.search).toString()}`}
        className="text-accent underline-offset-2 hover:underline"
        data-drill-through={props.row.dimension}
      >
        {label}
      </Link>
      <span className="text-xs font-normal text-neutral-600">{count}</span>
    </span>
  );
}

/** A group row's cell under a MEASURE column — its subtotal, or the refusal. */
export function GroupSubtotalCell(props: {
  total: ReportTotal | undefined;
  currency: string | null;
  t: Translator;
  renderMoney: (amount: string) => JSX.Element;
}) {
  if (props.total === undefined || props.total === null) return null;
  // ⚠ **THE REFUSAL IS THE SIBLING'S AND IS FED, NEVER BYPASSED.** A subtotal
  // that cannot lawfully sum shows an em-dash AND its reason — §7.2.2 p85, and
  // `showReason` defaults to true here because a group row has no footer
  // sentence to hang the reason on.
  if (isRefusedTotal(props.total)) {
    return <RefusedTotalCell total={props.total} t={props.t} />;
  }
  return props.renderMoney(String(props.total));
}

/**
 * The URL a subtotal opens: THIS report, the group's filters applied, ungrouped.
 *
 * ⚠ **`group_by` IS REMOVED AND `page` IS RESET, AND BOTH ARE THE POINT.**
 * Drilling means *show me the facts behind this number*; carrying the grouping
 * through would open the same subtotal again, and carrying page 4 of the
 * grouped view would open page 4 of a shorter report — a blank screen under a
 * chip naming a group with rows in it.
 *
 * ⚠ **EVERY OTHER PARAMETER SURVIVES.** The clerk's date window, their search
 * and their sort are the question they were already asking; a drill-through
 * that silently widened the window would open rows the subtotal never counted,
 * which is the same fault as opening too few.
 *
 * A pure function, exported, so the address can be asserted without mounting a
 * router — and asserted BY ADDRESS, which is what hard-won law 2's fixture
 * lesson asks for.
 */
export function drillSearch(
  filters: Record<string, string | number>,
  current: URLSearchParams,
): URLSearchParams {
  const next = new URLSearchParams(current);
  next.delete("group_by");
  next.delete("page");
  for (const [name, value] of Object.entries(filters)) {
    // `f.<name>` is BR-SHL-011's URL grammar for a list filter, which is what
    // `paramsFrom` reads back on the way in. Writing a bare `name` here would
    // round-trip to nothing and the drill would open the unfiltered report —
    // the exact failure this whole component exists to prevent, one layer up.
    next.set(`f.${name}`, String(value));
  }
  return next;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 P2.18 (05-prototype/09 Reports Build Brief.pdf p12, read as an image per B14 rule 42)
// screens: 2·1 group rows
// generated: 2026-09-27 by lane REP-P2-TAIL
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST — reportGroupRow.dom.test.tsx was shown red before this file existed (the viewer rendered a group row as a line of empty cells)
// exceptions: (1) a group row is an ordinary row rather than a spanning band — reasoning in the docstring, and it also avoids touching the kit's pinned baseline · (2) NO drill-through is rendered where the server sends `filters: null`, which is 44 of 71 dataset/dimension pairs today (DEF-REP-6871) — an absence, never a disabled control
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
