// ── Trace ──────────────────────────────────────────────
// Story:    US-REP-001 (S44 report library) · US-REP-002 (S46 viewer) ·
//           US-REP-003 (IS-11 downloads) · US-REP-005 · US-REP-006 · US-REP-007
//           Screens: S44 · S46
// Rules:    BR-REP-001 (every money report names its date basis) · BR-REP-002
//           (read-models) · BR-REP-006 (LIVE vocabularies) · BR-REP-018 (IS-11
//           downloads) · BR-REP-024 (a figure that cannot be computed is null
//           WITH a reason — never 0, never the string "null") · BR-SHL-011
//           (the list/URL grammar) · CLAUDE.md rule 2 (money is a decimal
//           STRING beside its CHAR(3)) · rule 3 (a quantity with its unit)
// ───────────────────────────────────────────────────────
// The report-centre wrappers, in their own module beside `bankRecEndpoints.ts`
// and `billingOpsEndpoints.ts` — the precedent this follows.
//
// ⚠ **EVERY MONEY FIELD HERE IS `string | null`, AND THE NULL IS LOAD-BEARING.**
// A production defect on 2026-08-16 rendered the literal text `null USD` on a
// tile, which is what a `${amount} ${currency}` template does with an absent
// figure. So: an amount that could not be computed arrives as `null` beside a
// `reason_code`, and the screen renders the REASON. Typing these as `string`
// would let a screen print a plausible 0.00 for a figure nobody computed, which
// is BR-REP-024's whole subject.
import { api } from "./client";
import type { ApiClient, ApiResponse } from "./client";

/** A 2xx with no body where the contract promises one is a server bug (B12 r1).
 *  Restated here rather than imported, exactly as `bankRecEndpoints.ts` does,
 *  so this file adds no coupling to a 7,900-line module several lanes edit. */
function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

// ── The S44 catalogue ─────────────────────────────────────────────────────

/** How a card behaves when it is clicked. */
export type ReportCardKind = "viewer" | "route" | "generic" | "absent";

/** `BR-REP-019`'s three, closed. The SCREEN shows two sub-tabs — Standard is
 *  `built_in`, Custom is `mine` and `shared` together — because the PO ruled
 *  origin is not a filter: *"a filter dropdown hides that you can author a
 *  report at all."* The third value is what lets the Custom list grow an Owner
 *  column in Phase 5 without a second read. */
export type ReportOrigin = "built_in" | "mine" | "shared";

export interface ReportCard {
  key: string;
  /** ⚠ **THE NAME THE SERVER RESOLVED, AND THE SCREEN DOES NOT RE-DERIVE IT.**
   *  Until `P1.1` the server sent no title at all and the screen named every
   *  card through `t("reports.card.<key>.name")` — which is why a utility could
   *  never author one: it cannot edit our locale catalogues. Precedence is the
   *  tables' own: `name_override` → `name_i18n[locale]` → `name`. */
  name: string;
  /** True when THIS utility renamed it, so the screen leaves its own catalogue
   *  copy alone. See `ReportLibraryPage.displayName`. */
  name_overridden: boolean;
  /** `report_categories.code` — the group and its sub-group. Never rendered:
   *  B14 rule 31, the NAME is what a person reads. */
  group: string;
  group_name: string;
  sub_group: string | null;
  kind: ReportCardKind;
  origin: ReportOrigin;
  /** The card's eyebrow — the sub-group's NAME, which is what p20 draws. */
  badge: string;
  /** FALSE when this deployment cannot produce the report. Then `reason_code`
   *  is set and the card opens nothing — see US-REP-001 TC-4. */
  available: boolean;
  /** BR-REP-001. `null` on a report that carries no money. */
  basis: string | null;
  /** The drawing's own words — *Posting date*, *Clearing date*, *As at*, *Read
   *  date*. Three different facts map to one basis code and a clerk reads the
   *  label, so the seed keeps it verbatim rather than deriving it. */
  basis_label: string | null;
  reason_code: string | null;
  /** Engineering prose for the log and the tooltip; the SENTENCE a user reads
   *  is the catalogue entry keyed on `reason_code` (TD-16 — the server sends
   *  keys, the UI renders language). */
  reason_detail: string | null;
  /** A1 screen id for a `route` card: S41 · S56 · S59 · S11 · S61. */
  routes_to_screen: string | null;
  service_codes: string[];
  pinned: boolean;
}

/** One catalogue group with its sub-groups, from `report_categories`. */
export interface ReportCatalogueGroup {
  code: string;
  name: string;
  sub_groups: { code: string; name: string }[];
}

export interface ReportVocabularies {
  /** BR-REP-006: the tenant's ENABLED services — never a hardcoded trio. */
  services: { code: string; name: string }[];
  bill_types: string[];
  purposes: string[];
  current_period: {
    start: string;
    end: string;
    fy_label: string | null;
    period: number | null;
  } | null;
  currency: string | null;
  /** Set when the tenant has no fiscal calendar: the viewer then has no default
   *  window and says so rather than substituting a calendar month. */
  period_unavailable_reason: string | null;
}

export interface ReportLibrary {
  /** Only the groups THIS page has cards in — a heading over nothing is
   *  furniture, and after a filter most of six are (1·2B callout ④). */
  groups: ReportCatalogueGroup[];
  /** Every group, for the filter's own dropdown: a filter that offered only
   *  what is already on screen could never be undone. */
  group_options: { code: string; name: string }[];
  /** The CATALOGUE's shape, which `groups` is not — `groups` holds only what
   *  this page draws. The sub-line states the catalogue (p20 callout ①). */
  group_total: number;
  sub_group_total: number;
  cards: ReportCard[];
  /** `available`/`total` describe the CATALOGUE and never the page — p20
   *  callout ①, *"the sub-line states the shape of the catalogue"*. */
  available: number;
  total: number;
  /** How many cards the FILTERS matched, which is what the pager counts. */
  count: number;
  page: number;
  per: number;
  pages: number;
  origin: "standard" | "custom";
  /** BOTH sub-tab counts, so `Custom · 0` reads without being clicked — p20
   *  callout ④, which is the whole reason the strip is in Phase 1. */
  origin_counts: { standard: number; custom: number };
  q: string;
  group: string;
  service: string;
}

export interface ReportLibraryResponse extends ReportLibrary {
  vocabularies: ReportVocabularies;
}

/** What the screen asks for. Every one of these is read SERVER-SIDE (`P1.2`):
 *  a screen that filtered an array it was handed would have to be handed the
 *  whole array, which is the `NFR-3` breach this product already carries in
 *  four places. */
export interface ReportLibraryQuery {
  q?: string;
  group?: string;
  service?: string;
  origin?: "standard" | "custom";
  page?: number;
  per?: number;
}

export async function getReportLibrary(
  client: ApiClient = api,
  query: ReportLibraryQuery = {},
): Promise<ReportLibraryResponse> {
  // Only what was asked for goes on the wire. An empty string is not a filter:
  // `?group=` would be a filter on the empty group, and the server would have
  // to guess which was meant.
  const params: Record<string, string> = {};
  if (query.q) params.q = query.q;
  if (query.group) params.group = query.group;
  if (query.service) params.service = query.service;
  if (query.origin) params.origin = query.origin;
  if (query.page !== undefined) params.page = String(query.page);
  if (query.per !== undefined) params.per = String(query.per);
  return requireData(await client.get<ReportLibraryResponse>("/reports", { query: params }));
}

// ── The S46 viewer ────────────────────────────────────────────────────────

/** One KPI tile. `value` is `null` WITH a `reason_code` whenever the figure
 *  could not be computed (BR-REP-024) — never 0 and never "0.00". */
export interface ReportKpi {
  key: string;
  value: string | number | null;
  /** ⚠ **`"percent"` WAS ALREADY BEING SENT AND WAS NOT IN THIS UNION
   *  (`P6.11`).** `apps/reports/queries.py` has served `kind="percent"` for
   *  R33's `on_time_pct` since the work-orders dataset landed, and this type
   *  admitted only two values — so the wire and the type disagreed, and the
   *  tile fell through to the bare-number branch and printed `91.689630`. The
   *  mismatch was invisible because nothing narrowed on `kind` until a
   *  percent branch was written; `tsc` then named it at once. Hard rule 2:
   *  a percentage is STORED to six and DISPLAYED to two. */
  kind: "money" | "count" | "percent";
  /** A share, a sub-total or another second line. Null when undefined — a
   *  percentage of an empty total is not 0%. */
  detail: string | null;
  /** ⚠ **WHAT `detail` IS, SO THE SCREEN CAN RENDER ITS UNIT** (`P2.13`).
   *  `"share"` = a percentage of this report's own total, drawn `42%`. Absent =
   *  a plain string, which is what every tile but the ageing bands sends.
   *
   *  It exists because the bands sent `"42.0"` and the screen printed `42.0` —
   *  a number with no unit, beside five others, where the drawing reads `42%`. */
  detail_kind?: "share" | "money" | null;
  reason_code: string | null;
}

/** The reason half of an absence, in the shape every gap in this product takes:
 *  a stable machine `code` the SCREEN keys its sentence on. */
export interface ReportGap {
  code: string;
  br_ref: string;
  detail: string;
  wanted_reads?: string[];
  /** ⚠ **HOW MANY ACCOUNTS THIS GAP LEFT OUT** (`CR-179-BRC10`). Present on a
   *  counted gap — the viewer lists those under *Not worked out*. */
  count?: number;
  /** The catalogue key of a counted gap's reason. */
  message_key?: string;
}

/** CLAUDE.md rule 3 — a quantity NEVER arrives without its unit. */
export interface ReportQuantity {
  quantity: string;
  unit: string;
  /**
   * ⚠ **IS THIS FIGURE A READING, OR A COUNT OF THINGS?** (`DEF-REP-7010`).
   *
   * `BR-RAT-090` — a CAPACITY service is billed by a COUNT of the unit's
   * assets, so **`0 cart` means nobody has a cart here** and **`0 kgal` means
   * the meter was read, and read zero.** Two different facts, the same `"0"`
   * on the wire, and the live register printed both on every row: *`0 cart ·
   * 0 connection · 0 kW · 15.2 kgal`* — four figures to find the one measure
   * that had moved.
   *
   * ⚠ **ABSENT MEANS *A READING*, WHICH KEEPS EVERY EXISTING REPORT
   * UNCHANGED.** Only the read model can know which is which; a screen that
   * guessed from the UNIT would be the hand-typed list §12 forbids, and it
   * would be wrong the first time a utility called its carts something else.
   */
  measured?: boolean;
}

export interface ReportRow {
  [column: string]: string | number | boolean | null | string[] | ReportQuantity[];
}

/**
 * ⚠ **A TOTAL THAT WILL NOT CARRY A NUMBER** (`P2.22`).
 *
 * Brief §7.2.2, p85: a balance summed across time, a DSO averaged across
 * routes and two units added together are three sums that produce a confident
 * figure meaning nothing. The server replaces such a figure with THIS, and the
 * only reason it is a shape rather than a `null` is that `null` already means
 * something else on this wire — *"not counted yet"*, the `BR-REP-033` pattern
 * the KPI tiles use, with a different sentence and a different renderer.
 * Rendering two different absences through one branch is how *"we could not
 * read the ledger control total"* comes to say *"balances do not sum across
 * time"*.
 *
 * ⚠ **`value` IS ALWAYS `null` AND NO DIGIT OF THE REFUSED FIGURE IS HERE.** A
 * client that ignores `refused` entirely still cannot print a number.
 */
export interface RefusedTotal {
  value: null;
  /** The em-dash. Sent rather than typed client-side so the file and the
   *  screen cannot disagree about the character. */
  display: string;
  refused: true;
  measure: string;
  /** Keys `reports.totals.<reason_code>` in all eleven catalogues. */
  reason_code: string;
  /** The English, for a catalogue that has not been fanned in yet. */
  reason: string;
  across: string[];
}

export type ReportTotal = string | number | null | RefusedTotal;

/** A narrowing that is a function and not an inline `in` check, because it is
 *  asked in three places and a fourth would eventually get it wrong. */
export function isRefusedTotal(total: ReportTotal): total is RefusedTotal {
  return (
    typeof total === "object" && total !== null && (total as RefusedTotal).refused === true
  );
}

/**
 * A SUBTOTAL ROW, INSERTED BY THE SERVER AT EVERY GROUP LEVEL (`P2.17`).
 *
 * It arrives inside `rows`, flat and in order, because `P2.24` opens and
 * closes a level IN PLACE and a nested payload would make *collapse* a
 * different shape from *expand*.
 */
export interface ReportGroupRow {
  __kind__: "group";
  /** 0, 1 or 2 — `MAX_GROUP_LEVELS` is three. */
  level: number;
  dimension: string;
  value: string | number | null;
  /** What this group IS — the dimension/value pairs that label it. */
  path: { dimension: string; column: string; value: string | number | null }[];
  /**
   * ⚠ **THE FILTERS THAT REPRODUCE THIS GROUP — AND THEY ARE NOT THE `path`**
   * (`DEF-REP-6869`, `P2.18`).
   *
   * `slicers.group_rows()`'s docstring claimed *"the path IS the filter set"*
   * and it is wrong three ways: the path's `dimension` is `consumer_class`
   * where the dataset declares the filter `class`; its `value` is the display
   * label `Residential` where the filter's vocabulary is the code
   * `residential`; and its `column` is the display column. Measured on real
   * PostgreSQL 16: replaying the path returns **30 rows — the WHOLE report,
   * with the parameter silently dropped** — against groups of 11 and 19.
   *
   * ⚠ **`null` MEANS DRAW NO DRILL-THROUGH AT ALL.** `runner.bind` discards an
   * undeclared parameter without complaining, so a guessed filter opens the
   * unfiltered report under a chip naming one group — hard-won law 2's mirror,
   * a control that runs and answers a different question. 44 of the registry's
   * 71 dataset/dimension pairs are in this state today (`DEF-REP-6871`).
   */
  filters: Record<string, string | number> | null;
  /** Keys `reports.drill.<code>`. Present exactly when `filters` is null. */
  drill_unavailable: string | null;
  /** How many FACT rows this subtotal covers — the 412. */
  rows: number;
  /** Its measures, each already through `additivity`, so an unlawful one is a
   *  `RefusedTotal` here exactly as in the footer. */
  subtotals: Record<string, ReportTotal>;
}

/** A narrowing rather than an inline `"__kind__" in row`, because the viewer,
 *  the group row and the totals row each ask it and a fourth would get it
 *  wrong — the reason `isRefusedTotal` is a function too. */
export function isReportGroupRow(row: ReportRow | ReportGroupRow): row is ReportGroupRow {
  return (row as ReportGroupRow).__kind__ === "group";
}

/**
 * WHAT KIND OF THING ONE COLUMN IS, FROM THE DATASET THAT DECLARES IT
 * (`DEF-REP-6902` · `DEF-REP-6903`).
 *
 * ⚠ **WITHOUT THIS THE SCREEN GUESSED, AND IT GUESSED FROM A HAND-TYPED MAP
 * NAMING FIVE REPORTS OUT OF FORTY-SIX.** `MONEY_COLUMNS` in the viewer is
 * that map. Every column it did not name was rendered with `String(...)`, so
 * the trend pack printed `15816.000000` in its footer under a tile reading
 * `$15,816.00` for the same figure, and a meter reading reached a clerk as
 * `46754.000000 kWh`. CLAUDE.md hard rule 2 — money stored to four places, a
 * percentage to six, **both DISPLAY two** — could not be obeyed by a screen
 * that did not know which figures were money.
 *
 * ⚠ **IT IS THE DATASET'S DECLARATION AND NEVER A SNIFF OF THE VALUE.**
 * `"247.87"` and `"684"` are both decimal strings and only one of them wants a
 * currency symbol; the dataset is the one place that knows which.
 *
 * Absent for a column the dataset does not declare — several queries select a
 * derived column — and an absent entry means *render it as text*, which is
 * what the screen did for every column before this existed.
 */
export interface ReportColumnMeta {
  /** `text` · `date` · `money` · `percent` · `quantity` · `count`. */
  type: string;
  /** Present on a `quantity` — CLAUDE.md hard rule 3. */
  unit: string | null;
  /** A quantity whose unit is a SIBLING COLUMN, which is how one row carries
   *  `26.24 kgal` and `684 kWh` at once. */
  unit_from: string | null;
  money_basis: string | null;
  /** The STORED scale — 4 for money, 6 for a percentage. It is what the figure
   *  IS, never how many digits a person reads. */
  scale: number | null;
}

export interface ReportResponse {
  key: string;
  /** ⚠ **WHICH OF THE NINE DATASETS THIS REPORT IS BUILT ON** (`P5.3`).
   *  2·2's panel offers the columns, measures, dimensions and filters the
   *  DATASET declares, so it has to be told which one — and a screen that
   *  derived it from the report key would be a hand-typed map, which is the
   *  thing `P0.7` deleted six of. Optional only because the three ledger-owned
   *  viewers answer through their own read models rather than through the
   *  runner; where it is absent the panel offers nothing rather than guessing. */
  dataset?: string;
  /** ⚠ **THE NAME A PERSON READS, FROM THE ROW** (`DEF-REP-6867`). B14 rule 31
   *  forbids a database id — or a slug — as the visible value of a field, and
   *  a report a utility wrote has its name in `report_definitions.name` and
   *  nowhere else: there is no `reports.card.<key>.name` catalogue entry for a
   *  key we never shipped. Absent on a report whose name IS in the catalogue. */
  name?: string;
  /** ⚠ **WHERE THIS REPORT LIVES, FROM ITS OWN ROW** (`DEF-REP-6863`). 2·2's
   *  *Where it lives* used to read the catalogue card, and `GET /reports`
   *  answers ONE sub-tab — so a report on the Custom sub-tab had no card in
   *  hand and the panel opened with an empty Group. The report knows. */
  group?: string;
  sub_group?: string | null;
  /** BR-REP-001. Required, never optional: a money report without its basis is
   *  a defect by contract, so the type does not let one exist. */
  basis: "posting" | "clearing";
  window: { start?: string; end?: string; as_of?: string };
  currency: string | null;
  columns: string[];
  /**
   * ⚠ **WHICH RECORD THIS PAGE OF MONEY BELONGS TO** (`DEF-REP-7052`).
   *
   * Composed on the server from the SUBJECT's own `head_from`, which has been
   * published since `P2.14` and was read by nothing — so the statement, and
   * the shipped account statement before it, never named the account it was
   * about. Absent on the forty-five reports that are about no particular
   * record, and absent when no record was named; the screen then draws
   * nothing rather than an empty separator.
   *
   * ⚠ **VALUES ONLY, AND NEVER AN ID** (B14 rule 31). Each value is a word a
   * clerk already reads — an account number, a person's name, a premises
   * address, a unit label. `field` is the server's own name for the part and
   * is NOT rendered; it exists so a test can assert which parts arrived.
   *
   * ⚠ **THE SCREEN HOLDS NO TABLE OF WHICH SUBJECT SHOWS WHAT.** A subject
   * added on the server appears here with no front-end change, which is the
   * whole reason the composition is not done in this repository's TSX.
   */
  head?: { subject: string; fields: { field: string; value: string }[] };
  /**
   * ⚠ **WHAT THE EDITOR MAY ASK *THIS REPORT* FOR** (`DEF-REP-7072`).
   *
   * Present only where a MODULE VIEWER owns the report and its columns are
   * therefore not its dataset's. The statement serves seven names; the
   * `journal_lines` dataset declares five; the two lists intersect in
   * `reference` and nothing else — so the panel offered the dataset's five,
   * the runner honoured the dataset's five, and opening the editor cut a
   * seven-column statement to ONE column. Neither half was wrong about its own
   * vocabulary, which is why nothing caught it.
   *
   * Absent on every dataset-backed report, where the panel goes on reading
   * `GET /reports/datasets` exactly as it did.
   */
  column_choices?: string[];
  /** ⚠ **WHAT KIND OF THING EACH SERVED COLUMN IS** (`DEF-REP-6902`). Keyed by
   *  the column name. Absent on a report whose read model is not a dataset. */
  column_meta?: Record<string, ReportColumnMeta>;
  /**
   * ⚠ **CAN THIS REPORT ACTUALLY BE DOWNLOADED** (`DEF-REP-6899`).
   *
   * The server asks the same registry `POST /exports` consults. The viewer
   * drew `Download CSV` on every report that served a payload — eighteen at
   * the time, four of them registered — so fourteen offered a button whose
   * POST answered 404 and whose failure was invisible by construction.
   *
   * ⚠ **ABSENT MEANS *DO NOT DRAW IT*, NOT *PROBABLY FINE*.** An older server,
   * or any payload that reaches this type without passing the flag, must not
   * be read as permission: a control that is missing is a smaller fault than
   * one that fails in silence, which is the whole of this defect.
   */
  exportable?: boolean;
  rows: (ReportRow | ReportGroupRow)[];
  kpis: ReportKpi[];
  totals: Record<string, ReportTotal>;
  unavailable: ReportGap[];
  /** Payments by method only — the per-payment rows behind the method mix. */
  details?: ReportRow[];
  detail_columns?: string[];
  purposes?: { purpose: string; count: number; amount: string | null }[];
  /**
   * ⚠ **THE SERVED ROWS ARE GROUP ROWS AND THE FACTS ARE NOT HERE**
   * (`P2.24`). True on the SQL grouping path: every group's Σ covers the whole
   * filtered set, so the facts behind it are fetched by drilling rather than
   * being interleaved.
   *
   * ⚠ **A PAGER MUST READ THIS BEFORE IT READS `page.total`** — see
   * `DEF-REP-6891`. `page.total` is a count of FACTS, so quoting it over a
   * table drawing three group rows prints *"1–36 of 36"* above three lines.
   */
  collapsed?: boolean;
  /** ⚠ **PRESENT ONLY ON A REPORT THAT PAGES** (`ar_aging` since `P2.21`).
   *  Absent means *this is all of it*; it does not mean *page one*. A reader
   *  that treated the two the same would print "1–50 of 50" over a whole
   *  bounded report. */
  page?: { page: number; per: number; total: number; pages: number };
  /** ⚠ **WHAT ONE ROW IS, AS A CODE** (`P2.23`). The screen turns it into a
   *  sentence through `reports.grain.<code>` — *"One row per account"*. Absent
   *  means this report does not state its grain, and the screen then states
   *  NOTHING: a grain line that is wrong is worse than none, because a reader
   *  believes it. */
  grain?: string;
  /** ⚠ **WHAT THIS REPORT'S TABLE MAY OFFER** (`P2.2` · `P2.3` · `P2.5`).
   *
   *  A sort caret is drawn ONLY over a column named in `sorts`, and the search
   *  box only when `searchable`. Offering either where the query ignores it is
   *  hard-won law 2's mirror — a live screen behind a dead control — and the
   *  account ledger DECLINES sort on purpose, because ordering a running
   *  balance by amount destroys the column.
   *
   *  Absent = neither. `revenue_by_service_rate` and `payments_by_method` are
   *  bounded by the service list and the tender list rather than by tenant
   *  size, so they page, sort and search not at all. */
  controls?: {
    sorts: string[];
    sort: string;
    dir: "asc" | "desc";
    searchable: boolean;
    /** ⚠ **WHAT THIS REPORT CANNOT RUN WITHOUT** (`DEF-REP-7070`). Absent on
     *  the forty-five reports that need nothing named — and absence must be
     *  read as *nothing is required*, never as *we did not say*, because the
     *  editor draws a chooser for each entry and a guessed one would add a
     *  step to a report that has none. */
    requires?: ReportRequiredParam[];
    /** `CR-185-BRC10` — the report is a DOCUMENT handed to someone (the Owner
     *  summary), so the viewer offers Print beside Download. Server-declared;
     *  absent is read as NO, and a report that is not a document draws none. */
    printable?: boolean;
    /** ⚠ **WHAT THIS REPORT ASKS FOR BEFORE IT CAN ANSWER** (`CR-179-BRC10`).
     *  Server-declared, drawn generically by the standard viewer — no screen
     *  knows a report's input names. Absent means the report declares none,
     *  and the viewer then draws only the `REPORT_FILTERS` bar it always drew. */
    inputs?: ReportInput[];
  };
}

/** One choice of a declared `select`/`multi` input, or of a table column's
 *  fixed list. `label` is a name a person reads (B14 rule 31); `label_key` is a
 *  catalogue key instead, with `params` for its placeholders. */
export interface ReportInputOption {
  value: string;
  label?: string;
  label_key?: string;
  params?: Record<string, string | number>;
}

/** One record of a table input's `choices` list. Every field beyond `value`
 *  and `label` is data a column may filter on (`depends_on`), display
 *  (`display` … `from`) or read a `now` figure from (`now_from`). */
export interface ReportInputChoice {
  value: string;
  label: string;
  [field: string]: unknown;
}

/** One column of a declared table input. */
export interface ReportInputColumn {
  name: string;
  kind: "select" | "display" | "money" | "unit_price";
  /** The header's catalogue key. Absent → `<input label_key>.column.<name>`. */
  label_key?: string;
  /** A fixed list (a `select` with no `choices`). */
  options?: ReportInputOption[];
  /** The name of the `choices` list this `select` draws from. */
  choices?: string;
  /** The column whose chosen value a choice must carry under the same name. */
  depends_on?: string;
  /** The `choices` list a `display` column reads its value from. */
  from?: string;
  /** The `choices` list whose chosen record carries `now: {<name>: figure}`. */
  now_from?: string;
  /** The `item_kind`s for which this box is not asked for (drawn as a dash and
   *  sent as null). */
  hidden_for_item_kinds?: string[];
}

export interface ReportInputShortcut {
  kind: "percent";
  label_key: string;
  options: string[];
}

interface ReportInputBase {
  /** The run parameter. Travels in the URL as `in.<param>` and to the server
   *  BARE, as a string. */
  param: string;
  label_key: string;
  /** What the server applies when the parameter is absent. */
  default?: string;
}

export type ReportInput =
  | (ReportInputBase & { kind: "select"; options: ReportInputOption[] })
  | (ReportInputBase & {
      kind: "multi";
      options: ReportInputOption[];
      /** Present → empty means ALL and the box reads this; absent → empty
       *  means nothing chosen yet. */
      all_label_key?: string;
    })
  | (ReportInputBase & {
      kind: "table";
      add_label_key?: string;
      /** One instruction under the table, when the report declares one. */
      note_key?: string;
      columns: ReportInputColumn[];
      choices: Record<string, ReportInputChoice[]>;
      shortcuts?: ReportInputShortcut[];
    });

/** The declared inputs' values, by `param`, each ONE string — a multi is
 *  comma-joined and a table is one JSON string. */
export type ReportInputValues = Record<string, string>;

/**
 * A query as the SERVER reads it: every key bare, declared inputs flattened in
 * beside the fixed ones. One function, so the run, the export and the schedule
 * cannot carry different parameter sets.
 */
export function flatReportParams(query: ReportQuery): Record<string, string> {
  const flat: Record<string, string> = {};
  for (const [name, value] of Object.entries(query)) {
    if (name === "inputs") continue;
    if (value !== undefined && value !== "") {
      flat[name] = String(value);
    }
  }
  for (const [name, value] of Object.entries(query.inputs ?? {})) {
    if (value !== "") {
      flat[name] = value;
    }
  }
  return flat;
}

/**
 * ONE INPUT A REPORT IS ABOUT, DECLARED BY THE SERVER (`DEF-REP-7070`).
 *
 * ⚠ **A DECLARATION, NOT A REFUSAL.** `unavailable` says *you did not name an
 * account*, and only after a run that returned nothing. This says *this report
 * is about one account*, on every run including the ones that succeed — which
 * is what lets screen 2·2 ask for it FIRST instead of showing four empty tiles
 * and a reason below the fold.
 *
 * ⚠ **THE SCREEN HOLDS NO TABLE OF WHICH REPORT NEEDS WHAT.** `finds` names
 * the KIND of record, so a statement drawn at the premises grain asks for a
 * premises without one line of front-end code knowing it is a statement.
 */
export interface ReportRequiredParam {
  /** The run parameter — today `subject_id`, and it travels in the URL where a
   *  clerk never reads it (B14 rule 31). */
  param: string;
  /** The kind of record it names: `account`, `premises`, `unit`, `customer`. */
  finds: string;
}

export interface ReportQuery {
  from?: string;
  to?: string;
  bill_type?: string;
  service?: string;
  purpose?: string;
  class?: string;
  /** ⚠ **`per=all` — the WHOLE filtered set.** `ar_aging` began paging at fifty
   *  on 2026-09-24 (`P2.21`), and this viewer renders one table with no pager;
   *  without this it would have shown fifty rows of a receivable of any size
   *  and looked entirely correct. The Finance Aging view is the screen that
   *  pages. */
  per?: string;
  /** ⚠ **THE TABLE'S OWN FOUR, SERVER-SIDE** (`P2.1`–`P2.3` · `P2.5`).
   *  `q` searches the dataset's declared searchable columns, `sort`/`dir` order
   *  in SQL, `page` cuts. They are sent BARE like the window bounds and unlike
   *  the `f.` list filters, because `apps/reports/runner._RUN_CONTROLS` reads
   *  them as the RUNNER's vocabulary rather than any dataset's. */
  q?: string;
  sort?: string;
  dir?: string;
  page?: string;
  /** ⚠ **`P2.17` — THE GROUP LEVELS, COMMA-SEPARATED, AT MOST THREE.**
   *  Sent BARE for the reason `sort` and `page` are: `runner._RUN_CONTROLS`
   *  reads it as the RUNNER's vocabulary, not as any dataset's filter.
   *  A level this dataset cannot group by is DROPPED by the server with its
   *  reason in `unavailable` — never a 4xx, because a clerk following a stale
   *  bookmark should get their report rather than an error page. */
  group_by?: string;
  /** ⚠ **`P5.3` — THE COLUMNS THE CLERK HAS TICKED, COMMA-SEPARATED.**
   *  Sent BARE for the reason `group_by` is: `runner._RUN_CONTROLS` reads it as
   *  the RUNNER's vocabulary, not as any dataset's filter.
   *
   *  This is what makes the 2·2 preview live — *"Adding a column shows it in
   *  the rows below without a save"* — and it is why 2·2 is a panel rather than
   *  a wizard (PO ruling 2026-09-26). A name the dataset does not declare is
   *  DROPPED server-side, never 4xx: at SAVE an unknown column is refused with
   *  the column named, and at RENDER the caller may be following a stale
   *  bookmark. */
  columns?: string;
  /** ⚠ **`BR-REP-038` — THE SUBJECT A FOUR-GRAIN REPORT IS DRAWN AT, AND THE
   *  ONE ROW IT IS ABOUT.** Sent BARE for the reason `group_by` is:
   *  `runner._RUN_CONTROLS` reads both as the RUNNER's vocabulary, because a
   *  subject is declared on the DEFINITION and spans two definitions sitting
   *  on two different datasets.
   *
   *  `subject_id` is an id and it travels in the URL, where the clerk never
   *  reads it (B14 rule 31) — exactly as the retired customer-statement screen
   *  put a customer id there. It is never a visible value.
   *
   *  ⚠ **WITHOUT THESE TWO THE STATEMENT COULD NOT BE OPENED AT ALL.** Measured
   *  in a browser at 1440 before they were added: `/reports/statement?subject_id=…`
   *  rendered four empty tiles reading *Choose an account first* over a URL
   *  that named one, because `paramsFrom` rebuilds the request and dropped it.
   *  That is hard-won law 2's mirror — a live screen behind a control nothing
   *  carries — and it is the identical miss `group_by` and `columns` each
   *  record one comment up. */
  subject?: string;
  subject_id?: string;
  /** ⚠ **THE SERVER-DECLARED INPUTS' VALUES, BY PARAM** (`CR-179-BRC10`).
   *  A bag rather than named fields, so no report's input names are written
   *  into this type. In the URL each is `in.<param>`; on the wire each is
   *  sent BARE (`flatReportParams`). */
  inputs?: ReportInputValues;
}

/**
 * The AR ageing's own query — p035's five criteria plus the page.
 *
 * ⚠ **A SEPARATE SHAPE FROM `ReportQuery` BECAUSE THE WIRE NAMES DIFFER.**
 * `runReport` sends every key BARE and `apps/reports/queries.ar_aging` reads
 * the list criteria under `BR-SHL-011`'s `f.` grammar — so the names are
 * written out here exactly as the server reads them, rather than derived by a
 * rule. `DEF-131` and `DEF-REP-6648` are both one param whose two halves were
 * each internally consistent and never compared.
 */
export interface AgingReportQuery {
  /** The position's date. BARE — a period bound is not a list filter (DEF-095).
   *
   * ⚠ **`from` IS SENT ALTHOUGH THE AGEING READS ONLY `to`, AND LEAVING IT OUT
   * ANSWERED 422 ON EVERY REQUEST.** `apps/reports/api` requires BOTH bounds
   * for every report — a receivable is a POSITION at a date and the lower
   * bound reaches no figure in it, but the handler refuses a half window with
   * `reports.viewer.param_required` before any report code runs. Found by
   * opening the screen, which is the only thing that could have seen it: `tsc`
   * and fourteen backend cases were green, because the backend tests call the
   * viewer with both. */
  from?: string;
  to?: string;
  "f.band"?: string;
  "f.service"?: string;
  "f.premises"?: string;
  "f.class"?: string;
  q?: string;
  sort?: string;
  dir?: string;
  page?: string;
  per?: string;
}

/** `GET /reports/ar_aging` — ONE PAGE of A14's ageing (`P2.21`). */
export async function runAgingReport(
  query: AgingReportQuery,
  client: ApiClient = api,
): Promise<ReportResponse> {
  const search = new URLSearchParams();
  for (const [name, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") {
      search.set(name, value);
    }
  }
  const suffix = search.toString();
  return requireData(
    await client.get<ReportResponse>(`/reports/ar_aging${suffix === "" ? "" : `?${suffix}`}`),
  );
}


export async function runReport(
  key: string,
  query: ReportQuery,
  client: ApiClient = api,
): Promise<ReportResponse> {
  // `flatReportParams` — declared inputs travel BARE beside the fixed ones.
  const search = new URLSearchParams(flatReportParams(query));
  const suffix = search.toString();
  return requireData(
    await client.get<ReportResponse>(`/reports/${key}${suffix === "" ? "" : `?${suffix}`}`),
  );
}

// ── US-REP-003 — the IS-11 download ───────────────────────────────────────

export interface AcceptedExport {
  job_id: string;
  status_url: string;
}

/**
 * `POST /exports` — the SAME platform route the nine exportable lists use.
 *
 * The four reports are registered export RESOURCES (`apps/reports/exports.py`),
 * so the 50,000-row cap, the RLS-scoped stream, the `audit_log` row and the
 * IS-11 filename all come from one implementation. A second download path for
 * reports would be a second filename grammar and a second cap.
 *
 * `filters` is the viewer's own parameter set, so the file is the report on
 * screen rather than an approximation re-derived under different defaults.
 */
/**
 * `POST /exports` — §8.2's RIGHT PATH, which must never hold a page.
 *
 * ⚠ **`filters` IS WIDENED TO A PLAIN MAP AND THAT IS DELIBERATE** (`P2.5`).
 * The screen builds it through `reportExportFilters`, which drops `page` and
 * `per` and keeps everything else, so the file is the whole FILTERED set. The
 * registry's `select` then runs the report with `whole=True`
 * (`apps/reports/exports.py:146,178`).
 *
 * The reason that matters: when the billing register started paging, its export
 * silently inherited the screen's FIFTY rows. A clerk would have exported a
 * 38,000-row register and received a valid-looking file of fifty — no error, no
 * gate, no test.
 */
export async function requestReportExport(
  key: string,
  filters: ReportQuery | Record<string, string>,
  client: ApiClient = api,
): Promise<AcceptedExport> {
  const clean: Record<string, string> = {};
  // A `ReportQuery` carrying declared inputs is flattened first, so the file
  // is asked with the same parameters the screen ran with.
  const flat: Record<string, string | undefined> =
    "inputs" in filters && typeof filters.inputs === "object"
      ? flatReportParams(filters as ReportQuery)
      : (filters as Record<string, string | undefined>);
  for (const [name, value] of Object.entries(flat)) {
    // ⚠ `page` and `per` never travel. A file made of page three is not a
    // smaller file, it is a wrong one.
    if (value !== undefined && value !== "" && name !== "page" && name !== "per") {
      clean[name] = String(value);
    }
  }
  return requireData(
    await client.post<AcceptedExport>("/exports", { resource: key, filters: clean }),
  );
}

// ── CR-142-BRC07 Phase 5 · the builder's own calls ────────────────────────

/** One column a dataset produces, as `GET /reports/datasets` declares it.
 *
 *  ⚠ **THE PANEL COUNTS THIS LIST AND NEVER A LIST OF ITS OWN.** 2·2's header
 *  reads *"4 of 7"* and *"13 available"* by counting what the server sent, so a
 *  screen and the engine cannot be counting different things — which is exactly
 *  what the six hand-typed maps `P0.7` deleted were doing. */
export interface DatasetColumn {
  name: string;
  type: string;
  /** Present on a `quantity` — CLAUDE.md hard rule 3. A read of `684` is not a
   *  number anybody can compare; `684 kWh` is. */
  unit: string | null;
  unit_from: string | null;
  /** Present on `money` — BR-REP-001. */
  money_basis: string | null;
  scale: number | null;
}

/** A column a row COUNTS, with how it totals and whether that total is lawful. */
export interface DatasetMeasure {
  name: string;
  aggregation: string;
  /** `full` · `semi` · `non` · `within_service`. The panel shows the
   *  aggregation per measure BECAUSE of this — p31 callout ③: *"each one
   *  carries its own aggregation, so the footer totals what the measure says
   *  rather than what the renderer assumed."* */
  additivity: string;
  /** The dimensions this measure may NOT be aggregated across. */
  forbidden_across: string[];
}

export interface DatasetDimension {
  name: string;
  attributes: string[];
  /** Coarse → fine. Group-to-three-levels reads this. */
  hierarchy: string[] | null;
  conformed: boolean;
}

export interface ReportDataset {
  code: string;
  owner_module: string;
  /** What ONE ROW IS, in words a clerk reads. */
  grain: string;
  columns: DatasetColumn[];
  measures: DatasetMeasure[];
  dimensions: DatasetDimension[];
  filters: string[];
  time_hierarchy: string;
  paginates: boolean;
}

export interface ReportDatasetsResponse {
  datasets: ReportDataset[];
}

export const reportDatasetsQueryKey = ["reports", "datasets"] as const;

/** `GET /reports/datasets` — what the edit panel is allowed to offer.
 *
 *  ⚠ **THIS IS THE SECURITY BOUNDARY OF THE WHOLE FEATURE, SEEN FROM THE
 *  CLIENT.** §8.1: *"Every arrow into the database passes through a reviewed
 *  dataset … the definition chooses FROM WHAT A DATASET OFFERS, and a dataset
 *  is code that went through review."* The panel offers exactly what this
 *  answer declares, and the server refuses anything else at save — so the
 *  client half is a convenience and the server half is the wall. */
export async function getReportDatasets(
  client: ApiClient = api,
): Promise<ReportDatasetsResponse> {
  return requireData(await client.get<ReportDatasetsResponse>("/reports/datasets"));
}

/** `private` or `shared` — `BR-REP-019`'s signed two-value enum.
 *
 *  ⚠ NOT the same vocabulary as `ReportOrigin`, which has three. A row is
 *  `built_in`, `mine` or `shared` on the CATALOGUE — that is where it came from
 *  — and `private` or `shared` in the TABLE, which is who may see it. The
 *  catalogue's `mine` and `shared` are both tenant rows; the difference is
 *  whether the reader owns it. Naming them alike is how two screens come to
 *  disagree about what a word means. */
export type ReportVisibility = "private" | "shared";

/** The definition a clerk is holding in the panel, on its way to the server.
 *
 *  ⚠ **IT NAMES COLUMNS, NEVER SQL.** Every string here is checked against the
 *  dataset's declaration server-side before anything reaches a query. */
export interface ReportDefinitionDraft {
  name: string;
  dataset: string;
  group: string;
  sub_group?: string | null;
  columns?: string[];
  filters?: Record<string, string>;
  group_by?: string[];
  sort?: string[];
  service_codes?: string[];
  visibility?: ReportVisibility;
  /** Which standard report this was copied from, or absent for *from scratch*.
   *  p22 callout ⑤: *"This column is the difference between a catalogue and a
   *  junk drawer."* */
  based_on?: string | null;
}

export interface SavedReportDefinition {
  id: string;
  key: string;
  name: string;
  dataset: string;
  group: string;
  sub_group: string | null;
  visibility: ReportVisibility;
  owner_user_id: string | null;
  based_on: string | null;
  created: boolean;
}

/** `POST /reports/definitions` — screen 2·4's **Save**.
 *
 *  ⚠ **THE REPLY'S `key` IS WHAT THE SCREEN NAVIGATES TO, AND THE SCREEN MUST
 *  NOT GUESS IT.** Saving *Overdue 60+* twice gives `overdue-60` and
 *  `overdue-60-2`; only the server knows which one it just wrote. A screen that
 *  slugged the name itself would open the FIRST report after saving the second
 *  — p23's own sentence: *"a save that gives no sign of where the thing went is
 *  how a clerk saves the same report three times."* */
export async function saveReportDefinition(
  draft: ReportDefinitionDraft,
  client: ApiClient = api,
): Promise<SavedReportDefinition> {
  return requireData(
    await client.post<SavedReportDefinition>("/reports/definitions", draft),
  );
}

/** `PATCH /reports/definitions/{id}` — 2·2's **Save** on a row you own.
 *
 *  ⚠ A built-in is never PATCHed: it has no row of yours to change, so editing
 *  one calls `saveReportDefinition` and the platform row is untouched. That is
 *  copy-on-write, and the server refuses a platform id here by name rather than
 *  quietly making a copy, because a screen that reaches it has a bug. */
export async function updateReportDefinition(
  id: string,
  changes: Partial<ReportDefinitionDraft>,
  client: ApiClient = api,
): Promise<SavedReportDefinition> {
  return requireData(
    await client.patch<SavedReportDefinition>(`/reports/definitions/${id}`, changes),
  );
}

/** `DELETE /reports/definitions/{id}` — 1·2's row action. */
export async function deleteReportDefinition(
  id: string,
  client: ApiClient = api,
): Promise<{ key: string; deleted: boolean }> {
  return requireData(
    await client.del<{ key: string; deleted: boolean }>(`/reports/definitions/${id}`),
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-REP-001@c6c35b2 (co-packets US-REP-002/003/005/006/007; 04-docs/05-modules/12-reports/06-epics/EP-REP-01-report-center.md · EP-REP-02-canned-reports.md · 12-reports/02-business-rules.md · apps/reports/{catalog,queries,exports}.py, the shapes these types describe)
// screens: S44 · S46
// generated: 2026-08-16 by story-coder (reports lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint --max-warnings 0✔ vitest✔ vite build✔
// exceptions: (1) these wrappers live in their OWN module rather than in `api/endpoints.ts`, following `bankRecEndpoints.ts` and `billingOpsEndpoints.ts` — and because five lanes share this working tree and endpoints.ts is 7,900 lines several of them are editing (law 11) · (2) `GET /reports` is an endpoint no signed document contracts; see `apps/reports/catalog.py` for why it is served · (3) every money field is `string | null` and every null carries a reason — typing one as `string` would let a screen print a 0.00 nobody computed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
