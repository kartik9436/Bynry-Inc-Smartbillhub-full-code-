// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `CR-138-BRC07` `P4.21` — *"The old refunds address 404s or
//           redirects **deliberately**. No silent dead link."* The move itself
//           is `P4.10`, which took S58 from `/finance/refunds` to
//           `/payments/refunds` and superseded `CR-059` §10's placement.
// Rules:    B14 rule 31 (no database id on screen — including the ADDRESS
//           BAR) · BR-SHL-025 · hard-won law 2's MIRROR (a live screen behind
//           a dead control; here, a live control in front of a moved screen)
// Defects:  `DEF-PAY-6297` — the three screens `fb3526105` routed have no
//           `SCREEN_ROUTES` row, so two carry NO screen id and one carries the
//           SUMMARY tab's. Pinned by value below.
// Screens:  S58 Refunds & credits (6·1) at its new address · the old one
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT WAS ALREADY COVERED, AND WHY IT IS NOT ENOUGH FOR THIS TASK
// ══════════════════════════════════════════════════════════════════════════
// `refundsAndCredits.dom.test.tsx` holds:
//
//     it("the old Finance address is still declared, so nothing in circulation
//        404s", () => { expect(REFUNDS_LEGACY_ROUTE).toBe("/finance/refunds"); });
//
// **That case asserts a STRING CONSTANT.** Delete the
// `{ path: REFUNDS_LEGACY_ROUTE.slice(1), element: <RefundsLegacyRedirect /> }`
// line from `App.tsx` entirely and it stays green, because a constant declaring
// an address is not the same fact as a router serving one. It is law 7's
// *looking at the wrong thing*, and `P4.21`'s whole subject — *no silent dead
// link* — is precisely the difference between the two.
//
// ══════════════════════════════════════════════════════════════════════════
// SO THIS FILE DRIVES THE APP'S OWN ROUTE TABLE
// ══════════════════════════════════════════════════════════════════════════
// `APP_ROUTES` is handed to `createMemoryRouter` and opened at the real
// address. **A test that writes its own `<Route>` is testing its own fixture**
// — that has already happened twice on this feature — and driving the app's
// own router is also the only way to see a `<Navigate>` actually navigate: a
// redirect is an EFFECT, so `renderToStaticMarkup` never runs it and a static
// render of this screen would show the redirect's markup (nothing) and prove
// the opposite of what it claimed. The destination is read off
// `router.state.location`, which is the router's own answer rather than a
// probe component's reading of it.
//
// ⚠ **AND THE DESTINATION IS ASSERTED TWICE, BY ADDRESS AND BY SCREEN** — the
// briefing's own requirement, and `DEF-CWP-3925`'s lesson: an address that
// looks right can open onto *"not built yet"*, and a screen that renders can be
// mounted at an address nothing links to.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { APP_ROUTES } from "@/App";
import { queryKeys } from "@/api/queryClient";
import type { SessionUser, ShellDisplay } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import { resolveScreen } from "@/routing/screenIds";
import { REFUNDS_LEGACY_ROUTE, REFUNDS_ROUTE } from "./paymentsShared";

const TENANT = "brazosbend";

// ⚠ **CLEANUP IS EXPLICIT.** This repo's vitest config declares no
// `setupFiles` and no `globals`, deliberately (see `vite.config.ts`), so
// `@testing-library/react`'s auto-cleanup never runs. Without this line the
// second case in a file renders a SECOND copy of the app over the first and
// every query throws *"Found multiple elements"* — which the first draft of
// this file did, and which reads like a product fault rather than a harness one.
afterEach(cleanup);

/** A clerk with the reach the refunds queue grants — `AdminOrClerk` server-side. */
const DANA: SessionUser = {
  id: "u-dana",
  full_name: "Dana Whitfield",
  email: "dana.whitfield@sample.test",
  phone: null,
  role: "billing_clerk",
  role_name: "Billing Clerk",
  must_change_password: false,
};

/**
 * `GET /shell/display` — **what the app shell BOOTS on, and without it nothing
 * below renders at all.**
 *
 * ⚠ The first draft of this file seeded only `queryKeys.me` and every case
 * asserted against `LoadingSkeleton`: `ShellWithSession` returns its skeleton
 * until this query resolves, so the route's element is never mounted, the
 * `<Navigate>` never fires, and the address never moves. **Three cases failed
 * loudly, which is the good outcome — a case asserting an ABSENCE would have
 * passed silently over a screen that was never rendered** (`DEF-SHL-4272`'s
 * own lesson, one layer down).
 */
const SHELL: ShellDisplay = {
  regional: {
    country: "US",
    timezone: "America/Chicago",
    language: "en",
    first_day_of_week: "sunday",
    currency: "USD",
    number_format: "1,234.56",
    date_format: "MM/DD/YYYY",
    time_format: "12-hour",
  },
  company: {
    legal_name: "Brazos Bend Utility District No. 1",
    dba_name: "Brazos Bend Utilities",
    has_logo: false,
    mark: { letters: "BB", background_hex: null, ink_hex: null, contrast_ratio: null },
    brand_primary_hex: null,
  },
  period: null,
} as unknown as ShellDisplay;

/** Open one address in **the app's own router** and let its effects run.
 *
 *  ⚠ `createMemoryRouter(APP_ROUTES)` and never a hand-written `<Route>`: a
 *  test that declares its own route table is testing its own fixture, which
 *  has already happened twice on this feature. The router is RETURNED so the
 *  destination can be read from `router.state.location` — the router's own
 *  answer to *"where did that go"*, rather than a probe component's.
 *
 *  ⚠ `render`, never `renderToStaticMarkup`: a `<Navigate>` redirects in an
 *  EFFECT, and a static render would show the redirect element's empty output
 *  while the address never moved — proving the opposite of what it claimed. */
function openAt(...entries: string[]) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  client.setQueryData(queryKeys.me, DANA);
  client.setQueryData(queryKeys.shellDisplay, SHELL);
  const router = createMemoryRouter(APP_ROUTES, {
    initialEntries: entries,
    initialIndex: entries.length - 1,
  });
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return router;
}

/** Every `path` the app's route table declares, at every depth — the same walk
 *  `screenIds.test.tsx` and `forcedPasswordChange.dom.test.tsx` already do.
 *  Asserted against the TABLE rather than by eye, because `/:tenant/*` matches
 *  every address and *"it rendered something"* proves nothing at all. */
function routePatterns(): string[] {
  const patterns: string[] = [];
  const walk = (routes: readonly { path?: string; children?: readonly unknown[] }[]) => {
    for (const route of routes) {
      if (typeof route.path === "string") patterns.push(route.path);
      if (route.children) walk(route.children as never);
    }
  };
  walk(APP_ROUTES as never);
  return patterns;
}

describe("P4.21 — the old refunds address is served, not abandoned", () => {
  it("`/finance/refunds` is a REGISTERED route and not merely a constant", () => {
    // The half the existing case cannot see. `REFUNDS_LEGACY_ROUTE` being the
    // right string says nothing about whether anything answers at it.
    expect(routePatterns()).toContain(REFUNDS_LEGACY_ROUTE.slice(1));
    expect(routePatterns()).toContain(REFUNDS_ROUTE.slice(1));
  });

  it("opening it REDIRECTS to the payments address — no 404, no blank screen", () => {
    const router = openAt(`/${TENANT}${REFUNDS_LEGACY_ROUTE}`);
    // ⚠ **THE TENANT SEGMENT IS IN THE ASSERTION ON PURPOSE.** `DEF-CWP-3925`:
    // a component mounted outside `/:tenant/…` builds `//payments/refunds`, a
    // protocol-relative URL to another host, and `toContain("payments/refunds")`
    // reads it as a perfectly good answer.
    expect(router.state.location.pathname).toBe(`/${TENANT}${REFUNDS_ROUTE}`);
    expect(router.state.location.pathname).not.toContain("/finance/");
  });

  it("it REPLACES rather than pushes, so Back does not bounce off the old address", () => {
    // `<Navigate replace>` — without it a clerk who follows an old bookmark
    // and then presses Back is sent straight back to the redirect and forward
    // again, which is a dead link wearing a working one's clothes. The history
    // stack is the assertion: two entries in, two entries out, with the old
    // address REPLACED rather than a third pushed on top of it.
    const router = openAt(`/${TENANT}/payments`, `/${TENANT}${REFUNDS_LEGACY_ROUTE}`);
    expect(router.state.location.pathname).toBe(`/${TENANT}${REFUNDS_ROUTE}`);
    expect(router.state.historyAction).toBe("REPLACE");
  });

  it("and it lands on the SCREEN, not just at the address (DEF-CWP-3925)", () => {
    // An address is half the proof. The other half is that something a person
    // recognises as Refunds & credits is on the page — the blueprint's own 6·1
    // heading, read out of the catalogue rather than typed here, so a copy
    // change moves the screen and this assertion together.
    openAt(`/${TENANT}${REFUNDS_LEGACY_ROUTE}`);
    const heading = i18n.t("payments.refunds.title");
    expect(heading).not.toContain("payments.refunds."); // the key must resolve
    expect(document.body.textContent).toContain(heading);
  });

  it("the payments address opens the SAME screen, so the redirect is not a detour", () => {
    const router = openAt(`/${TENANT}${REFUNDS_ROUTE}`);
    expect(router.state.location.pathname).toBe(`/${TENANT}${REFUNDS_ROUTE}`);
    expect(document.body.textContent).toContain(i18n.t("payments.refunds.title"));
  });

  it("an address NOBODY declared still does not silently open Refunds", () => {
    // ⚠ **WHAT WOULD MAKE EVERY CASE ABOVE PASS WRONGLY:** a catch-all that
    // rendered the last screen for any address. `/:tenant/*` exists, so this
    // case pins that it does NOT draw this screen — without it, "the refunds
    // heading is on the page" is a sentence about the router's fallback.
    const router = openAt(`/${TENANT}/finance/refunds-that-never-existed`);
    expect(router.state.location.pathname).toBe(`/${TENANT}/finance/refunds-that-never-existed`);
    expect(document.body.textContent).not.toContain(i18n.t("payments.refunds.title"));
  });
});

describe("P4.21 — the screen ID the move left behind (DEF-PAY-6297, fixed)", () => {
  // These cases pinned the WRONG answer on purpose, so the day the rows were
  // added this block went red and named `DEF-PAY-6297`. That happened in
  // 2.445.10 (`700751f97`, `DEF-SHL-6047`) and nobody turned the hold round
  // until `DEF-PAY-10104` found it red. They now assert the corrected ids.

  it("the NEW refunds address wears the Refunds screen's own id — `S58 · FIN-01.refunds`", () => {
    const resolved = resolveScreen(`/${TENANT}${REFUNDS_ROUTE}`);
    expect({ a1: resolved.a1, r10: resolved.r10, route: resolved.route?.path }).toEqual({
      a1: "S58",
      r10: "FIN-01.refunds",
      // Its own row, declared above `payments/:tab`, so `refunds` is never
      // read as an unknown tab that falls back to Summary.
      route: "/:tenant/payments/refunds",
    });
  });

  it("the OLD address still claims `S58 · FIN-01.refunds` over a screen it no longer holds", () => {
    const resolved = resolveScreen(`/${TENANT}${REFUNDS_LEGACY_ROUTE}`);
    expect(resolved.a1).toBe("S58");
    expect(resolved.r10).toBe("FIN-01.refunds");
    // The id is on the DOOR and the room is elsewhere. Harmless to a clerk —
    // the address redirects before any badge renders.
  });

  it("7·3d resolves to its own row, a dotted child of Outstandings", () => {
    const resolved = resolveScreen(`/${TENANT}/payments/outstandings/send-notice`);
    expect(resolved.a1).toBeNull();
    expect(resolved.r10).toBe("PAY-02.send-notice");
    expect(resolved.route?.path).toBe("/:tenant/payments/outstandings/send-notice");
  });

  it("7·2 resolves to its own row and deliberately draws no badge", () => {
    const resolved = resolveScreen(`/${TENANT}/payments/debtors/AC-2026-00001`);
    expect(resolved.a1).toBeNull();
    expect(resolved.r10).toBeNull();
    expect(resolved.route?.path).toBe("/:tenant/payments/debtors/:accountNo");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-138-BRC07 `P4.21` · `P4.10`'s move · blueprint p023 (the task row)
// generated: 2026-09-23 by LANE P4-TESTS
// checklist: A=n/a B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST, through `vitest` — with the
//         `REFUNDS_LEGACY_ROUTE` route line commented out of `App.tsx` the
//         registered-route case failed and the redirect case reported
//         `/brazosbend/finance/refunds` unchanged (the catch-all's *"not
//         found"*), which is the dead link this task exists to forbid.
// exceptions: (1) THE SCREEN-ID BLOCK ASSERTS TODAY'S WRONG ANSWER. It is
//         `DEF-PAY-6297` and it is pinned rather than fixed, for the reason
//         written above the block. (2) `screenIds.test.tsx` IS RED AND WAS RED
//         BEFORE THIS LANE — 16 routed addresses have no registry row, 13 of
//         them older than `fb3526105`. Not fixed here: three rows out of
//         sixteen cannot turn it green, so the fix could not be proved.
// status: VERIFIED-UNRATIFIED
