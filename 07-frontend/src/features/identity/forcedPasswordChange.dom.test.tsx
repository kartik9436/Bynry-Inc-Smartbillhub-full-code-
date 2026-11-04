// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-IDN-5653 — every invited user is locked out. Sign-in SUCCEEDS,
//          redirects to `/change-password`, and that screen did not exist.
// Rules:   BR-IDN-022 (forced change on first sign-in) · BR-IDN-011 (a
//          successful forced change ACTIVATES an invited membership) ·
//          BR-IDN-005 (it revokes every prior session, and KEEPS this one).
// ───────────────────────────────────────────────────────
/**
 * ⚠ **THE ASSERTION THAT WAS MISSING IS THE POINT OF THIS FILE.**
 *
 * `SignInPage` already had tests, and they passed throughout. They asserted
 * the route CONSTANT — that a user with `must_change_password` is sent to
 * `FORCED_PASSWORD_CHANGE_ROUTE`. That is a statement about a STRING, and a
 * string is satisfied by a destination that does not exist. `tsc` was happy,
 * every test was green, and the address had nothing behind it, so a user who
 * signed in correctly landed on a blank screen and could never clear the flag
 * that put them there — **not recoverable by retrying, and not by resetting
 * the password, because a reset sets the same flag again.**
 *
 * So these cases assert the DESTINATION RENDERS, never that a constant equals
 * a string. That is hard-won law 2's mirror: a live door onto a screen nobody
 * built, and no gate in this repo reads rendered output (law 6).
 *
 * ⚠ **AND THE FIRST FOUR CASES WERE NOT ENOUGH, WHICH IS WORTH RECORDING
 * BECAUSE THEY WERE WRITTEN AS THE RED PROOF AND TWO OF THEM WERE GREEN ON THE
 * DEFECT.** The catch-all does not render the words *"not built"* — it renders
 * the app shell, which renders a LOADING SKELETON while it fetches settings the
 * server refuses to serve to this exact user. So *"the html is longer than 200
 * characters and does not say not-built"* passed over the broken screen, and so
 * did *"there is no `<nav>`"*: a skeleton has no nav either. **A check that a
 * SKELETON satisfies is a check about nothing**, and both are now written
 * against the things only the real screen has — two password boxes and the
 * screen's own `data-page` handle. Each was re-run against the unregistered
 * route and shown RED before it was trusted green (law 7).
 *
 * ⚠ **AND EVEN THESE CANNOT SEE THE DEFECT THAT ACTUALLY SHIPPED IN THE FIRST
 * BUILD OF THE SCREEN, WHICH IS WHY THE WALKTHROUGH EXISTS.** `renderAt` SEEDS
 * `queryKeys.me`. The product did not: `SignInPage` threw the sign-in response
 * away, so on the one path that matters the cache was EMPTY, and a screen that
 * treated absence as "not signed in" bounced the invited user straight back to
 * the door they had just come through. Every case here passed throughout.
 * `10-scripts/def_idn_5653_forced_password_walkthrough.mjs` is what found it.
 * **A fixture that seeds state the product never produces will make a broken
 * screen look correct.**
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, useRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import type { SessionUser } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { splitPasswordRefusal } from "@/features/identity/ChangePasswordPage";
import {
  DASHBOARD_ROUTE,
  FORCED_PASSWORD_CHANGE_ROUTE,
  routeAfterSignIn,
} from "@/features/identity/SignInPage";

/** ⚠ **A USER WHO MUST CHANGE THEIR PASSWORD**, which is the only state this
 *  screen is ever reached in. Seeding `must_change_password: false` would put
 *  the harness in a state the screen never sees. */
const FORCED: SessionUser = {
  id: "u-forced",
  full_name: "Sam Reyes",
  email: "sam.reyes@sample.test",
  phone: null,
  role: "billing_clerk",
  role_name: "Billing Clerk",
  must_change_password: true,
};

function RoutedApp() {
  return useRoutes(APP_ROUTES as never);
}

/** The app's own route table, rendered at one address exactly as the router
 *  resolves it — never a component mounted bare, and never without the
 *  providers the real app supplies. The first draft of this helper omitted
 *  them and every case failed inside `useTranslation` — **red for the wrong
 *  reason, which proves nothing** (hard-won law 7), and it would have been
 *  trusted as a red proof of the missing screen. */
function renderAt(path: string, session: SessionUser = FORCED): string {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  queryClient.setQueryData(queryKeys.me, session);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <RoutedApp />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Every `path` the route table declares, at every depth. */
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

const TENANT = "brazosbend";
const FORCED_PATH = `/${TENANT}${FORCED_PASSWORD_CHANGE_ROUTE}`;

describe("DEF-IDN-5653 · the forced-change screen a temp password sends you to", () => {
  it("the address the sign-in redirect names is a registered route", () => {
    // ⚠ Asserted against the ROUTE TABLE rather than by eye: a `*` catch-all
    // matches every address, so "it rendered something" proves nothing at all.
    //
    // ⚠ And asserted against `SignInPage`'S OWN CONSTANT rather than against
    // the literal `"change-password"`. That is the durable half: the door and
    // the room behind it are now ONE string, so a lane that renames the route
    // cannot leave the redirect pointing at the old one — which is exactly the
    // shape of this defect.
    expect(routePatterns()).toContain(FORCED_PASSWORD_CHANGE_ROUTE.slice(1));
  });

  it("every destination the sign-in redirect can choose is a registered route", () => {
    // THE PREVENTION THE DEFECT ASKED FOR, and it is deliberately written over
    // the FUNCTION rather than over the two constants: `routeAfterSignIn` is
    // the only thing that decides where a signed-in user lands, so walking its
    // two answers is walking every door sign-in has. A third branch added later
    // arrives here with no test unless this case is updated — which is the
    // point, because `/change-password` was a third door nobody checked.
    const patterns = routePatterns();
    for (const user of [FORCED, { ...FORCED, must_change_password: false }]) {
      expect(patterns).toContain(routeAfterSignIn(user).slice(1));
    }
    // The pair is named so a reader can see WHICH two without running it.
    expect([
      routeAfterSignIn(FORCED),
      routeAfterSignIn({ ...FORCED, must_change_password: false }),
    ]).toEqual([FORCED_PASSWORD_CHANGE_ROUTE, DASHBOARD_ROUTE]);
  });

  it("renders the screen itself, not the shell's loading skeleton", () => {
    // ⚠ THIS IS THE CASE THAT WAS GREEN ON THE DEFECT. It used to ask only
    // that the markup was longer than 200 characters and did not say "not
    // built" — both true of the skeleton the catch-all rendered inside the
    // shell, which is what the PO photographed. It now asks for the screen's
    // OWN handle, which nothing else in the product renders.
    const html = renderAt(FORCED_PATH);
    expect(html).toContain('data-page="change-password"');
    expect(html).not.toContain("skeleton");
    expect(html).not.toMatch(/not built|isn't built|coming soon/i);
  });

  it("asks for the new password twice and never for the old one", () => {
    // BR-IDN-022 — on a FORCED change `services.change_password` does not read
    // `current_password` at all. Asking for it would be a field the server
    // ignores, in front of a user who by definition only has a temporary one.
    const html = renderAt(FORCED_PATH);
    expect(html.match(/type="password"/g) ?? []).toHaveLength(2);
    expect(html.toLowerCase()).not.toContain("current password");
    // …and the two boxes are the NEW-password pair, told apart by the
    // credential-manager hint rather than by their labels, which translate.
    expect(html.match(/autocomplete="new-password"/gi) ?? []).toHaveLength(2);
  });

  it("renders OUTSIDE the app shell, because it gates every app screen", () => {
    // `App.tsx`'s own comment required this: "When that screen lands it must
    // render OUTSIDE the shell, since it gates every app screen." A user who
    // must change their password must not be able to navigate away from it —
    // and, the half that actually bit, the shell cannot even BOOT here: every
    // read it makes is refused 403 while the flag is set.
    //
    // ⚠ The old version of this case asked only that there was no `<nav>`. A
    // skeleton has no nav either, so it passed on the broken screen. It now
    // asserts the screen IS there and the shell's own furniture is NOT.
    const html = renderAt(FORCED_PATH);
    expect(html).toContain('data-page="change-password"');
    expect(html).not.toMatch(/<nav|sidebar|role="navigation"/i);
    expect(html).not.toContain("foot-menu"); // the shell's user menu
  });

  it("sends a user who owes no change to the product instead of an unusable form", () => {
    // The screen collects no current password, so a voluntary change would be
    // refused by the server. Rather than draw a form that cannot succeed, it
    // steps out of the way. ⚠ Only a POSITIVE answer moves anybody: ABSENCE of
    // a session must NOT, which is the defect the walkthrough caught.
    const html = renderAt(FORCED_PATH, { ...FORCED, must_change_password: false });
    expect(html).not.toContain('data-page="change-password"');
  });
});

describe("DEF-IDN-5653 · the tenant's password rules come from the server's refusal", () => {
  // The screen cannot READ the policy: `identity/auth.py`'s
  // `_FORCED_CHANGE_EXEMPT` admits only `POST /me/password` and
  // `DELETE /auth/session` while a change is owed, so
  // `GET /settings/security-policy` answers 403 for exactly this user —
  // measured against a running server, not inferred. The rules therefore
  // arrive as `field_errors` on the refusal, and this is the split that puts
  // them on the field instead of printing a form-level sentence that points at
  // a list the screen does not draw.
  it("puts every broken rule on its field and drops the form-level line", () => {
    const split = splitPasswordRefusal({
      message_key: "errors.identity.password_policy",
      field_errors: [
        {
          field: "new_password",
          message_key: "errors.identity.password_too_short",
          params: { min_length: 12 },
        },
        { field: "new_password", message_key: "errors.identity.password_needs_symbol" },
      ],
    });
    expect(split.fieldMessages.map((entry) => entry.key)).toEqual([
      "errors.identity.password_too_short",
      "errors.identity.password_needs_symbol",
    ]);
    // The tenant's OWN minimum rides along — never a number this screen holds.
    expect(split.fieldMessages[0].params).toEqual({ min_length: 12 });
    // ⚠ NULL, and that is the assertion. `errors.identity.password_policy`
    // reads "…doesn't meet the rules below", and there are no rules below on
    // this screen — the field messages ARE the rules.
    expect(split.formKey).toBeNull();
  });

  it("keeps the form-level line when the refusal names no field", () => {
    const split = splitPasswordRefusal({
      message_key: "errors.identity.temp_password_expired",
      params: {},
    });
    expect(split.fieldMessages).toEqual([]);
    expect(split.formKey).toBe("errors.identity.temp_password_expired");
  });
});
