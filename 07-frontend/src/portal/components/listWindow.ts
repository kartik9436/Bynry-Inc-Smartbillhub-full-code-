// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CWP-5747 — *"every customer-portal list holds ALL its rows in
//          the browser"*. Six portal edge endpoints served an unbounded array
//          and `PortalListTable` searched, sorted and sliced it client-side.
//          `GET readings` was every reading an account had ever taken.
// Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
//          BR-SHL-011 (the URL grammar q/sort/dir/page/per/f.<name>) ·
//          IS-2 (the page-size vocabulary) · IS-3 (search is debounced) ·
//          BR-CWP-011 (the signed-in surface calls the PORTAL edge and
//          nothing else — which is why the debouncer is imported from
//          `components/searchDebounce` and not from `DataTable`)
// Screens: CWP-023 · CWP-027 · CWP-031 · CWP-034 · CWP-041
// Tests:   src/portal/components/listWindow.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * The state five portal screens hold so that their SERVER can page, search and
 * sort — and the `PortalServerWindow` they hand to `PortalListTable`.
 *
 * ⚠ **IT IS ONE HOOK FOR FIVE SCREENS BECAUSE IT IS ONE BEHAVIOUR.** Page,
 * rows-per-page, the typed needle, rule 13's sort cycle and the chips are the
 * same five pieces of state on every list in the portal, and every one of them
 * has to travel on the request. Five screens each holding their own five would
 * be five chances to forget that typing resets the page to 1 — which is the
 * least-surprise law `DataTable.withSearch` already applies on the staff side.
 *
 * ⚠ **THE SEARCH IS DEBOUNCED AND THE BOX IS NOT.** What a person is typing is
 * held here and rendered immediately; what is SENT is the settled value, 300 ms
 * later (IS-3). Without that split a six-character serial is six requests, the
 * last four of which are already stale when they answer — and with a naive
 * `value={sent}` the input would also lag a keystroke behind the person's
 * fingers, which is the worse of the two bugs because it is felt.
 *
 * ⚠ **THE MINIMUM IS ONE CHARACTER HERE AND TWO ON THE STAFF SIDE**, and
 * `searchDebounce.ts` argues that out at the option it is passed to. In one
 * sentence: a customer typing `8` to find meter `8841-C` must not silently get
 * their whole list back, and the predicate this replaces had no minimum at all.
 */

import { useCallback, useMemo, useRef, useState } from "react";

import { createSearchDebouncer } from "@/components/searchDebounce";
import type { SearchDebouncer } from "@/components/searchDebounce";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { PageSize } from "@/components/tableTypes";

import type { PortalListRequest } from "../api/portalClient";
import type { PortalServerWindow, SortState } from "./listTable";

/** ⚠ **ONE CHARACTER, NOT IS-3's TWO.** See the note above and the option's own
 *  docstring in `components/searchDebounce.ts`. */
const PORTAL_SEARCH_MIN_CHARS = 1;

/** Two characters before a typed word is taken for one of a screen's own
 *  vocabulary words. One would make `a` name April, August and every other
 *  month at once, and the first of them would win silently. */
const WORD_MIN_CHARS = 2;

/**
 * The twelve month names as THIS reader sees them, keyed by the two digits the
 * server stores — `{ "01": "January Jan", … }`.
 *
 * ⚠ **BOTH THE LONG AND THE SHORT FORM ARE IN THE STRING, AND THAT IS ON
 * PURPOSE.** `monthYearText` renders the SHORT form by default — *Aug 2026* —
 * so the predicate this replaces matched `aug` and not `august`. Holding both
 * means `august` finds the same bills, which is a search a person will try and
 * which used to answer nothing. Nothing else about the match widens: the test
 * is still `includes`, and a locale whose short form is not a prefix of its
 * long one is covered because both are present.
 *
 * ⚠ **BUILT FROM `Intl`, NEVER FROM A LIST TYPED OUT HERE** (hard-won law 2:
 * the front end names the eleven SERVICES by hand in two files and the
 * eleventh silently never appeared on screen). The browser owns the calendar.
 */
export function monthWords(language: string): Record<string, string> {
  const words: Record<string, string> = {};
  for (let index = 0; index < 12; index += 1) {
    const when = new Date(2000, index, 1);
    const long = new Intl.DateTimeFormat(language, { month: "long" }).format(when);
    const short = new Intl.DateTimeFormat(language, { month: "short" }).format(when);
    words[String(index + 1).padStart(2, "0")] = `${long} ${short}`;
  }
  return words;
}

/** A screen's own translated words, by the CODE the server knows them by —
 *  `{ "08": "August", "09": "September", … }` or `{ bill: "Bills", … }`. */
export interface PortalVocabulary {
  /** The filter name it resolves to, sent as `f.<name>`. */
  name: string;
  words: Record<string, string>;
}

/**
 * Split what a person typed into the CODES it names in their own language and
 * the text the server can match for itself.
 *
 * ⚠ **THIS EXISTS BECAUSE THE SERVER MAY NOT OWN THE WORDS AND THE SCREEN MAY
 * NOT OWN THE ROWS (`DEF-CWP-5747`).** `CWP-027` prints *August 2026* over a
 * bill number and `CWP-031` prints *Bills* over a document's kind, and both
 * were searchable because the browser held every row and matched the string it
 * had just rendered. The rows are one page now, so the match has to happen on
 * the server — and B14 rule 35 says the server does not write those words in
 * any of the eleven languages, let alone all of them. So the SCREEN, which drew
 * the word and knows the language, turns it back into the code the server
 * stores: *August* becomes `f.month=08`, *Bills* becomes `f.group=bill`.
 *
 * ⚠ **IT IS A SUBSTRING MATCH BECAUSE THE PREDICATE IT REPLACES WAS ONE.**
 * `monthYearText(...).toLowerCase().includes(needle)` matched `gust` as
 * happily as `aug`, so this does too — anything stricter would be this commit
 * quietly removing a search a customer already relies on.
 *
 * ⚠ **A TOKEN THAT NAMES NOTHING IS LEFT FOR THE SERVER**, so *BL-2608* still
 * travels as `q` and *august 2026* resolves BOTH halves — the month here, the
 * year by the four-digit rule its own screen declares.
 *
 * ⚠ **ONE CODE PER VOCABULARY, FIRST MATCH.** Two month names containing one
 * token is rare and the alternative is an OR the server grammar has no spelling
 * for; a customer who meant the other one types another letter.
 */
export function splitNeedle(
  needle: string,
  vocabularies: PortalVocabulary[],
  /** A token of exactly four digits is a YEAR and is sent under this filter
   *  name. It is separate from a vocabulary because there is no list of years
   *  to write down, and because *2026* is not a word in any language. */
  year?: string,
): { filters: Record<string, string>; rest: string } {
  const filters: Record<string, string> = {};
  const rest: string[] = [];
  for (const token of needle.trim().split(/\s+/).filter(Boolean)) {
    const lowered = token.toLowerCase();
    if (year !== undefined && /^\d{4}$/.test(token) && filters[year] === undefined) {
      filters[year] = token;
      continue;
    }
    let taken = false;
    for (const vocabulary of vocabularies) {
      if (filters[vocabulary.name] !== undefined) continue;
      if (lowered.length < WORD_MIN_CHARS) continue;
      const hit = Object.entries(vocabulary.words).find(([, word]) =>
        word.toLowerCase().includes(lowered),
      );
      if (hit !== undefined) {
        filters[vocabulary.name] = hit[0];
        taken = true;
        break;
      }
    }
    if (!taken) rest.push(token);
  }
  return { filters, rest: rest.join(" ") };
}

export interface PortalListWindowOptions {
  /** The size the list opens on. IS-2's default is 50 and no screen overrides
   *  it today; the argument exists so a test can page a short fixture without
   *  building 51 rows. */
  per?: PageSize;
  /** Rule 13's cleared state is `null` and means *the order the server sent*,
   *  which for every portal list is newest-first. A screen passes a sort here
   *  only where its drawing opens on something else. */
  sort?: SortState;
  /** The chips' opening values, as `f.<name>`. `all` is the absence. */
  filters?: Record<string, string>;
  /**
   * Turn what a person typed into the filters and the text the SERVER can
   * match — see `splitNeedle`. A screen passes this only where it prints a
   * word the server does not hold: a month name, a translated kind.
   *
   * ⚠ **THE RESOLVED FILTERS DO NOT OVERWRITE A CHOSEN CHIP.** A customer who
   * has pressed *Unpaid* and then types *August* means both, so the two are
   * merged with the chip's own value winning its own key.
   */
  resolve?: (needle: string) => { filters: Record<string, string>; rest: string };
}

export interface PortalListWindowApi {
  /** What to send. Pass it straight to the `portalClient` wrapper. ⚠ **IT IS
   *  ALSO THE EFFECT'S DEPENDENCY** — a screen depends on this object's own
   *  fields, so a page turn, a settled keystroke, a sort and a chip each
   *  re-fetch and nothing else does. */
  request: PortalListRequest;
  /** What is IN the search box this instant, debounced or not. */
  typed: string;
  /** The chosen chip for one filter, `all` when none. `CWP-034` reads it to
   *  say which meter tab is current. */
  filter: (name: string) => string;
  setPage: (page: number) => void;
  setPer: (per: PageSize) => void;
  setFilter: (name: string, value: string) => void;
  /** What a person typed. `CWP-041` owns its search box (`DEF-CWP-4879`) and
   *  feeds this instead of drawing the table's. */
  type: (raw: string) => void;
  /* ⚠ **`sort` AND `setSort` ARE NOT RETURNED, AND THAT IS HARD-WON LAW 2.**
     Rule 13's cycle belongs to `PortalListTable` — it computes `nextSort` and
     calls `window().onSort`, which reaches this state without passing through
     a screen. Returning the pair would be API no caller has, which is exactly
     the dead prop `toolbarLead` was for ten days. Bring them back with the
     screen that needs to set a sort of its own, not before. */
  /**
   * The `PortalServerWindow` for `PortalListTable`. `total` and `populated`
   * are the SERVER's answers and this hook cannot invent either: `count` is
   * the whole matching set, and `populated` is whether the list has any rows
   * at all — without which a page of nothing under a typed search renders
   * *you have no bills* at a customer who has eleven months of them.
   */
  window: (answer: {
    total: number;
    populated: boolean;
    busy?: boolean;
    /**
     * The page and the size the SERVER actually answered with — its own echo,
     * not what was asked for.
     *
     * ⚠ **THEY DIFFER EXACTLY WHEN `BR-SHL-011`'s CLAMP FIRES**, and that is
     * the case they exist for: a person who types `?page=999` into a two-page
     * list is served the LAST page, and a footer reading the number this hook
     * asked for would say *Page 999 of 2* over the rows of page 2. Passing the
     * echo also keeps the table's footer and the phone stack's — which reads
     * the payload directly — from disagreeing about which page is open.
     *
     * Omitted, the hook's own state stands in, which is right for a list that
     * has not answered yet.
     */
    page?: number;
    per?: PageSize;
    search?: { placeholder: string };
    chips?: {
      name: string;
      label: string;
      testId?: string;
      options: { key: string; label: string }[];
    };
  }) => PortalServerWindow;
}

export function usePortalListWindow(options: PortalListWindowOptions = {}): PortalListWindowApi {
  const [page, setPageState] = useState(1);
  const [per, setPerState] = useState<PageSize>(options.per ?? DEFAULT_PAGE_SIZE);
  const [sort, setSortState] = useState<SortState>(options.sort ?? null);
  const [filters, setFilters] = useState<Record<string, string>>(options.filters ?? {});
  /** What the person can see in the box. */
  const [typed, setTyped] = useState("");
  /** What has been SENT — the settled value, 300 ms behind the box. */
  const [needle, setNeedle] = useState("");

  // ⚠ **THE DEBOUNCER IS BUILT ONCE AND FIRES THROUGH A REF.** Rebuilding it
  // on every render would restart its timer on every keystroke and it would
  // never fire; capturing `setNeedle` directly is safe because React's setters
  // are stable, and the page reset rides with it so a search can never land on
  // page 7 of a result set that now has two pages.
  const debouncer = useRef<SearchDebouncer | null>(null);
  if (debouncer.current === null) {
    debouncer.current = createSearchDebouncer(
      (value) => {
        setNeedle(value);
        setPageState(1);
      },
      "",
      { minChars: PORTAL_SEARCH_MIN_CHARS },
    );
  }

  const type = useCallback((raw: string) => {
    setTyped(raw);
    debouncer.current?.type(raw);
  }, []);

  const setPage = useCallback((next: number) => setPageState(Math.max(1, next)), []);
  const setPer = useCallback((next: PageSize) => {
    setPerState(next);
    // A new size is a new result set, so the page number goes with it — asking
    // for page 7 of a list that now has 4 is a blank table.
    setPageState(1);
  }, []);
  const setSort = useCallback((next: SortState) => {
    setSortState(next);
    setPageState(1);
  }, []);
  const setFilter = useCallback((name: string, value: string) => {
    setFilters((current) => ({ ...current, [name]: value }));
    setPageState(1);
  }, []);

  /**
   * ⚠ **HELD IN A REF AND KEPT OUT OF THE MEMO'S DEPENDENCIES, AND THAT IS A
   * BUG FIX RATHER THAN A STYLE CHOICE.** A screen writes `resolve` as an
   * inline arrow — `resolve: (needle) => splitNeedle(needle, [...])` — which is
   * a NEW function on every render. Depending on it would make `request` a new
   * object every render, the screen's effect would re-fetch on every render,
   * and each answer would render again: an endless loop that shows as a
   * flickering screen and a server under load, with `tsc` and every type
   * green. Found by `Bills.dom.test.tsx`'s failed-read case, which could never
   * settle on its own error card.
   *
   * ⚠ **WHAT IT COSTS, STATED:** a language change does not re-resolve the
   * needle until the next keystroke. A person switching language mid-search is
   * not a case this product has, and the alternative is the loop above.
   */
  const resolveRef = useRef(options.resolve);
  resolveRef.current = options.resolve;
  const request = useMemo<PortalListRequest>(() => {
    const resolved = resolveRef.current?.(needle) ?? { filters: {}, rest: needle };
    return {
      page,
      per,
      q: resolved.rest,
      sort: sort?.key ?? null,
      // ⚠ **`dir` ONLY TRAVELS WITH A `sort`.** Sent alone it would flip the
      // server's own default order on a list nobody has sorted, which is the
      // `BR-CUS-1046` inversion in the other direction.
      dir: sort?.dir,
      // A chip the person pressed wins its own key over a word they typed.
      filters: { ...resolved.filters, ...filters },
    };
  }, [page, per, needle, sort, filters]);

  const filter = useCallback((name: string) => filters[name] ?? "all", [filters]);

  const window = useCallback<PortalListWindowApi["window"]>(
    (answer) => ({
      total: answer.total,
      populated: answer.populated,
      busy: answer.busy,
      page: answer.page ?? page,
      per: answer.per ?? per,
      onPage: setPage,
      onPer: setPer,
      sort,
      onSort: setSort,
      search:
        answer.search === undefined
          ? undefined
          : { placeholder: answer.search.placeholder, value: typed, onChange: type },
      chips:
        answer.chips === undefined
          ? undefined
          : {
              label: answer.chips.label,
              testId: answer.chips.testId,
              current: filters[answer.chips.name] ?? "all",
              onChoose: (key: string) => setFilter(answer.chips!.name, key),
              options: answer.chips.options,
            },
    }),
    [page, per, sort, typed, filters, setPage, setPer, setSort, setFilter, type],
  );

  return { request, typed, filter, setPage, setPer, setFilter, type, window };
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CWP-5747 — the portal pagination lane, 2026-09-19
// generated: 2026-09-19
// exceptions: none — this file renders nothing and declares no class. It is
//   covered by the `portal/` DIRECTORY entry in route-b-migrated.txt, which
//   expands to every .ts/.tsx beneath it (CR-068 wave A).
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
