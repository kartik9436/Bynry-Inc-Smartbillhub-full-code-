// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-WRK-4094 — four Work list screens seed from
//           `defaultRequestState(config)` and never look at the query string,
//           so `?q=` is silently dropped and every deep link into them lands
//           on an unfiltered list.
// Change:   CR-073 — universal search gained four Work groups, and a per-group
//           "View all" that opens `/work/…?q=<term>`. Without this the link
//           would promise a filter and deliver a full list.
// Rules:    BR-SHL-011 (the list URL grammar `q/sort/dir/page/per/f.<name>`) ·
//           BR-SHL-005 (per-group "View all")
// Tests:    07-frontend/src/routing/seedQueryFromUrl.test.ts ·
//           07-frontend/src/routing/searchDestinations.test.ts (the pin that
//           says every `?q=` destination is a screen which parses it)
// ───────────────────────────────────────────────────────

import type { TableRequestState } from "@/components/tableTypes";

/**
 * Seed a list screen's `q` from the URL, ONCE, at mount.
 *
 * ⚠ **WHY THIS IS NOT `parseTableParams`, WHICH ALREADY EXISTS AND DOES MORE.**
 * That helper reads the WHOLE grammar — `q`, `sort`, `dir`, `page`, `per` and
 * `f.<name>` — and the screens that use it also WRITE the URL back on every
 * change, so the address bar and the table stay one fact. The four Work lists
 * do neither: they hold their state locally and never call `setParams`. Giving
 * them the full parser would have them READ a page number, a sort and a filter
 * set they will never write back, so a reload would silently restore a state
 * the user had since left — the read-half hazard `ServiceRequestsListPage`
 * records for its embedded mode, in the other direction.
 *
 * **So this honours exactly one parameter, which is exactly the one a deep link
 * carries**, and the screens keep their local state for everything else. When
 * a Work list is next given full URL state it should adopt `parseTableParams`
 * and delete this call — the two are not meant to coexist on one screen.
 *
 * Pure, so it can be tested without a router and called from a `useState`
 * initialiser without re-seeding on every render.
 */
export function seedQueryFromUrl(
  state: TableRequestState,
  params: URLSearchParams,
): TableRequestState {
  const q = params.get("q");
  // An absent `q` and an empty `q` are the same instruction — show everything —
  // and neither is an error (BR-SHL-011: unknown or invalid values fall back,
  // never error).
  return q ? { ...state, q } : state;
}

export default seedQueryFromUrl;
