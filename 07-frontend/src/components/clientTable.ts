// ── Trace ──────────────────────────────────────────────
// Change:   CR-138-BRC07 · P4.7 / P4.9 — the payments blueprint's 7·1 Debtors,
//           7·3a Ladder and 7·3b Write-offs each gain *"the toolbar · ⇅
//           headers · columns · paging"*, and all three read an endpoint that
//           takes no page parameter yet.
// Rules:    B14 rule 43 (a piece of UI is built as a COMPONENT — standalone
//           code inside a page is not reuse) · B14 rule 12 (the table toolbar)
//           · B14 rule 13 (sorting) · B14 rule 16 (the pagination footer) ·
//           NFR-3 (universal server pagination — which this is a STAND-IN for
//           and not an answer to)
// Tests:    src/components/clientTable.test.ts
// ───────────────────────────────────────────────────────
/**
 * **THE SERVER'S HALF OF A TABLE, RUN IN THE BROWSER — DELIBERATELY, AND NOT A
 * DESIGN.**
 *
 * `DataTable` is a SERVER-paged component: it is handed one page and a total
 * and it reports state changes back. A list whose endpoint takes no `q`,
 * `sort`, `page` or `per` cannot give it either, so this does the search, the
 * filter, the sort and the slice over the rows that endpoint served whole.
 *
 * ⚠ **IT IS A SEAM AND IT IS MEANT TO BE DELETED.** When an endpoint grows
 * those parameters, this call is what goes and the screen above it does not
 * change. Saying so here is the point — the next lane needs to know which line
 * to remove.
 *
 * ⚠ **AND IT IS NOT A WAY TO SATISFY `NFR-3`.** `NFR-3` is about what the
 * SERVER materialises; a browser that has already been handed 40,000 rows has
 * already paid the cost the rule exists to prevent. Every list that reaches for
 * this owes a backend task, and on the payments blueprint those tasks have
 * numbers: `P4.1` for `GET /outstandings`, `P4.2` for the ladder board, and
 * `GET /write-offs` — which is `NFR-3`'s fourth unpaginated read and which
 * `CLAUDE.md` does not name.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHY IT IS IN THE KIT RATHER THAN IN A SCREEN
 * ══════════════════════════════════════════════════════════════════════════
 * It was written inside `features/assets/AssetLifecycleTab.tsx` on 2026-09-12
 * and three of this repository's lists now need exactly it. B14 rule 43, PO
 * verbatim: *"make them coponents - dont write stand alone code , engineer
 * it"*. Copying it into `features/payments/` would be the fourth place one
 * decision about how a missing value sorts gets taken — which is the same
 * shape `SelectionToolbar` was extracted to end.
 *
 * `AssetLifecycleTab` re-exports this name, so its own importers and its own
 * tests are byte-for-byte unaffected.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * THE ACCESSORS ARE PASSED IN, AND THAT IS LOAD-BEARING
 * ══════════════════════════════════════════════════════════════════════════
 * A stringly-typed sort — `row[state.sort]` — silently returns `undefined` for
 * a key nobody mapped and then "sorts" every row equal. That is a check that
 * cannot fail (hard-won law 7): the column header cycles, the arrow moves, and
 * the list never reorders. The caller supplies `sortValue`, so a key it does
 * not handle is a branch it had to write.
 */
import { filterValueList } from "./tableTypes";
import type { TableRequestState } from "./tableTypes";

/** What one row offers each of the three operations. */
export interface ClientTableSpec<Row> {
  /** The haystacks the search box matches against, already stringified. */
  search: (row: Row) => string[];
  /** `true` keeps the row. Called once per declared filter that has a value. */
  filter: (row: Row, name: string, value: string) => boolean;
  /**
   * The value the named column sorts on. `null` means *this row has no such
   * value*, which is NOT zero and NOT the empty string — see below.
   */
  sortValue: (row: Row, key: string) => string | number | null;
}

/**
 * Search → filter → sort → slice, in that order, over rows already in hand.
 *
 * `total` is the count AFTER search and filters and BEFORE the slice, because
 * that is the number `DataTable`'s footer means by *"of N"*.
 *
 * ⚠ **`matched` IS THE WHOLE FILTERED SET, AND IT EXISTS SO A FOOTER CAN FOOT
 * (`DEF-LED-6717`).** A table that prints a Total has to add up the rows the
 * reader is being told about — everything the search and the filters kept, not
 * just the slice on screen and not a neighbouring figure that happens to be
 * close. The Revenue-by-service table printed `kpis.billed` under rows summed
 * on a different basis, and the Product Owner photographed `$50.00` of rows
 * above a Total of `$0.00`. CLAUDE.md's `NFR-3` paragraph states the rule this
 * field serves: the total and the rows are ONE aggregate over ONE filtered set,
 * one of them windowed.
 *
 * It is ADDITIVE — `page` and `total` are byte-for-byte what they were — so no
 * existing caller changes behaviour by its arrival.
 */
export function clientPage<Row>(
  rows: readonly Row[],
  state: TableRequestState,
  spec: ClientTableSpec<Row>,
): { page: Row[]; total: number; matched: Row[] } {
  const term = state.q.trim().toLowerCase();
  let out = rows.filter((row) => {
    // Two characters is `SEARCH_MIN_CHARS`, the same floor the shared debouncer
    // applies before it will issue a request — so a list that searches here and
    // a list that searches on the server narrow at the same keystroke.
    if (term.length >= 2 && !spec.search(row).some((field) => field.toLowerCase().includes(term))) {
      return false;
    }
    // OQ-306 — a multi-select dimension (`service`) holds several values and
    // keeps a row matching ANY of them; every other dimension is a list of one.
    return Object.entries(state.filters).every(([name, value]) =>
      value === "" ? true : filterValueList(name, value).some((one) => spec.filter(row, name, one)),
    );
  });
  out = [...out].sort((a, b) => {
    const left = spec.sortValue(a, state.sort);
    const right = spec.sortValue(b, state.sort);
    // ⚠ A MISSING VALUE SORTS LAST IN BOTH DIRECTIONS. "No due date recorded"
    // is not "due in year zero", and a dash at the top of an ascending list
    // reads as the earliest date there is — which on a debtor list is the row a
    // clerk would chase first.
    if (left === null && right === null) return 0;
    if (left === null) return 1;
    if (right === null) return -1;
    const order =
      typeof left === "number" && typeof right === "number"
        ? left - right
        : String(left).localeCompare(String(right));
    return state.dir === "desc" ? -order : order;
  });
  const from = (state.page - 1) * state.per;
  return { page: out.slice(from, from + state.per), total: out.length, matched: out };
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/06 Payments Page Blueprint.pdf p081–p086 rendered at 2.0 and read as IMAGES (B14 rule 42) · 12-governance/change-requests/CR-138-BRC07-payments-phase-4-debtors-and-money-out.md §3 P4.7/P4.9 · 04-docs/02-decisions/14-ui-conventions.md rules 12/13/14/15/16/43
// generated: 2026-09-23 by LANE P4-SCREENS-A
// checklist: A✔ B=n/a(no endpoint of its own) C✔ D=n/a E✔(three payments lists render it) F✔ G✔ H=n/a
// exceptions: (1) the IMPLEMENTATION is `AssetLifecycleTab.clientPage` moved here unchanged apart from its comments, so the assets lists it already drives cannot shift behaviour inside a rule-43 extraction · (2) this is a STAND-IN for server paging and says so twice; P4.1 and P4.2 are the tasks that delete its payments callers
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
