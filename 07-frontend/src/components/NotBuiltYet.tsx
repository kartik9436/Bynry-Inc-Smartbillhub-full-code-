// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-011 (EP-SHL-04 §Stories — the shared state patterns, each
//           existing exactly once) · US-SHL-001 (the shell owns the app's URL
//           shape, so it owns what an address with no screen renders)
//           Screens: none of its own — this is the state EVERY unrouted path
//           renders, inside the shell frame
// Rules:    BR-SHL-020 (a failure state is plain language, never a code) ·
//           BR-SHL-025 (something this deployment cannot honour renders WITH
//           its reason, never blank and never a bare absence) ·
//           BR-SHL-001 (the sidebar's own declared destinations) ·
//           BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// THE ONE DISTINCTION THIS FILE EXISTS FOR
// ══════════════════════════════════════════════════════════════════════════
// **"This screen is not built yet" is a legitimate state. `SMARTBillHub — W0
// scaffold` is not a way to say it.**
//
// That sentence is DEF-152, and it is the second time the same string reached a
// real user on a SIDEBAR item. Measured in a browser on 2026-08-16 against the
// live build, signed in as a brand-new tenant's owner, the whole content pane of
// `/{tenant}/reports` was:
//
//     SMARTBillHub — W0 scaffold
//
// DEF-129 was the identical string on `/{tenant}/dashboard` three days earlier —
// the first screen after every sign-in. Both times the gap was UNDERSTOOD and
// written down honestly (App.tsx said in as many words that `/reports` is S44
// and is not minted here) and both times a developer string shipped anyway.
//
// Every other unbuilt surface in this product already gets this right — the
// Accounts page has two such panels, Billing two, Payments three, Settings a
// whole family — and they read as considered product because each says what it
// is waiting for in the user's own language. The catch-all read as a broken
// deployment. Fixing the CATCH-ALL rather than the reports route is what closes
// the whole class: **any** unrouted path in the product used to fail this way,
// and there is no list of them because they are, by definition, the paths
// nobody enumerated.
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS RENDERS, AND WHY IN THAT ORDER
// ══════════════════════════════════════════════════════════════════════════
//   1. the destination's own NAME when the sidebar declares one, so the page a
//      user clicked to reach is the page that answers them;
//   2. WHAT THE SCREEN WILL DO — only when a register entry below states it.
//      There is no guessing: an address nobody declared gets the generic
//      sentence, which promises nothing;
//   3. WHAT IT IS WAITING ON, in the same voice;
//   4. anything under this destination that IS finished, as links, taken from
//      `SHELL_NAV`'s own child config so there is one source and not a second
//      hand-written list;
//   5. a way back to the Dashboard, because a user who lands here has nowhere
//      else to click.
//
// No ID, no story number, no wave name appears on screen. A1 ids, US- ids and
// OQ- ids are the ticket vocabulary (CLAUDE.md §Screen IDs); a utility clerk
// reading "S44 / US-REP-001" learns nothing and is being shown our filing
// system. The ids live in `reason` below, which is engineering-facing.
//
// ══════════════════════════════════════════════════════════════════════════
// THE REGISTER, AND WHY IT IS A REGISTER RATHER THAN A DEFAULT
// ══════════════════════════════════════════════════════════════════════════
// `UNBUILT_SIDEBAR_DESTINATIONS` is the exact, dated list of TOP-LEVEL NAV
// destinations this deployment knowingly cannot open, in the G23/G25 discipline:
// one line, a date, a reason long enough to be a reason, and what closes it.
//
// It is not a convenience list. `sidebarReachability.test.tsx` reads THIS array
// and fails when a sidebar path falls through to the catch-all without an entry
// — so adding a nav item that points at nothing is a red test, and the only way
// to make it green is either to build the screen or to write down, here, what
// the user will be told instead. It fails the other way too: an entry for a path
// that now resolves to a real screen is STALE and fails, so the register records
// the win and cannot keep claiming debt that is paid off (DEF-077 — a register
// nobody audits is how a gate becomes a hardcoded pass).
//
// **An entry here is not permission to ship a blank page.** It is the opposite:
// it obliges the destination to carry its own sentences, and the test asserts
// the SPECIFIC copy renders rather than the generic fallback.
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { SHELL_NAV } from "./AppShell";
import { PageHeader } from "./PageHeader";
// `DASHBOARD_ROUTE` is declared by `DashboardPage` and by no shared helper —
// `features/reports/reportsShared` exports the two REPORT routes (S59, S60) and
// not this one. Imported from its declaring module, which is what App.tsx does
// for the same constant. (Written down because the first draft of this file
// reached for `reportsShared` on the assumption that a `*Shared` file holds
// every route in its folder, and tsc caught it.)
import { DASHBOARD_ROUTE } from "@/features/reports/DashboardPage";
import { useTenantPath, withinTenant } from "@/routing/tenantPath";

import "./NotBuiltYet.css";
import { ButtonLink } from "@/components/Button";

/**
 * One knowingly-unbuilt sidebar destination.
 *
 * `bodyKey` and `waitingKey` are what the USER reads; `reason` is what the next
 * agent reads. Both are required — a destination registered without copy would
 * render the generic sentence, which is the "considered product" half missing.
 */
export interface UnbuiltDestination {
  /** Tenant-relative path, exactly as `SHELL_NAV` declares it. */
  path: string;
  /** YYYY-MM-DD this entry was written or last re-verified. */
  dated: string;
  /** Catalogue key: what this screen will do, in the user's language. */
  bodyKey: string;
  /** Catalogue key: what it is waiting on, in the user's language. */
  waitingKey: string;
  /** Engineering-facing: why it is unbuilt and what closes it. IDs belong HERE. */
  reason: string;
}

// This register was EMPTY between the reports screen landing and 2026-08-16 —
// its one entry, `/reports`, went out in the same commit as the screen that
// closed it, because an entry outliving its gap tells a user a finished screen
// is unfinished (hard-won law 1). It is the mechanism, not the list.
//
// It held one entry again from 2026-08-16 to 2026-09-03 — `/work` — and that
// was the case it was built for: prototype r10 drew a **Work** item on the
// rail, the PO asked for the rail to match, and the module behind it was an
// OPEN QUESTION (OQ-249: in scope or not, a tenth module or tabs on Assets,
// which tables it would own). Hiding the item would have misreported the
// product's shape; building it would have answered the question by writing
// code. The destination said what it was, in the user's language, instead.
//
// The PO ruled on 2026-09-03 — *"it will become the module itself"* — and the
// entry left in the same commit as the first real `/work` route (CR-070 wave A,
// the Work shell with its Orders tab), exactly as its own CLOSED BY clause
// said it must: an entry outliving its gap tells a user a finished screen is
// unfinished (hard-won law 1). The register is EMPTY again, and
// `sidebarReachability.test.tsx` is what proves every rail item lands on a
// real screen while it stays that way.
// It held one entry again on 2026-09-06 — `/runbooks` — for the few hours
// between the PO putting Runbooks on the rail (BR-SHL-001 amendment 3, *"Nav
// bar will have Runbook as menu item - above reports module"*) and CR-075 wave
// D task D2 landing `RBS-001` at that path. **The entry left in the same commit
// as the route**, exactly as its own CLOSED BY clause said it must and exactly
// as `/work`'s did before it: an entry outliving its gap tells a user a
// finished screen is unfinished (hard-won law 1), and that is
// `DEF-CWP-3925`'s whole mechanism — landing a screen and releasing the thing
// that pointed at it are two acts, and only the first feels like the work.
// The register is EMPTY again, and `sidebarReachability.test.tsx` is what
// proves every rail item lands on a real screen while it stays that way.
export const UNBUILT_SIDEBAR_DESTINATIONS: readonly UnbuiltDestination[] = [];

/** The register entry for a tenant-relative path, or null. */
export function unbuiltDestinationFor(relativePath: string): UnbuiltDestination | null {
  return UNBUILT_SIDEBAR_DESTINATIONS.find((entry) => entry.path === relativePath) ?? null;
}

/**
 * THE STATE AN ADDRESS WITH NO SCREEN RENDERS.
 *
 * Mounted at `path: "*"` inside the shell, so it keeps the sidebar, the topbar
 * and the tenant — a user is never dumped outside the product to be told a part
 * of it is unfinished.
 */
export function NotBuiltYetPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const tenantPath = useTenantPath();

  const relative = withinTenant(location.pathname);
  const declared = unbuiltDestinationFor(relative);
  const navItem = SHELL_NAV.find((item) => item.path === relative) ?? null;

  // The destination's own name when the sidebar has one; otherwise the state
  // names itself. Never the raw path — a URL in an <h1> is a developer string
  // wearing a different hat.
  const title = navItem === null ? t("shell.notBuilt.title") : t(navItem.labelKey);

  // Only a REGISTERED destination has children worth offering: an arbitrary
  // unrouted path has no declared siblings, and inventing some would be this
  // component guessing where the user meant to go.
  const ready = declared === null ? [] : (navItem?.children ?? []);

  return (
    <>
      <PageHeader title={title} />
      <div className="not-built" data-not-built-yet="true">
        <p className="not-built-body" role="note">
          {declared === null ? t("shell.notBuilt.generic.body") : t(declared.bodyKey)}
        </p>
        <p className="not-built-waiting">
          {declared === null ? t("shell.notBuilt.generic.waiting") : t(declared.waitingKey)}
        </p>
        {ready.length > 0 && (
          <div className="not-built-ready">
            <h3>{t("shell.notBuilt.readyNow")}</h3>
            <ul>
              {ready.map((child) => (
                <li key={child.path}>
                  <Link to={tenantPath(child.path)}>{t(child.labelKey)}</Link>
                </li>
              ))}
            </ul>
          </div>
        )}
        <ButtonLink variant="secondary" className="not-built-back"  to={tenantPath(DASHBOARD_ROUTE)}>
          {t("shell.notBuilt.backToDashboard")}
        </ButtonLink>
      </div>
    </>
  );
}

export default NotBuiltYetPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-011@41aa2ae (story+rules snapshot — 00-platform-shell/06-epics/EP-SHL-04-states-feedback.md §US-SHL-011 · 00-platform-shell/02-business-rules.md BR-SHL-020/025/044 · BR-SHL-001's own nav config · 12-governance/10-defect-log.csv DEF-152)
// generated: 2026-08-16 by story-coder (DEF-151/DEF-152 production-fix lane — the Reports sidebar item rendered the literal string "SMARTBillHub — W0 scaffold" to a production user, the second time that string reached one)
// checklist: A✔ B✔ C✔ D=deferred(no API call — this state exists precisely because there is no screen and no read behind the address) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: RED PROVED FIRST, twice — (1) in a booted browser against the live build, /{tenant}/reports rendered a content pane whose entire innerText was "SMARTBillHub — W0 scaffold"; (2) sidebarReachability.test.tsx fails naming /reports when its register entry is removed, and fails naming the developer string when App.tsx still mounts ModulePlaceholder. Both quoted verbatim in the lane report. tsc✔ eslint --max-warnings 0✔ vitest✔ vite build✔ run_gates✔
// exceptions: (1) THIS IS A SEVENTH SHARED STATE AND A18 DRAWS SIX. A18 §1-§6 are empty list, zero results, loading, failed-with-retry, inline validation and permission denied; "the screen behind this address is not built" is none of them, and rendering it as A18 §6 would tell a user they lack permission for a screen that does not exist. Reported, not resolved here: A18 owes a §7, and this file is what it would specify · (2) NO A1 SCREEN ID IS CLAIMED and none is invented — this is a state, not a screen, so `g25_screen_coverage.py`'s `screens:` stamp is deliberately absent (CLAUDE.md forbids renumbering A1) · (3) the register carries ONE entry today and the test enforces that it stays exact in both directions; a second entry is a process event, like surface_debt.txt
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
