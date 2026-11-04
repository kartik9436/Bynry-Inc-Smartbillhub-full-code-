// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-003 (global search) — where a result row and a "View all"
//           link go.  Screens: shell chrome → S14 · S15 · S49 · S17 · S30 ·
//           S33 and the customers/requests lists
// Rules:    BR-SHL-005 AS AMENDED 2026-09-05 by CR-073 (fifteen groups,
//           per-group View all) ·
//           BR-SHL-011 (the list URL grammar `q/sort/dir/page/per/f.<name>`) ·
//           B14 rule 31 (a database id may be a ROUTE, never a visible value)
// Tests:    07-frontend/src/routing/searchDestinations.test.ts — asserts every
//           path here EQUALS the feature module's own route constant, in both
//           directions, so this second list cannot go stale
// ───────────────────────────────────────────────────────
// WHERE EACH SEARCH GROUP GOES, AS PLAIN DATA.
//
// `components/GlobalSearchResults.tsx` is a presentational component in
// `components/`, and the route constants it would otherwise need live in ten
// `features/` modules. Importing features from the shared component layer
// would invert the dependency for every screen that already imports the kit.
//
// **THIS IS A SECOND LIST AND IT CANNOT GO STALE**, which is the only thing that
// makes a second list acceptable — the same bargain `routing/sidebarDestinations.ts`
// struck and for the same reason. `searchDestinations.test.ts` asserts each path
// equals its feature's exported constant; move a route and forget this file and
// that suite fails naming the group.
//
// ⚠ **"VIEW ALL" OPENS THE MODULE'S OWN LIST WITH `?q=`, RATHER THAN A NEW
// RESULTS SCREEN.** That was this lane's call (12-governance/02-decision-log.md,
// 2026-09-03) and the reasoning is that BR-SHL-011's grammar already makes every
// list in the product searchable and shareable by URL: a dedicated results page
// would be a tenth screen that re-implements filtering, paging and column
// choice, all of which the list it would duplicate already has. Nothing is lost
// — the list counts properly, which is the one thing the ≤5 popover cannot do.
//
// Tenant-relative, like every route constant since path tenancy (PO 2026-08-10):
// this states the SCREEN, `tenantPath()` states which utility.

import type { SearchEntity } from "@/api/endpoints";

export interface SearchDestination {
  /** The module list "View all in ‹module›" opens, with `?q=` appended. */
  list: string;
  /** The row's own record, or null where the module has no detail screen. */
  detail: ((id: string) => string) | null;
}

export const SEARCH_DESTINATIONS: Record<SearchEntity, SearchDestination> = {
  premises: { list: "/premises", detail: (id) => `/premises/${id}` },
  units: { list: "/premises/units", detail: (id) => `/premises/units/${id}` },
  assets: { list: "/assets", detail: (id) => `/assets/${id}` },
  // ⚠ A master account has NO list of its own — it is an `accounts` row with
  // `kind='master'` (BR-CUS-068), and S17 has no master-only view. "View all"
  // therefore opens the Accounts list with the query applied, which shows both
  // kinds. The GROUP is still separate in the popover, which is the half the PO
  // asked for: a master account is findable without competing for one of the
  // five rows a regular-account group is capped at.
  master_accounts: { list: "/accounts", detail: (id) => `/accounts/${id}` },
  accounts: { list: "/accounts", detail: (id) => `/accounts/${id}` },
  customers: { list: "/customers", detail: null },
  // ⚠ `/billing/bills/{id}`, NOT `/billing/{id}`. `/billing/:tab` is the bills
  // screen's TAB route, so a uuid in that position resolves as a tab name and
  // the bill never opens — a dead link that `tsc` and every test would pass.
  bills: { list: "/billing", detail: (id) => `/billing/bills/${id}` },
  // ⚠ NO PAYMENT DETAIL SCREEN EXISTS. `/payments/:tab` is the tabbed payments
  // page and there is no `/payments/{id}` route, so a payment row opens the
  // Payments list rather than a URL that would resolve to a tab called by a
  // uuid. REPORTED rather than invented — a route is not a lane's to mint.
  payments: { list: "/payments", detail: null },
  requests: { list: "/requests", detail: (id) => `/requests/${id}` },

  // ── CR-073, 2026-09-05 — Work's four and Plans & Rates' two ─────────────
  //
  // ⚠ **EVERY ROUTE CONSTANT IN THE WORK MODULE IS WRITTEN WITHOUT `/:tenant`
  // AND THESE MATCH THAT, WHICH IS NOT A STYLE CHOICE.** `App.tsx` mounts the
  // module's screens as CHILDREN of a `:tenant` route and registers each with
  // `ROUTE.slice(1)`, so a path that carried its own tenant segment would
  // become `:tenant/:tenant/work/orders/…` and match NOTHING — the address
  // would fall through to the not-built-yet page. That is `DEF-WRK-4051`, it
  // made two shipped screens unreachable for three commits, and neither `tsc`
  // nor 44 unit cases could see it because every one of them mounted its
  // component under a pattern spelled out in its own test file. Only the
  // browser could, and did.
  work_orders: { list: "/work/orders", detail: (id) => `/work/orders/${id}` },
  work_order_templates: {
    list: "/work/templates",
    detail: (id) => `/work/templates/${id}`,
  },
  // ⚠ NO PARTS DETAIL SCREEN EXISTS — `App.tsx` serves `/work/parts` and
  // nothing below it. The row opens the parts register filtered to its own
  // part number, which is the `payments`/`customers` precedent above.
  // REPORTED rather than invented; a route is not a lane's to mint.
  parts: { list: "/work/parts", detail: null },
  // ⚠ **`detail: null` HERE IS A DELIBERATE DOWNGRADE AND NOT A MISSING
  // ROUTE.** A technician HAS a detail screen — `/work/crews/:slug`, addressed
  // by a SLUG derived from their name, never by an id — but a crew and a
  // contractor do NOT, and this is ONE group because `Work-023` is one table.
  // A `detail` here would have to resolve for people and 404 for the other two
  // kinds, and `resultPath` is given only the entity, the id and the label, so
  // it cannot tell them apart. A link that lands somewhere true for every row
  // beats one that is right two thirds of the time: every workforce row opens
  // the crews list filtered to that name, and the person's own page is one
  // click further on. `CR-073` §2a.
  workforce: { list: "/work/crews", detail: null },
  plans: { list: "/plans-rates/plans", detail: (id) => `/plans-rates/plans/${id}` },
  charges: {
    list: "/plans-rates/charge-codes",
    detail: (id) => `/plans-rates/charge-codes/${id}`,
  },
};

/** Where an entity's rows go, or `null` when this client has never heard of it.
 *
 * ⚠ **A SERVER ONE DEPLOY AHEAD IS A REAL CASE, NOT A HYPOTHETICAL.** The
 * groups grew from four to nine in one ruling and from nine to fifteen in the
 * next (`CR-073`); a sixteenth will arrive the same way,
 * and the browser holding an older bundle is the normal state of a deploy. The
 * union type says nine and the WIRE can say ten, so every lookup here is
 * guarded. The rows still render — dropping them silently is the SignupWizard
 * failure, where a front end holding its own copy of a server list left the
 * eleventh utility service off the screen with every test passing. */
function destinationFor(entity: SearchEntity): SearchDestination | null {
  return SEARCH_DESTINATIONS[entity] ?? null;
}

/** The "View all" href for a group: the module list carrying BR-SHL-011's `q`.
 *
 * An unknown group has no list to open, so its rows carry no "View all" — the
 * caller checks for null rather than being handed a link to nowhere. */
export function viewAllPath(entity: SearchEntity, query: string): string | null {
  const destination = destinationFor(entity);
  return destination ? `${destination.list}?q=${encodeURIComponent(query)}` : null;
}

/** Where a result row goes. Never null, so a row is never a dead click.
 *
 * Where the module HAS a detail screen the row opens that record. Where it does
 * not — customers and payments today — the row opens the module's own list
 * FILTERED TO THAT ROW'S IDENTIFIER (`?q=<label>`), which is the closest thing
 * to "open this record" the product can honestly offer: one row, on the screen
 * that owns it, rather than a list of everything or a route that does not
 * resolve. `label` is the identifier, never the id (B14 rule 31). */
export function resultPath(entity: SearchEntity, id: string, label: string): string {
  const destination = destinationFor(entity);
  // An entity this bundle does not know: send the reader to the ONE place that
  // can certainly find it — the search they already typed, on the dashboard.
  // Not a dead link, and not a guessed route built from an unknown entity name.
  if (!destination) return `/dashboard?q=${encodeURIComponent(label)}`;
  if (destination.detail) return destination.detail(id);
  return `${destination.list}?q=${encodeURIComponent(label)}`;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-003 (EP-SHL-01) + the PO ruling of 2026-09-03
// generated: 2026-09-03 by story-coder (universal-search lane)
// checklist: A✔ B=n/a C✔ D=n/a(paths as data) E✔ F✔ G✔ H=deferred(PO)
// exceptions: `customers` has `detail: null` — `CustomersListPage` is the only
//         customer screen in the product and no `/customers/{id}` route exists,
//         so the row opens the list rather than a 404. REPORTED, not invented.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
