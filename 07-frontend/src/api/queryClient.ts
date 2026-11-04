// ── Trace ──────────────────────────────────────────────
// Component: FI-02 TanStack Query setup (B13 §2)
// Story:    US-TEN-003 (S62 checklist) · US-TEN-001 (S1/S112 catalog) · US-TEN-009 (S8 Settings entity keys) ·
//           US-RAT-001 · US-RAT-004 · US-RAT-008 · US-RAT-009 · US-RAT-010 (Plans & Rates entity keys)
//           Screens: S1, S8, S9, S10, S11, S12, S13, S62, S110–S114
//           AMENDED 2026-08-15 (tenant custom-fields lane): US-TEN-014 · US-SHL-015 (EP-TEN-09 · EP-SHL-07 — the S8 definition list and
//           the per-screen REGISTRY are two resources; a definition write invalidates both, a screen render pulls only the second)
// Rules:    BR-SHL-015 (display-only money — no client-side money state) · BR-TEN-015 (checklist read live) ·
//           BR-TEN-029 (reference-data counts computed live — cached only as a server answer, never a client counter) ·
//           BR-RAT-027 (the derived plan base is a SERVER answer that gets cached, never a client sum)
// ───────────────────────────────────────────────────────
// FI-02 (B13 §2): the ONE QueryClient and the entity key vocabulary used to
// invalidate it. Three defaults are LAW here, not taste:
//   1. NO optimistic updates on money mutations — the server is the only place
//      a money figure is ever computed (CLAUDE.md #2, BR-SHL-015). This file
//      therefore sets no `onMutate` cache-writing default anywhere; a screen
//      that wants one is writing money client-side, which is forbidden.
//   2. NO query-layer retry — client.ts already retries exactly the rows B12 r1
//      allows (429/502/503/504 on idempotent GETs). A second retry layer would
//      multiply requests past the per-tenant throttle (11b G12) and would also
//      retry the statuses the contract says to surface.
//   3. Errors pass through untouched: an ApiError reaches the component with
//      its `message_key`/`field_errors` intact, because that is what the UI
//      renders language from (TD-16).
//   4. ⛔ `DEF-SHL-6378` — A 401 IS ALSO SAID OUT LOUD, ONCE, FOR THE WHOLE APP.
//      The cache's `onError` OBSERVES every failed query and mutation and, for
//      a 401 only, announces that the session has ended; it swallows nothing,
//      so (3) is still true. The shell is the one listener and it replaces the
//      whole screen, which is why no page may treat a 401 as its own refusal —
//      the PO saw *"You don't have access to this."* on Payments as a System
//      Admin whose session had simply run out.
import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { isSessionExpired } from "@/api/client";
import { announceSessionExpired } from "@/api/sessionExpiry";

/** (4) above — the cache half. The transport announces too; the listener is idempotent. */
function announceIfSessionExpired(error: unknown): void {
  if (isSessionExpired(error)) {
    announceSessionExpired();
  }
}

// Reference/catalog reads change rarely and are ETag-cacheable server-side
// (11b G6); operational reads are re-fetched when a screen asks.
export const REFERENCE_STALE_MS = 5 * 60 * 1000;
export const DEFAULT_STALE_MS = 30 * 1000;

/**
 * S7's own window — **five minutes** (PO ruling 2026-08-19, decision 2).
 *
 * The PO's question was *"is time enough to reduce the refresh and compute"*,
 * and the answer was measured rather than guessed. `refetchOnWindowFocus` is
 * off, so at the 30 s default five nav clicks in a minute already cost ONE
 * call — the click-storm is already absorbed. The cost the default does NOT
 * absorb is the long tail: a clerk returning to the landing screen through the
 * day. At 30 s that is roughly **40 computes** over a working day of ~40
 * returns; at five minutes a glance every half hour costs **16**, and even
 * continuous five-minute polling caps at 96 per clerk-day.
 *
 * **It is a constant of its own and NOT a move of `DEFAULT_STALE_MS`**, which
 * governs every operational read in the product: a five-minute default would
 * make an account balance five minutes stale on a screen a clerk is editing.
 * This one screen originates no data and every figure on it is a rollup, which
 * is exactly why it can afford the window.
 *
 * ⚠ **The SERVER half of that ruling is not built** — a cache keyed on tenant +
 * as-of was authorised on the condition the screen states the cache AGE (the
 * PO's standing rule: *"where cached, state cache age rather than disagree with
 * Finance"*). Doing that honestly needs a shared cache backend this deployment
 * does not configure and an invalidation owner nobody has named, so it is
 * reported as not done rather than half-built. The client half stands alone
 * and weakens nothing: a browser cache entry that a person can refresh is not a
 * figure the product is asserting.
 */
export const DASHBOARD_STALE_MS = 5 * 60 * 1000;

export function createQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({ onError: announceIfSessionExpired }),
    mutationCache: new MutationCache({ onError: announceIfSessionExpired }),
    defaultOptions: {
      queries: {
        staleTime: DEFAULT_STALE_MS,
        retry: false, // see (2) above — the transport already owns retry policy
        refetchOnWindowFocus: false,
        // Errors surface to the component (A18 §4/§5 states), never swallowed.
        throwOnError: false,
      },
      mutations: {
        retry: false, // NEVER replay a mutation (CLAUDE.md #6: idempotency is the server's)
        throwOnError: false,
      },
    },
  });
}

/**
 * Entity keys for invalidation. One place, so a mutation in one screen can
 * invalidate another screen's read without either importing the other.
 */
export const queryKeys = {
  pricingPlans: ["public", "pricing-plans"] as const,
  subdomainCheck: (subdomain: string) => ["public", "subdomain-check", subdomain] as const,
  // CR-145-BRC08 — keyed by TENANT because the answer is per-utility and the
  // sign-in screen is the one place a person moves between tenants without a
  // reload: an unkeyed entry would show one utility's answer on another's door.
  signInOptions: (tenant: string) => ["public", "sign-in-options", tenant] as const,
  checklist: ["tenants", "checklist"] as const,
  session: ["auth", "session"] as const,
  me: ["me"] as const,
  // S8 Settings (US-TEN-005..012 · US-IDN-004..010 · US-MET-006). One key per
  // server resource, so a save in one tab invalidates exactly what it changed.
  companyProfile: ["settings", "company"] as const,
  // S8 Integrations (US-INT-001 · 013 · 018) — ONE key, because the endpoint
  // answers the whole grid in one document: every manifest joined to this
  // tenant's connection state. Splitting it would let the cards and the
  // category chips disagree about which tenant they describe.
  integrations: ["settings", "integrations"] as const,
  // CR-068 wave A — the customer portal's back office (CWP-069 · CWP-070) and
  // the guest front page (CWP-001). Three resources, three keys; a Branding
  // save invalidates the front page because that is what it changes.
  portalSettings: ["settings", "portal"] as const,
  portalBranding: ["settings", "portal", "branding"] as const,
  portalFront: ["portal", "front"] as const,
  // CR-068 wave D — the back office's three published-content lists.
  portalHelp: ["settings", "portal", "help"] as const,
  portalTips: ["settings", "portal", "tips"] as const,
  serviceCentres: ["settings", "reference-data", "service-centres"] as const,
  // S143 (US-INT-037): one document per provider — the rows and the choices
  // arrive together, so a save replaces the whole document from the server.
  integrationMappings: (key: string) => ["settings", "integrations", "mappings", key] as const,
  // S142 (US-INT-020): one PAGE of a connection's runs, keyed by the request
  // that produced it — a trace search and an outcome filter are different
  // questions and must never answer each other from cache.
  integrationRuns: (key: string, request: string) =>
    ["settings", "integrations", "runs", key, request] as const,
  // …and one RUN, which carries the two things the list may not (the items and
  // the provider's own words), so it is its own document and its own entry.
  integrationRun: (key: string, runId: string) =>
    ["settings", "integrations", "run", key, runId] as const,
  // CR-070 wave A — the Work shell's Orders tab (US-WRK-004): one PAGE of
  // `GET /work-orders`, keyed by the request that produced it, so a search
  // or a page turn is a different cache entry and never a stale one.
  // ⚠ **THE FILTERS ARE PART OF THE KEY (CR-070 wave G).** They were not, and
  // could not have been, before the dispatcher existed — wave A's list took
  // only `q`/`page`/`per`. Leaving them out now would serve a cached UNFILTERED
  // page the instant a dispatcher picked a chip, which reads as a filter that
  // silently did nothing: exactly the failure `BR-WRK-026`'s `400` on a seventh
  // filter exists to prevent, arriving through the cache instead of the wire.
  workOrders: (q: string, page: number, per: number, filters: Record<string, string> = {}) =>
    ["work", "orders", q, page, per, filters] as const,
  // The five tiles and the footer's denominator (CR-070 wave G).
  workKpis: () => ["work", "kpis"] as const,
  // US-WRK-011 — tenancy's areas, read through Work's seam.
  workAreas: () => ["work", "areas"] as const,
  // CR-070 wave I · Work-021's own read. A SEPARATE key from the list and from
  // the detail row, because the EDIT FORM is a different shape of the same
  // record: the list needs an area's NAME to draw a cell, the form needs its ID
  // to select an option. Sharing one key would let a list fetch populate the
  // form's cache with a row whose selects cannot post back what they show — and
  // it fails silently, which is `DEF-CUS-3653`'s shape.
  workOrderEdit: (orderId: string) => ["work", "orders", "edit", orderId] as const,
  // CR-070 wave I · the day's pins (US-WRK-029). Keyed by the SAME six filters
  // the list is keyed by, so switching to Map keeps the narrowing a dispatcher
  // has already made instead of silently widening it back to everything.
  workOrderMap: (q: string, filters: Record<string, string> = {}) =>
    ["work", "orders", "map", q, filters] as const,
  // CR-070 wave H · Work-008. Under the `["work"]` prefix so one bulk write
  // invalidates the detail, its checklist and its audit together — a tick
  // moves the header count, and three keys that had to be invalidated by hand
  // are three chances to forget one.
  workOrder: (orderId: string) => ["work", "order", orderId] as const,
  workOrderChecklist: (orderId: string) =>
    ["work", "order", orderId, "checklist"] as const,
  workOrderAudit: (orderId: string) => ["work", "order", orderId, "audit"] as const,
  workTemplatesPublished: () => ["work", "templates", "published"] as const,
  // A reference list this module filters on — `work_order_types`,
  // `work_priorities`. Under the `["work"]` prefix so one bulk write can
  // invalidate everything this screen reads with a single call.
  workLookup: (listCode: string) => ["work", "lookup", listCode] as const,
  // CR-070 wave C · Work-025. The prefix `["work", "parts"]` is what the Add
  // part modal invalidates after a successful POST, so the register redraws
  // with the new row without the screen re-implementing the fetch.
  workParts: (q: string, page: number, per: number, filters: Record<string, string> = {}) =>
    ["work", "parts", q, page, per, filters] as const,
  // CR-070 wave B — the approval queue (US-WRK-003, BR-WRK-007). A SEPARATE
  // key from `workOrders` above, and deliberately so: the two lists are
  // disjoint windows on one table (open work · finished work nobody accepted),
  // so accepting an order must expire this and not that.
  workAwaitingApproval: (page: number, per: number) =>
    ["work", "awaiting-approval", page, per] as const,
  // CR-070 wave D · Work-013 and Work-022. The prefix `["work", "templates"]`
  // is what Duplicate, Deactivate and Delete invalidate, so the LIST redraws
  // after an act pressed on the DETAIL — the two screens are one record seen
  // twice, and a stale count on the list is how *"published · draft ·
  // inactive"* starts lying.
  workTemplates: (q: string, service: string, page: number, per: number) =>
    ["work", "templates", q, service, page, per] as const,
  // CR-070 wave F · Work-023 and Work-024. The prefix `["work"]` is what the
  // skills wizard invalidates on save, because a proficiency change moves the
  // SKILLS cell on the crews list as well as the panel it was edited on — two
  // reads of one fact, and invalidating only the one in front of you is how
  // they disagree until a reload.
  workCrews: (q: string, page: number, per: number) =>
    ["work", "crews", q, page, per] as const,
  workTechnician: (slug: string) => ["work", "technician", slug] as const,
  workCertificationWatch: () => ["work", "certification-watch"] as const,
  workTemplate: (templateId: string) => ["work", "template", templateId] as const,
  workTemplateVersions: (templateId: string) =>
    ["work", "template", templateId, "versions"] as const,

  // DEF-SHL-4272 — the app shell's boot read: branding + display formats, open
  // to every signed-in role. Keyed under "shell" and NOT under "settings" on
  // purpose: it is not a settings resource, it is what a screen needs to draw
  // itself, and a key under "settings" would be swept by a broad settings
  // invalidation that has nothing to do with it. Saving on Settings → Regional
  // or → Company invalidates this key EXPLICITLY (see those tabs) so the
  // sidebar name and the date format change without a reload.
  shellDisplay: ["shell", "display"] as const,
  regionalSettings: ["settings", "regional"] as const,
  tenantServices: ["settings", "services"] as const,
  numberSeries: ["settings", "number-series"] as const,
  // S107 · DEF-1092 — what the tenant buys from BYNRY (plan, implementation
  // order, add-ons). Keyed under "settings" because that is where the screen
  // lives, and ONE key because the endpoint answers all three in one document
  // — splitting it would let the plan and the order disagree about which
  // tenant they describe. Nothing in the product writes this resource, so no
  // save invalidates it.
  subscription: ["settings", "subscription"] as const,
  securityPolicy: ["settings", "security-policy"] as const,
  // CR-155-BRC09 — the Audit log card on Settings → Security. A SEPARATE key
  // from the policy above, because a save invalidates this one (the save is
  // what puts a new row in it) while the policy read answers itself from the
  // mutation's own response.
  securityPolicyAudit: ["settings", "security-policy", "audit"] as const,
  // OQ-FLD-12797 — the field app's certificate pins, the card under the audit
  // card. Its own key: its save answers itself and moves nothing above it.
  fieldAppPins: ["settings", "security-policy", "field-app-pins"] as const,
  holidays: ["settings", "holidays"] as const,
  lookupCards: ["lookups"] as const,
  lookupEntries: (listCode: string, q: string, page: number, per: number) =>
    ["lookups", listCode, q, page, per] as const,
  tenantUsers: (page: number, per: number) => ["users", page, per] as const,
  rolesMatrix: ["roles"] as const,
  // BR-SHL-025: the caller's OWN A4 row — reference-cacheable, and the ONLY
  // permission read a non-admin can make (the /roles grid is admin-only).
  myPermissions: ["me", "permissions"] as const,
  // S8 → Notifications, the delivery/dispatch home (BR-TEN-041 #8, US-NOT-013).
  // Two keys and not one: a re-queue changes BOTH the counts and the list, and
  // one key would make a screen invalidate a read it did not change.
  outboundSummary: ["outbound", "summary"] as const,
  // CR-009 · the signed-in user's OWN in-app inbox (BR-NOT-019). ONE key, not
  // two, and that is the opposite call from the outbound pair above: the badge
  // and the list arrive in ONE response precisely so they cannot disagree, so
  // splitting the key would re-create the disagreement the endpoint avoids.
  // No user id in the key: the server derives the inbox from the session and
  // has no route that accepts one, and `queryClient.clear()` on sign-out
  // (BR-SHL-009) is what stops the next person seeing the last one's mail.
  inAppMessages: ["in-app-messages"] as const,
  // US-SHL-003 — the topbar search, keyed by the DEBOUNCED query. The query is
  // part of the key so re-typing a term a user has just searched is answered
  // from cache with no request; no user id, for the same reason the inbox
  // carries none — the server derives the tenant and the role from the session,
  // and `queryClient.clear()` on sign-out (BR-SHL-009) is what stops the next
  // person reading the last one's results.
  globalSearch: (q: string) => ["search", q] as const,
  // ⚠ **`page` IS PART OF THE KEY BECAUSE THE PAGE IS THE SERVER'S**
  // (`DEF-NOT-5746`). The dispatch queue used to ask for one page of fifty and
  // slice it again in the browser, so page two existed only in the footer's
  // arithmetic and there was nothing for a second key to hold. It pages through
  // `GET /outbound` now; without the page here, turning one would read the
  // previous page back out of cache.
  //
  // It DEFAULTS to 1 deliberately: `outboundQueue(50)` still spells the key the
  // queue opens on, so every caller that primes or invalidates the first page —
  // two suites do — keeps working without being rewritten.
  // DEF-NOT-10650 (1A) — and the VIEW, because *Needing attention* and *All
  // messages* are two different lists at the same page and size. It defaults
  // to the view the screen opens on, so `outboundQueue(50)` still spells it.
  outboundQueue: (per: number, page = 1, view = "attention") =>
    ["outbound", "queue", per, page, view] as const,
  /** Every page of the dispatch queue, at every size. A re-queue changes the
   *  COUNT as well as the row, so it invalidates the prefix and not one page. */
  outboundQueueAll: ["outbound", "queue"] as const,
  // CR-007 · SET-09 / SET-10. Two keys and not one, for the same reason the
  // outbound pair is two: publishing a version changes the DETAIL (versions,
  // preview, which variant is live) and it changes the CATALOG row's
  // "Last edited" and variant count. One key would make the detail screen
  // invalidate a list it did not change, and the list refetch on every
  // keystroke of the editor.
  templateCatalog: (q: string, category: string, sort: string, page: number, per: number) =>
    ["template-catalog", q, category, sort, page, per] as const,
  templateDetail: (code: string, variantId: string | null) =>
    ["template-catalog", "detail", code, variantId ?? "default"] as const,
  routes: ["routes"] as const,
  cycles: ["cycles"] as const,
  // S64/S66/S69/S70/S71 — one key per rule page, so saving one never
  // invalidates another's read (they are five independent documents).
  rulePage: (slug: string) => ["settings", "rule-page", slug] as const,
  // DEF-901 / BR-TEN-162 — WHICH SERVICES THIS TENANT ACTUALLY METERS, read
  // from its own asset estate. Keyed under "assets" and not under "settings",
  // because that is the resource it is: adding a meter must invalidate it, and
  // saving a threshold must not.
  meteredServices: ["assets", "metered-services"] as const,
  // DEF-902 / BR-TEN-161 — how far behind the platform fixture ONE reference
  // list is. Under the "lookups" prefix so an add/delete on the list (which
  // invalidates ["lookups"]) refreshes the gap with it: minting the missing
  // row by hand must clear the notice that asked for it.
  lookupFixtureGap: (listCode: string) => ["lookups", listCode, "fixture-gap"] as const,
  // EP-TEN-09. The S8 management list and the per-screen REGISTRY are two
  // different resources: a definition write invalidates both, but a screen
  // rendering `<CustomFields>` must never pull the whole management table.
  customFields: (query: string) => ["custom-fields", "definitions", query] as const,
  // CR-161-BRC10 W1 — the one slot list, served by the server.
  customFieldSlots: () => ["custom-fields", "slots"] as const,
  customFieldRegistry: (entity: string, screen: string, mode: string) =>
    ["custom-fields", "registry", entity, screen, mode] as const,
  // S61 audit viewer. The window (hot vs archive) is part of the key because
  // it is part of the QUERY (BR-AUD-013) — not a display toggle over one result.
  auditLog: (query: string) => ["audit-log", query] as const,
  auditEntry: (entryId: string) => ["audit-log", "entry", entryId] as const,
  // CR-067 B2: the technical record is a SEPARATE System-Admin-only read, so it
  // is a separate key — an Executive's cache must never hold it, and a 403 for
  // one caller must not be cached as the answer for the row itself.
  auditDiagnostic: (entryId: string) => ["audit-log", "entry", entryId, "diagnostic"] as const,
  // S9–S13 Plans & Rates. Each tab's list is keyed by its serialized request
  // state, so a filter change is a different query rather than a mutation of
  // one cached page. The four catalogs are independent resources: publishing a
  // plan must not invalidate the tax list, and does not.
  plans: (query: string) => ["plans", query] as const,
  plan: (planId: string) => ["plans", "detail", planId] as const,
  //: CR-087 D5 / PRB-21 — the units a plan prices, PAGED. The page number is
  //: part of the key because the server pages this read: a key that ignored it
  //: would serve page 1's rows under page 3's heading, which is the shape of a
  //: list that silently stops at fifty.
  planUnits: (planId: string, page: number) => ["plans", "units", planId, page] as const,
  //: PO ruling 2026-09-18 — what moved underneath a plan. Keyed by PAGE
  //: like every other server-paged read, so a page a clerk walked back to
  //: is served from cache rather than re-counted.
  planBoundChanges: (planId: string, page: number) =>
    ["plans", "bound-changes", planId, page] as const,
  rateSchedules: (query: string) => ["rate-schedules", query] as const,
  rateSchedule: (tariffId: string) => ["rate-schedules", "detail", tariffId] as const,
  // DEF-434 — RAT-03 step 4's impact analysis. Under the same `["rate-schedules"]`
  // head as the detail, so filing a version invalidates the figures that were
  // computed BEFORE it; and keyed by the effective date too, because the "before"
  // side is the version in force THEN (BR-RAT-007), so two dates are two answers.
  rateScheduleImpact: (tariffId: string, effectiveFrom: string) =>
    ["rate-schedules", "impact", tariffId, effectiveFrom] as const,
  // `CR-130-BRC07` §3 — RAT-03 step 3's **Based on** list. Keyed by BOTH the
  // service being priced and the basis, because they are two different
  // questions with two different answers: the usage list is a subset of the
  // charge list, and caching one under the other would offer a clerk services
  // the server will refuse.
  percentBasisOptions: (service: string, basis: string) =>
    ["rate-schedules", "percent-basis-options", service, basis] as const,
  charges: (query: string) => ["charges", query] as const,
  taxes: (query: string) => ["taxes", query] as const,
  // CR-013 row 8 / row 14 — the two reads behind the shared definition detail
  // (BR-RAT-084). Keyed under the same head as their list, so saving a charge
  // invalidates both the catalog and the open detail with one `["charges"]`.
  charge: (chargeId: string) => ["charges", "detail", chargeId] as const,
  //: CR-087 · CHG-01's Plans tab — which plans this charge code reaches, PAGED.
  //: The page number is part of the key for `planUnits`' reason: the server
  //: pages this read, so a key that ignored it would serve page 1's rows under
  //: page 3's heading.
  chargePlans: (chargeId: string, page: number) =>
    ["charges", "plans", chargeId, page] as const,
  tax: (taxId: string) => ["taxes", "detail", taxId] as const,
  // CR-013 part 3 — §18 row 10 (the landing tab) and row 11 (the detail). Same
  // head/detail shape as the four catalogs above, for the same reason.
  discounts: (query: string) => ["discounts", query] as const,
  discount: (discountId: string) => ["discounts", "detail", discountId] as const,
  taxJurisdictions: ["tax-jurisdictions"] as const,
  rateChanges: (query: string) => ["rate-changes", query] as const,
  // S8 → Accounting (BR-BIL-067/069). The tenant's chart of accounts, read by
  // the GL-mapping picker. It is a REFERENCE read with no query of its own —
  // one key, so a re-point in the service panel and one in the tax panel share
  // a single cached chart instead of fetching it twice.
  ledgerAccounts: ["ledger", "accounts"] as const,
  // S41's dual-basis remittance table (`GET /finance/taxes`). Keyed by the
  // PERIOD because the endpoint requires one and its money columns are of that
  // period. The S71 settings table reads the same query for the tenant's list
  // of tax AUTHORITIES and their 2200-nn account codes — the row SET is the
  // chart's tax-payable accounts and does not vary with the window, so the two
  // consumers share one cached answer rather than fetching the list twice.
  remittanceByAuthority: (period: string) => ["finance", "taxes", period] as const,
};

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07; co-packets EP-TEN-03@d5f8c32 · EP-RAT-01@6304a38 · EP-RAT-02@0b56fac · EP-RAT-03@7d1a8ef · EP-RAT-04@f69a661)
// generated: 2026-08-09 by story-coder v1 (W0 Settings screens lane added the S8 entity keys) · AMENDED 2026-08-09 by story-coder (frontend integration lane: rule-page, permission and S61 keys) · AMENDED 2026-08-09 by story-coder (W1 Plans & Rates entity keys) · AMENDED 2026-08-11 by story-coder (S8 Accounting / GL mapping lane — `ledgerAccounts`, the chart the BR-BIL-067 and BR-BIL-069 pickers share) · AMENDED 2026-08-15 by story-coder (settings-screens lane — `remittanceByAuthority`, the S41 read the S71 per-authority remitting-basis table borrows for its authority list) · AMENDED 2026-08-15 by story-coder (tenant custom-fields lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: trace_lint✔ (227 stories, 459 BR refs, 60 OQs) run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ (399+111 baseline unchanged and green; this packet adds 88 passing + 19 todo across 5 files — every todo is browser-interaction, server/RLS-isolation or unbuilt-neighbour-module scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
