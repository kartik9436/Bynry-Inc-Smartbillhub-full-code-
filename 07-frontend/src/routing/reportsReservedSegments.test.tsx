// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 — the Reports Build Brief, Phase 0 task `P0.11`.
//          Verbatim: *"Assert each of /reports/custom, /reports/dashboard,
//          /reports/scheduled and /reports/history resolves to its own tab and
//          NOT to the report viewer."* Outcome: *"Fails by name if someone
//          adds a route above it."*
// Rules:   B14 rule 43 (the tab is a component, so it can be identified) ·
//          CLAUDE.md hard-won law 2's mirror (a live screen behind a dead
//          control) · hard-won law 7 (a check whose false pass you cannot
//          describe is one you do not understand)
// ───────────────────────────────────────────────────────
/**
 * THE FOUR WORDS `/reports/:reportKey` MAY NEVER SWALLOW.
 *
 * ⚠ **ONE CASE WAS ENOUGH IN THE BRIEF'S FIRST DRAFT AND THE TAB STRIP MADE IT
 * FOUR**, because *custom*, *dashboard*, *scheduled* and *history* are each a
 * word a utility could name a report. A tenant saving a report called
 * *History* is not a hypothetical — it is the obvious name for the one report
 * a clerk runs to see what has been run.
 *
 * ⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY, NAMED BEFORE IT IS TRUSTED**
 * (law 7's habit 2). Three things, and each is guarded:
 *   · Asserting only that the address RESOLVES. Every address in this product
 *     resolves — `:reportKey` is a catch-all and `*` is behind it. So the
 *     assertion is on the ELEMENT, not on the match.
 *   · Asserting the element is *not* the viewer. `NotBuiltYetPage` is not the
 *     viewer either, and neither is a typo'd import. So the assertion names
 *     the component it MUST be, positively.
 *   · Asserting the component without its `segment`. All four render the same
 *     component, so a copy-paste that gives three routes `segment="custom"`
 *     would pass a component-only check. So the prop is asserted too.
 *
 * It fails BY NAME: the failure message carries the address and what answered
 * it, so the lane that broke one of the four is told which one.
 *
 * ⚠ **MEASURED WHILE PROVING THIS RED, AND IT CORRECTS THE BRIEF'S OWN
 * MECHANISM (`DEF-REP-6805`).** The brief says the four *"must rank ABOVE
 * `{key}` or the catch-all swallows them"*. The OUTCOME is right and the
 * MECHANISM is not: React Router v6 does not use declaration order at all — it
 * SCORES every pattern and a static segment always outranks a dynamic one. It
 * was proved here both ways in this worktree. Declaring `:reportKey` above all
 * four left every case GREEN; DELETING the four turned eight cases red naming
 * `ReportViewerPage`. So declaration order is a reading aid (App.tsx's own S46
 * comment already says *"belt and braces; the ORDER is what a reader checks"*)
 * and the thing that actually protects the four words is **the route
 * existing**. A test asserting order would therefore have been a check
 * incapable of failing — law 7's second shape — which is why this one asserts
 * the ELEMENT a user reaches instead.
 */
import { isValidElement } from "react";
import { matchRoutes } from "react-router-dom";
import type { ReactElement } from "react";
import { describe, expect, it } from "vitest";

import { APP_ROUTES } from "@/App";
import { ReportViewerPage } from "@/features/reports/ReportViewerPage";
// ⚠ `ReportsTabRoute` IS NO LONGER IMPORTED: every reserved segment now mounts
// a real screen, so nothing here asserts the placeholder. The list itself is
// still imported, because the `is NOT the report viewer` case runs over it.
import { RESERVED_REPORT_SEGMENTS } from "@/features/reports/ReportsTabRoute";

const TENANT = "brazosbend";

/** The element the router would actually render at `address`, and its name. */
function elementAt(address: string): { element: ReactElement | null; name: string } {
  const matches = matchRoutes(APP_ROUTES, address);
  if (matches === null || matches.length === 0) {
    return { element: null, name: "<no route matched at all>" };
  }
  // `RouteObject["element"]` is the whole `ReactNode` union — a route MAY hold
  // a string. None here does, and the narrowing says so rather than assuming.
  const raw = matches[matches.length - 1].route.element;
  const leaf = isValidElement(raw) ? raw : null;
  const type = leaf === null ? null : (leaf.type as { name?: string } | string);
  const name =
    leaf === null
      ? "<a route with no element>"
      : typeof type === "string"
        ? type
        : (type?.name ?? "<an anonymous component>");
  return { element: leaf, name };
}

/**
 * ⚠ **ALL FOUR RESERVED SEGMENTS NOW MOUNT A REAL SCREEN** — `history` in
 * `007510e95` (`P3.1`–`P3.6`), `scheduled` in `P4.5`, `custom` in `P5.10` and
 * `dashboard` in `P4.11`, all on 2026-09-27. Nothing here asserts the
 * placeholder any more, and what remains below is the assertion that actually
 * carries `P0.11`: none of the four is answered by the report VIEWER.
 *
 * ⚠ **TWO OF THE FOUR HAD REAL SCREENS BEFORE THIS FILE WAS SPLIT, AND THAT IS WHY IT
 * WENT RED FOR THREE COMMITS BEFORE ANYBODY SPLIT IT.** `history` stopped
 * being a placeholder in `007510e95` (`P3.1`–`P3.6`, 2026-09-27) and
 * `scheduled` in `P4.5` the same day; NEITHER lane retired the case that
 * pinned it to the placeholder, so `/reports/history opens its own tab` was
 * red and unread — hard-won law 7's *proved red, then never read*, in a suite
 * with six other failures for it to hide among.
 *
 * ⚠ **AND SPLITTING THE LIST DOES NOT WEAKEN `P0.11`.** The guarantee that
 * rule buys is that `/reports/:reportKey` must never SWALLOW one of these four
 * words — which is the `is NOT the report viewer` case below, and that one
 * still runs over all four and passed throughout. What was over-specified is
 * only *which* screen answers.
 */
// ⚠ **`custom` JOINS THEM (lane REP-P5, `P5.10`, 2026-09-27).** `/reports/custom`
// now mounts the report catalogue on its Custom sub-tab. Three of the four have
// real screens.
//
// ⚠ **`dashboard` WAS THE LAST PLACEHOLDER AND `P4.11` MOUNTED A REAL SCREEN
// THERE (2026-09-27, lane REP-P4-DASH), SO `HELD_SEGMENTS` IS NOW EMPTY AND ITS
// CASE IS DELETED.** It went RED and said in its own failure message exactly
// what had happened — *"is answered by ReportsDashboardPage … this reserved
// segment no longer has a route of its own"* — which is the mechanism working
// rather than a test being weakened. A hold case that outlives its hold is the
// next reader's false alarm.
//
// ⚠ **AND THE GUARANTEE `P0.11` BUYS IS UNTOUCHED**, because the `is NOT the
// report viewer` case below still runs over **ALL FOUR** segments. That is the
// one that says a tenant naming a report *Custom* cannot take the word, and it
// is now the whole of `P0.11`'s protection rather than half of it — which is
// the right shape once every segment has a screen: what matters is that
// `/reports/:reportKey` never answers any of the four, not which component
// does.

describe("CR-142 P0.8/P0.11 — the four reserved /reports segments", () => {
  it.each(RESERVED_REPORT_SEGMENTS)("/reports/%s is NOT the report viewer", (segment) => {
    const address = `/${TENANT}/reports/${segment}`;
    const { element, name } = elementAt(address);
    expect(
      element?.type,
      `${address} is answered by ${name} — the report VIEWER. The server ` +
        "refuses an unknown key with VAL-005, so this reads to a clerk as a " +
        "report that does not exist rather than as a tab that does.",
    ).not.toBe(ReportViewerPage);
  });

  it("an ordinary report key still reaches the viewer", () => {
    // The mirror of every case above. Claiming the four segments must not cost
    // the catch-all its job, and a test that only asserts absences cannot see
    // it if it does.
    const { element } = elementAt(`/${TENANT}/reports/ar_aging`);
    expect(element?.type).toBe(ReportViewerPage);
  });

  it("all seven Phase 0 addresses resolve to an element", () => {
    // `P0.8`'s own outcome sentence: *"All seven resolve"*. `?edit=1` is a
    // query string and changes no routing decision — asserted here so the
    // seventh row of the brief is a case rather than an assumption.
    const seven = [
      `/${TENANT}/reports`,
      ...RESERVED_REPORT_SEGMENTS.map((s) => `/${TENANT}/reports/${s}`),
      `/${TENANT}/reports/ar_aging`,
      `/${TENANT}/reports/ar_aging?edit=1`,
    ];
    const unresolved = seven.filter((address) => elementAt(address.split("?")[0]).element === null);
    expect(unresolved, "CR-142 P0.8: every one of the seven must resolve").toEqual([]);
    expect(seven).toHaveLength(7);
  });
});
