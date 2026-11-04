// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Defect:  DEF-CWP-4440 — `i18n.changeLanguage` was called NOWHERE in the
//          portal. PO: *"Language setting does not work in customer portal"*.
// Rules:   BR-CWP-105 · hard-won law 2 (built is not wired)
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **THIS FILE ASSERTS THE WIRE AND NOTHING ELSE, AND THAT IS THE POINT.**
// The rule itself is arithmetic and is asserted in `language.test.ts` without
// mounting anything. What no pure test can prove — and what the defect
// actually was — is that **the running application ever calls the applier at
// all**. So every case here mounts `PortalApp`, the component `App.tsx`
// renders, seeds the caches the real pages fill, and watches the real i18next
// instance. Nothing below calls `resolvePortalLanguage` by hand.
//
// ⚠ **AND `PortalApp` IS MOUNTED, NOT `PortalLanguage`.** Mounting the applier
// directly would prove it works and say nothing about whether the portal
// mounts it — which is exactly the gap that let this defect exist: every piece
// on the staff side was correct and the portal simply never called any of it.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";
import { queryKeys } from "@/api/queryClient";

import type { PortalFront } from "../api/guestClient";
import type { PortalSession } from "../api/portalClient";
import { PortalApp } from "../PortalApp";
import { GUEST_LANGUAGE_KEY } from "./language";

afterEach(cleanup);
beforeEach(async () => {
  window.sessionStorage.clear();
  await i18n.changeLanguage("en");
});

const FRONT = (language: string | null): PortalFront => ({
  tenant: {
    slug: "pine-hill",
    name: "Pine Hill Water",
    brand_primary_hex: null,
    brand_accent_hex: null,
  },
  is_live: true,
  regional: { timezone: "America/Chicago", date_format: "DD-MMM-YY", language },
  // `PORTAL_LOCALES` — the two the portal OFFERS (`BR-CWP-106`).
  locales: ["en", "es"],
  cards: [],
  links: { help: false, visit: false },
  services: [],
  strapline: null,
  office_hours_text: null,
  emergency_phone: null,
});

const SESSION = (language: string | null): PortalSession => ({
  customer: { display_name: "Maria Alvarez" },
  accounts: [],
  account_count: 1,
  language,
});

/**
 * Mounts the portal the way `App.tsx` does, with whatever the pages would
 * already have put in the cache.
 *
 * ⚠ **THE ROUTE PATTERN IS THE REAL ONE.** `DEF-CWP-3925`'s own post-mortem:
 * a fixture that mounts a portal component with no `/:tenant/portal` route
 * leaves `useParams().tenant` undefined and every address it builds comes out
 * `//portal/…` — a perfectly good string to `toContain`. Mount under the path
 * the router actually serves or the assertion cannot be written.
 */
function mountPortal(seed: { front?: PortalFront; session?: PortalSession }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  if (seed.front) client.setQueryData(queryKeys.portalFront, seed.front);
  // The literal twenty pages use. Spelling it differently here would subscribe
  // to a cache nobody fills — and would look exactly like "no preference".
  if (seed.session) client.setQueryData(["portal", "session"], seed.session);
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/pine-hill/portal/home"]}>
        <Routes>
          <Route path="/:tenant/portal/*" element={<PortalApp />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("the portal applies a language at all (DEF-CWP-4440)", () => {
  it("applies the UTILITY's language to a guest", async () => {
    expect(i18n.language).toBe("en");
    mountPortal({ front: FRONT("es-MX") });
    await waitFor(() => expect(i18n.language).toBe("es-MX"));
  });

  it("gives a signed-in customer THEIR OWN account language over the utility's", async () => {
    // PO 2026-09-07: *"Signed customer should get their own references."*
    mountPortal({ front: FRONT("es-MX"), session: SESSION("de") });
    await waitFor(() => expect(i18n.language).toBe("de"));
  });

  it("falls back to the utility when the customer has stated none", async () => {
    // `null` is also what the server sends when a login's four accounts
    // disagree, so this is that case too.
    mountPortal({ front: FRONT("es-MX"), session: SESSION(null) });
    await waitFor(() => expect(i18n.language).toBe("es-MX"));
  });

  it("honours a guest's own stored choice over the utility's language", async () => {
    window.sessionStorage.setItem(GUEST_LANGUAGE_KEY, "de");
    mountPortal({ front: FRONT("es-MX") });
    await waitFor(() => expect(i18n.language).toBe("de"));
  });

  it("lets the signed-in customer's account beat a stored guest choice", async () => {
    // Somebody picked German from the top menu and THEN signed in. Their
    // account is their own statement and it is the more considered one.
    window.sessionStorage.setItem(GUEST_LANGUAGE_KEY, "de");
    mountPortal({ front: FRONT("en"), session: SESSION("es-MX") });
    await waitFor(() => expect(i18n.language).toBe("es-MX"));
  });

  // ⚠ **THESE TWO START THE APP IN GERMAN, AND THAT IS NOT DECORATION.** Both
  // assert an outcome of `en`, which is also i18next's own default — so from a
  // clean start each would PASS over an application that applies no language at
  // all, which is the whole defect. Proved: with `<PortalLanguage />` removed
  // from `PortalApp`, six of these eight go red and these two did not.
  // Starting somewhere else makes the assertion a real one: `en` can now only
  // be reached by the applier actually running and actually resolving.
  it("clamps a lawful tenant setting this build has no catalogue for", async () => {
    // `en-US` is one of the server's twelve seeded codes and one of nobody's
    // eleven catalogues.
    await i18n.changeLanguage("de");
    mountPortal({ front: FRONT("en-US") });
    await waitFor(() => expect(i18n.language).toBe("en"));
  });

  it("falls to the BROWSER when the utility has chosen no language", async () => {
    // The chain's tail. jsdom reports `navigator.language` as `en-US`, which
    // clamps to `en` — so a portal that started in German must END in English,
    // by way of the browser step and nothing else.
    await i18n.changeLanguage("de");
    mountPortal({ front: FRONT(null) });
    await waitFor(() => expect(i18n.language).toBe("en"));
  });

  // ═══════════════════════════════════════════════════════════════════════
  // ⚠ **A DECLARED BLIND SPOT, WITH ITS NUMBER — READ THIS BEFORE TRUSTING
  // THIS FILE (law 7's fifth shape).** These NINE cases prove the language is
  // resolved and applied. **NOT ONE OF THEM can see the regression that
  // actually shipped past them on 2026-09-07**, and it is worth naming
  // exactly:
  //
  //   On a real first load the FRAME came out Spanish — *Inicio · Ayuda ·
  //   Horario de atención* — and the CARD inside it stayed ENGLISH —
  //   *Welcome back · Password · Sign in · OR* — on one screen, at one moment,
  //   with `i18n.language` reading `es-MX` and `t()` answering *Entrar* when
  //   asked by hand. Walking to another screen and back fixed it.
  //
  // The mechanism is effect ORDER: `<PortalLanguage />` is an earlier sibling
  // than `{element}` in `PortalApp`, so `changeLanguage` fires before the
  // screens below attach their own `languageChanged` listeners; they have
  // already rendered with the English `t` and never hear the event.
  // `PortalApp` now calls `useTranslation()` itself so `useRoutes` rebuilds
  // the tree, which is the shape `ShellWithSession` has always had on the
  // staff side and the reason the staff app never had this bug.
  //
  // **REMOVING THAT LINE LEAVES ALL NINE CASES HERE GREEN — measured, not
  // assumed.** jsdom cannot reproduce it: with no server every screen's own
  // query settles and re-renders it, which hides the missed event. The guard
  // that DOES catch it is the browser walkthrough,
  // `10-scripts/render-checks/def-cwp-4440-portal-language.mjs` step 5, which
  // opens a screen on a FRESH LOAD and reads the card. That is hard-won law 6
  // in one sentence: no gate here looks at rendered output.
  // ═══════════════════════════════════════════════════════════════════════
  it("the rendered SCREEN follows the language, not only the i18n instance", async () => {
    // What this DOES prove: the words a person reads change when the tenant's
    // language arrives, rather than only the instance's `language` property.
    // What it does NOT prove is the paragraph above.
    //
    // ⚠ **THE ORDER IS PART OF THE TEST.** A first draft seeded the front into
    // the cache and then mounted, so everything rendered once already knowing
    // the language — the sequence under test never happened. The real load
    // order is: screens render FIRST, in English; the language arrives after.
    //
    // ⚠ **NO CATALOGUE STRING IS HARDCODED.** The rendering before and after
    // are compared, so this stays true when copy is reworded.
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: Infinity } },
    });
    const { container } = render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/pine-hill/portal/home"]}>
          <Routes>
            <Route path="/:tenant/portal/*" element={<PortalApp />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect((container.textContent ?? "").length).toBeGreaterThan(10));
    const beforeTheLanguageArrives = container.textContent ?? "";
    expect(i18n.language).toBe("en");

    // The tenant's language lands, exactly as the real fetch does.
    client.setQueryData(queryKeys.portalFront, FRONT("es-MX"));
    await waitFor(() => expect(i18n.language).toBe("es-MX"));
    await waitFor(() =>
      expect(container.textContent ?? "").not.toBe(beforeTheLanguageArrives),
    );
  });

  it("does NOT fetch the session — a guest must not be 401'd on every page", async () => {
    // ⚠ THE CHECK THAT PROTECTS THE GUEST HALF. `PortalLanguage` subscribes to
    // the session cache with `enabled: false`. If a later lane removes that,
    // every visitor on every portal page fires `GET /portal/session`, is
    // refused, and burns a signed-in throttle slot — with nothing visibly
    // wrong. A query client with no queryFn that could succeed makes the
    // attempt observable.
    const calls: string[] = [];
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const original = client.getQueryCache().build.bind(client.getQueryCache());
    client.getQueryCache().build = ((c: unknown, options: { queryKey: unknown }) => {
      calls.push(JSON.stringify(options.queryKey));
      return original(c as never, options as never);
    }) as typeof original;
    client.setQueryData(queryKeys.portalFront, FRONT("es-MX"));
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/pine-hill/portal/home"]}>
          <Routes>
            <Route path="/:tenant/portal/*" element={<PortalApp />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(i18n.language).toBe("es-MX"));
    const sessionQuery = client.getQueryState(["portal", "session"]);
    // Subscribed (so it re-renders when a page fills it) but never fetched.
    expect(sessionQuery?.fetchStatus ?? "idle").toBe("idle");
    expect(sessionQuery?.data).toBeUndefined();
  });
});
