// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CWP-4440 — the wire that was missing. `i18n.changeLanguage` was
//          called in ONE place in the whole application and it was the staff
//          shell; this is the portal's.
// Rules:   BR-CWP-105 (the order) · BR-CWP-021 (a customer fact never travels
//          on the guest surface, which is why there are two payloads)
// Tests:   src/portal/components/PortalLanguage.dom.test.tsx
// Impacts: src/portal/PortalApp.tsx (its only mount point)
// ───────────────────────────────────────────────────────
//
// THE ONE PLACE THE PORTAL APPLIES A LANGUAGE.
//
// ⚠ **WHY HERE AND NOT IN THE TWO FRAMES, WHICH IS WHERE `PortalRegionalProvider`
// LIVES.** The date format is a VALUE a component renders, so it belongs in a
// context published by the frame every screen passes through. A language is a
// SIDE EFFECT on one global i18next instance. `PortalShell` and `GuestFrame`
// are re-mounted by every page — that is `DEF-CWP-3900`'s own finding, in this
// same folder — so applying it there would re-run the effect on every
// navigation, and the guard would be doing real work rather than being a
// formality. `PortalApp` is mounted ONCE for the life of the portal, which is
// exactly what a global side effect wants and is the same argument
// `ShellWithSession` makes on the staff side.
//
// ⚠ **AND IT RENDERS NOTHING, DELIBERATELY.** Anything visible here would be
// outside both frames and would draw above the header on every portal screen.
// The one thing a reader can see is the language everything else is in.
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import { queryKeys } from "@/api/queryClient";

import { getPortalFront } from "../api/guestClient";
import { getSession } from "../api/portalClient";
import { readerLocale } from "./languageName";
import { readGuestLanguage, resolvePortalLanguage } from "./language";

/**
 * Applies `BR-CWP-105`'s language to the whole portal. Renders nothing.
 */
export function PortalLanguage() {
  const { i18n } = useTranslation();

  // The tenant's own default. Anonymous, cheap, and every portal page already
  // reads it under this very key — so react-query serves this from the cache
  // and it costs no second request.
  const frontQuery = useQuery({
    queryKey: queryKeys.portalFront,
    queryFn: () => getPortalFront(api),
  });

  // ⚠ **`enabled: false` IS LOAD-BEARING AND IS NOT A DISABLED QUERY.** It
  // subscribes to the session cache and NEVER fetches. That is the whole
  // point: this component is mounted on the guest half of the portal too, and
  // a `GET portal/session` from here would answer **401 for every visitor on
  // every page** — an error in their console, a hit against the signed-in
  // throttle, and a request whose only purpose is to be refused. Every
  // signed-in page already fetches the session under this key before it
  // renders its shell, so by the time a customer can see anything the cache is
  // warm and this observer re-renders with it.
  //
  // ⚠ **THE KEY IS THE LITERAL THE PAGES USE.** `["portal", "session"]` is not
  // in `queryKeys` — twenty pages spell it out — so spelling it differently
  // here would silently subscribe to a cache nobody fills, and the customer's
  // own language would never arrive. It is the kind of miss that looks exactly
  // like *the customer has no preference*.
  const sessionQuery = useQuery({
    queryKey: ["portal", "session"],
    queryFn: () => getSession(api),
    enabled: false,
  });

  const wanted = resolvePortalLanguage({
    account: sessionQuery.data?.language ?? null,
    guestChoice: readGuestLanguage(),
    tenant: frontQuery.data?.regional.language ?? null,
    // `readerLocale` is the function the help routes already fill `?locale=`
    // with (`BR-CWP-094`). Reusing it rather than reading `navigator` again
    // keeps one answer to *what does this stranger read*.
    browser: readerLocale("en"),
  });

  useEffect(() => {
    // Guard on inequality — the staff shell's own reasoning, transferred:
    // `changeLanguage` on every render would refetch the catalog chunk and
    // reset any switch already in flight.
    if (wanted !== null && i18n.language !== wanted) {
      void i18n.changeLanguage(wanted);
    }
  }, [wanted, i18n]);

  return null;
}
