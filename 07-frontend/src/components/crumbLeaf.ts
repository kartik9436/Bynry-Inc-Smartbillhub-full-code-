// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-002 (the topbar breadcrumb) — its `it.todo` "(leaf): detail
//           crumbs use the record's human identifier … lands with the consuming
//           detail screens", which is what this is
// Rules:    BR-SHL-004 (`Module › Sub-context`; ancestors link up, the leaf is
//           plain text; the browser tab mirrors the leaf)
// Defects:  DEF-374 (2026-08-21, OPEN since) — *"NO WIZARD OR DETAIL SCREEN CAN
//           SUPPLY ITS OWN BREADCRUMB LEAF"*. Its own fix_suggestion names this
//           shape: *"One shell-level mechanism (a context the screen sets, the
//           way the page title is set) fixes it for all five Plans & Rates
//           wizards, the three definition details and every record detail in
//           the product at once. Building it per screen is how the same
//           sentence gets written nine times and drifts."*
// ───────────────────────────────────────────────────────
// ONE EXTRA BREADCRUMB CRUMB, SUPPLIED BY THE SCREEN THAT KNOWS IT.
//
// `breadcrumbFor` resolves crumbs from `SHELL_NAV` and the PATHNAME alone, and
// it is right to: query params never move the breadcrumb (US-SHL-002 TC-3), and
// a record id is never a crumb (B14 rule 31 — no database id on screen). So a
// screen whose sub-context is not in the path — a tab riding in `?tab=`, a
// record whose human number only the screen has fetched — had no way to say so.
// `breadcrumbFor`'s own comment promised the leaf was *"the consuming detail
// screen's to supply when it lands"* and NOTHING WAS EVER BUILT FOR IT, which
// is hard-won law 1 in the shell: three wizard lanes in a row read that comment
// as a plan and moved on, each recording the same absence in its own file.
//
// ⚠ **IT IS A NO-OP OUTSIDE THE SHELL, ON PURPOSE.** The default context value
// is a function that does nothing, so the ~40 suites that mount a screen bare —
// no `AppShell`, no provider — behave exactly as they did and none of them can
// throw. That is the same posture `PageHeader`'s optional props take: absent,
// nothing renders and no pixel moves.
//
// ⚠ **IT IS A FUNCTION AND NOT A VALUE IN THE CONTEXT.** The shell holds the
// leaf in its own `useState` and passes the SETTER down; React guarantees a
// setter's identity is stable across renders, so the effect below runs when the
// LEAF changes and never because the shell re-rendered. A context carrying the
// leaf itself would have to be re-created on every keystroke in the global
// search box.
//
// ⚠ **THE CLEANUP IS THE HALF THAT MATTERS.** Navigating away unmounts the
// screen, and without `publish(null)` the old leaf would outlive it — a crumb
// naming the tab you just left, on a screen that never set one. That is hard-won
// law 2's mirror (a stale control over a live screen) in the breadcrumb.
import { createContext, useContext, useEffect } from "react";

/** The shell's own setter. The default does nothing — see the header. */
export const CrumbLeafContext = createContext<(leaf: string | null) => void>(() => undefined);

/**
 * Publish one extra, FINAL breadcrumb crumb for as long as this screen is
 * mounted. `null` publishes nothing, which is how a screen with no sub-context
 * (the Accounts tab of the register, a wizard on its first step) says so — an
 * empty crumb is not the same claim as no crumb.
 *
 * The text is the RESOLVED word a person reads, never a key and never an id:
 * this hook cannot translate and B14 rule 31 forbids the id.
 */
export function useCrumbLeaf(leaf: string | null): void {
  const publish = useContext(CrumbLeafContext);
  useEffect(() => {
    publish(leaf);
    return () => publish(null);
  }, [publish, leaf]);
}
