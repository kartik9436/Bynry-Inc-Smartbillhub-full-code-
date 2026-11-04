// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-004 (EP-WRK-01) — the Work rail entry stops being a
//           not-built-yet screen and becomes the shell the dispatcher grows
//           into. Screens: Work-006 (the shell) · Work-007 (Orders tab) ·
//           Work-005 (Templates tab, the blank page until wave D)
// Rules:    BR-WRK-005 (screen ids recorded, none moves) · BR-SHL-001 (the
//           rail entry is unchanged — `/work` between Payments and Finance) ·
//           BR-SHL-044 / B14 rule 2 (ONE page header per screen, and the page
//           header is what draws a tab strip) · B14 rule 36 (compose the kit) ·
//           rule 21 (Tailwind utilities; this file is on route-b-migrated.txt
//           from its first commit) · rule 31 (no id on screen) · rule 32 (no
//           sentence on the strip) · CLAUDE.md hard-won law 2 (a tab pointing
//           at nothing is dead UI — the strip renders ONLY the tabs whose
//           screen exists at this wave)
// Tests:    src/features/work/WorkShell.test.tsx ·
//           src/routing/sidebarReachability.test.tsx (/work is a real screen)
// Impacts:  src/App.tsx (five routes mount this) · every Work list screen
//           (each spreads `useWorkTabs()` onto its own PageHeader)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE STRIP IS THE SHARED PAGE HEADER'S, NOT THIS MODULE'S — AMENDED
// 2026-09-05, `DEF-WRK-3955`.** The Product Owner put this module beside
// Payments and said, verbatim: *"work - tabs does not match with our UI rules -
// ensure you follow all UI rules for Work UI/screen while Ui is build as per
// images you ahev taken"*. Payments' tabs are UNDERLINED; Work's were BOXED.
//
// Nothing was wrong with the boxed strip. It rendered, it was reachable, it was
// accessible, and it passed `tsc`, eslint, every gate and every test — which is
// the point. It was a SECOND ANSWER to a question `components/PageHeader.tsx`
// already answers for eight other features, and a second answer drifts. B14
// rule 36 says so in the PO's own words (*"style guide and tailwind component
// remain same"*), and `DEF-CWP-3655` is the same shape one module along, where
// the portal grew a second kit that had to be folded back.
//
// ⚠ **AND THE DRAWING IS NOT THE AUTHORITY ON THIS ONE.** `Work-007.png` and
// `Work-009.png` both draw a boxed folder tab ABOVE the page head, and the
// strip built from them was a faithful copy. Rule 36 splits the two authorities
// exactly here: **the captured packs give LAYOUT and DETAIL, `r10` gives the
// VISUAL STYLE, and the shared component kit is how you comply.** A tab's shape
// and where it sits relative to the title are style. The divergence is stamped
// in `04-docs/05-modules/16-work/08-screen-layouts.md`, in the table that file
// keeps for exactly this.
//
// THE STRIP GROWS WITH THE WAVES, AND ONLY WITH THEM.
// `09-component-inventory.md` names eight tabs — Orders · Awaiting approval ·
// Map · Crews · Parts · Templates · Rules · Performance. Two had a screen at
// wave A: Orders (that wave's table) and Templates (the blank page the PO ruled
// on 2026-08-25, replaced in wave D). A tab for a screen that does not exist
// would be a control onto nothing (law 2, G13's shape), so `WORK_TABS` holds
// only the tabs whose screen exists, and each later wave appends its own in the
// commit that lands the screen. Add a tab here without its screen and the shell
// lies.
//
// FIVE AT THIS COMMIT — **Crews** (wave F, `Work-023`) joined on 2026-09-05,
// and before it Parts (wave C, `Work-025`) and Awaiting approval (wave B,
// `Work-009`) arrived from different lanes on the same day. They are kept in the INVENTORY's order rather than in the
// order the waves happened to land, because the strip is read by a dispatcher
// and not by a changelog — Awaiting approval sits beside Orders, which is the
// list it is the other half of.
//
// NOT A NESTED LAYOUT ROUTE, ON PURPOSE. React Router's `<Outlet/>` shape would
// put an `index` child under a parent that has its own element, and the
// screen-id table's flattening (`screenIds.test.tsx`) then sees the parent's
// path twice. `PremisesTabsPage` solved the same shape by mounting one
// component at three paths with a `tab` prop; this does the same with
// `children`, so every route is a flat row with exactly one screen id.
import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

import type { PageHeaderTab } from "@/components/PageHeader";
import { useTenantPath } from "@/routing/tenantPath";

/* ⚠ **EVERY WORK ROUTE CONSTANT IS DECLARED HERE, AND THAT MOVED ON 2026-09-05
   (`DEF-WRK-3955`).** Two of them used to live in the screen they open and this
   file imported them back — which was fine while nothing pointed the other way.
   The moment each screen started composing this module's strip, that became a
   CYCLE, and an import cycle in ES modules does not fail: the constant is
   simply `undefined` while the other module's body runs. `WORK_TABS` built two
   tabs whose `path` was `undefined`, `tenantPath` threw *"Cannot read
   properties of undefined"*, and `tsc` had nothing to say about any of it.

   So the strip owns the addresses and each screen re-exports its own, which
   keeps every existing `import { WORK_ORDER_TEMPLATES_ROUTE } from
   "./TemplatesPage"` working and leaves the dependency running one way. */

/** The rail entry — Work-006. Tenant-relative, like every route constant. */
export const WORK_ROUTE = "/work";
/** Work-007, the Orders tab. `/work` itself lands here too. */
export const WORK_ORDERS_ROUTE = "/work/orders";
/** `WRK-25` — the At risk tab (CR-168-BRC10 §30, lane BOARDS). PO answer (1)
 *  of 2026-10-05, verbatim: *"(b) Make At risk its own tab next to Orders,
 *  because the design says “a dispatcher opens it first”. Schedule and
 *  Raise across buildings stay inside Performance."* It was a view of
 *  Performance (`?view=at-risk`, 2.514.0) until then; that address now
 *  forwards here. */
export const WORK_AT_RISK_ROUTE = "/work/at-risk";
/** `Work-021` — everything a dispatcher changes after the order exists
 *  (CR-070 wave I, `US-WRK-031`). A uuid in the ADDRESS and never on the page:
 *  B14 rule 31 governs what a field SHOWS, not how a link is built. */
export const WORK_ORDER_EDIT_ROUTE = "/work/orders/:orderId/edit";
/** The day's pins — a sub-screen of `Work-007` with its own address, so the Map
 *  tab is a real link and a dispatcher can bookmark the day (`US-WRK-029`). */
export const WORK_MAP_ROUTE = "/work/map";
/** `Work-009`'s route — CR-070 wave B. */
export const WORK_AWAITING_APPROVAL_ROUTE = "/work/awaiting-approval";
/** `Work-034` — *From the field*, the office side of the native field app
 *  (CR-187-BRC10, EP-WRK-11). ONE screen, three panes, three addresses: the
 *  acceptance queue here, and the two below. */
export const WORK_FIELD_ROUTE = "/work/field";
/** `Work-034`'s second pane — orders a technician raised on site (US-WRK-056). */
export const WORK_FIELD_RAISED_ROUTE = "/work/field/raised";
/** `Work-034`'s third pane — the dispatcher's alerts (US-WRK-057). */
export const WORK_FIELD_ALERTS_ROUTE = "/work/field/alerts";
/** `Work-034`'s fourth pane — route findings (`BR-WRK-067`, PO 2026-10-22). */
export const WORK_FIELD_FINDINGS_ROUTE = "/work/field/findings";
/** `Work-034`'s fifth pane — field work the server refused, kept for the
 *  office (`CR-194-BRC10`, PO 2026-10-26, *"store on both"*). */
export const WORK_FIELD_REFUSED_ROUTE = "/work/field/refused";
/** `Work-023`, the crews screen — CR-070 wave F. */
export const WORK_CREWS_ROUTE = "/work/crews";
/** Work-025, the parts register — CR-070 wave C. */
export const WORK_PARTS_ROUTE = "/work/parts";
/** `Work-013`, the templates list — CR-070 wave D. */
export const WORK_ORDER_TEMPLATES_ROUTE = "/work/templates";
/** `Work-026`, the rules list — CR-070 wave M, `US-WRK-037`. The five-step
 *  builder is a SUB-screen at `/work/rules/new` and lives with its own file.
 *
 *  ⚠ **NO `:tenant` SEGMENT, LIKE EVERY ROUTE CONSTANT IN THIS MODULE** — see
 *  the note on `WORK_PERFORMANCE_ROUTE` below and `DEF-WRK-4051`. */
export const WORK_RULES_ROUTE = "/work/rules";
/** `Work-027`, the performance tab — CR-070 wave N, `US-WRK-054`.
 *
 *  ⚠ **NO `:tenant` SEGMENT, LIKE EVERY ROUTE CONSTANT IN THIS MODULE.**
 *  `App.tsx` mounts these under a `:tenant` route and registers each as
 *  `ROUTE.slice(1)`, so a constant that carried the tenant itself would come
 *  out `:tenant/:tenant/work/performance`, match nothing, and fall through to
 *  *"This screen is not built yet"* — with `tsc`, every test, the build and
 *  `G13` all passing over it. That is `DEF-WRK-4051`, which made both of wave
 *  H's screens unreachable from the day they shipped. */
export const WORK_PERFORMANCE_ROUTE = "/work/performance";

export type WorkTabId =
  | "orders"
  | "at-risk"
  | "map"
  | "approvals"
  | "field"
  | "crews"
  | "parts"
  | "templates"
  | "rules"
  | "performance";

export interface WorkTab {
  id: WorkTabId;
  path: string;
  labelKey: string;
  /** Further addresses that are the SAME tab — a screen whose panes each have
   *  their own address (`Work-034`). Absent = the tab is its one path. */
  subPaths?: readonly string[];
}

/** The tabs whose screen EXISTS at this wave — see the header.
 *
 * ⚠ **THE INVENTORY'S ORDER, NOT THE ORDER THEY WERE BUILT IN.**
 * `09-component-inventory.md` draws the strip as *Orders · Awaiting approval ·
 * Map · Crews · Parts · Templates · Rules · Performance*, so Parts sits
 * BEFORE Templates however late it arrives. A strip that grew in commit order
 * would reshuffle itself under a clerk every wave.
 *
 * ⚠ **AND THIS ARRAY IS EDITED BY MORE THAN ONE LANE AT A TIME.** Wave B adds
 * *Awaiting approval* while wave C adds *Parts*; whichever commits second must
 * re-derive this file from the pushed tip and re-apply its own entry, or a tab
 * disappears with a correct file count and a diff that never mentions it
 * (CLAUDE.md law 11's mechanism two). */
export const WORK_TABS: readonly WorkTab[] = [
  { id: "orders", path: WORK_ORDERS_ROUTE, labelKey: "work.tabs.orders" },
  // CR-168-BRC10 §30 — RIGHT AFTER ORDERS, by the PO's own answer (1) of
  // 2026-10-05: *"Make At risk its own tab next to Orders, because the design
  // says “a dispatcher opens it first”"*. The one tab placed by a ruling
  // rather than by the inventory's order.
  { id: "at-risk", path: WORK_AT_RISK_ROUTE, labelKey: "work.tabs.atRisk" },
  // CR-070 wave B — Work-009. Beside Orders because it is the same table seen
  // through the other window: open work here, finished-and-unaccepted there.
  { id: "approvals", path: WORK_AWAITING_APPROVAL_ROUTE, labelKey: "work.tabs.approvals" },
  // CR-187-BRC10 (EP-WRK-11) — `Work-034`, *From the field*. Beside Approvals
  // because it is the other half of the same desk: Approvals is the drawn
  // queue (`Work-009`); this is what the HANDSETS sent — finished jobs with
  // their outcome, orders raised on site, and alerts. One tab with three
  // panes rather than three tabs: the strip already held nine (see
  // `field/FieldDeskPage.tsx`).
  {
    id: "field",
    path: WORK_FIELD_ROUTE,
    labelKey: "work.tabs.field",
    subPaths: [WORK_FIELD_RAISED_ROUTE, WORK_FIELD_ALERTS_ROUTE, WORK_FIELD_FINDINGS_ROUTE, WORK_FIELD_REFUSED_ROUTE],
  },
  // CR-070 wave I — the same open orders drawn on the ground (`US-WRK-029`).
  //
  // ⚠ **PLACED WHERE THE INVENTORY DRAWS IT, NOT WHERE IT WAS BUILT.** The
  // strip reads *Orders · Awaiting approval · Map · Crews · Parts · Templates ·
  // Rules · Performance*, and a strip that grew in COMMIT order would reshuffle
  // itself under a clerk every wave. A first draft put Map beside Orders and
  // `WorkShell.test.tsx` said so — which is precisely what that assertion is
  // for.
  { id: "map", path: WORK_MAP_ROUTE, labelKey: "work.tabs.map" },
  // CR-070 wave F — `Work-023`. It sits BEFORE Parts because the inventory's
  // order is *Orders · Awaiting approval · Map · Crews · Parts · Templates ·
  // Rules · Performance*, and the strip is read by a dispatcher rather than by
  // a changelog. Map landed in wave I and now sits above.
  { id: "crews", path: WORK_CREWS_ROUTE, labelKey: "work.tabs.crews" },
  { id: "parts", path: WORK_PARTS_ROUTE, labelKey: "work.tabs.parts" },
  { id: "templates", path: WORK_ORDER_TEMPLATES_ROUTE, labelKey: "work.tabs.templates" },
  // CR-070 wave M — `Work-026`. BETWEEN Templates and Performance, which is
  // exactly where the note wave N left here said it would go: the inventory
  // draws the strip as *Orders · Awaiting approval · Map · Crews · Parts ·
  // Templates · Rules · Performance*, and a strip that grew in commit order
  // would reshuffle itself under a clerk every wave.
  { id: "rules", path: WORK_RULES_ROUTE, labelKey: "work.tabs.rules" },
  // CR-070 wave N — `Work-027`. LAST, and now genuinely last: Rules landed in
  // wave M and sits directly above.
  { id: "performance", path: WORK_PERFORMANCE_ROUTE, labelKey: "work.tabs.performance" },
];

/**
 * THE MODULE'S STRIP, AS THE SHARED PAGE HEADER'S OWN PROPS.
 *
 * Spread it: `<PageHeader title={…} {...useWorkTabs(sentence)} />`. What comes
 * back is `tabs`, `activeTabId`, `tabsLabel` and nothing else — the kit draws
 * the strip, so this module owns WHICH tabs exist and never how they look.
 *
 * ⚠ **THE ACTIVE TAB IS DERIVED FROM THE URL AND IS NOT PASSED IN.** A screen
 * that had to name its own tab would be stating a fact the router already
 * holds, and two answers to one question is how a figure drifts: the day a
 * route moves, a hand-written id keeps pointing at the old tab and no check in
 * this repo can see it. `PaymentsPage` reads its active tab from the route for
 * the same reason. `/work` is Orders — the rail entry and the Orders tab are
 * one screen (WRK-01) — and anything unrecognised selects NOTHING rather than
 * guessing, which is the behaviour `PageHeader` documents for an id that
 * matches no tab.
 *
 * ⚠ **THE SENTENCE IS THE ACTIVE TAB'S EXPLAINER, NOT A ROLL-UP.** It used to
 * ride in `rollup`, which has no width cap, so every Work screen's description
 * ran the full width of a 1440px window — B14 rule 18, which caps a description
 * at 80% (`--desc-measure`). `.page-header-explainer` is the slot that carries
 * that cap, and it is also where the kit puts a per-tab sentence: below the
 * strip, because the strip is what a returning user reaches for first
 * (`BR-SHL-044` property (b)).
 */
export function useWorkTabs(explainer?: string): {
  tabs: PageHeaderTab[];
  activeTabId: string;
  tabsLabel: string;
} {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const { pathname } = useLocation();
  const active = activeWorkTab(pathname);
  return {
    tabs: WORK_TABS.map((tab) => ({
      id: tab.id,
      label: t(tab.labelKey),
      // A REAL LINK, kept from the strip this replaces. `PageHeaderTab.to` was
      // added to the kit in the same commit precisely so that composing it cost
      // no behaviour: ⌘-click still opens a tab in a second window.
      to: tenantPath(tab.path),
      explainer: tab.id === active && explainer !== undefined ? explainer : undefined,
    })),
    // `?? ""` and not `?? WORK_TABS[0].id`: an unrecognised Work address must
    // select no tab at all rather than light up Orders (see above).
    activeTabId: active ?? "",
    tabsLabel: t("work.tabs.label"),
  };
}

/**
 * Which tab a Work address is on — exported so a test can ask without a DOM.
 *
 * `/work` and `/work/orders` are the same screen, so both answer `orders`. The
 * match is on the tenant-relative SUFFIX because every Work path is static and
 * every one of them sits under `/:tenant`.
 */
export function activeWorkTab(pathname: string): WorkTabId | null {
  const trimmed = pathname.replace(/\/+$/, "");
  if (trimmed.endsWith(WORK_ROUTE)) return "orders";
  for (const tab of WORK_TABS) {
    if (trimmed.endsWith(tab.path)) return tab.id;
    if (tab.subPaths?.some((sub) => trimmed.endsWith(sub))) return tab.id;
  }
  return null;
}

/**
 * The module frame — `data-work-shell` and the active tab, for the routes in
 * `App.tsx` and for anything reading the shell from outside.
 *
 * ⚠ **IT NO LONGER DRAWS A STRIP.** Each Work screen draws its own page header
 * and spreads `useWorkTabs()` onto it, because B14 rule 2 gives the page header
 * one owner per screen and the strip is part of that header. A frame that drew
 * a second strip above the header is what `DEF-WRK-3955` was.
 */
export function WorkShell(props: { tab: WorkTabId; children: ReactNode }) {
  return (
    <div data-work-shell="" data-work-active-tab={props.tab}>
      {props.children}
    </div>
  );
}

export default WorkShell;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-004@67caa1a9 (EP-WRK-01) · 09-component-inventory.md `WorkTabs` · 10-execution-plan.md wave A task A5
// generated: 2026-09-03 by the CR-070 wave A build lane
// checklist: A=n/a(no backend half — a strip) B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST — with `/work` still listed in UNBUILT_SIDEBAR_DESTINATIONS, sidebarReachability.test.tsx fails "STALE ENTRY: /work now resolves to a real screen"; quoted in the lane report. tsc · vitest · routeBUtilities.test.ts (every utility here compiles) · the cr070-a walkthrough reads the strip's computed style
// exceptions: five tabs of eight — stated in the header; each later wave appends its own with its screen (wave B added Awaiting approval, wave C added Parts, wave F added Crews; Map is wave I, Rules wave L, Performance wave M)
// AMENDED 2026-09-05 (DEF-WRK-3955, the Work UI conformance lane) — the hand-rolled
//   `WorkTabs` nav is DELETED and the strip is the shared `PageHeader`'s, so the
//   module stops being the one feature in eight whose tabs look different. The
//   drawing's boxed folder tab is a stamped divergence in 08-screen-layouts.md
//   (B14 rule 36: the pack gives layout, r10 gives style, the kit is how you
//   comply). Proved by looking, in Chromium, against Payments on the same run.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
