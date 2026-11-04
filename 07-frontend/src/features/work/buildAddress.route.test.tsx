// ── Trace ──────────────────────────────────────────────
// Change:  CR-151-BRC09 §6 task R3 (PO ruling 2026-09-28) — a build gets its
//          own page again, at `/{tenant}/connections/{id}`, and the redirect
//          that answers that address today is deleted in the commit that
//          flips the route, never before it.
// Rules:   CLAUDE.md hard-won law 2's MIRROR — *"WHEN YOU WRITE A HOLD, WRITE
//          THE TEST THAT FIRES WHEN THE HOLD EXPIRES, in the same commit —
//          assert the destination by ADDRESS and by the screen id it opens"* ·
//          law 7 (*looking at the wrong thing*: a hold-expiry test once
//          asserted a screen was REGISTERED at an address while the router
//          mounted it somewhere else, and every check passed) ·
//          `12-governance/02-decision-log.md` 2026-09-28, which supersedes the
//          2026-09-04 "one destination" row in its FIRST CLAUSE ONLY
// Tests:   this file IS the test
// Impacts: src/App.tsx (the route) · src/routing/screenIds.ts (the badge) ·
//          src/features/work/BuildRedirect.tsx (deleted at the flip)
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS FILE EXISTS TO GO RED ON A DAY NOBODY IS THINKING ABOUT IT.**
// `CR-151-BRC09` §6a orders the work so that no link ever breaks: the doorway
// keeps answering `/{tenant}/connections/{id}` until the detail page is on the
// branch, and then ONE commit flips the element, deletes the doorway and
// restores the screen id. **Landing a screen and releasing the thing that
// pointed at it are two acts, and only the first one feels like the work** —
// which is how the customer portal's front page came to have two working doors
// out of eight over screens that had shipped days earlier (`DEF-CWP-3925`).
// So the moment the element stops being the doorway, the assertion below
// demands the badge, by name, in its failure message.
//
// ⚠ **THE COMPONENT NAME IS THE DISCRIMINATOR, NEVER THE ASSERTION, AND THE
// DIFFERENCE IS THE WHOLE OF LAW 7's *looking at the wrong thing*.** The test
// that failed that way asserted a screen was REGISTERED at an address and
// never asked what the ROUTER mounted there; both screens opened onto *"not
// built yet"* and every check passed. This one reads the router FIRST — what
// is actually mounted at the address — and then requires the registry to agree
// with it. Neither record can move without the other.
import type { ReactElement } from "react";
import type { RouteObject } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { APP_ROUTES } from "@/App";
import { SCREEN_ROUTES, resolveScreen } from "@/routing/screenIds";

/** The build's address, as a FULL route pattern, tenant segment included. */
const BUILD_ADDRESS = "/:tenant/connections/:connectionId";

/**
 * A concrete address of the kind a clerk has bookmarked. The id is a shape,
 * not a fixture: B14 rule 37 makes every drawn figure an illustration, and
 * nothing here depends on the value.
 */
const A_BOOKMARK = "/ottumwa/connections/8f14e45f-ceea-467a-9575-1c2d04b1e6ab";

/**
 * The name the doorway is mounted under while the page is being built. When
 * the route is flipped this simply stops matching and the page arm applies —
 * there is no list to remember to edit.
 */
const DOORWAY = "BuildRedirect";

/** The route object at a full pattern, or null — and the path it was found at. */
function findRoute(routes: readonly RouteObject[], want: string, parent = ""): RouteObject | null {
  for (const route of routes) {
    let here = parent;
    if (typeof route.path === "string") {
      here = route.path.startsWith("/")
        ? route.path
        : `${parent === "/" ? "" : parent}/${route.path}`;
      if (here === want && route.element !== undefined) {
        return route;
      }
    }
    if (route.children) {
      const found = findRoute(route.children, want, here);
      if (found !== null) {
        return found;
      }
    }
  }
  return null;
}

/** What `App.tsx` actually mounts there, by the component's own name. */
function mountedName(route: RouteObject): string {
  const element = route.element as ReactElement;
  const type = element.type as { name?: string; displayName?: string };
  return type.displayName ?? type.name ?? "";
}

describe("the build's address never stops answering", () => {
  // ⚠ THE BOOKMARK GUARANTEE, AND IT IS THE REASON THE ADDRESS DID NOT MOVE.
  // Wave O kept this route in 2026-09-04 rather than 404 every link the New
  // Connect wizard had handed out for three weeks; CR-151-BRC09 spends that
  // same property a second time by putting the page back at the SAME address.
  // A flip that deletes the route instead of swapping its element breaks every
  // one of those links, and this is what says so.
  it("is mounted in App.tsx, with an element", () => {
    const route = findRoute(APP_ROUTES, BUILD_ADDRESS);
    expect(route, `${BUILD_ADDRESS} must stay mounted — every bookmark and every
"Open this connection" link the wizard handed out resolves here (CR-070 §W.11,
kept by CR-151-BRC09 §8). Swap its element; never delete the route.`).not.toBeNull();
    expect(route?.element).toBeDefined();
  });

  it("has a row in the screen-id map", () => {
    // `screenIds.test.tsx` already asserts the two lists hold the same paths in
    // the same order. This is the one row THIS change is about, named so that a
    // failure here says which address rather than which index.
    expect(SCREEN_ROUTES.map((entry) => entry.path)).toContain(BUILD_ADDRESS);
  });
});

describe("the hold expires the day the page lands, and this is what fires", () => {
  it("keeps the router and the screen-id map telling one story", () => {
    const route = findRoute(APP_ROUTES, BUILD_ADDRESS);
    expect(route).not.toBeNull();
    const row = SCREEN_ROUTES.find((entry) => entry.path === BUILD_ADDRESS);
    expect(row).toBeDefined();
    if (route === null || row === undefined) {
      return;
    }

    if (mountedName(route) === DOORWAY) {
      // ── THE HOLD IS STILL ON ──────────────────────────────────────────
      // A badge says *"this is a screen"*, and a reader who saw one flash and
      // then landed somewhere else would have been told two different things
      // about where they are. So a doorway carries none, and says why.
      expect(row.noScreen).toBe("redirect");
      expect(row.ids.a1).toBeNull();
      expect(row.ids.r10).toBeNull();
      return;
    }

    // ── THE HOLD HAS EXPIRED: SOMETHING OTHER THAN THE DOORWAY IS MOUNTED ──
    // Everything below is the release, and it is asserted BY SCREEN ID.
    const owed = `The build address now mounts a page, not the doorway, so
CR-151-BRC09 §6a's flip has begun. Finish it in THIS commit:
  1. 07-frontend/src/routing/screenIds.ts — the row for ${BUILD_ADDRESS} must
     drop \`noScreen: "redirect"\` and carry a real screen id again (NCT-02 was
     retired by CR-070 wave O and is re-allocated here).
  2. 10-scripts/gates/g29_allocated_badges.txt — the row wave O removed comes
     back, and G29's screen count rises by one.
  3. 07-frontend/src/features/work/BuildRedirect.tsx and its .dom.test.tsx are
     DELETED — a doorway nothing mounts is dead code that still looks wired.
A screen id is how a reader, a tester and the PO name this screen; a component
name is not on screen and nobody can quote it.`;

    expect(row.noScreen, owed).toBeUndefined();
    expect(row.ids.a1 ?? row.ids.r10, owed).not.toBeNull();

    // ⚠ AND IT MUST RESOLVE FOR A REAL ADDRESS, NOT ONLY IN THE TABLE.
    // A fixture that cannot tell a working link from a broken one is how the
    // portal's front page hid eight dead doors: mounted bare, `useParams()`
    // gave undefined and every address it built came out `//portal/…`, which
    // reads as a perfectly good string. So the pattern is exercised against a
    // CONCRETE bookmarked address, the way a clerk arrives.
    const resolved = resolveScreen(A_BOOKMARK);
    expect(resolved.a1 ?? resolved.r10, owed).not.toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-151-BRC09 §6 task R3 · PO ruling 2026-09-28 · decision log 2026-09-28 (late)
// generated: 2026-09-28 by the CR-151-BRC09 REVERSAL lane
// checklist: A✔ B=n/a C✔ D=n/a E✔(it reads App.tsx's own route table) F✔ G✔ H=n/a
// gates: proved RED before it was trusted green — by pointing DOORWAY at a name
//   nothing mounts, which is the flip simulated, and watching the release arm
//   demand the screen id. Green with the doorway in place, which is today.
// exceptions: E3 the component NAME is read, once, as the discriminator between
//   the two arms — never as an assertion. Stated at the top with the law-7
//   defect it would otherwise repeat.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
