// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-001 · US-SHL-002 · US-SHL-003 · US-SHL-004 · US-SHL-005 (EP-SHL-01 §Stories)  Screens: shell-chrome (hosts S7–S48 and every authenticated screen), S48
// Rules:    BR-SHL-001 (sidebar + canonical order) · BR-SHL-002 (persisted state — controlled here) · BR-SHL-003 (nav hidden per access)
//           BR-SHL-004 (breadcrumb + tab title) · BR-SHL-005/006 (global search scope/isolation — server-side) · BR-SHL-007/026 (bell) · BR-SHL-008 (user block + the four-item S48 menu)
//           BR-SHL-025 (an affordance the user cannot use renders DISABLED WITH ITS REASON, never absent)
// ───────────────────────────────────────────────────────
// FE-01 AppShell (B13 §1): the ONE authenticated frame — collapsible sidebar,
// topbar (breadcrumb · global search · notifications bell), sidebar footer
// user block — hosting every module screen through its <Outlet/>. Layout is
// ported from the signed prototype reference (05-prototype/UtilityBilling.html
// .app-shell/.sidebar/.topbar); its runtime is never ported (CLAUDE.md law).
// What is UI here vs. wiring that arrives later, honestly split:
//   · nav items are config-driven (SHELL_NAV) and RBAC-gated by the
//     SERVER-PROVIDED accessible-module set (BR-SHL-003; BR-SHL-025 forbids
//     client-side role-name checks, so the prop carries the membership's
//     server-computed set, not a role name);
//   · sidebar collapsed state is a controlled prop, and **IT IS NOT PERSISTED
//     TODAY** — nothing passes `collapsed`, so the shell keeps the choice in
//     internal state and forgets it on the next mount, exactly as the column
//     chooser did until DEF-647. This line used to claim that "persistence
//     lives in `user_preferences` via US-SHL-013's service, which the session
//     wiring reads BEFORE mounting the shell (no width flash)"; no such read
//     existed anywhere in this app, and hard-won law 1 is that a comment
//     claiming a guarantee is not the guarantee. Corrected 2026-08-24 with
//     DEF-647's fix, which built the missing half: `GET|PUT /user-preferences/
//     {key}` is SERVED now and `getUserPreference`/`putUserPreference` are
//     wrapped in `api/endpoints.ts`, so wiring `shell.sidebar_collapsed`
//     (BR-SHL-002/027) is a small, real piece of work with nothing blocking it
//     — REPORTED, not silently done here, because it is a second screen's
//     behaviour and belongs with its own walkthrough;
//   · the search box posts the debounced query (IS-3 mechanics via the ONE
//     createSearchDebouncer) to `onSearch` — the `GET /search` endpoint and
//     the grouped results popover land with FI-01 (BR-SHL-005/006);
//   · the bell renders the badge/popover shell from props — the BR-SHL-026
//     event feed, read-state writes and deep-links land with BE-09;
//   · the footer user block renders initials · name · current-tenant role
//     (BR-SHL-008) and opens the S48 menu — all FOUR of its items, three of
//     them disabled WITH their reason (see USER_MENU_ITEMS below);
//   · route-level permission blocks (A18 §6 on a direct URL) are FI-04 /
//     EP-SHL-06 scope — this file only hides nav items.
import { Fragment, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import { useTenantPath, withinTenant } from "@/routing/tenantPath";

// ── THE PRODUCT VERSION, READ FROM ITS ONE SOURCE ──────────────────────────
// `07-frontend/package.json`'s `version` field IS the single source of truth
// for the `<release>.<change>.<fix>` product version
// (12-governance/13-change-process.md §7, PO-ruled 2026-08-16). This import is
// a DERIVATION, not a copy: there is no version literal anywhere in this file,
// so the number on screen cannot drift from the number in the manifest.
//
// Why package.json and not a new VERSION file at the repo root: the frontend
// and the backend build from SEPARATE docker contexts (`./07-frontend` and
// `./06-backend`, docker-compose.yml), so no file above either directory is
// readable at build time. A root VERSION file would therefore have to be
// COPIED into both — three committed copies instead of two, which is hard-won
// law 5 pointing the wrong way. package.json is the one version field that
// already exists, that npm and vite require anyway, and that the running app
// can read with no build-config change.
//
// STILL OWED, and named here rather than assumed away (law 1): the ONE
// remaining derived copy is `06-backend/pyproject.toml`'s `version`, which
// Python packaging cannot read out of a JSON file in a sibling build context.
// Nothing yet fails when the two disagree. The gate §7.4 requires — "a gate
// refuses a CR marked done with no version" — does not exist either. Both are
// recorded as owed in 12-governance/11-change-requests.md (CR-004 §7).
// `DEF-CWP-9162` (2026-10-02) — read through `BuildVersion.tsx`, which re-exports
// package.json's version so the staff frame and both portal frames import ONE
// constant rather than three copies of this line.
import { APP_VERSION } from "./BuildVersion";

import { CrumbLeafContext } from "./crumbLeaf";
import { createSearchDebouncer } from "./DataTable";
import type { SearchDebouncer } from "./DataTable";
// US-SHL-003 — the results popover. Its own file because AppShell.tsx is not on
// `src/styles/route-b-migrated.txt` and cannot be, so a Tailwind utility written
// here would render as nothing at all (B14 rule 21's migration clause).
import { GlobalSearchResults } from "./GlobalSearchResults";
import { ProductName } from "./ProductName";
import type { SearchGroup } from "@/api/endpoints";

import "./AppShell.css";
import { Button, ButtonLink } from "@/components/Button";
import {
  HelpIcon,
  NavAccountsIcon,
  NavAssetsIcon,
  NavBillingIcon,
  NavDashboardIcon,
  NavFinanceIcon,
  NavPaymentsIcon,
  NavPlansRatesIcon,
  NavPremisesIcon,
  NavReadsIcon,
  NavReportsIcon,
  NavRunbooksIcon,
  NavSettingsIcon,
  NavWorkIcon,
  ShellBellIcon,
  ShellMenuIcon,
  ShellSearchIcon,
} from "@/components/icons";

/** DEF-450 — where the top-bar help control points, declared ONCE. `OQ-307`
 *  asks where it should really go, and this constant is the single place that
 *  changes when it is answered — not a literal in the markup.
 *
 *  ⚠ **IT IS `null` UNTIL THAT QUESTION IS ANSWERED, AND IT USED TO BE A REAL
 *  URL POINTING AT ANOTHER COMPANY'S PRODUCT (`DEF-SHL-7825`, found in a
 *  browser on 2026-09-28).** It read `https://code.claude.com/docs` — the
 *  documentation for the tool this product is BUILT WITH — so the `?` in the
 *  top bar of all 114 screens took a utility clerk out of the product and onto
 *  a page about writing code. **The comment here said *"the product's own
 *  documentation route"* and `OQ-307`'s register row said *"a page written for
 *  engineers"*, so both places a reader would check described a destination
 *  this constant did not hold** — hard-won law 1, exactly.
 *
 *  ⚠ **AND THE REPLACEMENT IS NOT A BETTER GUESS.** Choosing a destination
 *  here would answer `OQ-307` by picking a value, which the prime directive
 *  forbids. `BR-SHL-025` is the ruled shape for a control with nowhere to go —
 *  disabled, with its reason ON the control, never hidden — and `BR-SHL-008`
 *  already argues it in this same file: *"absence teaches a user the feature
 *  does not exist, a disabled item with its reason teaches them it is not
 *  ready"*. The PO asked for the icon (`DEF-450`), so the icon stays.
 *
 *  ⚠ **THE DAY THIS STOPS BEING `null`, RELEASE THE CONTROL.** `AppShell.test
 *  .tsx`'s *"the help control's hold"* cases assert BOTH halves and go red on
 *  a destination arriving, because landing the help centre and releasing the
 *  thing that pointed at it are two acts and only the first feels like the
 *  work (law 2's mirror, `DEF-CWP-3925`). */
export const HELP_ROUTE: string | null = null;

// ── Nav config (BR-SHL-001 — canonical order, submenus, inline-SVG icons) ──
// Icons are the prototype's inline stroke SVGs (A12: currentColor, no icon
// font) — static markup ported as layout, not runtime.

export interface ShellNavChild {
  path: string;
  labelKey: string;
}

export interface ShellNavItem {
  module: string; // matched against the server-provided accessible-module set
  path: string;
  labelKey: string;
  // ONE glyph from `components/icons.tsx` — `<NavPremisesIcon />`, not the
  // children of an <svg> this file draws (DEF-349). The 16px sizing rule
  // `.side-item .side-icon` travels with the glyph, so a rail item cannot be
  // given a shape that forgets it.
  icon: ReactNode;
  children?: ShellNavChild[];
}

// BR-SHL-001 as amended THREE TIMES. CURRENT ORDER (PO ruling 2026-09-06):
// Dashboard · Plans & Rates · **Premises · Assets** · Accounts · Reads ·
// Billing · Payments · **Work** · Finance · **Runbooks** · Reports · Settings.
// THIRTEEN items, not twelve.
//
// ⚠ THIS COMMENT SAID "amended TWICE … twelve items" UNTIL 2026-09-06, WHICH IS
// EXACTLY THE SHAPE AMENDMENT 1 CAME FROM — see the note under amendment 2. The
// rule was amended in 00-platform-shell/02-business-rules.md in the SAME commit
// as this file; neither is allowed to be the only place the order lives.
//
// Amendment 3 (2026-09-06) adds ONE item. PO verbatim: "Nav bar will have
// Runbook as menu item - above reports module."
//   · RUNBOOKS SITS BETWEEN FINANCE AND REPORTS, and it opens RBS-001, the
//     Runbooks home. ⚠ THIS BULLET READ "It resolves to the NOT-BUILT-YET
//     screen" FOR THE FEW HOURS BETWEEN THE RULING AND CR-075 wave D task D2,
//     which landed the screen at `/{tenant}/runbooks` the same day and deleted
//     the register row in the same commit.
//   · ⚠ AND THE HOLD SHIPPED WITH THE TEST THAT FIRED WHEN IT EXPIRED (hard-won
//     law 2's mirror, DEF-CWP-3925 — eight of a page's doors still refusing over
//     screens that had shipped days earlier, every check green).
//     features/runbooks/navHoldExpiry.test.tsx asserted the destination by
//     ADDRESS and by SCREEN ID, went red the moment D2 mounted RBS-001, and its
//     assertions were TURNED AROUND rather than deleted — it now holds the
//     opposite claim, which is the one worth keeping. G103 cannot see any of
//     this: that gate reads only files under portal/ and files declaring a CWP
//     screen, so it covers 36 portal holds and 0 staff-app holds.
//
// Amendment 2 (2026-08-16) does two things, both from prototype r10:
//   · PREMISES AND ASSETS SWAP. The rule said Assets first and this file
//     followed it; r10 draws Premises first. Asked directly which wins, the PO
//     ruled for r10. The rule was amended, not overridden here — a nav order
//     living in a comment and contradicting its own rule is how the FIRST
//     amendment came about.
//   · WORK IS ADDED, before Finance. It resolves to a NOT-BUILT-YET screen and
//     nothing more: whether Work is a tenth module owning its own tables or
//     tabs on Assets is OQ-249, and a rail entry is not permission to answer
//     it. The honest placeholder is the point — r10 shows the destination, so
//     hiding it would misreport the product's shape, and building it would
//     resolve an open question by writing code.
//
// Amendment 1 (2026-08-10, "Setting should be at last on nav bar") moved
// Settings from SECOND to LAST, and that half still stands. It closed the same
// kind of divergence: the rule said second, the prototype drew it last, and the
// code followed the rule until the PO saw the deployed sidebar.
//
// Billing deliberately has NO submenu (tabbed page).
//
// Every `path` below is TENANT-RELATIVE (PO 2026-08-10 path tenancy): the nav
// config states the screen, `tenantPath()` states which utility. That is what
// keeps one config serving every tenant and makes it impossible for a nav item
// to point at another tenant's data.
export const SHELL_NAV: readonly ShellNavItem[] = [
  {
    module: "dashboard",
    path: "/dashboard",
    labelKey: "shell.nav.dashboard",
    icon: <NavDashboardIcon />,
  },
  {
    module: "plans-rates",
    path: "/plans-rates",
    labelKey: "shell.nav.plansRates",
    // PO ruling 2026-08-10 ("In plan Nav bar - no sub menu required"). The
    // prototype's sidebar lists Plans & Rates as ONE item; the four sub-paths
    // are the page's own tab strip, and duplicating them in the sidebar gave
    // the same four destinations two different homes.
    icon: <NavPlansRatesIcon />,
  },
  // BR-SHL-001 amendment 2 (2026-08-16 / r10): Premises comes BEFORE Assets.
  {
    module: "premises",
    path: "/premises",
    labelKey: "shell.nav.premises",
    icon: <NavPremisesIcon />,
    children: [
      { path: "/premises", labelKey: "shell.nav.premises.premises" },
      { path: "/premises/units", labelKey: "shell.nav.premises.units" },
    ],
  },
  {
    module: "assets",
    path: "/assets",
    labelKey: "shell.nav.assets",
    icon: <NavAssetsIcon />,
  },
  {
    module: "accounts",
    path: "/accounts",
    labelKey: "shell.nav.accounts",
    icon: <NavAccountsIcon />,
  },
  {
    module: "reads",
    path: "/reads",
    labelKey: "shell.nav.reads",
    icon: <NavReadsIcon />,
    children: [
      { path: "/reads", labelKey: "shell.nav.reads.reads" },
      // ⚖️ **THE TWO NAV WORDS ARE GONE WITH ENTRY 14's REDIRECT.** A nav
      //    word pointing at a `<Navigate>` is a door to a door, and the Read
      //    cycles tab it forwards to is already reachable from *Meter
      //    Reads* above. The ADDRESSES stay routed — there are tickets with
      //    them in — and `ReadCyclesTab.test.tsx`'s pairing case is what
      //    made this due.
    ],
  },
  {
    module: "billing",
    path: "/billing",
    labelKey: "shell.nav.billing",
    icon: <NavBillingIcon />,
    // BR-SHL-001: Billing is a tabbed page — no submenu.
  },
  {
    module: "payments",
    path: "/payments",
    labelKey: "shell.nav.payments",
    icon: <NavPaymentsIcon />,
    children: [
      { path: "/payments", labelKey: "shell.nav.payments.summary" },
      { path: "/payments/record", labelKey: "shell.nav.payments.record" },
      { path: "/payments/outstandings", labelKey: "shell.nav.payments.outstandings" },
    ],
  },
  // BR-SHL-001 amendment 2 (2026-08-16 / r10): Work sits between Payments and
  // Finance. It is a RAIL ENTRY ONLY — `/work` resolves to the not-built-yet
  // screen (UNBUILT_SIDEBAR_DESTINATIONS names it), because the module behind
  // it is OQ-249: in scope or not, tenth module or Assets tabs, which tables it
  // would own. Showing the destination honestly is r10's shape; building it
  // would answer an open question by writing code.
  {
    module: "work",
    path: "/work",
    labelKey: "shell.nav.work",
    // A wrench — r10's own icon vocabulary for field work.
    icon: <NavWorkIcon />,
  },
  {
    module: "finance",
    path: "/finance",
    labelKey: "shell.nav.finance",
    icon: <NavFinanceIcon />,
    children: [
      // ⚠ CR-060 T10 — `/finance` LANDS ON THE TRIAL BALANCE now, so the crumb
      // for the bare path is the General Ledger's and Revenue & AR has a
      // segment of its own. These are BREADCRUMB data, not a submenu (the PO
      // removed sidebar submenus on 2026-08-10); a crumb still reading
      // "Revenue & AR" over the trial balance is hard-won law 1 in the one
      // place a user checks where they are.
      { path: "/finance", labelKey: "finance.tab.gl" },
      { path: "/finance/revenue", labelKey: "shell.nav.finance.revenue" },
      { path: "/finance/deposits", labelKey: "shell.nav.finance.deposits" },
      { path: "/finance/taxes", labelKey: "shell.nav.finance.taxes" },
      { path: "/finance/export", labelKey: "shell.nav.finance.export" },
    ],
  },
  // BR-SHL-001 amendment 3 (PO 2026-09-06): Runbooks sits between Finance and
  // Reports, and `/runbooks` opens RBS-001, the Runbooks home (CR-075 wave D
  // task D2, the same day). ⚠ THIS COMMENT SAID "RAIL ENTRY ONLY — `/runbooks`
  // resolves to the not-built-yet screen" until that landed; the register row
  // in UNBUILT_SIDEBAR_DESTINATIONS went out in the same commit as the route,
  // and `navHoldExpiry.test.tsx` is what made sure it did.
  {
    module: "runbooks",
    path: "/runbooks",
    labelKey: "shell.nav.runbooks",
    // A checklist on a clipboard — a written procedure that gets run.
    icon: <NavRunbooksIcon />,
    // No `children`: RBS-002..008 are the module's own screens and only
    // RBS-004 and RBS-006 are routed, both of them BELOW a runbook rather than
    // beside the home — so a breadcrumb child here would point at nothing.
  },
  {
    module: "reports",
    path: "/reports",
    labelKey: "shell.nav.reports",
    icon: <NavReportsIcon />,
    // The two ledger-owned report viewers that ship today (US-LED-009 · S59,
    // US-LED-010 · S60). `children` is BREADCRUMB data on this rail, not a
    // submenu — the PO removed sidebar submenus on 2026-08-10 and this file
    // keeps the config so US-SHL-002 can resolve a second crumb. Without these
    // two rows a user standing on the account-ledger report reads a breadcrumb
    // that says only "Reports". The report LIBRARY that would make them
    // reachable from the rail is S44 / US-REP-001 and is not built.
    children: [
      { path: "/reports/account-ledger", labelKey: "reports.ledger.title" },
      { path: "/reports/by-premises", labelKey: "reports.premises.title" },
    ],
  },
  {
    module: "settings",
    path: "/settings",
    labelKey: "shell.nav.settings",
    icon: <NavSettingsIcon />,
  },
];

// ── S48 user menu (BR-SHL-008 — the order IS the specification) ────────────
//
// 05-prototype/UtilityBilling.html:625-631 draws this menu, and its items and
// their ORDER are the spec:
//
//   Alex Reed                                   ← identity header, ruled off
//   alex@silvercreek.example · Owner
//   My profile
//   Change password
//   Two-factor authentication
//   ──────────────────────────────────────────  ← <hr class="hr">
//   Sign out                                    ← --color-accent, alone below the rule
//
// The app shipped ONE item ("Sign out") and nothing else — PO, live app,
// 2026-08-11: "in prototype there are 3 option when I click on it". That was a
// deliberate call recorded in ShellWithSession's header on 2026-08-10 ("three
// dead items on a menu are worse than a short menu that works") and it was the
// WRONG call: BR-SHL-025 already answers this question for the whole product —
// an affordance a user cannot use right now renders DISABLED WITH ITS REASON,
// never absent, so nobody hunts for a control that was hidden. The billing
// screens do exactly this for Void. Absence taught the user the feature does
// not exist; a disabled item with its reason teaches them it is not ready yet,
// which is the truth.
//
// WHY EACH IS UNAVAILABLE — two different reasons, so two different strings.
// This is not one blanket "coming soon":
//   · My profile / Change password — the SERVER routes exist and are served
//     (`PATCH /api/{tenant}/me`, `POST /api/{tenant}/me/password`, both in
//     06-backend/openapi/schema.json). What is missing is the S48 modal, which
//     is the open remainder of US-SHL-005. That is hard-won law 2 read from the
//     other end: an endpoint nothing calls. REPORTED, not silently deferred.
//   · Two-factor authentication — there is no endpoint at all, and BR-IDN-028
//     is explicit that no 2FA section exists on the v1 Security tab. A
//     different fact, so it gets a different sentence.
//
// The order lives here as DATA rather than as JSX so a test can pin it against
// the prototype without parsing markup, exactly as SHELL_NAV's order is pinned.

export interface UserMenuItem {
  id: string;
  labelKey: string;
  /**
   * BR-SHL-025: null = the item works. A key ⇒ it renders disabled and the
   * copy behind that key says WHY, on the control itself.
   */
  unavailableReasonKey: string | null;
  /** The prototype's `<hr class="hr">` — Sign out sits alone below the rule. */
  separatorBefore?: true;
}

/** BR-SHL-008's identity, as the shell needs it. */
export interface ShellUser {
  fullName: string;
  /** The S48 menu header's "email · role" line — the prototype's own copy. */
  email: string;
  /** The role of the CURRENT tenant's membership, never a global one. */
  roleName: string;
}

export const USER_MENU_ITEMS: readonly UserMenuItem[] = [
  {
    id: "profile",
    labelKey: "shell.user.myProfile",
    unavailableReasonKey: "shell.user.unavailable.myProfile",
  },
  {
    id: "changePassword",
    labelKey: "shell.user.changePassword",
    unavailableReasonKey: "shell.user.unavailable.changePassword",
  },
  {
    id: "twoFactor",
    labelKey: "shell.user.twoFactor",
    unavailableReasonKey: "shell.user.unavailable.twoFactor",
  },
  {
    id: "signOut",
    labelKey: "shell.user.signOut",
    unavailableReasonKey: null,
    separatorBefore: true,
  },
];

/**
 * The open S48 popover. Its own component, and exported, for one reason: this
 * project has no DOM library, so a menu that only exists inside AppShell's
 * `useState` could not be rendered in a test at all — and the last time this
 * menu went untested it shipped with one of its four items (DEF-038). Nothing
 * about it is conditional on a prop nobody passes: AppShell is its caller and
 * every prop here is required.
 */
export function UserMenu(props: {
  user: ShellUser;
  onSignOut: () => void;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="foot-menu" role="menu" aria-label={t("shell.user.menuLabel")}>
      {/* The prototype's ruled identity header: name, then "email · role". It
          answers "who am I signed in as, here" before offering anything to do
          about it — which in a multi-tenant product is the question. */}
      <div className="foot-menu-identity">
        <div className="foot-menu-name">{props.user.fullName}</div>
        <div className="foot-menu-meta">
          {t("shell.user.identity", { email: props.user.email, role: props.user.roleName })}
        </div>
      </div>
      {USER_MENU_ITEMS.map((item) => (
        <Fragment key={item.id}>
          {item.separatorBefore === true && <hr className="foot-menu-sep" />}
          {item.unavailableReasonKey === null ? (
            <button
              type="button"
              role="menuitem"
              className="foot-menu-item foot-menu-signout"
              onClick={() => {
                props.onDismiss();
                props.onSignOut();
              }}
            >
              {t(item.labelKey)}
            </button>
          ) : (
            // BR-SHL-025, exactly as GuardedButton renders a blocked Void:
            // disabled, with the reason ON the control. Not hidden — nobody
            // should have to hunt for a menu item that was taken away.
            <button
              type="button"
              role="menuitem"
              className="foot-menu-item"
              disabled
              aria-disabled="true"
              title={t(item.unavailableReasonKey)}
            >
              {t(item.labelKey)}
            </button>
          )}
        </Fragment>
      ))}
    </div>
  );
}

// ── Pure helpers (testable without a browser) ──────────────────────────────

// BR-SHL-003: items outside the server-provided accessible-module set are
// HIDDEN (A18 §6 "nav item is hidden where possible"). An undefined set means
// the identity wiring has not delivered one yet (FI-01/identity packets) —
// the shell renders ungated; the server stays the security boundary.
export function visibleNavItems(
  nav: readonly ShellNavItem[],
  accessibleModules?: readonly string[],
): readonly ShellNavItem[] {
  if (accessibleModules === undefined) {
    return nav;
  }
  return nav.filter((item) => accessibleModules.includes(item.module));
}

export interface CrumbSegment {
  labelKey: string;
  path?: string; // present = a clickable ancestor (BR-SHL-004)
}

// BR-SHL-004: `Module` on a module root; `Module › Sub-context` inside a
// declared sub-area. The pathname alone decides — and it is the TENANT-RELATIVE
// pathname (`withinTenant`), so `/brazosbend/premises/units` and
// `/lonestar/premises/units` produce the same crumbs from one config. Query
// params (`?step=`, `?tab=`) never move the breadcrumb (US-SHL-002 TC-3). A deeper path this
// config does not know (a record detail, an unknown id) falls back to the
// module segment (TC-5); the record's human-identifier leaf is the consuming
// detail screen's to supply when it lands — never a UUID.
export function breadcrumbFor(
  pathname: string,
  nav: readonly ShellNavItem[],
): CrumbSegment[] {
  const item = nav.find((i) => pathname === i.path || pathname.startsWith(`${i.path}/`));
  if (item === undefined) {
    return [];
  }
  const child = (item.children ?? []).find(
    (c) => c.path !== item.path && (pathname === c.path || pathname.startsWith(`${c.path}/`)),
  );
  if (child === undefined) {
    return [{ labelKey: item.labelKey }];
  }
  return [{ labelKey: item.labelKey, path: item.path }, { labelKey: child.labelKey }];
}

// BR-SHL-008: initials derive from the full name (first letters of first and
// last name — no avatar upload exists in B2 or the prototype).
export function initialsOf(fullName: string): string {
  const words = fullName.trim().split(/\s+/).filter((w) => w !== "");
  if (words.length === 0) {
    return "";
  }
  const first = words[0][0];
  const last = words.length > 1 ? words[words.length - 1][0] : "";
  return `${first}${last}`.toUpperCase();
}

// BR-SHL-007: unread badge caps its display at "9+" (the key holds the copy).
export const BELL_BADGE_CAP = 9;

/**
 * The bell's one-click door to *Messages needing attention* — PO 2026-10-22,
 * verbatim: *"B. Setup stays in one place, and clerks can still reach failed
 * messages in one click from the bell."* Settings → Configure → Notifications
 * → Messages needing attention. Spelled here rather than imported because the
 * frame may not import a feature screen; `bellMessagesLink.test.tsx` asserts it
 * equals `SettingsPage`'s `MESSAGES_NEEDING_ATTENTION_PATH` and that it routes.
 */
export const BELL_MESSAGES_PATH = "/settings/reference-data/notifications/messages";

// ── The component ──────────────────────────────────────────────────────────

export interface ShellBellItem {
  id: string;
  text: string; // event copy, produced with its module's packet (BR-SHL-026 catalog)
  read: boolean;
}

export interface AppShellProps {
  nav?: readonly ShellNavItem[]; // config-driven; defaults to the canonical SHELL_NAV
  // Server-provided accessible-module set for the CURRENT tenant membership
  // (roles → role_permissions, BR-SHL-025 — never a client role-name check).
  accessibleModules?: readonly string[];
  tenantName?: string; // sidebar tenant block; arrives with the session wiring
  // CR-048 wave D — the utility's own mark beside its name, PO 2026-08-27:
  // *"use them everywhere — bills, notices, the app header, the customer
  // portal."* A ReactNode rather than the mark's data, deliberately: this file
  // is shell chrome and must not learn what a `brand_primary_hex` is, and
  // `ShellWithSession` already holds the company profile this comes from.
  // NOT OPTIONAL-AND-UNPASSED: `ShellWithSession` passes it in the same commit
  // that adds it (hard-won law 2, which this very file has been the scene of
  // four times — the user block, sign-out, the tenant name and the bell).
  tenantMark?: ReactNode;
  // BR-SHL-008 footer block + the S48 menu's identity header. `email` is
  // REQUIRED, not optional: the prototype's menu header reads
  // "alex@silvercreek.example · Owner", and an optional field would be one more
  // prop nothing passes — the shape of DEF-007/008/009/010. Required means
  // `tsc` proves the caller supplies it; there is nothing left for a gate to
  // catch.
  user?: ShellUser;
  // BR-SHL-009 sign-out. REQUIRED. It was optional until 2026-08-11, and an
  // AppShell rendered without it had no way to sign out at all — which is
  // exactly what the PO found on the live deployment (DEF-008). A frame that
  // can render a signed-in user must be able to sign them out, so the type
  // system says so rather than a comment.
  onSignOut: () => void;
  // Controlled collapse. BR-SHL-002/027 want this persisted per user under
  // `shell.sidebar_collapsed`; NOTHING PASSES THIS PAIR TODAY, so the shell
  // holds the choice internally and loses it on remount (see the header note —
  // the endpoint exists since DEF-647; the wiring is REPORTED and unbuilt).
  collapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
  // ── US-SHL-003 · GLOBAL SEARCH, WIRED 2026-09-03 ─────────────────────────
  // `onSearch` fires the debounced IS-3 query; the four props under it are what
  // comes back. `ShellWithSession` passes all five — see the note above the
  // input for what changed and why the exemption that hid this prop is gone.
  onSearch?: (q: string) => void;
  searchGroups?: readonly SearchGroup[];
  searchStatus?: "idle" | "loading" | "error" | "ready";
  onSearchRetry?: () => void;
  formatSearchMoney?: (amount: string, currency: string) => string;
  bellItems?: readonly ShellBellItem[]; // newest-first as served (BR-SHL-007); BE-09 wiring later
  onBellSelect?: (item: ShellBellItem) => void; // deep-link to the subject record
  onMarkAllRead?: () => void;
}

export function AppShell(props: AppShellProps) {
  const { t } = useTranslation();
  const location = useLocation();
  // Path tenancy (PO 2026-08-10): the config is tenant-relative, the URLs are
  // not. `tenantPath` is the ONE builder every link in this frame goes through;
  // `here` is the same location with the tenant segment taken off, which is what
  // the nav/breadcrumb config is written against.
  const tenantPath = useTenantPath();
  const here = withinTenant(location.pathname);
  const nav = props.nav ?? SHELL_NAV;

  // BR-SHL-002: default expanded; controlled when the session wiring supplies
  // the stored preference (read BEFORE mount, so the first paint is right).
  const [internalCollapsed, setInternalCollapsed] = useState(false);
  const collapsed = props.collapsed ?? internalCollapsed;
  function toggleCollapsed(): void {
    const next = !collapsed;
    setInternalCollapsed(next);
    props.onCollapsedChange?.(next);
  }

  // US-SHL-003: the global search inherits IS-3 mechanics through the ONE
  // debouncer implementation (300 ms, min 2 chars) — never re-implemented.
  const [searchInput, setSearchInput] = useState("");
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const fireRef = useRef<(q: string) => void>(() => undefined);
  fireRef.current = (q) => props.onSearch?.(q);
  const debouncerRef = useRef<SearchDebouncer | null>(null);
  if (debouncerRef.current === null) {
    debouncerRef.current = createSearchDebouncer((q) => fireRef.current(q));
  }
  const debouncer = debouncerRef.current;
  useEffect(() => {
    const active = debouncerRef.current;
    return () => active?.clear(); // cancel a pending fire on unmount
  }, []);
  function handleClearSearch(): void {
    setSearchInput("");
    debouncer.clear();
    props.onSearch?.(""); // IS-3: ✕ clears immediately, no debounce
  }

  const crumbs = breadcrumbFor(here, nav);
  const leafKey = crumbs.length > 0 ? crumbs[crumbs.length - 1].labelKey : null;
  // ── US-SHL-002's `it.todo` (leaf) · DEF-374 ────────────────────────────────
  // The extra crumb a SCREEN supplies, because the shell cannot know it:
  // `breadcrumbFor` reads the pathname alone and must (TC-3 — `?tab=`/`?step=`
  // never move the breadcrumb), so a tab riding in the query string and a
  // record whose human number only the screen has fetched were both unsayable.
  // Held here rather than in a context VALUE so the setter's identity is stable
  // and `useCrumbLeaf`'s effect fires on the leaf and not on every re-render.
  // Nothing publishes by default: every screen that sets none renders the crumb
  // it always did, byte for byte.
  const [crumbLeaf, setCrumbLeaf] = useState<string | null>(null);
  // ⚠ WITH A LEAF, THE MODULE CRUMB STOPS BEING THE LEAF AND BECOMES AN
  // ANCESTOR — so it links. `breadcrumbFor` gives a module root no `path`
  // (its three signed assertions in `AppShell.test.tsx` pin that shape), so the
  // address is taken from the nav item here, with the same predicate that
  // matched it. A crumb that LOOKS like a way back and is not is a real defect
  // this product has already filed (`DEF-MET-5870`).
  const moduleHome = nav.find((i) => here === i.path || here.startsWith(`${i.path}/`))?.path;
  useEffect(() => {
    // BR-SHL-004: the browser tab mirrors the breadcrumb leaf — whichever crumb
    // IS the leaf, which is the screen's own once it publishes one.
    document.title =
      crumbLeaf !== null
        ? t("shell.docTitle", { leaf: crumbLeaf })
        : leafKey === null
          ? t("app.name")
          : t("shell.docTitle", { leaf: t(leafKey) });
  }, [leafKey, crumbLeaf, t]);

  const items = visibleNavItems(nav, props.accessibleModules);
  const bellItems = props.bellItems ?? [];
  const unread = bellItems.filter((item) => !item.read).length;

  return (
    // DEF-374 — the whole frame is inside the provider, because the crumb is
    // drawn in the topbar and published from the <Outlet/> below it.
    <CrumbLeafContext.Provider value={setCrumbLeaf}>
    <div className={`app-shell${collapsed ? " collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          {/* The name in two sizes and two colours (decision log 2026-10-02);
              `brand-name` is what the collapsed rail hides. */}
          <ProductName size="shell" className="brand-name" />
          {!collapsed && (
            <button
              type="button"
              className="nav-toggle"
              aria-label={t("shell.sidebar.collapse")}
              onClick={toggleCollapsed}
            >
              <ShellMenuIcon size={16} />
            </button>
          )}
        </div>

        {props.tenantName !== undefined && (
          // BR-SHL-008 sidebar tenant block. The prototype
          // (UtilityBilling.html:607) draws TWO lines and a chevron:
          //
          //     Silver Creek Water              ⌄
          //     1,247 connections · Growth
          //
          // and the app drew the name alone — PO, live app, 2026-08-11: "under
          // sliver Water Creek on Nav Bar # of accounts and growth plan is
          // shown; can you match that".
          //
          // THE SECOND LINE IS NOT RENDERED WITH NUMBERS, AND THAT IS THE
          // POINT. "1,247 connections · Growth" is prototype FIXTURE data. This
          // deployment serves neither figure:
          //   · no endpoint returns a connection count — `GET /accounts` is a
          //     paginated list behind the `premises_accounts` permission, and
          //     "connection" has no definition in A16 tying it to accounts,
          //     units, service points or meters. Counting a page of it here
          //     would print a number that is wrong in a different way on every
          //     screen;
          //   · no endpoint returns the SUBSCRIPTION plan name ("Growth").
          //     A1 §S8 puts it on the Plan tab with the entitlement counters,
          //     and `settings.arrivesWith.billingPlan` already says in the
          //     product that the subscription "arrives with the Billing plan
          //     feature".
          // So the line states the absence with its reason — the same call S30
          // makes for a draft bill's missing number (DEF-033), and the same one
          // BR-SHL-025 makes for a control you cannot use. A hardcoded 1,247
          // would have been a fabricated figure on every page of the product.
          //
          // NO CHEVRON. The prototype's `<svg>` here has no handler even in the
          // prototype — `.tenant` carries `cursor:pointer` and nothing else, so
          // the design specifies no behaviour for it. No story and no endpoint
          // covers switching tenants, and under path tenancy (PO 2026-08-10)
          // the tenant IS the URL. A disclosure control that discloses nothing
          // is a promise the product cannot keep, so it is omitted and the
          // decision is written down (12-governance/02-decision-log.md
          // 2026-08-11) rather than left for the next agent to "restore".
          <div className="tenant">
            {/* CR-048 wave D. `.sidebar .tenant` is `justify-content:
                space-between`, so a second child would be pushed to the far
                edge — the mark and the name are wrapped in one flex row
                instead. It is an inline style and not a class on purpose:
                B14 rule 21 forbids adding a stylesheet rule, and this file is
                not in `route-b-migrated.txt`, so a Tailwind utility here would
                render as nothing at all. */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
              {props.tenantMark}
              {/* ⚠ **THE SECOND LINE IS GONE — `DEF-2887`, PO 2026-08-31 from
                  the deployed product.** It rendered
                  `shell.tenant.metricsUnavailable` — *"Connections and plan not
                  shown yet"* — directly under `.tn`, so **every screen of the
                  product** read *"Silver Creek Water / Connections and plan not
                  shown yet"*. In an identity slot a sentence is read as
                  identity whatever it says, and this one had become part of
                  the utility's name.

                  ⚠ **AND THE ABSENCE IT STATED WAS STALE, WHICH IS HARD-WON
                  LAW 1 RUNNING BACKWARDS.** The long comment above still says
                  the subscription plan *"arrives with the Billing plan
                  feature"* and that the product says so at
                  `settings.arrivesWith.billingPlan`. **Both claims are now
                  false.** That key does not exist, and the FEATURE HAS
                  SHIPPED: `features/tenancy/SettingsBillingPlanTab.tsx` draws
                  `settings.billingPlan.plan.heading` — *"Subscription plan"* —
                  with the plan, its price and the band it is sized for. So the
                  shell was announcing a gap that had been closed, on every
                  page, in eleven languages. A stale absence-claim misleads
                  exactly as much as a stale guarantee; nothing in this repo
                  re-reads an absence when the thing it named arrives.

                  **NOTHING IS DELETED FROM THE PRODUCT.** The one figure still
                  genuinely unserved — the live connection count — is stated
                  where a person goes looking for it, on that same tab, at
                  `settings.billingPlan.plan.connectionsUnavailable`: *"Your
                  live account total is not counted against this range here."*
                  Law 1 is satisfied by the sentence existing in the right
                  place, not by it existing in every place.

                  **BOTH KEYS ARE DELETED FROM ALL ELEVEN CATALOGUES**, not
                  parked: `shell.tenant.metricsUnavailable` and
                  `.metricsReason` had exactly this one call site, and copy
                  that asserts something no longer true is worse kept than
                  gone. It also keeps `G18` at 232 dead / 0 unparked, and means
                  a lane that reinstates the line cannot quietly find its
                  sentence again. */}
              <div className="tenant-id">
                <span className="tn">{props.tenantName}</span>
              </div>
            </div>
          </div>
        )}

        <nav aria-label={t("shell.nav.label")}>
          {items.map((item) => {
            return (
              <div key={item.module}>
                <NavLink
                  to={tenantPath(item.path)}
                  className={({ isActive }) => `side-item${isActive ? " active" : ""}`}
                >
                  {item.icon}
                  <span className="side-label">{t(item.labelKey)}</span>
                </NavLink>
                {/* PO rulings 2026-08-10 — Plans & Rates ("no sub menu required")
                    and then Premises ("same is the case with premises UI; no
                    Sub menu"), each with a prototype screenshot: the sidebar
                    renders NO submenus. Every sub-destination is the page's own
                    tab strip; listing them in both places gave the same
                    destinations two homes and pushed the daily items down the
                    rail.
                    `children` REMAINS in the config on purpose. US-SHL-002's
                    breadcrumb resolves its second crumb from it, so deleting
                    the data as well as the rendering would degrade
                    "Finance › Deposits & Bank" to "Finance". One concern
                    changed, not two. */}
              </div>
            );
          })}
        </nav>

        {/* The running build's version, on screen. Change process §7 rule 2:
            "VISIBLE IN THE RUNNING APP. If a user cannot read the version on
            screen, a defect report cannot name it, and 'is it fixed?' becomes
            unanswerable." Two production defects were reported on 2026-08-16
            and neither the PO nor the product could say which build they were
            looking at; this element is the answer to that.

            RENDERED UNCONDITIONALLY, and that is deliberate. The user block
            below is optional (`props.user`), and a version a signed-out or
            half-loaded frame cannot show is a version missing from exactly the
            screenshot a defect report is most likely to carry.

            PLACED BEFORE the user block so that this element carries the flex
            column's ONLY `margin-top: auto` — two auto margins in one column
            split the free space and would float the user block into the middle
            of the rail. See AppShell.css.

            NOT translated, deliberately: `2.4.0` reads identically in all
            eleven locales, and a catalogue key here would invite someone to
            translate a number. */}
        <div className="sidebar-version" data-testid="app-version">
          v{APP_VERSION}
        </div>

        {props.user !== undefined && (
          // BR-SHL-008: initials avatar · name · CURRENT-tenant role, opening
          // the S48 menu UPWARD out of the footer. All four items render, in
          // USER_MENU_ITEMS' order; the three without a destination render
          // disabled WITH their reason (BR-SHL-025) rather than absent.
          <div className="foot-wrap">
            {userMenuOpen && (
              <UserMenu
                user={props.user}
                onSignOut={props.onSignOut}
                onDismiss={() => setUserMenuOpen(false)}
              />
            )}
            <button
              type="button"
              className="foot"
              aria-haspopup="menu"
              aria-expanded={userMenuOpen}
              onClick={() => setUserMenuOpen((open) => !open)}
            >
              <span className="av" aria-hidden="true">
                {initialsOf(props.user.fullName)}
              </span>
              <div className="foot-id">
                <div className="foot-name">{props.user.fullName}</div>
                <div className="foot-role">{props.user.roleName}</div>
              </div>
            </button>
          </div>
        )}
      </aside>

      <div className="main">
        <div className="topbar">
          {collapsed && (
            <button
              type="button"
              className="nav-toggle"
              aria-label={t("shell.sidebar.expand")}
              onClick={toggleCollapsed}
            >
              <ShellMenuIcon size={18} />
            </button>
          )}

          <nav className="crumbs" aria-label={t("shell.crumbs.label")}>
            {crumbs.map((segment, index) => {
              // ⚠ THE LAST CONFIG CRUMB IS ONLY THE LEAF WHILE NO SCREEN HAS
              // PUBLISHED ONE. With `crumbLeaf` set it is an ancestor, and an
              // ancestor links (BR-SHL-004).
              const isLeaf = index === crumbs.length - 1 && crumbLeaf === null;
              const to =
                segment.path ??
                (index === crumbs.length - 1 && crumbLeaf !== null ? moduleHome : undefined);
              return (
                <span key={segment.labelKey}>
                  {index > 0 && (
                    <span className="sep" aria-hidden="true">
                      ›
                    </span>
                  )}
                  {isLeaf || to === undefined ? (
                    // BR-SHL-004: the leaf is plain text, never a link.
                    <span className="cur">{t(segment.labelKey)}</span>
                  ) : (
                    // Ancestors link back up. Restoring the target list's
                    // prior URL state (IS-4) lands with the list screens'
                    // own URL-state wiring.
                    <Link to={tenantPath(to)}>{t(segment.labelKey)}</Link>
                  )}
                </span>
              );
            })}
            {crumbLeaf !== null && (
              // The screen's own crumb — DEF-374. Plain text, like every leaf,
              // and a WORD rather than a key or an id (B14 rule 31).
              <span key="__screen_leaf">
                <span className="sep" aria-hidden="true">
                  ›
                </span>
                <span className="cur">{crumbLeaf}</span>
              </span>
            )}
          </nav>

          {/* ── US-SHL-003 · THE BOX SEARCHES (PO 2026-09-03) ───────────────
              **THE DEF-2423 BRANCH IS GONE, AND ITS OWN COMMENT SAID IT WOULD
              GO THIS WAY.** From 2026-09-01 this input rendered DISABLED with
              *"Search is not available yet"* in the placeholder, because
              `onSearch` had no caller: the BE-08 kernel, this debouncer and the
              ✕ all existed and no route joined them. That was honest and it was
              never the goal — the old comment ended *"the day FI-01 lands, a
              caller passes `onSearch` and this whole branch goes away by
              itself"*. `GET /search` exists now
              (`06-backend/apps/tenancy/search_api.py`), `ShellWithSession`
              passes the handler, and the branch has gone. The
              `shell.search.unavailable` string is retired from all eleven
              catalogues in the same commit — a string nothing renders is the
              next lane's false lead.

              ⚠ **AND `check_unwired_props.py`'s BY-NAME EXEMPTION FOR
              `AppShell.onSearch` IS REMOVED IN THE SAME COMMIT.** It existed so
              G13 (built-is-not-wired) would pass on purpose while the endpoint
              was missing. Leaving it would leave the guard blind to this prop
              FOREVER, and the next lane to break the wiring would not be told —
              which is the defect G13 exists to catch, wearing the costume of
              its own exemption.

              THE BAR IS WIDER — the PO's *"if you have to increase the length
              of search bar please increase it"*, because nine groups is more to
              say than four. It is `flex: 0 1 360px` with `min-width` on the
              EXISTING `.shell-search` selector, so the bar SHRINKS before it
              pushes anything, and the bell and the help icon cannot be forced
              off the header at a narrow width. No media query and no new class.

              ⚠ `components/AppShell.tsx` is NOT on `src/styles/route-b-migrated.txt`
              and cannot be (the ledger says why: it builds a class name at
              runtime, which Tailwind's scanner cannot see), so a utility
              written HERE emits no CSS and renders as nothing at all. That is
              why the popover is `components/GlobalSearchResults.tsx` — new UI,
              in utilities, on the ledger — and why everything in this block
              still names a class `AppShell.css` already declares. */}
          <div className="shell-search">
            <ShellSearchIcon />
            <input
              type="search"
              value={searchInput}
              placeholder={t("shell.search.placeholder")}
              aria-label={t("shell.search.label")}
              onChange={(e) => {
                setSearchInput(e.target.value);
                debouncer.type(e.target.value);
              }}
            />
            {searchInput !== "" && (
              <button
                type="button"
                className="shell-search-clear"
                aria-label={t("shell.search.clear")}
                onClick={handleClearSearch}
              >
                ✕
              </button>
            )}
            {/* The popover hangs off `.shell-search`, which is already
                `position: relative` — so it is positioned without a new rule
                and without moving the header's layout. */}
            <GlobalSearchResults
              query={searchInput}
              groups={props.searchGroups ?? []}
              status={props.searchStatus ?? "idle"}
              onRetry={() => props.onSearchRetry?.()}
              onNavigate={handleClearSearch}
              toHref={tenantPath}
              formatMoney={
                props.formatSearchMoney ?? ((amount, currency) => `${amount} ${currency}`)
              }
            />
          </div>

          {/* DEF-450 — r10 draws a help control in the top bar, LEFT of the
              bell, and we drew only the bell. PO: "No help ? icon in the top
              bar".

              ⚠ **IT WAS A LINK AND IT IS NOW A DISABLED BUTTON, AND THAT IS A
              FIX RATHER THAN A RETREAT (`DEF-SHL-7825`).** This comment used to
              argue that a link was the honest shape because r10's bare
              `<button>` had no handler — true about r10, and it quietly assumed
              the href went somewhere of ours. It went to
              `https://code.claude.com/docs`. **A control that navigates is only
              more honest than one that does nothing if it navigates somewhere
              true**; pointing at another product's documentation is the same
              dead control with a longer walk.

              `BR-SHL-025` is the ruled shape and `USER_MENU_ITEMS` above uses
              it in this same file: disabled, `aria-disabled`, the reason ON the
              control, not hidden.

              ⚠ **THE LABEL IS THE ACCESSIBLE NAME AND THE REASON IS THE
              `title`, WHICH IS `RowAction`'s SHAPE COPIED RATHER THAN A SECOND
              ONE INVENTED** (`RowActions.tsx` — *"`reason` and `disabled` are
              ONE prop"*, `aria-label={label}`, `title={blocked ?? label}`).
              Every other blocked control in this product reads that way, and
              two shapes for one idea is how two screens start disagreeing
              (B14 rule 34's reasoning). It also keeps `shell.help.label` in
              use: putting the reason in both places would have orphaned it,
              and a key nothing reads is the next lane's false lead.

              ⚠ **AND ONE THING IS REPORTED RATHER THAN FIXED HERE.**
              `BR-SHL-025`'s own wording asks for *focusable*, and a `disabled`
              button is not focusable, so neither string reaches a keyboard-only
              user — true of `USER_MENU_ITEMS` beside it and of every
              `RowAction` in the product. Changing that is a product-wide
              decision about `aria-disabled` versus `disabled`, not one screen's
              to take, so this matches what ships and the gap is in the defect
              row instead.

              The day `HELP_ROUTE` holds a destination this goes back to being a
              link, and the test named in its docstring is what says so. */}
          <button
            type="button"
            className="shell-help"
            disabled
            aria-disabled="true"
            data-help-unavailable=""
            title={t("shell.help.unavailable")}
            aria-label={t("shell.help.label")}
          >
            <HelpIcon />
          </button>

          {/* US-SHL-004 bell shell — badge + popover from props; the
              BR-SHL-026 event feed and read-state writes land with BE-09. */}
          <details className="shell-bell">
            <summary
              aria-label={
                unread > 0
                  ? t("shell.bell.labelUnread", { count: unread })
                  : t("shell.bell.label")
              }
              title={t("shell.bell.label")}
            >
              <ShellBellIcon />
              {unread > 0 && (
                <span className="bell-badge" aria-hidden="true">
                  {unread > BELL_BADGE_CAP ? t("shell.bell.overflow") : String(unread)}
                </span>
              )}
            </summary>
            <div className="bell-menu">
              {bellItems.length === 0 ? (
                <p className="bell-empty">{t("shell.bell.empty")}</p>
              ) : (
                <>
                  {bellItems.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className={`bell-item${item.read ? " read" : ""}`}
                      onClick={() => props.onBellSelect?.(item)}
                    >
                      {item.text}
                    </button>
                  ))}
                  <Button
                    variant="ghost"
                    className="bell-mark-all"
                    onClick={() => props.onMarkAllRead?.()}
                  >
                    {t("shell.bell.markAllRead")}
                  </Button>
                </>
              )}
              {/* Shown whether or not the bell holds anything: a bounced email
                  is one click away from any screen (PO 2026-10-22). */}
              <ButtonLink
                variant="ghost"
                className="bell-mark-all"
                to={tenantPath(BELL_MESSAGES_PATH)}
                data-testid="bell-messages-link"
                onClick={(event) => event.currentTarget.closest("details")?.removeAttribute("open")}
              >
                {t("notifications.queue.listTitle")}
              </ButtonLink>
            </div>
          </details>
        </div>

        {/* ⚠ `DEF-MET-4959` — `view` IS LOAD-BEARING FAR BEYOND THIS FILE.
            `FormModal.css` declares `.view input/select/textarea` and `.view
            select`, so EVERY control in the product takes its height, padding,
            font and chevron from this one class name — including components
            that declare their own Tailwind sizes and silently do not get them.
            Renaming or restructuring this wrapper restyles the whole staff app
            with every check green. Measured on the Assets map: four selects,
            all six of their own utilities inert. */}
        <main className="view">
          <Outlet />
        </main>
      </div>
    </div>
    </CrumbLeafContext.Provider>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-001@b16a4de (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1 · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`) · AMENDED 2026-08-11 by story-coder v1 (S48 user-menu lane — PO live-app report: DEF-038 the menu had 1 of its 4 items, DEF-039 its popover named tokens that do not exist, DEF-040 the tenant block drew 1 of its 2 lines)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 94/94✔ (12 todo this packet — browser/server/consumer scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔ · 2026-08-11 S48 re-run: tsc✔ eslint✔ vitest✔ (2 expected-red copy tests — the 10 new keys belong to the i18n lane)
// exceptions: E4 [2026-08-11] the tenant block's SECOND line carries a stated absence, not the prototype's "1,247 connections · Growth": no endpoint serves a connection count (and A16 does not define "connection" against accounts / units / service points / meters) and none serves the subscription plan name. Rendering either would fabricate a figure — reported, not chosen · E4 [2026-08-11] the prototype's chevron on that block is NOT drawn: it has no handler in the prototype either, and no story or endpoint covers switching tenants · E4 [2026-08-11] three of the four S48 items render disabled with their reason; `PATCH /me` and `POST /me/password` are SERVED with no typed wrapper and no caller, which is the open remainder of US-SHL-005 (reported)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
