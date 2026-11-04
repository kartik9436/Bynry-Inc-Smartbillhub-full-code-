// ── Trace ──────────────────────────────────────────────
// Change:   CR-139-BRC08 · Finance blueprint `P2.18` — *"The Revenue & AR view
//           strip … five views — Services · Aging · Tie-out · Write-offs ·
//           Refunds — switched by `?view=`. The KPI strip sits above the strip
//           on every view; pending counts ride in the labels."*
// Task:     `P2.18`, over `P1.15`'s four-view split on tab 1 (the SAME strip,
//           which is why this file exists at all)
// Rules:    B14 rule 43 (a piece of UI used twice is a COMPONENT — standalone
//           code inside a page is not reuse) · rule 21 (this file adds NO class
//           to any stylesheet; every class below is one `finance.css` already
//           declares, so `G31` owns it and is satisfied) · rule 44 (the drawing
//           says WHAT is on the screen and how it is arranged; our component
//           kit says HOW it is built and wins) · BR-SHL-011 (the URL grammar)
// Tests:    src/features/ledger/revenueArViews.dom.test.tsx
// Impacts:  features/ledger/RevenueArPage.tsx (five views) ·
//           features/ledger/GeneralLedgerPage.tsx (four views, was inline)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY A COMPONENT AND NOT A SECOND `<nav>` IN A SECOND PAGE
// ══════════════════════════════════════════════════════════════════════════
// `P1.15` built the General-ledger tab's four-view strip as ~25 lines of JSX
// INSIDE `GeneralLedgerPage.tsx`, a 1,273-line page. `P2.18` needs the same
// control on Revenue & AR. **Writing it a second time is precisely what B14
// rule 43 was ratified to stop** — PO, verbatim: *"make them coponents - dont
// write stand alone code , engineer it"*, ruled after *"use it"* turned out to
// mean 120 lines inline in a 4,186-line page, importable by nothing.
//
// So the strip moved here and BOTH pages mount it. The General-ledger strip is
// byte-for-byte what it rendered before — same `<nav className="fin-params">`,
// same `Button` variants, same `aria-current` — because a rule-43 extraction
// that also restyles a live screen is two changes wearing one commit, and the
// second one has no proof behind it.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE ACTIVE VIEW IS `primary` AND THE DRAWING DRAWS THE OPPOSITE EMPHASIS
// ══════════════════════════════════════════════════════════════════════════
// Blueprint p033, p034, p036 and p038 all draw the CURRENT view's label in
// muted grey and the other four in the accent — *"current is not a link"*,
// de-emphasis rather than emphasis. This renders the current one `primary` and
// the rest `ghost`, which is the opposite.
//
// **B14 rule 44 is why, and it is the ratified answer to exactly this**: the
// drawing says WHAT is on the screen and how it is ARRANGED — five labels, in
// that order, counts riding in two of them — and *"our token scale, spacing and
// component kit say HOW it is built and win every time."* The kit's way of
// saying *this one is current* is `Button variant="primary"` plus
// `aria-current="page"`, and tab 1's strip one click away already says it that
// way. Two adjacent strips in one product disagreeing about what "current"
// looks like is a worse outcome than either treatment on its own.
//
// **IT IS REPORTED, NOT SILENTLY FOLLOWED** (§16 of the UI skill, and rule 44's
// own clause): the divergence is named here, in this lane's README beside the
// screenshots, and in the decision log.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE COUNT IS THE WHOLE POPULATION, NEVER THE PAGE
// ══════════════════════════════════════════════════════════════════════════
// p038 states what the number is for in terms: *"The answer to 'a page lies
// about what is pending' is the count in the view label: `Write-offs · 2`
// states the true total on every page, so paging can no longer hide
// anything."* A caller that passes `rows.length` of the page on screen has
// built the lie the badge exists to end. `CountBadge`'s own header repeats it
// because this is the half that is easy to get wrong later.
import type { ReactNode } from "react";

import { Button } from "@/components/Button";
import { CountBadge } from "@/components/CountBadge";

import { FINANCE_TAB_REVENUE, financeTabPath } from "./financeShared";

/** One member of a view strip. */
export interface ViewStripItem {
  /** The `?view=` value. Never rendered — rule 31 keeps internal codes off the
   *  screen and this is one. */
  id: string;
  /** Already translated by the caller: the eleven catalogues are the page's
   *  business, not this component's. */
  label: string;
  /** The whole-population pending count, or `null`/`undefined` where this view
   *  has no such number. `0` renders nothing — see `CountBadge`. */
  count?: number | null;
  /** What the count is OF, for a screen reader. Required wherever `count` is,
   *  because a bare *"2"* tells a non-sighted user nothing. */
  countLabel?: string;
}

export interface ViewStripProps {
  /** ⚠ **ONE DECLARED LIST, AND THAT IS THE REVERSIBILITY HINGE.** The number
   *  of views on Revenue & AR was contested right up to the day this was built
   *  (five in the task table, eight in a same-dated log entry; the PO ruled
   *  *"5 is correct"*). Passing the set in means a future change to that answer
   *  is an edit to ONE array in the consuming page — never a rebuild of this
   *  control. */
  items: readonly ViewStripItem[];
  /** The `id` currently showing. A value not in `items` highlights nothing,
   *  which cannot happen through `viewFrom`-style resolvers and is not worth a
   *  throw. */
  active: string;
  onSelect: (id: string) => void;
  /** The `<nav>`'s accessible name — a strip with no name is one of several
   *  unlabelled landmarks on a page that already has a tab strip above it. */
  label: string;
}

export function ViewStrip(props: ViewStripProps): ReactNode {
  return (
    <nav className="fin-params" aria-label={props.label}>
      {props.items.map((item) => (
        <Button
          key={item.id}
          variant={item.id === props.active ? "primary" : "ghost"}
          aria-current={item.id === props.active ? "page" : undefined}
          onClick={() => props.onSelect(item.id)}
        >
          {item.label}
          <CountBadge count={item.count} srLabel={item.countLabel ?? ""} />
        </Button>
      ))}
    </nav>
  );
}

/**
 * The `?view=` switch, written once because both pages had the same bug in it.
 *
 * ⚠ **IT PRESERVES THE REST OF THE QUERY STRING, AND THAT IS `P1.9`'s FIX.**
 * The General-ledger strip originally called `setSearchParams({ view })`, which
 * REPLACES the whole query string: `q`, `sort`, `page` and every `f.*` were
 * wiped by changing section, and a browser Back could not bring them home. Only
 * `view` moves. Building the Revenue & AR strip without re-reading that fix is
 * how a fixed bug comes back in a new file.
 */
export function withView(current: URLSearchParams, view: string): URLSearchParams {
  const next = new URLSearchParams(current);
  next.set("view", view);
  return next;
}

/**
 * **THE ADDRESS OF ONE REVENUE & AR VIEW — THE ONE PLACE A DOOR NAMES IT
 * (`P2.23`).**
 *
 * `P2.18` turns one screen into five, and a restructure that moves doors is
 * *"exactly how a door ends up pointing at nothing, with every test green"* —
 * the blueprint's own outcome line for `P2.23`, citing hard-won law 2. Two
 * doors in this product already pointed at `/finance/revenue` and landed a
 * clerk on the board; with five views they land on **Services** instead of the
 * thing they promised.
 *
 * ⚠ **IT COMPOSES `financeTabPath` RATHER THAN CARRYING A SECOND LITERAL.**
 * That function is the one place deciding where a Finance tab lives — the
 * lesson of `DEF-PAY-6329`, where a door held `/finance` as a literal, `CR-060`
 * T10 moved what lives there, and a clerk pressed *"Open the Finance queue"*,
 * landed on the trial balance and **reported the write-off screen as missing**.
 * Nothing 404'd and nothing went red, because the wrong address is a real
 * working screen. If the tab moves again, every door moves with it.
 *
 * ⚠ **CALLERS PASS A MEMBER OF `REVENUE_AR_VIEWS`, AND THE TESTS ARE WHAT PIN
 * THAT.** The parameter is a plain `string` on purpose: typing it against the
 * union declared in `RevenueArPage` would make this module import that 1,800-
 * line page, which is a cycle for a door helper. `revenueArDoors.dom.test.tsx`
 * asserts every door's view value IS in that array, which is the check that
 * actually matters — a typo'd `?view=writeoff` resolves to the landing view and
 * looks fine.
 */
export function revenueArViewPath(view: string): string {
  return `${financeTabPath(FINANCE_TAB_REVENUE)}?view=${encodeURIComponent(view)}`;
}

export default ViewStrip;

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/07 Finance Blueprint.pdf p015 (`P2.18`), p032 (tab 2's
//         own screen count and task list), p033/p034/p036/p038 (the strip drawn
//         on four of the five views) — rendered at scale 3 and read as IMAGES
//         (B14 rule 42) · 04-docs/02-decisions/14-ui-conventions.md rules
//         21/31/43/44 · features/ledger/GeneralLedgerPage.tsx `P1.15`
// generated: 2026-09-24 by LANE FIN-P2B
// checklist: A✔ B=n/a(no endpoint) C✔ D=n/a E✔(two host pages) F✔ G✔ H=n/a
// exceptions:
//   E1 **THE ACTIVE VIEW'S EMPHASIS IS INVERTED FROM THE DRAWING** — rule 44,
//      set out in full in the header above. Reported, not silently followed.
//   E2 **NO CLASS ADDED AND NO TAILWIND UTILITY IN THIS FILE.** `fin-params` is
//      declared by `features/ledger/finance.css`, so `G31` owns this file and
//      is satisfied; the one Tailwind-bearing part is `CountBadge`, which is on
//      `route-b-migrated.txt` in its own right (B14 rule 21).
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
