// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-006 · US-SHL-007 (EP-SHL-02 §Stories)  Screens: every list screen (S14, S15, S17, S25, S30, S33, S34, S37, S45, S49, S108, …)
// Change:   CS-40 (CR-059 §0d.2) — *"sets 1–31 August and the list, its count and its total all narrow, and the range survives a refresh"*
// Defect:   DEF-3504 — PO, walking all four Record payments tabs: *"I cannot filter payment by date"*; the server and the API client had all four date filters, `TableFilterConfig` had no date kind
// Rules:    BR-SHL-010 (capability-row config) · BR-SHL-011 (URL grammar + fallback law) · BR-SHL-023 / BR-SHL-034 (one date-formatting path) · IS-8 (tenant regional format)
// ───────────────────────────────────────────────────────
// FE-02/FE-03 shared contract (B13 §1): the capability-row config and the typed
// request-state object that DataTable and FilterBar both speak. BR-SHL-011's URL
// grammar (q / sort / dir / page / per / f.<name>) lives here ONCE — a consuming
// screen serializes this state into its URL and its A11 list request with these
// helpers, never with ad-hoc param code.
import type { ReactNode } from "react";

// TYPE-ONLY, and that is the whole reason this import is allowed to exist here.
// `RegionalDateFormat` is DateCell's, because DateCell is the one place that
// knows what a tenant's date format can be (BR-SHL-023 / BR-SHL-034). A VALUE
// import would drag `@/i18n` — DateCell's own import — into every module that
// touches a table config, which is most of the app; `import type` is erased at
// compile time and adds no runtime edge at all.
import type { RegionalDateFormat } from "./DateCell";
// `DEF-LED-10071` — the period arithmetic. `periodWindow` imports nothing from
// this file, so the edge points one way and no cycle forms.
import { periodRefusal, periodWindow } from "./periodWindow";
import type { PeriodChoice, PeriodMonth } from "./periodWindow";

// IS-2 (as amended 2026-08-09, API batch Lane C): page-size options on screen
// are 50/100/200/500/1000, default 50. (EP-SHL-02's TC text still shows the
// superseded 25/50/100 set — the amended standard governs.)
export const PAGE_SIZES = [50, 100, 200, 500, 1000] as const;
export type PageSize = (typeof PAGE_SIZES)[number];
export const DEFAULT_PAGE_SIZE: PageSize = 50;

export type SortDirection = "asc" | "desc";

// The whole framework state in BR-SHL-011's vocabulary. The consumer serializes
// it (serializeTableParams) into its URL so views are shareable/bookmarkable,
// and into its list-endpoint query per A11. The server applies a stable
// secondary sort by id behind the single user-chosen column (IS-2) — the
// request carries only `sort`/`dir`.
export interface TableRequestState {
  q: string; // IS-3 per-list search text; "" = no search
  sort: string; // sorted column key
  dir: SortDirection;
  page: number; // 1-based
  per: PageSize;
  filters: Record<string, string>; // IS-4 declared filters only, AND-combined server-side
}

export interface TableColumnConfig<Row> {
  key: string;
  // Header copy, pre-translated by the consuming screen from ITS catalog keys
  // (IS-8 — the framework never hardcodes a screen's column names).
  label: string;
  sortable?: boolean; // the capability-matrix row's "Sortable" set
  /**
   * `DEF-MET-10164` — the server sort name this column's header sends, when it
   * is NOT the column's own key. Two columns that order by one fact share one
   * sort: **Created** (key `created`) and **Age** (key `age`, `sortKey:
   * "created"`) both send `sort=created`, because an age is only the distance
   * from that stamp to today. Both headers then show as sorted. Absent = the
   * key, which is every column before this field.
   */
  sortKey?: string;
  identity?: boolean; // BR-SHL-013: the identity column can never be hidden
  /**
   * **THIS COLUMN CANNOT BE HIDDEN EITHER — for a reason that is not identity.**
   *
   * `identity` already locks ONE column and there can only be one of it
   * (`DataTable` finds it with `.find`). A screen sometimes has others that a
   * clerk must not be able to remove: on `CON-01` the Product Owner ruled ten
   * columns and named the three that may be hidden — Environment, Where and Why
   * — so the other seven are locked, because a connector list with no State or
   * no Actions is not a shorter list, it is a different screen.
   *
   * ⚠ **IT LOCKS THE TOGGLE, IT DOES NOT HIDE THE ROW FROM THE `▦` PANEL.**
   * `ColumnChooser` already draws a locked item as a disabled checkbox reading
   * *Always shown*, which is the honest presentation: the clerk can see the
   * column exists and learn that it stays. Dropping it from the panel entirely
   * would make the list of columns disagree with the table.
   *
   * ⚠ **AND IT MUST BE HONOURED IN BOTH PLACES OR IT IS WORSE THAN ABSENT.**
   * `toggleColumnVisible` is what a keyboard or a stale stored preference goes
   * through; the disabled checkbox is only what a mouse sees. A flag enforced
   * in the UI and not in the reducer is a lock that a saved column set from
   * before the flag existed walks straight past.
   *
   * Absent = false, so every table that existed before this field is
   * byte-for-byte unchanged.
   */
  locked?: boolean;
  numeric?: boolean; // right-aligned, tabular numerals (A12 money/number cells)
  /**
   * A short marker on the HEADER — rendered as an ⓘ after the column name, with
   * this string as its accessible name. For a column whose values carry a fact
   * the screen explains elsewhere.
   *
   * ⚠ **IT IS NOT A SECOND PLACE TO WRITE A SENTENCE.** B14 rule 33 puts
   * RATIONALE at zero words on screen; rule 32 puts a stated absence in a
   * `<details>` CLOSED by default. Pass the DISCLOSURE'S OWN SUMMARY here so
   * the marker and the thing it points at read as one, and put the explanation
   * in the disclosure. First used by S30's Status column (billing blueprint
   * entry 01, p007, legend 1 — *"an ⓘ on the Status header where the fact
   * actually bites"*).
   */
  headerNote?: string;
  defaultVisible?: boolean; // default true; the matrix row's default column set
  /**
   * Custom cell renderer slot — MoneyCell/UnitCell/DateCell (FE-11..13) plug in
   * here when they land; default rendering is String(row[key]).
   *
   * ⚠ **A TABLE CELL HOLDS A VALUE, AND A CONTROL HOLDS A LABEL. THE SENTENCE
   * EXPLAINING EITHER GOES IN A TOOLTIP, IN THE OPENED DETAIL, OR IN HELP —
   * NEVER RENDERED INLINE.** Read this before you return prose from here.
   *
   * On 2026-08-30 the Product Owner walked two deployed screens and found the
   * SAME mistake ten times in one sitting: *"why so much text - just show some
   * status"*, *"this is internal not required"*, *"this sentence is too long"*,
   * *"all these long messages are breaking to UI ... just use 3 or 4 wrods"*.
   * Every one of them was an honest, correct, well-intentioned sentence
   * rendered inside a cell.
   *
   * The reason it keeps happening is that nothing here stops it. A sentence in
   * a cell sets the height of its WHOLE ROW and wraps at whatever width the
   * column happens to have, so one 95-character explanation on twelve rows
   * turns a scannable list into a wall — and no check in this repo can see it,
   * because jsdom performs no layout and every source-reading gate passes over
   * a `<p>` exactly as it passes over a number. It is found by a person
   * looking at the screen, which is the most expensive way to find anything.
   *
   * **Keep the fact, lose the paragraph.** Three or four words in the cell, the
   * whole sentence on `title`, and the full explanation on the page the row
   * opens. That is not a summary that loses information — every word stays in
   * the DOM and stays reachable by a screen reader; what changes is how much of
   * the row it is allowed to take.
   */
  cell?: (row: Row) => ReactNode;
  /**
   * `DEF-WRK-9689` — a CONTROL in the column's head in place of its label (the
   * select column's *Select all* box). `label` still names the column in the
   * `▦` panel and stays the accessible name a host should give the control.
   * Absent = the label, which is every column before this field.
   */
  header?: () => ReactNode;
}

/**
 * CS-40 / DEF-3504 — THE SECOND KIND OF FILTER: A DATE RANGE.
 *
 * The Product Owner walked the deployed Record payments tabs and said *"I
 * cannot filter payment by date"*. Nothing was missing on the server —
 * `apps/payments/selectors.py` matches `posted_from`, `posted_to`,
 * `cleared_from` and `cleared_to`, and `api/endpoints.ts` has declared all four
 * since `PAYMENT_FILTERS` was written. The single missing piece was here:
 * `TableFilterConfig` was `{name, label, options}` and the shared bar could
 * draw an option list and nothing else, so the payments screen declared the
 * four option lists it COULD draw and stated the absence of the other two in
 * plain English on the tab. Four other lists carry the same debt.
 *
 * ⚠ **TWO PARAM NAMES, NOT ONE, AND THAT IS WHY THIS IS A DESCRIPTOR RATHER
 * THAN A `kind` STRING.** A range is one control and one chip to a clerk, and
 * TWO `f.<name>` params on the wire — which is exactly what the server already
 * accepts and exactly what BR-SHL-011's grammar already says. So NOTHING moves
 * on the API: no new param shape, no array value, no `from..to` encoding to
 * parse on either side. `TableRequestState.filters` stays
 * `Record<string, string>` and each end is an ordinary entry in it, keyed by
 * its own server param name. The group's `name` is the CHIP's identity and a
 * React key; it is never a URL param when `dateRange` is present.
 *
 * ⚠ **`dateFormat` IS REQUIRED HERE ON PURPOSE.** IS-8 says a date renders in
 * the TENANT's regional format, and the native `<input type="date">` renders in
 * the BROWSER's — so the chip is the only place a tenant ever sees theirs, and
 * a range whose chip could not be formatted would be a control that says
 * nothing about what it applied. Making it required means a screen cannot
 * declare a range and forget it: the failure is a red typecheck at the
 * declaration, not a wrong-looking date on a deployed screen. `dateRangeFilter`
 * below is the one-line way to build one.
 */
export interface TableFilterDateRange {
  /** The `f.<name>` param for the START of the range, e.g. `posted_from`. */
  from: string;
  /** The `f.<name>` param for the END of the range, e.g. `posted_to`. */
  to: string;
  /** IS-8 tenant Regional date format — what the CHIP renders in. */
  dateFormat: RegionalDateFormat;
}

/**
 * `DEF-LED-10071` J3 — a PERIOD: a quick choice (*Last 30 days*, …) or Custom
 * From/To, drawn by the shared `PeriodPicker` inside the `+ Filter` panel and
 * shown as ONE chip (*Period: Last 30 days ✕*).
 *
 * THREE `f.<name>` params, all ordinary entries in `TableRequestState.filters`:
 * the choice and the two ends it resolves to. A quick choice is RE-COUNTED
 * from `today` whenever a link is opened, so *Last 30 days* means the last
 * thirty days on the day it is read; Custom keeps the dates it carries.
 *
 * `today` is the UTILITY's business date, supplied by the screen (BR-TEN-043)
 * — this descriptor never reads a clock.
 */
export interface TableFilterPeriod {
  /** The `f.<name>` param holding the quick choice, e.g. `period`. */
  choice: string;
  /** The `f.<name>` param holding the resolved START, e.g. `period_from`. */
  from: string;
  /** The `f.<name>` param holding the resolved END, e.g. `period_to`. */
  to: string;
  choices: readonly PeriodChoice[];
  today: string;
  month?: PeriodMonth | null;
  /** IS-8 tenant Regional date format — what the boxes and the chip render in. */
  dateFormat: RegionalDateFormat;
}

export interface TableFilterConfig {
  name: string; // the `f.<name>` URL param name (BR-SHL-011)
  label: string; // pre-translated by the consuming screen
  options: { value: string; label: string }[];
  /**
   * `DEF-WRK-9582` — a TWO-LEVEL list (job type › sub-type, BR-WRK-058), keyed
   * by option VALUE: `1` is a heading that has sub-types (drawn bold; choosing
   * it matches the heading and every sub-type under it — the server's own
   * filter), `2` a sub-type drawn indented under it. A value not named is a
   * flat option. Absent = a flat list, which is every list before this field.
   * (A separate map rather than a key on each option, so the option type every
   * screen already builds is untouched.)
   */
  levels?: Record<string, 1 | 2>;
  /**
   * `DEF-RAT-9803` — how many rows each option would show, keyed by option
   * VALUE, drawn after the option's label INSIDE the `+ Filter` panel only
   * (`Base · 9`); the applied chip reads the label alone (`Kind: Base`). The
   * charge-code list's Kind chips moved into the panel (PO 2026-10-06: *"on
   * list view filter options are showing outside it should be in the filter
   * dropdown"*) and kept their counts. Opt-in, a separate map for the same
   * reason as `levels`: absent draws every existing panel byte for byte.
   */
  counts?: Record<string, number>;
  /**
   * ABSENT = an option list, which is what every filter in the product was
   * until 2026-09-03 and what every existing declaration still is. Present =
   * the two-ended date range above, and `options` is then empty because a
   * range offers none.
   *
   * ⚠ IT IS OPTIONAL ON THE ONE INTERFACE RATHER THAN A DISCRIMINATED UNION,
   * AND THAT IS A DELIBERATE CHOICE WITH A MEASURED REASON. Two screens read
   * `filter.options` off a `TableFilterConfig[]` today —
   * `UnitsListPage.chipFilters` and `TemplateCatalog`'s per-group option fill —
   * and a union whose date member had no `options` would turn both into
   * typecheck errors in files this lane does not own. `options` stays required
   * and always readable; `filter.dateRange !== undefined` narrows just as well.
   */
  dateRange?: TableFilterDateRange;
  /** `DEF-LED-10071` — a period (quick choice or Custom); `options` is empty. */
  period?: TableFilterPeriod;
}

/**
 * Build the date-range half of a screen's declared filter set.
 *
 * The screen writes one call instead of remembering that a range declares an
 * empty `options` — and, more usefully, cannot declare one without handing over
 * the tenant's date format, because the argument is required.
 *
 *     dateRangeFilter({
 *       name: "posted",
 *       label: t("payments.filter.posted"),
 *       from: "posted_from",
 *       to: "posted_to",
 *       dateFormat,
 *     })
 */
export function dateRangeFilter(spec: {
  name: string;
  label: string;
  from: string;
  to: string;
  dateFormat: RegionalDateFormat;
}): TableFilterConfig {
  return {
    name: spec.name,
    label: spec.label,
    options: [],
    dateRange: { from: spec.from, to: spec.to, dateFormat: spec.dateFormat },
  };
}

/**
 * The `f.<name>` params ONE declared filter owns — one for an option list, two
 * for a date range.
 *
 * Both `parseTableParams` and `serializeTableParams` walk this rather than
 * reaching for `filter.name` themselves, so the URL grammar for a range is
 * stated ONCE and the two halves of the round trip cannot disagree about it.
 * For an option filter it returns `[filter.name]`, which is byte-for-byte what
 * both functions did before this landed.
 */
export function filterParamNames(filter: TableFilterConfig): string[] {
  if (filter.period !== undefined) {
    return [filter.period.choice, filter.period.from, filter.period.to];
  }
  return filter.dateRange === undefined
    ? [filter.name]
    : [filter.dateRange.from, filter.dateRange.to];
}

/**
 * **OQ-306 CLOSED — THE SERVICE FILTER TAKES SEVERAL VALUES (PO 2026-10-02,
 * verbatim: *"Allow several services at once."*).** Shown: a clerk reviewing
 * Water and Sewer schedules together. A row matches when its service is ANY of
 * those picked; different dimensions still AND together (IS-4).
 *
 * ⚠ **ONE LIST, KEYED BY THE FILTER'S NAME, AND THAT IS WHY NO SCREEN OPTS
 * IN.** The ruling reaches *every list whose + Filter offers Service*, and every
 * one of them declares its service dimension as `service`. A per-screen
 * `multi: true` would be twelve places to forget it (the thirteenth list is the
 * one that ships single-select); a name here is one.
 *
 * ⚠ **THE WIRE STAYS A STRING.** Several values travel as ONE comma-joined
 * value — `f.service=water,sewer` — so `TableRequestState.filters` stays
 * `Record<string, string>`, the URL round trip is unchanged, and the server
 * splits it in one place (`core/pagination.py` `filter_values`). Service codes
 * never contain a comma.
 */
export const MULTI_SELECT_FILTER_NAMES: readonly string[] = ["service"];
export const MULTI_VALUE_SEPARATOR = ",";

export function isMultiSelectFilter(name: string): boolean {
  return MULTI_SELECT_FILTER_NAMES.includes(name);
}

/**
 * The values one applied filter holds, in order: `"water,sewer"` →
 * `["water", "sewer"]`. A single-select filter's value is returned whole, so a
 * value that happens to contain a comma is never split on a list that does not
 * multi-select. `undefined` / `""` → `[]`.
 */
export function filterValueList(name: string, value: string | undefined): string[] {
  if (value === undefined || value === "") {
    return [];
  }
  if (!isMultiSelectFilter(name)) {
    return [value];
  }
  const out: string[] = [];
  for (const piece of value.split(MULTI_VALUE_SEPARATOR)) {
    const one = piece.trim();
    if (one !== "" && !out.includes(one)) {
      out.push(one);
    }
  }
  return out;
}

const DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

/**
 * Is this string a real calendar day, `YYYY-MM-DD`?
 *
 * ⚠ **PURE ARITHMETIC, NO `Date` AT ALL, AND THAT IS THE POINT.** DateCell's
 * own law is that a calendar date never round-trips through a `Date`: parsing
 * `2026-08-25` as UTC midnight and reading it back in a zone west of that shows
 * the 24th. Validation has the same exposure as formatting, so it takes the
 * same precaution — the leap rule and a twelve-entry table are the whole of it,
 * and there is no clock anywhere near this function.
 *
 * A shape check alone is not enough: `^\d{4}-\d{2}-\d{2}$` accepts `2026-02-31`
 * and `2026-13-01`, and both would go to the server as a filter that matches
 * nothing while the chip beside the list reads like a date.
 */
export function isCalendarDate(value: string): boolean {
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (parts === null) {
    return false;
  }
  const [, yearText, monthText, dayText] = parts;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (month < 1 || month > 12 || day < 1) {
    return false;
  }
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const longest = month === 2 && leap ? 29 : DAYS_IN_MONTH[month - 1];
  return day <= longest;
}

// One capability-matrix row (B9), declared by the consuming screen's epic.
// BR-SHL-010: a capability absent here (searchFields, filters, …) is not
// rendered — the framework never invents one.
export interface TableConfig<Row> {
  /** e.g. "S17" — keys the `table.<screen>.columns` preference (BR-SHL-013).
   *
   * ⚠ **THIS FIELD WAS DECORATIVE UNTIL 2026-08-24 (DEF-647).** Its only
   * documented purpose was to key that preference, and no code anywhere read
   * it for that: there was no endpoint and no caller, so the column chooser
   * reset to the declared defaults on every remount. It is LOAD-BEARING now —
   * `columnPreferenceKey` below turns it into the stored key, and DataTable
   * reads that key on mount and writes it on change. Two lists that share a
   * `screenId` share one saved column set, which is why the screens with two
   * tables give each its own suffix (`SET-05` / `SET-05.cycles`). */
  screenId: string;
  columns: TableColumnConfig<Row>[];
  getRowId: (row: Row) => string;
  searchFields?: string[]; // IS-3 declared search fields; absent = no search box
  /** B14 rule 19 — THIS LIST'S OWN SEARCH PROMPT, as an i18n KEY (DEF-510).
   *
   * Absent = `table.search.placeholder`, "Search this list", which is what every
   * list in the product said until 2026-08-22 — so adding this field changed no
   * screen, and a screen opts in with one line.
   *
   * ⚠ IT IS A KEY, NOT A SENTENCE. The copy stays in the catalogues where the
   * other ten languages can reach it; a literal here would ship English to a
   * `fr-FR` tenant and no gate reads a prop for translatability.
   *
   * Rule 19 is "Search {entities}…" PER MODULE, and r10 writes three different
   * sentences on one page — `Search address…` on PRM-01, `Search premises,
   * units, meters…` on PRM-01U, `Search runs, files, users…` on PRM-04 — each
   * naming WHAT the search matches. Ours told the user nothing: the premises
   * search matches address, premise number, owner and city, and there was no
   * way to learn that. The screens still on the default are listed in DEF-510's
   * register row with the r10 sentence each one is owed. */
  searchPlaceholder?: string;
  filters?: TableFilterConfig[]; // IS-4 declared filters; absent = no filters
  defaultSort: { sort: string; dir: SortDirection };
  /** CR-029 RC-W3-T0 — EXPANDABLE ROWS. What one row opens into.
   *
   * Absent = the capability does not exist on this list, exactly as
   * BR-SHL-010 requires: no expander column, no per-row control, no Expand
   * all, and byte-identical markup to a list that never heard of the feature
   * (asserted against `__fixtures__/DataTable.baseline.html`).
   *
   * ⚠ IT LIVES ON THE CONFIG, NOT ON `DataTableProps`, and that is the same
   * decision `cell` already embodies: the capability-matrix row is where a
   * screen DECLARES what its table can do, and the framework renders only
   * what is declared. `filterBarSlot`/`downloadSlot` are props because they
   * are composed ELEMENTS the consumer hands over; this is a per-row render
   * function of the row type, which is `cell`'s shape and belongs beside it.
   *
   * ⚠ THE CONTENT IS TABULAR — that is what it is. SET-06.3 opens a premises
   * row into its unit/meter sub-table, so a consumer returns a
   * `<table className="data-table">`, which keeps B14 rule 20's ONE table type
   * (body 13.5px / header 12px) inside the disclosure instead of inventing a
   * second one. The kit supplies the row and the full-width cell; it does not
   * dictate the columns, because the sub-table's columns are the consuming
   * screen's business.
   *
   * ⚠ AND IT IS A SECOND CAPABILITY ON THE ONE TABLE, NOT A SECOND TABLE
   * (B8 · B14 rule 20). A `DataTableExpandable` would be the fifth place row
   * hover, cell padding, the sort control and the pager each get an opinion —
   * DEF-348's shape one component larger. */
  renderExpanded?: (row: Row) => ReactNode;
  /** **THE WHOLE ROW IS THE TARGET — where a screen declares one.**
   *
   * Absent = the capability does not exist on this list, exactly as
   * BR-SHL-010 requires and exactly as `renderExpanded` above already works:
   * no handler, no cursor change, no `data-row-href`, and byte-identical
   * markup to a list that never heard of the feature. Every existing list is
   * therefore unchanged by this field existing.
   *
   * ⚠ **IT IS A CONVENIENCE OVER A REAL LINK, NEVER A REPLACEMENT FOR ONE.**
   * A `<tr>` is not focusable and cannot be operated by a keyboard, so a row
   * whose only affordance is a row click is unreachable without a mouse — the
   * clickable-`<div>` defect wearing a table's clothes. The identity cell's
   * `<a>` keeps working and keeps being the thing Tab reaches; this widens the
   * MOUSE target to the rest of the row. A list that declares `rowHref` and has
   * no identity link is the shape to refuse, not to ship.
   *
   * ⚠ **A CLICK THAT LANDS ON SOMETHING INTERACTIVE IS NOT A ROW CLICK.** The
   * handler ignores any event whose target sits inside a link, a button, an
   * input, a label or a `[role]`-bearing element — otherwise the select
   * checkbox, the identity link and every row action would each navigate as
   * well as doing their own job, and a clerk ticking a checkbox would leave the
   * page. Text selection is left alone for the same reason.
   */
  rowHref?: (row: Row) => string | null;
}

export function defaultRequestState<Row>(config: TableConfig<Row>): TableRequestState {
  return {
    q: "",
    sort: config.defaultSort.sort,
    dir: config.defaultSort.dir,
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    filters: {},
  };
}

// BR-SHL-013: the "Reset to default" target — the matrix row's default set.
export function defaultVisibleColumns<Row>(config: TableConfig<Row>): string[] {
  return config.columns.filter((c) => c.defaultVisible !== false).map((c) => c.key);
}

// ── The stored column preference (BR-SHL-013 / BR-SHL-024 · DEF-647) ───────
// BR-SHL-027: "ALL user preferences (column sets, sidebar state, saved
// mappings) persist SERVER-SIDE in user_preferences — never localStorage-only
// (resets otherwise)." These two helpers are the pure halves of that round
// trip: the KEY it is stored under and the SANITISER that turns whatever came
// back into a visible-column list. Both live here beside `defaultVisibleColumns`
// because the fallback they return IS that function.

/** BR-SHL-024's key grammar, as the server enforces it (`apps/tenancy/
 *  preferences.py`): a namespace then one or more `[A-Za-z0-9_-]` segments,
 *  ≤128 characters. Mirrored here so a screen whose `screenId` cannot form a
 *  lawful key is skipped SILENTLY rather than answered with a 422 on every
 *  column click. */
const PREFERENCE_KEY_PATTERN = /^table(\.[A-Za-z0-9_-]+)+$/;
const PREFERENCE_KEY_MAX_CHARS = 128;

/**
 * `table.<screen>.columns` — the key BR-SHL-013 and BR-SHL-027 both name.
 *
 * Returns `null` when the screen's id cannot form a lawful key (empty, or
 * carrying a character the grammar excludes). Null means "this list does not
 * persist": the chooser still works for the session, exactly as it did before
 * this landed, and nothing 422s in a loop. A null here is worth a look at the
 * screen's `screenId`, not a silent shrug — see `columnsFromPreference`.
 */
export function columnPreferenceKey<Row>(config: TableConfig<Row>): string | null {
  const key = `table.${config.screenId}.columns`;
  if (key.length > PREFERENCE_KEY_MAX_CHARS || !PREFERENCE_KEY_PATTERN.test(key)) {
    return null;
  }
  return key;
}

/**
 * Whatever came back from the store → the ordered visible-column list to use.
 *
 * THE THREE STATES THIS HAS TO GET RIGHT, and each is a real one:
 *
 *  1. **Nothing stored yet** (`null`/absent, the answer for every user until
 *     they first choose) → the config's declared defaults. BR-SHL-024:
 *     "unknown keys read as absent (callers fall back to defaults)".
 *  2. **A stored key that no longer exists** — a column removed from the
 *     capability row since the user saved. That key is IGNORED, not rendered
 *     and not fatal: a released column rename must never break the list of
 *     everyone who had saved a view. (DataTable filters again on render for
 *     the same reason; this is the same law applied at the boundary.)
 *  3. **A stored value that is not a list of strings at all** — hand-edited,
 *     or a key collision with another feature → defaults. Never a crash: a
 *     preference is a convenience and a broken one must not cost the user the
 *     screen.
 *
 * ⚠ It deliberately does NOT re-insert the identity column. BR-SHL-013's
 * "identity column can never be hidden" is DataTable's own invariant, applied
 * on every render to the controlled and uncontrolled paths alike; duplicating
 * it here would make the two implementations able to disagree.
 */
export function columnsFromPreference<Row>(stored: unknown, config: TableConfig<Row>): string[] {
  if (!Array.isArray(stored)) {
    return defaultVisibleColumns(config);
  }
  const known = new Set(config.columns.map((c) => c.key));
  const visible = stored.filter(
    (key): key is string => typeof key === "string" && known.has(key),
  );
  // An array that survives the filter with nothing left (every stored column
  // was removed from the screen) is treated as "no usable preference" rather
  // than as "hide everything" — an empty table has no way back except Reset.
  return visible.length > 0 ? visible : defaultVisibleColumns(config);
}

export function isPageSize(value: number): value is PageSize {
  return (PAGE_SIZES as readonly number[]).includes(value);
}

/**
 * **A NAMESPACE FOR A TABLE THAT SHARES ITS PAGE WITH ANOTHER TABLE.**
 *
 * ⚠ **ADDED 2026-09-21 (`DEF-CUS-6099`) AND IT IS OPTIONAL, SO NOTHING
 * EXISTING MOVES.** Absent — which is every caller that has ever called these
 * two — the params are `q`, `sort`, `dir`, `page`, `per` and `f.<name>`,
 * byte for byte as before.
 *
 * ⚠ **WHY A PREFIX RATHER THAN JUST LETTING BOTH TABLES USE THE BARE NAMES.**
 * The Accounts register draws eight tabs at ONE address and each tab is its own
 * table. Sharing the bare names is what `DEF-664` is about from the other
 * side: switching from the Accounts tab to New connects would carry `q=smith`
 * and `sort=name` across, so the second tab opens on page 3 of a search
 * somebody typed into the first. `NewConnectsTab`'s answer was to read NO url
 * at all — which cost the other half, `DEF-CUS-6099`: the filter is lost on
 * reload and cannot be pasted to a colleague, while the sibling tab on the same
 * page does both. A namespace gives each tab its own room in one query string.
 */
export function prefixed(prefix: string | undefined, name: string): string {
  return prefix === undefined || prefix === "" ? name : `${prefix}${name}`;
}

// BR-SHL-011: unknown params are ignored; invalid values fall back to defaults
// or clamp — NEVER an error screen.
export function parseTableParams<Row>(
  params: URLSearchParams,
  config: TableConfig<Row>,
  prefix?: string,
): TableRequestState {
  const key = (name: string) => prefixed(prefix, name);
  const state = defaultRequestState(config);
  state.q = params.get(key("q")) ?? "";
  // BR-SHL-011: a sort field outside the screen's sortable set falls back to
  // the screen's default sort (US-SHL-006 TC-5).
  const sort = params.get(key("sort"));
  if (
    sort !== null &&
    config.columns.some((c) => c.sortable === true && (c.sortKey ?? c.key) === sort)
  ) {
    state.sort = sort;
    const dir = params.get(key("dir"));
    state.dir = dir === "asc" || dir === "desc" ? dir : "asc";
  }
  const page = Number(params.get(key("page")));
  if (Number.isInteger(page) && page >= 1) {
    // An out-of-range page clamps to the last REAL page via clampPage once the
    // server total is known — parse time cannot know it yet.
    state.page = page;
  }
  const per = Number(params.get(key("per")));
  if (isPageSize(per)) {
    state.per = per;
  }
  // BR-SHL-011: only DECLARED filters restore; `f.<unknown>` is ignored
  // (US-SHL-007 TC-5), and an absent value never creates an entry.
  for (const filter of config.filters ?? []) {
    if (filter.period !== undefined) {
      restorePeriod(filter.period, (name) => params.get(key(`f.${name}`)), state.filters);
      continue;
    }
    const dated = filter.dateRange !== undefined;
    for (const param of filterParamNames(filter)) {
      const value = params.get(key(`f.${param}`));
      if (value === null || value === "") {
        continue;
      }
      // ⚠ CS-40 — A DATE END THAT IS NOT A DATE IS DROPPED, SILENTLY, HERE.
      // BR-SHL-011 already rules that an invalid value falls back and never
      // reaches an error screen, and this is the same rule at the same
      // boundary: a hand-edited or truncated `f.posted_from=banana` would
      // otherwise ride to the server, which answers it with everything or with
      // a 422 — and either way the chip beside the list would claim a range
      // the rows do not obey. Dropping it means the list is honestly
      // unfiltered on that end and the chip says so, which is the whole
      // complaint behind DEF-3504 read the other way round.
      if (dated && !isCalendarDate(value)) {
        continue;
      }
      state.filters[param] = value;
    }
  }
  return state;
}

/**
 * `DEF-LED-10071` J5 — a period restores from the URL only when it is one a
 * clerk could have chosen: a known quick choice (re-counted from `today`), or
 * Custom with two real dates that neither cross nor end after today. Anything
 * else is dropped WHOLE, so a chip never claims a window the rows do not obey
 * (BR-SHL-011: an invalid value falls back, never an error screen).
 */
function restorePeriod(
  period: TableFilterPeriod,
  read: (name: string) => string | null,
  into: Record<string, string>,
): void {
  const choice = period.choices.find((one) => one === read(period.choice));
  if (choice === undefined) return;
  const window = periodWindow(choice, period.today, period.month) ?? {
    from: read(period.from) ?? "",
    to: read(period.to) ?? "",
  };
  if (periodRefusal(window.from, window.to, period.today) !== null) return;
  into[period.choice] = choice;
  into[period.from] = window.from;
  into[period.to] = window.to;
}

export function serializeTableParams<Row>(
  state: TableRequestState,
  config: TableConfig<Row>,
  prefix?: string,
): URLSearchParams {
  const key = (name: string) => prefixed(prefix, name);
  const params = new URLSearchParams();
  if (state.q !== "") {
    params.set(key("q"), state.q);
  }
  // sort/dir always serialize — US-SHL-006 TC-2 expects the URL to carry them
  // even when they match the screen default; defaults for q/page/per are
  // omitted as noise (parse restores them).
  params.set(key("sort"), state.sort);
  params.set(key("dir"), state.dir);
  if (state.page > 1) {
    params.set(key("page"), String(state.page));
  }
  if (state.per !== DEFAULT_PAGE_SIZE) {
    params.set(key("per"), String(state.per));
  }
  for (const filter of config.filters ?? []) {
    for (const param of filterParamNames(filter)) {
      const value = state.filters[param];
      if (value !== undefined) {
        params.set(key(`f.${param}`), value);
      }
    }
  }
  return params;
}

export function pageCount(totalRows: number, per: PageSize): number {
  return Math.max(1, Math.ceil(totalRows / per));
}

// BR-SHL-011: an out-of-range page CLAMPS to the last real page (US-SHL-006
// TC-5 — `?page=999` on 60 rows lands on the final page, no error).
export function clampPage(page: number, totalRows: number, per: PageSize): number {
  return Math.min(Math.max(1, page), pageCount(totalRows, per));
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-006@e879338 (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-09-03 by the CS-40 lane (DEF-3504 — `TableFilterConfig` gains an optional `dateRange` descriptor, `dateRangeFilter` builds one, `filterParamNames` is the single statement of which `f.` params a filter owns, and `isCalendarDate` drops a URL date end that is not a real day; the option-list path is byte-identical and asserted so against two committed fixtures)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ tsc✔ eslint✔ vitest 31/31✔ (5 TC todo this packet — browser/journey/backend scope) · [CS-40 2026-09-03] tsc✔ eslint✔ g13✔ g15✔ g27✔ g31✔ g37✔ g43✔ g44✔ g45✔ vitest src/components+src/styles 36 files / 432 passed / 30 todo
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
