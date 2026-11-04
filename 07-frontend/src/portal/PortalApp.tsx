// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-001 (EP-CWP-01) — the portal's own root, mounted at
//           `/:tenant/portal/*` (CR-068 §11c). Screens: CWP-001
// Rules:    BR-CWP-007 (`/{tenant}/portal/…` — the PO's ruling read literally:
//           the tenant first, `portal` second; CR-068 §0 row 3 — the bare
//           tenant root stays the staff app's) · BR-CWP-011 (a second
//           application root: it shares no shell, no session and no role
//           model with the staff app) · CR-068 §11c (*"Not a `features/`
//           folder"*)
// Tests:    src/portal/routing/screenIds.test.ts · src/portal/guest/FrontPage.test.tsx
// Impacts:  src/App.tsx (one route, a sibling of the staff shell)
// ───────────────────────────────────────────────────────
import { useRoutes } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { HeadingLevelProvider } from "@/components/HeadingLevel";

import { PortalA11y } from "./components/a11y";
import { PortalDocumentTitle } from "./components/PortalDocumentTitle";
import { PortalLanguage } from "./components/PortalLanguage";
import { PortalScreenIdTag } from "./components/PortalScreenIdTag";
import { PORTAL_ROUTES } from "./routing/portalRoutes";
import { CurrentAccountProvider } from "./shell/currentAccount";
import { useQuery } from "@tanstack/react-query";
import type { CSSProperties } from "react";

import { queryKeys } from "@/api/queryClient";

import type { PortalFront } from "./api/guestClient";
import { brandStyle } from "./shell/GuestFrame";

/** The ink (and the utility's colour) for a portal state drawn OUTSIDE both
 *  frames — the sign-in wall a signed-out visitor meets on 36 account pages,
 *  and the three frameless *not found* addresses. Group A ruling 3(a),
 *  PO/QA 2026-10-23; inventory `group-a-inventory.md` §6.2 (1): the wall's
 *  *Retry* / *Sign in* drew `#f3f2f2` on `#ec3013` (3.76) and ignored the
 *  utility's own colour, because the inks were set only on the frames.
 *
 *  ⚠ It READS the front-page cache and never fetches (`enabled: false`): every
 *  page that can draw the wall has already asked for the front page under this
 *  key, so this adds no request. Before that answer exists the stock accent's
 *  inks apply — the same thing a frame writes for a utility with no colour. */
export function usePortalRootStyle(): CSSProperties {
  const front = useQuery<PortalFront>({ queryKey: queryKeys.portalFront, enabled: false });
  return brandStyle(front.data?.tenant ?? ({ brand_primary_hex: null } as unknown as PortalFront["tenant"]));
}

/**
 * Everything under `/{tenant}/portal`. The route table is `PORTAL_ROUTES`.
 *
 * ⚠ **`CurrentAccountProvider` WRAPS `useRoutes`, AND THE ORDER IS THE WHOLE
 * POINT** (`BR-CWP-010`, `DEF-CWP-3900`). This component is mounted once for
 * the life of the portal; everything inside it is re-mounted on every tab
 * change. The chosen account therefore has to be held HERE — held one level
 * down, inside `PortalShell`, it is thrown away by the navigation it is
 * supposed to survive, which is what shipped and what a customer experienced
 * as the switcher silently resetting to their first account.
 *
 * ⚠ **`PortalLanguage` IS MOUNTED HERE FOR THE SAME REASON, AND ITS ABSENCE IS
 * WHY THIS FILE HAD ZERO i18n REFERENCES UNTIL 2026-09-07** (`DEF-CWP-4440`,
 * `BR-CWP-105`). The Product Owner, on the running product: *"Language setting
 * does not work in customer portal"* — and it did not, anywhere, because
 * `i18n.changeLanguage` was called in exactly ONE place in the whole
 * application and that place was `components/ShellWithSession.tsx`, the STAFF
 * shell. The portal is that shell's SIBLING in `App.tsx`, not a descendant, so
 * it inherited none of the wiring and **nothing went red**: every portal string
 * resolved, in English, and every test asserted the English it was written
 * against. **A second shell inherits none of the first shell's wiring** — the
 * date format was the same hole one field over (`DEF-CWP-3994`), and this is
 * the last of it.
 *
 * Applying a language is a SIDE EFFECT on one global i18next instance rather
 * than a value a component renders, so it belongs where a component is mounted
 * ONCE — here, beside the account above it — and not in `PortalShell` or
 * `GuestFrame`, which every page re-mounts. It renders nothing.
 */
export function PortalApp() {
  // ⚠ **THIS SUBSCRIPTION IS THE FIX, NOT DECORATION, AND THE WALKTHROUGH IS
  // THE ONLY THING THAT FOUND IT (`DEF-CWP-4440`, 2026-09-07).** `useRoutes`
  // BUILDS the screen elements, so unless THIS component re-renders when the
  // language changes, `element` stays the object it already was and React
  // reuses that subtree untouched.
  //
  // What that looked like on a real first load: the FRAME was Spanish —
  // *Inicio · Ayuda · Horario de atención* — and the CARD inside it was
  // English — *Welcome back · Password · Sign in · OR* — on the same screen,
  // at the same moment, with `i18n.language` reading `es-MX` and `t()`
  // returning *Entrar* when asked by hand. Walking to another screen and back
  // fixed it, because that screen mounted after the switch. **Every unit test
  // passed**: they assert `i18n.language`, and `i18n.language` was right.
  //
  // The mechanism is effect ORDER. `<PortalLanguage />` is an earlier sibling
  // than `{element}`, so its effect runs — and `changeLanguage` fires — before
  // the screens below have attached their own `languageChanged` listeners.
  // They had already rendered with the English `t` and never heard the event.
  //
  // ⚠ **THE STAFF SHELL NEVER HAD THIS BUG AND THE DIFFERENCE IS THE WHOLE
  // LESSON.** `ShellWithSession` applies the language AND is the layout route
  // the staff screens render inside, so its own re-render carries them with
  // it. An applier that renders `null` BESIDE the screens reaches nothing.
  // Subscribing here restores that shape: the component that produces the
  // screens is the component that hears the language change.
  useTranslation();
  const element = useRoutes(PORTAL_ROUTES);
  const rootStyle = usePortalRootStyle();
  return (
    <CurrentAccountProvider>
      {/* ⚠ **`data-portal` IS THE PORTAL'S ROOT MARK AND IT IS LOAD-BEARING,
          NOT A TEST HANDLE (`CR-085`, B14 rule 39).** `styles/global.css`
          restores the browser's own `p { margin-block: 1em }` for the STAFF
          app, where 84 paragraphs have no margin of their own and run their
          text together without it. In the portal that same declaration put
          **17px** between an input and its helper where rule 39 ratifies 6 —
          and because it is `1em` it is a different number at every font size,
          so no fixed scale can contain it. One rule in `global.css`
          (`[data-portal] p`) turns it off here and leaves every staff screen
          byte-identical.

          ⚠ **IT WRAPS THE WHOLE PORTAL AND NOT EACH FRAME.** `PortalShell`
          and `GuestFrame` carry `data-portal-frame`, but three of the fifty
          portal addresses render neither — `/help/:slug`, `/visit` and
          `/visit/:slug` all answer *"We could not find that"* outside a
          frame. A reset that covered 47 of 50 would be the second spacing
          scale this rule exists to prevent.

          A plain `<div>` with no layout of its own: the shell below sets
          `min-h-screen`, which is viewport-relative and unaffected by an
          ancestor. */}
      <div data-portal="" style={rootStyle}>
        <PortalLanguage />
        {/* `DEF-CWP-10562` — every page's tab title is its own heading and the
            utility's name. Mounted once, here, so no route can be born
            without one. */}
        <PortalDocumentTitle />
        {/* F-02 / F-04 (`DEF-CWP-10547`, `DEF-CWP-10552`): the announcer, the
            focus rescue and route focus, mounted ONCE here because every frame
            below is re-mounted on every navigation — an announcer inside a
            frame would be torn down by the very page change it must speak. */}
        <PortalA11y>
          {/* `DEF-CWP-10563` — the portal keeps an outline: the page head is
              the one h1, so a section heading drawn at the top of a page is an
              h2 and each section hands the next level to what it contains.
              The staff app sets no level and its kit renders exactly as
              before. */}
          <HeadingLevelProvider level={2}>{element}</HeadingLevelProvider>
        </PortalA11y>
        <PortalScreenIdTag />
      </div>
    </CurrentAccountProvider>
  );
}
