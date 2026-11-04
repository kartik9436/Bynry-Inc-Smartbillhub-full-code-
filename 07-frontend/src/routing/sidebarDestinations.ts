// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-001 (the shell owns the app's URL shape and its nav config)
//           Screens: every screen the sidebar points at
// Rules:    BR-SHL-001 (the sidebar IS the declared nav config)
// ───────────────────────────────────────────────────────
// EVERY DESTINATION THE SIDEBAR OFFERS, AS PLAIN DATA.
//
// `SHELL_NAV` in `components/AppShell.tsx` is the ONE nav config and stays so.
// This file exists because that one carries inline SVG icons as JSX and imports
// `AppShell.css`, and the Playwright harness — which runs specs through a
// transpiler with no JSX-plus-CSS pipeline — cannot import it at run time. A
// browser smoke check that must visit every sidebar destination therefore needs
// the paths without the component.
//
// **THIS IS A SECOND LIST AND IT CANNOT GO STALE**, which is the only thing
// that makes a second list acceptable: `sidebarReachability.test.tsx` asserts it
// EQUALS `SHELL_NAV`'s own destinations, in order, in both directions — the
// G23/G25 discipline. Add a nav item and forget this file and that suite fails
// naming the path. Delete one and it fails the same way. A register that keeps
// claiming debt it has paid off is how a gate stops being a gate (DEF-077).
//
// Tenant-relative, like every route constant since path tenancy landed (PO
// 2026-08-10): the list states the SCREEN, `tenantPath()` states which utility.

/** Every path the sidebar can reach: each item, then its declared children. */
export const SIDEBAR_DESTINATIONS = [
  "/dashboard",
  "/plans-rates",
  // BR-SHL-001 amendment 2 (2026-08-16 / r10): Premises before Assets.
  "/premises",
  "/premises/units",
  "/assets",
  "/accounts",
  "/reads",
  // Entry 14's redirect: these two addresses forward to the Read cycles tab
  // and are no longer sidebar destinations (see AppShell's note).
  "/billing",
  "/payments",
  "/payments/record",
  "/payments/outstandings",
  // r10 / CR-003 placed the rail entry; CR-070 wave A (2026-09-03) made it a
  // screen — the Work shell with its Orders tab (the PO ruled the module its
  // own that day). Its not-built-yet register entry left in the same commit.
  "/work",
  "/finance",
  // CR-060 T10 (2026-09-02) added Revenue & AR as a Finance child in
  // `SHELL_NAV` and did not add it here — DEF-3463, the second of the three
  // mirrors that commit left behind.
  "/finance/revenue",
  "/finance/deposits",
  "/finance/taxes",
  "/finance/export",
  // BR-SHL-001 amendment 3 (PO 2026-09-06, "Nav bar will have Runbook as menu
  // item - above reports module"): Runbooks sits between Finance and Reports.
  // It opens the not-built-yet screen until CR-075 wave D routes RBS-001.
  "/runbooks",
  "/reports",
  "/reports/account-ledger",
  "/reports/by-premises",
  "/settings",
] as const;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-001@b16a4de (story+rules snapshot — the same packet sidebarReachability.test.tsx carries; BR-SHL-001's nav config) + 12-governance/10-defect-log.csv DEF-176
// generated: 2026-08-16 by story-coder (DEF-176 finance-route outage lane)
// checklist: A✔ B✔ C✔ D=deferred(no API call — this module is the sidebar's own paths as data) E=deferred(no screen — the SCREEN half is e2e/DEF-176-sidebar-smoke.spec.ts, which walks all 21 of these in a browser) F✔ G✔ H=deferred(PO 2026-08-09)
// gates: the equality assertion in sidebarReachability.test.tsx was proved RED by deleting "/finance/taxes" from this list — it failed naming that path
// exceptions: (1) a SECOND list of paths, held to the first by a test rather than by construction — the alternative was moving SHELL_NAV's paths out of AppShell.tsx, a refactor of a file other lanes were editing on the day this landed
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
