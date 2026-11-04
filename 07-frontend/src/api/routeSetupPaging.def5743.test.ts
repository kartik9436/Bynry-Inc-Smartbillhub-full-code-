// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-MET-5743 — route setup fetches the whole tenant and pages it in
//          the browser. PO report 2026-09-18: *"Route setup becomes unusable at
//          5,000–10,000 premises"*.
// Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
//          BR-SHL-011 (q/sort/dir/page/per) · BR-SHL-033 (a long picker is a
//          SEARCH picker) · CLAUDE.md hard-won law 7 (prove a guard goes RED)
// Screens: SET-06 step 2 · SET-07 step 2 · S26 · S27
// ───────────────────────────────────────────────────────
/**
 * **THE REQUEST IS THE ASSERTION, NOT THE RENDER.**
 *
 * ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, ASKED FIRST (law 7, habit 2).** A
 * test that counts rendered rows cannot tell server paging from a client slice:
 * fifty rows appear either way. A test that asserts a picker "shows results"
 * passes when it shows the first fifty of four thousand — which is the defect,
 * not the fix. So every case here counts what went over the wire, or proves a
 * row that CANNOT be on page one is still reachable.
 *
 * ⚠ **THE STUB BEHAVES LIKE THE SERVER, AND THAT IS LOAD-BEARING.** It holds
 * 4,000 rows and honours `q`, `page` and `per`. A stub that returned its whole
 * array whatever it was asked would pass over a screen that had gone back to
 * slicing in the browser — a fixture that cannot tell a working page from a
 * broken one, which is `DEF-CWP-3925`'s shape.
 *
 * **PROVED RED against the branch before the fix** (`caf716c13`):
 *   · `one page, not forty` — `listAll` made **4** requests over 4,000 routes
 *     where this asserts 1;
 *   · `the picker asks for a page` — the wrapper sent NO query at all, so
 *     `query` was `undefined` and every `page`/`per`/`sort` expectation failed;
 *   · `a match beyond page one` — the wrapper returned the envelope object
 *     where an array was expected, and the screen's `.filter` threw.
 */
import { describe, expect, it } from "vitest";

import {
  getCycleRoutes,
  getRouteOptions,
  getRoutePremisesMembers,
  getRoutePremisesPicker,
  getRoutes,
  getRoutesPage,
} from "./endpoints";
import type { ApiClient } from "./client";

interface Recorded {
  path: string;
  query: Record<string, unknown> | undefined;
  search: URLSearchParams | null;
}

/**
 * A stub that PAGES, MATCHES and COUNTS the way the endpoint does.
 *
 * It reads the window out of `options.query` (how `getRoutesPage` asks) or out
 * of the path's own query string (how the premises picker asks), so one stub
 * serves both shapes without either wrapper being written to suit it.
 */
function server(rows: { id: string; code: string; name: string | null }[]): {
  client: ApiClient;
  calls: Recorded[];
} {
  const calls: Recorded[] = [];
  const client = {
    get: async (path: string, options?: { query?: Record<string, unknown> }) => {
      const [bare, queryString] = path.split("?");
      const search = queryString === undefined ? null : new URLSearchParams(queryString);
      calls.push({ path: bare, query: options?.query, search });

      const read = (name: string): string | undefined => {
        const fromOptions = options?.query?.[name];
        if (fromOptions !== undefined && fromOptions !== "") {
          return String(fromOptions);
        }
        return search?.get(name) ?? undefined;
      };

      const term = (read("q") ?? "").toLowerCase();
      const matched =
        term.length < 2
          ? rows
          : rows.filter(
              (row) =>
                row.code.toLowerCase().includes(term) ||
                (row.name ?? "").toLowerCase().includes(term),
            );
      // ⚠ NO WINDOW MEANS EVERY MATCHING ROW — `NFR-5`, and the one behaviour
      // `Select all {n}` and the members read both depend on.
      const perRaw = read("per");
      const per = perRaw === undefined ? matched.length : Number(perRaw);
      const page = Number(read("page") ?? 1);
      return {
        data: {
          count: matched.length,
          next: null,
          previous: null,
          results: matched.slice((page - 1) * per, page * per),
        },
        status: 200,
        headers: new Headers(),
      };
    },
  } as unknown as ApiClient;
  return { client, calls };
}

const route = (index: number) => ({
  id: `r${index}`,
  code: `RT-${String(index).padStart(4, "0")}`,
  name: index === 3999 ? "Willow Bend spur" : `Route ${index}`,
});

const FOUR_THOUSAND = Array.from({ length: 4000 }, (_unused, index) => route(index));

// ═══════════════════════════════════════════════════════════════════════════
// ONE PAGE, NOT FORTY
// ═══════════════════════════════════════════════════════════════════════════

describe("DEF-MET-5743 · the wire carries one page", () => {
  it("a route table asks for ONE page and is told the true total", async () => {
    const { client, calls } = server(FOUR_THOUSAND);

    const page = await getRoutesPage(
      { q: "", sort: "code", dir: "asc", page: 1, per: 50, filters: {} },
      client,
    );

    expect(calls).toHaveLength(1);
    expect(page.rows).toHaveLength(50);
    // The count is the LIST, not the page — the footer's "1–50 of 4,000".
    expect(page.total).toBe(4000);
  });

  it("⛔ the deprecated whole-list read still walks every page — which is the defect", async () => {
    const { client, calls } = server(FOUR_THOUSAND);

    const rows = await getRoutes(client);

    // ⚠ **THIS ASSERTS THE DEFECT, DELIBERATELY.** `listAll` is not capped and
    // must never be: a ceiling would be an `NFR-5` cap, and a truncating one
    // would be worse than the slowness. So it is still correct and still
    // expensive, and this case is what goes RED the day somebody "fixes" it by
    // stopping early — which would silently lose 3,000 routes.
    expect(rows).toHaveLength(4000);
    expect(calls.length).toBeGreaterThan(1);
    expect(calls.every((call) => call.path === "/routes")).toBe(true);
  });

  it("the premises picker sends the window and the ordering, in BR-SHL-011's grammar", async () => {
    const { client, calls } = server(FOUR_THOUSAND);

    await getRoutePremisesPicker(
      { areas: [], sort: "address_line", dir: "desc", page: 3, per: 100 },
      client,
    );

    expect(calls).toHaveLength(1);
    expect(calls[0].path).toBe("/routes/premises-picker");
    expect(calls[0].search?.get("page")).toBe("3");
    expect(calls[0].search?.get("per")).toBe("100");
    expect(calls[0].search?.get("sort")).toBe("address_line");
    expect(calls[0].search?.get("dir")).toBe("desc");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// NO SILENT TRUNCATION
// ═══════════════════════════════════════════════════════════════════════════

describe("DEF-MET-5743 · a picker never shows a truncated set that looks complete", () => {
  it("finds a match that lives on page eighty, because the SERVER matched it", async () => {
    const { client, calls } = server(FOUR_THOUSAND);

    const found = await getRouteOptions("Willow", client);

    expect(calls).toHaveLength(1);
    // Row 3,999 of 4,000 — a client-side filter over page one would return
    // nothing here and the clerk would be told the route does not exist.
    expect(found.options).toHaveLength(1);
    expect(found.options[0].label).toBe("RT-3999 · Willow Bend spur");
    expect(found.total).toBe(1);
    expect(found.hasMore).toBe(false);
  });

  it("says when it is NOT showing everything, instead of looking complete", async () => {
    const { client } = server(FOUR_THOUSAND);

    const everything = await getRouteOptions("", client);

    expect(everything.options).toHaveLength(50);
    expect(everything.total).toBe(4000);
    // ⚠ The one field that separates "here are the routes" from "here are the
    // first fifty of four thousand". A picker with no such field cannot say so
    // and therefore lies by omission.
    expect(everything.hasMore).toBe(true);
  });

  it("B14 rule 31 — the option's visible text is the CODE, never the id", async () => {
    const { client } = server(FOUR_THOUSAND.slice(0, 3));

    const options = (await getRouteOptions("", client)).options;

    for (const option of options) {
      expect(option.label).not.toContain(option.value);
      expect(option.label.startsWith("RT-")).toBe(true);
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// THE TWO WHOLE-SET READS, AND WHY EACH IS ALLOWED
// ═══════════════════════════════════════════════════════════════════════════

describe("DEF-MET-5743 · re-opening an edit reads the WHOLE membership", () => {
  it("a route's own members come back complete and in ONE request", async () => {
    const { client, calls } = server(FOUR_THOUSAND.slice(0, 900));

    const members = await getRoutePremisesMembers("route-1", "water", client);

    // ⚠ **COMPLETE IS THE POINT.** The commit sends `premises_ids` as the whole
    // membership, so a seed that stopped at a page would REMOVE every member
    // past it the moment the clerk pressed Save.
    expect(members).toHaveLength(900);
    expect(calls).toHaveLength(1);
    expect(calls[0].search?.get("members")).toBe("1");
    expect(calls[0].search?.get("route_id")).toBe("route-1");
    // No `per` — bounded by the ROUTE, and never capped.
    expect(calls[0].search?.get("per")).toBeNull();
  });

  it("a cycle's own routes come back complete, following count past the page", async () => {
    const { client, calls } = server(FOUR_THOUSAND.slice(0, 1200));

    const routes = await getCycleRoutes("cycle-1", client);

    expect(routes).toHaveLength(1200);
    // Two requests at `per=1000` — it FOLLOWS `count` rather than trusting one
    // page, for the same reason: a cycle silently missing its 1,001st route
    // would be saved without it.
    expect(calls).toHaveLength(2);
    expect(calls[0].query?.["f.cycle"]).toBe("cycle-1");
  });
});
