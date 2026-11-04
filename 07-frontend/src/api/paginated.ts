// ── Trace ──────────────────────────────────────────────
// Component: FI-01 typed endpoint wrappers (B13 §2) — the ONE description of
//            the list envelope every paged GET in this product answers with.
// Story:    DEF-WRK-4119 · DEF-WRK-4119 · DEF-AST-4120 — three screens rendered
//           empty over rows the server had returned, because each described the
//           reply BY HAND and each description was wrong.
// Rules:    CLAUDE.md hard-won law 5 (one source, derive views on demand) ·
//           hard-won law 1 (a comment claiming a guarantee is not the
//           guarantee) · law 7's *incapable of failing* clause
// Tests:    src/api/paginated.test.ts (its own cases) ·
//           src/features/work/workEndpoints.envelope.test.ts (against the
//           RECORDED server reply, not an invented one)
// Impacts:  src/api/endpoints.ts (re-exports `Paginated` from here) ·
//           src/features/work/workEndpoints.ts ·
//           10-scripts/gates/g114_list_envelope.py (fails a second description)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY THIS FILE EXISTS, IN ONE SENTENCE: A HAND-WRITTEN RESPONSE TYPE IS
// CHECKED AGAINST NOTHING.**
//
// On 2026-09-05 three shipped Work screens drew an empty table over rows the
// API had returned. `Work → Rules` said *"No results for ''."* over the seven
// rules a supervisor had just created; `Settings → Labour rates` did the same
// over four; the asset detail's Maintenance history showed a dash in every
// WORK ORDER cell. `tsc`, eslint, 116 gates, 9,810 backend tests and 367
// front-end test files were green over all three, and stayed green, because
// **the only description of the wire was a TypeScript interface somebody typed
// out, and TypeScript cannot check an interface against a live response.**
//
// ⚠ **THE MISTAKE WAS NOT A TYPO — IT WAS READING ONE LAYER TOO LOW, AND THAT
// IS WHY IT LOOKED RIGHT.** Every list view in this product is
//
//     return Response(_envelope(request, selectors.<something>_page(...)))
//
// and `_envelope` (`apps/work/api.py`) BUILDS A FRESH DICT:
//
//     {"count": …, "next": …, "previous": …, "results": result["rows"]}
//
// The selector it wraps returns `{rows, page, per, total, pages}`. So a lane
// that opened `selectors.py` — the right file, the obvious file, the file the
// row shape genuinely lives in — and transcribed the dict it found there wrote
// a type that is a **perfect description of the layer below the boundary** and
// a complete fiction about the wire. `query.data?.rows` is then `undefined`,
// `undefined ?? []` is a legal empty array, and the screen renders its own
// *no results* state with total confidence.
//
// ⚠ **AND `_envelope` DISCARDS EVERY OTHER KEY**, which is a second way to lose
// data silently: `asset_work_orders` set `result["maintenance_index"]` and then
// handed `result` to `_envelope`, which never copied it. Two call sites in that
// same file spell out `{**_envelope(request, result), "counts": …}` precisely
// because they hit this and noticed. The third did not.
//
// ── SO THE RULE THIS FILE ENFORCES ─────────────────────────────────────────
// **A screen never describes a paged reply. It calls `readListPage` and gets
// rows and a total.** There is one description of the envelope in this
// repository and it is `Paginated` below; `g114_list_envelope.py` fails the
// build when a second one appears.
//
// ⚠ **AND THE GUARD IS AT RUNTIME AS WELL AS IN THE TYPES, BECAUSE THE TYPES
// ARE THE THING THAT FAILED.** `readListPage` ASSERTS the envelope it was
// promised. That is the whole difference between this bug and a visible one:
// the failure mode being cured is *a missing key reads as an empty list*, so a
// helper that merely destructured `body.results` would reproduce it exactly one
// layer further in. A wrong shape now throws, by name, naming the path and the
// keys that did arrive — which a person reads in the console in five seconds
// and which `readListPage`'s own tests pin.
import { api } from "./client";
import type { ApiClient } from "./client";

/**
 * The DRF list envelope — `core.pagination.StandardPagination`, and the shape
 * `apps/work/api.py::_envelope` builds by hand for the modules that page in
 * their selectors.
 *
 * ⚠ **THIS IS THE ONLY PLACE THESE FOUR NAMES ARE WRITTEN.** Every other file
 * imports it. `PAGINATED_KEYS` below is the same fact as data, so the runtime
 * guard and the gate cannot drift from the type.
 */
export interface Paginated<Row> {
  count: number;
  next: string | null;
  previous: string | null;
  results: Row[];
}

/** `Paginated`'s keys as data — read by `assertPaginated` and by `G114`. */
export const PAGINATED_KEYS = ["count", "next", "previous", "results"] as const;

/**
 * What a table actually wants: the rows, and the TRUE total so that
 * *"Showing 1–50 of N"* is a true sentence.
 *
 * Deliberately NOT the envelope. A screen that never sees `results` cannot
 * mis-spell it, and a screen that never sees `next` cannot invent paging the
 * server is already doing.
 */
export interface PagedRows<Row> {
  rows: Row[];
  total: number;
}

/** The error `assertPaginated` raises. Named so a test can assert the class
 *  rather than a message, and so a console reader knows this is OUR check
 *  firing rather than a network fault. */
export class ListEnvelopeError extends Error {
  readonly path: string;
  readonly received: string[];
  constructor(path: string, received: string[]) {
    super(
      `${path} did not answer the list envelope. Expected {${PAGINATED_KEYS.join(", ")}}; ` +
        `received {${received.join(", ") || "nothing"}}. ` +
        `A reply carrying \`rows\`/\`per\`/\`pages\` is the SELECTOR's dict — the view wraps it ` +
        `in _envelope() before it reaches the wire (DEF-WRK-4119).`,
    );
    this.name = "ListEnvelopeError";
    this.path = path;
    this.received = received;
  }
}

/**
 * Prove the body really is the envelope, then hand back rows and total.
 *
 * ⚠ **IT CHECKS `results` AND `count` AND NOT MERELY TRUTHINESS.** An empty
 * page is `{count: 0, results: []}` and is perfectly valid — so the test is
 * *is `results` an array*, never *does it have anything in it*. Confusing those
 * two is how a zero-result assertion passes over a page that never loaded.
 */
export function unwrapPage<Row>(path: string, body: unknown): PagedRows<Row> {
  const bag = (body ?? {}) as Record<string, unknown>;
  if (!Array.isArray(bag.results) || typeof bag.count !== "number") {
    throw new ListEnvelopeError(path, Object.keys(bag));
  }
  return { rows: bag.results as Row[], total: bag.count };
}

/** A 2xx with no body where the contract promises one is a server bug (B12 r1). */
function requireBody<T>(path: string, data: T | null): T {
  if (data === null) {
    throw new Error(`empty body from ${path} where the contract promises one`);
  }
  return data;
}

/**
 * **THE ONE READER OF A PAGED LIST.** Give it a path and the query a screen
 * wants; it returns `{rows, total}`.
 *
 * `query` is passed through untouched apart from dropping `undefined`, so a
 * caller keeps BR-SHL-011's grammar (`q`, `page`, `per`, `f.<name>`) without
 * this helper needing to know any of it.
 */
export async function readListPage<Row>(
  path: string,
  query: Record<string, string | number | boolean | undefined> = {},
  client: ApiClient = api,
): Promise<PagedRows<Row>> {
  const response = await client.get<Paginated<Row>>(path, { query });
  return unwrapPage<Row>(path, requireBody(path, response.data));
}

/**
 * The same read, for a route that carries EXTRA facts beside the page.
 *
 * ⚠ **THIS EXISTS BECAUSE `_envelope` THROWS THE EXTRAS AWAY AND THE SERVER
 * HAS TO PUT THEM BACK BY HAND** (`{**_envelope(request, result), "counts": …}`).
 * A caller that needs one gets the whole body beside the unwrapped rows, so it
 * reads `body.maintenance_index` from the SAME object the rows came out of and
 * cannot end up describing a second shape to get at it.
 */
export async function readListPageWith<Row, Body = Record<string, unknown>>(
  path: string,
  query: Record<string, string | number | boolean | undefined> = {},
  client: ApiClient = api,
): Promise<PagedRows<Row> & { body: Body }> {
  const response = await client.get<Paginated<Row> & Body>(path, { query });
  const body = requireBody(path, response.data);
  return { ...unwrapPage<Row>(path, body), body: body as Body };
}
