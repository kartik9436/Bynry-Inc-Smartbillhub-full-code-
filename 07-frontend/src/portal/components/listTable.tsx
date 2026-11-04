// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CWP-3977 (D2 in 04-docs/05-modules/15-portal/14-layout-audit.md)
//           — *"NO PORTAL LIST USES THE SHARED TABLE, SO NO LIST CAN BE
//           SEARCHED, SORTED OR PAGED"*; and rows X6 (no row icons anywhere)
//           and X7 (no footer anywhere) of 13-wireframe-delta.md.
// Decision: 12-governance/02-decision-log.md, 2026-09-05 — *"The portal's lists
//           get the shared FURNITURE, not the staff DataTable"*. Read it before
//           changing what this file composes; five findings are recorded there.
// Rules:    B14 rule 12 (toolbar) · 13 (sorting ⇅, asc → desc → clear) ·
//           15 (row actions are ICONS, max 2) · 16 (pagination footer) ·
//           17 (empty state) · 19 (search placeholder) · 20 (table type is one
//           SIZE — body 13.5px, headers 12px) · 21 (Tailwind only) ·
//           31 (no database id on screen) · 36 (compose the kit)
// Screens:  CWP-023 · CWP-027 · CWP-031 · CWP-034 · CWP-037 · CWP-041
// ───────────────────────────────────────────────────────
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useAnnounce } from "./a11y";
import { MiniTable, SegmentedChoice, TextInput } from "./primitives";
import type { MiniTableColumn } from "./primitives";
import { ListPager, pageSlice } from "@/components/ListPager";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { PageSize } from "@/components/tableTypes";
import { RowAction, RowActionAnchor, RowActionLink, RowActions } from "@/components/RowActions";

/**
 * The portal's list furniture: a toolbar, sortable headings, row icons and a
 * pagination footer, wrapped around the ONE table the portal renders.
 *
 * ⚠ **THIS IS NOT A SECOND TABLE. `MiniTable` STILL DRAWS EVERY `<table>` IN
 * THE PORTAL** and this component draws none — it filters, sorts and slices
 * rows, then hands them over. That distinction is the whole decision of
 * 2026-09-05 and it is what keeps the answer to *"how many table types does
 * the portal have"* at one.
 *
 * ⚠ **WHY NOT THE STAFF `DataTable`, WHICH ALREADY DOES ALL OF THIS.** Because
 * it cannot run here, and the reasons are structural rather than stylistic —
 * each one was checked against the code, not assumed:
 *
 *   1. It imports `getUserPreference` / `putUserPreference` from
 *      `@/api/endpoints`. **No file under `src/portal/` imports that module**,
 *      and `BR-CWP-011` is why: *"the SIGNED-IN surface calls the PORTAL edge
 *      and nothing else"*.
 *   2. Those calls would fail for every customer. `useColumnPreference` fires
 *      on mount against `GET|PUT /user-preferences/{key}`, which is
 *      `@permission_classes([AnyTenantRole])` — a **staff** role. The portal
 *      authenticates as `IsPortalCustomer`. Every list, every mount, a 403.
 *   3. `DataTable.css` reads `var(--color-surface)`, which is `#eae9e9` — grey.
 *      That is `DEF-CWP-3987` (D12) exactly: the shared `Panel` already renders
 *      grey in the portal for this reason, so one screen shows a white main
 *      column beside a grey rail. Composing `DataTable` would spread that to
 *      six more screens. **A token that does not travel with its component is
 *      the trap here.**
 *   4. It takes a server total and a `TableRequestState`. Nothing on the portal
 *      edge pages — see the note on `rows` below.
 *
 * ⚠ **THE FOOTER IS THE SHARED KIT'S `ListPager` AND NOT A PORTAL COPY.** Its
 * own docstring answers this same question for the staff app's five
 * non-`DataTable` lists (`CR-029` RC-W3, PO 2026-08-23) and every clause of it
 * is true here: *"client-held arrays … no request state, no server total,
 * nothing to sort server-side"*. Reusing it keeps **one footer in the
 * product**, on the four `table.pager.*` keys that are already written in all
 * eleven catalogues — which is also why this file adds no plural key.
 */
export interface PortalTableColumn<Row> {
  key: string;
  /** Already translated by the screen (rule 19 / IS-8 — the kit never holds a
   *  screen's column names). */
  label: string;
  align?: "left" | "right";
  /** Rule 13. A sortable column MUST also give `sortValue`, or the heading
   *  would offer an order it cannot compute. */
  sortable?: boolean;
  /** What the sort compares — never the rendered cell, which is a `ReactNode`.
   *  Return a number for money and counts so `9` sorts below `10`, and an ISO
   *  date string for dates so lexical order is chronological. */
  sortValue?: (row: Row) => string | number | null;
  cell: (row: Row) => ReactNode;
}

/** One row icon. Rule 15: a glyph from `components/icons.tsx`, an accessible
 *  name, at most two per row. `to` navigates, `onClick` acts; exactly one. */
export interface PortalRowIcon<Row> {
  key: string;
  icon: ReactNode;
  /** Translated, and it becomes both `aria-label` and `title`. */
  label: (row: Row) => string;
  /** Rule 31 — whatever this builds is a path a person could read, never a
   *  database id. */
  to?: (row: Row) => string;
  /**
   * An address OUTSIDE the app — today, one of the API's document routes
   * (`CR-085` `CPB-14`). It wins over `to` when both are given, and it renders
   * a plain `<a href>` rather than a router `Link`, because a `Link` to
   * `/api/…` navigates the SPA to a route it does not have and fetches nothing.
   * ⚠ Rule 31 applies here too: the address carries the NUMBER printed on the
   * customer's paper, never a row id.
   */
  href?: (row: Row) => string | null;
  onClick?: (row: Row) => void;
  /** `null` = allowed. Anything else disables the control and says why
   *  (`BR-SHL-025`) — which is how `CWP-041`'s printer disappears on a bounced
   *  payment without the icon silently vanishing from the row. */
  reason?: (row: Row) => string | null;
  /** Omit the icon entirely for this row. Use it only where the drawing says
   *  the action does not exist, never as a substitute for `reason`. */
  absent?: (row: Row) => boolean;
}

/**
 * **`DEF-CWP-5747` — THE SERVER-WINDOWED MODE.** Passed, `rows` is ONE PAGE the
 * SERVER already searched, filtered, sorted and sliced; `total` is the server's
 * own `count` of the whole MATCHING set, and every control below is a REQUEST
 * rather than a slice.
 *
 * ⚠ **ALL FOUR MOVE TOGETHER OR NONE OF THEM DOES, AND THAT IS THE WHOLE
 * REASON THIS DEFECT WAS FILED RATHER THAN HALF-FIXED ON 2026-09-18.** This
 * component used to hold every row: it searched, chipped, sorted and sliced an
 * array the endpoint served in full. Take the page from the server and leave
 * the other three here, and each of them silently searches ONE PAGE OF N — a
 * customer typing a bill number that is on page 7 is told they have no such
 * bill. A correctness defect manufactured in the name of a payload defect, and
 * one that passes every test in this repo, because a search case with twelve
 * fixture rows never crosses a page boundary.
 *
 * ⚠ **SO THERE IS NO `match` ANYWHERE ON THIS TYPE.** A server-windowed caller
 * gives the search box its PLACEHOLDER and the chips their WORDS, and cannot
 * give either a predicate: the predicate is the server's. That is deliberate —
 * a `match` this component were free to ignore is exactly the dead prop
 * hard-won law 2 is about, and G13 cannot see an ignored one.
 *
 * ⚠ **OMITTED, THIS COMPONENT BEHAVES EXACTLY AS IT DID** and holds the array
 * it was handed. `CWP-037` (equipment) and `CWP-046` (open requests) are the
 * two lists that stay that way, and each says why at its own call site.
 */
export interface PortalServerWindow {
  /** The server's `count` — the whole MATCHING set, never `rows.length`.
   *  `DEF-NOT-5746` records what the other answer costs: a footer reading
   *  *"1–50 of 50"* over four thousand rows, with a next arrow that reached
   *  nothing. */
  total: number;
  page: number;
  per: PageSize;
  onPage: (page: number) => void;
  onPer: (per: PageSize) => void;
  /** Rule 12's search box. The screen holds the typed string and sends it as
   *  `?q=`; this component renders the box and never reads a row. */
  search?: { placeholder: string; value: string; onChange: (value: string) => void };
  /** Rule 12's chips, narrowed by the SERVER. `current` is `all` when none is
   *  chosen, and `all` is supplied here exactly as it is in the client mode. */
  chips?: {
    label: string;
    testId?: string;
    current: string;
    onChoose: (key: string) => void;
    options: { key: string; label: string }[];
  };
  /** Rule 13's state, held by the screen because it travels as `?sort=`/`?dir=`.
   *  `null` is the *cleared* step of the cycle and means the server's own
   *  order, which for every portal list is newest-first. */
  sort: SortState;
  onSort: (next: SortState) => void;
  /** TRUE while a page is in flight. The table stays mounted and the rows stay
   *  on screen — blanking a list to a spinner on every page turn is a worse
   *  screen than a half-second of stale rows, and it loses the reader's place.
   *  It is ALSO what stops a double-press double-fetching. */
  busy?: boolean;
  /** Whether this list has ANY rows at all, ignoring the search and the chip.
   *  ⚠ **WITHOUT IT THE TWO EMPTY STATES CANNOT BE TOLD APART.** Client-side
   *  this component compared `props.rows.length` (everything) with the
   *  filtered length; with a server window it only ever sees the matching set,
   *  so `count: 0` under a typed search would otherwise render *you have no
   *  bills* at a customer who has eleven months of them. */
  populated: boolean;
}

export interface PortalListTableProps<Row> {
  /** `CWP-027` — the `data-list` hook and nothing else. Not an id (rule 31). */
  screen: string;
  caption: string;
  columns: PortalTableColumn<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  rowMuted?: (row: Row) => boolean;
  /** Rule 17 — what is missing and what fills it, as a sentence. */
  empty: ReactNode;
  /**
   * Rule 12's search box. `placeholder` is the screen's own *"Search bills…"*
   * (rule 19); `match` decides what a typed string looks at — **the fields a
   * customer can see**, never an id.
   */
  search?: { placeholder: string; match: (row: Row, needle: string) => boolean };
  /** Rule 12's chips, filtered HERE over the payload the screen already holds.
   *  `All` is the default and is supplied by this component, so a screen passes
   *  only the narrowing ones. */
  chips?: {
    label: string;
    /** The `data-segmented` hook. Defaults to `<screen>-filter`; a screen that
     *  already had chips passes the id its own suite addresses, so moving the
     *  control into the toolbar does not silently break that suite's click. */
    testId?: string;
    options: { key: string; label: string; match: (row: Row) => boolean }[];
  };
  /* ⚠ **`toolbarLead` IS DELETED (`DEF-CWP-5747`, 2026-09-19) — IT WAS DEAD
     API FOR TEN DAYS AND `G13` SAID SO THE WHOLE TIME.** It arrived in
     `a54389bd6` on 2026-09-09 for `CWP-041`'s *All | This year*, on the
     reasoning that a filter the SERVER applies could not be a `chips` option
     because `chips` filtered rows this component already held. **No caller
     ever passed it** — dated with `git log -S`, not assumed — and the decision
     log of 2026-09-18 named it for whoever opened this file next.

     That reasoning is now simply untrue: with the server window below, EVERY
     chip is a filter the server applies, so the year pair is an ordinary
     `server.chips` entry and looks like what it is. Hard-won law 2 in both
     directions — the prop was built and never wired, and the thing it was
     built for now has a real home. */
  /** Rule 15. Two is the maximum the drawing gives any portal row. */
  icons?: PortalRowIcon<Row>[];
  /**
   * Rule 16's footer. **Off for the two lists the drawing gives no footer** —
   * `CWP-037` meters and equipment, `CWP-039` payment methods — where a
   * customer has three rows and a pager would be furniture over nothing.
   */
  footer?: boolean;
  /** Shown when a search or a chip matches nothing. A different state from
   *  `empty`: one says *you have no bills*, the other *none of your bills says
   *  that*, and answering the second with the first is a small lie. */
  noMatch?: ReactNode;
  /** `DEF-CWP-5747` — see `PortalServerWindow`. Passed, `rows` IS the page and
   *  this component filters, sorts and slices NOTHING. `search` and `chips`
   *  above are then not passed either: their predicates would never be called,
   *  and the placeholder and the words travel on the window instead. */
  server?: PortalServerWindow;
}

/** Rule 13's state. `null` is the CLEARED step of the cycle and means *the
 *  order the server sent*, which for every portal list is newest-first.
 *  ⚠ **EXPORTED SINCE `DEF-CWP-5747`** because a server-windowed screen holds
 *  it — it travels as `?sort=` and `?dir=` — and a screen that had to spell the
 *  shape out again would be free to spell it differently. */
export type SortState = { key: string; dir: "asc" | "desc" } | null;

/** Rule 13's cycle: asc → desc → **clear**. Clearing returns the list to the
 *  order the server sent, which for every portal list is newest-first — the
 *  order a customer expects before they touch anything. */
export function nextSort(current: SortState, key: string): SortState {
  if (current === null || current.key !== key) return { key, dir: "asc" };
  if (current.dir === "asc") return { key, dir: "desc" };
  return null;
}

/** Sort comparison, exported so it is testable without a browser. `null` sorts
 *  LAST in both directions: a missing date is not "earliest", it is unknown,
 *  and burying it under a descending sort would hide the row. */
export function compareValues(a: string | number | null, b: string | number | null): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b));
}

export function PortalListTable<Row>(props: PortalListTableProps<Row>) {
  const { t } = useTranslation();
  // ⚠ **THE CLIENT-HELD STATE IS STILL HERE AND IS STILL THE DEFAULT.** A
  // server-windowed caller (`DEF-CWP-5747`) holds all five of these itself,
  // because each one travels on the request; the two lists that are not
  // windowed — `CWP-037` equipment, `CWP-046` open requests — keep them here.
  const [query, setQuery] = useState("");
  const [chip, setChip] = useState("all");
  const [sort, setSort] = useState<SortState>(null);
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(DEFAULT_PAGE_SIZE);
  // Narrowed ONCE into a const, so the two modes are decided at the top of the
  // function and never re-derived inside a branch that could disagree.
  const server = props.server;
  const windowed = server !== undefined;

  const chipOption = props.chips?.options.find((o) => o.key === chip) ?? null;
  const needle = query.trim().toLowerCase();

  const shown = useMemo(() => {
    // ⚠ **WINDOWED, THE ROWS ARE THE ANSWER AND NOTHING HERE TOUCHES THEM.**
    // The server searched, chipped, sorted and sliced the WHOLE set; filtering
    // a page again would narrow the narrowed set, and sorting it again would
    // sort fifty rows out of four thousand into a convincing wrong order.
    if (server !== undefined) return props.rows;
    let out = props.rows;
    if (chipOption !== null) out = out.filter((row) => chipOption.match(row));
    if (needle !== "" && props.search !== undefined) {
      const match = props.search.match;
      out = out.filter((row) => match(row, needle));
    }
    if (sort !== null) {
      const column = props.columns.find((c) => c.key === sort.key);
      const value = column?.sortValue;
      if (value !== undefined) {
        // A COPY. Sorting `props.rows` in place would reorder the caller's own
        // array, and on a screen that re-renders from the same reference the
        // "clear" step of rule 13's cycle could never get back to the server's
        // order — the list would stay wherever the last sort left it.
        out = [...out].sort((x, y) => {
          const d = compareValues(value(x), value(y));
          return sort.dir === "asc" ? d : -d;
        });
      }
    }
    return out;
  }, [server, props.rows, props.columns, props.search, chipOption, needle, sort]);

  // The page number belongs to a result set, so any change to the result set
  // returns to page 1 — the same least-surprise law `DataTable`'s
  // `withSearch` / `nextSortState` apply on the staff side. Derived rather than
  // stored, so there is no state to forget to reset.
  const total = windowed ? server.total : shown.length;
  const shownPer = windowed ? server.per : per;
  const pages = Math.max(1, Math.ceil(total / shownPer));
  const current = Math.min(windowed ? server.page : page, pages);
  // ⚠ **WINDOWED, THE SERVER ALREADY SLICED.** Unwindowed, this is the only
  // slice — and `pageSlice` stays imported for exactly that path, which is the
  // two lists the drawing gives no footer or a short one.
  const visible = windowed || props.footer === false ? shown : pageSlice(shown, current, shownPer);
  const activeSort = windowed ? server.sort : sort;
  const currentChip = windowed ? (server.chips?.current ?? "all") : chip;

  // ⚠ **F-04 (`DEF-CWP-10552`): A SORT, A PAGE OR A FILTER CHANGES THE LIST
  // AND SAID NOTHING.** The control keeps focus (it is not re-mounted — and if
  // it were, the frame's focus rescue would put it back); what was missing is
  // the news. So when the SORT, PAGE, PAGE SIZE or CHIP changes, the number
  // of rows now shown is announced once, politely — after a windowed list's
  // answer has arrived (`busy`), never on the first draw, and never per
  // keystroke of the search box, which would talk over the typing.
  const say = useAnnounce();
  const viewKey = `${activeSort?.key ?? ""}:${activeSort?.dir ?? ""}:${current}:${shownPer}:${currentChip}`;
  const spokenFor = useRef<string | null>(null);
  const busyNow = windowed && server.busy === true;
  useEffect(() => {
    if (busyNow) return;
    if (spokenFor.current === null) {
      spokenFor.current = viewKey;
      return;
    }
    if (spokenFor.current === viewKey) return;
    spokenFor.current = viewKey;
    say.polite(t("portal.a11y.listShowing", { count: visible.length }));
  }, [viewKey, busyNow, visible.length, say, t]);

  const columns: MiniTableColumn[] = props.columns.map((column) => ({
    key: column.key,
    align: column.align,
    label: column.sortable === true ? sortHeading(column) : column.label,
  }));
  if (props.icons !== undefined && props.icons.length > 0) {
    // The heading is `portal.table.actions` for every portal list, because the
    // drawing gives every portal list the same one. There WAS an
    // `iconsHeading?: string` override here from the day this component
    // landed; it never had a caller, so it was dead API and G13 said so
    // (hard-won law 2 — built is not wired). Bring it back with the screen
    // that needs a different word, not before.
    columns.push({ key: "__actions", label: t("portal.table.actions"), align: "right" });
  }

  function sortHeading(column: PortalTableColumn<Row>): ReactNode {
    const on = activeSort !== null && activeSort.key === column.key;
    return (
      <button
        type="button"
        // ⚠ **RULE 20'S HEADER TIER, NAMED RATHER THAN INHERITED.** The first
        // draft wrote `text-[length:inherit]` so the button would take whatever
        // the `<th>` had; the ruled scale has no arbitrary step and eslint
        // refuses one (decision log 2026-08-19). Naming the same two tokens the
        // `<th>` uses is better anyway: a sorted heading and a plain one are
        // then the same size BY DECLARATION rather than by inheritance, so
        // neither can drift if the container changes.
        className="inline-flex items-center gap-1 border-0 bg-transparent p-0 font-heading text-table-header font-bold uppercase tracking-table-header text-inherit"
        // The accessible name says what pressing it DOES, not what the column
        // is: a screen reader already reads the column heading beside it.
        aria-label={t("portal.table.sortBy", { column: column.label })}
        // rule 13's state, and the one thing a sighted user reads off the glyph.
        aria-sort={on ? (activeSort.dir === "asc" ? "ascending" : "descending") : "none"}
        data-sort={column.key}
        data-sort-dir={on ? activeSort.dir : "none"}
        onClick={() => {
          // ⚠ **RULE 13'S CYCLE IS COMPUTED IN ONE PLACE FOR BOTH MODES.**
          // `nextSort` is the cycle; who STORES the answer is what differs —
          // the screen, because it travels as `?sort=`/`?dir=`, or this
          // component. A second cycle on the screen side would be two answers
          // to *what does pressing this heading twice do*.
          if (server !== undefined) {
            server.onSort(nextSort(server.sort, column.key));
            server.onPage(1);
            return;
          }
          setSort((s) => nextSort(s, column.key));
          setPage(1);
        }}
      >
        {column.label}
        <span aria-hidden="true">{on ? (activeSort.dir === "asc" ? "↑" : "↓") : "⇅"}</span>
      </button>
    );
  }

  const rows = visible.map((row) => {
    const cells: Record<string, ReactNode> = {};
    for (const column of props.columns) cells[column.key] = column.cell(row);
    if (props.icons !== undefined && props.icons.length > 0) {
      cells.__actions = (
        <RowActions>
          {props.icons
            .filter((icon) => icon.absent?.(row) !== true)
            .map((icon) => {
              const reason = icon.reason?.(row) ?? null;
              const label = icon.label(row);
              // ⚠ **`href` BEFORE `to`, BECAUSE ONE OF THEM LEAVES THE APP**
              // (`CR-085` `CPB-14`). A row that serves a stored document points
              // at `/api/…`, which the router does not have — a `Link` there
              // changes the address bar and fetches nothing.
              const href = icon.href?.(row) ?? null;
              if (href !== null) {
                return (
                  <RowActionAnchor
                    key={icon.key}
                    href={href}
                    icon={icon.icon}
                    label={label}
                    reason={reason}
                  />
                );
              }
              if (icon.to !== undefined) {
                return (
                  <RowActionLink
                    key={icon.key}
                    to={icon.to(row)}
                    icon={icon.icon}
                    label={label}
                    reason={reason}
                  />
                );
              }
              return (
                <RowAction
                  key={icon.key}
                  icon={icon.icon}
                  label={label}
                  reason={reason}
                  onClick={() => icon.onClick?.(row)}
                />
              );
            })}
        </RowActions>
      );
    }
    return { key: props.rowKey(row), muted: props.rowMuted?.(row) === true, cells };
  });

  // Rule 17. An EMPTY list has no toolbar either: a search box over nothing is
  // a control that cannot do anything, and the sentence is the whole screen.
  //
  // ⚠ **WINDOWED, `rows.length` CANNOT ANSWER THIS** (`DEF-CWP-5747`). A page
  // of nothing is either a customer with no bills or a customer whose search
  // matched none of eleven months of them, and those are two different
  // sentences. `populated` is the server's answer to the first question and
  // the only thing that can tell them apart.
  if (windowed ? !server.populated : props.rows.length === 0) {
    return (
      <div data-list={props.screen} data-list-empty="">
        {props.empty}
      </div>
    );
  }

  const searchId = `list-search-${props.screen}`;
  // ⚠ **ONE TOOLBAR, TWO SOURCES FOR WHAT IT SAYS.** The placeholder and the
  // chip words are the screen's either way; what differs is whether this
  // component also holds their state. Resolving them here keeps the markup —
  // and therefore every `data-` hook forty test files select on — identical in
  // both modes.
  const searchBox = windowed ? server.search : props.search;
  const chipSet = windowed ? server.chips : props.chips;
  const busy = windowed && server.busy === true;
  return (
    <div data-list={props.screen} data-list-busy={busy ? "" : undefined}>
      {(searchBox !== undefined || chipSet !== undefined) && (
        <div className="mb-3 flex flex-wrap items-center gap-3" data-list-toolbar="">
          {searchBox !== undefined && (
            <div className="w-full max-w-xs">
              {/* The accessible name is the placeholder's own words. A
                  placeholder alone is not a label — it disappears the moment
                  somebody types, which is exactly when a screen-reader user
                  needs to know what the field is. */}
              <label className="sr-only" htmlFor={searchId}>
                {searchBox.placeholder}
              </label>
              <TextInput
                id={searchId}
                type="search"
                value={windowed ? (server.search?.value ?? "") : query}
                placeholder={searchBox.placeholder}
                onChange={(value) => {
                  if (server !== undefined) {
                    server.search?.onChange(value);
                    server.onPage(1);
                    return;
                  }
                  setQuery(value);
                  setPage(1);
                }}
              />
            </div>
          )}
          {chipSet !== undefined && (
            <SegmentedChoice
              testId={chipSet.testId ?? `${props.screen}-filter`}
              label={chipSet.label}
              current={currentChip}
              options={[
                { key: "all", label: t("table.filters.all") },
                ...chipSet.options.map((o) => ({ key: o.key, label: o.label })),
              ]}
              onChoose={(key) => {
                if (server !== undefined) {
                  server.chips?.onChoose(key);
                  server.onPage(1);
                  return;
                }
                setChip(key);
                setPage(1);
              }}
            />
          )}
        </div>
      )}

      {total === 0 ? (
        <p className="text-body text-neutral-600" data-list-nomatch="">
          {props.noMatch ?? t("portal.table.noMatch")}
        </p>
      ) : (
        <>
          <MiniTable caption={props.caption} columns={columns} rows={rows} />
          {props.footer !== false && (
            <ListPager
              total={total}
              page={current}
              per={shownPer}
              onPage={windowed ? server.onPage : setPage}
              onPer={
                windowed
                  ? (next) => {
                      // The page number belongs to a result set and a new size
                      // is a new result set, so both travel. Sending only the
                      // size would ask for page 7 of a list that now has 4.
                      server.onPer(next);
                      server.onPage(1);
                    }
                  : (next) => {
                      setPer(next);
                      setPage(1);
                    }
              }
            />
          )}
        </>
      )}
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CWP-3977 (D2) + 13-wireframe-delta X6/X7 — the portal tables lane
// generated: 2026-09-05
// exceptions: E4 the footer's `table-pager*` classes are DataTable.css's and are
//   reached through `ListPager`, which declares none of its own — B14 rule 21
//   governs NEW classes and this file declares none either. Checked rather than
//   assumed: the app has ONE entry (`index.html`), `App.tsx` has zero lazy
//   imports and `AppShell.tsx` imports `DataTable`, so `DataTable.css` is in the
//   single emitted stylesheet and those classes do reach a portal page.
// not built, deliberately: rule 12's `+ Filter ▾` and `▦ Columns`. A customer
//   with six columns has nothing to hide, and the staff column-preference route
//   is closed to a portal session (finding 2 above), so a portal column chooser
//   would have to be a SECOND preference store. Stated here as an absence
//   rather than drawn as a dead control — hard-won law 2's mirror.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
