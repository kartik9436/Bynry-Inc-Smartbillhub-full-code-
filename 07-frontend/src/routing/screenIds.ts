// ── Trace ──────────────────────────────────────────────
// Change:  CR-016 ADDENDUM — "EVERY SCREEN CARRIES ITS ID, VISIBLE" (PO,
//          2026-08-19), verbatim: *"Cr16 - I want you to give sreen Id to each
//          and Every screen and for time bing also display that as a tag -
//          right bottom for every UI screen so that we know which scren has a
//          problem - enrure engineer the screen IDs"*
// Defects: DEF-137 — *"S113 has no owning story, and screens do not carry
//          their own id in the frontend, so no gate can [check coverage]"*.
//          This file is the second half that defect says is missing.
// Rules:   A1 `04-docs/01-spec/01-screen-inventory.md` ALLOCATES every S-id ·
//          CLAUDE.md "Use A1 as the ticket vocabulary; never renumber" ·
//          CLAUDE.md hard-won law 8 ("every screen needs a story") ·
//          `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html` line 8830 (the
//          bottom-right badge) and lines 9195–9290 (its own id function)
// ───────────────────────────────────────────────────────
// THE ONE PLACE A SCREEN SAYS WHICH SCREEN IT IS.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THERE ARE TWO VOCABULARIES AND THEY DO NOT RECONCILE. THIS TABLE HOLDS
//   BOTH, ON PURPOSE, AND INVENTS NEITHER. ONLY ONE OF THEM IS RENDERED.
// ══════════════════════════════════════════════════════════════════════════
// **A1 uses `S1`–`S114`.** Every defect row, every story's `screens:`
// frontmatter, `13a-screen-component-map.md` and `g25_screen_coverage.py` all
// speak it. It is the ticket vocabulary and CLAUDE.md says it is never
// renumbered.
//
// **r10's own badge uses a MODULE-PREFIXED scheme** — `DSH-01`, `PLN-01`,
// `RAT-01`, `CHG-01`, `PLN-01.charges`. That is what the Product Owner reads
// off a prototype screenshot, and it is what every screenshot sent so far has
// carried.
//
// **They are not two names for one thing, and no mapping table existed
// anywhere in this repo before this file.** CLAUDE.md records why: A1 was
// extracted from r9, r10 redrew the product, and *"where A1's screen
// description contradicts r10, r10 is right and the spec is stale — file it,
// don't follow it."* Re-extraction never happened. So a screen can have an A1
// row, an r10 badge, BOTH, or NEITHER.
//
// Therefore each row carries `{ a1, r10 }` and either may be `null`. A
// single-string design would have forced a choice this lane is not allowed to
// make. **Nothing here adds an r10-style id to A1 or an S-id to r10** — both
// files stay authorities and this is the third artefact that maps between them.
//
// ⚠ **WHICH ONE THE USER SEES IS A PO RULING, 2026-08-19**, verbatim:
//
//     *"Keep S series for your reference for User and Product manager
//      reference assign tags that are visible on screen those should be as per
//      modules how we are using in r10"*
//
// So **the visible tag renders the r10 id and nothing else**, and the S-id
// stays internal — engineering and PM reference, never rendered. It does not
// disappear: it is still what a defect row, a story's `screens:` frontmatter
// and `g25_screen_coverage.py` resolve, so it rides in the DOM as
// `data-screen-a1` beside `data-screen-id`, and it is still half of this
// table. Only the RENDER narrows. (An earlier draft of this lane showed
// `S7 · DSH-01`; that was superseded by the ruling above before it shipped.)
//
// ⚠ **A SCREEN WITH NO r10 ID THEREFORE DRAWS NO TAG, AND THAT IS THE
//   FINDING** — the same rule A1 gets: an absent id is reported, never
//   invented. Putting `PRM-09` on a screen because the pattern suggests it
//   would have someone filing a defect against an id no authority defines. The
//   rows below name every one of them, and the gate counts them.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THE ids MEAN, AND WHAT IS DELIBERATELY *NOT* MINTED
// ══════════════════════════════════════════════════════════════════════════
// * **`a1` is quoted from A1 and never invented.** A screen A1 does not
//   allocate carries `a1: null` and a `note` saying so. That absence is the
//   finding — law 8's "every screen needs a story" — not a licence to take the
//   next free number out of the reserved S61–S90 block.
// * **A1 SUB-IDS ARE NOT MINTED EITHER.** r10 extends a parent id for a tab
//   (`PLN-01.charges`), and this table follows that convention **for the r10
//   half only**, because r10 defines it. `S9.charges` would be a new entry in
//   a vocabulary that is not ours to extend, so a tab of S9 reads `S9` on the
//   A1 half and `PLN-01.charges` on the r10 half.
// * **Where A1 allocates DISTINCT ids to what is one route here** — Payments'
//   three tabs are S32/S33/S34, the signup wizard's five steps are S110–S114 —
//   `byParam` selects the right one from the URL. That is reading A1, not
//   extending it.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY A SECOND LIST OF PATHS, AND WHAT KEEPS IT HONEST
// ══════════════════════════════════════════════════════════════════════════
// The alternative — a `handle: { screenId }` threaded onto every route object
// in App.tsx — spreads the map across 60 route literals and no reader can see
// the whole thing. So the map is one table, and `screenIds.test.tsx` asserts it
// EQUALS App.tsx's own flattened route patterns, in order, in both directions:
// add a route and forget this file and the suite fails naming the path; delete
// one and it fails the same way. That is the discipline
// `routing/sidebarDestinations.ts` already runs on (and the G23/G25 register
// discipline behind it) — a second list is acceptable only when something
// refuses to let it drift.
//
// ORDER IS LOAD-BEARING for the same reason it is in App.tsx: `matchPath` is
// exact, but a static segment and a dynamic one of the same shape both match
// (`plans-rates/plans/new` and `plans-rates/plans/:planId`), so the first entry
// wins and the order here is App.tsx's order.
import { matchPath } from "react-router-dom";

/** A screen's two names. Either half may be absent; both absent is a finding. */
export interface ScreenIds {
  /** The id A1 allocates. Quoted, never invented. */
  readonly a1: string | null;
  /** The badge r10 draws bottom-right for the same surface. */
  readonly r10: string | null;
}

/** Why a route carries no screen id at all, so "none" is never a shrug. */
export type NoScreenReason =
  /** A `<Navigate>`: it renders no screen, it forwards to one. */
  | "redirect"
  /** The catch-all. It has no screen BECAUSE the address has no screen. */
  | "catch-all"
  /**
   * A SECOND APPLICATION ROOT with its own screen register. `/:tenant/portal/*`
   * serves the customer portal, whose screens carry `CWP-###` ids from CR-068
   * §9 — a series the PO placed deliberately outside both vocabularies this
   * table holds. `src/portal/routing/screenIds.ts` is that register, G82 reads
   * it, and `ScreenIdTag` YIELDS to the portal's own tag on these addresses
   * rather than blanking `<body>` under it.
   */
  | "own-register";

export interface ScreenRoute {
  /** The FULL route pattern, tenant segment included, exactly as App.tsx nests it. */
  readonly path: string;
  /** The pair this route resolves to when no param changes the answer. */
  readonly ids: ScreenIds;
  /** A1 or r10 numbers one param's values separately — pick by value. */
  readonly byParam?: {
    readonly param: string;
    /** `route` = a `:param` segment; `search` = a `?param=` query value. */
    readonly from?: "route" | "search";
    readonly values: Readonly<Record<string, ScreenIds>>;
  };
  /**
   * A `?param=` whose mere PRESENCE opens a DETAIL over a LIST at the same
   * address, so one route draws two screens and each has its own id.
   *
   * ⚠ **NOT `byParam`, AND THE DIFFERENCE IS WHY THIS FIELD EXISTS.** That one
   * maps a param's VALUES to ids, and the value here is a template code —
   * thirty-eight of them, one more on the day a class is seeded. Enumerating
   * them would be a list that goes stale silently, which is the failure
   * `previewSurfaces` one module over was written to avoid (PO 2026-09-07:
   * *"you are correct - dont use hard coding"*). What decides the screen is
   * whether the parameter is there AT ALL.
   *
   * `over` names the id this replaces, so a refinement stays pinned to ONE tab
   * of a route that resolves seven: without it, `?template=` on the
   * routes-and-cycles tab would silently relabel that screen too.
   *
   * ⚠ **IT DOES NOT DRAW r10's DOTTED SUFFIX, ON PURPOSE.** r10's own id
   * function is `s.tplView ? 'SET-10.' + s.tplView : 'SET-09'` (prototype line
   * 9280), so the prototype's detail badge carries the template key. Ours must
   * not: one of this screen's addresses is `?template=bill:<uuid>` — the OTHER
   * store's rows (CR-048 E9) — and a badge reading `SET-10.bill:0f3c…` puts a
   * database id on screen, which B14 rule 31 forbids in the PO's own words
   * (*"no Databse ID on screen - that is a rule"*). The PARENT is the screen;
   * the suffix was always data, and this is data we may not draw.
   */
  readonly whenPresent?: {
    readonly param: string;
    readonly from?: "route" | "search";
    /** The r10 id this refinement replaces — the row's list screen. */
    readonly over: string;
    readonly ids: ScreenIds;
  };
  /** r10's sub-id convention: this param's value extends the r10 id. */
  readonly subIdFrom?: { readonly param: string; readonly from?: "route" | "search" };
  /** Set only when the route deliberately shows no screen at all. */
  readonly noScreen?: NoScreenReason;
  /** Anything a reader would otherwise have to reconstruct. */
  readonly note?: string;
}

const NONE: ScreenIds = { a1: null, r10: null };

/**
 * ⚠ **THE PAYMENTS *SUMMARY* TAB DRAWS NO BADGE, AND BOTH WAYS OF GIVING IT
 * ONE ARE BLOCKED BY A RULE — `DEF-3480`, PUT TO THE PRODUCT OWNER, OPEN.**
 *
 * The Product Owner walked the deployed build and reported *"no screen IDs are
 * shown on Payment screens"*. They are right about what they saw: Record
 * payments draws `PAY-01`, Outstandings draws `PAY-02`, and the tab a clerk
 * LANDS on — bare `/payments` falls back to Summary — draws nothing at all.
 *
 * **THE ROW'S OLD NOTE SAID *"r10 draws no Summary badge"* AND THAT WAS NOT
 * TRUE, WHICH IS WHY THIS PARAGRAPH REPLACES IT (hard-won law 1).** r10's own
 * id function, at prototype lines 9252–9255, is
 *
 *     const map = { record:'PAY-01', outstanding:'PAY-02',
 *                   deposits:'PAY-03', imports:'PAY-05' };
 *     return map[s.payTab] || 'PAY-' + (s.payTab || '01');
 *
 * and its Summary tab sets `payTab: 'summary'` (line 11293). No map key
 * matches, so the fallback runs and r10's badge reads `PAY-summary` at
 * RUNTIME. What r10 does NOT do is declare that string anywhere.
 *
 * **AND THAT DISTINCTION IS THE WHOLE ANSWER, BECAUSE A GATE MADE IT.**
 * `PAY-summary` was written into this table and `g29_screen_ids.py` refused it:
 *
 *     /:tenant/payments claims r10 badge "PAY-summary" — that is not a badge
 *     r10 draws. An id no authority defines is an id nobody can look up when
 *     it appears in a bug report.
 *
 * G29 reads the literal badge strings out of r10's `sid` block, and `'PAY-'`
 * is a prefix rather than a badge. The comparison with `PLN-01.charges` does
 * NOT hold: `'PLN-01.' + s.planRatesTab` leaves the literal `PLN-01` in the
 * prototype, so the parent id is declared and only the tab suffix is computed.
 * Payments has no declared parent to hang a suffix on. The gate is right and
 * the value is reverted.
 *
 * **SO BOTH ROADS OUT ARE BLOCKED BY A RULE, AND NEITHER IS A LANE'S TO OPEN:**
 *
 *   1. **Render the A1 id** (`S32`) and the tab is never blank again. That
 *      reverses a PO ruling of 2026-08-19, verbatim: *"Keep S series for your
 *      reference for User and Product manager reference assign tags that are
 *      visible on screen those should be as per modules how we are using in
 *      r10"* — quoted in this file's header, implemented by `screenLabel`, and
 *      asserted by a named case in `screenIds.test.tsx`.
 *   2. **Mint `PAY-summary`** and G29 refuses it, in the words above, for the
 *      reason this table states about every other absence: an absent id is
 *      REPORTED, never invented.
 *
 * CLAUDE.md law 13 names *"a ruling that collides with a signed rule"* as one
 * of the three things that legitimately reaches the Product Owner, and this is
 * one. It is recorded in `12-governance/02-decision-log.md` with both options
 * and what each costs, so nobody re-derives it. **Until it is ruled, the row
 * below keeps `r10: null` and the tab keeps drawing nothing** — which is this
 * table's own rule, applied to itself.
 */

/**
 * EVERY ROUTED SCREEN IN THE PRODUCT, IN App.tsx's OWN ORDER.
 *
 * The `note` on a row with `a1: null` is the report: that screen is not in the
 * inventory, so no story owns it and no ticket can name it (hard-won law 8).
 */
export const SCREEN_ROUTES: readonly ScreenRoute[] = [
  // ── Public, no tenant ───────────────────────────────────────────────────
  { path: "/", ids: { a1: "S1", r10: "ONB-01" } },
  {
    path: "/pricing",
    ids: NONE,
    noScreen: "redirect",
    note: "redirects to `/`, which IS S1",
  },
  {
    // A1 numbers the five onboarding steps separately (S110–S114) and the step
    // is URL state (`?step=`, A9), so the tag follows the step the user is on.
    path: "/signup",
    ids: { a1: "S110", r10: "ONB-04.1" },
    byParam: {
      param: "step",
      from: "search",
      values: {
        "1": { a1: "S110", r10: "ONB-04.1" },
        "2": { a1: "S111", r10: "ONB-04.2" },
        "3": { a1: "S112", r10: "ONB-04.3" },
        "4": { a1: "S113", r10: "ONB-04.4" },
        "5": { a1: "S114", r10: "ONB-04.5" },
      },
    },
    note: "S113 is the step DEF-137 found unowned; it is US-TEN-021 now",
  },
  {
    path: "/signin-help",
    ids: { a1: null, r10: "ONB-05" },
    note:
      "NO A1 ID AND NO r10 BADGE. App.tsx says so in its own words — *\"the ruling " +
      "names this public path; A1 has no screen for it (S2's 'First time / Sign in' " +
      "fork is the nearest), and none is invented\"*. Reported, not minted." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `ONB-05`, MINTED in the register — r10 draws ONB-01..04 for this family.",
  },

  // ── Per-tenant, outside the shell ───────────────────────────────────────
  { path: "/:tenant/signin", ids: { a1: "S3", r10: "ONB-03" } },
  {
    // ── DEF-IDN-5653 · the forced password change (2026-09-17) ─────────────
    // A SIBLING OF SIGN-IN, not a child of the shell, and this row sits beside
    // sign-in's for that reason: `BR-IDN-022` gates every app screen behind it,
    // and while the flag is set the server refuses every read the shell boots
    // on, so the shell cannot render it even in principle.
    path: "/:tenant/change-password",
    ids: NONE,
    note:
      "NO A1 ID AND NO r10 BADGE, reported rather than minted (hard-won law 8). A1 has no " +
      "screen for the forced password change and r10 draws none — the prototype's ONB family " +
      "stops at sign-in. `US-IDN-002` is the story that owns the screen and it names no S-id " +
      "of its own. The address was live as a redirect target for eight days with nothing " +
      "behind it (`DEF-IDN-5653`), which is precisely what an unowned screen costs, so the " +
      "absence is written down here instead of a number being invented for it.",
  },
  {
    // ── CR-170-BRC10 · the forgot-password page (2026-10-05) ───────────────
    // A sibling of sign-in for the same reason the forced change is: public,
    // signed out, no shell. `ONB-06` is ALLOCATED in g29_allocated_badges.txt
    // in the commit that built it — the next number after `/signin-help`'s
    // `ONB-05`, in the onboarding/auth family.
    path: "/:tenant/forgot-password",
    ids: { a1: null, r10: "ONB-06" },
  },
  {
    // ── CR-188-BRC10 · the set-password page (2026-10-22) ────────────────
    // Where an emailed one-time sign-in link lands. Public, signed out, no
    // shell. `ONB-07` is ALLOCATED in g29_allocated_badges.txt in the commit
    // that built it — the next number after `ONB-06`.
    path: "/:tenant/set-password",
    ids: { a1: null, r10: "ONB-07" },
  },
  {
    // ── CR-190-BRC10 · the agreement link's page (2026-10-22) ──────────────
    // BESIDE the portal, never inside it (PO answer 4). Not a portal screen,
    // so CR-068 §9's `CWP-###` series (the PO's to allocate) does not number
    // it, and r10 draws no badge for it.
    path: "/:tenant/portal/agreements/:token",
    ids: NONE,
    note:
      "NO A1 ID AND NO r10 BADGE, reported rather than minted (hard-won law 8). The page a " +
      "click-to-accept agreement email opens (CR-190-BRC10). It is outside the signed-in " +
      "portal by ruling, so the CWP register does not hold it either.",
  },
  {
    // ── DEF-BIL-10531 · the bill email link's page (2026-10-22) ────────────
    // BESIDE the portal, like the agreement page, for the same reason.
    path: "/:tenant/portal/bill",
    ids: NONE,
    note:
      "NO A1 ID AND NO r10 BADGE, reported rather than minted (hard-won law 8). The page a " +
      "bill email's direct PDF link opens (DEF-BIL-10531, PO 2026-10-22 'b direct PDF link'). " +
      "Outside the signed-in portal, so the CWP register does not hold it either.",
  },
  {
    path: "/:tenant/portal/*",
    ids: NONE,
    noScreen: "own-register",
    note:
      "CR-068: the customer portal is a second application root with its own register " +
      "(src/portal/routing/screenIds.ts, `CWP-###` per CR-068 §9, read by G82). The portal " +
      "draws its own tag; this row says the address is not the staff app's to number.",
  },
  {
    // ── CR-070 wave J · the technician's phone (2026-09-05) ────────────────
    // A THIRD application root (`BR-WRK-045` — a web app, not a native shell),
    // a sibling of the staff shell exactly as the portal is. Its three routes
    // are mounted INSIDE `MobileApp`, so this map — which mirrors `App.tsx`
    // row for row — carries one row, and the phone's own register carries the
    // screens: `src/features/work/mobile/screenIds.ts`.
    path: "/:tenant/work/mobile/*",
    ids: NONE,
    noScreen: "own-register",
    note:
      "CR-070 wave J: the technician's phone is a second surface with its own register " +
      "(src/features/work/mobile/screenIds.ts, `WRK-21`/`WRK-22` minted in " +
      "g29_allocated_badges.txt — r10 draws WRK-01..18 for the DESKTOP dispatcher and " +
      "does not draw the phone at all). This row says the address is not the staff " +
      "shell's to number, and it must stay ABOVE the shell's own `/work` family or a " +
      "technician's phone is matched by the dispatcher.",
  },

  // ── Per-tenant, inside the shell ────────────────────────────────────────
  {
    path: "/:tenant",
    ids: NONE,
    noScreen: "redirect",
    note: "the tenant index forwards to `dashboard`, which IS S7",
  },
  { path: "/:tenant/dashboard", ids: { a1: "S7", r10: "DSH-01" } },
  {
    path: "/:tenant/checklist",
    ids: { a1: "S62", r10: "DSH-02" },
    note: "S62 is an A1 addendum heading, not a table row — see the gate's parser note" +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `DSH-02`, MINTED — A1's own S62 addendum calls this a *Dashboard surface*, and r10 draws DSH-01.",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/runbooks",
    ids: { a1: null, r10: "RBS-001" },
    note:
      "RBS-001, the Runbooks home (CR-075 wave D task D2). The screen declares " +
      "data-screen RBS-001 itself; the badge was null from 2.445.10 until " +
      "g29_allocated_badges.txt carried RBS-001 (2.445.14), transcribed from " +
      "17-runbooks/01-overview.md's screen table like every other RBS row.",
  },

  // ── Runbooks (`CR-075`) — FIVE ROWS, AND THREE OF THEM ARE THIS WAVE'S ────
  //
  // ⚠ **`screenIds.test.tsx` WAS ALREADY RED AT THE TIP OVER THE OTHER TWO.**
  // Wave C mounted `RBS-004` and `RBS-006` on 2026-09-06 and added no rows here,
  // so the mirror assertion — *"covers every routed screen, in App.tsx's order,
  // with nothing extra"* — was failing on the branch before wave D started. It
  // was checked rather than assumed: a search of this file's whole history for
  // the word `runbooks` returns nothing, while the tip's `App.tsx` already
  // carries both routes. That is `DEF-WRK-4056` and `DEF-WRK-4076` a third time,
  // and the register's own conclusion applies — **a lane adds the rows rather
  // than leaving the suite red, because a red suite hides the NEXT regression
  // too.** All five land together.
  //
  // ⚠ **THE BADGES ARE MINTED, NOT BORROWED, AND `a1` IS `null` ON PURPOSE.**
  // The runbooks pack numbers these screens `S148`–`S155` in its SOURCE
  // document; A1 declares no row for any of them and CLAUDE.md's canonical A1
  // range stops at `S114`, so claiming an A1 id would mint into a vocabulary
  // that is never renumbered — which `g29_screen_ids.py` refuses by name. The
  // `RBS-` ids are the repo's own (`08-screen-layouts.md`'s table) and are
  // allocated in `g29_allocated_badges.txt` in this same commit, the way
  // `WRK-20`…`WRK-24` were.
  {
    path: "/:tenant/runbooks/templates",
    ids: { a1: null, r10: "RBS-002" },
    note: "the shipped library (CR-075 wave D task D3). A1 has no row for it and " +
      "the source document's own S148 is outside A1's range, so the badge is the " +
      "repo's own RBS id.",
  },
  {
    path: "/:tenant/runbooks/templates/:key",
    ids: { a1: null, r10: "RBS-002" },
    subIdFrom: { param: "key" },
    note: "one template, before adding — the same screen id with the template's " +
      "key as r10's sub-id, exactly as SET-06.3 and ONB-04.n do.",
  },
  {
    path: "/:tenant/runbooks/mine",
    ids: { a1: null, r10: "RBS-003" },
    note: "My runbooks (CR-075 wave D task D4) — the configured list, and the " +
      "door RBS-004 had none of until this wave.",
  },
  // ⚠ **ABOVE `:key`, AND THE ORDER IS LOAD-BEARING HERE IN A WAY IT IS NOT IN
  // THE ROUTER.** React Router ranks a static segment over a dynamic one on its
  // own, so `/runbooks/runs` opens `RBS-008` whatever this file says — but this
  // table is walked in ORDER, so without this row the badge falls through to
  // the row below and reads **`RBS-004.runs`**: *the setup screen for the
  // runbook whose key is `runs`*. It did, in the wave I walkthrough's first
  // screenshot, over a page whose own `data-screen` said `RBS-008`. The Product
  // Owner reads that badge off a screenshot to say which screen has a problem
  // (CR-016 addendum), so a wrong one sends them to the wrong screen — and no
  // test looks at it, because it is rendered chrome.
  {
    path: "/:tenant/runbooks/runs",
    ids: { a1: null, r10: "RBS-008" },
    note: "run history across every runbook (CR-075 wave I task I6). Registered " +
      "here in the same commit as the route, because the badge that was drawn " +
      "over it before this row said RBS-004.",
  },
  {
    path: "/:tenant/runbooks/work",
    ids: { a1: null, r10: "RBS-007" },
    note: "the work list (CR-075 wave H task H3) — findings, exceptions and " +
      "human tasks in one place. The sheet's route is `operations/work` and " +
      "`/{tenant}/work` belongs to the WORK module, so `operations` → " +
      "`runbooks` exactly as the three library routes above resolved it.",
  },
  {
    path: "/:tenant/runbooks/:key",
    ids: { a1: null, r10: "RBS-004" },
    subIdFrom: { param: "key" },
    note: "one runbook's seven tabs (CR-075 wave C task C3). Registered here by " +
      "wave D: the route shipped without its row and the mirror assertion has " +
      "been red since.",
  },
  // ⚠ **`RBS-004.run` — A STATIC DOTTED SUB-ID, AND NO `subIdFrom`.** The
  // Check wizard (`OQ-WRK-12792` → A, PO 2026-10-13) is a step of the runbook
  // it runs, so it carries its parent's id and a fixed suffix. `subIdFrom:
  // key` would draw `RBS-004.run.configuration_check`, a badge naming no
  // screen. The component's own frames are drawn as `RBS-005.n` in the sheets;
  // that id is NOT claimed here, because `g29_allocated_badges.txt` carries no
  // `RBS-005` row and a badge must never mint into a vocabulary by accident.
  {
    path: "/:tenant/runbooks/:key/run",
    ids: { a1: null, r10: "RBS-004.run" },
    note: "the runbook Check wizard — scope · checking · review · done — and the " +
      "one way a run starts (OQ-WRK-12792 → A, PO 2026-10-13; DEF-WRK-10123). " +
      "Review hands over to RBS-006 by address.",
  },
  {
    path: "/:tenant/runbooks/:key/runs/:runId",
    ids: { a1: null, r10: "RBS-006" },
    note: "one run's frozen result (CR-075 wave C task C2). Registered here by " +
      "wave D, for the reason the row above gives.",
  },

  // The four retired settings tabs CR-001 moved one level down. Live deep
  // links, so they redirect rather than 404; a redirect renders no screen.
  {
    path: "/:tenant/settings/regional",
    ids: NONE,
    noScreen: "redirect",
    note: "→ /settings/company/regional (CR-001)",
  },
  {
    path: "/:tenant/settings/routes-cycles",
    ids: NONE,
    noScreen: "redirect",
    note: "→ /settings/reference-data/routes-cycles (CR-001)",
  },
  {
    path: "/:tenant/settings/number-series",
    ids: NONE,
    noScreen: "redirect",
    note: "→ /settings/reference-data/number-series (CR-001)",
  },
  {
    path: "/:tenant/settings/templates",
    ids: NONE,
    noScreen: "redirect",
    note: "→ /settings/reference-data/templates (CR-001)",
  },
  {
    // 2026-10-22 — Notifications moved under Configure, next to Templates.
    path: "/:tenant/settings/notifications",
    ids: NONE,
    noScreen: "redirect",
    note: "→ /settings/reference-data/notifications (PO 2026-10-22)",
  },

  // ── CR-029 RC-W3 · Routes & Cycles, addressable (B17 §4) ────────────────
  // ⚠ SIX NEW PATHS AND **NO NEW A1 ID FOR ANY OF THEM**, which is this table's
  // own rule applied rather than an omission: A1 gives the whole Settings
  // surface ONE id (S8) and never numbered a tab, so every row here keeps S8.
  //
  // ⚠ **AND THE TWO DETAIL SCREENS CARRY `r10: null`, WHICH IS THE FINDING.**
  // B17 §4 allocates them `SET-06D` and `SET-07D`, and those are real ids — in
  // the PO's UPGRADED PROTOTYPE (2026-08-23), which supersedes r10 for these
  // screens exactly as r10 superseded r9. **The upgraded prototype is not a
  // file in this repo**: it arrived as screenshots, and `05-prototype/` still
  // holds r10 and r9 only. So `sid()` in r10's drawing has no branch for either
  // screen, and G29 refuses the claim — correctly. It refused `DIS-02` on the
  // same grounds and that ruling stands recorded in `screen_id_baseline.txt`:
  // *"an id no authority defines is an id nobody can look up when it turns up
  // in a bug report"*.
  //
  // So SET-06D / SET-07D stay the TICKET vocabulary (B17 §4, the CR record) and
  // do NOT become badge claims here. The cost is real and is the reported half:
  // **these two screens draw no visible tag**, which is what the PO's 2026-08-19
  // ruling asked every screen for. It closes the day the upgraded prototype
  // lands in `05-prototype/` with an id function G29 can read — REPORTED to the
  // coordinator rather than resolved by minting an id.
  // ── CR-030 W4 · BR-CUS-095's document checklist ─────────────────────────
  {
    path: "/:tenant/settings/reference-data/service-request-documents",
    ids: { a1: null, r10: "SET-04.serviceRequestDocuments" },
    note:
      "NO ID FROM EITHER AUTHORITY, and both halves are findings rather than " +
      "omissions. A1: decision D1 — B18 §12.2 records that the reserved band " +
      "S61–S90 is EXHAUSTED and CR-030 needs sixteen ids where ten remain, so " +
      "allocation is the PO's and the next free ground is S115. Minting a " +
      "number out of a band somebody else may already have promised is exactly " +
      "what this table forbids. r10: the prototype has no service-request " +
      "surface at all — its `sid()` emits no `REQ-` badge, because REQ-01/02/03 " +
      "come from the PO's upgraded prototype of 2026-08-24 which is NOT a file " +
      "in this repo (B19's own §Source says the screenshots are not in the " +
      "tree). Same finding, same refusal, as SET-06D / SET-07D one block below." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `SET-04.serviceRequestDocuments` — r10 builds a reference-list sub-id as `'SET-04.' + refList` itself, so this is its own convention and needs no new number.",
  },
  {
    path: "/:tenant/settings/reference-data/work-labour-rates",
    ids: { a1: null, r10: "WRK-17" },
    note:
      "\u26a0 ADDED BY THE CR-070 WAVE M LANE, NOT BY THE WAVE THAT BUILT THE SCREEN " +
      "(DEF-WRK-4076). Wave N mounted this route in App.tsx and shipped no row here, so " +
      "screenIds.test.tsx \u2014 the one assertion that keeps this table and the router " +
      "identical \u2014 was RED on the branch before wave M touched it. The row is added " +
      "rather than left red because a red suite hides the NEXT regression too. " +
      "The badge and the note are taken from the screen file's own header and nothing " +
      "beyond it is asserted here.",
  },
  {
    path: "/:tenant/settings/reference-data/read-formats",
    ids: { a1: null, r10: "SET-04.readFormats" },
    note:
      "CR-192-BRC10 (MQ-033 task 11) — Settings → Reads → Read formats. No A1 id " +
      "(the S61–S90 band is exhausted, see the service-request-documents row) and " +
      "no r10 frame (MQ-033 was ruled 2026-10-24, after r10). The badge uses r10's " +
      "own reference-card sub-id convention, `'SET-04.' + list`, so it needs no new number.",
  },
  {
    path: "/:tenant/settings/reference-data/read-formats/:formatId",
    ids: { a1: null, r10: "SET-04.readFormatDetail" },
    note: "CR-192-BRC10 — one read format: its draft's questions and its versions.",
  },
  {
    path: "/:tenant/settings/reference-data/cant-read-reasons",
    ids: { a1: null, r10: "SET-04.cantReadReasons" },
    note:
      "DEF-MET-10609 (decision log 2026-10-26, PO \"yes do it\") — the ONE can't-read " +
      "reason list for route and job readings, under Settings → Reference data → READS " +
      "beside Read formats. No A1 id and no r10 frame (ruled after r10); the badge uses " +
      "r10's `'SET-04.' + list` sub-id convention, the read formats' precedent.",
  },
  {
    path: "/:tenant/settings/reference-data/routes-cycles/routes/new",
    ids: { a1: "S8", r10: "SET-06.1" },
    note: "the route wizard as a URL (W3-T5) — it was `useState` inside the landing tab",
  },
  {
    path: "/:tenant/settings/reference-data/routes-cycles/routes/:routeId/edit",
    ids: { a1: "S8", r10: "SET-06.1" },
    note: "the EDITOR, pre-filled; same four steps, so the same id as the creator",
  },
  {
    path: "/:tenant/settings/reference-data/routes-cycles/routes/:routeId",
    ids: { a1: "S8", r10: "SET-06D" },
    note:
      "NO r10 BADGE, SO NO VISIBLE TAG. The route detail is SET-06D in B17 §4 and " +
      "in the CR-029 record, and that id comes from the PO's upgraded prototype " +
      "(2026-08-23), which is not a file in this repo — r10's own sid() has no " +
      "branch for it. Claiming it here would mint an id no authority in the tree " +
      "defines (the DIS-02 precedent). Reported." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `SET-06D` — the id B17 §4 and the CR-029 record already gave it, now ALLOCATED in g29_allocated_badges.txt so an authority defines it.",
  },
  {
    path: "/:tenant/settings/reference-data/routes-cycles/cycles/new",
    ids: { a1: "S8", r10: "SET-07.1" },
  },
  {
    path: "/:tenant/settings/reference-data/routes-cycles/cycles/:cycleId/edit",
    ids: { a1: "S8", r10: "SET-07.1" },
  },
  {
    path: "/:tenant/settings/reference-data/routes-cycles/cycles/:cycleId",
    ids: { a1: "S8", r10: "SET-07D" },
    note:
      "NO r10 BADGE, SO NO VISIBLE TAG — the cycle detail is SET-07D in B17 §4, " +
      "from the upgraded prototype that is not in this tree. Same finding and same " +
      "precedent as the route detail two rows up. Reported." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `SET-07D` — B17 §4's own id, now ALLOCATED in g29_allocated_badges.txt.",
  },

  // S8 is ONE A1 screen covering every Settings tab, so the A1 half never
  // changes here. r10 numbers the tabs separately (SET-01…SET-15) and that is
  // r10's own vocabulary, so the r10 half does.
  //
  // ⚠ A1's per-list ids S63–S71 and S75–S80 (holiday calendar, utility service size
  // classes, import mappings…) are NOT reachable by route: they are views
  // inside the Reference data card grid, opened without a URL of their own. So
  // no tag can show them and no gate can see them. Reported.
  {
    // CR-110-BRC04 wave A (2026-09-16): S147, the connector SET-UP screen —
    // one form rendered 28 ways from the manifest. Badge INT-07, the next free
    // number in the module's own run, ALLOCATED in g29_allocated_badges.txt
    // against this exact route in the same commit that mounts it.
    //
    // ⚠ S147 IS ALLOCATED BY THIS CR AND RECORDED IN A1'S OWN ADDENDUM, which
    // is the S141–S146 precedent rather than a mint here: the Runbooks
    // addendum states in as many words that *"S147 REMAINS THE NEXT FREE S"*,
    // and G29 refuses an `a1:` id A1 does not declare — so the spec moves
    // first and this row follows it.
    //
    // ⚠ IT IS LISTED FIRST, ahead of every `settings/integrations/…` row
    // below, for the reason those rows already give each other: this register
    // is matched IN ORDER. The paths do not collide today, and listing the
    // most specific first is what keeps that true when one of them grows a
    // wildcard.
    path: "/:tenant/settings/connectors/:providerKey/configure",
    ids: { a1: "S147", r10: "INT-07" },
  },
  {
    // CR-069 wave R (2026-09-06): S144, the keys we issue to a partner. Badge
    // INT-04, ALLOCATED in g29_allocated_badges.txt against this exact route
    // by wave D. ⚠ It is listed FIRST, ahead of `…/:key/mappings` and
    // `…/:key`, for the reason the note on S142 below already gives: this
    // register is matched IN ORDER, so `/:key` would swallow `/:key/access`
    // and tag this screen S142. Asserted in MachineKeysPage.test.tsx.
    path: "/:tenant/settings/integrations/:key/access",
    ids: { a1: "S144", r10: "INT-04" },
  },
  {
    // CR-069 wave D (2026-09-03): S143, the mapping editor — *their words for
    // our things*. A1's addendum records CR-069 §9's six ids S141–S146; the
    // badge is INT-03, ALLOCATED in g29_allocated_badges.txt by the first lane
    // to mount one of the six (the plan's own rule for B7).
    path: "/:tenant/settings/integrations/:key/mappings",
    ids: { a1: "S143", r10: "INT-03" },
  },
  {
    // CR-069 wave C (2026-09-04): S142, the connection detail — the run record
    // a support agent reads. Badge INT-02, already ALLOCATED in
    // g29_allocated_badges.txt against this exact route.
    // ⚠ It is listed AFTER the mappings route above because this register is
    // matched in order and `/:key` would otherwise swallow `/:key/mappings`
    // and tag S143's screen S142. The mappings route's own tag is asserted in
    // ConnectionDetailPage.test.tsx for that reason.
    path: "/:tenant/settings/integrations/:key",
    ids: { a1: "S142", r10: "INT-02" },
  },
  {
    // CR-068 wave A: the Customer portal segment's own strip. Overview is
    // CWP-069 (the default) and Branding is CWP-070; both allocated in
    // g29_allocated_badges.txt. A1 numbers every Settings surface S8.
    path: "/:tenant/settings/reference-data/customer-portal/:segment",
    ids: { a1: "S8", r10: "CWP-069" },
    byParam: {
      param: "segment",
      values: {
        overview: { a1: "S8", r10: "CWP-069" },
        branding: { a1: "S8", r10: "CWP-070" },
      },
    },
  },
  {
    // 2026-10-22 — Configure → Notifications' own strip and its rule pages.
    // Every segment — Messages needing attention, Blocked addresses, an open
    // rule page — draws r10's SET-12, the one id r10 gives the whole
    // Notifications surface. (Before the move these addresses fell through to
    // `:tab/:sub`'s default and drew SET-01.profile.)
    path: "/:tenant/settings/reference-data/notifications/:segment",
    ids: { a1: "S8", r10: "SET-12" },
  },
  {
    // …and every old `/settings/notifications/<sub>` redirects to its home.
    path: "/:tenant/settings/notifications/:sub",
    ids: NONE,
    noScreen: "redirect",
    note: "→ /settings/reference-data/notifications/<sub>; rights → Templates; sender → Connectors (PO 2026-10-22)",
  },
  {
    path: "/:tenant/settings",
    ids: { a1: "S8", r10: "SET-01.profile" },
    note: "bare /settings falls back to the Company tab (DEFAULT_SETTINGS_TAB)",
  },
  {
    path: "/:tenant/settings/:tab",
    // ⚠ THE DEFAULT PAIR IS NOT A GAP — it is what an UNRECOGNISED tab value
    // resolves to, and this param already falls back to a real default tab
    // inside its own screen. It carried `r10: null` until 2026-09-03, which was
    // consistent while 35 screens drew nothing; now that every screen carries a
    // badge it would be one of the last addresses whose corner went empty, and
    // a tag that went empty would disagree with what is actually drawn — this
    // file's own argument for the A1 half, applied to the visible half.
    ids: { a1: "S8", r10: "SET-01.profile" },
    byParam: {
      param: "tab",
      values: {
        company: { a1: "S8", r10: "SET-01.profile" },
        users: { a1: "S8", r10: "SET-02" },
        services: { a1: "S8", r10: "SET-03" },
        "reference-data": { a1: "S8", r10: "SET-04" },
        accounting: { a1: "S8", r10: "SET-11" },
        integrations: { a1: "S8", r10: "SET-13" },
        security: { a1: "S8", r10: "SET-14" },
        "billing-plan": { a1: "S8", r10: "SET-15" },
      },
    },
  },
  {
    // Both second-level strips at once — Company's (profile · regional) and
    // Configure's (reference-data · routes-cycles · number-series · templates).
    // The six sub ids are unique across the two tabs, so one table is exact.
    path: "/:tenant/settings/:tab/:sub",
    // The default pair, for the same reason as the row above.
    ids: { a1: "S8", r10: "SET-01.profile" },
    byParam: {
      param: "sub",
      values: {
        profile: { a1: "S8", r10: "SET-01.profile" },
        regional: { a1: "S8", r10: "SET-01.regional" },
        "reference-data": { a1: "S8", r10: "SET-04" },
        "routes-cycles": { a1: "S8", r10: "SET-05" },
        "number-series": { a1: "S8", r10: "SET-08" },
        templates: { a1: "S8", r10: "SET-09" },
        // 2026-10-22: Notifications, moved from the top row to Configure.
        notifications: { a1: "S8", r10: "SET-12" },
        // CR-068 wave A: Configure's fifth segment IS CWP-069, the portal
        // settings overview — a staff screen the blueprint numbered in the
        // portal's series. ALLOCATED in g29_allocated_badges.txt; r10 does not
        // draw it and no screenshot of r10 ever will.
        "customer-portal": { a1: "S8", r10: "CWP-069" },
      },
    },
    // ⚠ **THE TEMPLATE DETAIL IS `SET-10` AND IT DREW `SET-09` UNTIL TODAY
    //   (`DEF-NOT-4443`).** `SET-09` is the template CATALOGUE — a list of 38
    //   rows — and opening one of them replaces that list with the designer for
    //   ONE template, at the same address plus `?template=<code>`. Both screens
    //   therefore resolved through this row's `sub` value and both drew the
    //   list's badge, so a Product Owner photographing a fault on the designer
    //   filed it against the list.
    //
    //   r10 has said so from the beginning and nobody read it: its own id
    //   function (prototype line 9280) is
    //       if (s.cfgSub === 'templates')
    //         return s.tplView ? 'SET-10.' + s.tplView : 'SET-09';
    //   — the same `?template=` distinction, made in the prototype's own state.
    //   `SET-10` is therefore a badge r10 DECLARES (the literal survives in
    //   `'SET-10.'`, exactly as `PLN-01` survives in `'PLN-01.'`), so no row in
    //   `g29_allocated_badges.txt` is needed or wanted: the register is for ids
    //   NO authority defines, and minting one for an id r10 already draws would
    //   put a second authority behind one number.
    whenPresent: {
      param: "template",
      from: "search",
      over: "SET-09",
      ids: { a1: "S8", r10: "SET-10" },
    },
  },

  {
    path: "/:tenant/audit-log",
    ids: { a1: "S61", r10: "SET-16" },
    note: "S61 is an A1 addendum heading, not a table row; r10 draws no audit screen" +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `SET-16`, MINTED — reached from Settings → Security, and r10 draws SET-01..15.",
  },
  {
    path: "/:tenant/audit-log/retention",
    ids: { a1: null, r10: "SET-16.retention" },
    note:
      "NO A1 ID. The data-retention run ledger (US-MET-020 / US-AUD-007) was built " +
      "as a compliance answer an operator can send as a link; A1 has no row for it " +
      "and r10 draws no such screen. Reported." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `SET-16.retention` — a sub-view of the audit log allocated one row up.",
  },

  // ── Plans & Rates ───────────────────────────────────────────────────────
  { path: "/:tenant/plans-rates/plans/new", ids: { a1: "S10", r10: "PLN-03" } },
  {
    // PLN-02, the plan DETAIL (CR-013 P5 · screen inventory §18 row 2). r10's
    // own mapping (10372) expects `prView === 'pl'` → PLN-02 and its handler
    // sets `'plan'`, so the running drawing badges `PLN-plan` — an r10 bug
    // recorded in `07-r10-plans-rates-readout.md` §2 and confirmed on the PO's
    // screenshot. The SPECIFIED id is mapped here, exactly as RAT-02's is two
    // rows below; a walkthrough of this screen is evidenced by route +
    // heading text, as §2 instructs.
    path: "/:tenant/plans-rates/plans/:planId",
    ids: { a1: "S10", r10: "PLN-02" },
    note:
      "A1 gives the whole plan surface one id (S10 — 'New Plan wizard'); r10 " +
      "numbers the detail PLN-02 and its builder PLN-03",
  },
  {
    path: "/:tenant/plans-rates/plans/:planId/edit",
    ids: { a1: "S10", r10: "PLN-03" },
    note: "The same builder opened on a stored plan — one screen, two doors",
  },
  { path: "/:tenant/plans-rates/rates/new", ids: { a1: "S11", r10: "RAT-03" } },
  {
    // RAT-02, the rate schedule DETAIL (CR-013 P3 · screen inventory §18 row 5).
    // r10's own mapping (9203-9211) says `prView === 'rd'` → RAT-02 and its
    // handler sets `'rate'`, so the running drawing badges `PLN-rate` — an r10
    // bug recorded in 07-r10-plans-rates-readout.md §2 and confirmed on the
    // PO's screenshot. The SPECIFIED id is mapped here; a walkthrough of this
    // screen is evidenced by route + heading text, as §2 instructs.
    path: "/:tenant/plans-rates/rates/:tariffId",
    ids: { a1: "S11", r10: "RAT-02" },
    note:
      "A1 gives the whole rate-schedule surface one id (S11); r10 numbers the " +
      "detail RAT-02 and its wizard RAT-03",
  },
  { path: "/:tenant/plans-rates/rates/:tariffId/edit", ids: { a1: "S11", r10: "RAT-03" } },
  // ── CR-013 rows 8 · 11 · 14 — the shared definition detail ───────────────
  //
  // BR-RAT-084 (PO ruling 2026-08-20, option B) ratifies **three distinct
  // routes with three distinct screen ids** over ONE component, so a
  // walkthrough can evidence each and a deep link resolves. That also closes
  // OQ-281, which asked whether the shared shell is `CHG-01` or `CHG-03`:
  // neither answer survives, because a single id for three surfaces is exactly
  // what the ruling refuses.
  //
  // ⚠ THE THREE STRINGS ARE DERIVED, NOT MINTED FROM NOTHING, and the
  // derivation is r10's own sub-id grammar — the one `PLN-01` / `PLN-01.charges`
  // already follows in this file. r10 stamps `CHG-01` on all three (confirmed
  // on three browser screenshots, §2), so the charge detail keeps the badge the
  // running artefact actually draws and the other two extend it by kind. No
  // number is invented and the reserved A1 block is not touched.
  //
  // ⚠ A1 ALLOCATES NOTHING HERE, which is the finding rather than a licence.
  // A1's `S9` is the r9 landing with FOUR tabs and no detail pages at all (§7);
  // the spec is stale and r10 wins (CLAUDE.md). Reported, not renumbered.
  // ── CR-013 row 9 — CHG-02, the New/Edit charge-code WIZARD ──────────────
  //
  // A1 DOES allocate here, unusually for this module: `S12 | New Charge Code
  // form | Add charge code | Charge Codes tab`. It describes a MODAL and the
  // screen is now a full page (PO 2026-08-20, *"Wizards for each type - no
  // modal"*) — but it is the same screen doing the same job, so it keeps S12
  // rather than minting a number, exactly as `plans-rates/plans/new` keeps S10.
  //
  // ⚠ THE r10 ID IS THE **SPECIFIED** ONE, NOT THE EMITTED ONE, and §8 says why:
  // *"ALL FIVE WIZARDS EMIT THE SAME BADGE: `NEW-01`"* — worse than the CHG-01
  // collision, because the badge cannot tell a new plan from a new tax. The
  // inventory numbers this wizard CHG-02, so that is what is mapped, the same
  // treatment RAT-02 took two rows below. A walkthrough of this screen is
  // evidenced by route + heading text (§2), never by the badge.
  { path: "/:tenant/plans-rates/charge-codes/new", ids: { a1: "S12", r10: "CHG-02" } },
  {
    path: "/:tenant/plans-rates/charge-codes/:definitionId/edit",
    ids: { a1: "S12", r10: "CHG-02" },
    note: "The same wizard opened on a stored code — one screen, two doors",
  },
  {
    path: "/:tenant/plans-rates/charge-codes/:definitionId",
    ids: { a1: null, r10: "CHG-01" },
    note:
      "NO A1 ID. Charge-code detail — r10's own badge, confirmed on the PO's " +
      "screenshot of Water base service. A1's S9 predates every detail page.",
  },
  // ── CR-013 row 12 — DIS-02, the New/Edit DISCOUNT wizard ────────────────
  //
  // ⚠ NO A1 ID, AND UNLIKE `S12` THAT IS NOT AN OVERSIGHT TO WORK AROUND. A1
  // allocates `S11 New Rate wizard`, `S12 New Charge Code form` and `S13 New
  // Tax/Fee form` — and nothing at all for a discount, because A1's `S9` is the
  // **r9** landing with four tabs and no Discounts on it (`09-screen-inventory`
  // §7: *"r9-era and stale. r10 wins; file, do not follow"*). Minting a number
  // out of the reserved S61–S90 block to make the ratchet stay still is exactly
  // what this file forbids, so the absence is REPORTED and G29's
  // `screens_without_a1` rises by one.
  //
  // ⚠ AND NO r10 BADGE EITHER, WHICH IS A FINDING AND WAS PROVED BY THE GATE.
  // `DIS-02` was written here first, on §18 row 12's authority, and G29 refused
  // it: *"that is not a badge r10 draws"*. It is right. r10's own `sid` function
  // has a branch for every other Plans & Rates wizard — `PLN-03.n`, `RAT-03.n`,
  // `CHG-02.n` — and **no branch at all for the discount wizard**, so opening it
  // in the prototype badges the LANDING TAB (`PLN-01.discounts`). §8's claim
  // that *"ALL FIVE WIZARDS EMIT THE SAME BADGE: NEW-01"* is not what the source
  // does: the string `NEW-01` appears nowhere in the file. DEF-406.
  //
  // So this screen is named by NEITHER authority and both absences are written
  // down rather than papered over with an invented id — which is the whole
  // reason `DIS-02` stays the ticket vocabulary in §18 and does not become a
  // badge claim here. A walkthrough is evidenced by route + heading text.
  {
    path: "/:tenant/plans-rates/discounts/new",
    ids: { a1: null, r10: "DIS-02" },
    note:
      "NO A1 ID and NO r10 BADGE. A1's S9 is the r9 landing with four tabs and " +
      "no Discounts at all, so A1 allocates nothing for this screen; and r10's " +
      "own sid function has no discount-wizard branch, so the prototype badges " +
      "the landing tab here (DEF-406). The inventory calls it DIS-02 and that " +
      "stays the ticket vocabulary rather than becoming a badge nobody draws." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `DIS-02` — 06-rating/09-screen-inventory.md §18 row 12 records a lane writing exactly this string and G29 refusing it for want of an authority. It is ALLOCATED now, so the refusal is answered rather than waived.",
  },
  {
    path: "/:tenant/plans-rates/discounts/:definitionId/edit",
    ids: { a1: null, r10: "DIS-02" },
    note:
      "NO A1 ID and NO r10 BADGE, for the same two reasons as the create door " +
      "one row above. It is the same wizard opened on a stored discount — one " +
      "screen, two doors — and the edit door drafts a NEW dated version " +
      "(BR-RAT-078), never a rewrite, which is why no PATCH sits behind it." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `DIS-02` — one screen, two doors, so the same id as the create door.",
  },
  {
    path: "/:tenant/plans-rates/discounts/:definitionId",
    ids: { a1: null, r10: "CHG-01.discount" },
    note:
      "NO A1 ID. Discount detail. r10 stamps CHG-01 here too; BR-RAT-084 " +
      "requires three DISTINCT ids, so the kind extends the shell's badge in " +
      "r10's own sub-id grammar (PLN-01 -> PLN-01.charges).",
  },
  // ── CR-013 P4 row 15 — TAX-02, the New/Edit tax or fee wizard ────────────
  //
  // ⚠ THERE IS NO r10 BADGE FOR THIS SCREEN, AND THAT IS r10's BUG, NOT AN
  // OMISSION HERE. `09-screen-inventory.md` §8 records it: *"ALL FIVE WIZARDS
  // EMIT THE SAME BADGE: `NEW-01` … the screen ID cannot distinguish a new plan
  // from a new tax."* Read off r10's own `sid()` function, the tax wizard sets
  // `module: 'newTax'` and falls through every branch to the final fallback
  // `(m || 'APP').toUpperCase().slice(0, 3) + '-01'` — so the badge it draws is
  // the literal string `NEW-01`, which `sid()` never writes down and G29
  // therefore cannot accept. The SPECIFIED id is `TAX-02` and r10 emits it
  // nowhere, so claiming either would be minting an id no authority defines.
  // Both rows carry `r10: null` and the count rises by two, honestly.
  //
  // A1 DOES name it: `S13 | New Tax/Fee form | Add tax or fee | Taxes & Fees
  // tab`. That row is r9-era and describes a modal form; the SCREEN is the same
  // screen and the shape is r10's, which is the standing precedence rule.
  {
    path: "/:tenant/plans-rates/taxes-fees/new",
    ids: { a1: "S13", r10: "TAX-02" },
    note:
      "NO r10 BADGE. r10 renders this wizard under module 'newTax', which its " +
      "own sid() has no branch for, so the running canvas stamps the fallback " +
      "NEW-01 on all five wizards alike (inventory 8). TAX-02 is the specified " +
      "id and r10 emits it nowhere; neither string is a badge r10 draws." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `TAX-02` — the id CR-013 part 4 specifies, now ALLOCATED rather than left as ticket vocabulary.",
  },
  {
    path: "/:tenant/plans-rates/taxes-fees/:taxId/edit",
    ids: { a1: "S13", r10: "TAX-02" },
    note:
      "NO r10 BADGE — same cause as the new-tax row above. The edit door is the " +
      "same four-step screen with a record loaded, so it carries the same A1 id " +
      "and the same absent r10 badge, and it refuses an in-place edit of a tax " +
      "that is in force (CR-013 part 4)." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `TAX-02` — the same screen as the create door, so the same id.",
  },
  {
    path: "/:tenant/plans-rates/taxes-fees/:definitionId",
    ids: { a1: null, r10: "CHG-01.tax" },
    note: "NO A1 ID. Tax detail — same derivation as the discount row above.",
  },
  {
    path: "/:tenant/plans-rates",
    ids: { a1: "S9", r10: "PLN-01" },
    note: "A1's S9 is the whole tabbed screen; r10 numbers the Plans tab PLN-01",
  },
  {
    // A1 gives the tabbed screen ONE id (S9). r10 gives the Rates tab its own
    // (RAT-01) and extends the parent for the rest (`PLN-01.charges`).
    path: "/:tenant/plans-rates/:tab",
    ids: { a1: "S9", r10: "PLN-01" },
    byParam: {
      param: "tab",
      values: {
        plans: { a1: "S9", r10: "PLN-01" },
        rates: { a1: "S9", r10: "RAT-01" },
      },
    },
    subIdFrom: { param: "tab" },
    note: "charges/taxes/history read PLN-01.<tab>, exactly as r10 writes them",
  },

  // ── Premises & Units ────────────────────────────────────────────────────
  { path: "/:tenant/premises/new", ids: { a1: "S16", r10: "PRM-07" } },
  {
    path: "/:tenant/premises/import",
    ids: { a1: null, r10: "WFL-01" },
    note:
      "NO A1 ID. The five-stage import runner (Extract · Transform · Validate · " +
      "Load · Result), mounted 2026-08-21 by DEF-520 — the kit and its four " +
      "endpoints existed for a build with no screen rendering them, so the " +
      "Imports buttons still opened the old add-premises wizard. A1 draws no " +
      "workflow screen at all (CLAUDE.md: r10 wins on description, file it), " +
      "and no story owns it — hard-won law 8, reported. Reported.",
  },
  {
    path: "/:tenant/premises/units/import",
    ids: { a1: null, r10: "WFL-01" },
    note:
      "NO A1 ID. The SAME runner as the row above, and deliberately the same " +
      "r10 id: BR-MET-096 (PO 2026-08-21) rules ONE workflow for premises and " +
      "units, differing only in the Transform stage's field map. Two routes, " +
      "one screen — a second r10 id here would be the first crack in that. " +
      "Reported.",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/premises/units/new",
    ids: { a1: null, r10: "PRM-01U.new" },
    note:
      "The add-units wizard, a child of the units list (PRM-01U), so a dotted sub-id " +
      "and no new number. Without this row the badge read PRM-03, the unit DETAIL, " +
      "because units/:unitId matched the word new as a unit id.",
  },
  { path: "/:tenant/premises/units", ids: { a1: "S15", r10: "PRM-01U" } },
  {
    path: "/:tenant/premises/units/:unitId",
    ids: { a1: null, r10: "PRM-03" },
    note:
      "NO A1 ID. A1 draws Premises (S14), Units (S15) and the add form (S16) and " +
      "stops; the unit DETAIL screen is r10's PRM-03 and the spec is stale here " +
      "(CLAUDE.md: r10 wins on description, file it). Reported.",
  },
  {
    path: "/:tenant/premises/imports",
    ids: { a1: null, r10: "PRM-04" },
    note:
      "NO A1 ID. CR-023's third tab. A1 draws Premises (S14), Units (S15) and " +
      "the add form (S16) and stops; the Imports tab is r10's PRM-04 and the " +
      "spec has no row for it (CLAUDE.md: r10 wins on description, file it). " +
      "It is also the screen hard-won law 8 is about — no story owns it yet, " +
      "because CR-023 §11 lists PRM-04 as new and the epics are not re-authored. " +
      "Reported.",
  },
  { path: "/:tenant/premises", ids: { a1: "S14", r10: "PRM-01" } },
  {
    path: "/:tenant/premises/:premisesId",
    ids: { a1: null, r10: "PRM-02" },
    note: "NO A1 ID. Premises detail is r10's PRM-02 and A1 has no row for it. Reported.",
  },

  // ── Meter Reads ─────────────────────────────────────────────────────────
  // ⚖️ **BOTH ARE REDIRECTS NOW, AND THE IDS GO WITH THE SCREENS.** Entry 14
  // retired Routes as a screen (PO 2026-09-12) and entry 15 moved the cycles
  // list into the Read cycles TAB; the addresses are kept because tickets carry
  // them. A `<Navigate>` renders no screen, so it draws no tag — the same shape
  // `/signin`'s redirect row already takes. `S26`/`RDS-02R` and `S27`/`RDS-02C`
  // are not reassigned to anything: an id whose screen is gone is reported, not
  // recycled.
  {
    path: "/:tenant/reads/routes",
    ids: NONE,
    noScreen: "redirect",
    note:
      "Entry 14 retired Routes AS A SCREEN (PO 2026-09-12); the address is kept " +
      "because tickets carry it and forwards to the Read cycles tab. It drew " +
      "S26 / RDS-02R.",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/reads/routes/:routeId",
    ids: { a1: null, r10: null },
    note:
      "One route's own page (Meter Reads entry 21). Its parent /reads/routes is a " +
      "redirect with no badge. No badge: no r10 drawing and no allocated parent this " +
      "screen is plainly a child of, so an id here would be minted, which is the " +
      "g29_allocated_badges.txt authority's to do. Reported, not invented.",
  },
  {
    path: "/:tenant/reads/cycles",
    ids: NONE,
    noScreen: "redirect",
    note:
      "Entry 15 moved the cycles list into the Read cycles TAB on the reads " +
      "screen; this address is kept for the tickets that carry it and forwards " +
      "there. It drew S27 / RDS-02C.",
  },
  {
    // Meter Reads blueprint entry 20 — the cycle DETAIL, new on 2026-09-14.
    // ⚠ **NEITHER VOCABULARY HAS A ROW FOR IT, AND THAT IS THE FINDING RATHER
    // THAN A GAP TO FILL.** A1 was extracted from r9 and numbers no cycle
    // detail; r10 draws none either — the screen exists because a 2026-09-12 PO
    // ruling asked for *"a list view of read cycles"* and *"a detail view"*, and
    // the blueprint drew it afterwards. An absent id is REPORTED, never
    // invented: putting `RDS-02D` on it because the pattern suggests one is the
    // habit this file's header refuses by name, so the screen draws no tag.
    path: "/:tenant/reads/cycles/:cycleId",
    ids: NONE,
    note:
      "Meter Reads blueprint entry 20, the cycle DETAIL. NEITHER vocabulary " +
      "numbers it: A1 was extracted from r9 and has no cycle-detail row, and " +
      "r10 draws no such screen either. It exists because the PO asked on " +
      "2026-09-12 for a list view of read cycles and a detail view, and the " +
      "blueprint drew it afterwards. An absent id is REPORTED, never " +
      "invented, so this screen draws no tag.",
  },
  // ⚠ `/:tenant/reads/estimate` WAS HERE AND IS GONE (DEF-897, 2026-08-27).
  // PO on the live app: *"this can be modal - instead of page"*. "Estimate a
  // missing read" is a dialog mounted from S25's header now, so it is not a
  // routed screen and has no row here. Its old note — *"NO A1 ID … r10 has no
  // estimate view either"* — is why the row was `NONE` in the first place, and
  // is the same reason it never should have been a route.
  { path: "/:tenant/reads/upload", ids: { a1: "S28", r10: "RDS-03" } },
  {
    // CR-038 W5 (PO 2026-08-26): S29 is a PAGE now — "i want page to be open
    // for consitency - we dont open side panel". r10's RDS-04 draws it as a
    // drawer; the id is kept because the CONTENT is RDS-04's, and the overlay
    // presentation is what the ruling overrode. The old `?read=<id>` links
    // redirect here from S25.
    path: "/:tenant/reads/:readId",
    ids: { a1: "S29", r10: "RDS-04" },
  },
  {
    path: "/:tenant/reads",
    ids: { a1: "S25", r10: "RDS-01" },
  },

  // ── Accounts ────────────────────────────────────────────────────────────
  { path: "/:tenant/accounts/new", ids: { a1: "S18", r10: "ACC-03" } },
  { path: "/:tenant/accounts/import", ids: { a1: "S68", r10: "ACC-04" } },
  { path: "/:tenant/accounts", ids: { a1: "S17", r10: "ACC-01" } },
  // ── CR-056 W5 task 25 — the customers list ──────────────────────────────
  {
    path: "/:tenant/customers",
    ids: { a1: null, r10: "ACC-07" },
    note:
      "NO ID FROM EITHER AUTHORITY, and both halves are findings rather than " +
      "omissions. A1: B18 §12.2 records that the reserved band S61-S90 is " +
      "EXHAUSTED and that the next free ground is S115, so allocation is the " +
      "PO's. Minting a number out of a band somebody else may already have " +
      "been promised is exactly what this table forbids. r10: the prototype " +
      "draws no customers surface at all — a person is reached through an " +
      "account there too, which is the whole of what CR-056 §4 measured. The " +
      "screen therefore draws no visible tag, which is the reported half of " +
      "the PO ruling of 2026-08-19; same finding and same refusal as the " +
      "service-request rows above." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `ACC-07`, MINTED — a sibling of the accounts list ACC-01; r10 draws ACC-01..06.",
  },
  { path: "/:tenant/accounts/:accountId", ids: { a1: "S21", r10: "ACC-02" } },
  { path: "/:tenant/accounts/:accountId/move-out", ids: { a1: "S20", r10: "ACC-06" } },
  { path: "/:tenant/accounts/:accountId/move-in", ids: { a1: "S19", r10: "ACC-05" } },

  // ── The CLOSE-OUT — a screen NEITHER authority numbers (DEF-724) ─────────
  // ⚠ **THE ROUTE SHIPPED WITHOUT THIS ROW, WHICH IS DEF-710's SHAPE EXACTLY.**
  // `App.tsx` mounted `CloseOutPage` on 2026-08-27 under BR-CUS-430 and no
  // `SCREEN_ROUTES` row came with it, so `screenIds.test.tsx` — the one
  // assertion that holds this second list to the router's own table — was RED
  // on the branch, and G29 could not see the screen at all. DEF-710's own
  // prevention is the rule that was missed: *"a lane that mounts a route in
  // App.tsx adds its `SCREEN_ROUTES` row in the same commit."*
  //
  // ⚠ **NO A1 ID AND NO r10 BADGE, AND NEITHER IS INVENTED HERE.** The act is
  // eleven days younger than r10 (2026-08-16) and A1 was extracted from r9,
  // so no authority has numbered it: the PO ruled the ACT into existence on
  // 2026-08-27 (*"A disconnected customer can never be closed - Add a separate
  // close-out act — Cleaner in the record"*, BR-CUS-430) and neither vocabulary
  // has caught up. Allocating an S-id or an `ACC-0n` badge here would be this
  // lane extending a vocabulary that is not ours — the same refusal every other
  // unnumbered row on this table makes. So the visible tag draws NOTHING on
  // this screen, which is the finding rather than an invention, and it is
  // REPORTED: G29's `screens_without_a1` / `screens_without_r10` each carry it.
  {
    path: "/:tenant/accounts/:accountId/close-out",
    ids: { a1: null, r10: "ACC-02.closeOut" },
    note:
      "NO A1 ID, NO r10 BADGE. The close-out act (BR-CUS-430, PO 2026-08-27). A1 " +
      "predates it and r10 draws no badge for it, so both are absent rather than " +
      "guessed. Reported." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `ACC-02.closeOut` — a sub-view of the account detail r10 draws as ACC-02.",
  },

  // ── `CR-094-BRC01` wave L · `BR-CUS-1051` — THE EIGHT OVER THE ACCOUNT ───
  // PO 2026-09-13, verbatim: *"Yes move the eight quick actions over the
  // account"*. Five of the eight are the addresses above and just above this
  // line — UNCHANGED strings, now CHILD routes of `/accounts/:accountId`, which
  // is why `change-plan` and `payment-plan` moved UP this table: `flatten()`
  // reads children immediately after their parent and this list is held to its
  // order.
  //
  // ⚠ **THREE ADDRESSES ARE NEW, AND EACH IS A SECOND DOOR ONTO A SCREEN THAT
  // KEEPS ITS FIRST.** Each carries the ids of the screen it mounts, exactly as
  // the standalone `/move-ins/new` rows below carry S19/S20: two routes, one
  // screen, one id, so no debt count moves.
  {
    path: "/:tenant/accounts/:accountId/bills/:invoiceId/document",
    ids: { a1: null, r10: "BIL-05.document" },
    note:
      "THE SAME SCREEN AS `/billing/bills/:invoiceId/document`, mounted over the " +
      "account (BR-CUS-1051, PO 2026-09-13). Billing's address is untouched and " +
      "still the one a support ticket carries. BILL-SCOPED, which is why this is " +
      "the only one of the eight whose segment takes a parameter: BillDocumentPage " +
      "reads `useParams().invoiceId` and the rail resolves which bill.",
  },
  {
    path: "/:tenant/accounts/:accountId/issue-credit",
    ids: { a1: "S30", r10: "BIL-01" },
    note:
      "FixABillTab — the same correction workflow `/billing/fix?bill=` opens, " +
      "mounted over the account (BR-CUS-1051, PO 2026-09-13). It carries the ids " +
      "of the bills screen whose TAB it is, because that is the screen it belongs " +
      "to; billing's own address is untouched. A credit is raised ON A BILL, so " +
      "the bill still rides in `?bill=` here exactly as it does there.",
  },
  {
    path: "/:tenant/accounts/:accountId/change-plan",
    ids: { a1: "S23", r10: "PLN-04" },
    note:
      "r10 reaches Change plan as a modal on ACC-02 and gives it no badge of " +
      "its own. ⚠ CR-013 part 5 and `06-rating/09-screen-inventory.md` §18 " +
      "row 16 NUMBER this screen `PLN-04` — the sixteenth of the sixteen Plans " +
      "& Rates surfaces, governed by plan rules and living in Accounts, which " +
      "is why a PLN id names a screen under `/accounts`. That id is NOT put in " +
      "the r10 column and the attempt is recorded so it is not retried: G29's " +
      "authority for that column is the r10 file itself, and `PLN-04` appears " +
      "nowhere in it, so claiming it fails with `that is not a badge r10 " +
      "draws`. The gate is right — an id whose authority is the CR belongs in " +
      "the CR, and `screens_without_r10` stays at 16 because r10 genuinely " +
      "draws nothing here (checked 2026-08-21)" +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `PLN-04` — the number CR-013 part 5 and 06-rating §18 row 16 already give it, now ALLOCATED.",
  },
  {
    path: "/:tenant/accounts/:accountId/disconnect",
    ids: { a1: null, r10: "DSC-02" },
    note:
      "THE SAME FIVE-STEP WIZARD AS `/disconnects/new`, mounted over the account " +
      "(BR-CUS-1051, PO 2026-09-13). `/disconnects/new?account=` is untouched and " +
      "is still how the Accounts list and the Disconnects tab reach it. The wizard " +
      "reads its subject from `:accountId` here and from `?account=` there; it " +
      "SCHEDULES a cut and never performs one, either way.",
  },
  {
    path: "/:tenant/accounts/:accountId/payment-plan",
    ids: { a1: "S24", r10: "ACC-02.paymentPlan" },
    note: "as S23 — r10 draws it inside the account, with no id of its own" +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `ACC-02.paymentPlan` — this row's own note says r10 draws it inside the account, which is exactly what a dotted sub-id of ACC-02 says.",
  },


  // ── The STANDALONE move-in / move-out entries — PO ruling 2026-08-26 ─────
  // ⚠ **THE SAME TWO SCREENS, AT A SECOND ADDRESS — so they carry the SAME
  // ids, and NEITHER debt count moves.** S19 and S20 are allocated by A1 and
  // ACC-05 / ACC-06 are badges r10 itself draws; what is new is a door with
  // nothing in the path, so each wizard's FIRST STEP asks for its subject
  // instead of confirming one. This is the CHG-02 / DIS-02 precedent read the
  // other way round: two routes, one screen, one id — `screens_total` does not
  // move, `routes_total` rises by exactly two.
  //
  // The PO's own words, overruling the disabled Accounts-header controls:
  // *"Move-in and move-out stay disabled, on purpose … The live control is on
  // the account's own page and the button says so. -Enable Move in /move out"*.
  //
  // ⚠ **STATIC SEGMENTS, DECLARED BEFORE ANY FUTURE `:moveInId`** — here and in
  // `App.tsx`, or `/move-ins/new` is read as a move-in whose id is the word
  // "new". The `/transfers/new` rows below carry the same warning, and DEF-520
  // is the premises runner learning it the hard way.
  {
    path: "/:tenant/accounts/:accountId/work-orders/new",
    ids: { a1: null, r10: "WRK-12" },
    note:
      "CR-168-BRC10 image 19 (1\u00b74e), ruling 35 \u2014 the raise opened from an account, " +
      "arriving filled. The SAME three-step raise as /work/orders/new, so it carries the " +
      "same borrowed r10 badge the drawing carries; full page beside the account route, " +
      "not a dialog child (BR-CUS-1051), because the drawing draws a page.",
  },
  { path: "/:tenant/move-ins/new", ids: { a1: "S19", r10: "ACC-05" } },
  { path: "/:tenant/move-outs/new", ids: { a1: "S20", r10: "ACC-06" } },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/moves/:ref",
    ids: { a1: null, r10: null },
    note:
      "One move-in or move-out record read back (MVI-/MVO- numbered, BR-CUS-1090). " +
      "No badge: no r10 drawing and no allocated parent this screen is plainly a " +
      "child of, so an id here would be minted, which is the " +
      "g29_allocated_badges.txt authority's to do. Reported, not invented.",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/complaints/new",
    ids: { a1: null, r10: null },
    note:
      "The job intake wizard for a complaint (JobIntakeWizard, kind complaint). No " +
      "badge: no r10 drawing and no allocated parent this screen is plainly a child " +
      "of, so an id here would be minted, which is the g29_allocated_badges.txt " +
      "authority's to do. Reported, not invented.",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/services/new",
    ids: { a1: null, r10: null },
    note:
      "The job intake wizard for a consumer service (JobIntakeWizard, kind service). " +
      "No badge: no r10 drawing and no allocated parent this screen is plainly a " +
      "child of, so an id here would be minted, which is the " +
      "g29_allocated_badges.txt authority's to do. Reported, not invented.",
  },
  // ── Service requests (CR-030 W4 · REQ-01 · REQ-02 · REQ-03) ─────────────
  // ⚠ **THREE NEW SCREENS AND NOT ONE ID FROM EITHER AUTHORITY.** B18 §5.3
  // PROPOSES S83 (list), S84 (detail) and S85 (the applicant's form), and
  // proposing is not allocating: B18 §12.2's decision **D1** records that
  // A1's reserved band S61–S90 is EXHAUSTED and that this CR needs sixteen ids
  // where ten remain, so the next free ground is S115 and **allocation is the
  // PO's**. A1 declares no S83/S84/S85 today, and G29's first assertion —
  // *every `a1:` id in the map is an id A1 declares* — would refuse them. It
  // would be right; the DIS-02 entry in `screen_id_baseline.txt` settles the
  // principle: *"an id no authority defines is an id nobody can look up when it
  // turns up in a bug report"*.
  //
  // ⚠ **AND r10 DRAWS NO SERVICE-REQUEST SURFACE AT ALL.** Its `sid()` emits 92
  // badges and none begins `REQ-`; `REQ-01` … `REQ-03.sent` come from the PO's
  // upgraded prototype of 2026-08-24, whose screenshots B19 §Source states are
  // **not in this repo**. So these three screens draw NO VISIBLE TAG, which is
  // the cost the PO's 2026-08-19 ruling asks every screen to pay, and it is
  // REPORTED rather than paid with an invented badge. It closes the day the
  // upgraded prototype lands in `05-prototype/` with an id function G29 can
  // read — the identical position SET-06D / SET-07D are in.
  //
  // S83/S84/S85 remain the TICKET vocabulary in B18 and in the CR-030 record.
  {
    path: "/:tenant/requests/new",
    ids: { a1: null, r10: "REQ-03" },
    note:
      "REQ-03.1–6 + REQ-03.sent, the six-step capture form. B18 §5.3 proposes " +
      "S85 and A1 allocates nothing (decision D1 — the reserved band is " +
      "exhausted and allocation is the PO's); r10 draws no service-request " +
      "screen, so there is no badge to show. Both REPORTED, neither invented." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `REQ-03` — B18 §5.3's own id, now ALLOCATED.",
  },
  {
    path: "/:tenant/requests",
    ids: { a1: null, r10: "REQ-01" },
    note:
      "REQ-01, the Requests list. B18 §5.3 proposes S83; A1 allocates nothing " +
      "(decision D1) and r10 draws no service-request screen. ⚠ B19 §12.1 draws " +
      "this as a TAB of the accounts page and it is a route of its own here — " +
      "`AccountsListPage.tsx` owns that eight-tab strip and is another lane's " +
      "file today; the tab body is one line and is OWED, not done." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `REQ-01` — B18 §5.3's own id, now ALLOCATED.",
  },
  {
    path: "/:tenant/requests/:requestId",
    ids: { a1: null, r10: "REQ-02" },
    note:
      "REQ-02, the request detail and its THREE tabs. B18 §5.3 proposes S84; A1 " +
      "allocates nothing (decision D1) and r10 draws no service-request screen. " +
      "Per-tab deep links ride in `?tab=` rather than in the path, so the three " +
      "tabs are one screen here exactly as ACC-02's nine are." +
      "⚠ AMENDED 2026-09-15 (`CR-094-BRC01` wave 2): it said SIX until the screen " +
      "was rebuilt to the Accounts blueprint p082, which draws Applicant · " +
      "Documents · History. Amended in the same commit as the change that made " +
      "it wrong, which is the only way a line like this has ever been right." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `REQ-02` — B18 §5.3's own id, now ALLOCATED.",
  },

  // ── New Connect (CR-030 W6 tasks 6.11 / 6.13) ───────────────────────────
  // ⚠ **THESE TWO ROWS WERE MISSING AND THIS SUITE WAS RED ON `HEAD`.** The
  // routes were mounted in `App.tsx` on 2026-08-25 with no row here, so
  // `screenIds.test.tsx`'s one both-directions assertion failed naming them —
  // *"an added route that nobody mapped"*, which is exactly the drift it exists
  // to refuse. Filed as a defect by lane WOPLACEHOLDER and closed here rather
  // than left standing: a suite that is red for somebody else's reason is a
  // suite the next lane learns to skim past.
  //
  // Both take the D1 posture the three `requests` rows above carry, for the
  // same reasons: B18 proposes S87 (the wizard) and S88 (the detail), and
  // PROPOSING IS NOT ALLOCATING — A1 §S61–S90 still reads *"S82–S90 remain
  // reserved"* as amended 2026-08-24, and G29's first assertion (every `a1:` id
  // is one A1 declares) would refuse them. r10 draws no `NCT-` badge either:
  // `NCT-01`/`NCT-02` come from the PO's upgraded prototype of 2026-08-24,
  // whose screenshots are not in this repo. So both screens draw NO VISIBLE
  // TAG, reported rather than paid for with an invented id.
  {
    path: "/:tenant/connections/new",
    ids: { a1: null, r10: "NCT-01" },
    note:
      "NCT-01, the eight-step New Connect wizard. B18 proposes S87 and A1 " +
      "allocates nothing (decision D1 — the reserved band is exhausted and " +
      "allocation is the PO's); r10 draws no `NCT-` badge, so there is no tag " +
      "to show. Both REPORTED, neither invented. ⚠ The STATIC segment is " +
      "declared before `:connectionId` in App.tsx and here, or `new` is read " +
      "as a connection id." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `NCT-01` — B18 §5.4's own id, now ALLOCATED.",
  },
  // ⚠ **`NCT-02` IS RE-ALLOCATED AND THIS PATH IS A SCREEN AGAIN
  // (`CR-151-BRC09` §6a, PO ruling 2026-09-28).** It was retired on 2026-09-04
  // when `CR-070` wave O deleted the build's page and left a redirect answering
  // this address — a doorway that resolved where the build lived and sent the
  // reader to the premises or the account. The 2026-09-28 ruling reverses the
  // FIRST CLAUSE of that wave and nothing else: a build IS a thing a clerk
  // opens, and what the PO objected to was two screens for one fact.
  //
  // ⚠ **THE ADDRESS NEVER MOVED, WHICH IS WHY THIS ROW WAS KEPT RATHER THAN
  // DELETED IN 2026-09-04.** Every bookmark made while the old screen was live,
  // and every *Open this connection* link the wizard has handed out since,
  // resolves here and goes on resolving here. The doorway swapped its ELEMENT;
  // the route and this row were never the thing that changed.
  //
  // A badge says *"this is a screen"*, and now one genuinely is: the matching
  // row returns to `10-scripts/gates/g29_allocated_badges.txt` in this same
  // commit and `G29`'s screen count rises by one.
  // `07-frontend/src/features/work/buildAddress.route.test.tsx` is the test
  // written at the hold, which fires on the day the element changes and names
  // all three things the flip owes.
  {
    path: "/:tenant/connections/:connectionId",
    ids: { a1: null, r10: "NCT-02" },
    note:
      "NCT-02, the build's own detail page — header, seven tabs and a More " +
      "menu. Same D1 posture as `NCT-01` above: A1 allocates nothing (the " +
      "reserved band is exhausted and allocation is the PO's) and the badge " +
      "is B18 §5.4's own id, re-allocated by CR-151-BRC09 after CR-070 wave O " +
      "retired it. ⚠ The STATIC `new` segment is declared BEFORE this one in " +
      "App.tsx and here, or `new` is read as a connection id.",
  },

  // ── CR-030 W7 · the transfer and disconnect wizards ─────────────────────
  // Same D1 posture as the two `connections` rows above, for the same reason:
  // B18 §3 maps S89 as *"Transfers tab — list + 5-step wizard"* and S90 as
  // *"Disconnects tab — list + ladder + 5-step wizard"*, so each wizard is the
  // second half of an id A1 has NOT allocated — S82–S90 still read *"remain
  // reserved"* as amended 2026-08-24, and G29's first assertion would refuse an
  // `a1:` value here. r10 badges the two screens `TRF-02` and `DSC-02`, and
  // those badges come from the PO's upgraded prototype of 2026-08-24 whose
  // screenshots are not in this repo — so neither screen draws a visible tag.
  // Reported, not invented.
  {
    path: "/:tenant/transfers/new",
    ids: { a1: null, r10: "TRF-02" },
    note:
      "TRF-02, the five-step transfer wizard (B18 §5.7.7). B18 proposes S89 for " +
      "the id and A1 allocates nothing (decision D1). ⚠ The STATIC segment is " +
      "declared before any future `:transferId` in App.tsx and here, or `new` " +
      "is read as a transfer id." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `TRF-02` — B18 §5.7.7's own id (TRF-01 is the list), now ALLOCATED.",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/transfers/:ref",
    ids: { a1: null, r10: null },
    note:
      "One transfer read back by its TRF- number. No badge: no r10 drawing and no " +
      "allocated parent this screen is plainly a child of, so an id here would be " +
      "minted, which is the g29_allocated_badges.txt authority's to do. Reported, " +
      "not invented.",
  },
  {
    path: "/:tenant/disconnects/new",
    ids: { a1: null, r10: "DSC-02" },
    note:
      "DSC-02, the five-step disconnect wizard (B18 §5.8.7). B18 proposes S90 " +
      "for the id and A1 allocates nothing (decision D1). The wizard SCHEDULES " +
      "a cut and never performs one — `commit_cut` is a separate act on the " +
      "date — which is why the route is `/new` and not `/cut`." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `DSC-02` — B18 §5.8.7's own id (DSC-01 is the list), now ALLOCATED.",
  },
  // ── CR-125-BRC07 · THE DISCONNECT CASE RECORD (blueprint p143) ──────────
  // ⚠ **DECLARED AFTER `/disconnects/new`, AND THE ORDER IS THE ASSERTION.**
  // `screenIds.test.tsx` compares this list with `flatten(APP_ROUTES)` in
  // DECLARATION ORDER, on purpose — *"order is what makes `matchPath` pick the
  // static segment over the dynamic one"*. A row placed above the wizard would
  // resolve `/disconnects/new` to the record and call the word `new` a case
  // number. That is `accounts/master`'s trap and DEF-520's.
  //
  // ⛔ **THE ROW IS THE OTHER HALF OF A DOOR, AND IT WAS MISSING FOR AS LONG AS
  // IT TOOK A SIBLING TO NOTICE (`DEF-CUS-6042`).** The route was mounted in
  // `App.tsx` and absent here, so the screen was reachable only by typing a
  // URL: the Disconnects list's hold-expiry test reads `SCREEN_ROUTES`, so the
  // screen landing did not fire it and the list went on refusing `↗ Open` over
  // a page that existed. **Nothing could catch it** — `tsc` passes, the
  // record's own suite passes because it mounts the component directly, and
  // the list's suite passes because the absence it asserts is true of the
  // registry it reads. Mounting a route and registering it are two acts, and
  // only the first one feels like the work (hard-won law 2's mirror).
  {
    path: "/:tenant/disconnects/:ref",
    ids: { a1: null, r10: "DSC-03" },
    note:
      "DSC-03, the DISCONNECT CASE RECORD — blueprint p143, whose own red banner " +
      "read \"TODAY: no disconnect case page exists\". MINTED: r10 badges DSC-01 " +
      "(the list) and DSC-02 (the wizard) and draws no record, and A1 allocates " +
      "nothing for S90's second half (decision D1). `:ref` is the CASE NUMBER " +
      "and never a uuid (B14 rule 31) — `DSC-26-0003`, the series `OQ-427` " +
      "closed on 2026-08-27. Three actions and no more, which is the PO's " +
      "ruling of 2026-09-20 and not a reading of the drawing: \"too many " +
      "actions - keep critical ones\".",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/disconnects/:ref/reconnect",
    ids: { a1: null, r10: "DSC-03.reconnect" },
    note:
      "Reconnecting one disconnection case, a child of the case record (DSC-03), so " +
      "a dotted sub-id and no new number.",
  },

  // ── Billing ─────────────────────────────────────────────────────────────
  {
    path: "/:tenant/billing/bills/:invoiceId/document",
    ids: { a1: null, r10: "BIL-05.document" },
    note:
      "NO A1 ID. The rendered bill document. `documents.py` rendered every bill " +
      "twice and threw the result away until a screen could open one; A1 has no " +
      "row and r10 no badge. Reported." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `BIL-05.document` — the rendered document of the bill detail above.",
  },
  {
    path: "/:tenant/billing/bills/:invoiceId",
    ids: { a1: null, r10: "BIL-05" },
    note: "NO A1 ID. Bill detail. A1 draws the LIST (S30) and no detail screen. Reported." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `BIL-05`, MINTED — r10 draws BIL-01..04 and no bill detail.",
  },
  {
    path: "/:tenant/billing/pending",
    ids: { a1: null, r10: "BIL-06" },
    note:
      "NO A1 ID. The pending-billing queue (US-BIL-006, *\"hold ≠ forget\"*). A1's " +
      "2026-08-08 addendum gives S30 a pending-billing queue CHIP; the queue itself " +
      "is a screen A1 never numbered. Reported." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `BIL-06`, MINTED.",
  },
  {
    path: "/:tenant/billing/print",
    ids: { a1: null, r10: "BIL-07" },
    note:
      "NO A1 ID. Print bills — the PDF set plus its manifest, which is what a print " +
      "vendor receives (CR-053 task 13, BR-NOT-029). A1 numbers no print hand-over " +
      "screen and r10 draws none; the ruling that created it is later than both. " +
      "Reported, exactly as the pending queue above is." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `BIL-07`, MINTED.",
  },
  {
    path: "/:tenant/billing/one-time",
    ids: { a1: "S30", r10: "BIL-01" },
    note:
      "S30's One-time bill tab, redrawn as its own page (PO-confirmed design " +
      "2026-09-30, `11-one-time-bill-redesign.md`). It takes the tab's own address, " +
      "so it carries S30's ids rather than new ones (A1: \"never renumber\").",
  },
  { path: "/:tenant/billing/run", ids: { a1: "S31", r10: "BIL-02" } },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/billing/budget/enrol",
    ids: { a1: null, r10: null },
    note:
      "Budget billing, enrol an account. No badge: no r10 drawing and no allocated " +
      "parent this screen is plainly a child of, so an id here would be minted, " +
      "which is the g29_allocated_badges.txt authority's to do. Reported, not " +
      "invented.",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/billing/budget/settle-up",
    ids: { a1: null, r10: null },
    note:
      "Budget billing, the settle-up forecast. No badge: no r10 drawing and no " +
      "allocated parent this screen is plainly a child of, so an id here would be " +
      "minted, which is the g29_allocated_badges.txt authority's to do. Reported, " +
      "not invented.",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/billing/budget/asks",
    ids: { a1: null, r10: null },
    note:
      "Budget billing, customers' asks to join. No badge: no r10 drawing and no " +
      "allocated parent this screen is plainly a child of, so an id here would be " +
      "minted, which is the g29_allocated_badges.txt authority's to do. Reported, " +
      "not invented.",
  },
  { path: "/:tenant/billing", ids: { a1: "S30", r10: "BIL-01" } },
  {
    path: "/:tenant/billing/:tab",
    ids: { a1: "S30", r10: "BIL-01" },
    subIdFrom: { param: "tab" },
    note: "S31.2/S31.3 are STEPS of the run wizard, not tabs here — they stay unrouted",
  },

  // ── Payments ────────────────────────────────────────────────────────────
  {
    path: "/:tenant/payments/collections",
    ids: { a1: null, r10: "PAY-06" },
    note:
      "NO A1 ID. The collections ladder board (2026-08-16). A1's S70 is the " +
      "collections RULES in Settings, not the board a clerk drives. Reported." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `PAY-06`, MINTED — r10 draws PAY-01..05.",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/payments/imports/new",
    ids: { a1: null, r10: null },
    note:
      "The payments import workflow. The Imports tab itself still carries no badge " +
      "(PAY-05 is unclaimed, see the payments tab row). No badge: no r10 drawing and " +
      "no allocated parent this screen is plainly a child of, so an id here would be " +
      "minted, which is the g29_allocated_badges.txt authority's to do. Reported, " +
      "not invented.",
  },
  {
    // `PAY-04` / 3·2 *Your counter* (`CR-136-BRC07` `P2.6`). Declared ABOVE the
    // `:tab` row so the literal `counter/<code>` address is not resolved as a
    // tab; A1 draws no counter screen at all, so the A1 half is null and the
    // badge is MINTED in `g29_allocated_badges.txt`.
    //
    // ⚠ **THE PARAM IS THE COUNTER'S CODE AND NOT ITS ID** (B14 rule 31) —
    // `/brazosbend/payments/counter/CTR-260921-DW`, which is what the drawing
    // puts in the address bar on p052.
    path: "/:tenant/payments/counter/:counterCode",
    ids: { a1: null, r10: "PAY-07" },
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/payments/debtors/:accountNo",
    ids: { a1: null, r10: null },
    note:
      "One debtor's page, opened from Outstandings by the account NUMBER, never an " +
      "id (B14 rule 31). It is not a path child of a badged screen. No badge: no r10 " +
      "drawing and no allocated parent this screen is plainly a child of, so an id " +
      "here would be minted, which is the g29_allocated_badges.txt authority's to " +
      "do. Reported, not invented.",
  },
  {
    // **5·2 Settlement** (`CR-139-BRC07` `P5.7`) — one payout and the payments
    // inside it. Declared ABOVE the `:tab` row so the literal
    // `settlements/<reference>` address is not resolved as a tab; A1 draws no
    // settlements screen at all, so the A1 half is null and the badge is
    // MINTED in `g29_allocated_badges.txt`.
    //
    // ⚠ **THE PARAM IS THE PROVIDER'S OWN REFERENCE AND NOT A uuid** (B14 rule
    // 31) — `/brazosbend/payments/settlements/STL-260921-CARD`, which is what
    // the blueprint puts in the address bar on p071.
    //
    // ⚠ **THIS LIST HAS BEEN RED AND UNREAD SINCE BEFORE THIS ROW** —
    // `DEF-SHL-6047` (2026-09-20): the router declares more paths than this
    // registry holds, and `screenIds.test.tsx` has been failing on the
    // difference. Adding this row does not make it green and is not meant to;
    // it means this screen is not one of the missing ones.
    path: "/:tenant/payments/settlements/:settlementRef",
    ids: { a1: null, r10: "PAY-09" },
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/payments/refunds",
    ids: { a1: "S58", r10: "FIN-01.refunds" },
    note:
      "Refunds, MOVED here from /finance/refunds on 2026-09-23 (CR-138-BRC07 P4.10); " +
      "the old address redirects, so the screen keeps its own id rather than taking " +
      "a second one. Without this row the badge read PAY-summary, because " +
      "payments/:tab treated refunds as an unknown tab.",
  },
  {
    // **2·3a Record a payment** (`DEF-PAY-6317`) — the form's own address,
    // blueprint p037. Declared ABOVE the `:tab` row so the literal
    // `record/new` is never resolved as a tab, the same ordering the counter,
    // debtor and settlement rows above are declared for.
    //
    // **A1 `S35`**, which is p098's own Repo id for this frame and reads
    // *"Payment modals — Record, Credit, Adjust, Lockbox, Reverse, …"* in the
    // screen inventory. The eight acts of §03 share it.
    //
    // ⚠ **`r10` IS NULL AND THAT IS NOT AN OVERSIGHT.** r10 never drew a
    // record PAGE — the form has only ever been a modal over `PAY-01`, which
    // is what p038's TASK box says — so a badge here would be invented for a
    // drawing that does not exist, and `g29_allocated_badges.txt` exists to
    // refuse exactly that. The blueprint's own `PAY-M` is a PLACEHOLDER
    // meaning *a new payments screen*, not an r10 id; the file says so of
    // `PAY-N` in the same paragraph.
    path: "/:tenant/payments/record/new",
    ids: { a1: "S35", r10: null },
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/payments/outstandings/send-notice",
    ids: { a1: null, r10: "PAY-02.send-notice" },
    note:
      "Sending a notice from Outstandings, a child of that tab (PAY-02), so a dotted " +
      "sub-id and no new number.",
  },
  {
    path: "/:tenant/payments",
    ids: { a1: "S32", r10: "PAY-summary" },
    note:
      "bare /payments falls back to the Summary tab, which A1 numbers S32. r10 " +
      "DECLARES no badge for that tab — its id function computes one from the tab " +
      "name and declares nothing, which G29 refuses and DEF-3480 puts to the PO. " +
      "So this is the tab a clerk lands on and it draws no id; see the block above " +
      "NONE for both options and what each costs." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `PAY-summary` — DEF-3480's own case, answered rather than waived. r10 COMPUTES this exact string (`map[s.payTab] || 'PAY-' + s.payTab`, Summary sets `payTab: 'summary'`) and DECLARES it nowhere, which is why G29 refused it. It is ALLOCATED now, deliberately as the string r10 itself computes, so prototype and product agree.",
  },
  {
    // A1 gives each Payments tab its own screen id — S32 Summary, S33 Record
    // payments, S34 Outstandings — so this is the one route where the A1 half
    // moves with the URL.
    path: "/:tenant/payments/:tab",
    // The default pair: an unrecognised tab falls back to Summary, so it draws
    // Summary's badge rather than nothing. Same argument as the settings rows.
    ids: { a1: "S32", r10: "PAY-summary" },
    byParam: {
      param: "tab",
      values: {
        summary: { a1: "S32", r10: "PAY-summary" },
        record: { a1: "S33", r10: "PAY-01" },
        outstandings: { a1: "S34", r10: "PAY-02" },
        collections: { a1: null, r10: "PAY-06" },
        // ⚠ **THE THREE TABS `P0.8` LANDS WITH NO SCREEN BEHIND THEM, AND THEY
        // DRAW NO BADGE ON PURPOSE — FOUND IN A BROWSER AND BY NOTHING ELSE.**
        // Without these rows the `ids` default above runs and the badge read
        // `PAY-summary` while the clerk was on **Settlements**, which is the
        // exact shape this row's own note calls *"a bug report cannot describe
        // it"*.
        //
        // **NULL AND NOT A MINTED ID**: there is no screen here to name yet.
        // `PAY-03`/`PAY-04`/`PAY-05` would be badges invented for drawings r10
        // never made, and `g29_allocated_badges.txt` exists to refuse exactly
        // that. Each one is allocated by the wave that BUILDS its screen —
        // Counter and Settlements in phase 2, Imports with `P1.5`.
        // ⚠ **`counter` GOT ITS BADGE ON 2026-09-23 (`CR-136-BRC07` `P2.6`)**,
        // which is this block's own instruction being followed: *"Each one is
        // allocated by the wave that BUILDS its screen — Counter and
        // Settlements in phase 2."* `PAY-03` is MINTED in
        // `10-scripts/gates/g29_allocated_badges.txt`, which is the authority
        // G29 reads; it is not a string r10 draws and never was.
        //
        // ⚠ **NOT `PAY-03`, AND THE NEAR-MISS IS WORTH THE LINE.** The block
        // above reads *"`PAY-03`/`PAY-04`/`PAY-05` would be badges invented
        // for drawings r10 never made"*, which is true of 04 and false of the
        // other two: r10's own map is `{record:'PAY-01', outstanding:'PAY-02',
        // deposits:'PAY-03', imports:'PAY-05'}`, so **`PAY-03` is Finance →
        // Deposits** (S37, registered twice below) and `PAY-05` is the
        // payments Imports tab's when somebody claims it. Only `PAY-04` was
        // free, and it is taken here.
        counter: { a1: null, r10: "PAY-04" },
        imports: { a1: null, r10: null },
        // ⚠ **`settlements` GOT ITS BADGE ON 2026-09-23 (`CR-139-BRC07`
        // `P5.7`)**, which is this block's own instruction being followed:
        // *"Each one is allocated by the wave that BUILDS its screen — Counter
        // and Settlements in phase 2."* `PAY-08` is MINTED in
        // `10-scripts/gates/g29_allocated_badges.txt`; the blueprint's own
        // `PAY-P` is a PLACEHOLDER in the sense `PAY-N` was for the counter,
        // not an id r10 draws. The map was grepped before minting, which is
        // the near-miss the counter block records: `PAY-03` is Finance →
        // Deposits and `PAY-05` is the Imports tab's the day somebody claims
        // it, so the lowest free pair was `PAY-08` and `PAY-09`.
        settlements: { a1: null, r10: "PAY-08" },
      },
    },
    note:
      "⚠ THIS NOTE SAID `summary` AND `collections` CARRIED NO r10 ID, FOR TWO " +
      "DIFFERENT REASONS, AND BOTH REASONS ENDED ON 2026-09-03. `summary` was " +
      "DEF-3480's case — r10 computes a badge for that tab and declares none — and " +
      "`collections` is a board of ours that r10 never drew at all. The register " +
      "`10-scripts/gates/g29_allocated_badges.txt` now allocates `PAY-summary` (the " +
      "string r10 itself computes) and `PAY-06`, so both are ids an authority " +
      "defines. ⚠ **THESE TWO VALUES ARE WHY A BADGE IS SET IN BOTH PLACES:** the " +
      "static `/payments/collections` row above wins the router's match, but this " +
      "byParam value is what `resolveScreen` returns for the same screen reached as " +
      "a tab — leaving it null would show an id on one URL and nothing on the other, " +
      "which is the shape a bug report cannot describe.",
  },

  // ── Assets ──────────────────────────────────────────────────────────────
  {
    path: "/:tenant/assets/import",
    ids: { a1: null, r10: "WFL-01" },
    note:
      "NO A1 ID. The SAME five-stage runner as /premises/import, and " +
      "deliberately the same r10 id (BR-MET-096: one workflow, targets differ). " +
      "BR-AST-046 (CR-028, PO 2026-08-22) sends every assets import here, " +
      "tab-named, with the target in ?target=assets_*. The three assets " +
      "targets register with AST-W3; until then the route renders the stated " +
      "absence, never a dead runner. Reported.",
  },
  {
    // CR-028 AST-W4 (PO 2026-08-22 — "as per r10 - it is not modal"): S51 is
    // r10's AST-05 4-step wizard, a full-page route now. r10's own badge is
    // AST-05.<step>; the step half is wizard state, the parent id is the tag.
    path: "/:tenant/assets/new",
    ids: { a1: "S51", r10: "AST-05" },
  },
  {
    path: "/:tenant/assets",
    ids: { a1: "S49", r10: "AST-01" },
    note:
      "S51/S53/S54/S55 were modals on this screen until CR-028 AST-W4 made " +
      "them the four full-page routes below (B16 §5.2 as amended); only edit, " +
      "delete and bulk-assign stay modal here",
  },
  { path: "/:tenant/assets/:assetId/reassign", ids: { a1: "S55", r10: "AST-06" } },
  { path: "/:tenant/assets/:assetId/maintenance/new", ids: { a1: "S53", r10: "AST-07" } },
  {
    path: "/:tenant/assets/:assetId/work-orders/new",
    ids: { a1: null, r10: "WRK-24" },
    note:
      "The Assets door (Work-028) \u2014 CR-070 wave M, 2026-09-05: one form, four ways in, " +
      "a SIBLING of the maintenance row directly above (BR-WRK-056's own word for it). " +
      "\u26a0 THE BADGE IS MINTED, not borrowed: r10 draws WRK-01..18 for the dispatcher's " +
      "own screens and draws no raise form hosted on an asset. It is deliberately NOT " +
      "WRK-19, which was retired in wave D \u2014 reusing a retired badge would make an old " +
      "citation land on a screen it never named. " +
      "\u26a0 apps/assets writes NOTHING here: the form posts POST /work-orders with " +
      "asset_id, which is Work's own door.",
  },
  { path: "/:tenant/assets/:assetId/retire", ids: { a1: "S54", r10: "AST-08" } },
  {
    path: "/:tenant/assets/:assetId/edit",
    ids: { a1: null, r10: "AST-09" },
    note:
      "Edit one asset (CR-092 `AST-B-12`, PO 2026-09-11: \u201cthis should be form and not " +
      "modal\u201d) \u2014 the fifth asset surface to stop being a dialog, after the four " +
      "CR-028 AST-W4 converted on 2026-08-22. " +
      "\u26a0 THE BADGE IS MINTED, not borrowed: r10 draws AST-01..08 and draws no edit " +
      "screen at all, because in r10 editing was a dialog on the registry and a dialog " +
      "carries no badge. It is registered in gates/g29_allocated_badges.txt, which is the " +
      "third authority G29 reads. " +
      "\u26a0 A1 ALLOCATES NO ID FOR IT and none is minted: A1's S49\u2013S60 addendum names " +
      "add, reassign, log-repair and retire as separate screens and edit is not among them, " +
      "and CLAUDE.md says the S vocabulary is never renumbered.",
  },
  { path: "/:tenant/assets/:assetId", ids: { a1: "S50", r10: "AST-02" } },

  // ── Finance ─────────────────────────────────────────────────────────────
  {
    // ⚠ **CR-060 T10 MOVED WHAT THIS ADDRESS RENDERS AND THIS ROW STAYED
    // BEHIND (DEF-3463's third mirror).** The bare `/finance` used to draw
    // Revenue & AR; it draws the TRIAL BALANCE now — App.tsx maps it to
    // `GeneralLedgerPage` and its own comment says so — so the tag on the
    // books screen was announcing FIN-01, the id of a screen one click away.
    // A diagnostic whose whole job is *"so that we know which scren has a
    // problem"* is worse than nothing when it names the wrong screen.
    path: "/:tenant/finance",
    ids: { a1: "S56", r10: "FIN-02" },
    note:
      "CR-060 T10 — the bare /finance lands on the trial balance (S56 · r10 FIN-02), " +
      "the same screen /finance/gl serves. Revenue & AR keeps S36 and took a segment " +
      "of its own, on the row below.",
  },
  {
    // CR-060 T10 — Revenue & AR took a segment of its own on the same commit.
    // r10's own Finance map is `{ revenue:'FIN-01', journals:'FIN-02',
    // close:'FIN-03', recon:'FIN-04' }` (prototype line 9266), so FIN-01
    // follows the screen rather than the address.
    path: "/:tenant/finance/revenue",
    ids: { a1: "S36", r10: "FIN-01" },
  },
  { path: "/:tenant/finance/deposits/import", ids: { a1: "S38", r10: "PAY-03.import" },
    note:
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `PAY-03.import` — a sub-view of the deposits screen, which this map already badges PAY-03." },
  {
    path: "/:tenant/finance/deposits/statement",
    ids: { a1: "S37", r10: "PAY-03" },
    note:
      "CR-059 P8, the period reconciliation statement. It carries S37's own ID " +
      "rather than a new one: A1 numbers no screen for the tie-out, the four " +
      "backends behind it are S37/S40 work, and a reference list or a report " +
      "does not mint a screen ID (the Settings-card precedent). S40's explain " +
      "modal opens here as well as on the batch and needs no route.",
  },
  {
    path: "/:tenant/finance/deposits/:batchId",
    ids: { a1: "S39", r10: "FIN-05" },
    note: "S40's reconcile modal opens on this screen and needs no route",
  },
  { path: "/:tenant/finance/deposits", ids: { a1: "S37", r10: "PAY-03" } },
  // ⛔ `/:tenant/finance/write-offs` (`FIN-01.writeOffs`) IS GONE — `CR-135`
  // P1.10, 2026-09-22. It was a SECOND write-off approval queue beside the
  // `WriteOffQueuePanel` `CR-060` §8b folded into Revenue & AR, reachable only
  // by typing the address. The route went and this row goes with it in the same
  // commit, because `screenIds.test.tsx` compares this table to the router's
  // own and a row without a route is the same defect as a route without a row.
  {
    path: "/:tenant/finance/refunds",
    ids: { a1: "S58", r10: "FIN-01.refunds" },
    note:
      "S58 Record refund (CR-059 P3, task 18). A1 numbers S58 in the PROVISIONAL " +
      "S49–S60 block (addendum, OQ-014) and r10 draws no refunds screen at all, " +
      "which is why the r10 id is null and not a guess. The whole refund lifecycle " +
      "— raise, approve, issue, clear, void — is on this one route; the approval " +
      "queue GET /refunds had been mounted since 2026-08-28 and could never hold a " +
      "row, because nothing in the product could raise a refund." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `FIN-01.refunds` — a Finance tab under the FIN-01 parent.",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/finance/refunds/:refundId",
    ids: { a1: "S58", r10: null },
    note:
      "One refund, opened from the list (the screen's own SCREEN_ID is S58.detail). " +
      "A1 S58 is the refund screen; r10 has no refund drawing and the list's badge " +
      "is already a dotted sub-id, so no second dot is stacked on it.",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/finance/journal-entries/new",
    ids: { a1: null, r10: null },
    note:
      "A new journal batch. No badge: no r10 drawing and no allocated parent this " +
      "screen is plainly a child of, so an id here would be minted, which is the " +
      "g29_allocated_badges.txt authority's to do. Reported, not invented.",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/finance/journal-entries/:entryId/edit",
    ids: { a1: null, r10: null },
    note:
      "Editing a draft journal batch. No badge: no r10 drawing and no allocated " +
      "parent this screen is plainly a child of, so an id here would be minted, " +
      "which is the g29_allocated_badges.txt authority's to do. Reported, not " +
      "invented.",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/finance/journal-entries/:entryId",
    ids: { a1: null, r10: null },
    note:
      "One journal entry read back. No badge: no r10 drawing and no allocated parent " +
      "this screen is plainly a child of, so an id here would be minted, which is " +
      "the g29_allocated_badges.txt authority's to do. Reported, not invented.",
  },
  { path: "/:tenant/finance/taxes", ids: { a1: "S41", r10: "FIN-01.taxes" },
    note:
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `FIN-01.taxes` — a Finance tab, and FIN-01 is the parent this map already gives `/:tenant/finance/:tab`. Same shape as r10's own PLN-01.charges." },
  { path: "/:tenant/finance/gl", ids: { a1: "S56", r10: "FIN-02" } },
  {
    path: "/:tenant/finance/export",
    ids: { a1: "S42", r10: "FIN-03" },
    note: "S43's QuickBooks sync modal opens here and needs no route",
  },
  {
    path: "/:tenant/finance/cost-of-service",
    ids: { a1: "S73", r10: "FIN-01.costOfService" },
    note:
      "⚠ THIS NOTE READ \"NO A1 ID, AND App.tsx's OWN COMMENT CLAIMS ONE\" UNTIL " +
      "2026-09-03, AND IT WAS RIGHT AT THE TIME. A1's CR-004 addendum only said the " +
      "two were \"taken by EP-LED-06\" in prose, so the inventory allocated neither " +
      "and this row carried no A1 id for eighteen days while App.tsx's comment read " +
      "`// S73·S74`. CR-060 C27 closed it: A1 now RATIFIES both in a dated addendum " +
      "(OQ-204 first half). `a1` is S73, the captured supplier-invoice register; S74 " +
      "is its Bought-vs-billed sub-view, reached inside this one route, which is why " +
      "one id sits here and not two." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `FIN-01.costOfService` — a Finance tab under the FIN-01 parent.",
  },
  {
    path: "/:tenant/finance/:tab",
    ids: { a1: "S36", r10: "FIN-01" },
    subIdFrom: { param: "tab" },
    note: "every tab with a real screen is declared above; the rest fall back to S36",
  },

  // ── Reports ─────────────────────────────────────────────────────────────
  { path: "/:tenant/reports/account-ledger", ids: { a1: "S59", r10: "RPT-02" } },
  { path: "/:tenant/reports/by-premises", ids: { a1: "S60", r10: "RPT-02" } },
  {
    // CR-060 C16 / T17 — the customer statement, routed 2026-09-02 and mapped
    // here on 2026-09-03 (DEF-3463). App.tsx's own comment records why there is
    // no A1 id: the report was designed after A1 was extracted from a prototype
    // that has since been deleted, so an id here would resolve to nothing. r10
    // draws no customer statement either — its `reports` branch is
    // `repView === 'grid' ? 'RPT-01' : 'RPT-02'`, and RPT-02 is the VIEWER,
    // which this is not. Both halves are absent and both absences are stated.
    path: "/:tenant/reports/customer-statement",
    ids: { a1: null, r10: "RPT-03" },
    note:
      "NO A1 ID and no r10 id. The customer statement (CR-060 C16 / T17) was " +
      "designed after A1 was extracted and r10 draws no statement screen. Reported, " +
      "exactly as /finance/write-offs and /billing/print are." +
      "⚠ AMENDED 2026-09-03 (PO: \"We need unique screen ID - on every screen\"): the badge is now `RPT-03`, MINTED — r10 draws RPT-01..02.",
  },
  { path: "/:tenant/reports", ids: { a1: "S44", r10: "RPT-01" } },
  // ── CR-142-BRC07 `P0.8` · the four reserved segments ────────────────────
  // Routed on 2026-09-26 with no screen behind them, so that `:reportKey`
  // below can never swallow four ordinary English words a utility could each
  // name a report. A1 already carries two of the four.
  { path: "/:tenant/reports/custom", ids: { a1: "S47", r10: "RPT-01" } },
  {
    // ── `DEF-REP-7640` (2026-09-28) · the builder on a BLANK definition ──
    // The SAME screen as `/:tenant/reports/:reportKey/edit` below, opened on
    // nothing — `ReportEditorPage` with `blank`, not a second component — so
    // it carries that row's pair rather than a new id. A1's S47 is *"Report
    // builder"*; r10 draws the builder nowhere and `RPT-02` is the badge the
    // editor already wears, for the reason that row records.
    path: "/:tenant/reports/custom/new",
    ids: { a1: "S47", r10: "RPT-02" },
  },
  {
    // NEITHER id, and both absences are stated. A1 was extracted from r9,
    // which drew no reports dashboard at all; r10 draws RPT-01 (the library)
    // and RPT-02 (the viewer) and no third reports screen. The Reports Build
    // Brief calls this tab *"the forty-sixth answer"* and says why it is a tab
    // rather than a card: a dashboard has no parameters, no rows and no file.
    path: "/:tenant/reports/dashboard",
    ids: { a1: null, r10: null },
    note:
      "NO A1 ID and no r10 id. The Reports dashboard (CR-142-BRC07, the " +
      "brief's §7.3 'forty-sixth answer') was designed after A1 was extracted " +
      "from a prototype that has since been deleted, and r10's reports branch " +
      "draws only RPT-01 and RPT-02. Both halves are absent and both absences " +
      "are stated, exactly as /reports/customer-statement's were.",
  },
  { path: "/:tenant/reports/scheduled", ids: { a1: "S45", r10: "RPT-01" } },
  {
    // A1 gives ONE row — S45, *"Reports scheduled & history"* — for what the
    // Reports Build Brief draws as two tabs. The id is shared rather than a
    // second one minted, because minting an S-id is A1's act and not a routing
    // table's; the split is REPORTED and belongs with the brief's tab strip.
    path: "/:tenant/reports/history",
    ids: { a1: "S45", r10: "RPT-01" },
    note:
      "S45 is A1's single 'Reports scheduled & history' row and this is the " +
      "second half of it. The brief draws Scheduled and History as two tabs; " +
      "A1 has not been re-extracted since r9 was deleted, so no separate id " +
      "exists to cite. REPORTED rather than minted here.",
  },
  {
    // ── `DEF-REP-7643` (2026-09-28) · THE ROW THAT WAS NEVER WRITTEN ──────
    // `a2ad9b6c8` (2026-09-27) registered `/reports/history/:runId` in
    // App.tsx — 5·2, the run dialog as an ADDRESS, so a row a clerk sends a
    // colleague opens the same run — and `git log -S 'history/:runId'` on
    // THIS file returns nothing at all. `screenIds.test.tsx` compares the two
    // lists in order and has been RED ever since, in a suite where a true red
    // in a file nobody is editing reads as somebody else's (hard-won law 7,
    // *proved red then never read*).
    //
    // It is the same screen as its parent — the dialog is 5·1 with one run
    // open, not a second screen — so it carries the same pair rather than a
    // new id, exactly as `/reports/custom/new` carries the builder's above.
    path: "/:tenant/reports/history/:runId",
    ids: { a1: "S45", r10: "RPT-01" },
    note:
      "5·2 is 5·1 with one run open — an ADDRESS for the dialog, not a " +
      "second screen — so it shares S45 with its parent. Added 2026-09-28 " +
      "(DEF-REP-7643); the route landed on 2026-09-27 without it and the " +
      "screen-id test was red for a day.",
  },
  // 2·2, the report BUILDER, moved to its own address by PO ruling 2026-09-28
  // (*"the report editor — panel or its own page - own page"*). A1's S47 is
  // *"Report builder"* and is the id this screen has always carried — it was
  // simply never an address of its own while the builder was `?edit=1` on the
  // viewer. r10 draws the builder nowhere, so the badge stays the VIEWER's
  // `RPT-02`: it is the same report, being worked on, and minting an r10 id is
  // not this table's act (see /reports/dashboard's note for the same rule
  // applied in the other direction).
  { path: "/:tenant/reports/:reportKey/edit", ids: { a1: "S47", r10: "RPT-02" } },
  { path: "/:tenant/reports/:reportKey", ids: { a1: "S46", r10: "RPT-02" } },

  // ── Work (CR-070 wave A · the shell, the Orders tab, the templates page) ─
  // Five flat routes in App.tsx's order. `/work` and `/work/orders` are ONE
  // screen — Work-007, the dispatcher's Orders tab, r10's WRK-01 (`16-work/
  // 01-overview.md` §6). No `Work-nnn` number renders: whether it ever does is
  // unruled (BR-WRK-005), and the badge is r10's module id as the 2026-08-19
  // ruling requires.
  {
    path: "/:tenant/work",
    ids: { a1: null, r10: "WRK-01" },
    note:
      "The Work shell (Work-006) landing on its Orders tab (Work-007) — CR-070 wave A, " +
      "2026-09-03, the day the PO ruled Work its own module. Until that day this path " +
      "was the registered not-built-yet destination. r10 draws WRK-01 for the dispatcher; " +
      "A1 allocates nothing (its reserved band is exhausted), which is REPORTED, not invented.",
  },
  {
    path: "/:tenant/work/orders",
    ids: { a1: null, r10: "WRK-01" },
    note:
      "The same screen as /work — the Orders tab, addressed explicitly so a link can " +
      "name it once the strip grows (wave B adds Awaiting approval, wave G the rest).",
  },
  // ── CR-070 wave H · the order in hand ──────────────────────────────────
  {
    path: "/:tenant/work/orders/:orderId/edit",
    ids: { a1: null, r10: "WRK-03" },
    note:
      "The work-order edit screen (Work-021) — CR-070 wave I, 2026-09-05. Everything a " +
      "dispatcher changes AFTER the order exists, behind a Change effects box that says what " +
      "Save does: the customer is told, the technician's phone changes under him, and every " +
      "field is logged with who and when. The badge is BORROWED, not minted: 01-overview.md " +
      "\u00a76 maps Work-021 to r10's WRK-03. A1 allocates nothing (its reserved S61\u2013S90 " +
      "band is exhausted), which is REPORTED, not invented. " +
      "\u26a0 The `:orderId` is a uuid in the ADDRESS and never on the page (B14 rule 31): " +
      "what a dispatcher reads and quotes is `WO-4821`. " +
      "\u26a0 The customer notification is a REAL SEND on the `appointment` message kind, " +
      "not the stub six documents still described on the day this shipped \u2014 " +
      "OQ-WRK-1495 closed 2026-09-04 and DEF-WRK-4028 records the gap.",
  },
  {
    path: "/:tenant/work/map",
    ids: { a1: null, r10: "WRK-09" },
    note:
      "The day's pins (US-WRK-029, WM-23) — CR-070 wave I, 2026-09-05. A sub-screen of " +
      "Work-007 with its own address, so the Map tab is a real link and a dispatcher can " +
      "bookmark the day. r10 draws WRK-09 for the map, so the badge is borrowed and nothing " +
      "is minted. A1 allocates nothing, which is REPORTED, not invented. " +
      "\u26a0 An order with no coordinate is LISTED in the *not on the map* strip and never " +
      "silently dropped: unlike a list, you cannot count pins, so a map that quietly omitted " +
      "them would be lying about the day with nothing on screen to show it.",
  },
  {
    path: "/:tenant/work/awaiting-approval",
    ids: { a1: null, r10: "WRK-20" },
    note:
      "The approval queue (Work-009) — CR-070 wave B, 2026-09-04. Every order the field " +
      "has finished that nobody has accepted, across every connection AND every order " +
      "standing on an address, an account or a meter with no connection at all. " +
      "⚠ The badge is MINTED, not borrowed: r10 draws WRK-01..18 and 01-overview.md §6 " +
      "reads — for this screen, so WRK-20 is allocated in g29_allocated_badges.txt the way " +
      "WRK-19 was for the templates page. A1 allocates nothing (its reserved S61–S90 band " +
      "is exhausted), which is REPORTED, not invented. " +
      "⚠ The queue is a NULL and not a table (BR-WRK-007): it is `state = completed` with " +
      "no accepted_by, so no migration created it and none can drop it.",
  },
  {
    path: "/:tenant/work/field",
    ids: { a1: null, r10: "WRK-26" },
    note:
      "From the field (Work-034) — CR-187-BRC10, EP-WRK-11, US-WRK-055. The office side " +
      "of the native field app: finished jobs with their outcome, reason, blocker, steps " +
      "left, photographs and cost, accepted, reopened or followed on. ONE screen, three " +
      "panes, three addresses (this and /raised, /alerts), so one badge. r10 predates the " +
      "field app and draws none of it, so WRK-26 is MINTED in g29_allocated_badges.txt.",
  },
  {
    path: "/:tenant/work/field/raised",
    ids: { a1: null, r10: "WRK-26" },
    note:
      "From the field · Raised on site (Work-034, US-WRK-056) — orders a technician " +
      "raised on a handset, waiting for the office to accept or refuse (E2E-16, R23).",
  },
  {
    path: "/:tenant/work/field/alerts",
    ids: { a1: null, r10: "WRK-26" },
    note:
      "From the field · Alerts (Work-034, US-WRK-057) — the dispatcher's alerts, and " +
      "which emergencies went five minutes unanswered (R28).",
  },
  {
    path: "/:tenant/work/field/findings",
    ids: { a1: null, r10: "WRK-26" },
    note:
      "From the field · Route findings (Work-034, BR-WRK-067) — what a meter reader " +
      "flagged on a route, and the work order the office raised from it. The fourth " +
      "pane of the same screen, so the same badge.",
  },
  {
    path: "/:tenant/work/field/refused",
    ids: { a1: null, r10: "WRK-26" },
    note:
      "From the field · Refused work (Work-034, CR-194-BRC10) — field work the server " +
      "refused, kept for the office to review or apply (PO 2026-10-26, \"store on " +
      "both\"). The fifth pane of the same screen, so the same badge.",
  },
  {
    path: "/:tenant/work/crews",
    ids: { a1: null, r10: "WRK-07" },
    note:
      "The crews list (Work-023) — CR-070 wave F, 2026-09-05. Four people, a crew and a " +
      "contractor in ONE table, because whoever the work is offered to the skill match is " +
      "the same test (BR-WRK-028). r10 draws WRK-07 for the crews screen and " +
      "01-overview.md \u00a76 maps Work-023 to it, so the badge is borrowed and nothing is " +
      "minted. A1 allocates nothing (its reserved S61\u2013S90 band is exhausted), which is " +
      "REPORTED, not invented. " +
      "\u26a0 The certification watch shows every expiry and its date and REFUSES NOTHING " +
      "by default: OQ-WRK-1493 was ruled per-tenant on 2026-09-04, defaulting to warn, so " +
      "the drawing's *blocked from 4 template types* sentence renders only where a utility " +
      "has switched blocking on. " +
      "\u26a0 TODAY and UTILISATION are NOT drawn \u2014 both are jobs belonging to a " +
      "person, and work_orders has no assignee column until wave G.",
  },
  {
    path: "/:tenant/work/crews/:slug",
    ids: { a1: null, r10: "WRK-08" },
    note:
      "One technician (Work-024) \u2014 CR-070 wave F, 2026-09-05. Overview and " +
      "Certifications; Jobs waits on wave G's assignee column and Audit on wave M's trail " +
      "reader, and neither tab is drawn until its screen exists (the rule WorkShell.tsx " +
      "states for the module strip). r10 draws WRK-08 and 01-overview.md \u00a76 maps " +
      "Work-024 to it \u2014 borrowed, nothing minted. " +
      "\u26a0 THE PATH SEGMENT IS A SLUG AND NOT AN ID: `r-patel`, computed per tenant, " +
      "which is the address WS-24 itself draws and what B14 rule 31 requires of the most " +
      "visible value a screen has. The other utility's `r-patel` answers 404, identical to " +
      "one that does not exist. " +
      "\u26a0 The three-step skills wizard is a SUB-SCREEN of this one and takes no id " +
      "(01-overview.md \u00a76 lists it among the seven undrawn r10 surfaces that do not).",
  },
  {
    path: "/:tenant/work/parts",
    ids: { a1: null, r10: "WRK-10" },
    note:
      "The parts register (Work-025) — CR-070 wave C, 2026-09-04. r10 draws WRK-10 for the " +
      "parts screen, so the badge is r10's own and nothing is minted. A1 allocates nothing " +
      "(its reserved S61–S90 band is exhausted), which is REPORTED, not invented. " +
      "⚠ The screen deliberately draws NO stock column, no reorder banner and no location: " +
      "the wireframe draws all three and the commitment card that specifies the same screen " +
      "forbids them, so the card wins (DEF-WRK-3550) and whether a stock table may exist at " +
      "all is OQ-WRK-1490, open.",
  },
  // ⚠ **`DEF-SHL-6047` — REGISTERED 2026-10-02, ONE OF TWENTY ROUTES THE
  // ROUTER SERVED AND THIS TABLE DID NOT HOLD.** Without a row the badge fell
  // to `/:tenant/*` and drew nothing (or, for two of them, a WRONG id).
  {
    path: "/:tenant/work/parts/import",
    ids: { a1: null, r10: "WRK-10.import" },
    note:
      "Importing parts, a child of the parts register (WRK-10), so a dotted sub-id " +
      "and no new number.",
  },
  {
    path: "/:tenant/work/rules/new",
    ids: { a1: null, r10: "WRK-13" },
    note:
      "The rule builder (Work-026's sub-screen) \u2014 CR-070 wave M, 2026-09-05; THREE " +
      "steps since CR-168-BRC10 round 5 (Trigger \u00b7 Notify \u00b7 Review, the 26 Sep " +
      "ruling, P3.64). r10 draws WRK-13 for it (01-overview.md \u00a76), " +
      "so the badge is BORROWED and nothing is minted. A1 allocates nothing (its " +
      "reserved S61\u2013S90 band is exhausted), which is REPORTED, not invented. " +
      "\u26a0 IT IS DECLARED BEFORE THE LIST BELOW because that is App.tsx's order, and " +
      "this table is asserted against the router element for element.",
  },
  {
    path: "/:tenant/work/rules/:ruleId/edit",
    ids: { a1: null, r10: "WRK-13" },
    note:
      "The SAME three-step builder re-opened on a rule (CR-168-BRC10 P3.17, lane RULES, " +
      "2026-10-04). One component at two addresses, like the template builder.",
  },
  {
    path: "/:tenant/work/rules/:ruleId",
    ids: { a1: null, r10: "WRK-06.rule" },
    note:
      "One rule's page — Overview · Jobs · Audit (CR-168-BRC10 P3.62, images " +
      "62–64, lane RULES, 2026-10-04). The drawings carry the rules screen's own WRK-06, " +
      "so the record is a dotted child of it and nothing is minted.",
  },
  {
    path: "/:tenant/work/rules",
    ids: { a1: null, r10: "WRK-06" },
    note:
      "Rules that raise work orders on their own (Work-026) \u2014 CR-070 wave M, " +
      "2026-09-05. RULE \u00b7 SOURCE MODULE \u00b7 TRIGGER \u00b7 TEMPLATE RAISED \u00b7 " +
      "PRIORITY \u00b7 THIS MONTH \u00b7 ENABLED. r10 draws WRK-06, so the badge is " +
      "BORROWED. " +
      "\u26a0 A rule that is OFF raises nothing (BR-WRK-033) and KEEPS its memory of what " +
      "it has already raised, so switching one back on does not re-raise every subject it " +
      "has ever seen.",
  },
  {
    path: "/:tenant/work/at-risk",
    ids: { a1: null, r10: "WRK-25" },
    note:
      "At risk, its own Work tab next to Orders (CR-168-BRC10 \u00a730, lane BOARDS, " +
      "2026-10-05). PO answer (1): \"Make At risk its own tab next to Orders\". The board " +
      "was a view of Performance under WRK-16; r10 draws no such screen, so WRK-25 is MINTED " +
      "in g29_allocated_badges.txt. /work/performance?view=at-risk forwards here.",
  },
  {
    path: "/:tenant/work/performance",
    ids: { a1: null, r10: "WRK-16" },
    note:
      "\u26a0 ADDED BY THE CR-070 WAVE M LANE, NOT BY THE WAVE THAT BUILT THE SCREEN " +
      "(DEF-WRK-4076). Wave N mounted this route in App.tsx and shipped no row here, so " +
      "screenIds.test.tsx \u2014 the one assertion that keeps this table and the router " +
      "identical \u2014 was RED on the branch before wave M touched it. The row is added " +
      "rather than left red because a red suite hides the NEXT regression too. " +
      "The badge and the note are taken from the screen file's own header and nothing " +
      "beyond it is asserted here.",
  },
  {
    path: "/:tenant/work/templates",
    ids: { a1: null, r10: "WRK-04" },
    note:
      "The templates LIST (Work-013) — CR-070 wave D, 2026-09-05. " +
      "\u26a0 THE BADGE MOVED FROM `WRK-19` TO `WRK-04`, AND `WRK-19` IS RETIRED IN " +
      "`g29_allocated_badges.txt` IN THIS COMMIT. `WRK-19` was MINTED on 2026-09-03 " +
      "for the BLANK page that stood here — four sentences saying *not built yet*, " +
      "on the PO's ruling of 2026-08-25 — because r10 draws no badge for a screen " +
      "that did not exist. It exists now: 01-overview.md §6 maps Work-013 to r10's " +
      "own `WRK-04`, so the borrowed id replaces the minted one and nothing stays " +
      "minted that does not have to be. No A1 id: A1's reserved S61–S90 band is " +
      "exhausted, which is REPORTED, not invented.",
  },
  // ── CR-070 wave E · the eight-step builder (Work-014…017) ───────────────
  //
  // ⚠ **THE BADGE IS r10's OWN AND IS NOT MINTED.** `SMARTBillHub.dc.html`'s
  // `sid()` emits `'WRK-05.' + (s.twStep || 1)` for the template wizard — a
  // badge PER STEP, exactly as `ONB-04.n` is drawn for the five-step signup —
  // and `01-overview.md` §6 maps `Work-013`–`017` to *r10 `WRK-04`, `WRK-05.x`*.
  // So the eight steps take `WRK-05.1` … `WRK-05.8` and `g29_allocated_badges.txt`
  // gains nothing.
  //
  // The step is `?step=` URL state (A9), which is why this row reads it from
  // the SEARCH string rather than from a path parameter — the same shape the
  // signup wizard's row uses, and the reason a person photographing step 5
  // reports `WRK-05.5` rather than a badge that is right for one step in eight.
  {
    path: "/:tenant/work/templates/new",
    ids: { a1: null, r10: "WRK-05.1" },
    byParam: {
      param: "step",
      from: "search",
      values: {
        "1": { a1: null, r10: "WRK-05.1" },
        "2": { a1: null, r10: "WRK-05.2" },
        "3": { a1: null, r10: "WRK-05.3" },
        "4": { a1: null, r10: "WRK-05.4" },
        "5": { a1: null, r10: "WRK-05.5" },
        "6": { a1: null, r10: "WRK-05.6" },
        "7": { a1: null, r10: "WRK-05.7" },
        "8": { a1: null, r10: "WRK-05.8" },
      },
    },
    note:
      "The eight-step template builder (Work-014…017) — CR-070 wave E, 2026-09-05. " +
      "No A1 id: A1's reserved S61\u2013S90 band is exhausted, which is REPORTED, not " +
      "invented. \u26a0 The STATIC `new` is declared before `:templateId` in App.tsx " +
      "and here, or `new` is read as a template id \u2014 wave D wrote that ordering " +
      "in advance for this exact sibling.",
  },
  {
    path: "/:tenant/work/templates/:templateId/edit",
    ids: { a1: null, r10: "WRK-05.1" },
    byParam: {
      param: "step",
      from: "search",
      values: {
        "1": { a1: null, r10: "WRK-05.1" },
        "2": { a1: null, r10: "WRK-05.2" },
        "3": { a1: null, r10: "WRK-05.3" },
        "4": { a1: null, r10: "WRK-05.4" },
        "5": { a1: null, r10: "WRK-05.5" },
        "6": { a1: null, r10: "WRK-05.6" },
        "7": { a1: null, r10: "WRK-05.7" },
        "8": { a1: null, r10: "WRK-05.8" },
      },
    },
    note:
      "The SAME builder, opened on a template that already exists \u2014 `Edit " +
      "template` on Work-022 (CR-070 wave E, 2026-09-05). One component at two " +
      "addresses rather than two copies of eight steps.",
  },
  // ⚠ THESE TWO SIT HERE, AFTER THE TEMPLATE ROUTES, BECAUSE `App.tsx`
  // DECLARES THEM HERE — and this map is trusted only because it mirrors that
  // file row for row. `DEF-WRK-4051`'s fix mounted them at the end of the work
  // block (with a good reason written beside it: the static `new` must precede
  // the dynamic `:orderNo`), and this map still had them up beside
  // `/work/orders`, so the mirror assertion was RED on the branch before this
  // wave touched it (`DEF-WRK-4056`). Moving the ROUTES instead would have
  // fought a deliberate placement; moving the ROWS costs nothing and restores
  // the one property that makes this file worth reading.
  {
    path: "/:tenant/work/orders/new",
    ids: { a1: null, r10: "WRK-12" },
    note:
      "The three-step New order wizard (US-WRK-028) — CR-070 wave H, 2026-09-05. " +
      "A SUB-SCREEN of Work-007 and not a Work- id of its own: `WM-20` is named in " +
      "`WS-07`'s footer as + New work order and drawn nowhere in the blueprint, and " +
      "`05-user-stories.md` §4 records the seven undrawn r10 surfaces exactly this way. " +
      "The badge is BORROWED, not minted — r10 draws WRK-01..18 and WRK-12 is its own " +
      "id for this surface, so nothing is allocated in g29_allocated_badges.txt.",
  },
  {
    path: "/:tenant/work/orders/:orderNo",
    ids: { a1: null, r10: "WRK-02" },
    note:
      "The six-tab order detail (Work-008, US-WRK-033) — CR-070 wave H, 2026-09-05. " +
      "Overview · Checklist · Parts · Location · Customer · Audit, on template W4. " +
      "⚠ EVERY COLLECTION ON IT IS THE ORDER'S OWN COPY (BR-WRK-008): publish v3 of the " +
      "template with an eighth task and this screen still shows seven, because the seven " +
      "are rows on the order and nothing here is read through `template_id`. " +
      "The badge is r10's own WRK-02, borrowed rather than minted.",
  },
  {
    path: "/:tenant/work/templates/:templateId",
    ids: { a1: null, r10: "WRK-15" },
    note:
      "The template DETAIL (Work-022) — CR-070 wave D, 2026-09-05. Overview · Usage · " +
      "Versions · Audit, with Duplicate, Deactivate and a Delete that is disabled " +
      "carrying the NUMBER of orders that came from the template (BR-WRK-012, " +
      "BR-SHL-025). r10 draws `WRK-15` and 01-overview.md §6 maps Work-022 to it, so " +
      "nothing is minted here either. " +
      "\u26a0 `Edit template` LANDED 2026-09-05 (CR-070 wave E). This note said it " +
      "was NOT rendered because the eight-step builder did not exist; the builder " +
      "exists, so the control is live and points at `\u2026/templates/{id}/edit`. " +
      "A refusal that has stopped being true is the mirror of dead UI (DEF-CWP-3925), " +
      "which is why it is corrected in the commit that lands the screen.",
  },

  // ── Everything with no screen ───────────────────────────────────────────
  {
    path: "/:tenant/*",
    ids: NONE,
    noScreen: "catch-all",
    note: "NotBuiltYetPage — the address has no screen, so the tag shows none",
  },
];

/** What `resolveScreen` answers with: the pair plus the row it came from. */
export interface ResolvedScreen extends ScreenIds {
  /** The table row that matched, so a caller can read its note. */
  readonly route: ScreenRoute | null;
  /** `S7 · DSH-01`, `S7`, `DSH-01`, or "" when the screen has neither name. */
  readonly label: string;
}

const NO_MATCH: ResolvedScreen = { a1: null, r10: null, route: null, label: "" };

/**
 * WHAT THE USER SEES: the r10 id, alone, or "" when r10 has no id for this
 * screen (PO ruling 2026-08-19 — see the header). The S-id is NEVER rendered;
 * it travels in `data-screen-a1` for the harness and the ticket.
 */
export function screenLabel(ids: ScreenIds): string {
  return ids.r10 ?? "";
}

/**
 * Which screen is this URL?
 *
 * `pathname` is the browser's path INCLUDING the tenant segment, and `search`
 * is `location.search` — the signup wizard's step is a query value, so a
 * resolver that only read the path would tag all five of its screens S110.
 */
export function resolveScreen(pathname: string, search = ""): ResolvedScreen {
  for (const route of SCREEN_ROUTES) {
    const match = matchPath(route.path, pathname);
    if (match === null) {
      continue;
    }

    let ids = route.ids;
    const read = (param: string, from: "route" | "search" | undefined): string | undefined => {
      if (from === "search") {
        return new URLSearchParams(search).get(param) ?? undefined;
      }
      return match.params[param] ?? undefined;
    };

    if (route.byParam) {
      const value = read(route.byParam.param, route.byParam.from);
      // An UNKNOWN value keeps the row's default rather than blanking the tag:
      // every one of these params already falls back to a default tab in its
      // own screen (settingsTabFromParam, paymentsTabFromParam), so a tag that
      // went empty would disagree with the screen the user is looking at.
      if (value !== undefined && value in route.byParam.values) {
        ids = route.byParam.values[value];
      }
    }

    // A DETAIL OPENED OVER A LIST AT THE SAME ADDRESS. Read AFTER `byParam`,
    // because `over` is stated in terms of what that resolved to, and BEFORE
    // `subIdFrom`, so a route that had both would extend the detail's id rather
    // than the list's.
    if (route.whenPresent && ids.r10 === route.whenPresent.over) {
      const value = read(route.whenPresent.param, route.whenPresent.from);
      // An EMPTY value is not a detail: `?template=` with nothing after it is
      // the list, and the screen itself treats it that way.
      if (value !== undefined && value !== "") {
        ids = route.whenPresent.ids;
      }
    }

    if (route.subIdFrom && ids.r10 !== null) {
      const value = read(route.subIdFrom.param, route.subIdFrom.from);
      // Only when the sub-id is not already the whole answer: r10 writes the
      // Plans tab `PLN-01` and the Charges tab `PLN-01.charges`, never
      // `PLN-01.plans`.
      if (value !== undefined && !(route.byParam && value in route.byParam.values)) {
        ids = { a1: ids.a1, r10: `${ids.r10}.${value}` };
      }
    }

    return { ...ids, route, label: screenLabel(ids) };
  }
  return NO_MATCH;
}

// ══════════════════════════════════════════════════════════════════════════
// THE ONE SWITCH — "for time bing" is the PO's own framing
// ══════════════════════════════════════════════════════════════════════════
/**
 * Whether the VISIBLE bottom-right tag is drawn.
 *
 * **TO TURN THE TAG OFF, IN ONE PLACE: build with `VITE_SCREEN_ID_TAG=off`.**
 * Nothing else in the product reads this, no component takes a prop for it, and
 * removing the diagnostic never means editing a screen.
 *
 * ⚠ The MACHINE-READABLE half is deliberately NOT behind this switch.
 * `data-screen-id` on `<body>` stays whatever the flag says, because the e2e
 * suite and DEF-137's coverage gate read it, and a diagnostic the PO switches
 * off must not silently take the test harness's only handle with it.
 */
export const SCREEN_ID_TAG_ENABLED: boolean = screenIdTagSwitch() !== "off";

/**
 * The raw value of the switch, read defensively.
 *
 * ⚠ `import.meta.env` IS A VITE FACT, NOT A JAVASCRIPT ONE. Vite substitutes it
 * at build time, and every other runtime that loads this module leaves
 * `import.meta.env` UNDEFINED — Playwright transpiles specs with its own loader,
 * and `e2e/CR-016-screen-ids.spec.ts` imports this file for the map. A bare
 * `import.meta.env.VITE_SCREEN_ID_TAG` threw `Cannot read properties of
 * undefined` there and collected zero tests, which is how this was found.
 */
function screenIdTagSwitch(): string {
  const meta = import.meta as { env?: { VITE_SCREEN_ID_TAG?: string } };
  return (meta.env?.VITE_SCREEN_ID_TAG ?? "").toLowerCase();
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-016 addendum "EVERY SCREEN CARRIES ITS ID, VISIBLE" (PO 2026-08-19) + DEF-137
// screens: every routed screen in the product — this file is the map
// generated: 2026-08-19 by story-coder (CR-016 screen-id lane) · AMENDED 2026-08-22 by the CR-028 AST-W4 lane (the four full-page lifecycle flows: /assets/new S51·AST-05, /assets/:assetId/reassign S55·AST-06, /assets/:assetId/maintenance/new S53·AST-07, /assets/:assetId/retire S54·AST-08 — all four carry BOTH ids, so the G29 baseline counts are unchanged)
// amended: 2026-08-26 by lane MOVEENTRY — the two STANDALONE move rows,
//         `/:tenant/move-ins/new` and `/:tenant/move-outs/new` (PO ruling
//         *"-Enable Move in /move out"*). Both carry ids from BOTH authorities —
//         A1's S19/S20 and r10's ACC-05/ACC-06 — because they are the SAME two
//         screens at a second address, so `screens_without_a1` and
//         `screens_without_r10` do not move and only the two totals rise. The
//         G29 baseline banks exactly those two and says so.
// checklist: A✔ B✔ C✔ D=deferred(no API call — the map is static data) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: g29_screen_ids.py, proved RED by pointing /:tenant/dashboard at "S999"
// exceptions: (1) a SECOND list of route patterns, held to App.tsx's by screenIds.test.tsx rather than by construction — the alternative spreads the map across 60 route literals where no reader can see it whole · (2) A1 sub-ids are NOT minted for tabs; only r10's half carries a sub-id, because r10 is the file that defines that convention
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
